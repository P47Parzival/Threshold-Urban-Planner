from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import json
import time
from services.hotspots_service import hotspots_service
from services.esa_worldcover_service import esa_service
from services.gee_service import gee_service

router = APIRouter()

# Pydantic models for request/response
class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    properties: Dict[str, Any] = {}
    geometry: Dict[str, Any]

class VacantLandRequest(BaseModel):
    aoi: GeoJSONFeature
    min_area_m2: Optional[int] = 5000  # Minimum area in square meters (0.5 hectares)
    max_polygons: Optional[int] = 100  # Maximum number of polygons to return
    use_relaxed_filter: Optional[bool] = False  # Include grassland as potential vacant land
    use_square_fallback: Optional[bool] = True  # Use square geometry if polygon is invalid

class VacantLandPolygon(BaseModel):
    id: str
    geometry: Dict[str, Any]
    area: float  # in hectares
    score: Optional[float] = 0.0  # hotspot score (0-100)
    # Additional detailed data
    aqi: Optional[float] = None
    population_density: Optional[float] = None
    amenity_distances: Optional[Dict[str, float]] = None
    scoring_method: Optional[str] = None
    scoring_breakdown: Optional[Dict[str, Any]] = None
    landcover_class: Optional[int] = None
    centroid: Optional[List[float]] = None
    data_source: Optional[str] = None

class VacantLandResponse(BaseModel):
    success: bool
    message: str
    vacant_land_polygons: List[VacantLandPolygon]
    total_area: float
    avg_score: float
    processing_time: float
    cached: bool = False  # Indicates if results came from cache
    cache_stats: Optional[Dict[str, Any]] = None
    gee_status: Optional[Dict[str, Any]] = None  # Google Earth Engine status

# Removed router startup event - moved to main.py
# This ensures GEE initialization happens at app startup, not router startup

