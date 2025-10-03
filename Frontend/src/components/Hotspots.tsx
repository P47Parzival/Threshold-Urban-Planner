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
            <label>Step 1: Select Area of Interest</label>
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
            <label>Step 2: Analyze Vacant Land</label>
            <button
              className={`action-btn primary ${isAnalyzing ? 'analyzing' : ''}`}
              onClick={analyzeVacantLand}
              disabled={isAnalyzing || !aoiBounds}
              style={{ width: '100%', marginTop: '8px' }}
            >
              {isAnalyzing ? 'Analyzing...' : 'Find Hotspots'}
            </button>
          </div>

          {analysisResults && (
            <>
              <div className="setting-divider"></div>
              <div className="setting-item">
                <label>Analysis Results</label>
                <div className="analysis-summary">
                  <div className="metric-item">
                    <span className="metric-value">{vacantLandData.length}</span>
                    <span className="metric-label">Vacant Areas</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-value">
                      {analysisResults.total_area?.toFixed(1) ?? '0'}
                    </span>
                    <span className="metric-label">Total Area (ha)</span>
                  </div>
                </div>
              </div>
            </>
          )}

          <div className="setting-divider"></div>
          <div className="setting-item">
            <label>🎨 Score Legend</label>
            <div className="legend-item">
              <span className="legend-color" style={{ backgroundColor: '#4CAF50' }}></span>
              <span className="legend-text">Excellent</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ backgroundColor: '#F44336' }}></span>
              <span className="legend-text">Poor</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
