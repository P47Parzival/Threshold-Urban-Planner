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

    // Add new overlay if layer is selected
    if (layer) {
      const overlay = createNasaOverlay(mapInstance, mapsInstance, layer);
      if (overlay) {
        mapInstance.overlayMapTypes.push(overlay);
        setCurrentOverlay(overlay);
      }
    }
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