@router.post("/", response_model=VacantLandResponse)
async def analyze_vacant_land(request: VacantLandRequest):
    """
    Analyze vacant land within the provided Area of Interest (AOI).
    
    This endpoint will:
    1. Check for cached results with overlapping AOI
    2. If cache hit: return cached data
    3. If cache miss: process ESA WorldCover data
    4. Cache results for future use
    5. Return GeoJSON of suitable vacant land areas
    """
    
    try:
        start_time = time.time()
        
        print("="*60)
        print("🎯 HOTSPOTS ANALYSIS REQUEST RECEIVED")
        print(f"📊 AOI type: {request.aoi.geometry.get('type')}")
        print(f"⏱️  Request started at: {time.time()}")
        print("="*60)
        
        logging.info(f"Processing vacant land analysis for AOI")
        
        # Extract AOI geometry
        aoi_geometry = request.aoi.geometry
        
        if aoi_geometry.get("type") != "Polygon":
            raise HTTPException(status_code=400, detail="AOI must be a Polygon geometry")
        
        # Get coordinates from the AOI polygon
        coordinates = aoi_geometry.get("coordinates", [[]])[0]  # First ring of polygon
        
        if len(coordinates) < 4:  # Minimum for a valid polygon (including closing point)
            raise HTTPException(status_code=400, detail="Invalid polygon: insufficient coordinates")
        
        # Calculate bounding box for the AOI
        lngs = [coord[0] for coord in coordinates]
        lats = [coord[1] for coord in coordinates]
        
        bbox = {
            "min_lng": min(lngs),
            "max_lng": max(lngs),
            "min_lat": min(lats),
            "max_lat": max(lats)
        }
        
        logging.info(f"AOI bounding box: {bbox}")
        
        # Step 1: Check for cached results
        cached_aoi = await hotspots_service.find_overlapping_cache(aoi_geometry, overlap_threshold=0.7)
        
        if cached_aoi:
            logging.info(f"Found overlapping cached AOI: {cached_aoi.id}")
            cached_analysis = await hotspots_service.get_cached_analysis(cached_aoi.id)
            
            if cached_analysis:
                processing_time = time.time() - start_time
                
                # Convert cached data to response format
                vacant_polygons = [
                    VacantLandPolygon(
                        id=poly.id,
                        geometry=poly.geometry.dict(),
                        area=poly.area,
                        score=poly.hotspot_score
                    ) for poly in cached_analysis.vacant_polygons
                ]
                
                return VacantLandResponse(
                    success=True,
                    message=f"Retrieved {len(vacant_polygons)} cached vacant land areas",
                    vacant_land_polygons=vacant_polygons,
                    total_area=sum(poly.area for poly in vacant_polygons),
                    avg_score=sum(poly.score or 0 for poly in vacant_polygons) / len(vacant_polygons) if vacant_polygons else 0,
                    processing_time=processing_time,
                    cached=True,
                    cache_stats=cached_analysis.summary_stats
                )
        
        # Step 2: No cache hit - process ESA WorldCover data
        print("🔍 No cache hit found - processing with ESA WorldCover")
        print(f"🛰️  GEE Status: {gee_service.is_authenticated()}")
        logging.info("No cache hit, processing ESA WorldCover data")
        
        # For complex polygons or to avoid topology issues, be more aggressive with square fallback
        polygon_coords = aoi_geometry.get("coordinates", [])
        vertex_count = len(polygon_coords[0]) if polygon_coords and len(polygon_coords) > 0 else 0
        
        # Use square fallback for complex polygons (>15 vertices) or by default
        force_square = vertex_count > 15
        if force_square:
            logging.info(f"Polygon has {vertex_count} vertices, forcing square fallback to prevent topology issues")
        
        # Get vacant land polygons from ESA WorldCover using Google Earth Engine
        vacant_polygons_data = await esa_service.get_vacant_land_polygons(
            aoi_bounds=bbox,
            aoi_geometry=aoi_geometry,
            min_area_m2=request.min_area_m2,  # Use request parameter
            max_polygons=request.max_polygons,  # Use request parameter
            use_relaxed_filter=request.use_relaxed_filter,  # Use request parameter
            use_square_fallback=True  # Always enable square fallback
        )
        
        # Convert to response format with all detailed data
        vacant_polygons = [
            VacantLandPolygon(
                id=poly["id"],
                geometry=poly["geometry"],
                area=poly["area"],
                score=poly["hotspot_score"],
                aqi=poly.get("aqi"),
                population_density=poly.get("population_density"),
                amenity_distances=poly.get("amenity_distances"),
                scoring_method=poly.get("scoring_method"),
                scoring_breakdown=poly.get("scoring_breakdown"),
                landcover_class=poly.get("landcover_class"),
                centroid=poly.get("centroid"),
                data_source=poly.get("data_source")
            ) for poly in vacant_polygons_data
        ]
        
        # Calculate summary statistics
        total_area = sum(poly.area for poly in vacant_polygons)
        avg_score = sum(poly.score or 0 for poly in vacant_polygons) / len(vacant_polygons) if vacant_polygons else 0
        
        summary_stats = {
            "total_polygons": len(vacant_polygons),
            "total_area_ha": total_area,
            "avg_hotspot_score": avg_score,
            "min_area_ha": min(poly.area for poly in vacant_polygons) if vacant_polygons else 0,
            "max_area_ha": max(poly.area for poly in vacant_polygons) if vacant_polygons else 0,
            "min_area_m2": request.min_area_m2,
            "analysis_method": "ESA_WorldCover_GEE_2021",
            "use_relaxed_filter": request.use_relaxed_filter,
            "use_square_fallback": request.use_square_fallback
        }
        
        processing_time = time.time() - start_time
        
        # Step 3: Cache the results for future use
        try:
            await hotspots_service.cache_aoi_analysis(
                aoi_geometry=aoi_geometry,
                aoi_bounds=bbox,
                vacant_polygons=vacant_polygons_data,
                processing_time=processing_time,
                summary_stats=summary_stats
            )
            logging.info("Successfully cached analysis results")
        except Exception as cache_error:
            logging.warning(f"Failed to cache results: {str(cache_error)}")
        
        return VacantLandResponse(
            success=True,
            message=f"Found {len(vacant_polygons)} vacant land areas within AOI",
            vacant_land_polygons=vacant_polygons,
            total_area=total_area,
            avg_score=avg_score,
            processing_time=processing_time,
            cached=False,
            cache_stats=summary_stats,
            gee_status=gee_service.get_status()  # Include GEE status
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (400, etc.)
        raise
    except Exception as e:
        error_message = str(e)
        logging.error(f"Error in vacant land analysis: {error_message}")
        
        # Handle specific TopologyException
        if "TopologyException" in error_message or "side location conflict" in error_message:
            # Try again with square fallback forced
            try:
                logging.info("Retrying with forced square fallback due to topology error")
                
                # Retry with square fallback
                vacant_polygons_data = await esa_service.get_vacant_land_polygons(
                    aoi_bounds=bbox,
                    aoi_geometry=aoi_geometry,
                    min_area_m2=request.min_area_m2,
                    max_polygons=request.max_polygons,
                    use_relaxed_filter=request.use_relaxed_filter,
                    use_square_fallback=True  # Force square fallback
                )
                
                # Convert to response format
                vacant_polygons = [
                    VacantLandPolygon(
                        id=poly["id"],
                        geometry=poly["geometry"],
                        area=poly["area"],
                        score=poly["hotspot_score"]
                    ) for poly in vacant_polygons_data
                ]
                
                # Calculate summary
                total_area = sum(poly.area for poly in vacant_polygons)
                avg_score = sum(poly.score or 0 for poly in vacant_polygons) / len(vacant_polygons) if vacant_polygons else 0
                processing_time = time.time() - start_time
                
                return VacantLandResponse(
                    success=True,
                    message=f"Found {len(vacant_polygons)} vacant land areas (used square fallback due to geometry issues)",
                    vacant_land_polygons=vacant_polygons,
                    total_area=total_area,
                    avg_score=avg_score,
                    processing_time=processing_time,
                    cached=False,
                    cache_stats={"analysis_method": "ESA_WorldCover_GEE_2021_Square_Fallback"},
                    gee_status=gee_service.get_status()
                )
                
            except Exception as retry_error:
                logging.error(f"Square fallback retry also failed: {str(retry_error)}")
                raise HTTPException(status_code=500, detail=f"Geometry error (tried square fallback): {str(retry_error)}")
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_message}")

@router.get("/health")
async def health_check():
    """Health check endpoint for the vacant land service."""
    cache_stats = await hotspots_service.get_cache_statistics()
    gee_status = gee_service.get_status()
    return {
        "status": "healthy", 
        "service": "vacant-land-analysis",
        "cache_stats": cache_stats,
        "gee_status": gee_status
    }

@router.get("/cache/stats")
async def get_cache_statistics():
    """Get detailed cache statistics."""
    return await hotspots_service.get_cache_statistics()

@router.get("/gee/status")
async def get_gee_status():
    """Get Google Earth Engine status."""
    return gee_service.get_status()

@router.post("/landcover/stats")
async def get_landcover_statistics(aoi: GeoJSONFeature):
    """Get detailed land cover statistics for an AOI using Google Earth Engine."""
    try:
        stats = await esa_service.get_landcover_statistics(aoi.geometry)
        return {
            "success": True,
            "landcover_stats": stats,
            "gee_status": gee_service.get_status()
        }
    except Exception as e:
        logging.error(f"Error getting land cover statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting land cover statistics: {str(e)}")
