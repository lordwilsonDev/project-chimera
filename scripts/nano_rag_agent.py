#!/usr/bin/env python3
"""
🔥 NANO-RAG AGENT SYSTEM
========================

Axiom Inversion Applied:
- sparse_axion_rag → Infinite context memory
- Sovereign Trinity → Multi-agent safety router
- .nano files → Universal agent protocol
- File watching → Event-driven intelligence

Two Agents:
1. UI Agent - Writes requests to .nano, reads responses
2. RAG Agent - Watches .nano, retrieves context, generates response

40KB context window + infinite file memory = unlimited intelligence
"""

import asyncio
import json
import hashlib
import time
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

# Paths
NANO_DIR = Path.home() / "nano_memory"
NANO_INBOX = NANO_DIR / "inbox"      # User/UI writes here
NANO_OUTBOX = NANO_DIR / "outbox"    # Agent responses here
NANO_ARCHIVE = NANO_DIR / "archive"  # Processed files
RAG_INDEX = NANO_DIR / "index.jsonl"

# Ensure directories exist
for d in [NANO_DIR, NANO_INBOX, NANO_OUTBOX, NANO_ARCHIVE]:
    d.mkdir(exist_ok=True)


@dataclass
class NanoMessage:
    """Universal .nano file format"""
    id: str
    type: str  # "request", "response", "thought", "action"
    content: str
    context: List[str] = field(default_factory=list)  # Retrieved context
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    parent_id: Optional[str] = None  # For threading
    
    def to_file(self, path: Path):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def from_file(cls, path: Path) -> 'NanoMessage':
        with open(path) as f:
            data = json.load(f)
            return cls(**data)
    
    @property
    def hash(self) -> str:
        return hashlib.sha256(
            f"{self.id}:{self.content}:{self.timestamp}".encode()
        ).hexdigest()[:16]


class RAGRetriever:
    """
    Axiom Inversion: sparse_axion_rag's dual purpose
    Primary: Document retrieval
    Inverted: Infinite context window for any agent
    """
    
    def __init__(self):
        self.index: List[Dict] = []
        self._load_index()
    
    def _load_index(self):
        """Load existing nano index"""
        if RAG_INDEX.exists():
            with open(RAG_INDEX) as f:
                for line in f:
                    try:
                        self.index.append(json.loads(line))
                    except:
                        pass
    
    def index_message(self, msg: NanoMessage):
        """Add message to searchable index"""
        entry = {
            "id": msg.id,
            "content": msg.content,
            "type": msg.type,
            "timestamp": msg.timestamp,
            "hash": msg.hash,
        }
        self.index.append(entry)
        
        # Persist
        with open(RAG_INDEX, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    
    def retrieve(self, query: str, top_k: int = 5) -> List[str]:
        """
        Retrieve relevant context from nano history
        Simple keyword matching - can upgrade to embeddings
        """
        query_words = set(query.lower().split())
        scores = []
        
        for entry in self.index:
            content = entry.get("content", "").lower()
            content_words = set(content.split())
            
            # Jaccard similarity
            intersection = len(query_words & content_words)
            union = len(query_words | content_words)
            score = intersection / max(1, union)
            
            if score > 0:
                scores.append((score, entry["content"]))
        
        # Sort by score, return top k
        scores.sort(reverse=True)
        return [content for _, content in scores[:top_k]]


class SovereignFilter:
    """
    Axiom Inversion: Sovereign Trinity's dual purpose
    Primary: AI safety filtering
    Inverted: Multi-agent routing & consensus
    """
    
    DANGEROUS_PATTERNS = [
        "ignore previous", "bypass", "jailbreak",
        "harmful", "illegal", "kill", "bomb"
    ]
    
    def filter(self, content: str) -> tuple[bool, str]:
        """Check content safety, return (is_safe, reason)"""
        content_lower = content.lower()
        
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in content_lower:
                return False, f"AXIOM_VIOLATION: {pattern}"
        
        return True, "SAFE"
    
    def route(self, msg: NanoMessage) -> str:
        """Route message to appropriate agent type"""
        content_lower = msg.content.lower()
        
        if any(kw in content_lower for kw in ["code", "program", "function", "bug"]):
            return "code_agent"
        elif any(kw in content_lower for kw in ["search", "find", "look up"]):
            return "search_agent"
        elif any(kw in content_lower for kw in ["remember", "recall", "last time"]):
            return "memory_agent"
        else:
            return "general_agent"


class OllamaInterface:
    """
    Axiom Inversion: Ollama's dual purpose
    Primary: LLM inference
    Inverted: Reasoning engine with external memory
    """
    
    def __init__(self, model: str = "qwen2.5-coder:0.5b"):
        self.model = model
        self.base_url = "http://localhost:11434"
    
    async def generate(self, prompt: str, context: List[str]) -> str:
        """Generate response with RAG context"""
        import httpx
        
        # Build prompt with context
        if context:
            context_str = "\n".join([f"- {c[:200]}" for c in context])
            full_prompt = f"""Context from memory:
{context_str}

User query: {prompt}

Respond based on the context above if relevant. Be concise."""
        else:
            full_prompt = prompt
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": full_prompt,
                        "stream": False,
                    }
                )
                data = resp.json()
                return data.get("response", "")
        except Exception as e:
            return f"[Error: {e}]"


