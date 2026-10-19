"""
Authentication and Authorization Module for Project Atlas
Enforces API key authentication on administrative and protected endpoints.
"""

from typing import Optional
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from backend.app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_admin_key(
    api_key: Optional[str] = Security(api_key_header),
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> str:
    """
    Verify administrative API key from 'X-API-Key' header or 'Authorization: Bearer <token>'.
    Uses constant-time comparison to prevent timing attacks.
    """
    token = api_key or (auth.credentials if auth else None)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing administrative API key header 'X-API-Key' or 'Authorization: Bearer <token>'."
        )

    # Valid administrative keys configured via environment variables
    valid_keys = [k for k in [settings.ADMIN_API_KEY, settings.ATLAS_API_KEY] if k]

    is_valid = any(secrets.compare_digest(token, key) for key in valid_keys)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid administrative API key."
        )

    return token
