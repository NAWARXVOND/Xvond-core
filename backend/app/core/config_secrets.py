import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.config.settings import settings


SENSITIVE_WORDS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
    "client_secret",
    "auth_key",
)

ENCRYPTED_PREFIX = "xvond:enc:v1:"


def is_sensitive_key(key: str) -> bool:
    normalized = str(key).lower()
    return any(word in normalized for word in SENSITIVE_WORDS)


def _cipher() -> Fernet:
    source = settings.CONFIG_ENCRYPTION_KEY

    if not source and not settings.is_production:
        source = settings.JWT_SECRET

    if not source:
        raise RuntimeError("CONFIG_ENCRYPTION_KEY is required")

    key = base64.urlsafe_b64encode(
        hashlib.sha256(source.encode("utf-8")).digest()
    )
    return Fernet(key)


def _encrypt(value) -> str:
    if isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX):
        return value

    payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
    token = _cipher().encrypt(payload).decode("ascii")
    return ENCRYPTED_PREFIX + token


def _decrypt(value):
    if not isinstance(value, str) or not value.startswith(ENCRYPTED_PREFIX):
        return value

    token = value[len(ENCRYPTED_PREFIX):]

    try:
        payload = _cipher().decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise RuntimeError("Stored configuration secret cannot be decrypted") from exc

    return json.loads(payload.decode("utf-8"))


def protect_config(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if is_sensitive_key(key) and item not in (None, "", False):
                result[key] = _encrypt(item)
            else:
                result[key] = protect_config(item)
        return result

    if isinstance(value, list):
        return [protect_config(item) for item in value]

    return value


def reveal_config(value):
    if isinstance(value, dict):
        return {
            key: (
                _decrypt(item)
                if is_sensitive_key(key)
                else reveal_config(item)
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [reveal_config(item) for item in value]

    return value


def public_config(value):
    if isinstance(value, dict):
        return {
            key: public_config(item)
            for key, item in value.items()
            if not is_sensitive_key(key)
        }

    if isinstance(value, list):
        return [public_config(item) for item in value]

    return value


def configured_secret_fields(config: dict | None, prefix: str = "") -> list[str]:
    result = []

    for key, value in (config or {}).items():
        path = f"{prefix}.{key}" if prefix else str(key)

        if is_sensitive_key(key):
            if value not in (None, "", False):
                result.append(path)
            continue

        if isinstance(value, dict):
            result.extend(configured_secret_fields(value, path))

    return sorted(result)


def merge_config(existing: dict | None, incoming: dict | None) -> dict:
    result = dict(existing or {})

    if incoming is None:
        return protect_config(result)

    for key, value in incoming.items():
        if is_sensitive_key(key) and value in (None, ""):
            continue

        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value

    return protect_config(result)
