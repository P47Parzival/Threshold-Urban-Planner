from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any
from enum import Enum

class ServiceType(str, Enum):
    PARKS = "parks"
    FOOD = "food"
    HEALTHCARE = "healthcare"
    TRANSPORT = "transport"

class NeedLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class AOIBounds(BaseModel):
    north: float = Field(..., description="Northern boundary latitude")
    south: float = Field(..., description="Southern boundary latitude")
    east: float = Field(..., description="Eastern boundary longitude")
    west: float = Field(..., description="Western boundary longitude")

class ServiceAnalysisRequest(BaseModel):
    aoi_bounds: AOIBounds
    service_types: List[ServiceType] = Field(..., min_items=1, description="Types of services to analyze")
    grid_resolution: float = Field(default=2.0, ge=0.5, le=10.0, description="Grid cell size in kilometers")
    
class ServiceGap(BaseModel):
    center_lat: float = Field(..., description="Latitude of the service gap center")
    center_lng: float = Field(..., description="Longitude of the service gap center")
    service_type: ServiceType
    distance_to_nearest: float = Field(..., description="Distance to nearest service in kilometers")
    need_level: NeedLevel
    area_size: float = Field(..., description="Area size in square kilometers")
    recommendation: str = Field(..., description="Recommendation for addressing this gap")

class ServiceSummary(BaseModel):
    total_gaps: int = Field(..., description="Total number of gaps for this service")
    high_priority: int = Field(..., description="Number of high priority gaps")
    medium_priority: int = Field(..., description="Number of medium priority gaps")
    low_priority: int = Field(..., description="Number of low priority gaps")
    avg_distance: float = Field(..., description="Average distance to nearest service")

class ServiceAnalysisResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    total_service_gaps: int = Field(..., description="Total gaps across all services")
    analysis_summary: Dict[str, ServiceSummary] = Field(..., description="Summary by service type")
    service_gaps: Dict[str, List[ServiceGap]] = Field(..., description="Detailed gaps by service type")
    processing_time: Optional[float] = None
    data_source: str = Field(default="OpenStreetMap", description="Source of service location data")
    search_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed search results for each service type")