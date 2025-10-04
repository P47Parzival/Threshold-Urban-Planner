import asyncio
import aiohttp
import math
import json
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
        
        # Service distance thresholds (in kilometers) - Based on urban planning standards
        self.service_thresholds = {
            ServiceType.PARKS: {"good": 0.8, "fair": 2.0, "poor": 5.0},      # Parks should be within walking distance
            ServiceType.FOOD: {"good": 1.5, "fair": 5.0, "poor": 10.0},      # Grocery stores for daily needs
            ServiceType.HEALTHCARE: {"good": 3.0, "fair": 10.0, "poor": 20.0}, # Medical facilities
            ServiceType.TRANSPORT: {"good": 0.5, "fair": 1.5, "poor": 3.0}    # Public transport access
        }
        
        # Google Places API search types for each service
        self.google_places_types = {
            ServiceType.PARKS: ["park", "amusement_park", "zoo"],
            ServiceType.FOOD: ["supermarket", "grocery_or_supermarket", "food", "meal_takeaway", "restaurant"],
            ServiceType.HEALTHCARE: ["hospital", "pharmacy", "doctor", "dentist", "physiotherapist"],
            ServiceType.TRANSPORT: ["bus_station", "subway_station", "train_station", "transit_station"]
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
        
        # Test Google Places API if available
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
        test_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': '23.0225,72.5714',  # Ahmedabad coordinates
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

    async def _fetch_google_places(self, service_type: ServiceType, center_lat: float, center_lng: float, radius_km: float = 25) -> List[Tuple[float, float, str]]:
        """Fetch service locations from Google Places API"""
        if not self.google_maps_api_key:
            print(f"⚠️  No Google API key - skipping Google Places for {service_type.value}")
            return []
        
        places = []
        search_types = self.google_places_types[service_type]
        
        for place_type in search_types:
            try:
                url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                params = {
                    'location': f'{center_lat},{center_lng}',
                    'radius': int(radius_km * 1000),  # Convert km to meters
                    'type': place_type,
                    'key': self.google_maps_api_key
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=15) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == 'OK':
                                for place in data.get('results', []):
                                    location = place.get('geometry', {}).get('location', {})
                                    name = place.get('name', 'Unknown')
                                    if location.get('lat') and location.get('lng'):
                                        places.append((location['lat'], location['lng'], name))
                                
                                print(f"🗺️  Found {len(data.get('results', []))} {place_type} locations via Google Places")
                            else:
                                print(f"⚠️  Google Places API status: {data.get('status')} for {place_type}")
                        else:
                            print(f"❌ Google Places API error: {response.status} for {place_type}")
                            
            except Exception as e:
                print(f"❌ Error fetching {place_type} from Google Places: {str(e)}")
                continue
        
        # Remove duplicates (places within 100m of each other)
        unique_places = []
        for lat, lng, name in places:
            is_duplicate = False
            for existing_lat, existing_lng, _ in unique_places:
                if self._calculate_distance(lat, lng, existing_lat, existing_lng) < 0.1:  # 100m threshold
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_places.append((lat, lng, name))
        
        print(f"🎯 Google Places: {len(unique_places)} unique {service_type.value} locations (removed {len(places) - len(unique_places)} duplicates)")
        return unique_places

    async def _calculate_real_distance_google(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> Optional[float]:
        """Calculate real travel distance using Google Distance Matrix API"""
        if not self.google_maps_api_key:
            return None
            
        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                'origins': f'{origin_lat},{origin_lng}',
                'destinations': f'{dest_lat},{dest_lng}',
                'mode': 'driving',  # Can be 'walking', 'driving', 'transit'
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
                                    return distance_m / 1000.0  # Convert to km
                        
        except Exception as e:
            print(f"⚠️  Google Distance Matrix error: {str(e)}")
            
        return None

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
        print(f"🔍 Starting DYNAMIC service gap analysis for {len(request.service_types)} service types")
        
        # Generate analysis grid
        grid_points = self._generate_grid_points(request.aoi_bounds, request.grid_resolution)
        
        # Calculate AOI center for Google Places search
        center_lat = (request.aoi_bounds.north + request.aoi_bounds.south) / 2
        center_lng = (request.aoi_bounds.east + request.aoi_bounds.west) / 2
        
        # Calculate search radius (diagonal of AOI + buffer)
        lat_span = request.aoi_bounds.north - request.aoi_bounds.south
        lng_span = request.aoi_bounds.east - request.aoi_bounds.west
        diagonal_km = self._calculate_distance(
            request.aoi_bounds.south, request.aoi_bounds.west,
            request.aoi_bounds.north, request.aoi_bounds.east
        )
        search_radius = max(diagonal_km * 1.5, 10.0)  # At least 10km radius
        
        print(f"📍 AOI Center: ({center_lat:.4f}, {center_lng:.4f})")
        print(f"🔍 Search radius: {search_radius:.1f}km")
        
        # Fetch service locations for each type (Google Places first, then OSM fallback)
        service_locations = {}
        for service_type in request.service_types:
            print(f"\n🔍 Searching for {service_type.value} services...")
            
            # Try Google Places API first
            google_locations = await self._fetch_google_places(service_type, center_lat, center_lng, search_radius)
            
            if google_locations:
                # Store both location data and names for later use
                service_locations[service_type] = {
                    'locations': [(lat, lng) for lat, lng, name in google_locations],
                    'names': {f"{lat:.6f},{lng:.6f}": name for lat, lng, name in google_locations},
                    'source': 'google'
                }
                print(f"✅ Using {len(google_locations)} Google Places {service_type.value} locations")
            else:
                # Fallback to OpenStreetMap
                print(f"🔄 Falling back to OpenStreetMap for {service_type.value}")
                osm_locations = await self._fetch_osm_services(service_type, request.aoi_bounds)
                service_locations[service_type] = {
                    'locations': osm_locations,
                    'names': {},
                    'source': 'osm'
                }
        
        # Analyze gaps for each service type
        all_service_gaps = {}
        analysis_summary = {}
        
        for service_type in request.service_types:
            service_gaps = []
            service_data = service_locations[service_type]
            locations = service_data['locations']
            names_map = service_data['names']
            data_source = service_data['source']
            
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
                print(f"📊 Analyzing {len(grid_points)} grid points against {len(locations)} {service_type.value} locations")
                
                # Calculate distances for each grid point
                for lat, lng in grid_points:
                    min_distance = float('inf')
                    nearest_service_name = "Unknown"
                    nearest_service_coords = None
                    
                    # Find nearest service (using Haversine only for now to avoid timeout issues)
                    for service_lat, service_lng in locations:
                        # Use Haversine distance for now to avoid API timeout issues
                        distance = self._calculate_distance(lat, lng, service_lat, service_lng)
                        
                        if distance < min_distance:
                            min_distance = distance
                            nearest_service_coords = (service_lat, service_lng)
                    
                    # Get service name if available
                    if nearest_service_coords and names_map:
                        coord_key = f"{nearest_service_coords[0]:.6f},{nearest_service_coords[1]:.6f}"
                        nearest_service_name = names_map.get(coord_key, "Unknown")
                    
                    # Determine if this point represents a service gap
                    need_level = self._determine_need_level(min_distance, service_type)
                    
                    # Only include medium and high need areas as "gaps"
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
        
        # Determine data source used
        data_source = "Google Places API" if self.google_maps_api_key else "OpenStreetMap"
        
        response = ServiceAnalysisResponse(
            success=True,
            message=f"Found {total_gaps} service gaps using {data_source}",
            total_service_gaps=total_gaps,
            analysis_summary=analysis_summary,
            service_gaps=all_service_gaps,
            processing_time=processing_time,
            data_source=data_source
        )
        
        print(f"🔍 Response verification: success={response.success}, gaps={response.total_service_gaps}")
        print(f"📋 Service types in response: {list(response.service_gaps.keys())}")
        
        return response

# Global service instance
service_analysis_service = ServiceAnalysisService()