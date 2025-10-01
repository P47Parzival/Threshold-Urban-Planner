import { useState, useEffect } from 'react';
// @ts-ignore - google-map-react types may not be available
import GoogleMapReact from 'google-map-react';
import './Dashboard.css';

interface HotspotPolygon {
  id: string;
  coordinates: number[][];
  area: number;
  score?: number;
}

export default function Hotspots() {
  const [mapInstance, setMapInstance] = useState<any>(null);
  const [mapsInstance, setMapsInstance] = useState<any>(null);
  const [drawingManager, setDrawingManager] = useState<any>(null);
  const [isSelectingAOI, setIsSelectingAOI] = useState<boolean>(false);
  const [aoiPolygon, setAoiPolygon] = useState<any>(null);
  const [aoiBounds, setAoiBounds] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [vacantLandData, setVacantLandData] = useState<HotspotPolygon[]>([]);
  const [analysisResults, setAnalysisResults] = useState<any>(null);

  const defaultProps = {
    center: {
      lat: 23.218682,
      lng: 72.607738
    },
    zoom: 11
  };

  // Get the API key from environment variables (Vite)
  const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  const handleApiLoaded = (map: unknown, maps: unknown) => {
    console.log('Google Maps API loaded for Hotspots', { map, maps });
    setMapInstance(map);
    setMapsInstance(maps);

    // Initialize Drawing Manager for AOI selection
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

    // Listen for polygon complete event
    (maps as any).event.addListener(drawingMgr, 'polygoncomplete', (polygon: any) => {
      // Remove previous AOI polygon if exists
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

      // Stop drawing mode
      drawingMgr.setDrawingMode(null);
      setIsSelectingAOI(false);

      console.log('AOI polygon selected:', {
        bounds: bounds.toJSON(),
        pathLength: path.getLength()
      });
    });
  };

  const handleAOISelect = () => {
    if (!drawingManager) return;

    const newSelectionState = !isSelectingAOI;
    setIsSelectingAOI(newSelectionState);

    if (newSelectionState) {
      // Enable polygon drawing mode
      drawingManager.setDrawingMode(mapsInstance.drawing.OverlayType.POLYGON);
      console.log('AOI selection mode enabled - draw a polygon on the map');
    } else {
      // Disable drawing mode
      drawingManager.setDrawingMode(null);
      console.log('AOI selection mode disabled');
    }
  };

  const clearAOI = () => {
    if (aoiPolygon) {
      aoiPolygon.setMap(null);
      setAoiPolygon(null);
      setAoiBounds(null);
      setVacantLandData([]);
      setAnalysisResults(null);
      
      // Clear any existing data layers on the map
      if (mapInstance && mapInstance.data) {
        mapInstance.data.forEach((feature: any) => {
          mapInstance.data.remove(feature);
        });
      }
    }
  };

  const convertPolygonToGeoJSON = (polygon: any) => {
    const path = polygon.getPath();
    const coordinates: number[][] = [];
    
    for (let i = 0; i < path.getLength(); i++) {
      const latLng = path.getAt(i);
      coordinates.push([latLng.lng(), latLng.lat()]);
    }
    
    // Close the polygon by adding the first point at the end
    coordinates.push(coordinates[0]);

    return {
      type: 'Feature',
      properties: {},
      geometry: {
        type: 'Polygon',
        coordinates: [coordinates]
      }
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

      const response = await fetch('http://localhost:8000/api/vacant-land/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          aoi: aoiGeoJSON
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Backend error (${response.status}): ${errorText}`);
      }

      const data = await response.json();
      console.log('Vacant land analysis results:', data);

      setAnalysisResults(data);
      
      if (data.vacant_land_polygons && data.vacant_land_polygons.length > 0) {
        setVacantLandData(data.vacant_land_polygons);
        
        // Add the polygons to the map
        displayVacantLandPolygons(data.vacant_land_polygons);
        
        alert(`✅ Analysis complete! Found ${data.vacant_land_polygons.length} vacant land areas.`);
      } else {
        alert('No vacant land areas found in the selected AOI.');
      }

    } catch (error) {
      console.error('Error analyzing vacant land:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      alert(`❌ Error analyzing vacant land: ${errorMessage}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const displayVacantLandPolygons = (polygons: any[]) => {
    if (!mapInstance || !mapInstance.data) return;

    // Clear existing data
    mapInstance.data.forEach((feature: any) => {
      mapInstance.data.remove(feature);
    });

    // Add new polygons
    polygons.forEach((polygonData: any, index: number) => {
      if (polygonData.geometry) {
        const feature = mapInstance.data.addGeoJson({
          type: 'Feature',
          properties: {
            id: `vacant_${index}`,
            area: polygonData.area || 0,
            score: polygonData.score || 0
          },
          geometry: polygonData.geometry
        });

        // Style the polygons
        mapInstance.data.setStyle({
          fillColor: '#ffeb3b',
          fillOpacity: 0.4,
          strokeColor: '#ff9800',
          strokeOpacity: 0.8,
          strokeWeight: 2
        });
      }
    });

    // Add click listener for info windows
    mapInstance.data.addListener('click', (event: any) => {
      const feature = event.feature;
      const area = feature.getProperty('area') || 0;
      const score = feature.getProperty('score') || 0;
      
      const infoWindow = new mapsInstance.InfoWindow({
        content: `
          <div style="color: #333; font-family: Arial, sans-serif;">
            <h4 style="margin: 0 0 8px 0; color: #ff9800;">Vacant Land Area</h4>
            <p style="margin: 4px 0;"><strong>Area:</strong> ${area.toFixed(2)} hectares</p>
            <p style="margin: 4px 0;"><strong>Hotspot Score:</strong> ${score.toFixed(1)}/100</p>
            <p style="margin: 4px 0;"><em>Suitable for residential development</em></p>
          </div>
        `
      });

      infoWindow.setPosition(event.latLng);
      infoWindow.open(mapInstance);
    });
  };

  if (!googleMapsApiKey) {
    return (
      <div className="fullscreen-map-container">
        <div className="map-error-overlay">
          <div className="dashboard-card map-overlay-card">
            <h1>Hotspots Analysis</h1>
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

      {/* Hotspots Controls Overlay */}
      <div className="map-controls-overlay">
        <div className="dashboard-card map-overlay-card">
          <h3>🎯 Hotspots Analysis</h3>
          
          <div className="settings-section">
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
                  <button
                    className="clear-aoi-btn"
                    onClick={clearAOI}
                    disabled={isAnalyzing}
                  >
                    Clear AOI
                  </button>
                )}
              </div>
              <small className="setting-help">
                Draw a polygon on the map to define your area of interest
              </small>
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
                {isAnalyzing ? '🔍 Analyzing...' : '🚀 Find Hotspots'}
              </button>
              <small className="setting-help">
                Identify vacant land suitable for residential development
              </small>
            </div>

            {analysisResults && (
              <>
                <div className="setting-divider"></div>
                <div className="setting-item">
                  <label>Analysis Results</label>
                  <div className="analysis-summary">
                    <div className="metric-item">
                      <span className="metric-value">{vacantLandData.length}</span>
                      <span className="metric-label">Vacant Areas Found</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-value">
                        {analysisResults.total_area ? `${analysisResults.total_area.toFixed(1)}` : '0'}
                      </span>
                      <span className="metric-label">Total Area (ha)</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-value">
                        {analysisResults.avg_score ? `${analysisResults.avg_score.toFixed(1)}` : 'N/A'}
                      </span>
                      <span className="metric-label">Avg Hotspot Score</span>
                    </div>
                  </div>
                </div>
              </>
            )}

            <div className="setting-divider"></div>

            <div className="setting-item">
              <label>Legend</label>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#ffeb3b', border: '2px solid #ff9800' }}></span>
                <span className="legend-text">Vacant Land Areas</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#00ff00', opacity: 0.3 }}></span>
                <span className="legend-text">Selected AOI</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
