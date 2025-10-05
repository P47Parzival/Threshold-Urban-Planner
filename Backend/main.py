from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import auth, users, population, aqi, vacant_land, service_analysis, solar_analysis
from database.connection import connect_to_database, close_database_connection
from services.gee_service import gee_service
from services.hotspots_service import hotspots_service
from services.hotspot_scoring_service import hotspot_scoring_service
from services.distance_service import distance_service
from services.service_analysis_service import service_analysis_service
from services.solar_analysis_service import solar_service
import uvicorn
import logging

app = FastAPI(
    title="Threshold Urban Growth API",
    description="Backend API for urban growth visualization platform",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database events
@app.on_event("startup")
async def startup_event():
    # Configure logging to ensure our debug logs show up
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("="*80)
    print("🚀 STARTING BACKEND SERVER - INITIALIZING SERVICES")
    print("="*80)
    
    # Connect to database
    await connect_to_database()
    
    # Initialize hotspots service
    print("📊 Initializing Hotspots Service...")
    await hotspots_service.initialize()
    print("✅ Hotspots Service initialized")
    
    # Initialize Google Earth Engine
    print("🛰️  Initializing Google Earth Engine...")
    print("🔍 Checking GEE credentials in environment...")
    
    gee_initialized = await gee_service.initialize()
    
    if gee_initialized:
        print("="*80)
        print("🚀 GOOGLE EARTH ENGINE SUCCESSFULLY INITIALIZED!")
        print("✅ Real satellite data processing ENABLED")
        print("🌍 ESA WorldCover dataset ACCESSIBLE")
        print("="*80)
    else:
        print("="*80)
        print("❌ GOOGLE EARTH ENGINE INITIALIZATION FAILED!")
        print("⚠️  Will use SYNTHETIC FALLBACK data for hotspots")
        print("🔧 Check your GEE service account credentials")
        print("="*80)
    
    # Initialize Hotspot Scoring Service
    print("🤖 Initializing Hotspot Scoring Service...")
    await hotspot_scoring_service.initialize()
    
    # Initialize Distance Calculation Service
    print("📍 Initializing Distance Calculation Service...")
    await distance_service.initialize()
    
    # Initialize Service Analysis Service
    print("🏢 Initializing Service Analysis Service...")
    await service_analysis_service.initialize()
    
    # Initialize Solar Analysis Service
    print("🌞 Initializing Solar Analysis Service...")
    await solar_service.initialize()
    
    print("🎯 Backend startup complete!")
    print("="*80)

@app.on_event("shutdown")
async def shutdown_event():
    print("🔧 Shutting down services...")
    await close_database_connection()
    await distance_service.cleanup()
    print("✅ Services shut down successfully")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(population.router, prefix="/api/population", tags=["population"])
app.include_router(aqi.router, prefix="/api/aqi", tags=["air-quality"])
app.include_router(vacant_land.router, prefix="/api/vacant-land", tags=["vacant-land"])
app.include_router(service_analysis.router, prefix="/api/service-analysis", tags=["service-analysis"])
app.include_router(solar_analysis.router)

@app.get("/")
async def root():
    return {"message": "Threshold Urban Growth API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is operational"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
