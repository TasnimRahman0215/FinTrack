"""/api/v1/auth: sign up, log in, log out, and "who am I".

Called by frontend/src/api/auth.js. Login and signup set the HttpOnly session cookie.
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_auth, get_db
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.schemas.auth import AuthConfigOut, LoginIn, MeOut, PasswordChangeIn, SignupIn
from app.services import auth_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/auth", tags=["auth"])

# Slow down password guessing; limits are per process (see core/rate_limit.py).
# The tight per-account limit is keyed on (email, IP), so someone who knows your email can only
# lock *themselves* out, not you. The looser per-email limit still caps guessing that's spread
# over many IPs.
_login_per_ip = RateLimiter(max_hits=30, window_seconds=300)
_login_per_email_ip = RateLimiter(max_hits=10, window_seconds=300)
_login_per_email = RateLimiter(max_hits=100, window_seconds=900)
_signup_per_ip = RateLimiter(max_hits=10, window_seconds=3600)
# Changing a password re-checks the current one, so it's a password-guessing path too.
_password_change_per_user = RateLimiter(max_hits=5, window_seconds=900)


def _set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        token,
        max_age=s.session_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        path="/",
    )


@router.get("/config", response_model=AuthConfigOut)
def auth_config(db: Session = Depends(get_db)) -> AuthConfigOut:
    """Public settings the login page needs (whether to show "Sign up")."""
    return AuthConfigOut(signup_enabled=auth_service.signup_enabled(db))


@router.post("/signup", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def signup(
    data: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)
) -> MeOut:
    """Create an account and a household you own, and log in."""
    _signup_per_ip.hit(client_ip(request))
    token, ctx = auth_service.signup(db, data, user_agent=request.headers.get("user-agent"))
    _set_session_cookie(response, token)
    return auth_service.me(db, ctx)


@router.post("/login", response_model=MeOut)
def login(
    data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)
) -> MeOut:
    """Log in with email and password."""
    ip = client_ip(request)
    email = data.email.lower()
    _login_per_ip.hit(ip)
    _login_per_email_ip.hit(f"{email}|{ip}")
    _login_per_email.hit(email)
    token, ctx = auth_service.login(db, data, user_agent=request.headers.get("user-agent"))
    _set_session_cookie(response, token)
    return auth_service.me(db, ctx)


def _clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        s.session_cookie_name, path="/", secure=s.cookie_secure, samesite=s.cookie_samesite
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """End this session (server-side too) and clear the cookie."""
    auth_service.logout(db, request.cookies.get(get_settings().session_cookie_name))
    _clear_session_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    response: Response, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> None:
    """Sign out on every device (e.g. after losing a phone), this one included."""
    auth_service.logout_everywhere(db, ctx)
    _clear_session_cookie(response)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChangeIn, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> None:
    """Change your password. Every other session is signed out; this one stays signed in."""
    _password_change_per_user.hit(str(ctx.user.id))
    auth_service.change_password(db, ctx, data)


@router.get("/me", response_model=MeOut)
def me(ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)) -> MeOut:
    """The signed-in user, their active household and role. 401 when logged out."""
    return auth_service.me(db, ctx)
