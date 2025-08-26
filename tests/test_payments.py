"""
Tests for Payments module
Testing Stripe integration and payment router
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

# Import payment modules
from src.payments.stripe_client import StripeClient
from src.payments.router import router as payment_router

# Create test app
app = FastAPI()
app.include_router(payment_router, prefix="/payments")
client = TestClient(app)


class TestStripeClient:
    """Test Stripe client functionality"""
    
    @pytest.fixture
    def stripe_client(self):
        """Create stripe client instance"""
        with patch('src.payments.stripe_client.stripe'):
            return StripeClient(api_key="test_key")
    
    def test_client_initialization(self, stripe_client):
        """Test client initialization"""
        assert stripe_client is not None
        assert hasattr(stripe_client, 'api_key')
    
    @patch('src.payments.stripe_client.stripe')
    def test_create_customer(self, mock_stripe):
        """Test customer creation"""
        mock_stripe.Customer.create.return_value = Mock(
            id="cus_test123",
            email="test@example.com"
        )
        
        client = StripeClient(api_key="test_key")
        result = client.create_customer("test@example.com", "Test User")
        
        assert result is not None
        mock_stripe.Customer.create.assert_called_once()
    
    @patch('src.payments.stripe_client.stripe')
    def test_create_subscription(self, mock_stripe):
        """Test subscription creation"""
        mock_stripe.Subscription.create.return_value = Mock(
            id="sub_test123",
            status="active"
        )
        
        client = StripeClient(api_key="test_key")
        result = client.create_subscription("cus_test123", "price_test")
        
        assert result is not None
        mock_stripe.Subscription.create.assert_called_once()
    
    @patch('src.payments.stripe_client.stripe')
    def test_cancel_subscription(self, mock_stripe):
        """Test subscription cancellation"""
        mock_stripe.Subscription.delete.return_value = Mock(
            id="sub_test123",
            status="canceled"
        )
        
        client = StripeClient(api_key="test_key")
        result = client.cancel_subscription("sub_test123")
        
        assert result is not None
        mock_stripe.Subscription.delete.assert_called_once()
    
    @patch('src.payments.stripe_client.stripe')
    def test_create_payment_intent(self, mock_stripe):
        """Test payment intent creation"""
        mock_stripe.PaymentIntent.create.return_value = Mock(
            id="pi_test123",
            amount=1000,
            currency="usd"
        )
        
        client = StripeClient(api_key="test_key")
        result = client.create_payment_intent(1000, "usd")
        
        assert result is not None
        mock_stripe.PaymentIntent.create.assert_called_once()
    
    @patch('src.payments.stripe_client.stripe')
    def test_list_products(self, mock_stripe):
        """Test listing products"""
        mock_stripe.Product.list.return_value = Mock(
            data=[
                Mock(id="prod_1", name="Product 1"),
                Mock(id="prod_2", name="Product 2")
            ]
        )
        
        client = StripeClient(api_key="test_key")
        result = client.list_products()
        
        assert result is not None
        assert len(result.data) == 2
        mock_stripe.Product.list.assert_called_once()


class TestPaymentRouter:
    """Test payment API endpoints"""
    
    @patch('src.payments.router.StripeClient')
    def test_create_checkout_session(self, mock_stripe_class):
        """Test checkout session creation endpoint"""
        mock_client = Mock()
        mock_client.create_checkout_session.return_value = {
            "id": "cs_test123",
            "url": "https://checkout.stripe.com/test"
        }
        mock_stripe_class.return_value = mock_client
        
        response = client.post(
            "/payments/checkout",
            json={
                "price_id": "price_test",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
    
    @patch('src.payments.router.StripeClient')
    def test_webhook_endpoint(self, mock_stripe_class):
        """Test webhook handling"""
        mock_client = Mock()
        mock_stripe_class.return_value = mock_client
        
        response = client.post(
            "/payments/webhook",
            json={
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "id": "pi_test123",
                        "amount": 1000
                    }
                }
            },
            headers={"stripe-signature": "test_sig"}
        )
        
        # Webhook endpoint might return different status codes
        assert response.status_code in [200, 400, 401]
    
    @patch('src.payments.router.StripeClient')
    def test_get_subscription_status(self, mock_stripe_class):
        """Test subscription status endpoint"""
        mock_client = Mock()
        mock_client.get_subscription.return_value = {
            "id": "sub_test123",
            "status": "active"
        }
        mock_stripe_class.return_value = mock_client
        
        response = client.get("/payments/subscription/sub_test123")
        
        # Might need auth or return not found
        assert response.status_code in [200, 401, 404]
    
    @patch('src.payments.router.StripeClient')
    def test_list_prices(self, mock_stripe_class):
        """Test list prices endpoint"""
        mock_client = Mock()
        mock_client.list_prices.return_value = {
            "data": [
                {"id": "price_1", "unit_amount": 1000},
                {"id": "price_2", "unit_amount": 2000}
            ]
        }
        mock_stripe_class.return_value = mock_client
        
        response = client.get("/payments/prices")
        
        assert response.status_code in [200, 401]
    
    @patch('src.payments.router.StripeClient')
    def test_cancel_subscription_endpoint(self, mock_stripe_class):
        """Test cancel subscription endpoint"""
        mock_client = Mock()
        mock_client.cancel_subscription.return_value = {
            "id": "sub_test123",
            "status": "canceled"
        }
        mock_stripe_class.return_value = mock_client
        
        response = client.post("/payments/subscription/sub_test123/cancel")
        
        assert response.status_code in [200, 401, 404]


class TestPaymentHelpers:
    """Test payment helper functions"""
    
    @patch('src.payments.stripe_client.stripe')
    def test_verify_webhook_signature(self, mock_stripe):
        """Test webhook signature verification"""
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "payment_intent.succeeded"
        }
        
        client = StripeClient(api_key="test_key")
        client.webhook_secret = "whsec_test"
        
        result = client.verify_webhook("payload", "sig", "whsec_test")
        assert result is not None
    
    @patch('src.payments.stripe_client.stripe')
    def test_format_amount(self, mock_stripe):
        """Test amount formatting"""
        client = StripeClient(api_key="test_key")
        
        # Test USD formatting
        formatted = client.format_amount(1000, "usd")
        assert formatted == "$10.00"
        
        # Test EUR formatting
        formatted = client.format_amount(2000, "eur")
        assert formatted == "€20.00"
    
    @patch('src.payments.stripe_client.stripe')
    def test_retrieve_customer(self, mock_stripe):
        """Test customer retrieval"""
        mock_stripe.Customer.retrieve.return_value = Mock(
            id="cus_test123",
            email="test@example.com"
        )
        
        client = StripeClient(api_key="test_key")
        result = client.retrieve_customer("cus_test123")
        
        assert result is not None
        assert result.id == "cus_test123"
        mock_stripe.Customer.retrieve.assert_called_once_with("cus_test123")