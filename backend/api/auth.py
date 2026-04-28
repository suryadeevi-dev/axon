from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import jwt, JWTError
from urllib.parse import urlencode
from datetime import datetime, timedelta
import httpx
import os
import uuid

from models.user import UserCreate, UserLogin, User, UserPublic
from db import dynamo

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("JWT_SECRET", "changeme-use-a-strong-secret-in-prod")
ALGORITHM = "HS256"
TOKEN_TTL_DAYS = 7

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# Must match an Authorized Redirect URI in your Google Cloud OAuth app
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
)
# Where the backend sends the browser after successful OAuth
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return pwd_ctx.hash(password)


def _verify(password: str, hashed: str) -> bool:
    return pwd_ctx.verify(password, hashed)


def _create_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_TTL_DAYS)
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> UserPublic:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    user = dynamo.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return UserPublic(**{k: user[k] for k in ("id", "email", "name", "created_at")})


# ── Email / password ──────────────────────────────────────────────────────────

@router.post("/signup")
async def signup(body: UserCreate):
    if dynamo.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        name=body.name,
        password_hash=_hash(body.password),
    )
    dynamo.put_user(user.model_dump())
    token = _create_token(user.id, user.email)
    pub = UserPublic(id=user.id, email=user.email, name=user.name, created_at=user.created_at)
    return {"access_token": token, "token_type": "bearer", "user": pub.model_dump()}


@router.post("/login")
async def login(body: UserLogin):
    user = dynamo.get_user_by_email(body.email)
    if not user or not _verify(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = _create_token(user["id"], user["email"])
    pub = UserPublic(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])
    return {"access_token": token, "token_type": "bearer", "user": pub.model_dump()}


@router.post("/logout")
async def logout():
    return {"ok": True}


@router.get("/me")
async def me(user: UserPublic = Depends(current_user)):
    return user.model_dump()


# ── Google OAuth 2.0 ──────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    """Redirect browser to Google's consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(code: str = "", error: str = ""):
    """
    Google redirects here after consent.
    Exchange code → tokens → user info → upsert user → issue JWT → redirect frontend.
    """
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_denied")

    # Exchange authorization code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    if token_resp.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_token_failed")

    access_token = token_resp.json().get("access_token")

    # Fetch Google user profile
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if info_resp.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_userinfo_failed")

    g = info_resp.json()
    email: str = g.get("email", "")
    name: str = g.get("name") or g.get("given_name") or email.split("@")[0]
    google_id: str = g.get("sub", "")

    if not email:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_no_email")

    # Upsert user — create if new, reuse if existing
    existing = dynamo.get_user_by_email(email)
    if existing:
        user_id = existing["id"]
        user_name = existing["name"]
        created_at = existing["created_at"]
    else:
        new_user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            # No password for OAuth users — empty hash that can never verify
            password_hash="oauth:" + google_id,
        )
        dynamo.put_user(new_user.model_dump())
        user_id = new_user.id
        user_name = new_user.name
        created_at = new_user.created_at

    jwt_token = _create_token(user_id, email)

    # Redirect to frontend callback page with token in query param.
    # The frontend stores it in a cookie and navigates to /dashboard.
    pub = {"id": user_id, "email": email, "name": user_name, "created_at": created_at}
    import json, base64
    user_b64 = base64.urlsafe_b64encode(json.dumps(pub).encode()).decode()

    # Use hash fragment so token never hits server logs
    redirect_url = (
        f"{FRONTEND_URL}/callback"
        f"?token={jwt_token}"
        f"&user={user_b64}"
    )
    return RedirectResponse(redirect_url)
