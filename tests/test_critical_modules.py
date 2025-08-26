"""
Critical module tests with full mocking to increase coverage to 70%
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, create_autospec
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

class TestAuthDependenciesFull:
    """Full coverage tests for auth dependencies"""
    
    @patch('src.auth.dependencies.jwt')
    @patch('src.auth.dependencies.get_db')
    def test_verify_token_success(self, mock_get_db, mock_jwt):
        """Test successful token verification"""
        from src.auth.dependencies import verify_token
        
        mock_jwt.decode.return_value = {"sub": "testuser", "exp": datetime.utcnow() + timedelta(hours=1)}
        
        result = verify_token("valid_token")
        assert result is not None
        assert result["sub"] == "testuser"
    
    @patch('src.auth.dependencies.jwt')
    def test_verify_token_expired(self, mock_jwt):
        """Test expired token"""
        from src.auth.dependencies import verify_token
        
        mock_jwt.decode.side_effect = jwt.ExpiredSignatureError()
        
        result = verify_token("expired_token")
        assert result is None
    
    @patch('src.auth.dependencies.oauth2_scheme')
    def test_get_current_user_no_credentials(self, mock_oauth):
        """Test get current user without credentials"""
        from src.auth.dependencies import get_current_user
        from fastapi import HTTPException
        
        mock_oauth.return_value = None
        
        with pytest.raises(HTTPException):
            get_current_user(None, MagicMock())

class TestAuthRouterFull:
    """Full coverage tests for auth router"""
    
    @patch('src.auth.router.get_password_hash')
    @patch('src.auth.router.get_db')
    def test_register_duplicate_user(self, mock_get_db, mock_hash):
        """Test registering duplicate user"""
        from src.auth.router import register
        from fastapi import HTTPException
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # User already exists
        mock_db.query().filter().first.return_value = MagicMock()
        
        with pytest.raises(HTTPException) as exc:
            register({"username": "existing", "email": "test@test.com", "password": "pass"}, mock_db)
        
        assert exc.value.status_code == 400
    
    @patch('src.auth.router.verify_password')
    @patch('src.auth.router.get_db')
    def test_login_invalid_password(self, mock_get_db, mock_verify):
        """Test login with invalid password"""
        from src.auth.router import login
        from fastapi import HTTPException
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_verify.return_value = False
        
        # User exists but password wrong
        mock_db.query().filter().first.return_value = MagicMock()
        
        with pytest.raises(HTTPException) as exc:
            login(MagicMock(username="test", password="wrong"), mock_db)
        
        assert exc.value.status_code == 401

class TestPaymentsFull:
    """Full coverage tests for payments"""
    
    @patch('src.payments.stripe_client.stripe.Customer.create')
    def test_create_customer_error(self, mock_create):
        """Test customer creation error"""
        from src.payments.stripe_client import StripeClient
        import stripe
        
        mock_create.side_effect = stripe.error.StripeError("API Error")
        
        client = StripeClient()
        with pytest.raises(stripe.error.StripeError):
            client.create_customer("test@test.com", "Test User", 1)
    
    @patch('src.payments.stripe_client.stripe.Subscription.modify')
    def test_cancel_subscription_at_period_end(self, mock_modify):
        """Test cancelling subscription at period end"""
        from src.payments.stripe_client import StripeClient
        
        mock_modify.return_value = {"id": "sub_123", "cancel_at_period_end": True}
        
        client = StripeClient()
        result = client.cancel_subscription("sub_123", at_period_end=True)
        
        assert result["cancel_at_period_end"] is True
        mock_modify.assert_called_once()
    
    @patch('src.payments.stripe_client.stripe.Subscription.list')
    def test_list_customer_subscriptions_error(self, mock_list):
        """Test listing subscriptions error"""
        from src.payments.stripe_client import StripeClient
        import stripe
        
        mock_list.side_effect = stripe.error.StripeError("API Error")
        
        client = StripeClient()
        with pytest.raises(stripe.error.StripeError):
            client.list_customer_subscriptions("cus_123")

class TestSchedulerFull:
    """Full coverage tests for scheduler"""
    
    @patch('src.scheduler.run.schedule')
    def test_scheduler_init(self, mock_schedule):
        """Test scheduler initialization"""
        from src.scheduler.run import CryptoScheduler
        
        scheduler = CryptoScheduler()
        assert scheduler is not None
        assert scheduler.running is False
    
    @patch('src.scheduler.run.schedule')
    @patch('src.scheduler.run.threading.Thread')
    def test_start_scheduler(self, mock_thread, mock_schedule):
        """Test starting scheduler"""
        from src.scheduler.run import CryptoScheduler
        
        scheduler = CryptoScheduler()
        scheduler.start()
        
        assert scheduler.running is True
        mock_thread.assert_called_once()
    
    @patch('src.scheduler.run.schedule')
    def test_stop_scheduler(self, mock_schedule):
        """Test stopping scheduler"""
        from src.scheduler.run import CryptoScheduler
        
        scheduler = CryptoScheduler()
        scheduler.running = True
        scheduler.stop()
        
        assert scheduler.running is False
    
    @patch('src.scheduler.run.SCHEDULED_JOBS')
    def test_run_job(self, mock_jobs):
        """Test running a job"""
        from src.scheduler.run import CryptoScheduler
        
        mock_job = MagicMock(return_value={"status": "success"})
        mock_jobs.__getitem__.return_value = mock_job
        
        scheduler = CryptoScheduler()
        result = scheduler.run_job("test_job")
        
        assert result["status"] == "success"
    
    @patch('src.scheduler.run.schedule')
    def test_add_job(self, mock_schedule):
        """Test adding a job"""
        from src.scheduler.run import CryptoScheduler
        
        scheduler = CryptoScheduler()
        scheduler.add_job("test_job", "10:00", lambda: None)
        
        assert "test_job" in scheduler.jobs

class TestScannerFull:
    """Full coverage tests for scanner"""
    
    @patch('src.scan.scanner.Path')
    def test_scanner_outputs_dir_creation(self, mock_path):
        """Test scanner creates outputs directory"""
        from src.scan.scanner import SignalScanner
        
        mock_dir = MagicMock()
        mock_path.return_value = mock_dir
        
        scanner = SignalScanner(outputs_dir="./test")
        mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    @patch('src.scan.scanner.data_pipeline.get_symbol_data')
    def test_scan_symbol_error_handling(self, mock_get_data):
        """Test scan symbol error handling"""
        from src.scan.scanner import SignalScanner
        
        mock_get_data.side_effect = Exception("Data error")
        
        scanner = SignalScanner()
        result = scanner.scan_symbol("BTC-USD", "1h")
        
        assert result["symbol"] == "BTC-USD"
        assert result["score"] == 0
        assert "error" in result
    
    @patch('src.scan.scanner.data_pipeline.get_available_symbols')
    def test_scan_all_no_symbols(self, mock_get_symbols):
        """Test scanning with no symbols available"""
        from src.scan.scanner import SignalScanner
        
        mock_get_symbols.return_value = []
        
        scanner = SignalScanner()
        results = scanner.scan_all_symbols()
        
        assert results == []

class TestDataPipelineFull:
    """Full coverage tests for data pipeline"""
    
    @patch('src.data.pipeline.ccxt')
    def test_fetch_ohlcv_error(self, mock_ccxt):
        """Test OHLCV fetch error"""
        from src.data.pipeline import DataPipeline
        
        mock_exchange = MagicMock()
        mock_ccxt.binance.return_value = mock_exchange
        mock_exchange.fetch_ohlcv.side_effect = Exception("Network error")
        
        pipeline = DataPipeline()
        
        with pytest.raises(Exception):
            pipeline.fetch_ohlcv("BTC/USDT", "1h")
    
    @patch('src.data.pipeline.pd.read_parquet')
    def test_load_cached_data(self, mock_read):
        """Test loading cached data"""
        from src.data.pipeline import DataPipeline
        
        mock_df = pd.DataFrame({"close": [45000, 46000]})
        mock_read.return_value = mock_df
        
        pipeline = DataPipeline()
        df = pipeline.load_cached_data("BTC-USD", "1h")
        
        assert df is not None
        assert len(df) == 2
    
    def test_save_to_parquet(self, tmp_path):
        """Test saving data to parquet"""
        from src.data.pipeline import DataPipeline
        
        df = pd.DataFrame({"close": [45000, 46000]})
        
        pipeline = DataPipeline(data_dir=str(tmp_path))
        pipeline.save_to_parquet(df, "BTC-USD", "1h")
        
        saved_file = tmp_path / "BTC-USD_1h.parquet"
        assert saved_file.exists()

class TestExchangesFull:
    """Full coverage tests for exchanges"""
    
    @patch('src.data.exchanges.ccxt')
    def test_init_exchange_error(self, mock_ccxt):
        """Test exchange initialization error"""
        from src.data.exchanges import ExchangeManager
        
        mock_ccxt.binance.side_effect = Exception("Init error")
        
        manager = ExchangeManager()
        
        with pytest.raises(Exception):
            manager.init_exchange("binance")
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_fetch_trades(self, mock_binance):
        """Test fetching trades"""
        from src.data.exchanges import ExchangeManager
        
        mock_exchange = MagicMock()
        mock_binance.return_value = mock_exchange
        mock_exchange.fetch_trades.return_value = [
            {"price": 45000, "amount": 0.1, "timestamp": 1234567890}
        ]
        
        manager = ExchangeManager()
        trades = manager.fetch_trades("binance", "BTC/USDT")
        
        assert len(trades) == 1
        assert trades[0]["price"] == 45000
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_fetch_balance(self, mock_binance):
        """Test fetching balance"""
        from src.data.exchanges import ExchangeManager
        
        mock_exchange = MagicMock()
        mock_binance.return_value = mock_exchange
        mock_exchange.fetch_balance.return_value = {
            "BTC": {"free": 1.0, "used": 0.5, "total": 1.5},
            "USDT": {"free": 10000, "used": 0, "total": 10000}
        }
        
        manager = ExchangeManager()
        balance = manager.fetch_balance("binance")
        
        assert "BTC" in balance
        assert balance["BTC"]["total"] == 1.5

class TestNewsFull:
    """Full coverage tests for news modules"""
    
    @patch('src.news.cryptopanic.aiohttp.ClientSession')
    async def test_fetch_news_rate_limit(self, mock_session):
        """Test news fetch with rate limiting"""
        from src.news.cryptopanic import CryptoPanicClient
        
        mock_response = MagicMock()
        mock_response.status = 429  # Rate limited
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        client = CryptoPanicClient("test_key")
        news = await client.fetch_news()
        
        assert news == []
    
    @patch('src.news.gdelt.aiohttp.ClientSession')
    async def test_gdelt_parse_response(self, mock_session):
        """Test GDELT response parsing"""
        from src.news.gdelt import GDELTClient
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text.return_value = "Article 1\\tURL1\\t20240101T120000\\nArticle 2\\tURL2\\t20240101T130000"
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        client = GDELTClient()
        articles = await client.parse_gdelt_response(mock_response)
        
        assert len(articles) == 2