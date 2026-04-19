import { useEffect, useRef, useState, useCallback } from 'react';

// Google Maps API configuration
const GOOGLE_MAPS_API_KEY = 'AIzaSyBNzjlrxcQftseMwRfLuH3VXdrDk5n2q5s';

// 3D Model interface
interface Model3D {
  id: string;
  name: string;
  file: File;
  category: 'houses' | 'doors' | 'furniture' | 'vehicles';
  url?: string;
}

interface PlacedModel {
  id: string;
  model: Model3D;
  position: { lat: number; lng: number; height: number };
  rotation: { x: number; y: number; z: number };
  scale: { x: number; y: number; z: number };
  marker?: any; // Google Maps marker reference
}

declare global {
  interface Window {
    google: any;
    initThreeDMap: () => void;
  }
}

export default function ThreeDView() {
  const mapRef = useRef<HTMLDivElement>(null);
  const panoRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [streetViewError, setStreetViewError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [models, setModels] = useState<Model3D[]>([]);
  const [placedModels, setPlacedModels] = useState<PlacedModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<Model3D | null>(null);
  const [placementMode, setPlacementMode] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [mapInstance, setMapInstance] = useState<any>(null);
  const [panoramaInstance, setPanoramaInstance] = useState<any>(null);

  // File handling functions
  const handleFileUpload = useCallback((files: FileList) => {
    Array.from(files).forEach(file => {
      if (file.name.toLowerCase().endsWith('.glb')) {
        const model: Model3D = {
          id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
          name: file.name.replace('.glb', ''),
          file: file,
          category: determineCategory(file.name),
          url: URL.createObjectURL(file)
        };
        setModels(prev => [...prev, model]);
      }
    });
  }, []);

  const determineCategory = (filename: string): 'houses' | 'doors' | 'furniture' | 'vehicles' => {
    const name = filename.toLowerCase();
    if (name.includes('house') || name.includes('building') || name.includes('home')) return 'houses';
    if (name.includes('door') || name.includes('gate')) return 'doors';
    if (name.includes('car') || name.includes('vehicle') || name.includes('truck')) return 'vehicles';
    return 'furniture';
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = e.dataTransfer.files;
    handleFileUpload(files);
  }, [handleFileUpload]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFileUpload(e.target.files);
    }
  }, [handleFileUpload]);

  const selectModel = (model: Model3D) => {
    setSelectedModel(model);
    setPlacementMode(true);
  };

  const cancelPlacement = () => {
    setSelectedModel(null);
    setPlacementMode(false);
  };

  const placeModel = (position: { lat: number; lng: number }) => {
    if (selectedModel) {
      const placedModel: PlacedModel = {
        id: Date.now().toString(),
        model: selectedModel,
        position: { ...position, height: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        scale: { x: 1, y: 1, z: 1 }
      };
      setPlacedModels(prev => [...prev, placedModel]);
      
      // Add a marker to the map to show the placed model
      if (mapInstance) {
        const marker = new window.google.maps.Marker({
          position: position,
          map: mapInstance,
          title: `${selectedModel.name} - Click to remove`,
          icon: {
            url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
              <svg width="40" height="40" xmlns="http://www.w3.org/2000/svg">
                <circle cx="20" cy="20" r="18" fill="#007bff" stroke="#fff" stroke-width="2"/>
                <text x="20" y="26" text-anchor="middle" fill="white" font-size="16">
                  ${selectedModel.category === 'houses' ? '🏠' : 
                    selectedModel.category === 'doors' ? '🚪' :
                    selectedModel.category === 'vehicles' ? '🚗' : '🪑'}
                </text>
              </svg>
            `),
            scaledSize: new window.google.maps.Size(40, 40),
            anchor: new window.google.maps.Point(20, 20)
          }
        });

        // Add click listener to marker for removal
        marker.addListener('click', () => {
          if (window.confirm(`Remove ${selectedModel.name}?`)) {
            marker.setMap(null);
            removeModel(placedModel.id);
          }
        });

        // Store marker reference in the placed model for later cleanup
        placedModel.marker = marker;
      }
      
      setSelectedModel(null);
      setPlacementMode(false);
      
      console.log(`Placed ${selectedModel.name} at`, position);
    }
  };

  const removeModel = (modelId: string) => {
    const modelToRemove = placedModels.find(m => m.id === modelId);
    if (modelToRemove && modelToRemove.marker) {
      // Remove marker from map
      modelToRemove.marker.setMap(null);
    }
    setPlacedModels(prev => prev.filter(m => m.id !== modelId));
  };

  useEffect(() => {
    // Function to initialize the 3D map and street view
    const initThreeDMap = () => {
      if (!window.google || !mapRef.current || !panoRef.current) {
        console.error('Google Maps API not loaded or refs not available');
        setIsLoading(false);
        return;
      }

      setIsLoading(false);
      const location = { lat: 37.4219999, lng: -122.0840575 }; // Google HQ

      // Initialize the 3D map
      const map = new window.google.maps.Map(mapRef.current, {
        center: location,
        zoom: 14,
        mapTypeId: "satellite", // 3D look
        tilt: 45, // Add tilt for 3D effect
        heading: 0, // Rotation (0-360 degrees)
        mapTypeControl: true,
        mapTypeControlOptions: {
          style: window.google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
          position: window.google.maps.ControlPosition.TOP_CENTER,
        },
        zoomControl: true,
        zoomControlOptions: {
          position: window.google.maps.ControlPosition.RIGHT_CENTER,
        },
        scaleControl: true,
        streetViewControl: true,
        streetViewControlOptions: {
          position: window.google.maps.ControlPosition.RIGHT_TOP,
        },
        fullscreenControl: true,
      });

      // Store map instance for later use
      setMapInstance(map);

      // Street View Service to check availability and handle errors
      const streetViewService = new window.google.maps.StreetViewService();
      
      // Check if Street View is available at location
      streetViewService.getPanorama({
        location: location,
        radius: 50
      }, (data: any, status: any) => {
        if (status === window.google.maps.StreetViewStatus.OK) {
          // Street View is available, initialize panorama
          const panorama = new window.google.maps.StreetViewPanorama(
            panoRef.current,
            {
              position: location,
              pov: { heading: 34, pitch: 10 },
              zoom: 1,
              addressControl: true,
              linksControl: true,
              panControl: true,
              enableCloseButton: false,
              // Add error handling options
              motionTracking: false,
              motionTrackingControl: false,
            }
          );

          // Connect the map and street view
          map.setStreetView(panorama);

          // Store panorama instance for later use
          setPanoramaInstance(panorama);

          // Add click listener to Street View for model placement
          panorama.addListener('click', (event: any) => {
            if (placementMode && selectedModel) {
              // Get the clicked position in Street View
              const position = panorama.getPosition();
              if (position) {
                // Place model at the Street View location
                placeModel({
                  lat: position.lat(),
                  lng: position.lng()
                });
                console.log(`Placed ${selectedModel.name} in Street View at`, {
                  lat: position.lat(),
                  lng: position.lng()
                });
              }
            }
          });

          // Add error listeners for Street View
          panorama.addListener('status_changed', () => {
            const panoStatus = panorama.getStatus();
            if (panoStatus !== window.google.maps.StreetViewStatus.OK) {
              console.error('Street View status error:', panoStatus);
              setStreetViewError(`Street View unavailable: ${panoStatus}`);
            }
          });

          // Add click listener to map for Street View navigation ONLY (not model placement)
          map.addListener('click', (event: any) => {
            const clickedLocation = event.latLng;
            
            // Only use map for Street View navigation, not model placement
            if (!placementMode) {
              // Normal street view navigation
              streetViewService.getPanorama({
                location: clickedLocation,
                radius: 50
              }, (clickData: any, clickStatus: any) => {
                if (clickStatus === window.google.maps.StreetViewStatus.OK) {
                  panorama.setPosition(clickedLocation);
                  setStreetViewError(null);
                } else {
                  setStreetViewError('Street View not available at this location');
                  console.warn('Street View not available at clicked location:', clickStatus);
                }
              });
            }
          });

          // Add position change listener to panorama to update map center
          panorama.addListener('position_changed', () => {
            const position = panorama.getPosition();
            if (position) {
              map.setCenter(position);
            }
          });

          setStreetViewError(null);
          console.log('3D Map and Street View initialized successfully');
        } else {
          // Street View not available, show error
          console.error('Street View not available:', status);
          setStreetViewError(`Street View unavailable: ${status}. This may be due to API quota limits or location restrictions.`);
          
          // Still initialize map without Street View
          console.log('3D Map initialized without Street View');
        }
      });
    };

    // Set the global function
    window.initThreeDMap = initThreeDMap;

    // Load Google Maps API if not already loaded
    if (!window.google) {
      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&libraries=geometry&callback=initThreeDMap`;
      script.async = true;
      script.defer = true;
      script.onerror = (error) => {
        console.error('Failed to load Google Maps API:', error);
      };
      document.head.appendChild(script);

      // Cleanup function to remove script
      return () => {
        document.head.removeChild(script);
        delete window.initThreeDMap;
      };
    } else {
      // Google Maps API already loaded, initialize immediately
      initThreeDMap();
    }
  }, [placementMode, selectedModel]);

  return (
    <div 
      style={{ 
        height: '100vh', 
        width: '100%', 
        display: 'flex',
        position: 'relative'
      }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".glb"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileInputChange}
      />

      {/* Drag and drop overlay */}
      {isDragOver && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 123, 255, 0.2)',
          border: '3px dashed #007bff',
          zIndex: 2000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '24px',
          fontWeight: 'bold',
          color: '#007bff'
        }}>
          🏠 Drop GLB models here to add them!
        </div>
      )}

      {/* Header */}
      <div style={{
        position: 'absolute',
        top: '10px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        padding: '10px 20px',
        borderRadius: '8px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
        fontSize: '18px',
        fontWeight: 'bold',
        color: '#333'
      }}>
        🏗️ 3D Model Visualization
        {placementMode && (
          <div style={{ fontSize: '14px', color: '#007bff', marginTop: '5px' }}>
            Click in the Street View (360°) to place "{selectedModel?.name}"
          </div>
        )}
      </div>

      {/* Model Library Panel */}
      <div style={{
        position: 'absolute',
        top: '80px',
        right: '20px',
        width: '300px',
        maxHeight: '70vh',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderRadius: '12px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
        zIndex: 1000,
        overflow: 'hidden'
      }}>
        {/* Panel Header */}
        <div style={{
          padding: '15px',
          backgroundColor: '#007bff',
          color: 'white',
          fontWeight: 'bold',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>🏠 Model Library ({models.length})</span>
          <button
            onClick={() => fileInputRef.current?.click()}
            style={{
              background: 'rgba(255,255,255,0.2)',
              border: 'none',
              color: 'white',
              padding: '5px 10px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            + Add GLB
          </button>
        </div>

        {/* Model List */}
        <div style={{
          maxHeight: '300px',
          overflowY: 'auto',
          padding: '10px'
        }}>
          {models.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '20px',
              color: '#666',
              fontSize: '14px'
            }}>
              <div>📁 No models loaded</div>
              <div style={{ marginTop: '10px', fontSize: '12px' }}>
                Drag & drop GLB files or click "Add GLB"
              </div>
            </div>
          ) : (
            models.map(model => (
              <div
                key={model.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '8px',
                  margin: '5px 0',
                  backgroundColor: selectedModel?.id === model.id ? '#e3f2fd' : '#f8f9fa',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  border: selectedModel?.id === model.id ? '2px solid #007bff' : '1px solid #dee2e6'
                }}
                onClick={() => selectModel(model)}
              >
                <div style={{
                  fontSize: '20px',
                  marginRight: '10px'
                }}>
                  {model.category === 'houses' ? '🏠' : 
                   model.category === 'doors' ? '🚪' :
                   model.category === 'vehicles' ? '🚗' : '🪑'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 'bold', fontSize: '14px' }}>{model.name}</div>
                  <div style={{ fontSize: '12px', color: '#666', textTransform: 'capitalize' }}>
                    {model.category}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Placed Models */}
        {placedModels.length > 0 && (
          <>
            <div style={{
              padding: '10px 15px',
              backgroundColor: '#f8f9fa',
              borderTop: '1px solid #dee2e6',
              fontWeight: 'bold',
              fontSize: '14px'
            }}>
              🎯 Placed Models ({placedModels.length})
            </div>
            <div style={{
              maxHeight: '150px',
              overflowY: 'auto',
              padding: '10px'
            }}>
              {placedModels.map(placed => (
                <div
                  key={placed.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 8px',
                    margin: '3px 0',
                    backgroundColor: '#fff',
                    borderRadius: '4px',
                    border: '1px solid #dee2e6',
                    fontSize: '12px'
                  }}
                >
                  <span>{placed.model.name}</span>
                  <button
                    onClick={() => removeModel(placed.id)}
                    style={{
                      background: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '3px',
                      padding: '2px 6px',
                      cursor: 'pointer',
                      fontSize: '10px'
                    }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Placement Controls */}
        {placementMode && (
          <div style={{
            padding: '15px',
            backgroundColor: '#e3f2fd',
            borderTop: '1px solid #007bff'
          }}>
            <div style={{ fontSize: '14px', marginBottom: '10px', fontWeight: 'bold' }}>
              🎯 Placement Mode Active
            </div>
            <button
              onClick={cancelPlacement}
              style={{
                background: '#6c757d',
                color: 'white',
                border: 'none',
                padding: '8px 16px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px',
                width: '100%'
              }}
            >
              Cancel Placement
            </button>
          </div>
        )}
      </div>

      {/* Map Container */}
      <div 
        ref={mapRef}
        style={{ 
          height: '100%', 
          width: '50%', 
          borderRight: '2px solid #ccc',
          cursor: 'default' // Always default cursor for map (navigation only)
        }}
      />
      
      {/* Street View Container */}
      <div 
        ref={panoRef}
        style={{ 
          height: '100%', 
          width: '50%',
          position: 'relative',
          backgroundColor: '#f0f0f0',
          cursor: placementMode ? 'crosshair' : 'default'
        }}
      >
        {/* Loading indicator */}
        {isLoading && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 1001,
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            padding: '20px',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div>🔄 Loading Street View...</div>
          </div>
        )}
        
        {/* Street View Error Message */}
        {streetViewError && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 1001,
            backgroundColor: 'rgba(255, 0, 0, 0.9)',
            color: 'white',
            padding: '20px',
            borderRadius: '8px',
            textAlign: 'center',
            maxWidth: '80%',
            fontSize: '14px',
            lineHeight: '1.4'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '10px' }}>⚠️ Street View Error</div>
            <div>{streetViewError}</div>
            <div style={{ marginTop: '10px', fontSize: '12px', opacity: 0.8 }}>
              This is likely due to API quota limits (429 errors). The 3D map will still work.
            </div>
          </div>
        )}
      </div>

      {/* Instructions */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        zIndex: 1000,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        padding: '10px 15px',
        borderRadius: '8px',
        fontSize: '14px',
        maxWidth: '300px',
        lineHeight: '1.4'
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>💡 Instructions:</div>
        <div>• Drag & drop GLB files to add 3D models</div>
        <div>• Click models in library to select them</div>
        <div>• <strong>Click in Street View (360°) to place models</strong></div>
        <div>• Use satellite map to navigate to locations</div>
        <div>• Click placed markers to remove models</div>
        {placementMode && (
          <div style={{ marginTop: '8px', fontSize: '12px', color: '#90EE90', fontWeight: 'bold' }}>
            🎯 PLACEMENT MODE: Click in the Street View (right side) to place "{selectedModel?.name}"
          </div>
        )}
        {streetViewError && (
          <div style={{ marginTop: '8px', fontSize: '12px', color: '#ffcccc' }}>
            ⚠️ Street View currently unavailable due to API limits
          </div>
        )}
      </div>
    </div>
  );
}
