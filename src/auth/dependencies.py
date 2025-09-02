"""
Sofia V2 - Authentication Dependencies
FastAPI dependencies for user authentication and authorization
"""

import hashlib
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..data_hub.database import get_db
from .jwt_handler import jwt_handler
from .models import APIKey, SubscriptionTier, User

security = HTTPBearer()


class AuthenticationError(HTTPException):
    """Custom authentication error"""

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """Custom authorization error"""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    try:
        payload = jwt_handler.verify_access_token(credentials.credentials)
        user_id = payload.get("user_id")
        if user_id is None:
            raise AuthenticationError()
    except Exception:
        raise AuthenticationError()

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("Inactive user")

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user with subscription check"""
    if not current_user.is_active:
        raise AuthenticationError("Inactive user")

    return current_user


def get_api_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get user from API key (for API endpoints)"""
    # Check for API key in header
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None

    # Hash the API key to find it in database
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    api_key_record = (
        db.query(APIKey).filter(APIKey.key_hash == key_hash, APIKey.is_active == True).first()
    )

    if not api_key_record or not api_key_record.is_valid():
        raise AuthenticationError("Invalid API key")

    user = api_key_record.user
    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    # Update API key usage
    api_key_record.last_used = datetime.utcnow()
    api_key_record.calls_today += 1
    api_key_record.calls_this_month += 1

    # Update user usage
    user.api_calls_this_month += 1

    db.commit()

    return user


def require_subscription(min_tier: SubscriptionTier = SubscriptionTier.BASIC):
    """Dependency to require minimum subscription tier"""

    def subscription_check(current_user: User = Depends(get_current_active_user)):
        if not current_user.is_subscription_active():
            raise AuthorizationError("Active subscription required")

        # Check tier hierarchy
        tier_hierarchy = {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.BASIC: 1,
            SubscriptionTier.PRO: 2,
            SubscriptionTier.ENTERPRISE: 3,
        }

        user_tier_level = tier_hierarchy.get(current_user.subscription_tier, 0)
        required_tier_level = tier_hierarchy.get(min_tier, 1)

        if user_tier_level < required_tier_level:
            raise AuthorizationError(f"Subscription tier '{min_tier}' or higher required")

        return current_user

    return subscription_check


def check_rate_limit(current_user: User = Depends(get_current_active_user)) -> User:
    """Check if user has exceeded rate limits"""
    limits = current_user.get_rate_limits()

    # Check monthly API calls
    if current_user.api_calls_this_month >= limits["api_calls_per_month"]:
        raise AuthorizationError("Monthly API call limit exceeded")

    return current_user


def get_user_or_api_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get user from either JWT token or API key"""
    # First try API key
    api_user = get_api_user(request, db)
    if api_user:
        return api_user

    # Then try JWT token
    if credentials:
        try:
            payload = jwt_handler.verify_access_token(credentials.credentials)
            user_id = payload.get("user_id")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user and user.is_active:
                    return user
        except Exception:
            pass

    raise AuthenticationError("No valid authentication provided")


# Convenience functions for different subscription tiers
def require_basic_subscription():
    return require_subscription(SubscriptionTier.BASIC)


def require_pro_subscription():
    return require_subscription(SubscriptionTier.PRO)


def require_enterprise_subscription():
    return require_subscription(SubscriptionTier.ENTERPRISE)


def admin_required(current_user: User = Depends(get_current_active_user)) -> User:
    """Require admin privileges (for admin endpoints)"""
    # You can add admin field to User model or check by email domain
    admin_emails = ["admin@sofia-v2.com", "elyx5534@gmail.com"]  # Update with your admin emails

    if current_user.email not in admin_emails:
        raise AuthorizationError("Admin privileges required")

    return current_user
