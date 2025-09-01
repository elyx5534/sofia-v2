"""
Sofia V2 - Stripe Payment Integration
Handle subscription management, payments, and billing
"""

import stripe
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StripeClient:
    """Stripe payment management client"""
    
    def __init__(self):
        self.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_your_stripe_key_here")
        self.publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_your_stripe_key_here")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_your_webhook_secret")
        
        stripe.api_key = self.api_key
        
        # Product and price IDs (you'll create these in Stripe dashboard)
        self.price_ids = {
            "basic_monthly": os.getenv("STRIPE_BASIC_MONTHLY_PRICE_ID", "price_basic_monthly"),
            "basic_yearly": os.getenv("STRIPE_BASIC_YEARLY_PRICE_ID", "price_basic_yearly"),
            "pro_monthly": os.getenv("STRIPE_PRO_MONTHLY_PRICE_ID", "price_pro_monthly"),
            "pro_yearly": os.getenv("STRIPE_PRO_YEARLY_PRICE_ID", "price_pro_yearly"),
            "enterprise_monthly": os.getenv("STRIPE_ENTERPRISE_MONTHLY_PRICE_ID", "price_enterprise_monthly"),
            "enterprise_yearly": os.getenv("STRIPE_ENTERPRISE_YEARLY_PRICE_ID", "price_enterprise_yearly"),
        }
    
    def create_customer(self, email: str, name: str, user_id: int) -> Dict[str, Any]:
        """Create new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    "user_id": user_id,
                    "platform": "sofia_v2"
                }
            )
            logger.info(f"Created Stripe customer: {customer.id} for user {user_id}")
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise
    
    def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        user_id: int
    ) -> Dict[str, Any]:
        """Create Stripe checkout session for subscription"""
        try:
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": user_id
                },
                allow_promotion_codes=True,  # Allow discount codes
                billing_address_collection='required',
                tax_id_collection={
                    'enabled': True
                }
            )
            logger.info(f"Created checkout session: {checkout_session.id} for user {user_id}")
            return checkout_session
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise
    
    def create_portal_session(self, customer_id: str, return_url: str) -> Dict[str, Any]:
        """Create Stripe customer portal session for subscription management"""
        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            logger.info(f"Created portal session for customer: {customer_id}")
            return portal_session
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            raise
    
    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Get Stripe customer information"""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve customer {customer_id}: {e}")
            raise
    
    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get Stripe subscription information"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
            raise
    
    def list_customer_subscriptions(self, customer_id: str) -> List[Dict[str, Any]]:
        """List all subscriptions for a customer"""
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status='all'
            )
            return subscriptions.data
        except stripe.error.StripeError as e:
            logger.error(f"Failed to list subscriptions for customer {customer_id}: {e}")
            raise
    
    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Dict[str, Any]:
        """Cancel a subscription"""
        try:
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.cancel(subscription_id)
            
            logger.info(f"Cancelled subscription: {subscription_id}")
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            raise
    
    def update_subscription(self, subscription_id: str, new_price_id: str) -> Dict[str, Any]:
        """Update subscription to new price/plan"""
        try:
            # Get current subscription
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update subscription
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0]['id'],
                    'price': new_price_id,
                }],
                proration_behavior='immediate_with_remaining_time'
            )
            
            logger.info(f"Updated subscription {subscription_id} to price {new_price_id}")
            return updated_subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription {subscription_id}: {e}")
            raise
    
    def create_usage_record(self, subscription_item_id: str, quantity: int) -> Dict[str, Any]:
        """Create usage record for metered billing"""
        try:
            usage_record = stripe.UsageRecord.create(
                subscription_item=subscription_item_id,
                quantity=quantity,
                timestamp=int(datetime.utcnow().timestamp()),
                action='increment'
            )
            return usage_record
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create usage record: {e}")
            raise
    
    def construct_webhook_event(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Construct and verify webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            raise
    
    def get_price_info(self, price_id: str) -> Dict[str, Any]:
        """Get price information from Stripe"""
        try:
            price = stripe.Price.retrieve(price_id)
            return {
                "id": price.id,
                "amount": price.unit_amount,
                "currency": price.currency,
                "interval": price.recurring.interval if price.recurring else None,
                "interval_count": price.recurring.interval_count if price.recurring else None,
                "product": price.product
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve price {price_id}: {e}")
            raise
    
    def create_promotional_code(self, coupon_id: str, code: str) -> Dict[str, Any]:
        """Create promotional code"""
        try:
            promo_code = stripe.PromotionCode.create(
                coupon=coupon_id,
                code=code,
                active=True,
                max_redemptions=100
            )
            logger.info(f"Created promotional code: {code}")
            return promo_code
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create promotional code: {e}")
            raise
    
    def get_invoice_preview(self, customer_id: str, subscription_id: str) -> Dict[str, Any]:
        """Get upcoming invoice preview"""
        try:
            upcoming_invoice = stripe.Invoice.upcoming(
                customer=customer_id,
                subscription=subscription_id
            )
            return {
                "amount_due": upcoming_invoice.amount_due,
                "currency": upcoming_invoice.currency,
                "period_start": upcoming_invoice.period_start,
                "period_end": upcoming_invoice.period_end,
                "next_payment_attempt": upcoming_invoice.next_payment_attempt
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get invoice preview: {e}")
            raise


# Global Stripe client instance
stripe_client = StripeClient()


def map_price_id_to_tier(price_id: str) -> str:
    """Map Stripe price ID to subscription tier"""
    price_to_tier = {
        stripe_client.price_ids["basic_monthly"]: "basic",
        stripe_client.price_ids["basic_yearly"]: "basic",
        stripe_client.price_ids["pro_monthly"]: "pro",
        stripe_client.price_ids["pro_yearly"]: "pro",
        stripe_client.price_ids["enterprise_monthly"]: "enterprise",
        stripe_client.price_ids["enterprise_yearly"]: "enterprise",
    }
    return price_to_tier.get(price_id, "free")


def get_price_id_for_tier(tier: str, interval: str) -> Optional[str]:
    """Get Stripe price ID for subscription tier and billing interval"""
    price_map = {
        ("basic", "month"): stripe_client.price_ids["basic_monthly"],
        ("basic", "year"): stripe_client.price_ids["basic_yearly"],
        ("pro", "month"): stripe_client.price_ids["pro_monthly"],
        ("pro", "year"): stripe_client.price_ids["pro_yearly"],
        ("enterprise", "month"): stripe_client.price_ids["enterprise_monthly"],
        ("enterprise", "year"): stripe_client.price_ids["enterprise_yearly"],
    }
    return price_map.get((tier, interval))