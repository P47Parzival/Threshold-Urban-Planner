from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import os
import geopandas as gpd
import pandas as pd
import json
import time
from pathlib import Path
from shapely.geometry import box

router = APIRouter()

# Path to the population dataset
POPULATION_DATA_PATH = Path(__file__).parent.parent.parent.parent / "Population Dataset" / "kontur_population_20231101.gpkg"

@router.get("/density")
async def get_population_density(
    bbox: Optional[str] = Query(None, description="Bounding box as 'minLng,minLat,maxLng,maxLat' (leave empty for global sample)"),
    simplify: Optional[float] = Query(0.01, description="Simplification tolerance for geometry (default: 0.01 for testing)"),
    max_features: Optional[int] = Query(1000, description="Maximum features to return (default: 1000 for testing)")
):
    """
    Get population density data as GeoJSON (optimized for testing)
    
    Args:
        bbox: Bounding box to filter data (default: Ahmedabad region)
        simplify: Geometry simplification tolerance (default: 0.01 for testing)
        max_features: Maximum features to return (default: 1000 for testing)
    
    Returns:
        GeoJSON with population density features
    """
    try:
        if not POPULATION_DATA_PATH.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Population data file not found at {POPULATION_DATA_PATH}"
            )
        
        print(f"🔄 Starting population data processing...")
        print(f"📂 Reading from: {POPULATION_DATA_PATH}")
        print(f"📍 Bounding box: {bbox}")
        print(f"🎯 Max features: {max_features}")
        print(f"🔧 Simplification: {simplify}")
        
        # Parse bounding box for filtering
        bbox_geom = None
        if bbox:
            try:
                min_lng, min_lat, max_lng, max_lat = map(float, bbox.split(','))
                from shapely.geometry import box
                bbox_geom = box(min_lng, min_lat, max_lng, max_lat)
                print(f"📦 Created bounding box: ({min_lng}, {min_lat}) to ({max_lng}, {max_lat})")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid bbox format. Use 'minLng,minLat,maxLng,maxLat'"
                )
        
        # Strategy 1: Try reading with bbox if provided (most efficient)
        try:
            if bbox_geom:
                print("📖 Reading data with bounding box filter...")
                # First try with geopandas bbox parameter
                try:
                    gdf = gpd.read_file(POPULATION_DATA_PATH, bbox=(min_lng, min_lat, max_lng, max_lat))
                    print(f"✅ Loaded {len(gdf)} features within bounding box")
                except Exception as bbox_error:
                    print(f"⚠️ Direct bbox read failed: {bbox_error}")
                    print("📖 Falling back to sample read with post-filtering...")
                    # Read a larger sample and then filter
                    gdf = gpd.read_file(POPULATION_DATA_PATH, rows=max_features * 10)
                    print(f"✅ Loaded {len(gdf)} sample features")
                    # Apply bounding box filter
                    print("🔍 Filtering by bounding box...")
                    gdf = gdf[gdf.geometry.intersects(bbox_geom)]
                    print(f"✅ Filtered to {len(gdf)} features")
            else:
                print(f"📖 Reading first {max_features} features for testing...")
                gdf = gpd.read_file(POPULATION_DATA_PATH, rows=max_features)
                print(f"✅ Loaded {len(gdf)} features")
        except Exception as read_error:
            print(f"⚠️ All optimized reads failed: {read_error}")
            print("📖 Trying minimal sample read...")
            # Last resort: read just a few features to test
            gdf = gpd.read_file(POPULATION_DATA_PATH, rows=100)
            print(f"✅ Loaded {len(gdf)} minimal sample features")
            
            # Apply bounding box filter if needed
            if bbox_geom and len(gdf) > 0:
                print("🔍 Filtering minimal sample by bounding box...")
                gdf = gdf[gdf.geometry.intersects(bbox_geom)]
                print(f"✅ Filtered to {len(gdf)} features")
        
        # Check and fix coordinate reference system FIRST
        print(f"📍 Original CRS: {gdf.crs}")
        if gdf.crs is None:
            print("⚠️ No CRS defined, assuming EPSG:4326")
            gdf = gdf.set_crs('EPSG:4326')
        elif str(gdf.crs) != 'EPSG:4326':
            print("🔄 Reprojecting to EPSG:4326 (WGS84) for web mapping...")
            gdf = gdf.to_crs('EPSG:4326')
            print("✅ Reprojection complete")
        
        # Show actual bounds after CRS fix
        if len(gdf) > 0:
            bounds = gdf.total_bounds
            print(f"🌍 Geographic bounds: Lng {bounds[0]:.2f} to {bounds[2]:.2f}, Lat {bounds[1]:.2f} to {bounds[3]:.2f}")
        
        # Limit features if still too many
        if len(gdf) > max_features:
            print(f"✂️ Sampling {max_features} features from {len(gdf)} total...")
            gdf = gdf.sample(n=max_features, random_state=42)
        
        # Simplify geometries for better performance
        if simplify > 0:
            print(f"🔧 Simplifying geometries with tolerance {simplify}...")
            gdf['geometry'] = gdf['geometry'].simplify(simplify)
            print("✅ Geometry simplification complete")
        
        # Calculate population density if not already present
        print("📊 Processing population density...")
        if 'population_density' not in gdf.columns:
            # Assuming the GPKG has population and area columns
            if 'population' in gdf.columns:
                print("🧮 Calculating population density...")
                # Calculate area in km²
                gdf_proj = gdf.to_crs('EPSG:3857')  # Web Mercator for area calculation
                area_km2 = gdf_proj.geometry.area / 1_000_000  # Convert m² to km²
                gdf['population_density'] = gdf['population'] / area_km2
                gdf['population_density'] = gdf['population_density'].fillna(0)
                print("✅ Population density calculated")
            else:
                print("⚠️ No 'population' column found")
        else:
            print("✅ Population density already exists")
        
        # Check if we have any features
        if len(gdf) == 0:
            print("⚠️ No features found in the specified region!")
            return {
                "type": "FeatureCollection",
                "features": [],
                "metadata": {
                    "total_features": 0,
                    "bbox": bbox,
                    "simplification": simplify,
                    "max_features": max_features,
                    "processing_strategy": "optimized_for_testing",
                    "warning": "No features found in specified bounding box",
                    "columns": []
                }
            }
        
        # Convert to GeoJSON with NumPy compatibility fix
        print("🗺️ Converting to GeoJSON...")
        try:
            # Fix for NumPy 2.0 compatibility - use pandas-compatible approach
            import numpy as np
            
            # Ensure all numeric columns are compatible
            for col in gdf.columns:
                if col != 'geometry' and gdf[col].dtype == 'object':
                    try:
                        # Fix deprecation warning - use explicit error handling
                        numeric_col = pd.to_numeric(gdf[col], errors='coerce')
                        if not numeric_col.isna().all():  # If conversion succeeded for some values
                            gdf[col] = numeric_col.fillna(gdf[col])  # Keep original for non-numeric
                    except:
                        pass
            
            # Use __geo_interface__ method which is more stable
            geojson_dict = {
                "type": "FeatureCollection",
                "features": []
            }
            
            for idx, row in gdf.iterrows():
                try:
                    # Get geometry as dict
                    geom_dict = row.geometry.__geo_interface__
                    
                    # Get properties, excluding geometry and converting numpy types
                    properties = {}
                    for k, v in row.items():
                        if k != 'geometry':
                            # Convert numpy types to native Python types
                            if hasattr(v, 'item'):  # numpy scalar
                                properties[k] = v.item()
                            elif pd.isna(v):
                                properties[k] = None
                            else:
                                properties[k] = v
                    
                    feature = {
                        "type": "Feature",
                        "geometry": geom_dict,
                        "properties": properties
                    }
                    geojson_dict["features"].append(feature)
                    
                except Exception as feature_error:
                    print(f"⚠️ Skipping feature {idx}: {feature_error}")
                    continue
            
            geojson_data = geojson_dict
            
        except Exception as json_error:
            print(f"⚠️ All GeoJSON conversion failed: {json_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to convert data to GeoJSON: {str(json_error)}"
            )
        
        # Calculate geographic bounds for frontend auto-zoom
        data_bounds = None
        if len(gdf) > 0:
            bounds = gdf.total_bounds
            data_bounds = {
                "min_longitude": float(bounds[0]),
                "min_latitude": float(bounds[1]),
                "max_longitude": float(bounds[2]),
                "max_latitude": float(bounds[3]),
                "center": {
                    "longitude": float((bounds[0] + bounds[2]) / 2),
                    "latitude": float((bounds[1] + bounds[3]) / 2)
                }
            }
        
        print(f"🎉 Processing complete! Returning {len(gdf)} features")
        if data_bounds:
            print(f"📍 Data center: {data_bounds['center']['longitude']:.2f}, {data_bounds['center']['latitude']:.2f}")
        
        return {
            "type": "FeatureCollection",
            "features": geojson_data["features"],
            "metadata": {
                "total_features": len(gdf),
                "bbox": bbox,
                "simplification": simplify,
                "max_features": max_features,
                "processing_strategy": "optimized_for_testing",
                "columns": list(gdf.columns) if len(gdf) > 0 else [],
                "geographic_bounds": data_bounds
            }
        }
        
    except Exception as e:
        print(f"Error processing population data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing population data: {str(e)}"
        )

