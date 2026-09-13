import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic import BaseModel

from app.core.config import settings
from app.models.auth import Role

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)
ALGORITHM = "HS256"

password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)


# Người đang gọi, dựng hoàn toàn từ access token — không tra cơ sở dữ liệu (ADR-0006).
# Vì vậy vai trò và claim ở đây có thể lệch hiện trạng tối đa ACCESS_TOKEN_TTL.
class CurrentUser(BaseModel):
    user_id: int
    role: Role
    claims: list[str]


def create_access_token(user_id: int, role: Role, claims: list[str]) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "claims": claims,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> CurrentUser:
    """Ném jwt.InvalidTokenError khi token hết hạn, sai chữ ký hoặc sai định dạng."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "role", "claims", "exp"]},
    )
    return CurrentUser(
        user_id=int(payload["sub"]), role=payload["role"], claims=payload["claims"]
    )


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
