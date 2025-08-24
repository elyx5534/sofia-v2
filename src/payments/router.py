"""
Sofia V2 - Payment Router
FastAPI routes for subscription management and payments
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import logging

from .stripe_client import stripe_client, map_price_id_to_tier, get_price_id_for_tier
from ..auth.models import User, SubscriptionTier
from ..auth.dependencies import get_current_active_user
from ..data_hub.models import get_db
from pydantic import BaseModel


router = APIRouter(prefix="/payments", tags=["Payments"])
logger = logging.getLogger(__name__)


# Pydantic models
class CheckoutRequest(BaseModel):
    price_tier: str  # basic, pro, enterprise
    billing_interval: str  # month, year


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionInfo(BaseModel):
    tier: str
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    next_invoice_date: Optional[datetime]
    amount: Optional[int]
    currency: Optional[str]


@router.post("/create-checkout-session", response_model=CheckoutResponse)
async def create_checkout_session(
    checkout_request: CheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create Stripe checkout session for subscription upgrade"""
    
    # Validate tier and interval
    if checkout_request.price_tier not in ["basic", "pro", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription tier"
        )
    
    if checkout_request.billing_interval not in ["month", "year"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid billing interval"
        )
    
    # Get Stripe price ID
    price_id = get_price_id_for_tier(checkout_request.price_tier, checkout_request.billing_interval)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Price not found for specified tier and interval"
        )
    
    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe_client.create_customer(
                email=current_user.email,
                name=current_user.full_name or current_user.username,
                user_id=current_user.id
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        
        # Create checkout session
        checkout_session = stripe_client.create_checkout_session(
            customer_id=current_user.stripe_customer_id,
            price_id=price_id,
            success_url="http://localhost:8000/subscription/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:8000/subscription/cancel",
            user_id=current_user.id
        )
        
        return CheckoutResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )
        
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.post("/create-portal-session")
async def create_portal_session(
    current_user: User = Depends(get_current_active_user),
):
    """Create Stripe customer portal session for subscription management"""
    
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found. Please subscribe first."
        )
    
    try:
        portal_session = stripe_client.create_portal_session(
            customer_id=current_user.stripe_customer_id,
            return_url="http://localhost:8000/dashboard"
        )
        
        return {"portal_url": portal_session.url}
        
    except Exception as e:
        logger.error(f"Failed to create portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session"
        )


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription_info(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user's subscription information"""
    
    if not current_user.stripe_customer_id:
        return SubscriptionInfo(
            tier="free",
            status="active",
            current_period_start=None,
            current_period_end=None,
            cancel_at_period_end=False,
            next_invoice_date=None,
            amount=None,
            currency=None
        )
    
    try:
        # Get customer's active subscriptions
        subscriptions = stripe_client.list_customer_subscriptions(current_user.stripe_customer_id)
        
        if not subscriptions:
            return SubscriptionInfo(
                tier="free",
                status="active",
                current_period_start=None,
                current_period_end=None,
                cancel_at_period_end=False,
                next_invoice_date=None,
                amount=None,
                currency=None
            )
        
        # Get the most recent active subscription
        subscription = subscriptions[0]
        
        # Map Stripe price to tier
        price_id = subscription.items.data[0].price.id
        tier = map_price_id_to_tier(price_id)
        
        return SubscriptionInfo(
            tier=tier,
            status=subscription.status,
            current_period_start=datetime.fromtimestamp(subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            cancel_at_period_end=subscription.cancel_at_period_end,
            next_invoice_date=datetime.fromtimestamp(subscription.current_period_end),
            amount=subscription.items.data[0].price.unit_amount,
            currency=subscription.items.data[0].price.currency
        )
        
    except Exception as e:
        logger.error(f"Failed to get subscription info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription information"
        )


@router.get("/pricing")
async def get_pricing_plans():
    """Get available pricing plans"""
    
    plans = [
        {
            "tier": "free",
            "name": "Free",
            "description": "Perfect for getting started",
            "monthly_price": 0,
            "yearly_price": 0,
            "features": [
                "100 API calls/month",
                "5 backtests/day",
                "2 strategies",
                "12 months historical data",
                "Basic support"
            ],
            "popular": False
        },
        {
            "tier": "basic",
            "name": "Basic",
            "description": "For serious traders",
            "monthly_price": 49,
            "yearly_price": 490,  # 2 months free
            "features": [
                "1,000 API calls/month",
                "50 backtests/day",
                "10 strategies",
                "24 months historical data",
                "ML-powered strategies",
                "Email support"
            ],
            "popular": True
        },
        {
            "tier": "pro",
            "name": "Professional",
            "description": "Advanced features for professionals",
            "monthly_price": 199,
            "yearly_price": 1990,  # 2 months free
            "features": [
                "10,000 API calls/month",
                "200 backtests/day",
                "50 strategies",
                "5 years historical data",
                "Portfolio optimization",
                "Real-time signals",
                "Priority support",
                "Advanced analytics"
            ],
            "popular": False
        },
        {
            "tier": "enterprise",
            "name": "Enterprise",
            "description": "Custom solutions for institutions",
            "monthly_price": 999,
            "yearly_price": 9990,  # 2 months free
            "features": [
                "100,000 API calls/month",
                "1,000 backtests/day",
                "Unlimited strategies",
                "10 years historical data",
                "White-label solutions",
                "Custom integrations",
                "Dedicated support",
                "SLA guarantee"
            ],
            "popular": False
        }
    ]
    
    return {"plans": plans}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhooks for subscription events"""
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature"
        )
    
    try:
        event = stripe_client.construct_webhook_event(payload, sig_header)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )
    
    # Handle different webhook events
    if event["type"] == "checkout.session.completed":
        await handle_checkout_completed(event["data"]["object"], db)
    
    elif event["type"] == "customer.subscription.updated":
        await handle_subscription_updated(event["data"]["object"], db)
    
    elif event["type"] == "customer.subscription.deleted":
        await handle_subscription_deleted(event["data"]["object"], db)
    
    elif event["type"] == "invoice.payment_succeeded":
        await handle_payment_succeeded(event["data"]["object"], db)
    
    elif event["type"] == "invoice.payment_failed":
        await handle_payment_failed(event["data"]["object"], db)
    
    return {"status": "success"}


async def handle_checkout_completed(session, db: Session):
    """Handle successful checkout completion"""
    user_id = session.get("metadata", {}).get("user_id")
    if not user_id:
        logger.error("No user_id in checkout session metadata")
        return
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        logger.error(f"User {user_id} not found")
        return
    
    # Get subscription from session
    subscription_id = session.get("subscription")
    if subscription_id:
        try:
            subscription = stripe_client.get_subscription(subscription_id)
            
            # Update user subscription
            price_id = subscription.items.data[0].price.id
            tier = map_price_id_to_tier(price_id)
            
            user.subscription_tier = tier
            user.subscription_active = True
            user.subscription_expires = datetime.fromtimestamp(subscription.current_period_end)
            
            db.commit()
            logger.info(f"Updated user {user_id} subscription to {tier}")
            
        except Exception as e:
            logger.error(f"Failed to update subscription for user {user_id}: {e}")


async def handle_subscription_updated(subscription, db: Session):
    """Handle subscription updates (plan changes, renewals)"""
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.error(f"User with Stripe customer {customer_id} not found")
        return
    
    # Update subscription info
    price_id = subscription["items"]["data"][0]["price"]["id"]
    tier = map_price_id_to_tier(price_id)
    
    user.subscription_tier = tier
    user.subscription_active = subscription["status"] == "active"
    user.subscription_expires = datetime.fromtimestamp(subscription["current_period_end"])
    
    db.commit()
    logger.info(f"Updated subscription for user {user.id} to {tier}")


async def handle_subscription_deleted(subscription, db: Session):
    """Handle subscription cancellation"""
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.error(f"User with Stripe customer {customer_id} not found")
        return
    
    # Downgrade to free tier
    user.subscription_tier = SubscriptionTier.FREE
    user.subscription_active = True  # Free tier is always active
    user.subscription_expires = None
    
    db.commit()
    logger.info(f"Downgraded user {user.id} to free tier")


async def handle_payment_succeeded(invoice, db: Session):
    """Handle successful payment"""
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        logger.info(f"Payment succeeded for user {user.id}")
        # You can add additional logic here (send confirmation email, etc.)


async def handle_payment_failed(invoice, db: Session):
    """Handle failed payment"""
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        logger.warning(f"Payment failed for user {user.id}")
        # You can add logic here (send notification, grace period, etc.)