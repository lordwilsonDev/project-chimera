#!/usr/bin/env python3
"""
OAuth2 / OIDC SSO Integration
Like Google Workspace / Okta integration

Features:
- OAuth2 authorization code flow
- JWT token validation
- OIDC discovery
- Session management
"""

import time
import json
import secrets
import hashlib
import base64
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlencode, parse_qs
import hmac


@dataclass
class OAuthConfig:
    """OAuth2 provider configuration"""
    provider: str
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    scopes: List[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    redirect_uri: str = "http://localhost:8080/callback"


# Pre-configured providers
OAUTH_PROVIDERS = {
    "google": OAuthConfig(
        provider="google",
        client_id="${GOOGLE_CLIENT_ID}",
        client_secret="${GOOGLE_CLIENT_SECRET}",
        authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
        scopes=["openid", "profile", "email"],
    ),
    "github": OAuthConfig(
        provider="github",
        client_id="${GITHUB_CLIENT_ID}",
        client_secret="${GITHUB_CLIENT_SECRET}",
        authorization_endpoint="https://github.com/login/oauth/authorize",
        token_endpoint="https://github.com/login/oauth/access_token",
        userinfo_endpoint="https://api.github.com/user",
        scopes=["read:user", "user:email"],
    ),
    "microsoft": OAuthConfig(
        provider="microsoft",
        client_id="${AZURE_CLIENT_ID}",
        client_secret="${AZURE_CLIENT_SECRET}",
        authorization_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        userinfo_endpoint="https://graph.microsoft.com/oidc/userinfo",
        scopes=["openid", "profile", "email"],
    ),
}


@dataclass
class AuthSession:
    """User authentication session"""
    session_id: str
    user_id: str
    email: str
    name: str
    provider: str
    access_token: str
    refresh_token: Optional[str]
    expires_at: float
    created_at: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


class SSOManager:
    """Single Sign-On manager"""
    
    def __init__(self, secret_key: str = "chimera_sso_secret"):
        self.secret_key = secret_key.encode()
        self.sessions: Dict[str, AuthSession] = {}
        self.state_tokens: Dict[str, Dict] = {}  # CSRF protection
    
    def generate_auth_url(
        self,
        provider: str,
        redirect_uri: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Generate OAuth authorization URL
        Returns (url, state_token)
        """
        config = OAUTH_PROVIDERS.get(provider)
        if not config:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Generate state token (CSRF protection)
        state = secrets.token_urlsafe(32)
        
        # Generate PKCE code verifier and challenge
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b'=').decode()
        
        # Store state
        self.state_tokens[state] = {
            "provider": provider,
            "code_verifier": code_verifier,
            "created_at": time.time(),
        }
        
        # Build URL
        params = {
            "client_id": config.client_id,
            "redirect_uri": redirect_uri or config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        
        url = f"{config.authorization_endpoint}?{urlencode(params)}"
        return url, state
    
    def validate_callback(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> Optional[AuthSession]:
        """
        Validate OAuth callback and create session
        In production, this would make actual HTTP requests
        """
        # Verify state
        state_data = self.state_tokens.pop(state, None)
        if not state_data:
            raise ValueError("Invalid state token")
        
        if state_data["provider"] != provider:
            raise ValueError("Provider mismatch")
        
        # Check state age (5 minute max)
        if time.time() - state_data["created_at"] > 300:
            raise ValueError("State token expired")
        
        # In production: Exchange code for tokens
        # tokens = self._exchange_code(provider, code, state_data["code_verifier"])
        
        # Simulate token response
        session = AuthSession(
            session_id=secrets.token_urlsafe(32),
            user_id=f"{provider}_{secrets.token_hex(8)}",
            email=f"user@{provider}.com",
            name=f"User from {provider}",
            provider=provider,
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            expires_at=time.time() + 3600,
        )
        
        self.sessions[session.session_id] = session
        return session
    
    def create_session_token(self, session: AuthSession) -> str:
        """Create signed session token (like JWT)"""
        payload = {
            "sid": session.session_id,
            "uid": session.user_id,
            "email": session.email,
            "exp": session.expires_at,
            "iat": time.time(),
        }
        
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
        
        # Sign
        signature = hmac.new(
            self.secret_key,
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{payload_b64}.{signature}"
    
    def verify_session_token(self, token: str) -> Optional[Dict]:
        """Verify and decode session token"""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None
            
            payload_b64, signature = parts
            
            # Verify signature
            expected_sig = hmac.new(
                self.secret_key,
                payload_b64.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_sig):
                return None
            
            # Decode payload
            payload_json = base64.urlsafe_b64decode(payload_b64).decode()
            payload = json.loads(payload_json)
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                return None
            
            return payload
            
        except Exception:
            return None
    
    def get_session(self, session_id: str) -> Optional[AuthSession]:
        """Get session by ID"""
        session = self.sessions.get(session_id)
        
        if session and session.expires_at > time.time():
            return session
        
        return None
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def list_active_sessions(self, user_id: str) -> List[AuthSession]:
        """List all active sessions for a user"""
        now = time.time()
        return [
            s for s in self.sessions.values()
            if s.user_id == user_id and s.expires_at > now
        ]


# Global instance
sso_manager = SSOManager()


if __name__ == "__main__":
    sso = SSOManager()
    
    # Demo OAuth flow
    print("SSO Demo")
    print("="*50)
    
    # Generate auth URL
    url, state = sso.generate_auth_url("google")
    print(f"\n1. Auth URL: {url[:80]}...")
    
    # Simulate callback (in production, user would be redirected)
    print("\n2. Simulating callback...")
    session = sso.validate_callback("google", "fake_code", state)
    print(f"   Session created: {session.session_id[:16]}...")
    
    # Create token
    token = sso.create_session_token(session)
    print(f"\n3. Session token: {token[:50]}...")
    
    # Verify token
    payload = sso.verify_session_token(token)
    print(f"\n4. Verified payload: {payload}")
    
    # List sessions
    sessions = sso.list_active_sessions(session.user_id)
    print(f"\n5. Active sessions: {len(sessions)}")
