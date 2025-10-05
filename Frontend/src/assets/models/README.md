# 3D Models Directory

This directory contains GLB (GL Transmission Format Binary) files for 3D model visualization in the THRESHOLD platform.

## Folder Structure

```
models/
├── houses/          # House and building models
├── doors/           # Door and gate models  
├── furniture/       # Furniture and interior items
└── vehicles/        # Cars, trucks, and other vehicles
```

## Supported Format

- **File Type**: `.glb` (GL Transmission Format Binary)
- **Size Limit**: Recommended < 10MB per model for optimal performance
- **Textures**: Embedded textures are supported

## Usage

1. **Add Models**: 
   - Drag & drop GLB files directly onto the 3D View interface
   - Or click "Add GLB" button to browse and select files
   - Models are automatically categorized based on filename

2. **Place Models**:
   - Select a model from the library panel
   - Click anywhere on the map to place it
   - View your placement in Street View (when available)

3. **Manage Models**:
   - Remove placed models using the ✕ button
   - Models are organized by category with emoji icons

## Model Categories

### 🏠 Houses
- Residential buildings
- Commercial structures  
- Architectural models
- Keywords: `house`, `building`, `home`

### 🚪 Doors
- Entry doors
- Gates and barriers
- Architectural elements
- Keywords: `door`, `gate`

### 🪑 Furniture
- Interior furniture
- Decorative items
- Default category for uncategorized models

### 🚗 Vehicles
- Cars and trucks
- Transportation models
- Keywords: `car`, `vehicle`, `truck`

## Technical Notes

- Models are loaded using object URLs for browser compatibility
- Automatic filename-based categorization
- Real-time drag & drop support
- Memory management with cleanup on component unmount

## Example Workflow

1. Find or create GLB models of houses, doors, furniture, vehicles
2. Drag them into the 3D View interface
3. Select a model from the library
4. Click on empty land on the map
5. Switch to Street View to see your visualization
6. Repeat to build complete scenes

This system allows urban planners and users to visualize how buildings and structures would look in real-world locations before construction begins.
