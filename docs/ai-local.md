# Local AI Integration Guide

## Overview
Sofia V2 is designed to support local AI models for trading analysis, signal explanation, and market predictions. This ensures data privacy and eliminates dependency on external AI services.

## Status: Coming Soon
Local AI integration is currently in development. The UI includes disabled buttons and hook points that will be activated in a future release.

## Planned Architecture

### 1. Backend Options
- **Ollama**: Recommended for ease of use
- **llama.cpp**: For advanced users wanting more control
- **LocalAI**: Alternative option with OpenAI-compatible API

### 2. Supported Models

#### Recommended Models
| Model | Size | VRAM Required | Use Case |
|-------|------|--------------|----------|
| Llama 2 7B | 3.8GB | 6GB | General analysis, signal explanations |
| Mistral 7B | 4.1GB | 6GB | Technical analysis, pattern recognition |
| Phi-2 | 1.7GB | 3GB | Lightweight analysis for low-end systems |
| CodeLlama 7B | 3.8GB | 6GB | Strategy code generation and analysis |

#### Hardware Requirements
- **Minimum**: 8GB RAM, 4GB VRAM (GTX 1650 or better)
- **Recommended**: 16GB RAM, 8GB VRAM (RTX 3060 or better)
- **Optimal**: 32GB RAM, 12GB+ VRAM (RTX 3080 or better)

### 3. Features to be Enabled

#### Signal Explanation
- Natural language explanations of why trades were triggered
- Risk assessment in plain English
- Market context analysis

#### Market Analysis
- Technical indicator interpretation
- Pattern recognition explanations
- Trend analysis with reasoning

#### Price Predictions
- Short-term price movement predictions
- Confidence levels and risk assessments
- Multi-timeframe analysis

#### Strategy Generation
- Natural language to strategy code
- Strategy optimization suggestions
- Backtest result interpretation

## Security Considerations

### Data Privacy
- All AI processing happens locally
- No data leaves your machine
- Complete control over model and data

### Model Security
- Use only trusted model sources
- Verify model checksums
- Regular security updates

### API Security
- Local-only API endpoints
- No external network access required
- Optional authentication for multi-user setups

## Installation (Future)

### Step 1: Install Ollama
```bash
# Windows
winget install Ollama.Ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# macOS
brew install ollama
```

### Step 2: Download Models
```bash
# Pull recommended model
ollama pull llama2:7b

# Or lighter option
ollama pull phi
```

### Step 3: Configure Sofia
```yaml
# config/ai.yaml
ai:
  enabled: true
  backend: ollama
  endpoint: http://localhost:11434
  model: llama2:7b
  max_tokens: 2048
  temperature: 0.7
```

### Step 4: Verify Setup
```bash
# Test AI endpoint
curl http://localhost:8023/ai/status
```

## UI Integration Points

### Current Hook Points (Disabled)
1. **Trading Page**
   - "Explain Signal" button (tooltip: "Local AI coming soon")
   - "Analyze Market" button (disabled state)

2. **Strategy Page**
   - "Generate Strategy" button (disabled)
   - "Optimize with AI" button (disabled)

3. **Backtest Page**
   - "AI Analysis" tab (shows coming soon message)

4. **Settings Page**
   - "AI Configuration" section (read-only)
   - Model selection dropdown (disabled)

## Development Roadmap

### Phase 1: Foundation (Current)
- ✅ API endpoints stubbed
- ✅ UI hook points added
- ✅ Documentation prepared
- ⏳ Backend architecture design

### Phase 2: Basic Integration
- [ ] Ollama integration
- [ ] Simple explanations
- [ ] Basic market analysis
- [ ] Settings UI activation

### Phase 3: Advanced Features
- [ ] Multiple model support
- [ ] Custom fine-tuning
- [ ] Strategy generation
- [ ] Real-time analysis

### Phase 4: Optimization
- [ ] Model quantization options
- [ ] Response caching
- [ ] Batch processing
- [ ] Performance monitoring

## FAQ

### Q: When will local AI be available?
A: Target release is Q2 2025, pending testing and optimization.

### Q: Can I use cloud AI instead?
A: Sofia V2 is designed for local AI to ensure privacy. Cloud AI may be added as an optional feature later.

### Q: What if I don't have a GPU?
A: CPU inference is possible but slower. Phi-2 model is recommended for CPU-only systems.

### Q: Will this work on Raspberry Pi?
A: Lightweight models like Phi-2 may work on Pi 5 with 8GB RAM, but performance will be limited.

## Contributing
Interested in helping with local AI integration? Check our GitHub issues tagged with 'ai-local'.

## Support
For questions about local AI features, please open an issue on GitHub with the 'ai-local' tag.