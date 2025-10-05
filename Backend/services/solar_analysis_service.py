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
        Compute comprehensive solar suitability using Solar Suitability Index (SSI)
        Based on irradiance, slope, aspect, landcover, and shading factors
        """
        try:
            # Convert AOI to Earth Engine geometry
            aoi = ee.Geometry(aoi_geojson['geometry'])
            
            logger.info("🌞 Starting comprehensive solar suitability analysis...")
            
            # Check area size and adjust parameters accordingly
            aoi_area = aoi.area(maxError=1).getInfo()  # Area in square meters
            aoi_area_km2 = aoi_area / 1e6  # Convert to km²
            
            logger.info(f"📏 Analysis area: {aoi_area_km2:.1f} km²")
            
            # Dynamic parameters based on area size
            if aoi_area_km2 > 1000:  # Very large area (>1000 km²)
                SCALE = 200
                TOP_PERCENT = 5
                MIN_AREA_M2 = 10000
                MAX_PIXELS = 5e8
                logger.info("🔧 Using ultra-fast settings for very large area")
            elif aoi_area_km2 > 500:  # Large area (500-1000 km²)
                SCALE = 150
                TOP_PERCENT = 8
                MIN_AREA_M2 = 7500
                MAX_PIXELS = 7e8
                logger.info("🔧 Using fast settings for large area")
            elif aoi_area_km2 > 100:  # Medium area (100-500 km²)
                SCALE = 100
                TOP_PERCENT = 10
                MIN_AREA_M2 = 5000
                MAX_PIXELS = 1e9
                logger.info("🔧 Using balanced settings for medium area")
            else:  # Small area (<100 km²)
                SCALE = 50
                TOP_PERCENT = 15
                MIN_AREA_M2 = 2000
                MAX_PIXELS = 2e9
                logger.info("🔧 Using detailed settings for small area")
            
            YEAR = 2024
            
            # 1. DATASETS
            # ERA5-Land daily aggregated solar radiation
            era5 = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") \
                .select("surface_solar_radiation_downwards_sum") \
                .filterDate(ee.Date.fromYMD(YEAR, 1, 1), ee.Date.fromYMD(YEAR, 12, 31))
            
            # Mean solar energy (J/m²/day) -> convert to kWh/m²/day
            solar_mean = era5.mean().divide(3.6e6).rename('solar_kWh_m2_day')
            
            # DEM & derivatives
            dem = ee.Image("USGS/SRTMGL1_003")
            slope = ee.Terrain.slope(dem).rename('slope_deg')
            aspect = ee.Terrain.aspect(dem).rename('aspect_deg')
            
            # Landcover (WorldCover 2021)
            wc = ee.Image("ESA/WorldCover/v200/2021").select('Map').rename('worldcover')
            
            # 2. SUB-SCORES (0..1)
            # Solar irradiance score: normalize 2..8 kWh/m²/day -> 0..1
            S_irr = solar_mean.unitScale(2, 8).clamp(0, 1).rename('S_irr')
            
            # Slope score: prefer flatter areas (0° -> 1, 30° -> 0)
            S_slope = slope.multiply(-1).divide(30).add(1).clamp(0, 1).rename('S_slope')
            
            # Aspect score: best near south (180°) for northern hemisphere
            aspect_diff = aspect.subtract(180).abs()
            S_aspect = aspect_diff.divide(90).multiply(-1).add(1).clamp(0, 1).rename('S_aspect')
            
            # Landcover suitability (graded scoring)
            lc = wc
            S_land = ee.Image(0).rename('S_land') \
                .where(lc.eq(60), 1.0) \
                .where(lc.eq(30), 0.9) \
                .where(lc.eq(40), 0.7) \
                .where(lc.eq(50), 0.3) \
                .where(lc.eq(10), 0.2) \
                .where(lc.eq(80), 0.0)
            
            # Shade proxy: penalty for steep local relief
            S_shade = S_slope.rename('S_shade')
            
            # 3. COMBINE into Solar Suitability Index (SSI)
            # Weights (sum to 1.0)
            w_irr = 0.30      # Solar irradiance (most important)
            w_slope = 0.20    # Slope suitability
            w_aspect = 0.15   # Aspect orientation
            w_shade = 0.15    # Shading considerations
            w_land = 0.20     # Land cover suitability
            
            SSI = S_irr.multiply(w_irr) \
                .add(S_slope.multiply(w_slope)) \
                .add(S_aspect.multiply(w_aspect)) \
                .add(S_shade.multiply(w_shade)) \
                .add(S_land.multiply(w_land)) \
                .rename('ssi') \
                .clip(aoi)
            
            # 4. COMPUTE THRESHOLD for top N% within AOI
            perc = 100 - TOP_PERCENT
            percentile_reducer = ee.Reducer.percentile([perc])
            
            threshold_dict = SSI.reduceRegion(
                reducer=percentile_reducer,
                geometry=aoi,
                scale=SCALE,
                maxPixels=MAX_PIXELS,
                bestEffort=True
            )
            
            # Get threshold value
            threshold_key = f'ssi_p{int(perc)}'
            threshold = ee.Number(threshold_dict.get(threshold_key, 0.7))  # Default to 0.7 if computation fails
            
            logger.info(f"🎯 Using SSI threshold: {threshold.getInfo():.3f} for top {TOP_PERCENT}% areas")
            
            # 5. CREATE HIGH SUITABILITY MASK
            high_suitability = SSI.gte(threshold)
            
            # 6. VECTORIZE to polygons - with timeout protection
            vectors = high_suitability.selfMask().reduceToVectors(
                geometry=aoi,
                scale=SCALE,
                geometryType='polygon',
                eightConnected=False,
                labelProperty='ssi_class',
                maxPixels=MAX_PIXELS,
                bestEffort=True
            )
            
            # 7. FILTER by minimum area
            def add_area_and_filter(feature):
                area = feature.geometry().area(maxError=1)  # 1 meter error margin
                return feature.set('area_m2', area).set('area_hectares', area.divide(10000))
            
            vectors_with_area = vectors.map(add_area_and_filter)
            filtered_vectors = vectors_with_area.filter(ee.Filter.gte('area_m2', MIN_AREA_M2))
            
            # 8. ADD SSI VALUES to each polygon
            def add_ssi_stats(feature):
                # Sample SSI statistics within each polygon
                ssi_stats = SSI.reduceRegion(
                    reducer=ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True),
                    geometry=feature.geometry(),
                    scale=SCALE,
                    maxPixels=1e6,  # Reduced for individual polygons
                    bestEffort=True
                )
                
                return feature.set({
                    'ssi_mean': ssi_stats.get('ssi_mean', 0),
                    'ssi_max': ssi_stats.get('ssi_max', 0),
                    'solar_score': ee.Number(ssi_stats.get('ssi_mean', 0)).multiply(100)  # Convert to 0-100 scale
                })
            
            final_vectors = filtered_vectors.map(add_ssi_stats)
            
            # 9. GET RESULTS
            vector_data = final_vectors.getInfo()
            
            # Overall statistics
            overall_stats = SSI.reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    ee.Reducer.max(), sharedInputs=True
                ).combine(
                    ee.Reducer.min(), sharedInputs=True
                ),
                geometry=aoi,
                scale=SCALE,
                maxPixels=MAX_PIXELS,
                bestEffort=True
            )
            
            stats_data = overall_stats.getInfo()
            
            logger.info(f"✅ Solar analysis completed. Found {len(vector_data.get('features', []))} high-suitability solar areas")
            
            return {
                'success': True,
                'solar_polygons': vector_data.get('features', []),
                'statistics': {
                    'mean_ssi': stats_data.get('ssi_mean', 0),
                    'max_ssi': stats_data.get('ssi_max', 0),
                    'min_ssi': stats_data.get('ssi_min', 0),
                    'threshold_used': threshold.getInfo() if threshold else 0.7,
                    'top_percent': TOP_PERCENT
                },
                'analysis_date': datetime.now().isoformat(),
                'data_source': 'ECMWF ERA5-Land + ESA WorldCover + USGS SRTM',
                'methodology': 'Solar Suitability Index (SSI) with multi-factor analysis'
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
            
            # Run Earth Engine computation in thread pool with timeout
            loop = asyncio.get_event_loop()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        self.executor, 
                        self._compute_solar_suitability, 
                        aoi_geojson
                    ),
                    timeout=180  # 3 minute timeout
                )
            except asyncio.TimeoutError:
                logger.error("❌ Solar analysis timed out after 3 minutes")
                return {
                    'success': False,
                    'error': 'Analysis timed out. Try zooming to a smaller area or use a different map view.',
                    'solar_polygons': [],
                    'summary': {},
                    'statistics': {}
                }
            
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
                        
                        # Get SSI-based solar score from GEE analysis
                        properties = polygon.get('properties', {})
                        ssi_score = properties.get('solar_score', 70)  # Default to 70 if not available
                        solar_score = min(100.0, max(0.0, float(ssi_score))) / 100.0  # Convert to 0-1 scale
                        
                        # More realistic capacity estimation based on SSI score
                        base_capacity_per_hectare = 0.4  # MW per hectare (conservative for utility-scale)
                        estimated_capacity_mw = area_hectares * base_capacity_per_hectare * solar_score
                        
                        # Annual generation based on capacity factor (varies by solar score)
                        capacity_factor = 0.15 + (solar_score * 0.10)  # 15-25% capacity factor range
                        annual_generation_mwh = estimated_capacity_mw * 8760 * capacity_factor  # 8760 hours per year
                        
                        processed_polygon = {
                            'id': f'solar_{i}',
                            'geometry': geometry,
                            'properties': {
                                'area_hectares': round(area_hectares, 2),
                                'area_m2': round(area_m2, 2),
                                'solar_score': round(ssi_score, 1),  # Keep as 0-100 scale
                                'ssi_mean': properties.get('ssi_mean', solar_score),
                                'ssi_max': properties.get('ssi_max', solar_score),
                                'suitability_category': self._get_suitability_category(solar_score),
                                'estimated_capacity_mw': round(estimated_capacity_mw, 2),
                                'annual_generation_mwh': round(annual_generation_mwh, 2),
                                'capacity_factor': round(capacity_factor, 3),
                                'co2_offset_tons': round(annual_generation_mwh * 0.4, 2),  # ~0.4 tons CO2 per MWh
                                'analysis_type': 'solar_potential',
                                'methodology': 'SSI'
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
                'message': f'Found {len(processed_polygons)} solar hotspots in current view',
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
