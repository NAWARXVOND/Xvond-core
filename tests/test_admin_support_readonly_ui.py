from pathlib import Path


APP = Path("frontend/admin/app.js").read_text(encoding="utf-8")


def test_support_can_sign_in_to_internal_admin_surface():
    assert '"support"' in APP
    assert "XVOND_ADMIN_UI_ROLES" in APP
    assert "currentAdminUser" in APP
    assert "Read only" in APP


def test_support_company_view_uses_only_operator_safe_endpoints():
    block = APP.split("async function openSupportCompany", 1)[1].split("function openCreateCompany", 1)[0]
    assert "/admin/company-view/${companyId}" in block
    assert "/admin/operations/companies/${companyId}/usage" in block
    assert "/admin/operations/companies/${companyId}/external-unresolved" in block
    assert "/admin/operations/whatsapp/deliveries/unresolved" in block
    assert "/conversations" not in block
    assert "message.body" not in block
    assert "customer content is not exposed" in block


def test_support_ui_blocks_mutation_entry_points():
    assert "if(xvondSupportMode()){alert('Support access is read-only.');return}" in APP
    assert "openCreateCompany" in APP
    assert "openAddAIEmployee" in APP
    assert "openAgentTestChat" in APP
