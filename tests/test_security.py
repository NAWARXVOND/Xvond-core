import pytest

from backend.app.core.password_policy import validate_password
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    decode_access_token_claims,
)


def test_access_token_round_trip():
    token = create_access_token(42)
    assert decode_access_token(token) == 42
    assert decode_access_token_claims(token)["ver"] == 0


def test_access_token_contains_requested_session_version():
    token = create_access_token(7, token_version=3)
    claims = decode_access_token_claims(token)
    assert claims["sub"] == "7"
    assert claims["ver"] == 3


def test_password_policy_accepts_strong_password():
    validate_password("StrongPass123")


@pytest.mark.parametrize(
    "password",
    ["short1", "onlyletters", "1234567890"],
)
def test_password_policy_rejects_weak_passwords(password):
    with pytest.raises(ValueError):
        validate_password(password)
