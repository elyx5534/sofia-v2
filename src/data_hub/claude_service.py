"""Claude AI service for market analysis and insights."""

import json
from datetime import datetime
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel

from .models import OHLCVData
from .settings import settings


class MarketAnalysisRequest(BaseModel):
    """Request model for market analysis."""
    
    symbol: str
    asset_type: str
    ohlcv_data: list[OHLCVData]
    timeframe: str = "1h"
    analysis_type: str = "technical"  # technical, fundamental, sentiment


class MarketAnalysisResponse(BaseModel):
    """Response model for market analysis."""
    
    symbol: str
    analysis_type: str
    summary: str
    key_insights: list[str]
    risk_level: str  # low, medium, high
    recommendation: str  # buy, sell, hold
    confidence: float  # 0.0 to 1.0
    timestamp: datetime


class ClaudeService:
    """
    Service for integrating Claude AI for market analysis.
    
    Provides AI-powered analysis of market data including:
    - Technical analysis of OHLCV data
    - Market sentiment analysis
    - Risk assessment
    - Trading recommendations
    """

    def __init__(self) -> None:
        """Initialize Claude service."""
        if not settings.claude_api_key:
            raise ValueError("Claude API key not configured. Set CLAUDE_API_KEY environment variable.")
        
        self.client = Anthropic(api_key=settings.claude_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    async def analyze_market_data(self, request: MarketAnalysisRequest) -> MarketAnalysisResponse:
        """
        Analyze market data using Claude AI.
        
        Args:
            request: Market analysis request containing symbol and OHLCV data
            
        Returns:
            MarketAnalysisResponse with AI-generated insights
        """
        try:
            # Prepare the prompt
            prompt = self._create_analysis_prompt(request)
            
            # Call Claude API
            response = await self._call_claude_api(prompt)
            
            # Parse response
            analysis = self._parse_claude_response(response, request.symbol, request.analysis_type)
            
            return analysis
            
        except Exception as e:
            # Fallback response in case of API error
            return MarketAnalysisResponse(
                symbol=request.symbol,
                analysis_type=request.analysis_type,
                summary=f"Analysis temporarily unavailable: {str(e)}",
                key_insights=["API service temporarily unavailable"],
                risk_level="medium",
                recommendation="hold",
                confidence=0.0,
                timestamp=datetime.utcnow()
            )

    def _create_analysis_prompt(self, request: MarketAnalysisRequest) -> str:
        """Create analysis prompt for Claude."""
        # Convert OHLCV data to readable format
        ohlcv_summary = self._summarize_ohlcv_data(request.ohlcv_data)
        
        prompt = f"""
        You are a professional financial analyst. Analyze the following market data for {request.symbol} ({request.asset_type}) and provide insights.

        **Market Data Summary:**
        - Symbol: {request.symbol}
        - Asset Type: {request.asset_type}
        - Timeframe: {request.timeframe}
        - Data Points: {len(request.ohlcv_data)}
        
        **OHLCV Data Analysis:**
        {ohlcv_summary}

        **Analysis Type:** {request.analysis_type}

        Please provide a comprehensive analysis in the following JSON format:
        {{
            "summary": "Brief 2-3 sentence summary of current market condition",
            "key_insights": ["insight1", "insight2", "insight3"],
            "risk_level": "low|medium|high",
            "recommendation": "buy|sell|hold",
            "confidence": 0.85
        }}

        Focus on:
        1. Price trends and momentum
        2. Volume analysis
        3. Support/resistance levels
        4. Risk assessment
        5. Short-term outlook

        Provide practical, actionable insights based on the data.
        """
        
        return prompt

    def _summarize_ohlcv_data(self, ohlcv_data: list[OHLCVData]) -> str:
        """Create a readable summary of OHLCV data."""
        if not ohlcv_data:
            return "No data available"
        
        # Sort by timestamp
        sorted_data = sorted(ohlcv_data, key=lambda x: x.timestamp)
        
        latest = sorted_data[-1]
        oldest = sorted_data[0]
        
        # Calculate basic metrics
        prices = [candle.close for candle in sorted_data]
        volumes = [candle.volume for candle in sorted_data]
        
        price_change = latest.close - oldest.close
        price_change_pct = (price_change / oldest.close) * 100
        
        avg_volume = sum(volumes) / len(volumes)
        max_price = max(candle.high for candle in sorted_data)
        min_price = min(candle.low for candle in sorted_data)
        
        summary = f"""
        - Period: {oldest.timestamp.strftime('%Y-%m-%d %H:%M')} to {latest.timestamp.strftime('%Y-%m-%d %H:%M')}
        - Latest Price: ${latest.close:.4f}
        - Price Change: ${price_change:.4f} ({price_change_pct:+.2f}%)
        - High: ${max_price:.4f} | Low: ${min_price:.4f}
        - Average Volume: {avg_volume:,.0f}
        - Current Volume: {latest.volume:,.0f}
        """
        
        return summary

    async def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API with the analysis prompt."""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    def _parse_claude_response(self, response: str, symbol: str, analysis_type: str) -> MarketAnalysisResponse:
        """Parse Claude's response into structured format."""
        try:
            # Try to extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                return MarketAnalysisResponse(
                    symbol=symbol,
                    analysis_type=analysis_type,
                    summary=parsed.get("summary", "Analysis completed"),
                    key_insights=parsed.get("key_insights", []),
                    risk_level=parsed.get("risk_level", "medium"),
                    recommendation=parsed.get("recommendation", "hold"),
                    confidence=float(parsed.get("confidence", 0.5)),
                    timestamp=datetime.utcnow()
                )
            else:
                # Fallback if JSON parsing fails
                return MarketAnalysisResponse(
                    symbol=symbol,
                    analysis_type=analysis_type,
                    summary=response[:200] + "..." if len(response) > 200 else response,
                    key_insights=["Analysis completed but format parsing failed"],
                    risk_level="medium",
                    recommendation="hold",
                    confidence=0.5,
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            return MarketAnalysisResponse(
                symbol=symbol,
                analysis_type=analysis_type,
                summary=f"Response parsing error: {str(e)}",
                key_insights=["Response format error"],
                risk_level="medium",
                recommendation="hold",
                confidence=0.0,
                timestamp=datetime.utcnow()
            )


# Global service instance
claude_service = ClaudeService() if settings.claude_api_key else None


