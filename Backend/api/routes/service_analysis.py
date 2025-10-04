from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging
from models.service_analysis import ServiceAnalysisRequest, ServiceAnalysisResponse
from services.service_analysis_service import service_analysis_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=ServiceAnalysisResponse)
async def analyze_services(request: ServiceAnalysisRequest) -> ServiceAnalysisResponse:
    """
    Analyze service gaps (parks, food, healthcare, transport) within an Area of Interest (AOI).
    
    This endpoint:
    1. Takes AOI bounds and service types to analyze
    2. Generates a grid of analysis points within the AOI
    3. Fetches service locations from OpenStreetMap
    4. Calculates distances from each grid point to nearest services
    5. Identifies service gaps based on distance thresholds
    6. Returns detailed gap analysis with recommendations
    
    Args:
        request: ServiceAnalysisRequest containing AOI bounds, service types, and grid resolution
        
    Returns:
        ServiceAnalysisResponse with service gaps, summary statistics, and recommendations
    """
    try:
        print(f"🔍 Received service analysis request for {len(request.service_types)} services")
        print(f"📍 AOI: ({request.aoi_bounds.south:.4f}, {request.aoi_bounds.west:.4f}) to ({request.aoi_bounds.north:.4f}, {request.aoi_bounds.east:.4f})")
        print(f"🔲 Grid resolution: {request.grid_resolution}km")
        
        # Validate AOI bounds
        if (request.aoi_bounds.north <= request.aoi_bounds.south or 
            request.aoi_bounds.east <= request.aoi_bounds.west):
            raise HTTPException(
                status_code=400, 
                detail="Invalid AOI bounds: north must be > south, east must be > west"
            )
        
        # Check if service is initialized
        if not service_analysis_service.is_initialized:
            print("🔧 Initializing service analysis service...")
            await service_analysis_service.initialize()
        
        # Perform the analysis
        print("🚀 Starting service gap analysis...")
        result = await service_analysis_service.analyze_service_gaps(request)
        print(f"🎯 Analysis result: {result.total_service_gaps} gaps, success={result.success}")
        
        print(f"✅ Analysis complete: {result.total_service_gaps} gaps found")
        print(f"📤 Sending response to frontend...")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service analysis error: {str(e)}", exc_info=True)
        print(f"❌ Service analysis error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Service analysis failed: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for service analysis"""
    return {
        "status": "healthy",
        "service": "service_analysis",
        "initialized": service_analysis_service.is_initialized,
        "supported_services": ["parks", "food", "healthcare", "transport"]
    }