"""
Solar Analysis Service for THRESHOLD Platform
Analyzes solar generation potential using Google Earth Engine
"""

import ee
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SolarAnalysisService:
    def __init__(self):
        self.initialized = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    async def initialize(self):
        """Initialize Google Earth Engine"""
        try:
            if not self.initialized:
                # Initialize Earth Engine
                ee.Initialize()
                self.initialized = True
                logger.info("✅ Solar Analysis Service initialized with Google Earth Engine")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Solar Analysis Service: {e}")
            raise

    def _compute_solar_suitability(self, aoi_geojson: Dict) -> Dict:
        """
        Compute solar suitability using Google Earth Engine
        Based on solar irradiance, slope, and land cover
        """
        try:
            # Convert AOI to Earth Engine geometry
            aoi = ee.Geometry(aoi_geojson['geometry'])
            
            logger.info("🌞 Starting solar suitability analysis...")
            
            # 1. Load datasets
            # Solar irradiance data (NASA POWER)
            # ✅ Solar irradiance data (ECMWF ERA5-Land)
            # 1. Load datasets
            # ✅ Solar irradiance data (ECMWF ERA5-Land)
            solar_collection = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") \
                .select("surface_solar_radiation_downwards_sum") \
                .filterDate('2024-01-01', '2024-12-31')

            # Convert from J/m² → kWh/m²/day
            solar_mean = solar_collection.mean().divide(3.6e6)

            # DEM for slope calculation
            dem = ee.Image("USGS/SRTMGL1_003")
            slope = ee.Terrain.slope(dem)

            # ESA WorldCover for land types
            landcover = ee.Image("ESA/WorldCover/v200/2021").select("Map")

            # Mask suitable land types (bare = 60, grass = 30, cropland = 40)
            suitable_land = landcover.eq(60).Or(landcover.eq(30)).Or(landcover.eq(40))

            # Solar irradiance (ERA5-Land)
            solar_irradiance = solar_mean.select("surface_solar_radiation_downwards_sum")

            # Apply slope factor
            slope_rad = slope.multiply(3.14159 / 180)
            slope_factor = slope_rad.cos()

            # Combine irradiance & slope
            suitability_raw = solar_irradiance.multiply(slope_factor)

            # Mask by suitable land
            suitability_masked = suitability_raw.multiply(suitable_land)

            # Normalize (2–8 kWh/m²/day is typical global solar potential range)
            suitability_normalized = suitability_masked.unitScale(2, 8).clamp(0, 1)

            # 8. Create high suitability areas (threshold > 0.6)
            high_suitability = suitability_normalized.gt(0.6)
            
            # 9. Convert to vectors (polygons)
            vectors = high_suitability.selfMask().reduceToVectors(
                geometry=aoi,
                scale=100,  # 100m resolution
                geometryType='polygon',
                labelProperty='solar_score',
                bestEffort=True,
                maxPixels=1e8
            )
            
            # 10. Get additional statistics
            stats = suitability_normalized.reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    ee.Reducer.max(), sharedInputs=True
                ).combine(
                    ee.Reducer.min(), sharedInputs=True
                ),
                geometry=aoi,
                scale=100,
                maxPixels=1e8
            )
            
            # 11. Get results
            vector_data = vectors.getInfo()
            stats_data = stats.getInfo()
            
            logger.info(f"✅ Solar analysis completed. Found {len(vector_data.get('features', []))} suitable areas")
            
            return {
                'success': True,
                'solar_polygons': vector_data.get('features', []),
                'statistics': {
                    'mean_suitability': stats_data.get('ALLSKY_SFC_SW_DWN_mean', 0),
                    'max_suitability': stats_data.get('ALLSKY_SFC_SW_DWN_max', 0),
                    'min_suitability': stats_data.get('ALLSKY_SFC_SW_DWN_min', 0)
                },
                'analysis_date': datetime.now().isoformat(),
                'data_source': 'NASA POWER + ESA WorldCover + USGS SRTM'
            }
            
        except Exception as e:
            logger.error(f"❌ Solar suitability computation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'solar_polygons': [],
                'statistics': {}
            }

    async def analyze_solar_potential(self, aoi_geojson: Dict) -> Dict[str, Any]:
        """
        Analyze solar generation potential for given AOI
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            logger.info("🔍 Starting solar potential analysis...")
            
            # Run Earth Engine computation in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._compute_solar_suitability, 
                aoi_geojson
            )
            
            if not result['success']:
                return result
            
            # Process and enhance results
            solar_polygons = result['solar_polygons']
            processed_polygons = []
            
            for i, polygon in enumerate(solar_polygons):
                try:
                    # Calculate area
                    geometry = polygon.get('geometry', {})
                    if geometry.get('type') == 'Polygon':
                        coords = geometry.get('coordinates', [[]])[0]
                        area_m2 = self._calculate_polygon_area(coords)
                        area_hectares = area_m2 / 10000
                        
                        # Estimate solar potential
                        solar_score = min(1.0, max(0.0, (i + 1) / len(solar_polygons)))  # Simplified scoring
                        estimated_capacity_mw = area_hectares * 0.5 * solar_score  # ~0.5 MW per hectare for solar farms
                        annual_generation_mwh = estimated_capacity_mw * 1500 * solar_score  # ~1500 hours equivalent
                        
                        processed_polygon = {
                            'id': f'solar_{i}',
                            'geometry': geometry,
                            'properties': {
                                'area_hectares': round(area_hectares, 2),
                                'area_m2': round(area_m2, 2),
                                'solar_score': round(solar_score * 100, 1),  # Convert to 0-100 scale
                                'suitability_category': self._get_suitability_category(solar_score),
                                'estimated_capacity_mw': round(estimated_capacity_mw, 2),
                                'annual_generation_mwh': round(annual_generation_mwh, 2),
                                'co2_offset_tons': round(annual_generation_mwh * 0.4, 2),  # ~0.4 tons CO2 per MWh
                                'analysis_type': 'solar_potential'
                            }
                        }
                        processed_polygons.append(processed_polygon)
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error processing solar polygon {i}: {e}")
                    continue
            
            # Calculate summary statistics
            total_area = sum(p['properties']['area_hectares'] for p in processed_polygons)
            total_capacity = sum(p['properties']['estimated_capacity_mw'] for p in processed_polygons)
            total_generation = sum(p['properties']['annual_generation_mwh'] for p in processed_polygons)
            total_co2_offset = sum(p['properties']['co2_offset_tons'] for p in processed_polygons)
            
            return {
                'success': True,
                'message': f'Found {len(processed_polygons)} suitable solar areas',
                'solar_polygons': processed_polygons,
                'summary': {
                    'total_suitable_area_hectares': round(total_area, 2),
                    'total_estimated_capacity_mw': round(total_capacity, 2),
                    'total_annual_generation_mwh': round(total_generation, 2),
                    'total_co2_offset_tons_per_year': round(total_co2_offset, 2),
                    'average_solar_score': round(sum(p['properties']['solar_score'] for p in processed_polygons) / len(processed_polygons), 1) if processed_polygons else 0
                },
                'statistics': result['statistics'],
                'analysis_date': result['analysis_date'],
                'data_source': result['data_source'],
                'processing_time': 0  # Will be calculated by the API endpoint
            }
            
        except Exception as e:
            logger.error(f"❌ Solar analysis failed: {e}")
            return {
                'success': False,
                'error': f'Solar analysis failed: {str(e)}',
                'solar_polygons': [],
                'summary': {},
                'statistics': {}
            }

    def _calculate_polygon_area(self, coordinates: List[List[float]]) -> float:
        """Calculate polygon area using shoelace formula (approximate)"""
        try:
            if len(coordinates) < 3:
                return 0
            
            # Simple area calculation (not geodesically accurate, but good approximation)
            area = 0
            n = len(coordinates)
            for i in range(n):
                j = (i + 1) % n
                area += coordinates[i][0] * coordinates[j][1]
                area -= coordinates[j][0] * coordinates[i][1]
            area = abs(area) / 2.0
            
            # Convert from decimal degrees to approximate square meters
            # This is a rough approximation - for precise calculations, use proper geodesic methods
            lat_avg = sum(coord[1] for coord in coordinates) / len(coordinates)
            meters_per_degree = 111320 * abs(lat_avg * 3.14159 / 180)  # Rough conversion
            area_m2 = area * meters_per_degree * meters_per_degree
            
            return area_m2
            
        except Exception as e:
            logger.warning(f"⚠️ Area calculation failed: {e}")
            return 0

    def _get_suitability_category(self, score: float) -> str:
        """Get suitability category based on score"""
        if score >= 0.8:
            return 'Excellent'
        elif score >= 0.6:
            return 'Very Good'
        elif score >= 0.4:
            return 'Good'
        elif score >= 0.2:
            return 'Fair'
        else:
            return 'Poor'

# Global service instance
solar_service = SolarAnalysisService()
