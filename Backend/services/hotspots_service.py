from motor.motor_asyncio import AsyncIOMotorDatabase
from models.hotspots import AOICache, VacantLandAnalysis, GeoJSONGeometry
from database.connection import get_database
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from bson import ObjectId
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union
import geojson

class HotspotsService:
    def __init__(self):
        self.db: AsyncIOMotorDatabase = None
        self.aoi_cache_collection = None
        self.vacant_land_collection = None
    
    async def initialize(self):
        """Initialize database connection and collections."""
        self.db = await get_database()
        self.aoi_cache_collection = self.db.aoi_cache
        self.vacant_land_collection = self.db.vacant_land_analysis
        
        # Create geospatial index for AOI bounds
        await self.aoi_cache_collection.create_index([("aoi_geometry", "2dsphere")])
        await self.vacant_land_collection.create_index([("aoi_cache_id", 1)])
        
        logging.info("HotspotsService initialized with MongoDB collections")
    
    async def find_overlapping_cache(self, aoi_geometry: Dict[str, Any], overlap_threshold: float = 0.8) -> Optional[AOICache]:
        """
        Find cached AOI that significantly overlaps with the given AOI.
        
        Args:
            aoi_geometry: GeoJSON geometry of the AOI
            overlap_threshold: Minimum overlap ratio (0-1) to consider a match
            
        Returns:
            AOICache object if significant overlap found, None otherwise   
        """
        try:
            # Convert AOI to Shapely polygon for overlap calculation
            aoi_polygon = shape(aoi_geometry)
            aoi_area = aoi_polygon.area
            
            # Query MongoDB for geometrically intersecting AOIs
            cursor = self.aoi_cache_collection.find({
                "aoi_geometry": {
                    "$geoIntersects": {
                        "$geometry": aoi_geometry
                    }
                },
                # Only consider recent analyses (within last 30 days)
                "analysis_date": {
                    "$gte": datetime.utcnow() - timedelta(days=30)
                }
            })
            
            # Check overlap ratio for each intersecting AOI
            async for cached_aoi_doc in cursor:
                try:
                    cached_geometry = cached_aoi_doc["aoi_geometry"]
                    cached_polygon = shape(cached_geometry)
                    
                    # Calculate intersection area
                    intersection = aoi_polygon.intersection(cached_polygon)
                    intersection_area = intersection.area
                    
                    # Calculate overlap ratio (intersection / union)
                    union_area = aoi_polygon.union(cached_polygon).area
                    overlap_ratio = intersection_area / union_area if union_area > 0 else 0
                    
                    if overlap_ratio >= overlap_threshold:
                        logging.info(f"Found overlapping cache with {overlap_ratio:.2%} overlap")
                        return AOICache(**cached_aoi_doc)
                        
                except Exception as e:
                    logging.warning(f"Error processing cached AOI {cached_aoi_doc.get('_id')}: {str(e)}")
                    continue
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding overlapping cache: {str(e)}")
            return None
    
    async def get_cached_analysis(self, aoi_cache_id: ObjectId) -> Optional[VacantLandAnalysis]:
        """Retrieve cached vacant land analysis by AOI cache ID."""
        try:
            analysis_doc = await self.vacant_land_collection.find_one({"aoi_cache_id": aoi_cache_id})
            if analysis_doc:
                return VacantLandAnalysis(**analysis_doc)
            return None
        except Exception as e:
            logging.error(f"Error retrieving cached analysis: {str(e)}")
            return None
    
    async def cache_aoi_analysis(
        self, 
        aoi_geometry: Dict[str, Any], 
        aoi_bounds: Dict[str, float],
        vacant_polygons: List[Dict[str, Any]],
        processing_time: float,
        summary_stats: Dict[str, Any]
    ) -> ObjectId:
        """
        Cache the AOI and its analysis results.
        
        Returns:
            ObjectId of the cached analysis
        """
        try:
            # Calculate total AOI area
            aoi_polygon = shape(aoi_geometry)
            total_area_deg2 = aoi_polygon.area
            # Rough conversion to hectares (very approximate)
            total_area_ha = total_area_deg2 * 111000 * 111000 / 10000  # deg² to ha
            
            # Create AOI cache entry
            aoi_cache = AOICache(
                aoi_geometry=GeoJSONGeometry(**aoi_geometry),
                aoi_bounds=aoi_bounds,
                processing_time=processing_time,
                total_area=total_area_ha
            )
            
            # Insert AOI cache
            aoi_result = await self.aoi_cache_collection.insert_one(aoi_cache.dict(by_alias=True))
            aoi_cache_id = aoi_result.inserted_id
            
            # Create vacant land analysis entry
            vacant_analysis = VacantLandAnalysis(
                aoi_cache_id=aoi_cache_id,
                vacant_polygons=vacant_polygons,
                summary_stats=summary_stats,
                data_sources={
                    "satellite": "ESA WorldCover 2021",
                    "amenities": "Google Places API",
                    "analysis_date": datetime.utcnow().isoformat()
                }
            )
            
            # Insert analysis
            analysis_result = await self.vacant_land_collection.insert_one(vacant_analysis.dict(by_alias=True))
            
            logging.info(f"Cached AOI analysis: AOI={aoi_cache_id}, Analysis={analysis_result.inserted_id}")
            return analysis_result.inserted_id
            
        except Exception as e:
            logging.error(f"Error caching AOI analysis: {str(e)}")
            raise
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get statistics about cached data."""
        try:
            aoi_count = await self.aoi_cache_collection.count_documents({})
            analysis_count = await self.vacant_land_collection.count_documents({})
            
            # Get recent cache hits (last 7 days)
            recent_date = datetime.utcnow() - timedelta(days=7)
            recent_analyses = await self.aoi_cache_collection.count_documents({
                "analysis_date": {"$gte": recent_date}
            })
            
            return {
                "total_cached_aois": aoi_count,
                "total_analyses": analysis_count,
                "recent_analyses_7d": recent_analyses,
                "cache_enabled": True
            }
            
        except Exception as e:
            logging.error(f"Error getting cache statistics: {str(e)}")
            return {"cache_enabled": False, "error": str(e)}

# Global service instance
hotspots_service = HotspotsService()
