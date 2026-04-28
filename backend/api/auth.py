from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
import uuid

from models.user import UserCreate, UserLogin, User, UserPublic
from db import dynamo

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("JWT_SECRET", "changeme-use-a-strong-secret-in-prod")
ALGORITHM = "HS256"
TOKEN_TTL_DAYS = 7

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


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


@router.post("/signup")
async def signup(body: UserCreate):
    existing = dynamo.get_user_by_email(body.email)
    if existing:
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
    if not user or not _verify(body.password, user["password_hash"]):
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
