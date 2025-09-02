"""
Sofia V2 - Authentication Models
User, subscription, and API key management
"""

import hashlib
import secrets
from datetime import datetime
from enum import Enum

from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SubscriptionTier(str, Enum):
    """Subscription tiers"""

    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    """User model with authentication and subscription info"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)

    # Subscription info
    subscription_tier = Column(String(20), default=SubscriptionTier.FREE)
    subscription_active = Column(Boolean, default=True)
    subscription_expires = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String(100), nullable=True)

    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Usage tracking
    api_calls_this_month = Column(Integer, default=0)
    total_backtests = Column(Integer, default=0)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user")
    usage_logs = relationship("UsageLog", back_populates="user")

    def verify_password(self, password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(password, self.hashed_password)

    def set_password(self, password: str):
        """Set password hash"""
        self.hashed_password = pwd_context.hash(password)

    def generate_api_key(self) -> str:
        """Generate new API key for user"""
        key = f"sk_{'live' if self.subscription_tier != SubscriptionTier.FREE else 'test'}_{secrets.token_urlsafe(32)}"
        return key

    def is_subscription_active(self) -> bool:
        """Check if subscription is active and not expired"""
        if not self.subscription_active:
            return False
        if self.subscription_expires and self.subscription_expires < datetime.utcnow():
            return False
        return True

    def get_rate_limits(self) -> dict:
        """Get rate limits based on subscription tier"""
        limits = {
            SubscriptionTier.FREE: {
                "api_calls_per_month": 100,
                "backtests_per_day": 5,
                "concurrent_backtests": 1,
                "max_strategies": 2,
                "historical_data_months": 12,
            },
            SubscriptionTier.BASIC: {
                "api_calls_per_month": 1000,
                "backtests_per_day": 50,
                "concurrent_backtests": 3,
                "max_strategies": 10,
                "historical_data_months": 24,
            },
            SubscriptionTier.PRO: {
                "api_calls_per_month": 10000,
                "backtests_per_day": 200,
                "concurrent_backtests": 10,
                "max_strategies": 50,
                "historical_data_months": 60,
            },
            SubscriptionTier.ENTERPRISE: {
                "api_calls_per_month": 100000,
                "backtests_per_day": 1000,
                "concurrent_backtests": 50,
                "max_strategies": 999,
                "historical_data_months": 120,
            },
        }
        return limits.get(self.subscription_tier, limits[SubscriptionTier.FREE])


class APIKey(Base):
    """API keys for programmatic access"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(255), unique=True, index=True, nullable=False)
    key_prefix = Column(String(20), nullable=False)  # sk_live_xxx or sk_test_xxx
    name = Column(String(100), nullable=False)  # User-defined name

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Rate limiting
    calls_today = Column(Integer, default=0)
    calls_this_month = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(key.encode()).hexdigest()

    def is_valid(self) -> bool:
        """Check if API key is valid and not expired"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True


class UsageLog(Base):
    """Log API usage for billing and analytics"""

    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)

    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)

    # Request details
    request_size = Column(Integer, default=0)
    response_size = Column(Integer, default=0)
    processing_time = Column(Float, default=0.0)  # seconds

    # Metadata
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="usage_logs")


class SubscriptionPlan(Base):
    """Available subscription plans"""

    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    tier = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Pricing
    monthly_price = Column(Float, nullable=False)
    yearly_price = Column(Float, nullable=True)
    stripe_price_id = Column(String(100), nullable=True)

    # Features
    api_calls_per_month = Column(Integer, nullable=False)
    backtests_per_day = Column(Integer, nullable=False)
    max_strategies = Column(Integer, nullable=False)
    historical_data_months = Column(Integer, nullable=False)

    # Feature flags
    has_ml_strategies = Column(Boolean, default=False)
    has_portfolio_optimization = Column(Boolean, default=False)
    has_real_time_signals = Column(Boolean, default=False)
    has_api_access = Column(Boolean, default=True)
    has_white_label = Column(Boolean, default=False)
    has_priority_support = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_subscription_plans():
    """Initialize default subscription plans"""
    plans = [
        {
            "tier": "free",
            "name": "Free",
            "description": "Perfect for getting started with algorithmic trading",
            "monthly_price": 0.0,
            "yearly_price": 0.0,
            "api_calls_per_month": 100,
            "backtests_per_day": 5,
            "max_strategies": 2,
            "historical_data_months": 12,
            "has_ml_strategies": False,
            "has_api_access": True,
        },
        {
            "tier": "basic",
            "name": "Basic",
            "description": "For serious traders who want more features",
            "monthly_price": 49.0,
            "yearly_price": 490.0,
            "api_calls_per_month": 1000,
            "backtests_per_day": 50,
            "max_strategies": 10,
            "historical_data_months": 24,
            "has_ml_strategies": True,
            "has_api_access": True,
        },
        {
            "tier": "pro",
            "name": "Professional",
            "description": "Advanced features for professional traders",
            "monthly_price": 199.0,
            "yearly_price": 1990.0,
            "api_calls_per_month": 10000,
            "backtests_per_day": 200,
            "max_strategies": 50,
            "historical_data_months": 60,
            "has_ml_strategies": True,
            "has_portfolio_optimization": True,
            "has_real_time_signals": True,
            "has_priority_support": True,
            "has_api_access": True,
        },
        {
            "tier": "enterprise",
            "name": "Enterprise",
            "description": "Custom solutions for institutions",
            "monthly_price": 999.0,
            "yearly_price": 9990.0,
            "api_calls_per_month": 100000,
            "backtests_per_day": 1000,
            "max_strategies": 999,
            "historical_data_months": 120,
            "has_ml_strategies": True,
            "has_portfolio_optimization": True,
            "has_real_time_signals": True,
            "has_white_label": True,
            "has_priority_support": True,
            "has_api_access": True,
        },
    ]
    return plans


def create_tables(engine):
    """Create all authentication tables"""
    Base.metadata.create_all(bind=engine)