@router.get("/info")
async def get_population_info():
    """
    Get information about the population dataset (fast version for testing)
    """
    try:
        if not POPULATION_DATA_PATH.exists():
            return {
                "available": False,
                "path": str(POPULATION_DATA_PATH),
                "message": "Population data file not found",
                "file_size_gb": 0
            }
        
        # Get file size
        file_size_bytes = POPULATION_DATA_PATH.stat().st_size
        file_size_gb = round(file_size_bytes / (1024**3), 2)
        
        print(f"📊 Getting dataset info... File size: {file_size_gb} GB")
        
        # Read just the first few rows to get info (fast)
        gdf = gpd.read_file(POPULATION_DATA_PATH, rows=5)
        
        return {
            "available": True,
            "path": str(POPULATION_DATA_PATH),
            "file_size_gb": file_size_gb,
            "sample_features": len(gdf),
            "columns": list(gdf.columns),
            "crs": str(gdf.crs),
            "bounds": gdf.total_bounds.tolist(),
            "sample_properties": gdf.iloc[0].drop('geometry').to_dict() if len(gdf) > 0 else {},
            "optimization_note": "Using optimized reading for testing - max 1000 features, Ahmedabad region by default"
        }
        
    except Exception as e:
        print(f"❌ Error reading population data info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reading population data info: {str(e)}"
        )

