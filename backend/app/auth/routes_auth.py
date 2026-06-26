from fastapi import APIRouter, Depends, Request, Response, status
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.auth.session import clear_session_cookie, get_current_user, require_auth, set_session_cookie
from app.auth.user_registry import authenticate, get_user, set_debug_access
from app.config import settings

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    authenticated: bool
    username: str | None = None
    role: str | None = None
    debug_access: bool | None = None


class ProfileUpdateRequest(BaseModel):
    debug_access: bool = Field(description="Whether this user can access /debug telemetry surfaces.")


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    if not settings.app_auth_enabled:
        user = get_user(settings.app_auth_user)
        if user is None:
            return AuthResponse(
                authenticated=True,
                username=settings.app_auth_user,
                role=settings.app_auth_role,
                debug_access=settings.ai_soc_debug_api_enabled,
            )
        return AuthResponse(
            authenticated=True,
            username=user.username,
            role=user.role,
            debug_access=user.debug_access,
        )

    user = authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    set_session_cookie(response, request, user.username, role=user.role)
    return AuthResponse(
        authenticated=True,
        username=user.username,
        role=user.role,
        debug_access=user.debug_access,
    )


@router.get("/auth/me", response_model=AuthResponse)
def me(user: dict | None = Depends(get_current_user)) -> AuthResponse:
    if user is None:
        return AuthResponse(authenticated=False)
    return AuthResponse(
        authenticated=True,
        username=user["username"],
        role=user.get("role"),
        debug_access=bool(user.get("debug_access")),
    )


@router.patch("/auth/profile", response_model=AuthResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    user: dict = Depends(require_auth),
) -> AuthResponse:
    try:
        updated = set_debug_access(str(user["username"]), enabled=payload.debug_access)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found") from exc
    return AuthResponse(
        authenticated=True,
        username=updated.username,
        role=updated.role,
        debug_access=updated.debug_access,
    )


@router.post("/auth/logout", response_model=AuthResponse)
def logout(request: Request, response: Response) -> AuthResponse:
    clear_session_cookie(response, request)
    return AuthResponse(authenticated=False)
