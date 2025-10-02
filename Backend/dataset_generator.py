import pandas as pd
import random
import numpy as np

# Number of samples
N = 15000  # Increased for better training diversity

def generate_area_type():
    """Define different area types with realistic characteristics"""
    area_types = [
        {"type": "urban_core", "weight": 0.25, "pop_range": (8000, 35000), "aqi_range": (80, 250)},
        {"type": "suburban", "weight": 0.35, "pop_range": (2000, 12000), "aqi_range": (40, 120)},
        {"type": "rural", "weight": 0.20, "pop_range": (100, 3000), "aqi_range": (20, 80)},
        {"type": "industrial", "weight": 0.15, "pop_range": (1000, 8000), "aqi_range": (100, 300)},
        {"type": "outskirts", "weight": 0.05, "pop_range": (500, 5000), "aqi_range": (30, 100)}
    ]
    
    rand = random.random()
    cumulative = 0
    for area in area_types:
        cumulative += area["weight"]
        if rand <= cumulative:
            return area
    return area_types[0]  # fallback

def realistic_aqi(area_type, base_range):
    """Generate realistic AQI with seasonal and daily variations"""
    min_aqi, max_aqi = base_range
    
    # Base AQI for area type
    base_aqi = random.randint(min_aqi, max_aqi)
    
    # Add seasonal variation (winter higher AQI in many regions)
    seasonal_factor = random.uniform(0.8, 1.3)
    
    # Add daily variation
    daily_factor = random.uniform(0.9, 1.1)
    
    final_aqi = int(base_aqi * seasonal_factor * daily_factor)
    return max(15, min(400, final_aqi))  # Clamp to realistic range

def correlated_distances(area_type, pop_density):
    """Generate distances that correlate with area type and population density"""
    # Base distance modifiers for different area types
    distance_modifiers = {
        "urban_core": {"hospital": 0.3, "school": 0.4, "bus": 0.2, "rail": 0.5, "mall": 0.3, "airport": 1.2},
        "suburban": {"hospital": 0.8, "school": 0.6, "bus": 0.7, "rail": 0.9, "mall": 0.6, "airport": 0.8},
        "rural": {"hospital": 2.5, "school": 1.8, "bus": 3.0, "rail": 2.8, "mall": 2.2, "airport": 1.5},
        "industrial": {"hospital": 1.5, "school": 1.2, "bus": 1.0, "rail": 0.7, "mall": 1.4, "airport": 0.9},
        "outskirts": {"hospital": 2.0, "school": 1.5, "bus": 2.0, "rail": 1.8, "mall": 1.8, "airport": 1.2}
    }
    
    modifiers = distance_modifiers[area_type]
    
    # Population density factor (higher density = closer amenities)
    pop_factor = max(0.3, 1.5 - (pop_density / 25000))
    
    # Generate distances with realistic base ranges
    distances = {}
    base_distances = {
        "hospital": (0.5, 15),
        "school": (0.3, 12),
        "bus": (0.1, 8),
        "rail": (1.0, 25),
        "mall": (0.8, 18),
        "airport": (5, 60)
    }
    
    for amenity, (min_base, max_base) in base_distances.items():
        modifier = modifiers[amenity] * pop_factor
        
        # Add some randomness
        random_factor = random.uniform(0.7, 1.4)
        
        min_dist = min_base * modifier * random_factor
        max_dist = max_base * modifier * random_factor
        
        distance = random.uniform(min_dist, max_dist)
        distances[amenity] = round(max(0.1, distance), 2)
    
    return distances

def calculate_advanced_hotspot_score(aqi, pop_density, distances, area_type):
    """Enhanced hotspot scoring with more sophisticated logic"""
    
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
    if pop_density < 1000:
        pop_score = 0.2  # Too rural
    elif pop_density < 5000:
        pop_score = 0.6
    elif pop_density < 15000:
        pop_score = 1.0  # Optimal range
    elif pop_density < 25000:
        pop_score = 0.8
    else:
        pop_score = 0.4  # Too crowded
    
    # 3. Distance Scores (using sigmoid-like curves for more realistic scoring)
    def distance_score(dist, optimal, max_acceptable):
        if dist <= optimal:
            return 1.0
        elif dist <= max_acceptable:
            # Sigmoid decline
            decay = (dist - optimal) / (max_acceptable - optimal)
            return max(0, 1 - (decay ** 2))
        else:
            return 0.0
    
    # Optimal and maximum acceptable distances
    hosp_score = distance_score(distances["hospital"], 2.0, 10.0)
    school_score = distance_score(distances["school"], 1.0, 8.0)
    bus_score = distance_score(distances["bus"], 0.5, 3.0)
    rail_score = distance_score(distances["rail"], 2.0, 15.0)
    mall_score = distance_score(distances["mall"], 1.5, 10.0)
    airport_score = distance_score(distances["airport"], 15.0, 45.0)
    
    # 4. Area Type Bonus
    area_bonuses = {
        "urban_core": 0.05,
        "suburban": 0.10,  # Best for residential
        "rural": -0.05,
        "industrial": -0.10,
        "outskirts": 0.0
    }
    area_bonus = area_bonuses[area_type]
    
    # 5. Weighted Final Score with improved weights
    base_score = (
        (aqi_score * 0.25) +         # Environmental quality is crucial
        (pop_score * 0.20) +         # Population density for livability
        (hosp_score * 0.15) +        # Healthcare access
        (school_score * 0.15) +      # Education access
        (bus_score * 0.10) +         # Public transport
        (rail_score * 0.05) +        # Regional connectivity
        (mall_score * 0.08) +        # Commercial access
        (airport_score * 0.02)       # International connectivity
    )
    
    # Add area bonus and clamp to [0, 1]
    final_score = max(0, min(1, base_score + area_bonus))
    
    return round(final_score, 4)  # 4 decimals for precision