@router.get("/test")
async def test_population_endpoint():
    """
    Quick test endpoint to verify population data access
    """
    try:
        if not POPULATION_DATA_PATH.exists():
            return {
                "status": "error",
                "message": f"Population data file not found at {POPULATION_DATA_PATH}",
                "file_size_gb": 0
            }
        
        # Get file size
        file_size_bytes = POPULATION_DATA_PATH.stat().st_size
        file_size_gb = round(file_size_bytes / (1024**3), 2)
        
        # Quick test read (just 1 feature)
        test_gdf = gpd.read_file(POPULATION_DATA_PATH, rows=1)
        
        return {
            "status": "success",
            "message": "Population data is accessible",
            "file_size_gb": file_size_gb,
            "test_feature_count": len(test_gdf),
            "estimated_load_time_minutes": f"{file_size_gb * 2}-{file_size_gb * 4}",
            "recommended_approach": "Use bbox and max_features parameters for testing"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error accessing population data: {str(e)}",
            "recommendation": "Check file path and dependencies"
        }

@router.get("/density/ahmedabad")
async def get_ahmedabad_population_density(
    max_features: Optional[int] = Query(1000, description="Maximum features to return (default: 1000)")
):
    """
    Get population density data specifically for Ahmedabad region (optimized for testing)
    """
    try:
        # Ahmedabad bounding box (slightly larger area)
        ahmedabad_bbox = "72.3,22.8,72.9,23.4"
        
        print(f"🏙️ Loading Ahmedabad-specific population data...")
        print(f"📍 Ahmedabad bbox: {ahmedabad_bbox}")
        
        # Call the main density function with Ahmedabad bbox
        return await get_population_density(
            bbox=ahmedabad_bbox,
            simplify=0.005,  # Less simplification for better detail
            max_features=max_features
        )
        
    except Exception as e:
        print(f"❌ Error loading Ahmedabad population data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error loading Ahmedabad population data: {str(e)}"
        )

@router.get("/bounds")
async def get_population_bounds():
    """
    Get the geographic bounds of the population dataset (quick sample)
    """
    try:
        if not POPULATION_DATA_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Population data file not found"
            )
        
        print("📊 Getting dataset bounds...")
        
        # Read a sample to get bounds
        sample_gdf = gpd.read_file(POPULATION_DATA_PATH, rows=100)
        bounds = sample_gdf.total_bounds  # [minx, miny, maxx, maxy]
        
        return {
            "bounds": {
                "min_longitude": float(bounds[0]),
                "min_latitude": float(bounds[1]),
                "max_longitude": float(bounds[2]),
                "max_latitude": float(bounds[3])
            },
            "sample_features": len(sample_gdf),
            "center": {
                "longitude": float((bounds[0] + bounds[2]) / 2),
                "latitude": float((bounds[1] + bounds[3]) / 2)
            },
            "note": "Bounds calculated from first 100 features"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting bounds: {str(e)}"
        )
