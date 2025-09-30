import requests
import pandas as pd
import numpy as np

# AQI breakpoints for each pollutant
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

# Conversion functions
def ugm3_to_ppb_o3(ugm3): return ugm3 * 0.5  # O3: μg/m³ to ppb
def ugm3_to_ppb_no2(ugm3): return ugm3 * 0.532  # NO2: μg/m³ to ppb
def ugm3_to_ppb_so2(ugm3): return ugm3 * 0.382  # SO2: μg/m³ to ppb

# Calculate AQI for a single pollutant
def calculate_aqi(concentration, pollutant, truncate_decimals=None):
    if concentration is None or np.isnan(concentration):
        return np.nan
    # Truncate concentration per EPA rules
    if truncate_decimals == 1:
        concentration = np.floor(concentration * 10) / 10  # 1 decimal
    elif truncate_decimals == 0:
        concentration = np.floor(concentration)  # Integer
    breakpoints = AQI_BREAKPOINTS[pollutant]
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= concentration <= c_high:
            return ((i_high - i_low) / (c_high - c_low)) * (concentration - c_low) + i_low
    return np.nan  # Out of range

# Fetch and process data
url = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=24.27&longitude=74.06&start_date=2025-09-23&end_date=2025-09-30&hourly=pm10,pm2_5,nitrogen_dioxide,ozone,sulphur_dioxide,carbon_monoxide&timezone=auto"
response = requests.get(url)
data = response.json()

if "hourly" not in data:
    print("No hourly data returned:", data)
    exit()

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
df["o3_8h"] = df["ozone_ppb"].rolling(window=8, min_periods=6).mean().apply(lambda x: np.floor(x) if not np.isnan(x) else np.nan)
df["co_8h"] = df["carbon_monoxide"].rolling(window=8, min_periods=6).mean().apply(lambda x: np.floor(x * 10) / 10 if not np.isnan(x) else np.nan)
df["aqi_o3_8h"] = df["o3_8h"].apply(lambda x: calculate_aqi(x, "ozone_8h", truncate_decimals=0))
df["aqi_co_8h"] = df["co_8h"].apply(lambda x: calculate_aqi(x, "co_8h", truncate_decimals=1))

# Overall AQI (max of sub-indices)
df["aqi"] = df[["aqi_pm2_5", "aqi_pm10", "aqi_no2_1h", "aqi_o3_8h", "aqi_so2_1h", "aqi_co_8h"]].max(axis=1)

# Aggregate to daily AQI (max of hourly AQI per day)
daily_aqi = df["aqi"].resample("D").max().round(0).astype(int)
print("Daily AQI (Max of Hourly AQI):")
print(daily_aqi)

# Optional: Save to CSV
# daily_aqi.to_csv("udaipur_daily_aqi.csv")

# Optional: Print full hourly data for inspection
# print("\nHourly Data with AQI:")
# print(df[["pm2_5", "pm10", "no2_ppb", "o3_8h", "so2_ppb", "co_8h", "aqi"]])