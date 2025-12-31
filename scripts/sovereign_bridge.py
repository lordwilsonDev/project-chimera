#!/usr/bin/env python3
"""
Chimera-Sovereign Bridge
Connects Project Chimera messaging with Sovereign Trinity AI safety
"""

import asyncio
import httpx
import json
from dataclasses import dataclass
from typing import Optional
import sys
sys.path.insert(0, str(__file__).replace('/project-chimera/scripts/sovereign_bridge.py', '/sparse_axion_rag/scripts/sovereign'))

@dataclass
class Config:
    chimera_chat: str = "http://localhost:8080"
    chimera_crypto: str = "http://localhost:8081"
    chimera_ml: str = "http://localhost:8082"
    sovereign_bridge: str = "http://localhost:9999"


class ChimeraSovereignBridge:
    """
    Bridges Chimera's enterprise messaging with Sovereign Trinity's AI safety layer.
    
    Flow:
    1. Message comes into Chimera chat
    2. Chimera publishes to NATS
    3. This bridge catches it
    4. Runs through Sovereign Trinity safety checks
    5. Returns verified/modified message
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.stats = {
            "messages_processed": 0,
            "safety_blocks": 0,
            "crypto_ops": 0,
            "sentiment_analyzed": 0,
        }
    
    async def process_message(self, content: str, user_id: str) -> dict:
        """Full pipeline: safety → sentiment → sign → return"""
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = {
                "original": content,
                "user_id": user_id,
                "processed": True,
            }
            
            # 1. Sovereign Safety Check
            try:
                safety_resp = await client.post(
                    f"{self.config.sovereign_bridge}/process",
                    json={"type": "safety", "data": content}
                )
                safety = safety_resp.json()
                
                if not safety.get("safe", True):
                    self.stats["safety_blocks"] += 1
                    return {
                        "blocked": True,
                        "reason": safety.get("reason", "Safety filter"),
                        "user_id": user_id,
                    }
                
                result["safety"] = safety
            except Exception as e:
                result["safety_error"] = str(e)
            
            # 2. Sentiment Analysis
            try:
                sentiment_resp = await client.post(
                    f"{self.config.chimera_ml}/analyze",
                    json={"text": content, "user_id": user_id}
                )
                result["sentiment"] = sentiment_resp.json()
                self.stats["sentiment_analyzed"] += 1
            except Exception as e:
                result["sentiment_error"] = str(e)
            
            # 3. Cryptographic Signing
            try:
                sign_resp = await client.post(
                    f"{self.config.chimera_crypto}/sign",
                    json={"user_id": user_id, "message": content}
                )
                result["signature"] = sign_resp.json()
                self.stats["crypto_ops"] += 1
            except Exception as e:
                result["crypto_error"] = str(e)
            
            self.stats["messages_processed"] += 1
            return result
    
    async def health_check(self) -> dict:
        """Check all connected services"""
        services = {}
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            endpoints = {
                "chimera_chat": f"{self.config.chimera_chat}/health",
                "chimera_crypto": f"{self.config.chimera_crypto}/health",
                "chimera_ml": f"{self.config.chimera_ml}/health",
                "sovereign_bridge": f"{self.config.sovereign_bridge}/health",
            }
            
            for name, url in endpoints.items():
                try:
                    resp = await client.get(url)
                    services[name] = resp.status_code == 200
                except:
                    services[name] = False
        
        return {
            "services": services,
            "stats": self.stats,
            "healthy": all(services.values()),
        }


async def main():
    bridge = ChimeraSovereignBridge()
    
    print("🌉 Chimera-Sovereign Bridge")
    print("="*50)
    
    # Health check
    health = await bridge.health_check()
    print(f"Services: {json.dumps(health['services'], indent=2)}")
    
    # Test message
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
        result = await bridge.process_message(message, "test_user")
        print(f"\nResult: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
