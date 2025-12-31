#!/usr/bin/env python3
"""
🔥 CHIMERA-SOVEREIGN INTEGRATION
================================

Axiom Inversion: Full stack dual purpose

1. Chimera WebSocket → Also: Real-time agent sync
2. Sovereign Trinity → Also: Multi-agent safety consensus
3. Nano Files → Also: Distributed agent memory
4. RAG → Also: Infinite context for any model
5. Ollama → Also: Reasoning engine with external brain

This module connects everything.
"""

import asyncio
import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
import httpx

# Import our components
from nano_rag_agent import NanoMessage, NANO_INBOX, NANO_OUTBOX, RAGRetriever


@dataclass
class ChimeraConfig:
    """Configuration for the full integration"""
    # Services
    ollama_url: str = "http://localhost:11434"
    sovereign_bridge: str = "http://localhost:9999"
    chimera_chat: str = "http://localhost:8080"
    chimera_crypto: str = "http://localhost:8081"
    chimera_ml: str = "http://localhost:8082"
    
    # Models
    default_model: str = "qwen2.5-coder:0.5b"
    embedding_model: str = "nomic-embed-text"
    
    # RAG
    top_k_context: int = 5
    max_context_chars: int = 4000  # Stay under 40KB


class ChimeraIntegration:
    """
    Full integration of:
    - Chimera (enterprise messaging)
    - Sovereign Trinity (AI safety)
    - Nano-RAG (infinite context)
    - Ollama (local LLMs)
    """
    
    def __init__(self, config: Optional[ChimeraConfig] = None):
        self.config = config or ChimeraConfig()
        self.rag = RAGRetriever()
        self.stats = {
            "messages_processed": 0,
            "safety_blocks": 0,
            "context_retrievals": 0,
            "crypto_signs": 0,
        }
    
    async def process_message(
        self,
        content: str,
        user_id: str,
        channel_id: str = "general",
    ) -> Dict[str, Any]:
        """
        Full pipeline:
        1. RAG retrieve context
        2. Sovereign safety check
        3. Ollama generate
        4. Sentiment analysis
        5. Crypto sign
        6. Store in nano memory
        """
        
        result = {
            "user_id": user_id,
            "channel_id": channel_id,
            "original": content,
            "timestamp": time.time(),
        }
        
        async with httpx.AsyncClient(timeout=120) as client:
            
            # 1. RAG Context
            context = self.rag.retrieve(content, self.config.top_k_context)
            self.stats["context_retrievals"] += 1
            result["context_count"] = len(context)
            
            # Limit context size
            context_text = "\n".join(c[:500] for c in context)
            if len(context_text) > self.config.max_context_chars:
                context_text = context_text[:self.config.max_context_chars]
            
            # 2. Sovereign Safety Check
            try:
                safety_resp = await client.post(
                    f"{self.config.sovereign_bridge}/process",
                    json={"type": "safety", "data": content}
                )
                safety = safety_resp.json()
                
                if not safety.get("safe", True):
                    self.stats["safety_blocks"] += 1
                    result["blocked"] = True
                    result["reason"] = safety.get("reason", "Safety filter")
                    return result
                    
            except Exception as e:
                # Fallback to local safety check
                dangerous = ["ignore previous", "jailbreak", "bomb", "kill"]
                if any(d in content.lower() for d in dangerous):
                    result["blocked"] = True
                    result["reason"] = "Local safety filter"
                    return result
            
            # 3. Ollama Generate with Context
            prompt = f"""Context from memory:
{context_text}

User ({user_id}): {content}

Respond helpfully and concisely:"""
            
            try:
                ollama_resp = await client.post(
                    f"{self.config.ollama_url}/api/generate",
                    json={
                        "model": self.config.default_model,
                        "prompt": prompt,
                        "stream": False,
                    }
                )
                ollama_data = ollama_resp.json()
                response = ollama_data.get("response", "")
                result["response"] = response
                result["model"] = self.config.default_model
            except Exception as e:
                result["response"] = f"[LLM Error: {e}]"
            
            # 4. Sentiment Analysis
            try:
                ml_resp = await client.post(
                    f"{self.config.chimera_ml}/analyze",
                    json={"text": content, "user_id": user_id}
                )
                result["sentiment"] = ml_resp.json()
            except:
                pass
            
            # 5. Crypto Sign
            try:
                sign_resp = await client.post(
                    f"{self.config.chimera_crypto}/sign",
                    json={"user_id": user_id, "message": response}
                )
                result["signature"] = sign_resp.json()
                self.stats["crypto_signs"] += 1
            except:
                pass
            
            # 6. Store in Nano Memory
            msg = NanoMessage(
                id=f"chimera_{int(time.time() * 1000)}",
                type="conversation",
                content=f"User: {content}\nAssistant: {response}",
                metadata={
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "sentiment": result.get("sentiment"),
                }
            )
            # Index for future retrieval
            self.rag.index_message(msg)
            
            self.stats["messages_processed"] += 1
            
        return result
    
    async def health_check(self) -> Dict[str, Any]:
        """Check all services"""
        services = {}
        
        checks = [
            ("ollama", f"{self.config.ollama_url}/api/version"),
            ("sovereign_bridge", f"{self.config.sovereign_bridge}/health"),
            ("chimera_chat", f"{self.config.chimera_chat}/health"),
            ("chimera_crypto", f"{self.config.chimera_crypto}/health"),
            ("chimera_ml", f"{self.config.chimera_ml}/health"),
        ]
        
        async with httpx.AsyncClient(timeout=5) as client:
            for name, url in checks:
                try:
                    resp = await client.get(url)
                    services[name] = resp.status_code == 200
                except:
                    services[name] = False
        
        # Check nano directories
        services["nano_inbox"] = NANO_INBOX.exists()
        services["nano_outbox"] = NANO_OUTBOX.exists()
        
        return {
            "services": services,
            "stats": self.stats,
            "healthy": sum(services.values()) >= 3,  # At least 3 services up
        }


# CLI interface
async def main():
    import sys
    
    integration = ChimeraIntegration()
    
    print("🔥 Chimera-Sovereign Integration")
    print("=" * 50)
    
    # Health check
    health = await integration.health_check()
    print("\nServices:")
    for name, status in health["services"].items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {name}")
    
    # Process query if provided
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"\n📤 Processing: {query}")
        result = await integration.process_message(query, "cli_user")
        
        if result.get("blocked"):
            print(f"\n🛡️ Blocked: {result.get('reason')}")
        else:
            print(f"\n💬 Response:\n{result.get('response', 'No response')}")
            print(f"\n📊 Context used: {result.get('context_count', 0)} chunks")


if __name__ == "__main__":
    asyncio.run(main())
