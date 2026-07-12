import base64
import hashlib
import hmac
import os
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import Settings


ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_value, digest_value = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_value)
        expected = base64.b64decode(digest_value)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(*, user_id: uuid.UUID, session_id: uuid.UUID, token_type: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes) if token_type == "access" else timedelta(days=settings.refresh_token_days)
    claims = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": uuid.uuid4().hex,
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=ALGORITHM)


def decode_token(token: str, settings: Settings, expected_type: str) -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except JWTError as error:
        raise ValueError("Invalid or expired token") from error
    if claims.get("type") != expected_type or not claims.get("sub") or not claims.get("sid"):
        raise ValueError("Invalid token type")
    return claims
