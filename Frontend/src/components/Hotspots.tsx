import { useState, useEffect } from 'react';
// @ts-ignore
import GoogleMapReact from 'google-map-react';
import './Dashboard.css';

interface HotspotPolygon {
  id: string;
  coordinates: number[][];
  area: number;
  score?: number;
  aqi?: number;
  population_density?: number;
  amenity_distances?: { [key: string]: number };
  scoring_method?: string;
  scoring_breakdown?: { [key: string]: any };
}

interface ServiceGap {
  center_lat: number;
  center_lng: number;
  service_type: string;
  distance_to_nearest: number;
  need_level: 'low' | 'medium' | 'high';
  area_size: number;
  recommendation: string;
}

interface ServiceAnalysisResult {
  success: boolean;
  message?: string;
  total_service_gaps: number;
  analysis_summary: { [key: string]: any };
  service_gaps: { [key: string]: ServiceGap[] };
}

const getScoreColors = (score: number) => {
  if (score >= 80) {
    return { fillColor: '#4CAF50', strokeColor: '#2E7D32' };
  } else if (score >= 70) {
    return { fillColor: '#8BC34A', strokeColor: '#558B2F' };
  } else if (score >= 60) {
    return { fillColor: '#FFEB3B', strokeColor: '#F57F17' };
  } else if (score >= 50) {
    return { fillColor: '#FF9800', strokeColor: '#E65100' };
  } else {
    return { fillColor: '#F44336', strokeColor: '#C62828' };
  }
};

const getScoreCategory = (score: number) => {
  if (score >= 80) return 'Excellent';
  if (score >= 70) return 'Very Good';
  if (score >= 60) return 'Good';
  if (score >= 50) return 'Fair';
  return 'Poor';
};

