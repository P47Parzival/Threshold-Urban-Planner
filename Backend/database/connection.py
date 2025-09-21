from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Database:
    client: Optional[AsyncIOMotorClient] = None
    database = None

database = Database()

async def get_database():
    return database.database

async def connect_to_database():
    """Create database connection"""
    # MongoDB connection string - you can set this in .env file
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "threshold_urban_growth")
    
    print(f"Connecting to MongoDB at {mongodb_url}")
    database.client = AsyncIOMotorClient(mongodb_url)
    database.database = database.client[database_name]
    
    # Test the connection
    try:
        await database.client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        raise e

async def close_database_connection():
    """Close database connection"""
    if database.client:
        database.client.close()
        print("MongoDB connection closed.")
