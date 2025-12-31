#!/usr/bin/env python3
"""
🔥 CHIMERA UI AGENT
===================

The UI-side agent that:
1. Receives user input
2. Writes .nano requests
3. Watches for .nano responses
4. Displays to user

Dual Purpose via Axiom Inversion:
- Primary: User interface
- Inverted: Human-in-the-loop for multi-agent consensus
"""

import asyncio
import time
from pathlib import Path
from dataclasses import dataclass, asdict
import json

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.live import Live
    from rich.spinner import Spinner
    RICH = True
except ImportError:
    RICH = False
    class Console:
        def print(self, *a, **kw): print(*[str(x).replace('[', '').replace(']', '') for x in a])
        def input(self, prompt): return input(prompt.replace('[bold cyan]', '').replace('[/]', ''))

console = Console()

# Paths (must match nano_rag_agent.py)
NANO_DIR = Path.home() / "nano_memory"
NANO_INBOX = NANO_DIR / "inbox"
NANO_OUTBOX = NANO_DIR / "outbox"

# Ensure exists
NANO_INBOX.mkdir(parents=True, exist_ok=True)
NANO_OUTBOX.mkdir(parents=True, exist_ok=True)


@dataclass
class NanoMessage:
    id: str
    type: str
    content: str
    context: list = None
    metadata: dict = None
    timestamp: float = None
    parent_id: str = None
    
    def to_file(self, path: Path):
        data = {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "context": self.context or [],
            "metadata": self.metadata or {},
            "timestamp": self.timestamp or time.time(),
            "parent_id": self.parent_id,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def from_file(cls, path: Path):
        with open(path) as f:
            data = json.load(f)
            return cls(**data)


def send_request(content: str) -> str:
    """Send a request via .nano file"""
    msg_id = f"req_{int(time.time() * 1000)}"
    msg = NanoMessage(
        id=msg_id,
        type="request",
        content=content,
    )
    
    request_path = NANO_INBOX / f"{msg_id}.nano"
    msg.to_file(request_path)
    
    return msg_id


def wait_for_response(request_id: str, timeout: float = 120) -> tuple:
    """Wait for response, return (content, metadata)"""
    start = time.time()
    
    while time.time() - start < timeout:
        for nano_file in NANO_OUTBOX.glob("*.nano"):
            try:
                msg = NanoMessage.from_file(nano_file)
                if msg.parent_id == request_id:
                    nano_file.unlink()  # Clean up
                    return msg.content, msg.metadata or {}
            except:
                pass
        time.sleep(0.3)
    
    return None, {}


def interactive_mode():
    """Interactive chat mode"""
    console.print(Panel.fit(
        "🔥 [bold]CHIMERA UI AGENT[/bold]\n"
        "File-based AI with infinite memory\n"
        "Type 'exit' to quit | '/stats' for stats",
        style="bold magenta"
    ) if RICH else "🔥 CHIMERA UI AGENT - File-based AI")
    
    requests_sent = 0
    total_context_used = 0
    
    while True:
        try:
            user_input = console.input("\n[bold cyan]You >[/] " if RICH else "\nYou > ")
        except (EOFError, KeyboardInterrupt):
            break
        
        if not user_input.strip():
            continue
        
        if user_input.lower() in ['exit', 'quit', 'q']:
            console.print("[dim]Goodbye![/dim]" if RICH else "Goodbye!")
            break
        
        if user_input == '/stats':
            console.print(f"Requests: {requests_sent} | Context chunks used: {total_context_used}")
            continue
        
        # Send via .nano
        console.print("[dim]📤 Writing .nano request...[/dim]" if RICH else "📤 Sending...")
        request_id = send_request(user_input)
        requests_sent += 1
        
        # Wait for response
        console.print("[dim]⏳ Waiting for agent...[/dim]" if RICH else "⏳ Waiting...")
        response, metadata = wait_for_response(request_id)
        
        if response:
            context_count = metadata.get('context_count', 0)
            total_context_used += context_count
            
            console.print(f"\n[green]{response}[/green]" if RICH else f"\n{response}")
            
            if context_count > 0:
                console.print(
                    f"[dim]📚 Used {context_count} memory chunks | Route: {metadata.get('route', 'general')}[/dim]"
                    if RICH else f"[Memory: {context_count} chunks]"
                )
        else:
            console.print("[red]❌ No response (is the agent running?)[/red]" if RICH else "❌ Timeout")


def one_shot(query: str):
    """Single query mode"""
    console.print(f"[dim]📤 Sending: {query[:50]}...[/dim]" if RICH else f"📤 {query[:50]}...")
    
    request_id = send_request(query)
    response, metadata = wait_for_response(request_id)
    
    if response:
        print(response)
    else:
        print("❌ No response")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        one_shot(" ".join(sys.argv[1:]))
    else:
        interactive_mode()
