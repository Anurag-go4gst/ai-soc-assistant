import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth.session import clear_session_cookie, get_current_user, set_session_cookie
from app.config import settings

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    authenticated: bool
    username: str | None = None
    role: str | None = None


def _valid_credentials(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.app_auth_user) and hmac.compare_digest(
        password,
        settings.app_auth_password,
    )


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    if not settings.app_auth_enabled:
        return AuthResponse(authenticated=True, username=settings.app_auth_user, role="demo_analyst")

    if not settings.app_auth_password or not _valid_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    set_session_cookie(response, request, settings.app_auth_user)
    return AuthResponse(authenticated=True, username=settings.app_auth_user, role="demo_analyst")


@router.get("/auth/me", response_model=AuthResponse)
def me(user: dict | None = Depends(get_current_user)) -> AuthResponse:
    if user is None:
        return AuthResponse(authenticated=False)
    return AuthResponse(authenticated=True, username=user["username"], role=user["role"])


@router.post("/auth/logout", response_model=AuthResponse)
def logout(request: Request, response: Response) -> AuthResponse:
    clear_session_cookie(response, request)
    return AuthResponse(authenticated=False)
