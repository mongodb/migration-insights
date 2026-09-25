"""Owner id for saved log analyses: Kanopy username or a browser cookie."""
import base64
import json
import logging
import uuid

from flask import request

from .app_config import SECURE_COOKIES, parse_env_bool

logger = logging.getLogger(__name__)

OWNER_COOKIE_NAME = "mi_file_owner"
OWNER_COOKIE_MAX_AGE = 365 * 24 * 3600

_KANOPY_HEADERS = (
    "X-Kanopy-Internal-Authorization",
    "X-Forwarded-User-Token",
    "Authorization",
)


def kanopy_identity_enabled() -> bool:
    return parse_env_bool("MI_KANOPY_IDENTITY", False)


def kanopy_subject_from_token(raw: str) -> str:
    """Return the JWT ``sub`` claim. The mesh has already verified the signature."""
    token = raw.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Kanopy JWT must have 3 parts")
    payload = parts[1]
    padding = (-len(payload)) % 4
    try:
        decoded = base64.urlsafe_b64decode(payload + ("=" * padding))
        claims = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError("Kanopy JWT payload is not valid") from e
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Kanopy JWT is missing sub")
    return subject.strip()


def _cookie_owner(raw: str) -> str:
    try:
        return str(uuid.UUID(raw))
    except (ValueError, TypeError, AttributeError):
        return ""


def resolve_file_owner():
    """Return (owner, cookie_to_set).

    Cookie mode always yields an owner, minting one when the cookie is absent.
    Kanopy mode yields the JWT subject, or "" when the token is missing or invalid.
    """
    if kanopy_identity_enabled():
        raw = ""
        for name in _KANOPY_HEADERS:
            raw = request.headers.get(name) or ""
            if raw:
                break
        if not raw:
            return "", None
        try:
            return kanopy_subject_from_token(raw), None
        except ValueError:
            logger.warning("Kanopy identity header could not be decoded")
            return "", None

    existing = _cookie_owner(request.cookies.get(OWNER_COOKIE_NAME, ""))
    if existing:
        return existing, None
    minted = str(uuid.uuid4())
    return minted, minted


def attach_owner_cookie(response, cookie_value):
    """Set the owner cookie when cookie mode minted a new id."""
    if not cookie_value:
        return response
    response.set_cookie(
        OWNER_COOKIE_NAME,
        cookie_value,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="Strict",
        max_age=OWNER_COOKIE_MAX_AGE,
    )
    return response
