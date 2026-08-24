import pytest

from backend.app.core.password_policy import validate_password
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
)


def test_access_token_round_trip():
    token = create_access_token(42)
    assert decode_access_token(token) == 42


def test_password_policy_accepts_strong_password():
    validate_password("StrongPass123")


@pytest.mark.parametrize(
    "password",
    ["short1", "onlyletters", "1234567890"],
)
def test_password_policy_rejects_weak_passwords(password):
    with pytest.raises(ValueError):
        validate_password(password)
