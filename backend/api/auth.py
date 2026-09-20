import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["authentication"])

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
AUTH_SECRET_KEY = os.getenv(
    "AUTH_SECRET_KEY",
    "invoice-ai-local-secret-change-me",
)

TOKEN_EXPIRY_SECONDS = 60 * 60 * 8


class LoginRequest(BaseModel):
    username: str
    password: str


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }

    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode()

    payload_encoded = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")

    signature = hmac.new(
        AUTH_SECRET_KEY.encode(),
        payload_encoded.encode(),
        hashlib.sha256,
    ).digest()

    signature_encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    return f"{payload_encoded}.{signature_encoded}"


def verify_token(token: str) -> dict:
    try:
        payload_encoded, signature_encoded = token.split(".", 1)

        expected_signature = hmac.new(
            AUTH_SECRET_KEY.encode(),
            payload_encoded.encode(),
            hashlib.sha256,
        ).digest()

        expected_encoded = (
            base64.urlsafe_b64encode(expected_signature).decode().rstrip("=")
        )

        if not hmac.compare_digest(
            signature_encoded,
            expected_encoded,
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token",
            )

        padding = "=" * (4 - len(payload_encoded) % 4)

        payload = json.loads(base64.urlsafe_b64decode(payload_encoded + padding))

        if payload.get("exp", 0) < int(time.time()):
            raise HTTPException(
                status_code=401,
                detail="Authentication token expired",
            )

        return payload

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
        )


@router.post("/login")
def login(data: LoginRequest):
    username_ok = hmac.compare_digest(
        data.username,
        ADMIN_USERNAME,
    )

    password_ok = hmac.compare_digest(
        data.password,
        ADMIN_PASSWORD,
    )

    if not username_ok or not password_ok:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    return {
        "access_token": create_token(data.username),
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRY_SECONDS,
    }


@router.get("/me")
def me(
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = authorization[7:].strip()

    payload = verify_token(token)

    return {
        "username": payload["sub"],
        "role": "admin",
    }