# Generate enhanced dataset
print("🏗️  Generating Enhanced Urban Hotspot Dataset...")
print("=" * 60)

rows = []

for i in range(N):
    if i % 1000 == 0:
        print(f"⚙️  Generating sample {i}/{N}...")
    
    # 1. Determine area type
    area = generate_area_type()
    area_type = area["type"]
    
    # 2. Generate correlated population density
    min_pop, max_pop = area["pop_range"]
    pop_density = random.randint(min_pop, max_pop)
    
    # 3. Generate realistic AQI
    aqi_value = realistic_aqi(area_type, area["aqi_range"])
    
    # 4. Generate correlated distances
    distances = correlated_distances(area_type, pop_density)
    
    # 5. Calculate sophisticated hotspot score
    score = calculate_advanced_hotspot_score(aqi_value, pop_density, distances, area_type)
    
    # 6. Create row
    row = {
        "AQI": aqi_value,
        "PopulationDensity": pop_density,
        "DistHospital": distances["hospital"],
        "DistSchool": distances["school"],
        "DistAirport": distances["airport"],
        "DistBus": distances["bus"],
        "DistRailway": distances["rail"],
        "DistMall": distances["mall"],
        "HotspotScore": score,
        "AreaType": area_type  # For analysis (remove before training)
    }
    rows.append(row)

# Create DataFrame
df = pd.DataFrame(rows)

# Create training dataset (remove AreaType column)
df_train = df.drop(columns=['AreaType'])

# Save datasets
df_train.to_csv("urban_hotspot_score.csv", index=False)
df.to_csv("urban_hotspot_score_with_areas.csv", index=False)  # For analysis

print("=" * 60)
print("✅ ENHANCED DATASET CREATED SUCCESSFULLY!")
print("=" * 60)

# Dataset Statistics
print(f"📊 Total Samples: {len(df):,}")
print(f"📏 Features: {len(df_train.columns)-1} (excluding target)")
print(f"🎯 Target: HotspotScore (range: {df['HotspotScore'].min():.3f} - {df['HotspotScore'].max():.3f})")

print("\n🏙️  Area Type Distribution:")
area_counts = df['AreaType'].value_counts()
for area_type, count in area_counts.items():
    percentage = (count / len(df)) * 100
    print(f"   {area_type}: {count:,} ({percentage:.1f}%)")

print(f"\n📈 Score Distribution:")
print(f"   Mean: {df['HotspotScore'].mean():.3f}")
print(f"   Std:  {df['HotspotScore'].std():.3f}")
print(f"   High scores (>0.8): {(df['HotspotScore'] > 0.8).sum():,} ({((df['HotspotScore'] > 0.8).sum() / len(df)) * 100:.1f}%)")
print(f"   Low scores (<0.3): {(df['HotspotScore'] < 0.3).sum():,} ({((df['HotspotScore'] < 0.3).sum() / len(df)) * 100:.1f}%)")

print(f"\n🌍 AQI Distribution:")
print(f"   Mean: {df['AQI'].mean():.1f}")
print(f"   Good (≤50): {(df['AQI'] <= 50).sum():,}")
print(f"   Moderate (51-100): {((df['AQI'] > 50) & (df['AQI'] <= 100)).sum():,}")
print(f"   Unhealthy (>150): {(df['AQI'] > 150).sum():,}")

print(f"\n🏘️  Population Density:")
print(f"   Mean: {df['PopulationDensity'].mean():.0f} people/km²")
print(f"   Range: {df['PopulationDensity'].min():,} - {df['PopulationDensity'].max():,}")

print("\n📍 Average Distances (km):")
distance_cols = ['DistHospital', 'DistSchool', 'DistAirport', 'DistBus', 'DistRailway', 'DistMall']
for col in distance_cols:
    print(f"   {col.replace('Dist', '')}: {df[col].mean():.2f}")

print("\n🎯 READY FOR MODEL TRAINING!")
print(f"📁 Main dataset: urban_hotspot_score.csv ({len(df_train.columns)} columns)")
print(f"📁 Analysis dataset: urban_hotspot_score_with_areas.csv (includes area types)")
print("=" * 60)

# Show sample data
print("\n📋 Sample Data:")
print(df_train.head(10).to_string(index=False))

print(f"\n🚀 Next Steps:")
print(f"   1. Train your model on 'urban_hotspot_score.csv'")
print(f"   2. Generate 'scaler.pkl' for feature scaling")
print(f"   3. Integrate with backend for real hotspot scoring!")
print("=" * 60)
