"""
Comprehensive tests for scan module to increase coverage
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
from pathlib import Path

@pytest.fixture
def sample_dataframe():
    """Create sample dataframe for testing"""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')
    df = pd.DataFrame({
        'open': np.random.uniform(40000, 50000, 100),
        'high': np.random.uniform(41000, 51000, 100),
        'low': np.random.uniform(39000, 49000, 100),
        'close': np.random.uniform(40000, 50000, 100),
        'volume': np.random.uniform(100, 1000, 100)
    }, index=dates)
    return df

@pytest.fixture
def mock_indicators():
    """Create mock indicators"""
    return {
        'close': 45000,
        'rsi': 35,
        'sma_20': 44000,
        'sma_50': 43000,
        'bb_upper': 46000,
        'bb_lower': 42000,
        'macd': 100,
        'macd_signal': 80,
        'volume': 500,
        'volume_sma': 250,
        'price_change_1h': 2.5,
        'price_change_24h': 5.0
    }

class TestScanRules:
    """Test individual scan rules"""
    
    def test_rsi_rebound_rule(self, sample_dataframe, mock_indicators):
        """Test RSI rebound rule"""
        from src.scan.rules import RSIReboundRule
        
        rule = RSIReboundRule(oversold_threshold=30)
        
        # Test with oversold RSI
        mock_indicators['rsi'] = 35
        result = rule.evaluate(sample_dataframe, mock_indicators)
        
        assert 'signal' in result
        assert 'message' in result
        assert result['signal'] >= 0
    
    def test_sma_cross_rule(self, sample_dataframe, mock_indicators):
        """Test SMA crossover rule"""
        from src.scan.rules import SMACrossRule
        
        rule = SMACrossRule(fast_period=20, slow_period=50)
        
        # Add SMA columns to dataframe
        sample_dataframe['sma_20'] = sample_dataframe['close'].rolling(20).mean()
        sample_dataframe['sma_50'] = sample_dataframe['close'].rolling(50).mean()
        
        result = rule.evaluate(sample_dataframe, mock_indicators)
        
        assert 'signal' in result
        assert 'message' in result
        assert result['signal'] >= 0
    
    def test_bollinger_bands_bounce_rule(self, sample_dataframe, mock_indicators):
        """Test Bollinger Bands bounce rule"""
        from src.scan.rules import BollingerBandsBounceRule
        
        rule = BollingerBandsBounceRule(touch_threshold=0.02)
        
        # Add BB columns
        sma = sample_dataframe['close'].rolling(20).mean()
        std = sample_dataframe['close'].rolling(20).std()
        sample_dataframe['bb_upper'] = sma + (2 * std)
        sample_dataframe['bb_lower'] = sma - (2 * std)
        
        result = rule.evaluate(sample_dataframe, mock_indicators)
        
        assert 'signal' in result
        assert 'message' in result
        assert result['signal'] >= 0
    
    def test_volume_breakout_rule(self, sample_dataframe, mock_indicators):
        """Test volume breakout rule"""
        from src.scan.rules import VolumeBreakoutRule
        
        rule = VolumeBreakoutRule(volume_multiplier=2.0)
        
        # Add volume SMA
        sample_dataframe['volume_sma'] = sample_dataframe['volume'].rolling(20).mean()
        
        # Test with high volume
        mock_indicators['volume'] = 600
        mock_indicators['volume_sma'] = 250
        
        result = rule.evaluate(sample_dataframe, mock_indicators)
        
        assert 'signal' in result
        assert 'message' in result
        assert result['signal'] > 0  # Should have signal with 2.4x volume
    
    def test_macd_signal_rule(self, sample_dataframe, mock_indicators):
        """Test MACD signal rule"""
        from src.scan.rules import MACDSignalRule
        
        rule = MACDSignalRule()
        
        # Add MACD columns
        exp1 = sample_dataframe['close'].ewm(span=12, adjust=False).mean()
        exp2 = sample_dataframe['close'].ewm(span=26, adjust=False).mean()
        sample_dataframe['macd'] = exp1 - exp2
        sample_dataframe['macd_signal'] = sample_dataframe['macd'].ewm(span=9, adjust=False).mean()
        
        result = rule.evaluate(sample_dataframe, mock_indicators)
        
        assert 'signal' in result
        assert 'message' in result
        assert result['signal'] >= 0
    
    def test_price_action_rule(self, sample_dataframe, mock_indicators):
        """Test price action rule"""
        from src.scan.rules import PriceActionRule
        
        rule = PriceActionRule()
        
        # Test with positive momentum
        mock_indicators['price_change_1h'] = 6.0
        mock_indicators['price_change_24h'] = 10.0
        
        result = rule.evaluate(sample_dataframe, mock_indicators)
        
        assert 'signal' in result
        assert 'message' in result
        assert result['signal'] > 0  # Should have signal with good momentum

class TestSignalScanner:
    """Test SignalScanner class"""
    
    @patch('src.scan.scanner.data_pipeline')
    def test_scanner_initialization(self, mock_pipeline):
        """Test scanner initialization"""
        from src.scan.scanner import SignalScanner
        
        scanner = SignalScanner(outputs_dir="./test_outputs")
        
        assert scanner is not None
        assert len(scanner.rules) > 0
        assert scanner.outputs_dir.exists()
    
    @patch('src.scan.scanner.data_pipeline.get_symbol_data')
    @patch('src.scan.scanner.get_latest_indicators')
    def test_scan_symbol(self, mock_indicators, mock_get_data, sample_dataframe):
        """Test scanning single symbol"""
        from src.scan.scanner import SignalScanner
        
        mock_get_data.return_value = sample_dataframe
        mock_indicators.return_value = {
            'close': 45000,
            'rsi': 35,
            'sma_20': 44000,
            'sma_50': 43000,
            'volume': 500
        }
        
        scanner = SignalScanner()
        result = scanner.scan_symbol("BTC-USD", "1h")
        
        assert result is not None
        assert result['symbol'] == "BTC-USD"
        assert 'score' in result
        assert 'signals' in result
        assert 'indicators' in result
    
    @patch('src.scan.scanner.data_pipeline.get_symbol_data')
    def test_scan_symbol_insufficient_data(self, mock_get_data):
        """Test scanning with insufficient data"""
        from src.scan.scanner import SignalScanner
        
        # Return empty dataframe
        mock_get_data.return_value = pd.DataFrame()
        
        scanner = SignalScanner()
        result = scanner.scan_symbol("BTC-USD", "1h")
        
        assert result['symbol'] == "BTC-USD"
        assert result['score'] == 0
        assert result['error'] == 'Insufficient data'
    
    @patch('src.scan.scanner.data_pipeline.get_available_symbols')
    @patch('src.scan.scanner.SignalScanner.scan_symbol')
    def test_scan_all_symbols(self, mock_scan_symbol, mock_get_symbols):
        """Test scanning all symbols"""
        from src.scan.scanner import SignalScanner
        
        mock_get_symbols.return_value = ["BTC-USD", "ETH-USD", "SOL-USD"]
        mock_scan_symbol.return_value = {
            'symbol': 'BTC-USD',
            'score': 2.5,
            'signals': []
        }
        
        scanner = SignalScanner()
        results = scanner.scan_all_symbols(timeframe="1h", max_workers=2)
        
        assert len(results) == 3
        assert mock_scan_symbol.call_count == 3
    
    def test_get_top_signals(self):
        """Test getting top signals"""
        from src.scan.scanner import SignalScanner
        
        results = [
            {'symbol': 'BTC-USD', 'score': 3.0},
            {'symbol': 'ETH-USD', 'score': 2.0},
            {'symbol': 'SOL-USD', 'score': 0.3},
            {'symbol': 'ADA-USD', 'score': 1.5}
        ]
        
        scanner = SignalScanner()
        top = scanner.get_top_signals(results, limit=2)
        
        assert len(top) == 2
        assert top[0]['symbol'] == 'BTC-USD'
        assert top[1]['symbol'] == 'ETH-USD'
    
    def test_save_results(self, tmp_path):
        """Test saving scan results"""
        from src.scan.scanner import SignalScanner
        
        results = [
            {
                'symbol': 'BTC-USD',
                'score': 2.5,
                'signals': [{'message': 'Test signal'}],
                'indicators': {'close': 45000, 'rsi': 35},
                'timestamp': datetime.now().isoformat()
            }
        ]
        
        scanner = SignalScanner(outputs_dir=str(tmp_path))
        scanner.save_results(results, filename="test_scan")
        
        # Check JSON file
        json_file = tmp_path / "test_scan.json"
        assert json_file.exists()
        
        with open(json_file) as f:
            saved_data = json.load(f)
        assert len(saved_data) == 1
        assert saved_data[0]['symbol'] == 'BTC-USD'
        
        # Check CSV file
        csv_file = tmp_path / "test_scan.csv"
        assert csv_file.exists()
    
    def test_save_signals_json(self, tmp_path):
        """Test saving signals JSON"""
        from src.scan.scanner import SignalScanner
        
        results = [
            {'symbol': 'BTC-USD', 'score': 3.0, 'signals': [], 'indicators': {}},
            {'symbol': 'ETH-USD', 'score': 2.0, 'signals': [], 'indicators': {}},
            {'symbol': 'SOL-USD', 'score': 0.3, 'signals': [], 'indicators': {}}
        ]
        
        scanner = SignalScanner(outputs_dir=str(tmp_path))
        scanner.save_signals_json(results)
        
        signals_file = tmp_path / "signals.json"
        assert signals_file.exists()
        
        with open(signals_file) as f:
            signals = json.load(f)
        
        # Only high score signals should be saved
        assert len(signals) == 2
        assert signals[0]['symbol'] == 'BTC-USD'
    
    @patch('src.scan.scanner.SignalScanner.scan_all_symbols')
    @patch('src.scan.scanner.SignalScanner.save_results')
    @patch('src.scan.scanner.SignalScanner.save_signals_json')
    def test_run_scan(self, mock_save_signals, mock_save_results, mock_scan_all):
        """Test complete scan run"""
        from src.scan.scanner import SignalScanner
        
        mock_scan_all.return_value = [
            {'symbol': 'BTC-USD', 'score': 2.5},
            {'symbol': 'ETH-USD', 'score': 1.5}
        ]
        
        scanner = SignalScanner()
        results = scanner.run_scan(timeframe="1h", save_results=True)
        
        assert len(results) == 2
        assert mock_scan_all.called
        assert mock_save_results.called
        assert mock_save_signals.called

class TestScannerIntegration:
    """Integration tests for scanner"""
    
    @patch('src.scan.scanner.data_pipeline')
    def test_scanner_with_real_rules(self, mock_pipeline, sample_dataframe):
        """Test scanner with real rules"""
        from src.scan.scanner import SignalScanner
        from src.scan.rules import DEFAULT_RULES
        
        mock_pipeline.get_symbol_data.return_value = sample_dataframe
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD"]
        
        scanner = SignalScanner(rules=DEFAULT_RULES)
        
        # Mock indicators calculation
        with patch('src.scan.scanner.get_latest_indicators') as mock_ind:
            mock_ind.return_value = {
                'close': 45000,
                'rsi': 28,  # Oversold
                'sma_20': 44000,
                'sma_50': 43000,
                'bb_upper': 46000,
                'bb_lower': 42000,
                'macd': 100,
                'macd_signal': 80,
                'volume': 600,
                'volume_sma': 250,
                'price_change_1h': 6.0,
                'price_change_24h': 10.0
            }
            
            result = scanner.scan_symbol("BTC-USD", "1h")
            
            assert result['symbol'] == "BTC-USD"
            assert result['score'] > 0  # Should have signals
            assert len(result['signals']) > 0
    
    def test_scanner_error_handling(self):
        """Test scanner error handling"""
        from src.scan.scanner import SignalScanner
        
        scanner = SignalScanner()
        
        # Test with exception during scan
        with patch('src.scan.scanner.data_pipeline.get_symbol_data') as mock_get:
            mock_get.side_effect = Exception("Data fetch error")
            
            result = scanner.scan_symbol("BTC-USD", "1h")
            
            assert result['symbol'] == "BTC-USD"
            assert result['score'] == 0
            assert 'error' in result
            assert "Data fetch error" in result['error']