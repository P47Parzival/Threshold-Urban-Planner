from fastapi import APIRouter, HTTPException, Query
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

router = APIRouter()

# AQI breakpoints for each pollutant (EPA standards)
AQI_BREAKPOINTS = {
    "pm2_5": [
        (0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200), (150.5, 250.4, 201, 300), (250.5, 500.4, 301, 500)
    ],
    "pm10": [
        (0, 54, 0, 50), (55, 154, 51, 100), (155, 254, 101, 150),
        (255, 354, 151, 200), (355, 424, 201, 300), (425, 604, 301, 500)
    ],
    "ozone_8h": [
        (0, 54, 0, 50), (55, 70, 51, 100), (71, 85, 101, 150),
        (86, 105, 151, 200), (106, 200, 201, 300), (201, 604, 301, 500)
    ],
    "no2_1h": [
        (0, 53, 0, 50), (54, 100, 51, 100), (101, 360, 101, 150),
        (361, 649, 151, 200), (650, 1249, 201, 300), (1250, 2049, 301, 500)
    ],
    "so2_1h": [
        (0, 35, 0, 50), (36, 75, 51, 100), (76, 185, 101, 150),
        (186, 304, 151, 200), (305, 604, 201, 300), (605, 1004, 301, 500)
    ],
    "co_8h": [
        (0.0, 4.4, 0, 50), (4.5, 9.4, 51, 100), (9.5, 12.4, 101, 150),
        (12.5, 15.4, 151, 200), (15.5, 30.4, 201, 300), (30.5, 50.4, 301, 500)
    ]
}

# Conversion functions (μg/m³ to ppb)
def ugm3_to_ppb_o3(ugm3):
    """Convert O3 from μg/m³ to ppb"""
    return ugm3 * 0.5 if ugm3 is not None else None

def ugm3_to_ppb_no2(ugm3):
    """Convert NO2 from μg/m³ to ppb"""
    return ugm3 * 0.532 if ugm3 is not None else None

def ugm3_to_ppb_so2(ugm3):
    """Convert SO2 from μg/m³ to ppb"""
    return ugm3 * 0.382 if ugm3 is not None else None

def calculate_aqi(concentration, pollutant, truncate_decimals=None):
    """Calculate AQI for a single pollutant concentration"""
    if concentration is None or np.isnan(concentration):
        return np.nan
    
    # Truncate concentration per EPA rules
    if truncate_decimals == 1:
        concentration = np.floor(concentration * 10) / 10  # 1 decimal
    elif truncate_decimals == 0:
        concentration = np.floor(concentration)  # Integer
    
    breakpoints = AQI_BREAKPOINTS.get(pollutant)
    if not breakpoints:
        return np.nan
    
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= concentration <= c_high:
            return ((i_high - i_low) / (c_high - c_low)) * (concentration - c_low) + i_low
    
    return np.nan  # Out of range

def fetch_open_meteo_data(latitude: float, longitude: float, start_date: str, end_date: str):
    """Fetch air quality data from Open-Meteo API"""
    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?"
        f"latitude={latitude}&longitude={longitude}&"
        f"start_date={start_date}&end_date={end_date}&"
        f"hourly=pm10,pm2_5,nitrogen_dioxide,ozone,sulphur_dioxide,carbon_monoxide&"
        f"timezone=auto"
    )
    
    try:
        response = requests.get(url, timeout=30)
        
        # Handle different response codes gracefully
        if response.status_code == 400:
            # 400 typically means no data available for this location
            logging.info(f"No air quality data available for location {latitude}, {longitude}")
            return None
        elif response.status_code == 404:
            # 404 means location not found
            logging.info(f"Location not found in Open-Meteo database: {latitude}, {longitude}")
            return None
        elif response.status_code >= 500:
            # Server errors - we can retry later
            logging.warning(f"Open-Meteo server error for {latitude}, {longitude}: {response.status_code}")
            return None
        
        response.raise_for_status()  # Raise for other HTTP errors
        return response.json()
        
    except requests.Timeout:
        logging.warning(f"Timeout fetching data for {latitude}, {longitude}")
        return None
    except requests.ConnectionError:
        logging.warning(f"Connection error fetching data for {latitude}, {longitude}")
        return None
    except requests.RequestException as e:
        logging.warning(f"Request failed for {latitude}, {longitude}: {e}")
        return None

def process_aqi_data(data):
    """Process Open-Meteo data and calculate AQI"""
    if "hourly" not in data:
        raise HTTPException(status_code=400, detail="No hourly data returned from API")
    
    # Create DataFrame
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)
    
    # Convert units for AQI calculation
    df["ozone_ppb"] = df["ozone"].apply(ugm3_to_ppb_o3)
    df["no2_ppb"] = df["nitrogen_dioxide"].apply(ugm3_to_ppb_no2)
    df["so2_ppb"] = df["sulphur_dioxide"].apply(ugm3_to_ppb_so2)
    
    # Calculate hourly AQI for each pollutant
    df["aqi_pm2_5"] = df["pm2_5"].apply(lambda x: calculate_aqi(x, "pm2_5", truncate_decimals=1))
    df["aqi_pm10"] = df["pm10"].apply(lambda x: calculate_aqi(x, "pm10", truncate_decimals=0))
    df["aqi_no2_1h"] = df["no2_ppb"].apply(lambda x: calculate_aqi(x, "no2_1h", truncate_decimals=0))
    df["aqi_so2_1h"] = df["so2_ppb"].apply(lambda x: calculate_aqi(x, "so2_1h", truncate_decimals=0))
    
    # For O3 and CO (8-hour averages)
    df["o3_8h"] = df["ozone_ppb"].rolling(window=8, min_periods=6).mean().apply(
        lambda x: np.floor(x) if not np.isnan(x) else np.nan
    )
    df["co_8h"] = df["carbon_monoxide"].rolling(window=8, min_periods=6).mean().apply(
        lambda x: np.floor(x * 10) / 10 if not np.isnan(x) else np.nan
    )
    df["aqi_o3_8h"] = df["o3_8h"].apply(lambda x: calculate_aqi(x, "ozone_8h", truncate_decimals=0))
    df["aqi_co_8h"] = df["co_8h"].apply(lambda x: calculate_aqi(x, "co_8h", truncate_decimals=1))
    
    # Overall AQI (max of sub-indices)
    df["aqi"] = df[["aqi_pm2_5", "aqi_pm10", "aqi_no2_1h", "aqi_o3_8h", "aqi_so2_1h", "aqi_co_8h"]].max(axis=1)
    
    return df

