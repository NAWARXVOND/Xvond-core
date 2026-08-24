from backend.app.core.config_secrets import (
    ENCRYPTED_PREFIX,
    configured_secret_fields,
    merge_config,
    protect_config,
    public_config,
    reveal_config,
)


def test_public_config_removes_nested_secrets():
    value = {
        "phone_number_id": "123",
        "access_token": "secret-value",
        "nested": {
            "client_secret": "hidden",
            "region": "me",
        },
    }

    assert public_config(value) == {
        "phone_number_id": "123",
        "nested": {"region": "me"},
    }


def test_secret_metadata_and_merge_preserve_existing_value():
    current = protect_config(
        {"access_token": "existing", "region": "me"}
    )
    merged = merge_config(
        current,
        {"access_token": "", "region": "eu"},
    )

    assert merged["access_token"].startswith(ENCRYPTED_PREFIX)
    assert merged["access_token"] != "existing"
    assert reveal_config(merged)["access_token"] == "existing"
    assert merged["region"] == "eu"
    assert configured_secret_fields(merged) == ["access_token"]


def test_nested_secrets_round_trip_without_double_encryption():
    protected = protect_config(
        {
            "nested": {
                "client_secret": "hidden",
                "region": "me",
            }
        }
    )
    protected_again = protect_config(protected)

    assert protected_again == protected
    assert reveal_config(protected_again) == {
        "nested": {
            "client_secret": "hidden",
            "region": "me",
        }
    }
