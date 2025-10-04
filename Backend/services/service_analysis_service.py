import asyncio
import aiohttp
import math
import json
from typing import Dict, List, Tuple, Optional, Any
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
        
        # Service distance thresholds (in kilometers) - Based on urban planning standards
        self.service_thresholds = {
            ServiceType.PARKS: {"good": 0.8, "fair": 2.0, "poor": 5.0},
            ServiceType.FOOD: {"good": 1.5, "fair": 5.0, "poor": 10.0},
            ServiceType.HEALTHCARE: {"good": 3.0, "fair": 10.0, "poor": 20.0},
            ServiceType.TRANSPORT: {"good": 0.5, "fair": 1.5, "poor": 3.0}
        }
        
        # Google Places API search types for each service
        self.google_places_types = {
            ServiceType.PARKS: ["park", "amusement_park", "zoo", "campground"],
            ServiceType.FOOD: ["supermarket", "grocery_or_supermarket", "food", "meal_takeaway", "restaurant", "bakery"],
            ServiceType.HEALTHCARE: ["hospital", "pharmacy", "doctor", "dentist", "physiotherapist", "veterinary_care"],
            ServiceType.TRANSPORT: ["bus_station", "subway_station", "train_station", "transit_station", "airport"]
        }
        
        # OpenStreetMap Overpass API query templates
        self.overpass_queries = {
            ServiceType.PARKS: '''
                [out:json][timeout:25];
                (
                  way["leisure"="park"]({{bbox}});
                  way["leisure"="playground"]({{bbox}});
                  way["leisure"="recreation_ground"]({{bbox}});
                  way["leisure"="garden"]({{bbox}});
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
                  node["shop"="bakery"]({{bbox}});
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
                  node["amenity"="pharmacy"]({{bbox}});
                  node["amenity"="dentist"]({{bbox}});
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
                  node["aeroway"="aerodrome"]({{bbox}});
                  node["aeroway"="airport"]({{bbox}});
                  way["public_transport"="station"]({{bbox}});
                  way["aeroway"="aerodrome"]({{bbox}});
                );
                out center;
            '''
        }

    async def initialize(self):
        """Initialize the service analysis system"""
        print("🔍 Initializing Service Analysis Service...")
        print(f"🗺️  Google Maps API: {'✅ Available' if self.google_maps_api_key else '❌ Missing (using OSM only)'}")
        
        if self.google_maps_api_key:
            try:
                await self._test_google_places_api()
                print("✅ Google Places API connection verified")
            except Exception as e:
                print(f"⚠️  Google Places API test failed: {str(e)}")
                print("🔄 Will fallback to OpenStreetMap data")
        
        self.is_initialized = True
        return True
            
    async def _test_google_places_api(self):
        """Test Google Places API connectivity"""
        test_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': '23.0225,72.5714',
            'radius': 1000,
            'type': 'park',
            'key': self.google_maps_api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'OK':
                        print(f"🎯 Google Places API test successful - found {len(data.get('results', []))} parks near Ahmedabad")
                        return True
                    else:
                        raise Exception(f"API returned status: {data.get('status')}")
                else:
                    raise Exception(f"HTTP {response.status}")

    async def _fetch_google_places(self, service_type: ServiceType, center_lat: float, center_lng: float, radius_km: float = 25) -> Tuple[List[Tuple[float, float, str]], Dict[str, Any]]:
        """Fetch service locations from Google Places API and return search details"""
        if not self.google_maps_api_key:
            print(f"⚠️  No Google API key - skipping Google Places for {service_type.value}")
            return [], {"status": "no_api_key", "search_results": []}
        
        places = []
        search_results = []
        search_types = self.google_places_types[service_type]
        
        for place_type in search_types:
            try:
                url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                params = {
                    'location': f'{center_lat},{center_lng}',
                    'radius': int(radius_km * 1000),
                    'type': place_type,
                    'key': self.google_maps_api_key
                }
                
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(url, params=params, timeout=15) as response:
                            if response.status == 200:
                                data = await response.json()
                                status = data.get('status', 'UNKNOWN')
                                results_count = len(data.get('results', []))
                                
                                search_results.append({
                                    "place_type": place_type,
                                    "status": status,
                                    "count": results_count
                                })
                                
                                if status == 'OK':
                                    for place in data.get('results', []):
                                        location = place.get('geometry', {}).get('location', {})
                                        name = place.get('name', 'Unknown')
                                        if location.get('lat') and location.get('lng'):
                                            places.append((location['lat'], location['lng'], name))
                                    print(f"🗺️  Found {results_count} {place_type} locations via Google Places")
                                else:
                                    print(f"⚠️  Google Places API status: {status} for {place_type}")
                            else:
                                print(f"❌ Google Places API error: {response.status} for {place_type}")
                                search_results.append({
                                    "place_type": place_type,
                                    "status": f"HTTP_{response.status}",
                                    "count": 0
                                })
                    except Exception as e:
                        print(f"❌ Error fetching {place_type} from Google Places: {str(e)}")
                        search_results.append({
                            "place_type": place_type,
                            "status": "ERROR",
                            "count": 0
                        })
                        continue
            except Exception as e:
                print(f"❌ Error in outer block for {place_type}: {str(e)}")
                search_results.append({
                    "place_type": place_type,
                    "status": "ERROR",
                    "count": 0
                })
                continue
        
        # Remove duplicates
        unique_places = []
        for lat, lng, name in places:
            is_duplicate = False
            for existing_lat, existing_lng, _ in unique_places:
                if self._calculate_distance(lat, lng, existing_lat, existing_lng) < 0.1:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_places.append((lat, lng, name))
        
        duplicates_removed = len(places) - len(unique_places)
        print(f"🎯 Google Places: {len(unique_places)} unique {service_type.value} locations (removed {duplicates_removed} duplicates)")
        
        search_details = {
            "search_results": search_results,
            "total_found": len(places),
            "duplicates_removed": duplicates_removed,
            "final_count": len(unique_places)
        }
        
        return unique_places, search_details

    async def _calculate_real_distance_google(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> Optional[float]:
        """Calculate real travel distance using Google Distance Matrix API"""
        if not self.google_maps_api_key:
            return None
            
        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                'origins': f'{origin_lat},{origin_lng}',
                'destinations': f'{dest_lat},{dest_lng}',
                'mode': 'driving',
                'units': 'metric',
                'key': self.google_maps_api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'OK':
                            rows = data.get('rows', [])
                            if rows and rows[0].get('elements'):
                                element = rows[0]['elements'][0]
                                if element.get('status') == 'OK':
                                    distance_m = element.get('distance', {}).get('value', 0)
                                    return distance_m / 1000.0
        except Exception as e:
            print(f"⚠️  Google Distance Matrix error: {str(e)}")
        return None

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Haversine distance between two points in kilometers"""
        R = 6371
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
        lat_step = resolution_km / 111.0
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
        print(f"🔍 Starting DYNAMIC service gap analysis for {len(request.service_types)} service types")
        
        grid_points = self._generate_grid_points(request.aoi_bounds, request.grid_resolution)
        
        center_lat = (request.aoi_bounds.north + request.aoi_bounds.south) / 2
        center_lng = (request.aoi_bounds.east + request.aoi_bounds.west) / 2
        
        diagonal_km = self._calculate_distance(
            request.aoi_bounds.south, request.aoi_bounds.west,
            request.aoi_bounds.north, request.aoi_bounds.east
        )
        search_radius = max(diagonal_km * 1.5, 10.0)
        
        print(f"📍 AOI Center: ({center_lat:.4f}, {center_lng:.4f})")
        print(f"🔍 Search radius: {search_radius:.1f}km")
        
        service_locations = {}
        all_search_details = {}
        
        for service_type in request.service_types:
            print(f"\n🔍 Searching for {service_type.value} services...")
            
            google_locations, search_details = await self._fetch_google_places(service_type, center_lat, center_lng, search_radius)
            
            if google_locations:
                service_locations[service_type] = {
                    'locations': [(lat, lng) for lat, lng, name in google_locations],
                    'names': {f"{lat:.6f},{lng:.6f}": name for lat, lng, name in google_locations},
                    'source': 'google'
                }
                all_search_details[service_type.value] = search_details
                print(f"✅ Using {len(google_locations)} Google Places {service_type.value} locations")
            else:
                print(f"🔄 Falling back to OpenStreetMap for {service_type.value}")
                osm_locations = await self._fetch_osm_services(service_type, request.aoi_bounds)
                service_locations[service_type] = {
                    'locations': osm_locations,
                    'names': {},
                    'source': 'osm'
                }
                all_search_details[service_type.value] = {
                    "search_results": [{"place_type": "osm_fallback", "status": "OSM_USED", "count": len(osm_locations)}],
                    "total_found": len(osm_locations),
                    "duplicates_removed": 0,
                    "final_count": len(osm_locations)
                }
        
        all_service_gaps = {}
        analysis_summary = {}
        
        for service_type in request.service_types:
            service_gaps = []
            service_data = service_locations[service_type]
            locations = service_data['locations']
            names_map = service_data['names']
            
            if not locations:
                print(f"⚠️  No {service_type.value} locations found - marking all points as high need")
                for lat, lng in grid_points:
                    gap = ServiceGap(
                        center_lat=lat,
                        center_lng=lng,
                        service_type=service_type,
                        distance_to_nearest=999.0,
                        need_level=NeedLevel.HIGH,
                        area_size=request.grid_resolution ** 2,
                        recommendation=f"Critical: No {service_type.value} facilities found in area - immediate establishment needed"
                    )
                    service_gaps.append(gap)
            else:
                print(f"📊 Analyzing {len(grid_points)} grid points against {len(locations)} {service_type.value} locations")
                
                for lat, lng in grid_points:
                    min_distance = float('inf')
                    nearest_service_name = "Unknown"
                    nearest_service_coords = None
                    
                    for service_lat, service_lng in locations:
                        distance = self._calculate_distance(lat, lng, service_lat, service_lng)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_service_coords = (service_lat, service_lng)
                    
                    if nearest_service_coords and names_map:
                        coord_key = f"{nearest_service_coords[0]:.6f},{nearest_service_coords[1]:.6f}"
                        nearest_service_name = names_map.get(coord_key, "Unknown")
                    
                    need_level = self._determine_need_level(min_distance, service_type)
                    
                    if need_level in [NeedLevel.MEDIUM, NeedLevel.HIGH]:
                        recommendation = self._generate_recommendation(service_type, need_level, min_distance)
                        if nearest_service_name != "Unknown":
                            recommendation += f" (Nearest: {nearest_service_name})"
                        
                        gap = ServiceGap(
                            center_lat=lat,
                            center_lng=lng,
                            service_type=service_type,
                            distance_to_nearest=min_distance,
                            need_level=need_level,
                            area_size=request.grid_resolution ** 2,
                            recommendation=recommendation
                        )
                        service_gaps.append(gap)
            
            all_service_gaps[service_type.value] = service_gaps
            
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
        
        data_source = "Google Places API" if self.google_maps_api_key else "OpenStreetMap"
        
        response = ServiceAnalysisResponse(
            success=True,
            message=f"Found {total_gaps} service gaps using {data_source}",
            total_service_gaps=total_gaps,
            analysis_summary=analysis_summary,
            service_gaps=all_service_gaps,
            processing_time=processing_time,
            data_source=data_source,
            search_details=all_search_details
        )
        
        print(f"🔍 Response verification: success={response.success}, gaps={response.total_service_gaps}")
        print(f"📋 Service types in response: {list(response.service_gaps.keys())}")
        
        return response

# Global service instance
service_analysis_service = ServiceAnalysisService()