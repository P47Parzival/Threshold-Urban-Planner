import { useState, useEffect } from 'react';
// @ts-ignore - google-map-react types may not be available
import GoogleMapReact from 'google-map-react';
import './Dashboard.css';

interface TimelineMarker {
  index: number;
  date: string;
  dateObj: Date;
  isYearStart: boolean;
  isMonthStart: boolean;
  position: number;
}

export default function Maps() {
  const [activeNasaLayer, setActiveNasaLayer] = useState<string | null>('lst');
  const [mapInstance, setMapInstance] = useState<any>(null);
  const [mapsInstance, setMapsInstance] = useState<any>(null);
  const [currentOverlay, setCurrentOverlay] = useState<any>(null);
  const [selectedDate, setSelectedDate] = useState<string>('2025-09-22');
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [aoiBounds, setAoiBounds] = useState<any>(null);
  const [isSelectingAOI, setIsSelectingAOI] = useState<boolean>(false);
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [timelinePosition, setTimelinePosition] = useState<number>(0);
  const [drawingManager, setDrawingManager] = useState<any>(null);
  const [aoiRectangle, setAoiRectangle] = useState<any>(null);
  const [containerWidth, setContainerWidth] = useState<number>(1000);
  const [, setPopulationData] = useState<any>(null);
  const [populationOverlays, setPopulationOverlays] = useState<any[]>([]);

  // Viewport-based loading states
  const [currentViewport, setCurrentViewport] = useState<any>(null);
  const [currentZoom, setCurrentZoom] = useState<number>(10);
  const [isLoadingViewport, setIsLoadingViewport] = useState<boolean>(false);
  const [lastLoadedViewport, setLastLoadedViewport] = useState<any>(null);

  const defaultProps = {
    center: {
      lat: 23.218682,
      lng: 72.607738
    },
    zoom: 11
  };

  // Helper function to get timeline markers with proper spacing
  const getTimelineMarkers = (dateRange: string[], maxPosition: number, containerWidth: number = 1000): TimelineMarker[] => {
    // Calculate how many pixels each position takes
    const pixelsPerPosition = containerWidth / maxPosition;

    // Adjust minimum spacing based on screen size
    let minMarkerSpacing = 40; // Base spacing
    if (containerWidth > 1400) minMarkerSpacing = 30; // More markers on very wide screens
    else if (containerWidth > 1000) minMarkerSpacing = 35; // Moderate spacing on large screens
    else if (containerWidth < 600) minMarkerSpacing = 60; // Fewer markers on small screens

    const skipInterval = Math.max(1, Math.floor(minMarkerSpacing / pixelsPerPosition));

    const markers: TimelineMarker[] = [];

    dateRange.forEach((date: string, index: number) => {
      const dateObj = new Date(date);
      const isYearStart = dateObj.getMonth() === 0 && dateObj.getDate() <= 8;
      const isMonthStart = dateObj.getDate() <= 8;

      // Always show year markers, adjust month marker frequency based on available space
      const shouldShowMarker = isYearStart || (isMonthStart && index % skipInterval === 0);

      if (shouldShowMarker) {
        markers.push({
          index,
          date,
          dateObj,
          isYearStart,
          isMonthStart: isMonthStart && !isYearStart,
          position: (index / maxPosition) * 100
        });
      }
    });

    return markers;
  };

  // Track container width for responsive markers
  useEffect(() => {
    const updateWidth = () => {
      const container = document.querySelector('.timeline-slider-container') as HTMLElement;
      if (container) {
        setContainerWidth(container.offsetWidth);
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  // NASA GIBS tile URLs
  const getNasaTileUrl = (layer: string) => {
    const baseUrl = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';

    const layerConfigs = {
      lst: {
        name: 'MODIS_Terra_Land_Surface_Temp_Day',
        level: 'GoogleMapsCompatible_Level7'
      },
      ndvi: {
        name: 'MODIS_Terra_NDVI_8Day',
        level: 'GoogleMapsCompatible_Level9'
      }
    };

    const config = layerConfigs[layer as keyof typeof layerConfigs];
    if (!config) return null;

    return `${baseUrl}/${config.name}/default/${selectedDate}/${config.level}/{z}/{y}/{x}.png`;
  };

  const createNasaOverlay = (_map: any, maps: any, layer: string) => {
    const tileUrl = getNasaTileUrl(layer);
    if (!tileUrl) return null;

    const imageMapType = new maps.ImageMapType({
      getTileUrl: (coord: any, zoom: number) => {
        return tileUrl
          .replace('{z}', zoom.toString())
          .replace('{x}', coord.x.toString())
          .replace('{y}', coord.y.toString());
      },
      tileSize: new maps.Size(256, 256),
      maxZoom: 18,
      minZoom: 1,
      name: layer === 'lst' ? 'Land Surface Temperature' : 'Vegetation Index (NDVI)',
      opacity: 0.75
    });

    return imageMapType;
  };

  const updateNasaLayer = (layer: string | null) => {
    if (!mapInstance || !mapsInstance) return;

    // Remove current overlay
    if (currentOverlay) {
      mapInstance.overlayMapTypes.removeAt(0);
      setCurrentOverlay(null);
    }

    // Clear population overlays if switching away from population layer
    if (layer !== 'population' && populationOverlays.length > 0) {
      populationOverlays.forEach(overlay => overlay.setMap(null));
      setPopulationOverlays([]);
    }

    // Add new overlay based on layer type
    if (layer === 'population') {
      // Use viewport-based loading if map is ready and suitable, otherwise load Ahmedabad region
      if (mapInstance && currentViewport && isViewportSuitableForLoading(currentViewport, currentZoom)) {
        console.log('🎯 Using viewport-based population loading');
        loadViewportPopulationData(currentViewport, currentZoom);
      } else {
        console.log('🏙️ Map not ready or viewport too large, loading Ahmedabad region');
        loadAhmedabadPopulationData();
      }
    } else if (layer) {
      const overlay = createNasaOverlay(mapInstance, mapsInstance, layer);
      if (overlay) {
        mapInstance.overlayMapTypes.push(overlay);
        setCurrentOverlay(overlay);
      }
    }
  };

  // Debounced function to prevent too many API calls during map navigation
  const debouncedLoadViewportPopulation = (() => {
    let timeoutId: NodeJS.Timeout;
    return (bounds: any, zoom: number) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        loadViewportPopulationData(bounds, zoom);
      }, 800); // Wait 800ms after user stops moving/zooming
    };
  })();

  // Function to check if viewport is suitable for data loading
  const isViewportSuitableForLoading = (bounds: any, zoom: number): boolean => {
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    const latSpan = ne.lat() - sw.lat();
    const lngSpan = ne.lng() - sw.lng();
    const area = latSpan * lngSpan;

    console.log(`🔍 Viewport check: area=${area.toFixed(1)}°², zoom=${zoom}`);

    // Prevent global viewport loading
    if (area > 50000) {
      console.log('🚫 Viewport too large for loading (global view)');
      return false;
    }

    // Require minimum zoom level for loading
    if (zoom < 6) {
      console.log('🚫 Zoom level too low for loading (zoom in more)');
      return false;
    }

    return true;
  };

  // Function to check if viewport has changed significantly
  const hasViewportChangedSignificantly = (newBounds: any, oldBounds: any, newZoom: number, oldZoom: number): boolean => {
    if (!oldBounds || Math.abs(newZoom - oldZoom) >= 2) {
      return true; // Always reload on significant zoom change
    }

    const newNE = newBounds.getNorthEast();
    const newSW = newBounds.getSouthWest();
    const oldNE = oldBounds.getNorthEast();
    const oldSW = oldBounds.getSouthWest();

    // Check if viewport moved more than 50% of current view
    const latDiff = Math.abs(newNE.lat() - oldNE.lat()) + Math.abs(newSW.lat() - oldSW.lat());
    const lngDiff = Math.abs(newNE.lng() - oldNE.lng()) + Math.abs(newSW.lng() - oldSW.lng());
    const currentLatSpan = newNE.lat() - newSW.lat();
    const currentLngSpan = newNE.lng() - newSW.lng();

    return (latDiff / currentLatSpan > 0.5) || (lngDiff / currentLngSpan > 0.5);
  };

  // Function to load population data for current viewport with Level-of-Detail
  const loadViewportPopulationData = async (bounds: any, zoom: number) => {
    try {
      // 🚨 CRITICAL: Check if viewport is suitable for loading
      if (!isViewportSuitableForLoading(bounds, zoom)) {
        console.log('🚫 Viewport loading cancelled - not suitable');
        setIsLoadingViewport(false);
        return;
      }

      // Check if we should reload (significant viewport change)
      if (lastLoadedViewport && !hasViewportChangedSignificantly(bounds, lastLoadedViewport.bounds, zoom, lastLoadedViewport.zoom)) {
        console.log('🔄 Viewport change not significant enough, skipping reload');
        return;
      }

      setIsLoadingViewport(true);

      const ne = bounds.getNorthEast();
      const sw = bounds.getSouthWest();

      const north = ne.lat();
      const south = sw.lat();
      const east = ne.lng();
      const west = sw.lng();

      console.log(`🗺️ Loading viewport population data: bounds=(${west.toFixed(3)},${south.toFixed(3)},${east.toFixed(3)},${north.toFixed(3)}), zoom=${zoom}`);

      const response = await fetch(`http://localhost:8000/api/population/density/viewport?north=${north}&south=${south}&east=${east}&west=${west}&zoom_level=${zoom}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Viewport population data error:', response.status, errorText);
        throw new Error(`Backend error (${response.status}): ${errorText}`);
      }

      const data = await response.json();
      console.log('✅ Viewport population data loaded:', data.metadata);

      if (data.features && data.features.length > 0) {
        // Clear existing population overlays
        populationOverlays.forEach(overlay => overlay.setMap(null));
        setPopulationOverlays([]);

        setPopulationData(data);
        createPopulationChoropleth(data);

        // Update last loaded viewport
        setLastLoadedViewport({ bounds, zoom });

        console.log(`🎯 Loaded ${data.features.length} features for ${data.metadata.viewport?.lod_level || 'unknown'} detail level`);

        // Show LOD info to user
        if (data.metadata.viewport) {
          const lodInfo = `📊 Level: ${data.metadata.viewport.lod_level} | Features: ${data.features.length} | Zoom: ${zoom}`;
          console.log(lodInfo);
        }
      } else {
        console.warn('⚠️ No population features found in current viewport');
        // Don't clear existing data, just keep what we have
      }
    } catch (error) {
      console.error('❌ Error loading viewport population data:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);

      if (errorMessage.includes('Failed to fetch')) {
        console.warn('⚠️ Cannot connect to backend for viewport data');
      } else {
        console.error(`❌ Error loading viewport population data: ${errorMessage}`);
      }
    } finally {
      setIsLoadingViewport(false);
    }
  };

  // Function to load population data from backend (legacy method - kept for initial load)
  const loadPopulationData = async () => {
    try {
      console.log('🔄 Loading population data...');
      const response = await fetch('http://localhost:8000/api/population/density?max_features=500');

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Backend response error:', response.status, errorText);
        throw new Error(`Backend error (${response.status}): ${errorText}`);
      }

      const data = await response.json();
      console.log('✅ Population data loaded:', data.metadata);

      if (data.features && data.features.length > 0) {
        // Get geographic bounds from backend metadata (after CRS correction)
        const geoBounds = data.metadata?.geographic_bounds;

        if (geoBounds) {
          console.log('🌍 Geographic bounds from backend:', geoBounds);
          console.log(`📍 Data center: ${geoBounds.center.longitude.toFixed(2)}, ${geoBounds.center.latitude.toFixed(2)}`);

          // Auto-zoom to where the data actually is
          if (mapInstance) {
            console.log('🎯 Auto-zooming to data location...');
            mapInstance.setCenter({
              lat: geoBounds.center.latitude,
              lng: geoBounds.center.longitude
            });

            // Set appropriate zoom level based on data spread
            const latSpread = geoBounds.max_latitude - geoBounds.min_latitude;
            const lngSpread = geoBounds.max_longitude - geoBounds.min_longitude;
            const maxSpread = Math.max(latSpread, lngSpread);

            let zoomLevel = 10; // Default
            if (maxSpread > 50) zoomLevel = 4;      // Continental
            else if (maxSpread > 20) zoomLevel = 6;  // Country
            else if (maxSpread > 5) zoomLevel = 8;   // Regional
            else if (maxSpread > 1) zoomLevel = 10;  // City
            else zoomLevel = 12;                     // Local

            mapInstance.setZoom(zoomLevel);
            console.log(`📊 Set zoom to ${zoomLevel} (spread: ${maxSpread.toFixed(2)}°)`);
          }
        } else {
          console.warn('⚠️ No geographic bounds provided by backend');
        }

        setPopulationData(data);
        createPopulationChoropleth(data);
        console.log(`🗺️ Created choropleth with ${data.features.length} features`);

        const regionName = geoBounds ?
          `Lng: ${geoBounds.min_longitude.toFixed(2)} to ${geoBounds.max_longitude.toFixed(2)}, Lat: ${geoBounds.min_latitude.toFixed(2)} to ${geoBounds.max_latitude.toFixed(2)}` :
          'Unknown region';

        alert(`✅ Successfully loaded ${data.features.length} population features!\n\n📍 Data location: ${regionName}\n\n🎯 Map auto-zoomed to data area.`);
      } else {
        console.warn('⚠️ No population features found in response');
        alert('❌ No population data found. The dataset might be empty or corrupted.');
      }
    } catch (error) {
      console.error('❌ Error loading population data:', error);

      const errorMessage = error instanceof Error ? error.message : String(error);

      if (errorMessage.includes('Failed to fetch')) {
        alert('❌ Cannot connect to backend. Please ensure the backend server is running on http://localhost:8000');
      } else if (errorMessage.includes('Backend error')) {
        alert(`❌ Backend processing error: ${errorMessage}\n\nThis might be due to the large dataset size. Check the backend console for details.`);
      } else {
        alert(`❌ Error loading population data: ${errorMessage}`);
      }
    }
  };

  // Function to load Ahmedabad-specific population data
  const loadAhmedabadPopulationData = async () => {
    try {
      console.log('🏙️ Loading Ahmedabad-specific population data...');
      const response = await fetch('http://localhost:8000/api/population/density/ahmedabad?max_features=1000');

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Backend response error:', response.status, errorText);
        throw new Error(`Backend error (${response.status}): ${errorText}`);
      }

      const data = await response.json();
      console.log('✅ Ahmedabad population data loaded:', data.metadata);

      if (data.features && data.features.length > 0) {
        // Clear existing population overlays first
        populationOverlays.forEach(overlay => overlay.setMap(null));
        setPopulationOverlays([]);

        setPopulationData(data);
        createPopulationChoropleth(data);
        console.log(`🏙️ Created Ahmedabad choropleth with ${data.features.length} features`);

        // Zoom to Ahmedabad region
        if (mapInstance) {
          mapInstance.setCenter({ lat: 23.0225, lng: 72.5714 });
          mapInstance.setZoom(11);
        }

        alert(`✅ Successfully loaded ${data.features.length} population features for Ahmedabad region!`);
      } else {
        console.warn('⚠️ No population features found in Ahmedabad region');
        alert('❌ No population data found even in Ahmedabad region. The dataset might not cover India.');
      }
    } catch (error) {
      console.error('❌ Error loading Ahmedabad population data:', error);

      const errorMessage = error instanceof Error ? error.message : String(error);
      alert(`❌ Error loading Ahmedabad population data: ${errorMessage}`);
    }
  };

  // Function to create choropleth map from population data
  const createPopulationChoropleth = (data: any) => {
    if (!mapInstance || !mapsInstance || !data.features) return;

    // Clear existing population overlays
    populationOverlays.forEach(overlay => overlay.setMap(null));
    const newOverlays: any[] = [];

    // Create color scale for population density
    const getColor = (density: number) => {
      if (density > 10000) return '#800026';
      if (density > 5000) return '#BD0026';
      if (density > 2000) return '#E31A1C';
      if (density > 1000) return '#FC4E2A';
      if (density > 500) return '#FD8D3C';
      if (density > 200) return '#FEB24C';
      if (density > 100) return '#FED976';
      return '#FFEDA0';
    };

    // Process each feature in the population data
    console.log(`🔄 Processing ${data.features.length} population features...`);

    data.features.forEach((feature: any, index: number) => {
      if (feature.geometry && feature.geometry.type === 'Polygon') {
        const coordinates = feature.geometry.coordinates[0].map((coord: number[]) => ({
          lat: coord[1],
          lng: coord[0]
        }));

        const density = feature.properties.population_density || 0;
        const color = getColor(density);

        // Debug: Log first few features
        if (index < 3) {
          console.log(`📍 Feature ${index + 1}:`, {
            density: density.toFixed(0),
            color,
            coordinates: coordinates.slice(0, 2), // First 2 coordinates
            bounds: {
              lat: [Math.min(...coordinates.map((c: { lat: number; lng: number }) => c.lat)), Math.max(...coordinates.map((c: { lat: number; lng: number }) => c.lat))],
              lng: [Math.min(...coordinates.map((c: { lat: number; lng: number }) => c.lng)), Math.max(...coordinates.map((c: { lat: number; lng: number }) => c.lng))]
            }
          });
        }

        const polygon = new mapsInstance.Polygon({
          paths: coordinates,
          strokeColor: color,
          strokeOpacity: 0.8,
          strokeWeight: 1,
          fillColor: color,
          fillOpacity: 0.6,
        });

        polygon.setMap(mapInstance);
        newOverlays.push(polygon);

        // Add info window
        const infoWindow = new mapsInstance.InfoWindow({
          content: `<div style="color: #ef4444;">
          <h4 style="margin: 0 0 8px 0; font-weight: bold;">Population Density</h4>
          <p style="margin: 4px 0;"><strong>Density:</strong> ${density.toFixed(0)} people/km²</p>
          <p style="margin: 4px 0;"><strong>Total Population:</strong> ${(feature.properties.population || 0).toFixed(0)}</p>
        </div>`
        });

        polygon.addListener('click', (event: any) => {
          infoWindow.setPosition(event.latLng);
          infoWindow.open(mapInstance);
        });
      }
    });

    setPopulationOverlays(newOverlays);
  };

  const handleApiLoaded = (map: unknown, maps: unknown) => {
    console.log('Google Maps API loaded', { map, maps });
    setMapInstance(map);
    setMapsInstance(maps);

    // Initialize Drawing Manager
    const drawingMgr = new (maps as any).drawing.DrawingManager({
      drawingMode: null,
      drawingControl: false,
      rectangleOptions: {
        strokeColor: '#00ff00',
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: '#00ff00',
        fillOpacity: 0.2,
        editable: true,
        draggable: true,
      },
    });

    drawingMgr.setMap(map);
    setDrawingManager(drawingMgr);

    // Listen for rectangle complete event
    (maps as any).event.addListener(drawingMgr, 'rectanglecomplete', (rectangle: any) => {
      // Remove previous AOI rectangle if exists
      if (aoiRectangle) {
        aoiRectangle.setMap(null);
      }

      setAoiRectangle(rectangle);
      const bounds = rectangle.getBounds();
      setAoiBounds(bounds);

      // Stop drawing mode
      drawingMgr.setDrawingMode(null);
      setIsSelectingAOI(false);

      console.log('AOI selected:', bounds.toJSON());
    });

    // Add viewport change listeners for dynamic loading
    (maps as any).event.addListener(map, 'bounds_changed', () => {
      if (map) {
        const bounds = (map as any).getBounds();
        const zoom = (map as any).getZoom();

        setCurrentViewport(bounds);
        setCurrentZoom(zoom);

        // Debounced viewport loading for population layer (with suitability check)
        if (activeNasaLayer === 'population' && isViewportSuitableForLoading(bounds, zoom)) {
          debouncedLoadViewportPopulation(bounds, zoom);
        }
      }
    });

    (maps as any).event.addListener(map, 'zoom_changed', () => {
      if (map) {
        const zoom = (map as any).getZoom();
        setCurrentZoom(zoom);

        // Reload population data if zoom level changed significantly and population layer is active
        if (activeNasaLayer === 'population') {
          const bounds = (map as any).getBounds();
          if (isViewportSuitableForLoading(bounds, zoom)) {
            debouncedLoadViewportPopulation(bounds, zoom);
          }
        }
      }
    });

    // Initialize with LST layer
    setTimeout(() => {
      if (activeNasaLayer) {
        const overlay = createNasaOverlay(map, maps, activeNasaLayer);
        if (overlay) {
          (map as any).overlayMapTypes.push(overlay);
          setCurrentOverlay(overlay);
        }
      }
    }, 1000);
  };

  const handleNasaLayerChange = (layer: string | null) => {
    setActiveNasaLayer(layer);
    updateNasaLayer(layer);
  };

  const handleDateChange = (newDate: string) => {
    setSelectedDate(newDate);
    // Refresh the current NASA layer with new date
    if (activeNasaLayer) {
      updateNasaLayer(activeNasaLayer);
    }
  };

  // Generate date range for timeline (4 years)
  const generateDateRange = (): string[] => {
    const dates: string[] = [];
    const startDate = new Date('2021-01-01');
    const endDate = new Date('2025-12-31');
    const currentDate = new Date(startDate);

    while (currentDate <= endDate) {
      dates.push(new Date(currentDate).toISOString().split('T')[0]);
      currentDate.setDate(currentDate.getDate() + 8); // 8-day intervals for MODIS data
    }
    return dates;
  };

  const dateRange = generateDateRange();
  const maxPosition = dateRange.length - 1;

  const handleTimelineChange = (position: number) => {
    setTimelinePosition(position);
    const newDate = dateRange[position];
    handleDateChange(newDate);
  };

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handlePrevDate = () => {
    if (timelinePosition > 0) {
      handleTimelineChange(timelinePosition - 1);
    }
  };

  const handleNextDate = () => {
    if (timelinePosition < maxPosition) {
      handleTimelineChange(timelinePosition + 1);
    }
  };

  const formatDisplayDate = (date: string): string => {
    const d = new Date(date);
    const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
      'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    return `${d.getFullYear()} ${months[d.getMonth()]} ${d.getDate().toString().padStart(2, '0')}`;
  };

  const handleAOISelect = () => {
    if (!drawingManager) return;

    const newSelectionState = !isSelectingAOI;
    setIsSelectingAOI(newSelectionState);

    if (newSelectionState) {
      // Enable rectangle drawing mode
      drawingManager.setDrawingMode(mapsInstance.drawing.OverlayType.RECTANGLE);
      console.log('AOI selection mode enabled - draw a rectangle on the map');
    } else {
      // Disable drawing mode
      drawingManager.setDrawingMode(null);
      console.log('AOI selection mode disabled');
    }
  };

  const clearAOI = () => {
    if (aoiRectangle) {
      aoiRectangle.setMap(null);
      setAoiRectangle(null);
      setAoiBounds(null);
    }
  };

  const handleCaptureGIF = async () => {
    if (!aoiBounds || !activeNasaLayer) {
      alert('Please select an Area of Interest and a NASA layer first');
      return;
    }

    setIsCapturing(true);

    try {
      // This would implement the GIF capture logic
      console.log('Starting GIF capture for AOI:', aoiBounds);
      console.log('Date range:', dateRange[0], 'to', dateRange[maxPosition]);

      // Simulate capture process
      setTimeout(() => {
        setIsCapturing(false);
        alert('GIF capture completed! (This is a simulation)');
      }, 3000);

    } catch (error) {
      console.error('GIF capture failed:', error);
      setIsCapturing(false);
    }
  };

  // Auto-play timeline
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setTimelinePosition(prev => {
          if (prev >= maxPosition) {
            setIsPlaying(false);
            return 0; // Reset to beginning
          }
          const newPos = prev + 1;
          handleDateChange(dateRange[newPos]);
          return newPos;
        });
      }, 500); // Change every 500ms
    }
    return () => clearInterval(interval);
  }, [isPlaying, maxPosition, dateRange]);

  // Get the API key from environment variables (Vite)
  const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  if (!googleMapsApiKey) {
    return (
      <div className="fullscreen-map-container">
        <div className="map-error-overlay">
          <div className="dashboard-card map-overlay-card">
            <h1>Urban Growth Maps</h1>
            <p>Google Maps API key is not configured</p>
            <h3>Configuration Required</h3>
            <p>Please add your Google Maps API key to the environment variables.</p>
            <p>Add <code>VITE_GOOGLE_MAPS_API_KEY=your_api_key_here</code> to your .env file</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`fullscreen-map-container ${isSelectingAOI ? 'aoi-selecting' : ''}`}>
      <div className="map-wrapper-fullscreen">
        <GoogleMapReact
          bootstrapURLKeys={{
            key: googleMapsApiKey,
            libraries: ['drawing']
          }}
          defaultCenter={defaultProps.center}
          defaultZoom={defaultProps.zoom}
          yesIWantToUseGoogleMapApiInternals
          onGoogleApiLoaded={({ map, maps }: { map: unknown; maps: unknown }) => handleApiLoaded(map, maps)}
          options={{
            styles: [
              {
                featureType: "all",
                elementType: "geometry.fill",
                stylers: [{ color: "#242f3e" }]
              },
              {
                featureType: "all",
                elementType: "labels.text.fill",
                stylers: [{ color: "#746855" }]
              },
              {
                featureType: "all",
                elementType: "labels.text.stroke",
                stylers: [{ color: "#242f3e" }]
              },
              {
                featureType: "road",
                elementType: "geometry",
                stylers: [{ color: "#38414e" }]
              },
              {
                featureType: "road.highway",
                elementType: "geometry",
                stylers: [{ color: "#746855" }]
              },
              {
                featureType: "water",
                elementType: "geometry",
                stylers: [{ color: "#17263c" }]
              }
            ]
          }}
        >
        </GoogleMapReact>
      </div>

      {/* Map Controls Overlay */}
      <div className="map-controls-overlay">
        <div className="dashboard-card map-overlay-card">
          <h3>Map Controls</h3>
          <div className="settings-section">
            <div className="setting-item">
              <label>Map Type</label>
              <select className="setting-select">
                <option value="roadmap" className='text-black'>Roadmap</option>
                <option value="satellite" className='text-black'>Satellite</option>
                <option value="hybrid" className='text-black'>Hybrid</option>
                <option value="terrain" className='text-black'>Terrain</option>
              </select>
            </div>

            <div className="setting-divider"></div>

            <div className="setting-item">
              <label>NASA Satellite Data</label>
            </div>

            <div className="setting-item">
              <label>AOI & Capture</label>
              <div className="aoi-controls">
                <button
                  className={`aoi-btn ${isSelectingAOI ? 'active' : aoiBounds ? 'selected' : ''}`}
                  onClick={handleAOISelect}
                >
                  {isSelectingAOI ? 'Drawing...' : aoiBounds ? '✓ AOI Set' : 'Select AOI'}
                </button>
                {aoiBounds && (
                  <button
                    className="clear-aoi-btn"
                    onClick={clearAOI}
                  >
                    Clear AOI
                  </button>
                )}
                <button
                  className={`capture-btn ${isCapturing ? 'capturing' : ''}`}
                  onClick={handleCaptureGIF}
                  disabled={isCapturing || !aoiBounds}
                >
                  {isCapturing ? 'Capturing...' : '📹 GIF'}
                </button>
              </div>
            </div>

            <div className="setting-item">
              <label>
                <input
                  type="radio"
                  name="nasa-layer"
                  checked={activeNasaLayer === 'lst'}
                  onChange={() => handleNasaLayerChange('lst')}
                />
                LST
              </label>
              {activeNasaLayer === 'lst' && (
                <div className="nasa-inline-legend">
                  <span className="legend-color-bar lst-gradient"></span>
                  <span className="legend-tech-text">273-323K</span>
                </div>
              )}
            </div>

            <div className="setting-item">
              <label>
                <input
                  type="radio"
                  name="nasa-layer"
                  checked={activeNasaLayer === 'ndvi'}
                  onChange={() => handleNasaLayerChange('ndvi')}
                />
                NDVI
              </label>
              {activeNasaLayer === 'ndvi' && (
                <div className="nasa-inline-legend">
                  <span className="legend-color-bar ndvi-gradient"></span>
                  <span className="legend-tech-text">-1.0 to +1.0</span>
                </div>
              )}
            </div>

            <div className="setting-item">
              <label>
                <input
                  type="radio"
                  name="nasa-layer"
                  checked={activeNasaLayer === 'population'}
                  onChange={() => handleNasaLayerChange('population')}
                />
                Population
              </label>
              {activeNasaLayer === 'population' && (
                <>
                  <div className="nasa-inline-legend">
                    <span className="legend-color-bar population-gradient"></span>
                    <span className="legend-tech-text">0-10k+ /km²</span>
                  </div>
                  <div className="viewport-status">
                    {isLoadingViewport && (
                      <div className="loading-indicator">
                        <span className="loading-spinner">⟳</span>
                        <span>Loading...</span>
                      </div>
                    )}
                    <div className="lod-info">
                      <span className="lod-level">Detail: {currentZoom <= 4 ? 'Continental' : currentZoom <= 6 ? 'Country' : currentZoom <= 8 ? 'Region' : currentZoom <= 10 ? 'Regional' : currentZoom <= 12 ? 'City' : 'Detailed'}</span>
                      <span className="zoom-level">Zoom: {currentZoom}</span>
                    </div>
                    {currentZoom < 6 && (
                      <div className="viewport-warning">
                        <span style={{ color: '#ffa500', fontSize: '10px' }}>⚠️ Zoom in to load data</span>
                      </div>
                    )}
                    {currentViewport && (() => {
                      const ne = currentViewport.getNorthEast();
                      const sw = currentViewport.getSouthWest();
                      const area = (ne.lat() - sw.lat()) * (ne.lng() - sw.lng());
                      return area > 50000 ? (
                        <div className="viewport-warning">
                          <span style={{ color: '#ff6b6b', fontSize: '10px' }}>🚫 Area too large</span>
                        </div>
                      ) : null;
                    })()}
                  </div>
                </>
              )}
            </div>

            <div className="setting-item">
              <label>
                <input
                  type="radio"
                  name="nasa-layer"
                  checked={activeNasaLayer === null}
                  onChange={() => handleNasaLayerChange(null)}
                />
                None
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Timeline Controls */}
      <div className="timeline-overlay">
        <div className="timeline-container">
          {/* Date Display */}
          <div className="timeline-date-display">
            <span className="timeline-interval">8 DAYS</span>
            <span className="timeline-current-date">{formatDisplayDate(selectedDate)}</span>
          </div>

          {/* Timeline Controls */}
          <div className="timeline-controls">
            <button className="timeline-nav-btn" onClick={handlePrevDate} disabled={timelinePosition === 0}>
              ◀
            </button>
            <button className="timeline-play-btn" onClick={handlePlayPause}>
              {isPlaying ? '⏸' : '▶'}
            </button>
            <button className="timeline-nav-btn" onClick={handleNextDate} disabled={timelinePosition === maxPosition}>
              ▶
            </button>
          </div>

          {/* Timeline Slider */}
          <div className="timeline-slider-container">
            <div className="timeline-track">
              {/* Timeline markers with improved logic */}
              <div className="timeline-markers">
                {getTimelineMarkers(dateRange, maxPosition, containerWidth).map((marker: TimelineMarker) => (
                  <div
                    key={marker.index}
                    className={`timeline-marker ${marker.isYearStart ? 'year-marker' : marker.isMonthStart ? 'month-marker' : ''}`}
                    style={{ left: `${marker.position}%` }}
                  >
                    {marker.isYearStart && (
                      <span className="timeline-year-label">{marker.dateObj.getFullYear()}</span>
                    )}
                    {marker.isMonthStart && (
                      <span className="timeline-month-label">
                        {marker.dateObj.toLocaleDateString('en', { month: 'short' }).toUpperCase()}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {/* Progress bar */}
              <div className="timeline-progress" style={{ width: `${(timelinePosition / maxPosition) * 100}%` }}></div>

              {/* Slider thumb */}
              <input
                type="range"
                min="0"
                max={maxPosition}
                value={timelinePosition}
                onChange={(e) => handleTimelineChange(parseInt(e.target.value))}
                className="timeline-slider"
              />
            </div>
          </div>

          {/* Timeline Info */}
          <div className="timeline-info">
            <span className="timeline-range">
              {formatDisplayDate(dateRange[0])} - {formatDisplayDate(dateRange[maxPosition])}
            </span>
            <span className="timeline-position">
              {timelinePosition + 1} / {dateRange.length}
            </span>
          </div>
        </div>
      </div>

    </div>
  );
}