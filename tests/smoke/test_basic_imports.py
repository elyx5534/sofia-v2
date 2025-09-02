"""Basic import tests to verify module structure."""


def test_import_datahub():
    """Test DataHub import."""
    import src.services.datahub as dh

    assert hasattr(dh, "datahub")


def test_import_api_routes():
    """Test API route imports."""
    import src.api
    import src.api.routes.backtest
    import src.api.routes.quotes  # noqa: F401


def test_import_core_modules():
    """Test core module imports."""
    import src.core.engine
    import src.core.order_manager
    import src.core.portfolio
    import src.core.position_manager
    import src.core.risk_manager  # noqa: F401


def test_import_strategies():
    """Test strategy imports."""
    import src.backtest.strategies.base
    import src.backtest.strategies.registry
    import src.backtest.strategies.sma  # noqa: F401
