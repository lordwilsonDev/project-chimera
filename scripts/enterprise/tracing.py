#!/usr/bin/env python3
"""
OpenTelemetry Distributed Tracing
Like Google Dapper / Uber Jaeger

Features:
- Request tracing across services
- Span relationships
- Performance analysis
- Error tracking
"""

import time
import uuid
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from contextlib import contextmanager
from threading import local


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "ok"  # ok, error
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return -1


class Tracer:
    """Distributed tracing system"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.spans: Dict[str, Span] = {}
        self.traces: Dict[str, List[Span]] = {}
        self._local = local()
    
    def _generate_id(self) -> str:
        return uuid.uuid4().hex[:16]
    
    @property
    def current_span(self) -> Optional[Span]:
        return getattr(self._local, "span", None)
    
    @contextmanager
    def start_span(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ):
        """Start a new span"""
        
        # Inherit from current span if not specified
        if self.current_span and not trace_id:
            trace_id = self.current_span.trace_id
            parent_span_id = self.current_span.span_id
        
        span = Span(
            trace_id=trace_id or self._generate_id(),
            span_id=self._generate_id(),
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=self.service_name,
            start_time=time.time(),
        )
        
        # Store in local context
        old_span = self.current_span
        self._local.span = span
        
        try:
            yield span
            span.status = "ok"
        except Exception as e:
            span.status = "error"
            span.logs.append({
                "timestamp": time.time(),
                "level": "error",
                "message": str(e),
            })
            raise
        finally:
            span.end_time = time.time()
            self._local.span = old_span
            
            # Store span
            self.spans[span.span_id] = span
            
            if span.trace_id not in self.traces:
                self.traces[span.trace_id] = []
            self.traces[span.trace_id].append(span)
    
    def add_tag(self, key: str, value: str):
        """Add tag to current span"""
        if self.current_span:
            self.current_span.tags[key] = value
    
    def log(self, message: str, level: str = "info"):
        """Add log to current span"""
        if self.current_span:
            self.current_span.logs.append({
                "timestamp": time.time(),
                "level": level,
                "message": message,
            })
    
    def get_trace(self, trace_id: str) -> List[Dict]:
        """Get all spans for a trace"""
        spans = self.traces.get(trace_id, [])
        return [asdict(s) for s in spans]
    
    def get_trace_tree(self, trace_id: str) -> Dict:
        """Get trace as a tree structure"""
        spans = self.traces.get(trace_id, [])
        
        if not spans:
            return {}
        
        # Build tree
        spans_by_id = {s.span_id: asdict(s) for s in spans}
        root = None
        
        for span in spans:
            span_dict = spans_by_id[span.span_id]
            span_dict["children"] = []
            
            if span.parent_span_id and span.parent_span_id in spans_by_id:
                parent = spans_by_id[span.parent_span_id]
                if "children" not in parent:
                    parent["children"] = []
                parent["children"].append(span_dict)
            else:
                root = span_dict
        
        return root or {}
    
    def analyze_trace(self, trace_id: str) -> Dict:
        """Analyze a trace for performance insights"""
        spans = self.traces.get(trace_id, [])
        
        if not spans:
            return {"error": "Trace not found"}
        
        total_duration = max(s.duration_ms for s in spans)
        error_count = sum(1 for s in spans if s.status == "error")
        
        # Find slowest operations
        sorted_spans = sorted(spans, key=lambda s: s.duration_ms, reverse=True)
        slowest = sorted_spans[:5]
        
        return {
            "trace_id": trace_id,
            "span_count": len(spans),
            "total_duration_ms": total_duration,
            "error_count": error_count,
            "services": list(set(s.service_name for s in spans)),
            "slowest_operations": [
                {
                    "operation": s.operation_name,
                    "service": s.service_name,
                    "duration_ms": s.duration_ms,
                }
                for s in slowest
            ],
        }


# Create tracers for each service
tracers = {
    "chat-server": Tracer("chat-server"),
    "crypto-service": Tracer("crypto-service"),
    "ml-service": Tracer("ml-service"),
    "sovereign-bridge": Tracer("sovereign-bridge"),
}


def get_tracer(service_name: str) -> Tracer:
    if service_name not in tracers:
        tracers[service_name] = Tracer(service_name)
    return tracers[service_name]


if __name__ == "__main__":
    import asyncio
    
    # Demo distributed trace
    chat_tracer = get_tracer("chat-server")
    crypto_tracer = get_tracer("crypto-service")
    ml_tracer = get_tracer("ml-service")
    
    trace_id = uuid.uuid4().hex[:16]
    
    # Simulate request flow
    with chat_tracer.start_span("handle_message", trace_id=trace_id) as root:
        root.tags["user_id"] = "wilson"
        root.tags["message_id"] = "msg_123"
        
        time.sleep(0.01)  # Simulate work
        
        # Call crypto service
        with crypto_tracer.start_span("sign_message", trace_id=trace_id, parent_span_id=root.span_id) as crypto_span:
            crypto_span.tags["algorithm"] = "ed25519"
            time.sleep(0.005)
        
        # Call ML service
        with ml_tracer.start_span("analyze_sentiment", trace_id=trace_id, parent_span_id=root.span_id) as ml_span:
            ml_span.tags["model"] = "vader"
            time.sleep(0.008)
    
    # Analyze
    print("Trace Analysis:")
    print(json.dumps(chat_tracer.analyze_trace(trace_id), indent=2))
    
    print("\nTrace Tree:")
    print(json.dumps(chat_tracer.get_trace_tree(trace_id), indent=2))
