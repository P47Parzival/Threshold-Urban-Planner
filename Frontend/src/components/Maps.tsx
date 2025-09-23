import { useState } from 'react';
// @ts-ignore - google-map-react types may not be available
import GoogleMapReact from 'google-map-react';
import './Dashboard.css';

export default function Maps() {
  const [activeNasaLayer, setActiveNasaLayer] = useState<string | null>('lst');
  const [mapInstance, setMapInstance] = useState<any>(null);
  const [mapsInstance, setMapsInstance] = useState<any>(null);
  const [currentOverlay, setCurrentOverlay] = useState<any>(null);
  const [selectedDate, setSelectedDate] = useState<string>('2025-09-22');
  const defaultProps = {
    center: {
      lat: 23.218682,
      lng: 72.607738
    },
    zoom: 11
  };

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
    <div className="fullscreen-map-container">
      <div className="map-wrapper-fullscreen">
        <GoogleMapReact
          bootstrapURLKeys={{ key: googleMapsApiKey }}
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
              <label>Date</label>
              <input 
                type="date" 
                value={selectedDate}
                onChange={(e) => handleDateChange(e.target.value)}
                className="date-picker"
                min="2020-01-01"
                max="2025-12-31"
              />
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
    </div>
  );
}
