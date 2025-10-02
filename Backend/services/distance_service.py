"""
Distance Calculation Service
Uses Google Maps APIs to calculate real distances to amenities
"""

import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple
import os
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)

class DistanceService:
    def __init__(self):
        self.google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        self.places_base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        self.distance_matrix_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        self.session = None
        self.is_initialized = False
        
        # Cache for nearby places to avoid repeated API calls
        self.places_cache = {}
        self.cache_radius_km = 10  # Cache places within 10km radius
        
    async def initialize(self):
        """Initialize the distance service"""
        try:
            print("📍 Initializing Distance Calculation Service...")
            
            if not self.google_maps_api_key:
                print("⚠️  Google Maps API key not found in environment")
                print("🔧 Set GOOGLE_MAPS_API_KEY in your .env file")
                logger.warning("Google Maps API key not found")
                self.is_initialized = False
                return False
            
            # Create aiohttp session
            self.session = aiohttp.ClientSession()
            
            # Test API key with a simple geocoding request
            test_url = f"https://maps.googleapis.com/maps/api/geocode/json?address=test&key={self.google_maps_api_key}"
            
            async with self.session.get(test_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') != 'REQUEST_DENIED':
                        self.is_initialized = True
                        print("✅ Google Maps API key validated successfully")
                        logger.info("Distance service initialized successfully")
                        return True
                    else:
                        print(f"❌ Google Maps API key invalid: {data.get('error_message', 'Unknown error')}")
                        logger.error(f"Invalid API key: {data.get('error_message')}")
                        return False
                else:
                    print(f"❌ Failed to validate API key: HTTP {response.status}")
                    logger.error(f"Failed to validate API key: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Failed to initialize distance service: {str(e)}")
            logger.error(f"Failed to initialize distance service: {str(e)}")
            self.is_initialized = False
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        Returns distance in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r
    
    async def find_nearby_places(
        self, 
        lat: float, 
        lng: float, 
        place_type: str, 
        radius: int = 5000
    ) -> List[Dict]:
        """
        Find nearby places of a specific type using Google Places API
        
        Args:
            lat, lng: Location coordinates
            place_type: Google Places type (hospital, school, etc.)
            radius: Search radius in meters (max 50000)
            
        Returns:
            List of nearby places with coordinates and details
        """
        if not self.is_initialized:
            logger.warning("Distance service not initialized, using fallback")
            return []
        
        try:
            # Check cache first
            cache_key = f"{lat:.4f},{lng:.4f},{place_type},{radius}"
            if cache_key in self.places_cache:
                return self.places_cache[cache_key]
            
            params = {
                'location': f"{lat},{lng}",
                'radius': min(radius, 50000),  # Google's max is 50km
                'type': place_type,
                'key': self.google_maps_api_key
            }
            
            async with self.session.get(self.places_base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('status') == 'OK':
                        places = []
                        for result in data.get('results', [])[:10]:  # Limit to 10 closest
                            place = {
                                'name': result.get('name', 'Unknown'),
                                'lat': result['geometry']['location']['lat'],
                                'lng': result['geometry']['location']['lng'],
                                'rating': result.get('rating', 0),
                                'place_id': result.get('place_id'),
                                'types': result.get('types', [])
                            }
                            
                            # Calculate straight-line distance
                            place['distance_km'] = self.haversine_distance(lat, lng, place['lat'], place['lng'])
                            places.append(place)
                        
                        # Sort by distance
                        places.sort(key=lambda x: x['distance_km'])
                        
                        # Cache results
                        self.places_cache[cache_key] = places
                        
                        return places
                    else:
                        logger.warning(f"Places API error: {data.get('status')} - {data.get('error_message', '')}")
                        return []
                else:
                    logger.error(f"Places API HTTP error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error finding nearby places: {str(e)}")
            return []
    
    async def calculate_distance_matrix(
        self, 
        origins: List[Tuple[float, float]], 
        destinations: List[Tuple[float, float]]
    ) -> List[List[Dict]]:
        """
        Calculate travel distances using Google Distance Matrix API
        
        Args:
            origins: List of (lat, lng) tuples for starting points
            destinations: List of (lat, lng) tuples for destinations
            
        Returns:
            Matrix of distance/duration data
        """
        if not self.is_initialized:
            logger.warning("Distance service not initialized, using haversine distances")
            return self._calculate_haversine_matrix(origins, destinations)
        
        try:
            # Format coordinates for API
            origin_str = "|".join([f"{lat},{lng}" for lat, lng in origins])
            dest_str = "|".join([f"{lat},{lng}" for lat, lng in destinations])
            
            params = {
                'origins': origin_str,
                'destinations': dest_str,
                'mode': 'driving',
                'units': 'metric',
                'key': self.google_maps_api_key
            }
            
            async with self.session.get(self.distance_matrix_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('status') == 'OK':
                        matrix = []
                        for i, row in enumerate(data.get('rows', [])):
                            matrix_row = []
                            for j, element in enumerate(row.get('elements', [])):
                                if element.get('status') == 'OK':
                                    distance = element.get('distance', {})
                                    duration = element.get('duration', {})
                                    
                                    result = {
                                        'distance_km': distance.get('value', 0) / 1000,  # Convert m to km
                                        'distance_text': distance.get('text', ''),
                                        'duration_seconds': duration.get('value', 0),
                                        'duration_text': duration.get('text', ''),
                                        'status': 'OK'
                                    }
                                else:
                                    # Fallback to haversine distance
                                    fallback_dist = self.haversine_distance(
                                        origins[i][0], origins[i][1],
                                        destinations[j][0], destinations[j][1]
                                    )
                                    result = {
                                        'distance_km': fallback_dist,
                                        'distance_text': f"{fallback_dist:.1f} km",
                                        'duration_seconds': int(fallback_dist * 120),  # Estimate: 2 min/km
                                        'duration_text': f"~{int(fallback_dist * 2)} min",
                                        'status': 'FALLBACK'
                                    }
                                
                                matrix_row.append(result)
                            matrix.append(matrix_row)
                        
                        return matrix
                    else:
                        logger.warning(f"Distance Matrix API error: {data.get('status')}")
                        return self._calculate_haversine_matrix(origins, destinations)
                else:
                    logger.error(f"Distance Matrix API HTTP error: {response.status}")
                    return self._calculate_haversine_matrix(origins, destinations)
                    
        except Exception as e:
            logger.error(f"Error calculating distance matrix: {str(e)}")
            return self._calculate_haversine_matrix(origins, destinations)
    
    def _calculate_haversine_matrix(
        self, 
        origins: List[Tuple[float, float]], 
        destinations: List[Tuple[float, float]]
    ) -> List[List[Dict]]:
        """Fallback distance calculation using haversine formula"""
        matrix = []
        for i, (orig_lat, orig_lng) in enumerate(origins):
            row = []
            for j, (dest_lat, dest_lng) in enumerate(destinations):
                distance_km = self.haversine_distance(orig_lat, orig_lng, dest_lat, dest_lng)
                result = {
                    'distance_km': distance_km,
                    'distance_text': f"{distance_km:.1f} km",
                    'duration_seconds': int(distance_km * 120),  # Estimate: 2 min/km
                    'duration_text': f"~{int(distance_km * 2)} min",
                    'status': 'HAVERSINE'
                }
                row.append(result)
            matrix.append(row)
        return matrix
    
    async def calculate_amenity_distances(
        self, 
        lat: float, 
        lng: float,
        search_radius: int = 10000
    ) -> Dict[str, float]:
        """
        Calculate distances to all amenity types for a location
        
        Args:
            lat, lng: Location coordinates
            search_radius: Search radius in meters
            
        Returns:
            Dict with amenity distances in kilometers
        """
        amenity_types = {
            'hospital': 'hospital',
            'school': 'school',
            'bus': 'bus_station',
            'railway': 'train_station', 
            'mall': 'shopping_mall',
            'airport': 'airport'
        }
        
        distances = {}
        
        # Use concurrent requests for better performance
        tasks = []
        for amenity_key, google_type in amenity_types.items():
            task = self.find_nearby_places(lat, lng, google_type, search_radius)
            tasks.append((amenity_key, task))
        
        # Execute all searches concurrently
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        for i, (amenity_key, _) in enumerate(tasks):
            try:
                places = results[i] if not isinstance(results[i], Exception) else []
                
                if places:
                    # Get distance to closest place
                    closest_distance = min(place['distance_km'] for place in places)
                    distances[amenity_key] = round(closest_distance, 2)
                else:
                    # Default distances if no places found
                    default_distances = {
                        'hospital': 10.0,
                        'school': 8.0,
                        'bus': 5.0,
                        'railway': 15.0,
                        'mall': 10.0,
                        'airport': 30.0
                    }
                    distances[amenity_key] = default_distances.get(amenity_key, 10.0)
                    
            except Exception as e:
                logger.error(f"Error processing {amenity_key} distances: {str(e)}")
                distances[amenity_key] = 10.0  # Default fallback
        
        return distances
    
    def get_service_status(self) -> Dict[str, any]:
        """Get current service status"""
        return {
            "initialized": self.is_initialized,
            "api_key_configured": bool(self.google_maps_api_key),
            "session_active": self.session is not None and not self.session.closed,
            "cache_size": len(self.places_cache),
            "supported_amenities": ['hospital', 'school', 'bus', 'railway', 'mall', 'airport']
        }

# Global instance
distance_service = DistanceService()
