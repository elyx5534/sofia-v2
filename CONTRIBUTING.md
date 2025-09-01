# Contributing to Sofia V2

Thank you for your interest in contributing to Sofia V2! This document provides guidelines for contributing to the project.

## 🤝 How to Contribute

### 1. Fork and Clone
```bash
# Fork the repository on GitHub
git clone https://github.com/your-username/sofia-v2.git
cd sofia-v2
```

### 2. Set up Development Environment
```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest coverage black flake8
```

### 3. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 4. Make Changes
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation if needed
- Ensure all tests pass

### 5. Test Your Changes
```bash
# Run tests
python -m pytest

# Check coverage
coverage run -m pytest
coverage report

# Format code
black .

# Check linting
flake8
```

### 6. Commit and Push
```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

### 7. Create Pull Request
- Open a Pull Request on GitHub
- Describe your changes clearly
- Reference any related issues

## 📝 Coding Standards

### Python Code Style
- Use **Black** for code formatting
- Follow **PEP 8** conventions
- Use type hints where appropriate
- Write docstrings for functions and classes

```python
def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio for given returns.
    
    Args:
        returns: Series of returns
        risk_free_rate: Risk-free rate (default 2%)
        
    Returns:
        Sharpe ratio as float
    """
    excess_returns = returns - risk_free_rate / 252
    return excess_returns.mean() / excess_returns.std() * np.sqrt(252)
```

### Testing
- Write unit tests for all new functions
- Use pytest fixtures for common test data
- Aim for >80% test coverage
- Test both success and error cases

```python
def test_sharpe_ratio_calculation():
    """Test Sharpe ratio calculation with known values."""
    returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.01])
    expected_sharpe = 1.2345  # calculated manually
    assert abs(calculate_sharpe_ratio(returns) - expected_sharpe) < 0.001
```

### Documentation
- Update README.md for new features
- Add docstrings to all public functions
- Include examples in documentation
- Update API documentation if needed

## 🏗️ Project Architecture

### Directory Structure
```
src/
├── backtester/         # Backtesting engine
├── data_hub/          # Data collection and management  
├── trading_engine/    # Real-time trading system
├── ml/               # Machine learning models
├── strategies/       # Trading strategies
└── utils/           # Utility functions
```

### Key Principles
1. **Separation of Concerns**: Each module has a clear responsibility
2. **Testability**: All code should be easily testable
3. **Documentation**: Code should be self-documenting
4. **Performance**: Optimize for speed where necessary
5. **Security**: Never commit API keys or sensitive data

## 🐛 Bug Reports

When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages or logs
- Screenshots if applicable

Use this template:
```markdown
**Bug Description**
A clear description of the bug.

**To Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What you expected to happen.

**Environment**
- OS: [e.g. Windows 10, macOS 12.0, Ubuntu 20.04]
- Python: [e.g. 3.9.7]
- Sofia V2 Version: [e.g. 2.1.0]
```

## 💡 Feature Requests

For new features:
- Check if it already exists in issues
- Describe the use case clearly
- Explain why it would be valuable
- Consider implementation complexity

## 🔄 Development Workflow

### Git Workflow
- `main` branch for stable releases
- `develop` branch for integration
- Feature branches from `develop`
- Hotfix branches from `main`

### Commit Messages
Use conventional commits format:
```
feat: add new strategy for mean reversion
fix: resolve backtest calculation bug  
docs: update API documentation
test: add unit tests for portfolio class
refactor: optimize data fetching performance
```

### Code Review Process
1. All PRs require review from maintainers
2. Address all feedback before merging
3. Ensure CI tests pass
4. Squash commits when merging

## 📋 Development Tasks

Good first issues for new contributors:
- Add new technical indicators
- Improve test coverage
- Update documentation
- Fix UI/UX issues
- Add error handling

Advanced tasks:
- New trading strategies
- Performance optimizations
- ML model improvements
- New data sources

## 🆘 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and ideas
- **Code Comments**: For implementation questions

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to Sofia V2! 🚀