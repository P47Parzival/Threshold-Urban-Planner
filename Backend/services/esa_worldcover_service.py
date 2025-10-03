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
from services.hotspot_scoring_service import hotspot_scoring_service
from services.distance_service import distance_service
from api.routes.aqi import calculate_aqi_for_location
import asyncio

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
        self.dataset_id = "ESA/WorldCover/v200"  # Fixed: Using ImageCollection format
        
    async def get_vacant_land_polygons(
        self, 
        aoi_bounds: Dict[str, float],
        aoi_geometry: Dict[str, Any],
        min_area_m2: int = 5000,  # Minimum 5000 m² (0.5 hectares)
        max_polygons: int = 100,
        use_relaxed_filter: bool = False,
        use_square_fallback: bool = True  # New parameter for square fallback
    ) -> List[Dict[str, Any]]:
        """
        Extract vacant land polygons from ESA WorldCover using Google Earth Engine.
        
        Args:
            aoi_bounds: Bounding box {min_lng, max_lng, min_lat, max_lat}
            aoi_geometry: GeoJSON geometry for clipping
            min_area_m2: Minimum area in square meters
            max_polygons: Maximum number of polygons to return
            use_relaxed_filter: Include grassland (class 30) as potential vacant land
            use_square_fallback: Use square AOI if polygon geometry is invalid
            
        Returns:
            List of vacant land polygons with geometry and metadata
        """
        try:
            # Check if Google Earth Engine is initialized
            if not gee_service.is_authenticated():
                print("="*50)
                print("🚫 USING SYNTHETIC FALLBACK DATA")
                print("🔧 Google Earth Engine not authenticated")
                print("="*50)
                logging.error("="*50)
                logging.error("🚫 USING SYNTHETIC FALLBACK DATA")
                logging.error("🔧 Google Earth Engine not authenticated")
                logging.error("="*50)
                return await self._generate_synthetic_vacant_land(aoi_bounds, aoi_geometry)
            
            print("="*50)
            print("🛰️  PROCESSING WITH GOOGLE EARTH ENGINE")
            print("🌍 ESA WorldCover v200 - Real Satellite Data")
            print(f"📊 AOI Bounds: {aoi_bounds}")
            print("="*50)
            logging.info("="*50)
            logging.info("🛰️  PROCESSING WITH GOOGLE EARTH ENGINE")
            logging.info("🌍 ESA WorldCover v200 - Real Satellite Data")
            logging.info(f"📊 AOI Bounds: {aoi_bounds}")
            logging.info("="*50)
            
            # Step 1: Convert AOI GeoJSON to ee.Geometry with validation
            try:
                ee_geometry = self._create_validated_geometry(aoi_geometry, aoi_bounds, use_square_fallback)
                logging.info("Using original polygon geometry")
            except Exception as geom_error:
                logging.warning(f"Geometry validation failed: {str(geom_error)}")
                if use_square_fallback:
                    logging.info("Using square fallback geometry due to validation failure")
                    ee_geometry = self._create_square_geometry(aoi_bounds)
                else:
                    raise geom_error
            
            # Step 2: Load ESA WorldCover dataset (ImageCollection format)
            worldcover_collection = ee.ImageCollection(self.dataset_id).first()
            worldcover = worldcover_collection.select("Map")
            
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
            processed_polygons = await self._process_gee_results(
                vector_info, 
                aoi_geometry, 
                min_area_m2, 
                max_polygons
            )
            
            logging.info("="*50)
            logging.info("✅ REAL SATELLITE DATA PROCESSING COMPLETE")
            logging.info(f"🎯 Found {len(processed_polygons)} vacant land areas")
            logging.info("🛰️  Source: ESA WorldCover v200 via Google Earth Engine")
            logging.info("="*50)
            
            print("="*50)
            print("✅ REAL SATELLITE DATA PROCESSING COMPLETE")
            print(f"🎯 Found {len(processed_polygons)} vacant land areas")
            print("🛰️  Source: ESA WorldCover v200 via Google Earth Engine")
            print("="*50)
            
            return processed_polygons
            
        except Exception as e:
            print("="*50)
            print("❌ GOOGLE EARTH ENGINE PROCESSING FAILED")
            print(f"🚫 Error: {str(e)}")
            print("⚠️  FALLING BACK TO SYNTHETIC DATA")
            print("="*50)
            logging.error("="*50)
            logging.error("❌ GOOGLE EARTH ENGINE PROCESSING FAILED")
            logging.error(f"🚫 Error: {str(e)}")
            logging.error("⚠️  FALLING BACK TO SYNTHETIC DATA")
            logging.error("="*50)
            return await self._generate_synthetic_vacant_land(aoi_bounds, aoi_geometry)
    
    def _create_validated_geometry(self, aoi_geometry: Dict[str, Any], aoi_bounds: Dict[str, float], use_square_fallback: bool = True):
        """
        Create and validate ee.Geometry from GeoJSON, with fallback options.
        
        Args:
            aoi_geometry: GeoJSON geometry
            aoi_bounds: Bounding box for fallback
            use_square_fallback: Whether to use square fallback on validation failure
            
        Returns:
            ee.Geometry: Validated geometry
        """
        try:
            # For TopologyException prevention, be more aggressive with square fallback
            # Check if polygon is complex (many vertices or self-intersecting)
            coordinates = aoi_geometry.get("coordinates", [])
            if coordinates and len(coordinates) > 0:
                vertex_count = len(coordinates[0])
                
                # If polygon has many vertices, use square fallback preemptively
                if vertex_count > 20:
                    logging.info(f"Polygon has {vertex_count} vertices, using square fallback to prevent topology issues")
                    if use_square_fallback:
                        return self._create_square_geometry(aoi_bounds)
            
            # First, try to clean up the geometry
            cleaned_geometry = self._clean_polygon_geometry(aoi_geometry)
            
            # Create ee.Geometry from cleaned geometry
            ee_geometry = ee.Geometry(cleaned_geometry)
            
            # Test the geometry with a simple operation (this will fail if invalid)
            try:
                # Try a simple bounds operation to validate
                bounds_test = ee_geometry.bounds().getInfo()
                logging.info(f"Geometry validation successful")
                return ee_geometry
            except Exception as bounds_error:
                logging.warning(f"Bounds test failed: {str(bounds_error)}")
                raise bounds_error
            
        except Exception as e:
            error_msg = str(e)
            logging.warning(f"Geometry validation failed: {error_msg}")
            
            # Check for topology-related errors
            if any(keyword in error_msg.lower() for keyword in ["topology", "side location", "intersection", "invalid"]):
                logging.info("Detected topology-related error, forcing square fallback")
                if use_square_fallback:
                    return self._create_square_geometry(aoi_bounds)
            
            if use_square_fallback:
                logging.info("Creating square geometry from bounds due to general error")
                return self._create_square_geometry(aoi_bounds)
            else:
                raise e
    
    def _clean_polygon_geometry(self, geometry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean polygon geometry to fix common topology issues.
        
        Args:
            geometry: GeoJSON geometry
            
        Returns:
            Dict: Cleaned geometry
        """
        if geometry.get("type") != "Polygon":
            return geometry
        
        coordinates = geometry.get("coordinates", [[]])
        if not coordinates or not coordinates[0]:
            return geometry
        
        # Get the outer ring
        outer_ring = coordinates[0]
        
        # Remove duplicate consecutive points
        cleaned_ring = []
        for i, point in enumerate(outer_ring):
            if i == 0 or point != outer_ring[i-1]:
                cleaned_ring.append(point)
        
        # Ensure the ring is closed
        if len(cleaned_ring) > 0 and cleaned_ring[0] != cleaned_ring[-1]:
            cleaned_ring.append(cleaned_ring[0])
        
        # Ensure we have at least 4 points (including closing point)
        if len(cleaned_ring) < 4:
            logging.warning("Insufficient points in polygon, cannot clean")
            return geometry
        
        # Ensure counter-clockwise winding (GeoJSON standard)
        if self._is_clockwise(cleaned_ring):
            cleaned_ring.reverse()
        
        return {
            "type": "Polygon",
            "coordinates": [cleaned_ring]
        }
    
    def _is_clockwise(self, ring: List[List[float]]) -> bool:
        """Check if a polygon ring is clockwise oriented."""
        total = 0
        for i in range(len(ring) - 1):
            total += (ring[i+1][0] - ring[i][0]) * (ring[i+1][1] + ring[i][1])
        return total > 0
    
    def _create_square_geometry(self, bounds: Dict[str, float]):
        """
        Create a square ee.Geometry from bounding box.
        
        Args:
            bounds: Bounding box {min_lng, max_lng, min_lat, max_lat}
            
        Returns:
            ee.Geometry: Square geometry
        """
        min_lng = bounds["min_lng"]
        max_lng = bounds["max_lng"] 
        min_lat = bounds["min_lat"]
        max_lat = bounds["max_lat"]
        
        # Create a simple rectangle
        square_coords = [
            [min_lng, min_lat],
            [max_lng, min_lat],
            [max_lng, max_lat],
            [min_lng, max_lat],
            [min_lng, min_lat]  # Close the polygon
        ]
        
        square_geometry = {
            "type": "Polygon",
            "coordinates": [square_coords]
        }
        
        logging.info(f"Created square geometry: {square_coords}")
        return ee.Geometry(square_geometry)
    
    async def _process_gee_results(
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
                        
                        # Get landcover class from properties (default to 60 for bare land)
                        landcover_class = properties.get("landcover", 60)
                        
                        # Calculate real hotspot score using ML model and real data
                        scoring_result = await self._calculate_real_hotspot_score(
                            centroid.y, centroid.x, area_m2  # lat, lng, area
                        )
                        
                        # Extract score and detailed breakdown
                        hotspot_score = scoring_result.get("score", 50.0)
                        aqi_data = scoring_result.get("aqi_data", {})
                        distances = scoring_result.get("distances", {})
                        population_density = scoring_result.get("population_density", 5000)
                        scoring_method = scoring_result.get("method", "unknown")
                        scoring_breakdown = scoring_result.get("breakdown", {})
                        
                        processed.append({
                            "id": f"gee_vacant_{i}",
                            "geometry": geometry,
                            "area": area_m2 / 10000,  # Convert to hectares
                            "hotspot_score": hotspot_score,
                            "landcover_class": landcover_class,
                            "centroid": [centroid.x, centroid.y],
                            "data_source": "ESA_WorldCover_GEE",
                            "processing_date": datetime.utcnow().isoformat(),
                            # Detailed scoring data
                            "aqi": aqi_data.get("aqi"),
                            "population_density": population_density,
                            "amenity_distances": distances,
                            "scoring_method": scoring_method,
                            "scoring_breakdown": scoring_breakdown
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
            
            # Load WorldCover with correct ImageCollection format
            worldcover_collection = ee.ImageCollection(self.dataset_id).first()
            worldcover = worldcover_collection.select("Map").clip(ee_geometry)
            
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
        
        logging.warning("="*50)
        logging.warning("⚠️  GENERATING SYNTHETIC FALLBACK DATA")
        logging.warning("🔧 Google Earth Engine unavailable")
        logging.warning("⚡ Fast response (not real satellite data)")
        logging.warning("="*50)
        
        print("="*50)
        print("⚠️  GENERATING SYNTHETIC FALLBACK DATA")
        print("🔧 Google Earth Engine unavailable")
        print("⚡ Fast response (not real satellite data)")
        print("="*50)
        
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
                    area_m2 = area_ha * 10000  # Convert hectares to square meters
                    lat = center_lat
                    lng = center_lng
                    
                    # Calculate detailed scoring
                    scoring_result = await self._calculate_real_hotspot_score(
                        lat, lng, area_m2
                    )
                    
                    polygons.append({
                        "id": f"synthetic_gee_{i}",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [vertices]
                        },
                        "area": area_ha,
                        "hotspot_score": scoring_result.get("score", 50.0),
                        "landcover_class": 60,
                        "centroid": [center_lng, center_lat],
                        "data_source": "Synthetic_Fallback",
                        "processing_date": datetime.utcnow().isoformat(),
                        # Detailed scoring data
                        "aqi": scoring_result.get("aqi_data", {}).get("aqi"),
                        "population_density": scoring_result.get("population_density", 5000),
                        "amenity_distances": scoring_result.get("distances", {}),
                        "scoring_method": scoring_result.get("method", "unknown"),
                        "scoring_breakdown": scoring_result.get("breakdown", {})
                    })
        
        logging.warning("="*50)
        logging.warning(f"🔧 Generated {len(polygons)} SYNTHETIC polygons")
        logging.warning("⚠️  NOT REAL SATELLITE DATA")
        logging.warning("="*50)
        
        print("="*50)
        print(f"🔧 Generated {len(polygons)} SYNTHETIC polygons")
        print("⚠️  NOT REAL SATELLITE DATA")
        print("="*50)
        
        return polygons
    
    async def _calculate_real_hotspot_score(self, lat: float, lng: float, area_m2: float) -> Dict[str, Any]:
        """
        Calculate real hotspot score using ML model and live data
        
        Args:
            lat, lng: Coordinates of the polygon centroid
            area_m2: Area of the polygon in square meters
            
        Returns:
            Dict with score, detailed breakdown, and all input data
        """
        try:
            # Get real AQI data with today's date
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Call the AQI endpoint function directly with named parameters
            aqi_result = await calculate_aqi_for_location(
                latitude=lat, 
                longitude=lng, 
                date=today
            )
            aqi = aqi_result.get("aqi", 100) if aqi_result.get("data_available", False) else 100
            
            # Get population density (simplified - use a default based on area)
            # In a real implementation, you'd integrate with your population service
            population_density = 5000  # Default urban/suburban density
            
            # Get real distance data
            distances = await distance_service.calculate_amenity_distances(lat, lng)
            
            # Calculate hotspot score using ML model
            score_result = await hotspot_scoring_service.calculate_hotspot_score(
                aqi=aqi,
                population_density=population_density,
                distances=distances
            )
            
            # Convert from 0-1 scale to 0-100 scale for backward compatibility
            score_0_100 = score_result.get("score", 0.5) * 100
            
            # Add area bonus (larger plots are more valuable for development)
            area_bonus = min(20, (area_m2 / 50000) * 10)  # Up to 20 points for large areas (5+ hectares)
            final_score = min(100, score_0_100 + area_bonus)
            
            logging.info(f"Hotspot score calculated for ({lat:.4f}, {lng:.4f}): {final_score:.1f} (method: {score_result.get('method', 'unknown')})")
            
            # Return comprehensive result
            return {
                "score": round(final_score, 1),
                "aqi_data": aqi_result,
                "population_density": population_density,
                "distances": distances,
                "method": score_result.get("method", "unknown"),
                "breakdown": score_result.get("breakdown", {}),
                "area_bonus": area_bonus,
                "base_score": score_0_100
            }
            
        except Exception as e:
            logging.error(f"Error calculating real hotspot score: {str(e)}")
            
            # Fallback to simple scoring if real scoring fails
            landcover_class = 60  # Assume bare land
            area_score = min(100, (area_m2 / 10000) * 20)  # Larger = better score
            base_score = 60 if landcover_class == 60 else 45  # Bare land scores higher
            fallback_score = min(100, base_score + area_score)
            
            logging.warning(f"Using fallback scoring: {fallback_score}")
            return {
                "score": fallback_score,
                "aqi_data": {"aqi": None, "data_available": False},
                "population_density": 5000,
                "distances": {},
                "method": "error_fallback",
                "breakdown": {"error": str(e)},
                "area_bonus": 0,
                "base_score": fallback_score
            }
    
    async def _get_population_density(self, lat: float, lng: float) -> float:
        """
        Get population density for a location
        TODO: Integrate with your population service
        """
        try:
            # This is a simplified implementation
            # In reality, you'd call your population API here
            
            # For now, return a reasonable default based on general urban patterns
            # Urban centers: 8000-15000, Suburban: 2000-8000, Rural: 100-2000
            return 5000  # Default suburban density
            
        except Exception as e:
            logging.error(f"Error getting population density: {str(e)}")
            return 5000  # Default fallback

# Global service instance  
esa_service = ESAWorldCoverService()
