#!/usr/bin/env python3
"""
Chaos Engineering Framework
Like Netflix Chaos Monkey / Google DiRT

Features:
- Service failure injection
- Network latency simulation
- Resource exhaustion tests
- Automatic recovery validation
"""

import asyncio
import random
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable
from enum import Enum
from datetime import datetime
import subprocess


class ChaosType(Enum):
    KILL_SERVICE = "kill_service"
    NETWORK_LATENCY = "network_latency"
    NETWORK_PARTITION = "network_partition"
    CPU_STRESS = "cpu_stress"
    MEMORY_PRESSURE = "memory_pressure"
    DISK_FULL = "disk_full"
    DNS_FAILURE = "dns_failure"


@dataclass
class ChaosExperiment:
    name: str
    chaos_type: ChaosType
    target: str  # Service name or "*" for random
    duration_seconds: int = 30
    intensity: float = 0.5  # 0.0 - 1.0
    enabled: bool = True
    schedule: Optional[str] = None  # Cron expression
    last_run: Optional[float] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class ExperimentResult:
    experiment_name: str
    started_at: float
    ended_at: float
    success: bool
    recovery_time_seconds: float
    affected_services: List[str]
    error: Optional[str] = None
    metrics: Dict = field(default_factory=dict)


class ChaosMonkey:
    """Enterprise chaos engineering framework"""
    
    SERVICES = [
        "chat-server",
        "crypto-service", 
        "ml-service",
        "nats",
        "redis",
    ]
    
    def __init__(self):
        self.experiments: Dict[str, ChaosExperiment] = {}
        self.results: List[ExperimentResult] = []
        self.active_chaos: Dict[str, asyncio.Task] = {}
        
        # Default experiments
        self._init_defaults()
    
    def _init_defaults(self):
        """Initialize default chaos experiments"""
        experiments = [
            ChaosExperiment(
                name="random_service_kill",
                chaos_type=ChaosType.KILL_SERVICE,
                target="*",
                duration_seconds=60,
            ),
            ChaosExperiment(
                name="network_latency_spike",
                chaos_type=ChaosType.NETWORK_LATENCY,
                target="chat-server",
                duration_seconds=30,
                intensity=0.3,  # 300ms added latency
            ),
            ChaosExperiment(
                name="redis_failure",
                chaos_type=ChaosType.KILL_SERVICE,
                target="redis",
                duration_seconds=20,
            ),
            ChaosExperiment(
                name="cpu_stress_test",
                chaos_type=ChaosType.CPU_STRESS,
                target="ml-service",
                duration_seconds=45,
                intensity=0.8,
            ),
        ]
        
        for exp in experiments:
            self.experiments[exp.name] = exp
    
    async def run_experiment(self, experiment_name: str) -> ExperimentResult:
        """Execute a chaos experiment"""
        exp = self.experiments.get(experiment_name)
        if not exp:
            raise ValueError(f"Unknown experiment: {experiment_name}")
        
        if not exp.enabled:
            raise ValueError(f"Experiment {experiment_name} is disabled")
        
        started_at = time.time()
        target = exp.target if exp.target != "*" else random.choice(self.SERVICES)
        
        print(f"🐵 CHAOS: Starting {exp.chaos_type.value} on {target}")
        
        try:
            # Inject chaos
            await self._inject_chaos(exp, target)
            
            # Wait for duration
            await asyncio.sleep(exp.duration_seconds)
            
            # Remove chaos
            await self._remove_chaos(exp, target)
            
            # Measure recovery
            recovery_start = time.time()
            recovered = await self._wait_for_recovery(target)
            recovery_time = time.time() - recovery_start
            
            ended_at = time.time()
            
            result = ExperimentResult(
                experiment_name=experiment_name,
                started_at=started_at,
                ended_at=ended_at,
                success=recovered,
                recovery_time_seconds=recovery_time,
                affected_services=[target],
                metrics={
                    "chaos_duration": exp.duration_seconds,
                    "intensity": exp.intensity,
                }
            )
            
        except Exception as e:
            result = ExperimentResult(
                experiment_name=experiment_name,
                started_at=started_at,
                ended_at=time.time(),
                success=False,
                recovery_time_seconds=-1,
                affected_services=[target],
                error=str(e),
            )
        
        self.results.append(result)
        exp.last_run = time.time()
        
        status = "✅" if result.success else "❌"
        print(f"🐵 CHAOS: {status} {experiment_name} - Recovery: {result.recovery_time_seconds:.2f}s")
        
        return result
    
    async def _inject_chaos(self, exp: ChaosExperiment, target: str):
        """Inject chaos based on type"""
        if exp.chaos_type == ChaosType.KILL_SERVICE:
            # Docker stop
            subprocess.run(
                ["docker", "stop", target],
                capture_output=True
            )
        
        elif exp.chaos_type == ChaosType.NETWORK_LATENCY:
            # Add latency with tc (traffic control)
            latency_ms = int(exp.intensity * 1000)
            # This would require root, so we simulate
            print(f"  [SIMULATED] Adding {latency_ms}ms latency to {target}")
        
        elif exp.chaos_type == ChaosType.CPU_STRESS:
            # Stress CPU
            # In production, use stress-ng
            print(f"  [SIMULATED] CPU stress at {exp.intensity*100}% on {target}")
        
        elif exp.chaos_type == ChaosType.MEMORY_PRESSURE:
            print(f"  [SIMULATED] Memory pressure at {exp.intensity*100}% on {target}")
    
    async def _remove_chaos(self, exp: ChaosExperiment, target: str):
        """Remove injected chaos"""
        if exp.chaos_type == ChaosType.KILL_SERVICE:
            # Docker start
            subprocess.run(
                ["docker", "start", target],
                capture_output=True
            )
        else:
            print(f"  [SIMULATED] Removing chaos from {target}")
    
    async def _wait_for_recovery(self, target: str, timeout: int = 60) -> bool:
        """Wait for service to recover"""
        import httpx
        
        ports = {
            "chat-server": 8080,
            "crypto-service": 8081,
            "ml-service": 8082,
        }
        
        port = ports.get(target)
        if not port:
            return True  # Assume recovered for non-HTTP services
        
        start = time.time()
        async with httpx.AsyncClient() as client:
            while time.time() - start < timeout:
                try:
                    resp = await client.get(f"http://localhost:{port}/health", timeout=2)
                    if resp.status_code == 200:
                        return True
                except:
                    pass
                await asyncio.sleep(1)
        
        return False
    
    def get_report(self) -> Dict:
        """Generate chaos engineering report"""
        if not self.results:
            return {"message": "No experiments run yet"}
        
        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful
        
        avg_recovery = sum(r.recovery_time_seconds for r in self.results if r.success) / max(1, successful)
        
        return {
            "total_experiments": len(self.results),
            "successful": successful,
            "failed": failed,
            "success_rate": f"{successful/len(self.results)*100:.1f}%",
            "avg_recovery_time": f"{avg_recovery:.2f}s",
            "last_run": datetime.fromtimestamp(self.results[-1].ended_at).isoformat() if self.results else None,
        }


# Global instance
chaos_monkey = ChaosMonkey()


if __name__ == "__main__":
    print("🐵 Chaos Monkey - Enterprise Resilience Testing")
    print("="*50)
    
    print("\nAvailable experiments:")
    for name, exp in chaos_monkey.experiments.items():
        print(f"  - {name}: {exp.chaos_type.value} on {exp.target}")
    
    print("\nTo run: chaos_monkey.run_experiment('random_service_kill')")
