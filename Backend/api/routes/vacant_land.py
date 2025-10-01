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

class VacantLandPolygon(BaseModel):
    id: str
    geometry: Dict[str, Any]
    area: float  # in hectares
    score: Optional[float] = 0.0  # hotspot score (0-100)

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

@router.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await hotspots_service.initialize()
    # Initialize Google Earth Engine
    gee_initialized = await gee_service.initialize()
    if gee_initialized:
        logging.info("Google Earth Engine initialized successfully")
    else:
        logging.warning("Google Earth Engine initialization failed - will use fallback data")

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
        logging.info("No cache hit, processing ESA WorldCover data")
        
        # Get vacant land polygons from ESA WorldCover using Google Earth Engine
        vacant_polygons_data = await esa_service.get_vacant_land_polygons(
            aoi_bounds=bbox,
            aoi_geometry=aoi_geometry,
            min_area_m2=request.min_area_m2,  # Use request parameter
            max_polygons=request.max_polygons,  # Use request parameter
            use_relaxed_filter=request.use_relaxed_filter  # Use request parameter
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
            "use_relaxed_filter": request.use_relaxed_filter
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
        logging.error(f"Error in vacant land analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
