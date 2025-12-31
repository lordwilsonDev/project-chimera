#!/usr/bin/env python3
"""
Data Governance & Compliance
Like Anthropic/OpenAI data handling requirements

Features:
- PII detection and masking
- Data retention policies
- GDPR compliance helpers
- Data lineage tracking
"""

import re
import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path


class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"


class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class DataLineage:
    data_id: str
    source: str
    created_at: float
    transformations: List[str] = field(default_factory=list)
    accessed_by: List[str] = field(default_factory=list)
    classification: DataClassification = DataClassification.INTERNAL


@dataclass
class RetentionPolicy:
    name: str
    data_types: List[str]
    retention_days: int
    action: str  # "delete", "archive", "anonymize"
    enabled: bool = True


class DataGovernance:
    """Enterprise data governance system"""
    
    # PII patterns
    PII_PATTERNS = {
        PIIType.EMAIL: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        PIIType.PHONE: r'\b(?:\+1)?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
        PIIType.SSN: r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b',
        PIIType.CREDIT_CARD: r'\b[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}\b',
        PIIType.IP_ADDRESS: r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
    }
    
    def __init__(self, config_path: str = "/tmp/chimera_governance"):
        self.config_path = Path(config_path)
        self.config_path.mkdir(exist_ok=True)
        
        self.lineage: Dict[str, DataLineage] = {}
        self.retention_policies: Dict[str, RetentionPolicy] = {}
        
        # Default policies
        self._init_defaults()
    
    def _init_defaults(self):
        """Initialize default retention policies"""
        policies = [
            RetentionPolicy(
                name="message_retention",
                data_types=["message", "chat"],
                retention_days=90,
                action="archive",
            ),
            RetentionPolicy(
                name="audit_log_retention",
                data_types=["audit", "log"],
                retention_days=365,
                action="archive",
            ),
            RetentionPolicy(
                name="pii_retention",
                data_types=["pii", "personal"],
                retention_days=30,
                action="delete",
            ),
            RetentionPolicy(
                name="session_retention",
                data_types=["session", "token"],
                retention_days=7,
                action="delete",
            ),
        ]
        
        for policy in policies:
            self.retention_policies[policy.name] = policy
    
    def detect_pii(self, text: str) -> List[Tuple[PIIType, str, int, int]]:
        """Detect PII in text, returns list of (type, value, start, end)"""
        findings = []
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                findings.append((
                    pii_type,
                    match.group(),
                    match.start(),
                    match.end(),
                ))
        
        return findings
    
    def mask_pii(self, text: str, mask_char: str = "*") -> Tuple[str, List[PIIType]]:
        """Mask all PII in text"""
        findings = self.detect_pii(text)
        masked_types = set()
        
        # Sort by position descending to replace from end
        findings.sort(key=lambda x: x[2], reverse=True)
        
        for pii_type, value, start, end in findings:
            masked = value[0] + mask_char * (len(value) - 2) + value[-1]
            text = text[:start] + masked + text[end:]
            masked_types.add(pii_type)
        
        return text, list(masked_types)
    
    def anonymize(self, text: str) -> str:
        """Fully anonymize text by hashing PII"""
        findings = self.detect_pii(text)
        
        findings.sort(key=lambda x: x[2], reverse=True)
        
        for pii_type, value, start, end in findings:
            hashed = hashlib.sha256(value.encode()).hexdigest()[:8]
            text = text[:start] + f"[REDACTED:{pii_type.value}:{hashed}]" + text[end:]
        
        return text
    
    def classify_data(self, text: str) -> DataClassification:
        """Classify data based on content"""
        text_lower = text.lower()
        
        # Check for restricted content
        restricted_keywords = ["password", "secret", "api_key", "private_key", "ssn"]
        if any(kw in text_lower for kw in restricted_keywords):
            return DataClassification.RESTRICTED
        
        # Check for PII
        pii = self.detect_pii(text)
        if any(p[0] in [PIIType.SSN, PIIType.CREDIT_CARD] for p in pii):
            return DataClassification.RESTRICTED
        if pii:
            return DataClassification.CONFIDENTIAL
        
        # Check for internal markers
        internal_keywords = ["internal", "confidential", "proprietary"]
        if any(kw in text_lower for kw in internal_keywords):
            return DataClassification.INTERNAL
        
        return DataClassification.PUBLIC
    
    def track_lineage(
        self,
        data_id: str,
        source: str,
        classification: Optional[DataClassification] = None,
    ) -> DataLineage:
        """Track data lineage"""
        lineage = DataLineage(
            data_id=data_id,
            source=source,
            created_at=time.time(),
            classification=classification or DataClassification.INTERNAL,
        )
        
        self.lineage[data_id] = lineage
        return lineage
    
    def add_transformation(self, data_id: str, transformation: str):
        """Record a data transformation"""
        if data_id in self.lineage:
            self.lineage[data_id].transformations.append(
                f"{time.time()}: {transformation}"
            )
    
    def record_access(self, data_id: str, user_id: str):
        """Record data access"""
        if data_id in self.lineage:
            self.lineage[data_id].accessed_by.append(
                f"{user_id}@{time.time()}"
            )
    
    def gdpr_export(self, user_id: str) -> Dict:
        """GDPR data export for a user"""
        user_data = {
            "user_id": user_id,
            "export_date": time.time(),
            "data": [],
        }
        
        for data_id, lineage in self.lineage.items():
            if user_id in str(lineage.accessed_by) or user_id in lineage.source:
                user_data["data"].append({
                    "id": data_id,
                    "source": lineage.source,
                    "created": lineage.created_at,
                    "classification": lineage.classification.value,
                })
        
        return user_data
    
    def gdpr_delete(self, user_id: str) -> int:
        """GDPR data deletion for a user"""
        to_delete = []
        
        for data_id, lineage in self.lineage.items():
            if user_id in lineage.source:
                to_delete.append(data_id)
        
        for data_id in to_delete:
            del self.lineage[data_id]
        
        return len(to_delete)


# Global instance
data_governance = DataGovernance()


if __name__ == "__main__":
    dg = DataGovernance()
    
    # Test PII detection
    test_text = """
    Contact John at john.doe@example.com or call 555-123-4567.
    His SSN is 123-45-6789 and credit card is 4111-1111-1111-1111.
    IP address: 192.168.1.1
    """
    
    print("Original text:")
    print(test_text)
    
    print("\nPII detected:")
    for pii_type, value, start, end in dg.detect_pii(test_text):
        print(f"  {pii_type.value}: {value}")
    
    masked, types = dg.mask_pii(test_text)
    print("\nMasked text:")
    print(masked)
    
    print("\nAnonymized text:")
    print(dg.anonymize(test_text))
    
    print(f"\nClassification: {dg.classify_data(test_text).value}")
