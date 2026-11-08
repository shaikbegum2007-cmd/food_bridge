import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


bearer = HTTPBearer(auto_error=False)


def _secret() -> bytes:
    secret = os.getenv("JWT_SECRET", "development-only-change-this-secret")
    if os.getenv("APP_ENV") == "production" and secret == "development-only-change-this-secret":
        raise RuntimeError("JWT_SECRET must be set outside development.")
    return secret.encode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.urlsafe_b64encode(salt).decode()}:{base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_text, digest_text = stored.split(":", 1)
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_token(user: User) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(user.id), "role": user.role, "exp": int(time.time()) + 60 * 60 * 12}
    encode = lambda part: base64.urlsafe_b64encode(json.dumps(part, separators=(",", ":")).encode()).rstrip(b"=").decode()
    content = f"{encode(header)}.{encode(payload)}"
    signature = base64.urlsafe_b64encode(hmac.new(_secret(), content.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{content}.{signature}"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing access token.")
    if credentials is None:
        raise unauthorized
    try:
        header, payload, signature = credentials.credentials.split(".")
        content = f"{header}.{payload}"
        expected = base64.urlsafe_b64encode(hmac.new(_secret(), content.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(signature, expected):
            raise unauthorized
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(decoded)
        if claims.get("exp", 0) < time.time():
            raise unauthorized
        user = db.get(User, int(claims["sub"]))
        if user is None or not user.is_active or user.role != claims.get("role"):
            raise unauthorized
        return user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise unauthorized


def require_roles(*roles: str):
    def role_dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Your account is not permitted to perform this action.")
        return user

    return role_dependency
