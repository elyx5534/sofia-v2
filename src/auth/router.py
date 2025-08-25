"""
Sofia V2 - Authentication Router
FastAPI routes for user registration, login, and account management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
import hashlib

from .models import User, APIKey, SubscriptionTier, UsageLog
from .jwt_handler import jwt_handler
from .dependencies import get_current_user, get_current_active_user, admin_required
from ..data_hub.database import get_db
from pydantic import BaseModel, EmailStr


router = APIRouter(prefix="/auth", tags=["Authentication"])


# Pydantic models for request/response
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    subscription_tier: str
    subscription_active: bool
    subscription_expires: Optional[datetime]
    is_active: bool
    is_verified: bool
    created_at: datetime
    api_calls_this_month: int
    total_backtests: int

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes


class APIKeyCreate(BaseModel):
    name: str
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool
    calls_today: int
    calls_this_month: int

    class Config:
        from_attributes = True


class APIKeyWithSecret(BaseModel):
    """Response when creating new API key (includes secret)"""
    id: int
    name: str
    key: str  # Full API key - only shown once!
    key_prefix: str
    expires_at: Optional[datetime]


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register new user account"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Create new user
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        subscription_tier=SubscriptionTier.FREE,
        subscription_active=True
    )
    user.set_password(user_data.password)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """User login with email/username and password"""
    
    # Find user by email or username
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()
    
    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )
    
    # Create tokens
    access_token = jwt_handler.create_access_token(
        user_id=user.id,
        email=user.email,
        subscription_tier=user.subscription_tier
    )
    refresh_token = jwt_handler.create_refresh_token(user.id)
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    
    try:
        payload = jwt_handler.verify_refresh_token(refresh_token)
        user_id = payload.get("user_id")
    except HTTPException:
        raise
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Create new tokens
    access_token = jwt_handler.create_access_token(
        user_id=user.id,
        email=user.email,
        subscription_tier=user.subscription_tier
    )
    new_refresh_token = jwt_handler.create_refresh_token(user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": 1800
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user


@router.get("/me/limits")
async def get_user_limits(
    current_user: User = Depends(get_current_user)
):
    """Get current user's rate limits and usage"""
    limits = current_user.get_rate_limits()
    
    return {
        "subscription_tier": current_user.subscription_tier,
        "limits": limits,
        "usage": {
            "api_calls_this_month": current_user.api_calls_this_month,
            "total_backtests": current_user.total_backtests
        },
        "subscription_active": current_user.is_subscription_active(),
        "subscription_expires": current_user.subscription_expires
    }


@router.post("/api-keys", response_model=APIKeyWithSecret, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new API key for user"""
    
    # Check if user can create more API keys (limit based on subscription)
    existing_keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True
    ).count()
    
    max_keys = {
        SubscriptionTier.FREE: 1,
        SubscriptionTier.BASIC: 3,
        SubscriptionTier.PRO: 10,
        SubscriptionTier.ENTERPRISE: 50
    }.get(current_user.subscription_tier, 1)
    
    if existing_keys >= max_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {max_keys} API keys allowed for {current_user.subscription_tier} tier"
        )
    
    # Generate API key
    key = current_user.generate_api_key()
    key_hash = APIKey.hash_key(key)
    key_prefix = key[:12] + "..."
    
    # Set expiration if specified
    expires_at = None
    if api_key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=api_key_data.expires_in_days)
    
    # Create API key record
    api_key = APIKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=api_key_data.name,
        expires_at=expires_at
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return APIKeyWithSecret(
        id=api_key.id,
        name=api_key.name,
        key=key,  # Only returned once!
        key_prefix=key_prefix,
        expires_at=expires_at
    )


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's API keys"""
    
    api_keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id
    ).order_by(APIKey.created_at.desc()).all()
    
    return api_keys


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Revoke/delete API key"""
    
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Instead of deleting, deactivate for audit trail
    api_key.is_active = False
    db.commit()
    
    return {"message": "API key revoked successfully"}


@router.get("/usage-stats")
async def get_usage_statistics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    days: int = 30
):
    """Get usage statistics for current user"""
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    usage_logs = db.query(UsageLog).filter(
        UsageLog.user_id == current_user.id,
        UsageLog.timestamp >= since_date
    ).all()
    
    # Aggregate statistics
    stats = {
        "total_requests": len(usage_logs),
        "successful_requests": len([log for log in usage_logs if 200 <= log.status_code < 300]),
        "failed_requests": len([log for log in usage_logs if log.status_code >= 400]),
        "avg_response_time": sum(log.processing_time for log in usage_logs) / len(usage_logs) if usage_logs else 0,
        "endpoints_used": list(set(log.endpoint for log in usage_logs)),
        "period_days": days
    }
    
    return stats


# Admin endpoints
@router.get("/admin/users", response_model=List[UserResponse])
async def list_all_users(
    admin_user: User = Depends(admin_required),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Admin: List all users"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.put("/admin/users/{user_id}/subscription")
async def update_user_subscription(
    user_id: int,
    tier: SubscriptionTier,
    expires_in_days: Optional[int] = None,
    admin_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Admin: Update user subscription"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.subscription_tier = tier
    user.subscription_active = True
    
    if expires_in_days:
        user.subscription_expires = datetime.utcnow() + timedelta(days=expires_in_days)
    else:
        user.subscription_expires = None
    
    db.commit()
    
    return {"message": f"User subscription updated to {tier}"}


@router.get("/admin/stats")
async def get_platform_statistics(
    admin_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Admin: Get platform-wide statistics"""
    
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    paid_users = db.query(User).filter(User.subscription_tier != SubscriptionTier.FREE).count()
    
    # Usage in last 24 hours
    since_yesterday = datetime.utcnow() - timedelta(hours=24)
    recent_usage = db.query(UsageLog).filter(
        UsageLog.timestamp >= since_yesterday
    ).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "paid_users": paid_users,
        "free_users": total_users - paid_users,
        "api_calls_24h": recent_usage,
        "conversion_rate": (paid_users / total_users * 100) if total_users > 0 else 0
    }