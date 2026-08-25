let solutionsCatalog = null;
let solutionCompanies = [];

async function showSolutionsPage(button = null) {
    document.querySelectorAll(".page").forEach(item => item.classList.add("hidden"));
    document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
    document.getElementById("page-solutions").classList.remove("hidden");
    if (button) button.classList.add("active");
    document.getElementById("page-title").textContent = "Company Solutions";

    const [companiesData, catalog] = await Promise.all([
        api("/admin/companies"),
        api("/admin/solutions/catalog"),
    ]);
    solutionCompanies = companiesData.companies || [];
    solutionsCatalog = catalog;

    document.getElementById("solutions-company").innerHTML =
        solutionCompanies.map(item =>
            `<option value="${item.id}">${escapeAdmin(item.name)}</option>`
        ).join("");

    document.getElementById("service-catalog-grid").innerHTML =
        catalog.services.map(item => `
            <div class="agent">
                <h3>${escapeAdmin(item.name)}</h3>
                <p>${escapeAdmin(item.description)}</p>
                <span class="status status-active">${escapeAdmin(item.delivery_mode)}</span>
            </div>
        `).join("");

    await loadCompanySolutions();
}

async function loadCompanySolutions() {
    const companyId = document.getElementById("solutions-company").value;
    const target = document.getElementById("company-solutions-list");
    if (!companyId) {
        target.innerHTML = "<p>Create a company first.</p>";
        return;
    }

    const data = await api(`/admin/solutions/companies/${companyId}`);
    const items = data.solutions || [];
    target.innerHTML = items.length ? items.map(item => `
        <div class="agent">
            <h3>${escapeAdmin(item.name)}</h3>
            <p><strong>${escapeAdmin(item.service_name)}</strong></p>
            <p>Package: ${escapeAdmin(item.package_tier)} · Status: ${escapeAdmin(item.status)}</p>
            ${item.capabilities.length ? `<p>Capabilities: ${item.capabilities.map(escapeAdmin).join(", ")}</p>` : ""}
            ${item.channels.length ? `<p>Channels: ${item.channels.map(escapeAdmin).join(", ")}</p>` : ""}
            ${item.linked_agent_id ? `<p>Agent #${item.linked_agent_id}</p>` : ""}
        </div>
    `).join("") : "<p>No solutions assigned to this company.</p>";
}

function openCreateSolution() {
    if (!solutionsCatalog || !solutionCompanies.length) {
        alert("Create a company first.");
        return;
    }

    const companyOptions = solutionCompanies.map(item =>
        `<option value="${item.id}">${escapeAdmin(item.name)}</option>`
    ).join("");
    const serviceOptions = solutionsCatalog.services.map(item =>
        `<option value="${item.code}">${escapeAdmin(item.name)}</option>`
    ).join("");
    const packageOptions = solutionsCatalog.package_tiers.map(item =>
        `<option value="${item.code}">${escapeAdmin(item.name)}</option>`
    ).join("");
    const capabilities = solutionsCatalog.ai_employee_capabilities.map(item => `
        <label><input type="checkbox" name="solution-capability" value="${item.code}"> ${escapeAdmin(item.name)}</label>
    `).join("");
    const channels = solutionsCatalog.ai_employee_channels.map(item => `
        <label><input type="checkbox" name="solution-channel" value="${item.code}"> ${escapeAdmin(item.name)}</label>
    `).join("");

    openModal("Create Company Solution", `
        <div class="form-group">
            <label>Company</label>
            <select id="solution-company-id">${companyOptions}</select>
        </div>
        <div class="form-group">
            <label>Service</label>
            <select id="solution-service-code" onchange="toggleAIEmployeeFields()">${serviceOptions}</select>
        </div>
        <div class="form-group">
            <label>Solution / Employee Name</label>
            <input id="solution-name" placeholder="Customer Service AI Employee">
        </div>
        <div class="form-group">
            <label>Package</label>
            <select id="solution-package">${packageOptions}</select>
        </div>
        <div class="form-group">
            <label>Description</label>
            <textarea id="solution-description"></textarea>
        </div>
        <div id="ai-employee-fields" class="hidden">
            <div class="form-group">
                <label>Capabilities</label>
                <div style="display:grid;gap:8px">${capabilities}</div>
            </div>
            <div class="form-group">
                <label>Channels</label>
                <div style="display:grid;gap:8px">${channels}</div>
            </div>
            <div class="form-group">
                <label>AI Provider</label>
                <input id="solution-provider" value="groq">
            </div>
            <div class="form-group">
                <label>Model</label>
                <input id="solution-model" value="openai/gpt-oss-20b">
            </div>
            <div class="form-group">
                <label>System Prompt (optional)</label>
                <textarea id="solution-prompt" placeholder="Xvond will apply a safe business default when empty."></textarea>
            </div>
        </div>
        <button class="modal-submit" onclick="createSolution()">Create & Provision</button>
    `);
    toggleAIEmployeeFields();
}

function toggleAIEmployeeFields() {
    const value = document.getElementById("solution-service-code")?.value;
    document.getElementById("ai-employee-fields")?.classList.toggle(
        "hidden", value !== "ai_agents"
    );
}

function checkedValues(name) {
    return [...document.querySelectorAll(`input[name="${name}"]:checked`)]
        .map(item => item.value);
}

async function createSolution() {
    try {
        const companyId = document.getElementById("solution-company-id").value;
        const serviceCode = document.getElementById("solution-service-code").value;
        const name = document.getElementById("solution-name").value.trim();
        const packageTier = document.getElementById("solution-package").value;
        const description = document.getElementById("solution-description").value.trim();

        if (!name) throw new Error("Solution name is required");

        if (serviceCode === "ai_agents") {
            await api(`/admin/solutions/companies/${companyId}/ai-employee`, {
                method: "POST",
                body: JSON.stringify({
                    name,
                    description: description || null,
                    package_tier: packageTier,
                    provider: document.getElementById("solution-provider").value.trim(),
                    model: document.getElementById("solution-model").value.trim(),
                    system_prompt: document.getElementById("solution-prompt").value.trim() || null,
                    capabilities: checkedValues("solution-capability"),
                    channels: checkedValues("solution-channel"),
                }),
            });
        } else {
            await api(`/admin/solutions/companies/${companyId}`, {
                method: "POST",
                body: JSON.stringify({
                    service_code: serviceCode,
                    name,
                    package_tier: packageTier,
                    status: "discovery",
                    description: description || null,
                    configuration: {},
                }),
            });
        }

        closeModal();
        document.getElementById("solutions-company").value = companyId;
        await loadCompanySolutions();
    } catch (error) {
        alert(error.message);
    }
}

(function loadCompanyWorkspaceScripts() {
    if (document.querySelector('script[data-xvond-company-workspace]')) return;

    const workspace = document.createElement('script');
    workspace.src = '/static/admin/company_workspace.js';
    workspace.dataset.xvondCompanyWorkspace = '1';
    workspace.onload = () => {
        const automation = document.createElement('script');
        automation.src = '/static/admin/company_workspace_automation.js';
        automation.dataset.xvondCompanyWorkspaceAutomation = '1';
        document.body.appendChild(automation);
    };
    document.body.appendChild(workspace);
})();
