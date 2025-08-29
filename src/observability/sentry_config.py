"""
Sentry Configuration with Trading Flow Scope
"""

import os
import re
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.scrubber import EventScrubber
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


class TradingScopeScrubber:
    """Custom scrubber for trading-specific PII"""
    
    # Patterns to scrub
    PII_PATTERNS = [
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'s]+)', 'API_KEY_REDACTED'),
        (r'api[_-]?secret["\']?\s*[:=]\s*["\']?([^"\'s]+)', 'API_SECRET_REDACTED'),
        (r'password["\']?\s*[:=]\s*["\']?([^"\'s]+)', 'PASSWORD_REDACTED'),
        (r'token["\']?\s*[:=]\s*["\']?([^"\'s]+)', 'TOKEN_REDACTED'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL_REDACTED'),
        (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 'CARD_REDACTED'),
        (r'client[_-]?order[_-]?id["\']?\s*[:=]\s*["\']?([^"\'s]+)', 'ORDER_ID_REDACTED'),
    ]
    
    @classmethod
    def scrub_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively scrub sensitive data from dictionary"""
        if not isinstance(data, dict):
            return data
            
        scrubbed = {}
        for key, value in data.items():
            # Scrub keys
            if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'token', 'api_key']):
                scrubbed[key] = '[REDACTED]'
            elif isinstance(value, dict):
                scrubbed[key] = cls.scrub_dict(value)
            elif isinstance(value, list):
                scrubbed[key] = [cls.scrub_dict(item) if isinstance(item, dict) else item for item in value]
            elif isinstance(value, str):
                scrubbed[key] = cls.scrub_string(value)
            else:
                scrubbed[key] = value
                
        return scrubbed
    
    @classmethod
    def scrub_string(cls, text: str) -> str:
        """Scrub sensitive patterns from string"""
        for pattern, replacement in cls.PII_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text


def before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process event before sending to Sentry"""
    
    # Add trading context
    if 'contexts' not in event:
        event['contexts'] = {}
    
    event['contexts']['trading_flow'] = {
        'mode': os.getenv('TRADING_MODE', 'unknown'),
        'exchange': os.getenv('EXCHANGE', 'unknown'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'kill_switch': os.getenv('KILL_SWITCH', 'OFF'),
        'timestamp': datetime.now().isoformat()
    }
    
    # Scrub PII
    event = TradingScopeScrubber.scrub_dict(event)
    
    # Add fingerprinting for better grouping
    if 'exception' in event:
        exception = event['exception']['values'][0] if event['exception']['values'] else None
        if exception:
            # Group by exception type and key context
            fingerprint = [
                exception.get('type', 'unknown'),
                event.get('contexts', {}).get('trading_flow', {}).get('mode', 'unknown')
            ]
            
            # Add specific fingerprints for known issues
            if 'RateLimitExceeded' in str(exception.get('type', '')):
                fingerprint.append('rate_limit')
            elif 'OrderNotFound' in str(exception.get('type', '')):
                fingerprint.append('order_not_found')
            elif 'InsufficientBalance' in str(exception.get('type', '')):
                fingerprint.append('insufficient_balance')
                
            event['fingerprint'] = fingerprint
    
    return event


def init_sentry():
    """Initialize Sentry with trading-specific configuration"""
    if not SENTRY_AVAILABLE:
        print("Sentry SDK not installed")
        return False
        
    dsn = os.getenv('SENTRY_DSN')
    if not dsn:
        print("SENTRY_DSN not configured")
        return False
    
    try:
        # Configure integrations
        integrations = [
            LoggingIntegration(
                level=10,  # DEBUG
                event_level=40  # ERROR
            )
        ]
        
        # Add SQLAlchemy if available
        try:
            integrations.append(SqlalchemyIntegration())
        except:
            pass
        
        # Initialize Sentry
        sentry_sdk.init(
            dsn=dsn,
            integrations=integrations,
            
            # Performance monitoring
            traces_sample_rate=get_sample_rate(),
            profiles_sample_rate=get_sample_rate(),
            
            # Error sampling
            sample_rate=1.0,
            
            # Release tracking
            release=os.getenv('RELEASE_VERSION', 'v0.2.0'),
            environment=os.getenv('ENVIRONMENT', 'development'),
            
            # Server name
            server_name=os.getenv('SERVER_NAME', 'sofia-trading'),
            
            # Event processing
            before_send=before_send,
            
            # Breadcrumbs
            max_breadcrumbs=50,
            
            # Request bodies
            request_bodies='medium',
            
            # Shutdown
            shutdown_timeout=5,
            
            # Debug
            debug=os.getenv('SENTRY_DEBUG', 'false').lower() == 'true'
        )
        
        # Set initial scope
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("trading.mode", os.getenv('TRADING_MODE', 'unknown'))
            scope.set_tag("trading.exchange", os.getenv('EXCHANGE', 'unknown'))
            scope.set_tag("trading.environment", os.getenv('ENVIRONMENT', 'development'))
            scope.set_context("trading_config", {
                "max_daily_loss": os.getenv('MAX_DAILY_LOSS'),
                "max_position_usd": os.getenv('MAX_POSITION_USD'),
                "kill_switch": os.getenv('KILL_SWITCH')
            })
        
        print(f"Sentry initialized: {os.getenv('ENVIRONMENT')} / {os.getenv('RELEASE_VERSION')}")
        return True
        
    except Exception as e:
        print(f"Failed to initialize Sentry: {e}")
        return False


def get_sample_rate() -> float:
    """Get sampling rate based on environment"""
    env = os.getenv('ENVIRONMENT', 'development')
    
    if env == 'production':
        return 0.1  # 10% in production
    elif env == 'staging':
        return 0.5  # 50% in staging
    else:
        return 1.0  # 100% in development


def capture_trading_event(
    event_type: str,
    data: Dict[str, Any],
    level: str = "info"
):
    """Capture trading-specific event"""
    if not SENTRY_AVAILABLE:
        return
        
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("event.type", event_type)
        scope.set_context("event_data", TradingScopeScrubber.scrub_dict(data))
        
        message = f"Trading Event: {event_type}"
        
        if level == "error":
            sentry_sdk.capture_message(message, level="error")
        elif level == "warning":
            sentry_sdk.capture_message(message, level="warning")
        else:
            sentry_sdk.capture_message(message, level="info")


def capture_order_event(order: Dict[str, Any], event: str):
    """Capture order lifecycle event"""
    capture_trading_event(
        f"order.{event}",
        {
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "type": order.get("type"),
            "quantity": order.get("quantity"),
            "status": order.get("status")
        }
    )


def capture_risk_event(check: str, action: str, reason: str):
    """Capture risk check event"""
    capture_trading_event(
        "risk.check",
        {
            "check": check,
            "action": action,
            "reason": reason
        },
        level="warning" if action == "BLOCK" else "info"
    )