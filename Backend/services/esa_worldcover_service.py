"""
ESA WorldCover Data Processing Service with Google Earth Engine

This service handles:
1. Real ESA WorldCover satellite data processing using Google Earth Engine
2. Vacant land detection (class 60 - bare/sparse vegetation)  
3. Vectorization of raster data to GeoJSON polygons
4. Filtering and area calculations
"""

import ee
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from services.gee_service import gee_service

class ESAWorldCoverService:
    """Service for processing ESA WorldCover satellite data using Google Earth Engine."""
    
    # ESA WorldCover 2021 land cover classes
    LAND_COVER_CLASSES = {
        10: "Tree cover",
        20: "Shrubland", 
        30: "Grassland",
        40: "Cropland",
        50: "Built-up",
        60: "Bare / sparse vegetation",  # PRIMARY VACANT/DEVELOPABLE LAND
        70: "Snow and ice",
        80: "Permanent water bodies",
        90: "Herbaceous wetland",
        95: "Mangroves",
        100: "Moss and lichen"
    }
    
    # Classes that represent vacant/developable land
    VACANT_LAND_CLASSES = [60]  # Focus on bare/sparse vegetation
    POTENTIALLY_VACANT_CLASSES = [30, 60]  # Include some grassland
    
    def __init__(self):
        self.dataset_id = "ESA/WorldCover/v200"
        
    async def get_vacant_land_polygons(
        self, 
        aoi_bounds: Dict[str, float],
        aoi_geometry: Dict[str, Any],
        min_area_m2: int = 5000,  # Minimum 5000 m² (0.5 hectares)
        max_polygons: int = 100,
        use_relaxed_filter: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extract vacant land polygons from ESA WorldCover using Google Earth Engine.
        
        Args:
            aoi_bounds: Bounding box {min_lng, max_lng, min_lat, max_lat}
            aoi_geometry: GeoJSON geometry for clipping
            min_area_m2: Minimum area in square meters
            max_polygons: Maximum number of polygons to return
            use_relaxed_filter: Include grassland (class 30) as potential vacant land
            
        Returns:
            List of vacant land polygons with geometry and metadata
        """
        try:
            # Check if Google Earth Engine is initialized
            if not gee_service.is_authenticated():
                logging.warning("Google Earth Engine not authenticated, using fallback")
                return await self._generate_synthetic_vacant_land(aoi_bounds, aoi_geometry)
            
            logging.info(f"Processing ESA WorldCover data with GEE for bounds: {aoi_bounds}")
            
            # Step 1: Convert AOI GeoJSON to ee.Geometry
            ee_geometry = ee.Geometry(aoi_geometry)
            
            # Step 2: Load ESA WorldCover dataset
            worldcover = ee.Image(self.dataset_id).select("Map")
            
            # Step 3: Create mask for vacant land classes
            vacant_classes = self.POTENTIALLY_VACANT_CLASSES if use_relaxed_filter else self.VACANT_LAND_CLASSES
            
            # Create mask for vacant land (class 60, optionally 30)
            vacant_mask = worldcover.eq(vacant_classes[0])
            for class_id in vacant_classes[1:]:
                vacant_mask = vacant_mask.Or(worldcover.eq(class_id))
            
            # Apply mask and clip to AOI
            vacant_land = worldcover.updateMask(vacant_mask).clip(ee_geometry)
            
            # Step 4: Filter small objects using connected pixel count
            # Each pixel is ~10m x 10m = 100 m²
            min_pixels = max(1, min_area_m2 // 100)  # Convert area to pixel count
            
            # Calculate connected pixel count for each patch
            connected_pixels = vacant_land.connectedPixelCount(maxSize=256, eightConnected=True)
            
            # Calculate actual area in square meters
            pixel_area = ee.Image.pixelArea()  # Area of each pixel in m²
            patch_area = connected_pixels.multiply(pixel_area)
            
            # Filter patches by minimum area
            large_patches = vacant_land.updateMask(patch_area.gte(min_area_m2))
            
            # Step 5: Convert raster to vector polygons
            try:
                vectors = large_patches.reduceToVectors(
                    geometry=ee_geometry,
                    scale=10,  # 10m resolution
                    geometryType="polygon",
                    eightConnected=True,
                    labelProperty="landcover",
                    bestEffort=True,
                    maxPixels=1e8  # Increased for larger areas
                )
                
                # Get the result as GeoJSON
                vector_info = vectors.getInfo()
                
            except Exception as e:
                logging.warning(f"High-resolution vectorization failed: {str(e)}, trying lower resolution")
                # Fallback with lower resolution
                vectors = large_patches.reduceToVectors(
                    geometry=ee_geometry,
                    scale=30,  # Lower resolution
                    geometryType="polygon",
                    eightConnected=True,
                    labelProperty="landcover",
                    bestEffort=True,
                    maxPixels=1e7
                )
                vector_info = vectors.getInfo()
            
            # Step 6: Process the results
            processed_polygons = self._process_gee_results(
                vector_info, 
                aoi_geometry, 
                min_area_m2, 
                max_polygons
            )
            
            logging.info(f"Successfully processed {len(processed_polygons)} vacant land polygons with GEE")
            return processed_polygons
            
        except Exception as e:
            logging.error(f"Error processing ESA WorldCover with GEE: {str(e)}")
            # Fallback to synthetic data
            logging.info("Falling back to synthetic data generation")
            return await self._generate_synthetic_vacant_land(aoi_bounds, aoi_geometry)
    
    def _process_gee_results(
        self,
        vector_info: Dict[str, Any],
        aoi_geometry: Dict[str, Any],
        min_area_m2: int,
        max_polygons: int
    ) -> List[Dict[str, Any]]:
        """Process Google Earth Engine vector results into our format."""
        try:
            processed = []
            features = vector_info.get("features", [])
            
            logging.info(f"Processing {len(features)} features from GEE")
            
            for i, feature in enumerate(features[:max_polygons]):
                try:
                    geometry = feature.get("geometry", {})
                    properties = feature.get("properties", {})
                    
                    if geometry.get("type") != "Polygon":
                        continue
                    
                    # Calculate area using Shapely for accuracy
                    from shapely.geometry import shape
                    polygon_shape = shape(geometry)
                    
                    # Convert to approximate area in square meters
                    # This is rough - for precise calculations, use proper projection
                    area_deg2 = polygon_shape.area
                    # Rough conversion: 1 degree² ≈ 12100 km² at equator
                    # More accurate would be to use proper coordinate transformation
                    lat_center = sum(coord[1] for coord in geometry["coordinates"][0]) / len(geometry["coordinates"][0])
                    lat_correction = abs(lat_center / 90.0)  # Simple latitude correction
                    area_m2 = area_deg2 * 111000 * 111000 * lat_correction  # Very rough approximation
                    
                    if area_m2 >= min_area_m2:
                        # Get centroid
                        centroid = polygon_shape.centroid
                        
                        # Generate hotspot score based on area and land cover class
                        landcover_class = properties.get("landcover", 60)
                        area_score = min(100, (area_m2 / 10000) * 20)  # Larger = better score
                        base_score = 60 if landcover_class == 60 else 45  # Bare land scores higher
                        hotspot_score = min(100, base_score + area_score)
                        
                        processed.append({
                            "id": f"gee_vacant_{i}",
                            "geometry": geometry,
                            "area": area_m2 / 10000,  # Convert to hectares
                            "hotspot_score": hotspot_score,
                            "landcover_class": landcover_class,
                            "centroid": [centroid.x, centroid.y],
                            "data_source": "ESA_WorldCover_GEE",
                            "processing_date": datetime.utcnow().isoformat()
                        })
                        
                except Exception as e:
                    logging.warning(f"Error processing feature {i}: {str(e)}")
                    continue
            
            # Sort by hotspot score (highest first)
            processed.sort(key=lambda x: x["hotspot_score"], reverse=True)
            
            return processed
            
        except Exception as e:
            logging.error(f"Error processing GEE results: {str(e)}")
            return []
    
    async def get_landcover_statistics(
        self, 
        aoi_geometry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get land cover statistics for the AOI using Google Earth Engine.
        
        Args:
            aoi_geometry: GeoJSON geometry of the AOI
            
        Returns:
            Dictionary with land cover class statistics
        """
        try:
            if not gee_service.is_authenticated():
                return {"error": "Google Earth Engine not authenticated"}
            
            # Convert to ee.Geometry
            ee_geometry = ee.Geometry(aoi_geometry)
            
            # Load WorldCover
            worldcover = ee.Image(self.dataset_id).select("Map").clip(ee_geometry)
            
            # Calculate area for each land cover class
            pixel_area = ee.Image.pixelArea()
            
            stats = {}
            total_area = 0
            
            for class_id, class_name in self.LAND_COVER_CLASSES.items():
                class_mask = worldcover.eq(class_id)
                class_area = class_mask.multiply(pixel_area).reduceRegion(
                    reducer=ee.Reducer.sum(),
                    geometry=ee_geometry,
                    scale=10,
                    maxPixels=1e8,
                    bestEffort=True
                ).getInfo()
                
                area_m2 = class_area.get("Map", 0)
                area_ha = area_m2 / 10000  # Convert to hectares
                
                if area_ha > 0:
                    stats[class_name] = {
                        "class_id": class_id,
                        "area_ha": area_ha,
                        "area_m2": area_m2
                    }
                    total_area += area_ha
            
            # Calculate percentages
            for class_stats in stats.values():
                class_stats["percentage"] = (class_stats["area_ha"] / total_area * 100) if total_area > 0 else 0
            
            return {
                "total_area_ha": total_area,
                "land_cover_classes": stats,
                "data_source": "ESA_WorldCover_2021",
                "processing_date": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error getting land cover statistics: {str(e)}")
            return {"error": str(e)}
    
    async def _generate_synthetic_vacant_land(
        self, 
        bounds: Dict[str, float], 
        aoi_geometry: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate synthetic vacant land data when Google Earth Engine is unavailable.
        """
        import random
        from shapely.geometry import shape, Polygon
        
        logging.info("Generating synthetic vacant land data (GEE unavailable)")
        
        polygons = []
        aoi_polygon = shape(aoi_geometry)
        
        # Generate 3-8 synthetic vacant land areas
        num_polygons = random.randint(3, 8)
        
        for i in range(num_polygons):
            # Generate random points within AOI bounds
            center_lng = random.uniform(bounds["min_lng"], bounds["max_lng"])
            center_lat = random.uniform(bounds["min_lat"], bounds["max_lat"])
            
            # Create polygon with realistic shape variation
            base_size = random.uniform(0.0008, 0.003)  # 80-300m approximate
            
            # Create slightly irregular polygon
            vertices = []
            for angle in range(0, 360, 45):  # 8 vertices
                angle_rad = angle * 3.14159 / 180
                radius = base_size * random.uniform(0.7, 1.3)  # Vary radius
                x = center_lng + radius * random.uniform(0.8, 1.2) * (1 if angle_rad < 3.14159 else -1)
                y = center_lat + radius * random.uniform(0.8, 1.2) * (1 if angle_rad < 1.57 or angle_rad > 4.71 else -1)
                vertices.append([x, y])
            
            # Close the polygon
            vertices.append(vertices[0])
            
            test_polygon = Polygon(vertices)
            
            # Only include if it intersects with AOI
            if aoi_polygon.intersects(test_polygon):
                intersection = aoi_polygon.intersection(test_polygon)
                if hasattr(intersection, 'area') and intersection.area > 0:
                    area_ha = random.uniform(0.5, 8.0)
                    
                    polygons.append({
                        "id": f"synthetic_gee_{i}",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [vertices]
                        },
                        "area": area_ha,
                        "hotspot_score": random.uniform(50.0, 90.0),
                        "landcover_class": 60,
                        "centroid": [center_lng, center_lat],
                        "data_source": "Synthetic_Fallback",
                        "processing_date": datetime.utcnow().isoformat()
                    })
        
        return polygons

# Global service instance  
esa_service = ESAWorldCoverService()
