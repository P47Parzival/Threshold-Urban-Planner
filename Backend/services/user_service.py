from models.user import UserCreate, UserInDB, UserResponse
from database.connection import get_database
from utils.auth import get_password_hash, verify_password
from typing import Optional
from bson import ObjectId
from datetime import datetime

class UserService:
    @staticmethod
    async def create_user(user_data: UserCreate) -> UserResponse:
        """Create a new user"""
        db = await get_database()
        
        # Check if user already exists
        existing_user = await db.users.find_one({"email": user_data.email})
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Hash the password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user document
        user_doc = UserInDB(
            name=user_data.name,
            email=user_data.email,
            profession=user_data.profession,
            hashed_password=hashed_password,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Insert into database
        result = await db.users.insert_one(user_doc.dict(by_alias=True, exclude={"id"}))
        
        # Fetch the created user
        created_user = await db.users.find_one({"_id": result.inserted_id})
        
        return UserResponse(
            _id=str(created_user["_id"]),
            name=created_user["name"],
            email=created_user["email"],
            profession=created_user["profession"],
            created_at=created_user["created_at"]
        )
    
    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[UserResponse]:
        """Authenticate a user by email and password"""
        db = await get_database()
        
        # Find user by email
        user_doc = await db.users.find_one({"email": email})
        if not user_doc:
            return None
        
        # Verify password
        if not verify_password(password, user_doc["hashed_password"]):
            return None
        
        return UserResponse(
            _id=str(user_doc["_id"]),
            name=user_doc["name"],
            email=user_doc["email"],
            profession=user_doc["profession"],
            created_at=user_doc["created_at"]
        )
    
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[UserResponse]:
        """Get user by email"""
        db = await get_database()
        
        user_doc = await db.users.find_one({"email": email})
        if not user_doc:
            return None
        
        return UserResponse(
            _id=str(user_doc["_id"]),
            name=user_doc["name"],
            email=user_doc["email"],
            profession=user_doc["profession"],
            created_at=user_doc["created_at"]
        )
    
    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[UserResponse]:
        """Get user by ID"""
        db = await get_database()
        
        try:
            user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
            if not user_doc:
                return None
            
            return UserResponse(
                _id=str(user_doc["_id"]),
                name=user_doc["name"],
                email=user_doc["email"],
                profession=user_doc["profession"],
                created_at=user_doc["created_at"]
            )
        except Exception:
            return None
