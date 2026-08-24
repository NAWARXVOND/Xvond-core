import pytest
from fastapi import HTTPException

from backend.app.core.module_access import (
    company_module_enabled,
    require_company_module,
)


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *args):
        return self

    def first(self):
        return self.result


class FakeDB:
    def __init__(self, result):
        self.result = result

    def query(self, model):
        return FakeQuery(self.result)


def test_company_module_enabled_requires_enabled_record():
    assert company_module_enabled(FakeDB(object()), 1, "tools") is True
    assert company_module_enabled(FakeDB(None), 1, "tools") is False


def test_require_company_module_rejects_missing_module():
    with pytest.raises(HTTPException) as exc:
        require_company_module(FakeDB(None), 1, "channels")

    assert exc.value.status_code == 403
    assert "channels" in exc.value.detail
