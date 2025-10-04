import asyncio
import aiohttp
import math
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import os
from models.service_analysis import (
    ServiceType, NeedLevel, ServiceGap, ServiceSummary, 
    ServiceAnalysisRequest, ServiceAnalysisResponse, AOIBounds
)

class ServiceAnalysisService:
    def __init__(self):
        self.google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        self.is_initialized = False
        
        # Service distance thresholds (in kilometers)
        self.service_thresholds = {
            ServiceType.PARKS: {"good": 2.0, "fair": 5.0, "poor": 10.0},
            ServiceType.FOOD: {"good": 3.0, "fair": 8.0, "poor": 15.0},
            ServiceType.HEALTHCARE: {"good": 5.0, "fair": 15.0, "poor": 25.0},
            ServiceType.TRANSPORT: {"good": 1.0, "fair": 3.0, "poor": 5.0}
        }
        
        # OpenStreetMap Overpass API query templates
        self.overpass_queries = {
            ServiceType.PARKS: '''
                [out:json][timeout:25];
                (
                  way["leisure"="park"]({{bbox}});
                  way["leisure"="playground"]({{bbox}});
                  way["leisure"="recreation_ground"]({{bbox}});
                  relation["leisure"="park"]({{bbox}});
                );
                out center;
            ''',
            ServiceType.FOOD: '''
                [out:json][timeout:25];
                (
                  node["shop"="supermarket"]({{bbox}});
                  node["shop"="convenience"]({{bbox}});
                  node["shop"="grocery"]({{bbox}});
                  node["amenity"="marketplace"]({{bbox}});
                  way["shop"="supermarket"]({{bbox}});
                  way["shop"="convenience"]({{bbox}});
                );
                out center;
            ''',
            ServiceType.HEALTHCARE: '''
                [out:json][timeout:25];
                (
                  node["amenity"="hospital"]({{bbox}});
                  node["amenity"="clinic"]({{bbox}});
                  node["amenity"="doctors"]({{bbox}});
                  way["amenity"="hospital"]({{bbox}});
                  way["amenity"="clinic"]({{bbox}});
                );
                out center;
            ''',
            ServiceType.TRANSPORT: '''
                [out:json][timeout:25];
                (
                  node["public_transport"="station"]({{bbox}});
                  node["railway"="station"]({{bbox}});
                  node["amenity"="bus_station"]({{bbox}});
                  node["highway"="bus_stop"]({{bbox}});
                  way["public_transport"="station"]({{bbox}});
                );
                out center;
            '''
        }

    async def initialize(self):
        """Initialize the service analysis system"""
        print("🔍 Initializing Service Analysis Service...")
        print(f"🗺️  Google Maps API: {'✅ Available' if self.google_maps_api_key else '❌ Missing (using OSM only)'}")
        self.is_initialized = True
        return True

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Haversine distance between two points in kilometers"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    def _generate_grid_points(self, bounds: AOIBounds, resolution_km: float) -> List[Tuple[float, float]]:
        """Generate a grid of points within the AOI bounds"""
        # Convert km to approximate degrees (rough approximation)
        lat_step = resolution_km / 111.0  # 1 degree ≈ 111 km
        lng_step = resolution_km / (111.0 * math.cos(math.radians((bounds.north + bounds.south) / 2)))
        
        points = []
        lat = bounds.south
        while lat <= bounds.north:
            lng = bounds.west
            while lng <= bounds.east:
                points.append((lat, lng))
                lng += lng_step
            lat += lat_step
        
        print(f"📍 Generated {len(points)} grid points for analysis")
        return points

    async def _fetch_osm_services(self, service_type: ServiceType, bounds: AOIBounds) -> List[Tuple[float, float]]:
        """Fetch service locations from OpenStreetMap using Overpass API"""
        bbox_str = f"{bounds.south},{bounds.west},{bounds.north},{bounds.east}"
        query = self.overpass_queries[service_type].replace("{{bbox}}", bbox_str)
        
        overpass_url = "http://overpass-api.de/api/interpreter"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(overpass_url, data=query, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        services = []
                        
                        for element in data.get('elements', []):
                            if element.get('type') == 'node':
                                lat, lng = element.get('lat'), element.get('lon')
                                if lat and lng:
                                    services.append((lat, lng))
                            elif element.get('type') in ['way', 'relation'] and 'center' in element:
                                center = element['center']
                                lat, lng = center.get('lat'), center.get('lon')
                                if lat and lng:
                                    services.append((lat, lng))
                        
                        print(f"🗺️  Found {len(services)} {service_type.value} locations from OSM")
                        return services
                    else:
                        print(f"❌ OSM API error for {service_type.value}: {response.status}")
                        return []
        except Exception as e:
            print(f"❌ Error fetching {service_type.value} from OSM: {str(e)}")
            return []

    def _determine_need_level(self, distance: float, service_type: ServiceType) -> NeedLevel:
        """Determine need level based on distance and service type"""
        thresholds = self.service_thresholds[service_type]
        
        if distance > thresholds["poor"]:
            return NeedLevel.HIGH
        elif distance > thresholds["fair"]:
            return NeedLevel.MEDIUM
        else:
            return NeedLevel.LOW

    def _generate_recommendation(self, service_type: ServiceType, need_level: NeedLevel, distance: float) -> str:
        """Generate recommendation based on service gap"""
        service_names = {
            ServiceType.PARKS: "park or recreational facility",
            ServiceType.FOOD: "grocery store or supermarket",
            ServiceType.HEALTHCARE: "healthcare facility or clinic",
            ServiceType.TRANSPORT: "public transport station"
        }
        
        service_name = service_names[service_type]
        
        if need_level == NeedLevel.HIGH:
            return f"High priority: Establish new {service_name} within 5km (currently {distance:.1f}km away)"
        elif need_level == NeedLevel.MEDIUM:
            return f"Medium priority: Consider adding {service_name} to improve access (currently {distance:.1f}km away)"
        else:
            return f"Low priority: {service_name} access is adequate (currently {distance:.1f}km away)"

    async def analyze_service_gaps(self, request: ServiceAnalysisRequest) -> ServiceAnalysisResponse:
        """Main method to analyze service gaps within AOI"""
        start_time = datetime.now()
        print(f"🔍 Starting service gap analysis for {len(request.service_types)} service types")
        
        # Generate analysis grid
        grid_points = self._generate_grid_points(request.aoi_bounds, request.grid_resolution)
        
        # Fetch service locations for each type
        service_locations = {}
        for service_type in request.service_types:
            locations = await self._fetch_osm_services(service_type, request.aoi_bounds)
            service_locations[service_type] = locations
        
        # Analyze gaps for each service type
        all_service_gaps = {}
        analysis_summary = {}
        
        for service_type in request.service_types:
            service_gaps = []
            locations = service_locations[service_type]
            
            if not locations:
                print(f"⚠️  No {service_type.value} locations found - marking all points as high need")
                # If no services found, all points are high need
                for lat, lng in grid_points:
                    gap = ServiceGap(
                        center_lat=lat,
                        center_lng=lng,
                        service_type=service_type,
                        distance_to_nearest=999.0,  # Very high distance
                        need_level=NeedLevel.HIGH,
                        area_size=request.grid_resolution ** 2,
                        recommendation=f"Critical: No {service_type.value} facilities found in area - immediate establishment needed"
                    )
                    service_gaps.append(gap)
            else:
                # Calculate distances for each grid point
                for lat, lng in grid_points:
                    min_distance = float('inf')
                    
                    # Find nearest service
                    for service_lat, service_lng in locations:
                        distance = self._calculate_distance(lat, lng, service_lat, service_lng)
                        min_distance = min(min_distance, distance)
                    
                    # Determine if this point represents a service gap
                    need_level = self._determine_need_level(min_distance, service_type)
                    
                    # Only include medium and high need areas as "gaps"
                    if need_level in [NeedLevel.MEDIUM, NeedLevel.HIGH]:
                        gap = ServiceGap(
                            center_lat=lat,
                            center_lng=lng,
                            service_type=service_type,
                            distance_to_nearest=min_distance,
                            need_level=need_level,
                            area_size=request.grid_resolution ** 2,
                            recommendation=self._generate_recommendation(service_type, need_level, min_distance)
                        )
                        service_gaps.append(gap)
            
            all_service_gaps[service_type.value] = service_gaps
            
            # Generate summary
            high_count = sum(1 for gap in service_gaps if gap.need_level == NeedLevel.HIGH)
            medium_count = sum(1 for gap in service_gaps if gap.need_level == NeedLevel.MEDIUM)
            low_count = sum(1 for gap in service_gaps if gap.need_level == NeedLevel.LOW)
            avg_distance = sum(gap.distance_to_nearest for gap in service_gaps) / len(service_gaps) if service_gaps else 0
            
            analysis_summary[service_type.value] = ServiceSummary(
                total_gaps=len(service_gaps),
                high_priority=high_count,
                medium_priority=medium_count,
                low_priority=low_count,
                avg_distance=avg_distance
            )
            
            print(f"📊 {service_type.value}: {len(service_gaps)} gaps ({high_count} high, {medium_count} medium)")
        
        total_gaps = sum(len(gaps) for gaps in all_service_gaps.values())
        processing_time = (datetime.now() - start_time).total_seconds()
        
        print(f"✅ Service analysis completed in {processing_time:.2f}s - {total_gaps} total gaps found")
        
        return ServiceAnalysisResponse(
            success=True,
            message=f"Found {total_gaps} service gaps across {len(request.service_types)} service types",
            total_service_gaps=total_gaps,
            analysis_summary=analysis_summary,
            service_gaps=all_service_gaps,
            processing_time=processing_time,
            data_source="OpenStreetMap"
        )

# Global service instance
service_analysis_service = ServiceAnalysisService()