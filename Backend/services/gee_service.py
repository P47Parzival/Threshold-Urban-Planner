"""
Google Earth Engine Authentication and Setup Service

This service handles:
1. Google Earth Engine authentication with service account
2. Initialization and configuration
3. Error handling for GEE connectivity
"""

import ee
import os
import json
import logging
from typing import Optional
from datetime import datetime

class GoogleEarthEngineService:
    """Service for managing Google Earth Engine authentication and operations."""
    
    def __init__(self):
        self.is_initialized = False
        self.service_account_key_path = None
        self.service_account_email = None
        
    async def initialize(self) -> bool:
        """
        Initialize Google Earth Engine with service account authentication.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Get service account configuration from environment
            service_account_key = os.getenv('GEE_SERVICE_ACCOUNT_KEY')
            service_account_email = os.getenv('GEE_SERVICE_ACCOUNT_EMAIL')
            service_account_private_key = os.getenv('GEE_PRIVATE_KEY')
            
            if not service_account_key and not (service_account_email and service_account_private_key):
                logging.error("Google Earth Engine service account credentials not found in environment")
                return False
            
            # Method 1: Using service account key file
            if service_account_key:
                try:
                    # Parse the key if it's a JSON string
                    if service_account_key.startswith('{'):
                        key_data = json.loads(service_account_key)
                        # Create temporary key file
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                            json.dump(key_data, f)
                            self.service_account_key_path = f.name
                        
                        credentials = ee.ServiceAccountCredentials(
                            key_data['client_email'], 
                            self.service_account_key_path
                        )
                    else:
                        # Assume it's a file path
                        self.service_account_key_path = service_account_key
                        with open(service_account_key, 'r') as f:
                            key_data = json.load(f)
                        
                        credentials = ee.ServiceAccountCredentials(
                            key_data['client_email'], 
                            service_account_key
                        )
                    
                    ee.Initialize(credentials)
                    self.service_account_email = key_data['client_email']
                    
                except Exception as e:
                    logging.error(f"Failed to initialize GEE with service account key: {str(e)}")
                    return False
            
            # Method 2: Using individual credentials
            elif service_account_email and service_account_private_key:
                try:
                    # Create credentials from individual components
                    key_data = {
                        "type": "service_account",
                        "client_email": service_account_email,
                        "private_key": service_account_private_key.replace('\\n', '\n'),
                        "token_uri": "https://oauth2.googleapis.com/token"
                    }
                    
                    # Create temporary key file
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(key_data, f)
                        self.service_account_key_path = f.name
                    
                    credentials = ee.ServiceAccountCredentials(
                        service_account_email, 
                        self.service_account_key_path
                    )
                    
                    ee.Initialize(credentials)
                    self.service_account_email = service_account_email
                    
                except Exception as e:
                    logging.error(f"Failed to initialize GEE with individual credentials: {str(e)}")
                    return False
            
            # Test the connection with correct ESA WorldCover ImageCollection format
            test_collection = ee.ImageCollection('ESA/WorldCover/v200').first()
            test_image = test_collection.select("Map")
            info = test_image.getInfo()
            
            self.is_initialized = True
            logging.info("="*60)
            logging.info("🚀 GOOGLE EARTH ENGINE SUCCESSFULLY INITIALIZED")
            logging.info(f"📧 Service Account: {self.service_account_email}")
            logging.info(f"📊 ESA WorldCover Dataset: ACCESSIBLE")
            logging.info(f"🌍 Real Satellite Data: ENABLED")
            logging.info("="*60)
            
            return True
            
        except Exception as e:
            logging.error("="*60)
            logging.error("❌ GOOGLE EARTH ENGINE INITIALIZATION FAILED")
            logging.error(f"🚫 Error: {str(e)}")
            logging.error("⚠️  Will use SYNTHETIC FALLBACK data")
            logging.error("="*60)
            self.is_initialized = False
            return False
    
    def is_authenticated(self) -> bool:
        """Check if Google Earth Engine is properly authenticated."""
        if not self.is_initialized:
            return False
        
        try:
            # Try a simple operation to verify authentication
            ee.Number(1).getInfo()
            return True
        except Exception as e:
            logging.warning(f"GEE authentication check failed: {str(e)}")
            return False
    
    def get_status(self) -> dict:
        """Get current status of Google Earth Engine service."""
        return {
            "initialized": self.is_initialized,
            "authenticated": self.is_authenticated(),
            "service_account": self.service_account_email,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def cleanup(self):
        """Clean up temporary files and resources."""
        if self.service_account_key_path and os.path.exists(self.service_account_key_path):
            try:
                os.unlink(self.service_account_key_path)
                logging.info("Cleaned up temporary service account key file")
            except Exception as e:
                logging.warning(f"Failed to cleanup temporary key file: {str(e)}")

# Global service instance
gee_service = GoogleEarthEngineService()
