from backend.app.core.config_secrets import (
    configured_secret_fields,
    merge_config,
    public_config,
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
    current = {"access_token": "existing", "region": "me"}
    merged = merge_config(
        current,
        {"access_token": "", "region": "eu"},
    )

    assert merged["access_token"] == "existing"
    assert merged["region"] == "eu"
    assert configured_secret_fields(merged) == ["access_token"]
