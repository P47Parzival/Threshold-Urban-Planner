"""
Solar Analysis API Routes for THRESHOLD Platform
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import time
import logging

from services.solar_analysis_service import solar_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["solar-analysis"])

class SolarAnalysisRequest(BaseModel):
    aoi: Dict[str, Any]  # GeoJSON feature

class SolarPolygon(BaseModel):
    id: str
    geometry: Dict[str, Any]
    properties: Dict[str, Any]

class SolarSummary(BaseModel):
    total_suitable_area_hectares: float
    total_estimated_capacity_mw: float
    total_annual_generation_mwh: float
    total_co2_offset_tons_per_year: float
    average_solar_score: float

class SolarAnalysisResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    solar_polygons: List[SolarPolygon] = []
    summary: Optional[SolarSummary] = None
    statistics: Optional[Dict[str, Any]] = None
    analysis_date: Optional[str] = None
    data_source: Optional[str] = None
    processing_time: Optional[float] = None

@router.post("/solar-analysis/", response_model=SolarAnalysisResponse)
async def analyze_solar_potential(request: SolarAnalysisRequest):
    """
    Analyze solar generation potential for a given Area of Interest (AOI)
    
    This endpoint:
    1. Takes a GeoJSON polygon as AOI
    2. Uses Google Earth Engine to analyze solar irradiance, slope, and land cover
    3. Identifies suitable areas for solar installations
    4. Calculates potential capacity, generation, and environmental impact
    5. Returns polygons with detailed solar potential data
    """
    start_time = time.time()
    
    try:
        logger.info("🌞 Received solar analysis request")
        
        # Validate input
        if not request.aoi:
            raise HTTPException(status_code=400, detail="AOI is required")
        
        if not request.aoi.get('geometry'):
            raise HTTPException(status_code=400, detail="AOI must contain geometry")
        
        # Initialize service if needed
        if not solar_service.initialized:
            await solar_service.initialize()
        
        # Perform solar analysis
        result = await solar_service.analyze_solar_potential(request.aoi)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        result['processing_time'] = round(processing_time, 2)
        
        if not result['success']:
            logger.error(f"❌ Solar analysis failed: {result.get('error', 'Unknown error')}")
            raise HTTPException(
                status_code=500, 
                detail=f"Solar analysis failed: {result.get('error', 'Unknown error')}"
            )
        
        logger.info(f"✅ Solar analysis completed in {processing_time:.2f}s. Found {len(result['solar_polygons'])} suitable areas")
        
        # Convert to response model
        solar_polygons = [
            SolarPolygon(
                id=polygon['id'],
                geometry=polygon['geometry'],
                properties=polygon['properties']
            )
            for polygon in result['solar_polygons']
        ]
        
        summary = None
        if result.get('summary'):
            summary = SolarSummary(**result['summary'])
        
        return SolarAnalysisResponse(
            success=True,
            message=result.get('message'),
            solar_polygons=solar_polygons,
            summary=summary,
            statistics=result.get('statistics'),
            analysis_date=result.get('analysis_date'),
            data_source=result.get('data_source'),
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ Unexpected error in solar analysis: {e}")
        
        return SolarAnalysisResponse(
            success=False,
            error=f"Unexpected error: {str(e)}",
            processing_time=processing_time
        )

@router.get("/solar-analysis/health")
async def solar_analysis_health():
    """Health check for solar analysis service"""
    try:
        if not solar_service.initialized:
            await solar_service.initialize()
        
        return {
            "status": "healthy",
            "service": "Solar Analysis Service",
            "gee_initialized": solar_service.initialized,
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "Solar Analysis Service", 
            "error": str(e),
            "gee_initialized": False,
            "timestamp": time.time()
        }
