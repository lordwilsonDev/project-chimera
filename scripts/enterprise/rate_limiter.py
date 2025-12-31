#!/usr/bin/env python3
"""
Advanced Rate Limiting & Circuit Breaker
Like Netflix Hystrix / Google's Load Shedding

Features:
- Token bucket rate limiting
- Sliding window
- Circuit breaker pattern
- Load shedding
"""

import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable
from enum import Enum
from collections import deque
import threading


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RateLimitConfig:
    requests_per_second: float = 10.0
    burst_size: int = 20
    window_seconds: float = 1.0


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5       # Failures before opening
    success_threshold: int = 3       # Successes to close
    timeout_seconds: float = 30.0    # Time before half-open
    half_open_max_calls: int = 3     # Calls allowed in half-open


class TokenBucket:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens"""
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now


class SlidingWindowRateLimiter:
    """Sliding window rate limiter with precise counting"""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = {}
        self._lock = threading.Lock()
    
    def is_allowed(self, key: str = "default") -> bool:
        """Check if request is allowed"""
        now = time.time()
        
        with self._lock:
            if key not in self.requests:
                self.requests[key] = deque()
            
            window = self.requests[key]
            
            # Remove old entries
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()
            
            # Check limit
            if len(window) < self.max_requests:
                window.append(now)
                return True
            
            return False
    
    def get_remaining(self, key: str = "default") -> int:
        """Get remaining requests in window"""
        now = time.time()
        
        with self._lock:
            if key not in self.requests:
                return self.max_requests
            
            window = self.requests[key]
            cutoff = now - self.window_seconds
            
            # Count valid entries
            valid = sum(1 for t in window if t >= cutoff)
            return max(0, self.max_requests - valid)


class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = threading.Lock()
    
    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Check if timeout elapsed
                if self.last_failure_time:
                    elapsed = time.time() - self.last_failure_time
                    if elapsed >= self.config.timeout_seconds:
                        self.state = CircuitState.HALF_OPEN
                        self.half_open_calls = 0
                        return True
                return False
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False
            
            return False
    
    def record_success(self):
        """Record successful execution"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed execution"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
    
    def get_status(self) -> Dict:
        """Get circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }


class LoadShedder:
    """Load shedding based on system pressure"""
    
    def __init__(self, max_concurrent: int = 100):
        self.max_concurrent = max_concurrent
        self.current_load = 0
        self._lock = threading.Lock()
    
    def acquire(self) -> bool:
        """Try to acquire a slot"""
        with self._lock:
            if self.current_load < self.max_concurrent:
                self.current_load += 1
                return True
            return False
    
    def release(self):
        """Release a slot"""
        with self._lock:
            self.current_load = max(0, self.current_load - 1)
    
    def get_load_factor(self) -> float:
        """Get current load as percentage"""
        return self.current_load / self.max_concurrent * 100


# Pre-built instances for common use
rate_limiters = {
    "api": SlidingWindowRateLimiter(100, 60),  # 100 req/min
    "websocket": SlidingWindowRateLimiter(10, 1),  # 10 conn/sec
    "ai": SlidingWindowRateLimiter(20, 60),  # 20 ai calls/min
}

circuit_breakers = {
    "crypto-service": CircuitBreaker("crypto-service"),
    "ml-service": CircuitBreaker("ml-service"),
    "nats": CircuitBreaker("nats"),
    "redis": CircuitBreaker("redis"),
}

load_shedder = LoadShedder(max_concurrent=1000)


if __name__ == "__main__":
    # Demo rate limiter
    rl = SlidingWindowRateLimiter(5, 1.0)  # 5 req/sec
    
    print("Rate Limiter Test (5 req/sec):")
    for i in range(10):
        allowed = rl.is_allowed("test")
        remaining = rl.get_remaining("test")
        print(f"  Request {i+1}: {'✅' if allowed else '❌'} (remaining: {remaining})")
    
    # Demo circuit breaker
    print("\nCircuit Breaker Test:")
    cb = CircuitBreaker("test-service")
    
    # Simulate failures
    for i in range(6):
        if cb.can_execute():
            cb.record_failure()
            print(f"  Failure {i+1}: State={cb.state.value}")
    
    print(f"  After failures: {cb.get_status()}")
    
    # Demo load shedder
    print("\nLoad Shedder Test:")
    ls = LoadShedder(max_concurrent=3)
    
    for i in range(5):
        acquired = ls.acquire()
        print(f"  Slot {i+1}: {'✅' if acquired else '❌'} (load: {ls.get_load_factor():.0f}%)")
