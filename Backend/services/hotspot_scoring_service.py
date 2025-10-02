"""
Hotspot Scoring Service
Calculates hotspot scores for vacant land using trained ML model
"""

import logging
import pickle
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class HotspotScoringService:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_columns = [
            'AQI', 'PopulationDensity', 'DistHospital', 'DistSchool', 
            'DistAirport', 'DistBus', 'DistRailway', 'DistMall'
        ]
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize the ML model and scaler"""
        try:
            print("🤖 Initializing Hotspot Scoring Service...")
            
            # Try to load model and scaler from multiple possible locations
            possible_paths = [
                # Current directory (Backend/)
                (Path("hotspot_model.pkl"), Path("scaler.pkl")),
                # Model subdirectory in Backend
                (Path("Model/hotspot_model.pkl"), Path("Model/scaler.pkl")),
                # Parent Model directory
                (Path("../Model/hotspot_model.pkl"), Path("../Model/scaler.pkl")),
                # Try with different scaler name
                (Path("hotspot_model.pkl"), Path("scaler (1).pkl")),
                (Path("Model/hotspot_model.pkl"), Path("Model/scaler (1).pkl")),
                (Path("../Model/hotspot_model.pkl"), Path("../Model/scaler (1).pkl"))
            ]
            
            model_path = None
            scaler_path = None
            
            for m_path, s_path in possible_paths:
                if m_path.exists() and s_path.exists():
                    model_path = m_path
                    scaler_path = s_path
                    print(f"✅ Found model files at: {model_path} and {scaler_path}")
                    break
            
            if model_path and scaler_path:
                print("📦 Loading trained model and scaler...")
                
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                
                self.is_initialized = True
                print("✅ ML Model loaded successfully")
                print(f"📊 Features: {self.feature_columns}")
                print(f"🎯 Model Type: {type(self.model).__name__}")
                logger.info("Hotspot scoring service initialized with trained model")
                
            else:
                print("⚠️  ML Model files not found - using fallback scoring")
                print(f"🔍 Searched in these locations:")
                for m_path, s_path in possible_paths:
                    print(f"   • {m_path} and {s_path}")
                print("🔧 Train your model first and place files in Backend/ directory")
                self.is_initialized = False
                logger.warning("ML model not found, using fallback scoring")
                
        except Exception as e:
            print(f"❌ Failed to initialize ML model: {str(e)}")
            logger.error(f"Failed to initialize hotspot scoring service: {str(e)}")
            self.is_initialized = False
    
    def is_model_ready(self) -> bool:
        """Check if ML model is ready for predictions"""
        return self.is_initialized and self.model is not None and self.scaler is not None
    
    async def calculate_hotspot_score(
        self, 
        aqi: float,
        population_density: float,
        distances: Dict[str, float]
    ) -> Dict[str, any]:
        """
        Calculate hotspot score for a location
        
        Args:
            aqi: Air Quality Index value
            population_density: People per sq km
            distances: Dict with keys: hospital, school, airport, bus, railway, mall
            
        Returns:
            Dict with score, confidence, method, and breakdown
        """
        try:
            if self.is_model_ready():
                return await self._calculate_ml_score(aqi, population_density, distances)
            else:
                return await self._calculate_fallback_score(aqi, population_density, distances)
                
        except Exception as e:
            logger.error(f"Error calculating hotspot score: {str(e)}")
            return {
                "score": 0.5,
                "confidence": 0.0,
                "method": "error_fallback",
                "breakdown": {},
                "error": str(e)
            }
    
    async def _calculate_ml_score(
        self, 
        aqi: float, 
        population_density: float, 
        distances: Dict[str, float]
    ) -> Dict[str, any]:
        """Calculate score using trained ML model"""
        try:
            # Prepare feature vector
            features = np.array([[
                aqi,
                population_density,
                distances.get('hospital', 10.0),
                distances.get('school', 8.0),
                distances.get('airport', 30.0),
                distances.get('bus', 5.0),
                distances.get('railway', 15.0),
                distances.get('mall', 10.0)
            ]])
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Predict
            score = self.model.predict(features_scaled)[0]
            
            # Get confidence (if model supports it)
            confidence = 0.9  # Default high confidence for ML predictions
            if hasattr(self.model, 'predict_proba'):
                try:
                    # For classification models
                    proba = self.model.predict_proba(features_scaled)[0]
                    confidence = np.max(proba)
                except:
                    pass
            elif hasattr(self.model, 'score'):
                try:
                    # For regression models
                    confidence = 0.85  # High confidence for regression
                except:
                    pass
            
            # Create breakdown for transparency
            breakdown = self._create_score_breakdown(aqi, population_density, distances)
            
            return {
                "score": float(np.clip(score, 0.0, 1.0)),
                "confidence": float(confidence),
                "method": "ml_model",
                "breakdown": breakdown,
                "model_type": str(type(self.model).__name__)
            }
            
        except Exception as e:
            logger.error(f"ML scoring failed: {str(e)}")
            return await self._calculate_fallback_score(aqi, population_density, distances)
    
    async def _calculate_fallback_score(
        self, 
        aqi: float, 
        population_density: float, 
        distances: Dict[str, float]
    ) -> Dict[str, any]:
        """Calculate score using rule-based fallback method"""
        try:
            # Same logic as enhanced dataset generator
            
            # 1. AQI Score (lower is better, with thresholds)
            if aqi <= 50:
                aqi_score = 1.0
            elif aqi <= 100:
                aqi_score = 0.8
            elif aqi <= 150:
                aqi_score = 0.5
            elif aqi <= 200:
                aqi_score = 0.3
            else:
                aqi_score = 0.1
            
            # 2. Population Density Score (sweet spot around 8000-15000)
            if population_density < 1000:
                pop_score = 0.2  # Too rural
            elif population_density < 5000:
                pop_score = 0.6
            elif population_density < 15000:
                pop_score = 1.0  # Optimal range
            elif population_density < 25000:
                pop_score = 0.8
            else:
                pop_score = 0.4  # Too crowded
            
            # 3. Distance Scores
            def distance_score(dist, optimal, max_acceptable):
                if dist <= optimal:
                    return 1.0
                elif dist <= max_acceptable:
                    decay = (dist - optimal) / (max_acceptable - optimal)
                    return max(0, 1 - (decay ** 2))
                else:
                    return 0.0
            
            hosp_score = distance_score(distances.get('hospital', 10), 2.0, 10.0)
            school_score = distance_score(distances.get('school', 8), 1.0, 8.0)
            bus_score = distance_score(distances.get('bus', 5), 0.5, 3.0)
            rail_score = distance_score(distances.get('railway', 15), 2.0, 15.0)
            mall_score = distance_score(distances.get('mall', 10), 1.5, 10.0)
            airport_score = distance_score(distances.get('airport', 30), 15.0, 45.0)
            
            # 4. Weighted Final Score
            final_score = (
                (aqi_score * 0.25) +         # Environmental quality
                (pop_score * 0.20) +         # Population density
                (hosp_score * 0.15) +        # Healthcare access
                (school_score * 0.15) +      # Education access
                (bus_score * 0.10) +         # Public transport
                (rail_score * 0.05) +        # Regional connectivity
                (mall_score * 0.08) +        # Commercial access
                (airport_score * 0.02)       # International connectivity
            )
            
            breakdown = {
                "aqi_score": round(aqi_score, 3),
                "population_score": round(pop_score, 3),
                "hospital_score": round(hosp_score, 3),
                "school_score": round(school_score, 3),
                "bus_score": round(bus_score, 3),
                "railway_score": round(rail_score, 3),
                "mall_score": round(mall_score, 3),
                "airport_score": round(airport_score, 3)
            }
            
            return {
                "score": round(max(0.0, min(1.0, final_score)), 4),
                "confidence": 0.7,  # Medium confidence for rule-based
                "method": "rule_based_fallback",
                "breakdown": breakdown
            }
            
        except Exception as e:
            logger.error(f"Fallback scoring failed: {str(e)}")
            return {
                "score": 0.5,
                "confidence": 0.0,
                "method": "error",
                "breakdown": {},
                "error": str(e)
            }
    
    def _create_score_breakdown(
        self, 
        aqi: float, 
        population_density: float, 
        distances: Dict[str, float]
    ) -> Dict[str, any]:
        """Create a breakdown for transparency (approximation)"""
        return {
            "aqi": aqi,
            "population_density": population_density,
            "distances": distances,
            "note": "Breakdown approximated for ML model predictions"
        }
    
    async def calculate_batch_scores(
        self, 
        locations: List[Dict]
    ) -> List[Dict]:
        """
        Calculate hotspot scores for multiple locations
        
        Args:
            locations: List of dicts with aqi, population_density, distances
            
        Returns:
            List of score results
        """
        results = []
        
        for i, location in enumerate(locations):
            try:
                score_result = await self.calculate_hotspot_score(
                    aqi=location.get('aqi', 100),
                    population_density=location.get('population_density', 5000),
                    distances=location.get('distances', {})
                )
                score_result['location_index'] = i
                results.append(score_result)
                
            except Exception as e:
                logger.error(f"Error scoring location {i}: {str(e)}")
                results.append({
                    "location_index": i,
                    "score": 0.5,
                    "confidence": 0.0,
                    "method": "error",
                    "error": str(e)
                })
        
        return results
    
    def get_service_status(self) -> Dict[str, any]:
        """Get current service status"""
        return {
            "initialized": self.is_initialized,
            "model_ready": self.is_model_ready(),
            "feature_columns": self.feature_columns,
            "model_type": str(type(self.model).__name__) if self.model else None,
            "scaler_type": str(type(self.scaler).__name__) if self.scaler else None
        }

# Global instance
hotspot_scoring_service = HotspotScoringService()