export default function Hotspots() {
  const [mapInstance, setMapInstance] = useState<any>(null);
  const [mapsInstance, setMapsInstance] = useState<any>(null);
  const [drawingManager, setDrawingManager] = useState<any>(null);
  const [aoiPolygon, setAoiPolygon] = useState<any>(null);
  const [aoiBounds, setAoiBounds] = useState<any>(null);
  const [isSelectingAOI, setIsSelectingAOI] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [vacantLandData, setVacantLandData] = useState<HotspotPolygon[]>([]);
  const [analysisResults, setAnalysisResults] = useState<any>(null);

  // Service analysis state
  const [selectedServices, setSelectedServices] = useState<string[]>(['parks', 'food']);
  const [serviceAnalysisData, setServiceAnalysisData] = useState<ServiceAnalysisResult | null>(null);
  const [isAnalyzingServices, setIsAnalyzingServices] = useState(false);

  // Holds a reusable InfoWindow
  const [infoWindow, setInfoWindow] = useState<any>(null);

  const defaultProps = {
    center: { lat: 23.218682, lng: 72.607738 },
    zoom: 11
  };

  const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  const handleApiLoaded = (map: unknown, maps: unknown) => {
    console.log('Google Maps API loaded', { map, maps });
    setMapInstance(map);
    setMapsInstance(maps);

    // Create one InfoWindow instance to reuse
    try {
      const iw = new (maps as any).InfoWindow();
      setInfoWindow(iw);
      console.log('✅ InfoWindow instance created');
    } catch (err) {
      console.error('❌ Could not create InfoWindow:', err);
    }

    // Setup drawing manager
    const drawingMgr = new (maps as any).drawing.DrawingManager({
      drawingMode: null,
      drawingControl: false,
      polygonOptions: {
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

    // Optional: test data click layer
    (map as any).data.addListener('click', (evt: any) => {
      console.log('Test click on data layer:', evt);
    });

    (maps as any).event.addListener(drawingMgr, 'polygoncomplete', (polygon: any) => {
      if (aoiPolygon) {
        aoiPolygon.setMap(null);
      }
      setAoiPolygon(polygon);
      const bounds = new (maps as any).LatLngBounds();
      const path = polygon.getPath();
      for (let i = 0; i < path.getLength(); i++) {
        bounds.extend(path.getAt(i));
      }
      setAoiBounds(bounds);
      drawingMgr.setDrawingMode(null);
      setIsSelectingAOI(false);
      console.log('AOI polygon selected:', { bounds: bounds.toJSON() });
    });
  };

  const handleAOISelect = () => {
    if (!drawingManager || !mapsInstance) return;
    const next = !isSelectingAOI;
    setIsSelectingAOI(next);
    if (next) {
      drawingManager.setDrawingMode((mapsInstance as any).drawing.OverlayType.POLYGON);
    } else {
      drawingManager.setDrawingMode(null);
    }
  };

  const clearAOI = () => {
    if (aoiPolygon) {
      aoiPolygon.setMap(null);
      setAoiPolygon(null);
      setAoiBounds(null);
    }
    setVacantLandData([]);
    setAnalysisResults(null);
    setServiceAnalysisData(null);

    if (mapInstance && mapInstance.data) {
      mapInstance.data.forEach((feat: any) => {
        mapInstance.data.remove(feat);
      });
    }
  };

  const convertPolygonToGeoJSON = (polygon: any) => {
    const path = polygon.getPath();
    const coords: number[][] = [];
    for (let i = 0; i < path.getLength(); i++) {
      const ll = path.getAt(i);
      coords.push([ll.lng(), ll.lat()]);
    }
    coords.push(coords[0]);
    return {
      type: 'Feature',
      properties: {},
      geometry: { type: 'Polygon', coordinates: [coords] }
    };
  };

  const analyzeVacantLand = async () => {
    if (!aoiPolygon) {
      alert('Please select an Area of Interest first');
      return;
    }
    setIsAnalyzing(true);
    try {
      const aoiGeoJSON = convertPolygonToGeoJSON(aoiPolygon);
      console.log('Sending AOI to backend:', aoiGeoJSON);

      const resp = await fetch('http://localhost:8000/api/vacant-land/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aoi: aoiGeoJSON })
      });
      if (!resp.ok) {
        const t = await resp.text();
        throw new Error(`Backend error: ${resp.status} — ${t}`);
      }
      const data = await resp.json();
      console.log('Vacant land results:', data);
      setAnalysisResults(data);
      if (data.vacant_land_polygons && data.vacant_land_polygons.length > 0) {
        setVacantLandData(data.vacant_land_polygons);
        displayVacantLandPolygons(data.vacant_land_polygons);
        const cachedMsg = data.cached ? '⚡ Retrieved from cache!' : '🔍 Fresh result!';
        alert(`✅ ${cachedMsg} Found ${data.vacant_land_polygons.length} polygons.`);
      } else {
        alert('No vacant land found in AOI.');
      }
    } catch (err) {
      console.error('Error in analyzeVacantLand:', err);
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Error: ${msg}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const displayVacantLandPolygons = (polygons: any[]) => {
    if (!mapInstance || !mapInstance.data) {
      console.error('Map/data layer not ready');
      return;
    }
    console.log('Displaying polygons:', polygons.length);
    // clear existing
    mapInstance.data.forEach((f: any) => {
      mapInstance.data.remove(f);
    });

    // Clear old listeners
    mapsInstance.event.clearListeners(mapInstance.data, 'click');

    polygons.forEach((polyData, idx) => {
      if (!polyData.geometry) {
        console.warn('Polygon has no geometry:', polyData);
        return;
      }
      const feature = {
        type: 'Feature',
        properties: {
          id: `vacant_${idx}`,
          area: polyData.area || 0,
          score: polyData.hotspot_score ?? polyData.score ?? 0,
          aqi: polyData.aqi,
          population_density: polyData.population_density,
          amenity_distances: polyData.amenity_distances ?? {},
          scoring_method: polyData.scoring_method,
          scoring_breakdown: polyData.scoring_breakdown ?? {}
        },
        geometry: polyData.geometry
      };
      try {
        const added = mapInstance.data.addGeoJson(feature);
        console.log(`✅ Added polygon ${idx + 1}`, added);
      } catch (err) {
        console.error(`Error adding polygon ${idx + 1}:`, err);
      }
    });

    mapInstance.data.setStyle((feat: any) => {
      const s = feat.getProperty('score') || 0;
      const { fillColor, strokeColor } = getScoreColors(s);
      return {
        fillColor,
        fillOpacity: 0.6,
        strokeColor,
        strokeOpacity: 0.9,
        strokeWeight: 3,
        clickable: true
      };
    });

    console.log('🖱️ Adding click listener to map data');
    mapInstance.data.addListener('click', (evt: any) => {
      console.log('🎯 Data click event:', evt);
      
      if (!evt || !evt.feature) {
        console.warn('⚠️ No feature in click event', evt);
        return;
      }

      try {
        const feat = evt.feature;
        const area = feat.getProperty('area') || 0;
        const score = feat.getProperty('score') || 0;
        const aqi = feat.getProperty('aqi');
        const popD = feat.getProperty('population_density');
        const amenD = feat.getProperty('amenity_distances') || {};
        const method = feat.getProperty('scoring_method') || 'unknown';
        const breakdown = feat.getProperty('scoring_breakdown') || {};

        console.log('📊 InfoWindow data:', {
          area, score, aqi, popD, method,
          amenitiesCount: Object.keys(amenD).length,
          breakdownCount: Object.keys(breakdown).length,
          aqiAvailable: !!aqi,
          methodType: method
        });

        const scoreCat = getScoreCategory(score);
        const { fillColor } = getScoreColors(score);

        // Start with simple content first
        const content = `
          <div style="padding:12px; font-family:Arial, sans-serif; max-width:300px;">
            <h4 style="margin:0 0 8px 0; color:#2196F3;">🏗️ Vacant Land Hotspot</h4>
            <div style="color:#333;"><strong>Area:</strong> ${area.toFixed(2)} hectares</div>
            <div style="color:#333;"><strong>Score:</strong> ${score.toFixed(1)}/100</div>
            <div><strong>Category:</strong> ${scoreCat}</div>
            <div style="color:#333;"><strong>Method:</strong> ${method === 'ml_model' ? '🤖 ML Model' : '📏 Rule-based'}</div>
            ${aqi ? `<div style="color:#333;"><strong>AQI:</strong> ${aqi}</div>` : '<div style="color:#333;"><strong>AQI:</strong> Not available</div>'}
            ${popD ? `<div style="color:#333;"><strong>Population:</strong> ${popD.toLocaleString()}/km²</div>` : ''}
          </div>
        `;

        if (!infoWindow) {
          console.error('❌ infoWindow is not initialized');
          return;
        }

        console.log('🔧 Setting InfoWindow content and position...');
        infoWindow.setContent(content);
        infoWindow.setPosition(evt.latLng);
        infoWindow.open(mapInstance);
        console.log('✅ InfoWindow opened successfully');

      } catch (err) {
        console.error('❌ Error in click handler:', err);
        // Fallback alert
        alert('Polygon clicked - InfoWindow error, check console');
      }
    });
  };

  const analyzeServices = async () => {
    if (!aoiBounds || selectedServices.length === 0) {
      alert('Please select an AOI and at least one service type');
      return;
    }
    
    setIsAnalyzingServices(true);
    try {
      const bounds = aoiBounds.toJSON();
      const requestData = {
        aoi_bounds: {
          north: bounds.north,
          south: bounds.south,
          east: bounds.east,
          west: bounds.west
        },
        service_types: selectedServices,
        grid_resolution: 2.0
      };
      
      console.log('Sending service analysis request:', requestData);
      
      const resp = await fetch('http://localhost:8000/api/service-analysis/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });
      
      if (!resp.ok) {
        const errorText = await resp.text();
        throw new Error(`Service analysis failed: ${resp.status} - ${errorText}`);
      }
      
      const data = await resp.json();
      console.log('Service analysis results:', data);
      setServiceAnalysisData(data);
      
      if (data.total_service_gaps > 0) {
        displayServiceGaps(data.service_gaps);
        alert(`✅ Found ${data.total_service_gaps} service gaps across ${selectedServices.length} service types`);
      } else {
        alert('✅ No significant service gaps found in this area!');
      }
      
    } catch (err) {
      console.error('Service analysis error:', err);
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Error: ${msg}`);
    } finally {
      setIsAnalyzingServices(false);
    }
  };

  const displayServiceGaps = (serviceGaps: { [key: string]: ServiceGap[] }) => {
    if (!mapInstance || !mapInstance.data) {
      console.error('Map not ready for service gap display');
      return;
    }

    console.log('Displaying service gaps:', serviceGaps);

    // Add service gap markers to the map
    Object.entries(serviceGaps).forEach(([serviceType, gaps]) => {
      gaps.forEach((gap, idx) => {
        const feature = {
          type: 'Feature',
          properties: {
            id: `service_gap_${serviceType}_${idx}`,
            service_type: serviceType,
            need_level: gap.need_level,
            distance: gap.distance_to_nearest,
            recommendation: gap.recommendation,
            area_size: gap.area_size,
            gap_type: 'service_gap'
          },
          geometry: {
            type: 'Point',
            coordinates: [gap.center_lng, gap.center_lat]
          }
        };

        try {
          mapInstance.data.addGeoJson(feature);
          console.log(`✅ Added ${serviceType} service gap marker ${idx + 1}`);
        } catch (err) {
          console.error(`Error adding service gap ${serviceType}_${idx}:`, err);
        }
      });
    });

    // Update map styling to handle both vacant land and service gaps
    mapInstance.data.setStyle((feat: any) => {
      const gapType = feat.getProperty('gap_type');
      
      if (gapType === 'service_gap') {
        const needLevel = feat.getProperty('need_level');
        const serviceType = feat.getProperty('service_type');
        
        // Different colors for different service types and need levels
        const serviceColors = {
          parks: { high: '#FF5722', medium: '#FF9800', low: '#FFC107' },
          food: { high: '#9C27B0', medium: '#BA68C8', low: '#E1BEE7' },
          healthcare: { high: '#F44336', medium: '#EF5350', low: '#FFCDD2' },
          transport: { high: '#3F51B5', medium: '#5C6BC0', low: '#C5CAE9' }
        };
        
        const color = serviceColors[serviceType as keyof typeof serviceColors]?.[needLevel as keyof typeof serviceColors.parks] || '#757575';
        
        return {
          icon: {
            path: 'M 0,0 C -2,-20 -10,-22 -10,-30 A 10,10 0 1,1 10,-30 C 10,-22 2,-20 0,0 z',
            fillColor: color,
            fillOpacity: 0.9,
            strokeColor: '#FFFFFF',
            strokeWeight: 2,
            scale: 1.0
          },
          clickable: true
        };
      } else {
        // Existing vacant land styling
        const s = feat.getProperty('score') || 0;
        const { fillColor, strokeColor } = getScoreColors(s);
        return {
          fillColor,
          fillOpacity: 0.6,
          strokeColor,
          strokeOpacity: 0.9,
          strokeWeight: 3,
          clickable: true
        };
      }
    });

    // Update click listener to handle both vacant land and service gaps
    console.log('🖱️ Updating click listener for service gaps');
    mapsInstance.event.clearListeners(mapInstance.data, 'click');
    
    mapInstance.data.addListener('click', (evt: any) => {
      console.log('🎯 Data click event:', evt);
      
      if (!evt || !evt.feature) {
        console.warn('⚠️ No feature in click event', evt);
        return;
      }

      try {
        const feat = evt.feature;
        const gapType = feat.getProperty('gap_type');
        
        if (gapType === 'service_gap') {
          // Handle service gap click
          const serviceType = feat.getProperty('service_type');
          const needLevel = feat.getProperty('need_level');
          const distance = feat.getProperty('distance');
          const recommendation = feat.getProperty('recommendation');
          const areaSize = feat.getProperty('area_size');
          
          console.log('📊 Service Gap InfoWindow data:', {
            serviceType, needLevel, distance, recommendation
          });

          const serviceIcons = {
            parks: '🌳',
            food: '🛒', 
            healthcare: '🏥',
            transport: '🚌'
          };

          const needLevelColors = {
            high: '#FF5722',
            medium: '#FF9800', 
            low: '#FFC107'
          };

          const serviceIcon = serviceIcons[serviceType as keyof typeof serviceIcons] || '📍';
          const needColor = needLevelColors[needLevel as keyof typeof needLevelColors] || '#757575';

          const content = `
            <div style="padding:12px; font-family:Arial, sans-serif; max-width:320px;">
              <h4 style="margin:0 0 8px 0; color:#2196F3; display: flex; align-items: center;">
                ${serviceIcon} Service Gap Analysis
              </h4>
              
              <div style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin: 8px 0;">
                <div style="color:#333;"><strong>Service Type:</strong> ${serviceType.charAt(0).toUpperCase() + serviceType.slice(1)}</div>
                <div style="color:#333;"><strong>Need Level:</strong> 
                  <span style="color: ${needColor}; font-weight: bold;">${needLevel.toUpperCase()}</span>
                </div>
                <div style="color:#333;"><strong>Distance to Nearest:</strong> ${distance.toFixed(1)} km</div>
                <div style="color:#333;"><strong>Area Coverage:</strong> ${areaSize.toFixed(1)} km²</div>
              </div>
              
              <div style="background: #fff3e0; padding: 8px; border-radius: 4px; margin: 8px 0;">
                <h5 style="margin: 0 0 6px 0; color: #555; font-size: 12px;">💡 Recommendation</h5>
                <div style="font-size: 11px; color: #333; line-height: 1.4;">
                  ${recommendation}
                </div>
              </div>
              
              <div style="font-size: 10px; color: #666; margin-top: 8px; border-top: 1px solid #eee; padding-top: 6px;">
                📍 Click on green areas to see housing development potential
              </div>
            </div>
          `;

          if (!infoWindow) {
            console.error('❌ infoWindow is not initialized');
            return;
          }

          infoWindow.setContent(content);
          infoWindow.setPosition(evt.latLng);
          infoWindow.open(mapInstance);
          console.log('✅ Service Gap InfoWindow opened');

        } else {
          // Handle vacant land click (existing logic)
          const area = feat.getProperty('area') || 0;
          const score = feat.getProperty('score') || 0;
          const aqi = feat.getProperty('aqi');
          const popD = feat.getProperty('population_density');
          const amenD = feat.getProperty('amenity_distances') || {};
          const method = feat.getProperty('scoring_method') || 'unknown';
          const breakdown = feat.getProperty('scoring_breakdown') || {};

          console.log('📊 Vacant Land InfoWindow data:', {
            area, score, aqi, popD, method,
            amenitiesCount: Object.keys(amenD).length,
            breakdownCount: Object.keys(breakdown).length,
            aqiAvailable: !!aqi,
            methodType: method
          });

          const scoreCat = getScoreCategory(score);
          const { fillColor } = getScoreColors(score);

          const content = `
            <div style="padding:12px; font-family:Arial, sans-serif; max-width:300px;">
              <h4 style="margin:0 0 8px 0; color:#2196F3;">🏗️ Vacant Land Hotspot</h4>
              <div style="color:#333;"><strong>Area:</strong> ${area.toFixed(2)} hectares</div>
              <div style="color:#333;"><strong>Score:</strong> ${score.toFixed(1)}/100</div>
              <div><strong>Category:</strong> ${scoreCat}</div>
              <div style="color:#333;"><strong>Method:</strong> ${method === 'ml_model' ? '🤖 ML Model' : '📏 Rule-based'}</div>
              ${aqi ? `<div style="color:#333;"><strong>AQI:</strong> ${aqi}</div>` : '<div style="color:#333;"><strong>AQI:</strong> Not available</div>'}
              ${popD ? `<div style="color:#333;"><strong>Population:</strong> ${popD.toLocaleString()}/km²</div>` : ''}
              
              <div style="font-size: 10px; color: #666; margin-top: 8px; border-top: 1px solid #eee; padding-top: 6px;">
                📍 Click on colored markers to see service gap details
              </div>
            </div>
          `;

          if (!infoWindow) {
            console.error('❌ infoWindow is not initialized');
            return;
          }

          infoWindow.setContent(content);
          infoWindow.setPosition(evt.latLng);
          infoWindow.open(mapInstance);
          console.log('✅ Vacant Land InfoWindow opened');
        }

      } catch (err) {
        console.error('❌ Error in click handler:', err);
        alert('Feature clicked - InfoWindow error, check console');
      }
    });
  };

  const handleServiceToggle = (service: string) => {
    setSelectedServices(prev => 
      prev.includes(service) 
        ? prev.filter(s => s !== service)
        : [...prev, service]
    );
  };

  if (!googleMapsApiKey) {
    return (
      <div className="fullscreen-map-container">
        <div className="map-error-overlay">
          <div className="dashboard-card map-overlay-card">
            <h1>Hotspots Analysis</h1>
            <p>Google Maps API key not set</p>
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
            libraries: ['drawing', 'places']  // ensure “places” so InfoWindow etc is available
          }}
          defaultCenter={defaultProps.center}
          defaultZoom={defaultProps.zoom}
          yesIWantToUseGoogleMapApiInternals
          onGoogleApiLoaded={({ map, maps }) => handleApiLoaded(map, maps)}
          options={{
            styles: [
              {
                featureType: 'all',
                elementType: 'geometry.fill',
                stylers: [{ color: '#242f3e' }]
              },
              {
                featureType: 'all',
                elementType: 'labels.text.fill',
                stylers: [{ color: '#746855' }]
              },
              {
                featureType: 'all',
                elementType: 'labels.text.stroke',
                stylers: [{ color: '#242f3e' }]
              },
              {
                featureType: 'road',
                elementType: 'geometry',
                stylers: [{ color: '#38414e' }]
              },
              {
                featureType: 'road.highway',
                elementType: 'geometry',
                stylers: [{ color: '#746855' }]
              },
              {
                featureType: 'water',
                elementType: 'geometry',
                stylers: [{ color: '#17263c' }]
              }
            ]
          }}
        />
      </div>

      <div className="map-controls-overlay">
        <div className="dashboard-card map-overlay-card">
          <h3>🎯 Hotspots Analysis</h3>

          <div className="setting-item">
            <label>Select Area of Interest</label>
            <div className="aoi-controls">
              <button
                className={`aoi-btn ${isSelectingAOI ? 'active' : aoiBounds ? 'selected' : ''}`}
                onClick={handleAOISelect}
                disabled={isAnalyzing}
              >
                {isSelectingAOI ? 'Drawing...' : aoiBounds ? '✓ AOI Set' : 'Select AOI'}
              </button>
              {aoiBounds && (
                <button className="clear-aoi-btn" onClick={clearAOI} disabled={isAnalyzing}>
                  Clear AOI
                </button>
              )}
            </div>
          </div>

          <div className="setting-divider"></div>

          <div className="setting-item">
            <label>Select Analysis Types</label>
            
            <div className="analysis-options">
              <div className="checkbox-group">
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={true}
                    readOnly
                  />
                  <span>🏠 Housing Development (Vacant Land)</span>
                </label> <br />
                
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={selectedServices.includes('parks')}
                    onChange={() => handleServiceToggle('parks')}
                  />
                  <span>🌳 Parks & Recreation Access</span>
                </label> <br />
                
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={selectedServices.includes('food')}
                    onChange={() => handleServiceToggle('food')}
                  />
                  <span>🛒 Food & Grocery Access</span>
                </label> <br />
                
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={selectedServices.includes('healthcare')}
                    onChange={() => handleServiceToggle('healthcare')}
                  />
                  <span>🏥 Healthcare Access</span>
                </label> <br />
                
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={selectedServices.includes('transport')}
                    onChange={() => handleServiceToggle('transport')}
                  />
                  <span>🚌 Public Transport Access</span>
                </label>
              </div>
            </div>
          </div>

          <div className="setting-divider"></div>

          <div className="setting-item">
            <label>Run Analysis</label>
            <div className="analysis-buttons">
              <button
                className={`action-btn primary ${isAnalyzing ? 'analyzing' : ''}`}
                onClick={analyzeVacantLand}
                disabled={isAnalyzing || !aoiBounds}
                style={{ width: '100%', marginBottom: '8px' }}
              >
                {isAnalyzing ? 'Analyzing...' : 'Find Housing Hotspots'}
              </button>
              
              {selectedServices.length > 0 && (
                <button
                  className={`action-btn secondary ${isAnalyzingServices ? 'analyzing' : ''}`}
                  onClick={analyzeServices}
                  disabled={isAnalyzingServices || !aoiBounds || selectedServices.length === 0}
                  style={{ width: '100%' }}
                >
                  {isAnalyzingServices ? 'Analyzing...' : `Analyze ${selectedServices.length} Service${selectedServices.length > 1 ? 's' : ''}`}
                </button>
              )}
            </div>
          </div>

          {(analysisResults || serviceAnalysisData) && (
            <>
              <div className="setting-divider"></div>
              <div className="setting-item">
                <label>📊 Analysis Results</label>
                
                {analysisResults && (
                  <div className="analysis-summary">
                    <div className="metric-item">
                      <span className="metric-value">{vacantLandData.length}</span>
                      <span className="metric-label">Housing Areas</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-value">
                        {analysisResults.total_area?.toFixed(1) ?? '0'}
                      </span>
                      <span className="metric-label">Total Area (ha)</span>
                    </div>
                  </div>
                )}
                
                {serviceAnalysisData && (
                  <div className="service-analysis-summary">
                    <div className="metric-item">
                      <span className="metric-value">{serviceAnalysisData.total_service_gaps}</span>
                      <span className="metric-label">Service Gaps</span>
                    </div>
                    
                    {Object.entries(serviceAnalysisData.analysis_summary).map(([service, summary]: [string, any]) => (
                      <div key={service} className="service-summary">
                        <div className="service-name">
                          {service === 'parks' ? '🌳 Parks' : 
                           service === 'food' ? '🛒 Food' :
                           service === 'healthcare' ? '🏥 Healthcare' : 
                           service === 'transport' ? '🚌 Transport' : service}
                        </div>
                        <div className="service-stats">
                          <span className="high-priority">{summary.high_priority} high</span>
                          <span className="medium-priority">{summary.medium_priority} medium</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          <div className="setting-divider"></div>
          <div className="setting-item">
            <label>🎨 Map Legend</label>
            
            {/* Housing Development Legend */}
            <div style={{ marginBottom: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 'bold', marginBottom: '4px', color: '#555' }}>
                🏠 Housing Development
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#4CAF50' }}></span>
                <span className="legend-text">Excellent (80-100)</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#F44336' }}></span>
                <span className="legend-text">Poor (0-50)</span>
              </div>
            </div>

            {/* Service Gaps Legend */}
            {serviceAnalysisData && serviceAnalysisData.total_service_gaps > 0 && (
              <div>
                <div style={{ fontSize: '11px', fontWeight: 'bold', marginBottom: '4px', color: '#555' }}>
                  📍 Service Gaps (High Priority)
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#FF5722', borderRadius: '50%', width: '12px', height: '12px' }}></span>
                  <span className="legend-text">🌳 Parks</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#9C27B0', borderRadius: '50%', width: '12px', height: '12px' }}></span>
                  <span className="legend-text">🛒 Food</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#F44336', borderRadius: '50%', width: '12px', height: '12px' }}></span>
                  <span className="legend-text">🏥 Healthcare</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#3F51B5', borderRadius: '50%', width: '12px', height: '12px' }}></span>
                  <span className="legend-text">🚌 Transport</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
