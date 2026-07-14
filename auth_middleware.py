"""
Supabase authentication middleware for FastAPI.

Verifies Bearer tokens by calling Supabase's /auth/v1/user endpoint.
On success, injects { id, email, role } into request.state.user.
Returns 401 for missing, expired, or invalid tokens on protected paths.

Usage in server.py:
    from auth_middleware import SupabaseJWTMiddleware, get_current_user
    app.add_middleware(SupabaseJWTMiddleware)

Usage in a route:
    @app.get("/api/me")
    async def me(user=Depends(get_current_user)):
        return user
"""

import logging
import os
from typing import TypedDict

import httpx
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_SUPABASE_URL = "https://jdkiajauetprqgqcigta.supabase.co"

# Paths that bypass auth entirely (exact match).
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
})


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class AuthUser(TypedDict):
    id: str       # Supabase user UUID
    email: str    # User's email
    role: str     # "authenticated" for normal users


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class SupabaseJWTMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces Supabase auth on all /api/ routes.

    Protected routes: anything under /api/ that is not in _PUBLIC_PATHS.
    On valid token  → sets request.state.user (AuthUser) and continues.
    On missing token → 401 {"detail": "Authorization header required"}
    On bad token     → 401 {"detail": "<reason>"}
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Pass through public paths and non-API routes unchanged.
        if path in _PUBLIC_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # GETs are public reads (Landing/Dashboard/report view work anonymous).
        # Mutations (POST/PUT/DELETE) and SSE still require a token.
        if request.method == "GET" and not path.startswith("/api/stream/"):
            return await call_next(request)

        # Bypass auth for localhost development
        client_host = request.client.host if request.client else ""
        if client_host in ("127.0.0.1", "::1", "localhost"):
            return await call_next(request)

        # SSE endpoints: EventSource API can't send headers, so accept
        # the token as a ?token= query parameter instead.
        if path.startswith("/api/stream/"):
            token = request.query_params.get("token", "").strip()
            if not token:
                return _unauthorized("Token query parameter required for SSE")
        else:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return _unauthorized("Authorization header required")
            token = auth_header[len("Bearer "):].strip()

        try:
            user = await _verify_token(token)
        except ValueError as e:
            logger.warning("Auth failed: %s", e)
            return _unauthorized(str(e))

        request.state.user = user
        return await call_next(request)


# ---------------------------------------------------------------------------
# FastAPI dependency (optional — use in individual routes for typed access)
# ---------------------------------------------------------------------------

def get_current_user(request: Request) -> AuthUser:
    """
    FastAPI dependency that reads the user set by SupabaseJWTMiddleware.
    Use with Depends(get_current_user) in route handlers.

    Raises 401 if no user is present (middleware not applied or path skipped).
    """
    user: AuthUser | None = getattr(request.state, "user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _verify_token(token: str) -> AuthUser:
    """
    Verify a Supabase access token by calling the /auth/v1/user endpoint.

    Returns AuthUser on success, raises ValueError on failure.
    """
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY", "")
    if not anon_key:
        logger.error("SUPABASE_ANON_KEY env var is not set")
        raise ValueError("Server misconfiguration: SUPABASE_ANON_KEY not set")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{_SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": anon_key,
            },
        )

    if response.status_code != 200:
        logger.warning(
            "Supabase auth failed: status=%d body=%s",
            response.status_code,
            response.text[:200],
        )
        if response.status_code == 401:
            raise ValueError("Token has expired or is invalid")
        raise ValueError(f"Authentication failed (status {response.status_code})")

    data = response.json()
    user: AuthUser = {
        "id": data.get("id", ""),
        "email": data.get("email", ""),
        "role": data.get("role", "authenticated"),
    }
    logger.info("Authenticated user: %s", user["email"])
    return user


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": detail})