class NanoAgent:
    """
    The RAG Agent - watches inbox, processes with RAG context
    
    Axiom Inversion: File watcher's dual purpose
    Primary: Trigger builds on file change
    Inverted: Event-driven AI with infinite memory
    """
    
    def __init__(self):
        self.rag = RAGRetriever()
        self.filter = SovereignFilter()
        self.llm = OllamaInterface()
        self.running = False
    
    async def process_message(self, nano_path: Path) -> Optional[NanoMessage]:
        """Process a .nano request file"""
        try:
            msg = NanoMessage.from_file(nano_path)
        except Exception as e:
            print(f"❌ Failed to parse {nano_path}: {e}")
            return None
        
        print(f"📥 Processing: {msg.content[:50]}...")
        
        # 1. Safety filter
        is_safe, reason = self.filter.filter(msg.content)
        if not is_safe:
            response = NanoMessage(
                id=f"resp_{int(time.time())}",
                type="response",
                content=f"🛡️ Blocked: {reason}",
                parent_id=msg.id,
                metadata={"blocked": True}
            )
        else:
            # 2. Retrieve context (THE MAGIC - 40KB window + infinite memory)
            context = self.rag.retrieve(msg.content, top_k=5)
            print(f"   📚 Retrieved {len(context)} context chunks")
            
            # 3. Generate with context
            response_text = await self.llm.generate(msg.content, context)
            
            # 4. Create response
            response = NanoMessage(
                id=f"resp_{int(time.time())}",
                type="response",
                content=response_text,
                context=context,
                parent_id=msg.id,
                metadata={
                    "model": self.llm.model,
                    "context_count": len(context),
                    "route": self.filter.route(msg),
                }
            )
        
        # 5. Index both messages for future retrieval
        self.rag.index_message(msg)
        self.rag.index_message(response)
        
        # 6. Write response to outbox
        response_path = NANO_OUTBOX / f"{response.id}.nano"
        response.to_file(response_path)
        print(f"📤 Response: {response_path.name}")
        
        # 7. Archive original
        archive_path = NANO_ARCHIVE / nano_path.name
        nano_path.rename(archive_path)
        
        return response


class NanoWatcher(FileSystemEventHandler):
    """File system watcher for .nano inbox"""
    
    def __init__(self, agent: NanoAgent):
        self.agent = agent
        self.loop = asyncio.new_event_loop()
    
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith('.nano'):
            return
        
        # Process async
        asyncio.run(self.agent.process_message(Path(event.src_path)))


async def run_agent():
    """Run the nano-RAG agent"""
    print("═" * 60)
    print("  🔥 NANO-RAG AGENT v1.0")
    print("  Axiom Inversion Applied")
    print("═" * 60)
    print(f"  📁 Watching: {NANO_INBOX}")
    print(f"  📤 Responses: {NANO_OUTBOX}")
    print(f"  📚 Memory: {RAG_INDEX}")
    print("═" * 60)
    
    agent = NanoAgent()
    
    # Process any existing files first
    for nano_file in NANO_INBOX.glob("*.nano"):
        await agent.process_message(nano_file)
    
    # Watch for new files
    handler = NanoWatcher(agent)
    observer = Observer()
    observer.schedule(handler, str(NANO_INBOX), recursive=False)
    observer.start()
    
    print("\n👁️ Watching for .nano files... (Ctrl+C to stop)\n")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()


# ═══════════════════════════════════════════════════════════════
# UI AGENT HELPER - For the other side
# ═══════════════════════════════════════════════════════════════

def send_request(content: str) -> str:
    """
    UI Agent: Send a request via .nano file
    Returns the request ID to watch for response
    """
    msg = NanoMessage(
        id=f"req_{int(time.time())}",
        type="request",
        content=content,
    )
    
    request_path = NANO_INBOX / f"{msg.id}.nano"
    msg.to_file(request_path)
    
    return msg.id


def get_response(request_id: str, timeout: float = 60) -> Optional[str]:
    """
    UI Agent: Wait for response to a request
    """
    start = time.time()
    expected_prefix = f"resp_"
    
    while time.time() - start < timeout:
        for nano_file in NANO_OUTBOX.glob("*.nano"):
            try:
                msg = NanoMessage.from_file(nano_file)
                if msg.parent_id == request_id:
                    nano_file.unlink()  # Clean up after reading
                    return msg.content
            except:
                pass
        time.sleep(0.5)
    
    return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # CLI mode: send a request
        query = " ".join(sys.argv[1:])
        print(f"📤 Sending: {query}")
        req_id = send_request(query)
        print(f"⏳ Waiting for response...")
        response = get_response(req_id)
        if response:
            print(f"\n💬 Response:\n{response}")
        else:
            print("❌ Timeout waiting for response")
    else:
        # Daemon mode: run the agent
        asyncio.run(run_agent())
