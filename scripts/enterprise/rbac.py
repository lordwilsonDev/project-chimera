#!/usr/bin/env python3
"""
Enterprise RBAC (Role-Based Access Control)
Like Google/Meta/OpenAI internal systems

Features:
- Fine-grained permissions
- Role hierarchies
- Resource-level access
- Audit logging
"""

import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Optional
from enum import Enum, auto
from pathlib import Path


class Permission(Enum):
    # Messages
    MESSAGE_READ = auto()
    MESSAGE_WRITE = auto()
    MESSAGE_DELETE = auto()
    
    # Users
    USER_READ = auto()
    USER_WRITE = auto()
    USER_DELETE = auto()
    USER_INVITE = auto()
    
    # Channels
    CHANNEL_READ = auto()
    CHANNEL_CREATE = auto()
    CHANNEL_DELETE = auto()
    CHANNEL_ADMIN = auto()
    
    # System
    SYSTEM_ADMIN = auto()
    SYSTEM_AUDIT = auto()
    SYSTEM_CONFIG = auto()
    
    # AI
    AI_INVOKE = auto()
    AI_TRAIN = auto()
    AI_DEPLOY = auto()
    
    # Crypto
    CRYPTO_SIGN = auto()
    CRYPTO_ENCRYPT = auto()
    CRYPTO_ADMIN = auto()


@dataclass
class Role:
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    parent: Optional[str] = None  # Role inheritance
    
    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions


# Default roles like Google/OpenAI use
DEFAULT_ROLES = {
    "viewer": Role(
        name="viewer",
        permissions={
            Permission.MESSAGE_READ,
            Permission.USER_READ,
            Permission.CHANNEL_READ,
        }
    ),
    "member": Role(
        name="member",
        permissions={
            Permission.MESSAGE_READ,
            Permission.MESSAGE_WRITE,
            Permission.USER_READ,
            Permission.CHANNEL_READ,
            Permission.AI_INVOKE,
        },
        parent="viewer"
    ),
    "moderator": Role(
        name="moderator",
        permissions={
            Permission.MESSAGE_READ,
            Permission.MESSAGE_WRITE,
            Permission.MESSAGE_DELETE,
            Permission.USER_READ,
            Permission.USER_WRITE,
            Permission.CHANNEL_READ,
            Permission.CHANNEL_ADMIN,
            Permission.AI_INVOKE,
            Permission.SYSTEM_AUDIT,
        },
        parent="member"
    ),
    "admin": Role(
        name="admin",
        permissions={
            Permission.MESSAGE_READ,
            Permission.MESSAGE_WRITE,
            Permission.MESSAGE_DELETE,
            Permission.USER_READ,
            Permission.USER_WRITE,
            Permission.USER_DELETE,
            Permission.USER_INVITE,
            Permission.CHANNEL_READ,
            Permission.CHANNEL_CREATE,
            Permission.CHANNEL_DELETE,
            Permission.CHANNEL_ADMIN,
            Permission.SYSTEM_ADMIN,
            Permission.SYSTEM_AUDIT,
            Permission.SYSTEM_CONFIG,
            Permission.AI_INVOKE,
            Permission.AI_TRAIN,
            Permission.AI_DEPLOY,
            Permission.CRYPTO_SIGN,
            Permission.CRYPTO_ENCRYPT,
            Permission.CRYPTO_ADMIN,
        },
        parent="moderator"
    ),
}


@dataclass
class AuditEvent:
    timestamp: float
    user_id: str
    action: str
    resource: str
    resource_id: str
    result: str  # success, denied, error
    ip_address: str = ""
    user_agent: str = ""
    details: Dict = field(default_factory=dict)


class RBAC:
    """Enterprise RBAC system with audit logging"""
    
    def __init__(self, audit_dir: str = "/tmp/chimera_audit"):
        self.roles: Dict[str, Role] = dict(DEFAULT_ROLES)
        self.user_roles: Dict[str, Set[str]] = {}
        self.resource_permissions: Dict[str, Dict[str, Set[Permission]]] = {}
        self.audit_log: List[AuditEvent] = []
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(exist_ok=True)
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user"""
        if role_name not in self.roles:
            return False
        
        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()
        
        self.user_roles[user_id].add(role_name)
        
        self._audit(
            user_id="system",
            action="ROLE_ASSIGN",
            resource="user",
            resource_id=user_id,
            result="success",
            details={"role": role_name}
        )
        
        return True
    
    def check_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_id: Optional[str] = None,
        ip_address: str = "",
    ) -> bool:
        """Check if user has permission, with audit logging"""
        
        # Get all user roles
        user_roles = self.user_roles.get(user_id, set())
        
        # Check each role
        for role_name in user_roles:
            role = self.roles.get(role_name)
            if role and role.has_permission(permission):
                self._audit(
                    user_id=user_id,
                    action=f"PERMISSION_CHECK:{permission.name}",
                    resource="system",
                    resource_id=resource_id or "*",
                    result="success",
                    ip_address=ip_address,
                )
                return True
        
        # Permission denied
        self._audit(
            user_id=user_id,
            action=f"PERMISSION_CHECK:{permission.name}",
            resource="system",
            resource_id=resource_id or "*",
            result="denied",
            ip_address=ip_address,
        )
        return False
    
    def _audit(
        self,
        user_id: str,
        action: str,
        resource: str,
        resource_id: str,
        result: str,
        ip_address: str = "",
        user_agent: str = "",
        details: Dict = None,
    ):
        """Log an audit event"""
        event = AuditEvent(
            timestamp=time.time(),
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            result=result,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
        
        self.audit_log.append(event)
        
        # Persist to file
        audit_file = self.audit_dir / f"audit_{int(time.time() // 3600)}.jsonl"
        with open(audit_file, "a") as f:
            f.write(json.dumps(asdict(event)) + "\n")
    
    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit log with filters"""
        results = []
        
        for event in reversed(self.audit_log):
            if len(results) >= limit:
                break
            
            if user_id and event.user_id != user_id:
                continue
            if action and action not in event.action:
                continue
            if since and event.timestamp < since:
                continue
            
            results.append(event)
        
        return results


# Export for use
rbac = RBAC()


if __name__ == "__main__":
    # Demo
    rbac.assign_role("wilson", "admin")
    rbac.assign_role("guest", "viewer")
    
    print(f"Wilson can delete messages: {rbac.check_permission('wilson', Permission.MESSAGE_DELETE)}")
    print(f"Guest can delete messages: {rbac.check_permission('guest', Permission.MESSAGE_DELETE)}")
    print(f"Wilson can train AI: {rbac.check_permission('wilson', Permission.AI_TRAIN)}")
    
    print(f"\nAudit log: {len(rbac.audit_log)} events")
