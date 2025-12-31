#!/usr/bin/env python3
"""
Feature Flags System
Like LaunchDarkly / Google's internal feature gating

Features:
- Gradual rollouts (percentage-based)
- User targeting
- A/B testing
- Kill switches
"""

import json
import time
import random
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum
from pathlib import Path


class RolloutType(Enum):
    BOOLEAN = "boolean"      # On/off
    PERCENTAGE = "percentage"  # Gradual rollout
    USER_LIST = "user_list"   # Specific users
    RING = "ring"            # Ring-based (canary → beta → prod)


@dataclass
class FeatureFlag:
    name: str
    description: str
    enabled: bool = True
    rollout_type: RolloutType = RolloutType.BOOLEAN
    rollout_percentage: float = 100.0  # 0-100
    allowed_users: List[str] = field(default_factory=list)
    blocked_users: List[str] = field(default_factory=list)
    ring: str = "production"  # canary, beta, production
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class FeatureFlags:
    """Enterprise feature flag system"""
    
    RINGS = ["canary", "beta", "production"]
    
    def __init__(self, config_path: str = "/tmp/chimera_flags.json"):
        self.config_path = Path(config_path)
        self.flags: Dict[str, FeatureFlag] = {}
        self._load()
        
        # Default flags for Chimera
        self._init_defaults()
    
    def _init_defaults(self):
        """Initialize default feature flags"""
        defaults = [
            FeatureFlag(
                name="ai_safety_v2",
                description="New AI safety system with enhanced filtering",
                rollout_type=RolloutType.PERCENTAGE,
                rollout_percentage=50.0,
            ),
            FeatureFlag(
                name="encryption_aes256",
                description="Use AES-256 instead of ChaCha20",
                rollout_type=RolloutType.RING,
                ring="canary",
            ),
            FeatureFlag(
                name="sentiment_transformer",
                description="Use transformer model for sentiment",
                rollout_type=RolloutType.USER_LIST,
                allowed_users=["wilson", "admin"],
            ),
            FeatureFlag(
                name="websocket_compression",
                description="Enable WebSocket compression",
                enabled=True,
            ),
            FeatureFlag(
                name="rate_limit_v2",
                description="New rate limiting algorithm",
                rollout_type=RolloutType.PERCENTAGE,
                rollout_percentage=10.0,  # 10% canary
            ),
        ]
        
        for flag in defaults:
            if flag.name not in self.flags:
                self.flags[flag.name] = flag
    
    def _load(self):
        """Load flags from disk"""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    for name, flag_data in data.items():
                        flag_data["rollout_type"] = RolloutType(flag_data["rollout_type"])
                        self.flags[name] = FeatureFlag(**flag_data)
            except Exception:
                pass
    
    def _save(self):
        """Persist flags to disk"""
        data = {}
        for name, flag in self.flags.items():
            flag_dict = asdict(flag)
            flag_dict["rollout_type"] = flag.rollout_type.value
            data[name] = flag_dict
        
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        user_ring: str = "production",
    ) -> bool:
        """Check if feature is enabled for user"""
        
        flag = self.flags.get(flag_name)
        if not flag:
            return False
        
        if not flag.enabled:
            return False
        
        # Check blocked users
        if user_id and user_id in flag.blocked_users:
            return False
        
        # Check by rollout type
        if flag.rollout_type == RolloutType.BOOLEAN:
            return True
        
        elif flag.rollout_type == RolloutType.USER_LIST:
            return user_id in flag.allowed_users
        
        elif flag.rollout_type == RolloutType.PERCENTAGE:
            if not user_id:
                return random.random() * 100 < flag.rollout_percentage
            # Consistent hash for user
            hash_val = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest()[:8], 16)
            bucket = (hash_val % 100)
            return bucket < flag.rollout_percentage
        
        elif flag.rollout_type == RolloutType.RING:
            flag_ring_idx = self.RINGS.index(flag.ring) if flag.ring in self.RINGS else 0
            user_ring_idx = self.RINGS.index(user_ring) if user_ring in self.RINGS else 2
            return user_ring_idx <= flag_ring_idx
        
        return False
    
    def create_flag(self, flag: FeatureFlag) -> bool:
        """Create a new feature flag"""
        if flag.name in self.flags:
            return False
        
        self.flags[flag.name] = flag
        self._save()
        return True
    
    def update_rollout(self, flag_name: str, percentage: float) -> bool:
        """Update rollout percentage"""
        if flag_name not in self.flags:
            return False
        
        self.flags[flag_name].rollout_percentage = max(0, min(100, percentage))
        self.flags[flag_name].updated_at = time.time()
        self._save()
        return True
    
    def kill_switch(self, flag_name: str) -> bool:
        """Emergency disable a feature"""
        if flag_name not in self.flags:
            return False
        
        self.flags[flag_name].enabled = False
        self.flags[flag_name].updated_at = time.time()
        self._save()
        return True
    
    def get_all_flags(self) -> Dict[str, Dict]:
        """Get all flags status"""
        return {
            name: {
                "enabled": flag.enabled,
                "rollout_percentage": flag.rollout_percentage,
                "type": flag.rollout_type.value,
            }
            for name, flag in self.flags.items()
        }


# Global instance
feature_flags = FeatureFlags()


if __name__ == "__main__":
    ff = FeatureFlags()
    
    print("Feature Flags:")
    for name, status in ff.get_all_flags().items():
        print(f"  {name}: {status}")
    
    print(f"\nai_safety_v2 enabled for wilson: {ff.is_enabled('ai_safety_v2', 'wilson')}")
    print(f"ai_safety_v2 enabled for guest: {ff.is_enabled('ai_safety_v2', 'guest')}")
    print(f"encryption_aes256 enabled (canary): {ff.is_enabled('encryption_aes256', 'wilson', 'canary')}")
    print(f"encryption_aes256 enabled (prod): {ff.is_enabled('encryption_aes256', 'wilson', 'production')}")
