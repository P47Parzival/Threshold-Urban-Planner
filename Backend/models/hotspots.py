from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class GeoJSONGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]  # Polygon coordinates

class AOICache(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    aoi_geometry: GeoJSONGeometry
    aoi_bounds: Dict[str, float]  # min_lng, max_lng, min_lat, max_lat
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    processing_time: float
    total_area: float  # Total area of AOI in hectares
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class VacantLandPolygon(BaseModel):
    id: str
    geometry: GeoJSONGeometry
    area: float  # in hectares
    hotspot_score: float  # 0-100 score
    amenity_distances: Optional[Dict[str, float]] = None  # distances to amenities
    landcover_class: Optional[int] = None  # ESA WorldCover class
    centroid: List[float]  # [lng, lat] for the polygon center
    # Detailed scoring breakdown
    aqi: Optional[float] = None  # Air Quality Index
    population_density: Optional[float] = None  # People per sq km
    scoring_method: Optional[str] = None  # ml_model or rule_based_fallback
    scoring_breakdown: Optional[Dict[str, Any]] = None  # Detailed component scores

class VacantLandAnalysis(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    aoi_cache_id: PyObjectId  # Reference to AOICache
    vacant_polygons: List[VacantLandPolygon]
    summary_stats: Dict[str, Any]
    data_sources: Dict[str, str]  # Track data sources used
    analysis_version: str = "1.0"  # For future algorithm updates
    
    class Config:
        allow_population_by_field_name = True  
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
