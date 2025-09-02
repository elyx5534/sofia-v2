"""
Sofia V2 - JWT Token Management
Handle JWT token creation, validation, and refresh
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict

import jwt
from fastapi import HTTPException, status


class JWTHandler:
    """JWT token management for user authentication"""

    def __init__(self):
        self.secret_key = os.getenv(
            "JWT_SECRET_KEY", "sofia-v2-default-secret-change-in-production"
        )
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7

    def create_access_token(self, user_id: int, email: str, subscription_tier: str) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "user_id": user_id,
            "email": email,
            "subscription_tier": subscription_tier,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: int) -> str:
        """Create JWT refresh token"""
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        payload = {"user_id": user_id, "exp": expire, "iat": datetime.utcnow(), "type": "refresh"}

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Verify access token specifically"""
        payload = self.verify_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """Verify refresh token specifically"""
        payload = self.verify_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return payload

    def create_api_access_token(self, user_id: int, api_key_id: int) -> str:
        """Create long-lived token for API access"""
        expire = datetime.utcnow() + timedelta(days=30)  # API tokens last 30 days

        payload = {
            "user_id": user_id,
            "api_key_id": api_key_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "api_access",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)


# Global JWT handler instance
jwt_handler = JWTHandler()
