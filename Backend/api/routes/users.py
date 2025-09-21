from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from models.user import UserResponse
from services.user_service import UserService
from api.routes.auth import get_current_user

router = APIRouter()

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(current_user: UserResponse = Depends(get_current_user)):
    """Get user profile information"""
    return current_user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user by ID (authenticated users only)"""
    user = await UserService.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user
