#!/usr/bin/env python3
"""
Project Chimera - ML Sentiment Analysis Service
Multi-model ensemble sentiment analysis with NATS integration
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import nats
from nats.aio.client import Client as NATS

# Sentiment analyzers
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    print("⚠️ VADER not available - install vaderSentiment")

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    print("⚠️ TextBlob not available - install textblob")


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

@dataclass
class Config:
    port: int = int(os.getenv("PORT", "8082"))
    nats_url: str = os.getenv("NATS_URL", "nats://localhost:4222")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache_ttl: int = 3600  # 1 hour


config = Config()


# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    text: str
    user_id: Optional[str] = None


class SentimentResult(BaseModel):
    text: str
    compound: float  # -1 to 1
    positive: float
    negative: float
    neutral: float
    polarity: float  # TextBlob polarity
    subjectivity: float  # TextBlob subjectivity
    label: str  # positive, negative, neutral
    confidence: float
    source: str
    cached: bool = False
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    analyzers: dict
    nats_connected: bool
    redis_connected: bool


# ═══════════════════════════════════════════════════════════════
# SENTIMENT ANALYZER
# ═══════════════════════════════════════════════════════════════

class SentimentAnalyzer:
    """Multi-model ensemble sentiment analyzer"""
    
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer() if VADER_AVAILABLE else None
        self.stats = {
            "analyzed": 0,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
        }
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze text using ensemble of models"""
        
        # VADER analysis
        if self.vader:
            vader_scores = self.vader.polarity_scores(text)
        else:
            vader_scores = {"compound": 0, "pos": 0.33, "neg": 0.33, "neu": 0.34}
        
        # TextBlob analysis
        if TEXTBLOB_AVAILABLE:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
        else:
            polarity = 0
            subjectivity = 0.5
        
        # Ensemble compound score (weighted average)
        compound = vader_scores["compound"] * 0.6 + polarity * 0.4
        
        # Determine label
        if compound >= 0.05:
            label = "positive"
            self.stats["positive"] += 1
        elif compound <= -0.05:
            label = "negative"
            self.stats["negative"] += 1
        else:
            label = "neutral"
            self.stats["neutral"] += 1
        
        self.stats["analyzed"] += 1
        
        # Confidence based on agreement between models
        agreement = 1.0 - abs(vader_scores["compound"] - polarity)
        confidence = min(1.0, agreement + abs(compound) * 0.5)
        
        return SentimentResult(
            text=text[:100] + "..." if len(text) > 100 else text,
            compound=round(compound, 4),
            positive=round(vader_scores["pos"], 4),
            negative=round(vader_scores["neg"], 4),
            neutral=round(vader_scores["neu"], 4),
            polarity=round(polarity, 4),
            subjectivity=round(subjectivity, 4),
            label=label,
            confidence=round(confidence, 4),
            source="ensemble_vader_textblob",
            timestamp=datetime.utcnow().isoformat()
        )


# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════

analyzer = SentimentAnalyzer()
nats_client: Optional[NATS] = None
redis_client: Optional[redis.Redis] = None


# ═══════════════════════════════════════════════════════════════
# NATS HANDLER
# ═══════════════════════════════════════════════════════════════

async def message_handler(msg):
    """Handle incoming NATS messages for sentiment analysis"""
    try:
        data = json.loads(msg.data.decode())
        content = data.get("content", "")
        
        if content:
            result = analyzer.analyze(content)
            
            # Publish result back
            response = {
                "original_id": data.get("id"),
                "user_id": data.get("user_id"),
                "sentiment": asdict(result),
            }
            
            if nats_client:
                await nats_client.publish(
                    "chimera.sentiment.result",
                    json.dumps(response).encode()
                )
    except Exception as e:
        print(f"❌ NATS message error: {e}")


async def connect_nats():
    """Connect to NATS server"""
    global nats_client
    try:
        nats_client = await nats.connect(
            config.nats_url,
            reconnect_time_wait=2,
            max_reconnect_attempts=10,
        )
        await nats_client.subscribe("chimera.sentiment", cb=message_handler)
        print(f"✅ Connected to NATS: {config.nats_url}")
    except Exception as e:
        print(f"⚠️ NATS connection failed: {e}")


async def connect_redis():
    """Connect to Redis"""
    global redis_client
    try:
        redis_client = redis.from_url(config.redis_url)
        await redis_client.ping()
        print(f"✅ Connected to Redis: {config.redis_url}")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")


# ═══════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown"""
    print("═══════════════════════════════════════════════════")
    print("  🧠 PROJECT CHIMERA - ML Service v1.0")
    print("═══════════════════════════════════════════════════")
    
    await connect_nats()
    await connect_redis()
    
    yield
    
    if nats_client:
        await nats_client.close()
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="Chimera ML Service",
    description="Multi-model sentiment analysis",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="chimera-ml",
        version="1.0.0",
        analyzers={
            "vader": VADER_AVAILABLE,
            "textblob": TEXTBLOB_AVAILABLE,
        },
        nats_connected=nats_client is not None and nats_client.is_connected,
        redis_connected=redis_client is not None,
    )


@app.post("/analyze", response_model=SentimentResult)
async def analyze(request: AnalyzeRequest):
    """Analyze sentiment of text"""
    if not request.text.strip():
        raise HTTPException(400, "Text cannot be empty")
    
    # Check cache
    cache_key = f"sentiment:{hash(request.text)}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                result = SentimentResult(**json.loads(cached))
                result.cached = True
                return result
        except Exception:
            pass
    
    # Analyze
    result = analyzer.analyze(request.text)
    
    # Cache result
    if redis_client:
        try:
            await redis_client.setex(
                cache_key,
                config.cache_ttl,
                json.dumps(asdict(result))
            )
        except Exception:
            pass
    
    return result


@app.get("/stats")
async def stats():
    """Get analyzer statistics"""
    return {
        "stats": analyzer.stats,
        "models": {
            "vader": VADER_AVAILABLE,
            "textblob": TEXTBLOB_AVAILABLE,
        },
    }


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 ML service starting on port {config.port}")
    uvicorn.run(app, host="0.0.0.0", port=config.port)