@router.get("/calculate")
async def calculate_aqi_for_location(
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate"),
    date: str = Query(..., description="Target date (YYYY-MM-DD)")
):
    """Calculate AQI for a specific location and date"""
    try:
        # Parse the target date
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        # Calculate date range (7 days for rolling averages)
        start_date = target_date - timedelta(days=7)
        end_date = target_date
        
        # Fetch data from Open-Meteo
        data = fetch_open_meteo_data(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
        # Handle case where no data is available
        if data is None:
            return {
                "latitude": latitude,
                "longitude": longitude,
                "date": date,
                "data_available": False,
                "message": "No air quality data available for this location",
                "aqi": None,
                "pollutants": None,
                "sub_indices": None
            }
        
        # Check if data has the expected structure
        if "hourly" not in data or not data["hourly"]:
            return {
                "latitude": latitude,
                "longitude": longitude,
                "date": date,
                "data_available": False,
                "message": "No hourly data available for this location",
                "aqi": None,
                "pollutants": None,
                "sub_indices": None
            }
        
        # Process and calculate AQI
        df = process_aqi_data(data)
        
        # Get the latest available AQI data
        latest_data = df.tail(1)
        
        if latest_data.empty or latest_data["aqi"].isna().all():
            return {
                "latitude": data.get("latitude", latitude),
                "longitude": data.get("longitude", longitude),
                "date": date,
                "data_available": False,
                "message": "Unable to calculate AQI from available data",
                "aqi": None,
                "pollutants": None,
                "sub_indices": None
            }
        
        latest_row = latest_data.iloc[0]
        
        # Prepare response
        result = {
            "latitude": data.get("latitude", latitude),
            "longitude": data.get("longitude", longitude),
            "date": date,
            "timezone": data.get("timezone"),
            "data_available": True,
            "aqi": int(latest_row["aqi"]) if not np.isnan(latest_row["aqi"]) else None,
            "pollutants": {
                "pm2_5": float(latest_row["pm2_5"]) if not np.isnan(latest_row["pm2_5"]) else None,
                "pm10": float(latest_row["pm10"]) if not np.isnan(latest_row["pm10"]) else None,
                "no2": float(latest_row["nitrogen_dioxide"]) if not np.isnan(latest_row["nitrogen_dioxide"]) else None,
                "ozone": float(latest_row["ozone"]) if not np.isnan(latest_row["ozone"]) else None,
                "so2": float(latest_row["sulphur_dioxide"]) if not np.isnan(latest_row["sulphur_dioxide"]) else None,
                "co": float(latest_row["carbon_monoxide"]) if not np.isnan(latest_row["carbon_monoxide"]) else None,
            },
            "sub_indices": {
                "aqi_pm2_5": int(latest_row["aqi_pm2_5"]) if not np.isnan(latest_row["aqi_pm2_5"]) else None,
                "aqi_pm10": int(latest_row["aqi_pm10"]) if not np.isnan(latest_row["aqi_pm10"]) else None,
                "aqi_no2": int(latest_row["aqi_no2_1h"]) if not np.isnan(latest_row["aqi_no2_1h"]) else None,
                "aqi_ozone": int(latest_row["aqi_o3_8h"]) if not np.isnan(latest_row["aqi_o3_8h"]) else None,
                "aqi_so2": int(latest_row["aqi_so2_1h"]) if not np.isnan(latest_row["aqi_so2_1h"]) else None,
                "aqi_co": int(latest_row["aqi_co_8h"]) if not np.isnan(latest_row["aqi_co_8h"]) else None,
            }
        }
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error calculating AQI for {latitude}, {longitude}: {e}")
        # Return a graceful response instead of 500 error
        return {
            "latitude": latitude,
            "longitude": longitude,
            "date": date,
            "data_available": False,
            "message": f"Error processing data: {str(e)}",
            "aqi": None,
            "pollutants": None,
            "sub_indices": None
        }

@router.get("/batch")
async def calculate_aqi_batch(
    locations: str = Query(..., description="JSON string of locations: [{lat, lng}, ...]"),
    date: str = Query(..., description="Target date (YYYY-MM-DD)")
):
    """Calculate AQI for multiple locations at once"""
    try:
        import json
        location_list = json.loads(locations)
        
        results = []
        for location in location_list:
            try:
                result = await calculate_aqi_for_location(
                    latitude=location["lat"],
                    longitude=location["lng"],
                    date=date
                )
                results.append(result)
            except Exception as e:
                # Include failed locations with error info
                results.append({
                    "latitude": location["lat"],
                    "longitude": location["lng"],
                    "error": str(e),
                    "aqi": None
                })
        
        return {"results": results, "count": len(results)}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for locations")
    except Exception as e:
        logging.error(f"Error in batch AQI calculation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
