const API = "";

let token = localStorage.getItem("xvond_admin_token");

let companiesCache = [];


function escapeAdmin(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}



function authHeaders() {
    return {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
    };
}


async function api(
    url,
    options = {}
) {

    const response = await fetch(
        API + url,
        {
            ...options,
            headers: {
                ...(options.headers || {}),
                ...(token
                    ? {"Authorization": `Bearer ${token}`}
                    : {}
                ),
                "Content-Type": "application/json",
            }
        }
    );

    if (response.status === 401) {
        logout();
        throw new Error("Authentication expired");
    }

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.detail || "Request failed"
        );
    }

    return data;
}


async function login() {

    const email =
        document.getElementById(
            "login-email"
        ).value;

    const password =
        document.getElementById(
            "login-password"
        ).value;

    const error =
        document.getElementById(
            "login-error"
        );

    error.textContent = "";

    try {

        const data = await api(
            "/auth/login",
            {
                method: "POST",
                body: JSON.stringify({
                    email,
                    password,
                }),
            }
        );

        if (
            !["super_admin", "xvond_admin"]
            .includes(data.user.role)
        ) {
            throw new Error(
                "Xvond admin account required"
            );
        }

        token = data.access_token;

        localStorage.setItem(
            "xvond_admin_token",
            token
        );

        localStorage.setItem(
            "xvond_admin_user",
            JSON.stringify(
                data.user
            )
        );

        startApp();

    } catch (e) {
        error.textContent = e.message;
    }
}


function logout() {

    localStorage.removeItem(
        "xvond_admin_token"
    );

    localStorage.removeItem(
        "xvond_admin_user"
    );

    token = null;

    document
        .getElementById("app")
        .classList.add("hidden");

    document
        .getElementById("login-screen")
        .classList.remove("hidden");
}


function startApp() {

    document
        .getElementById("login-screen")
        .classList.add("hidden");

    document
        .getElementById("app")
        .classList.remove("hidden");

    const user = JSON.parse(
        localStorage.getItem(
            "xvond_admin_user"
        ) || "{}"
    );

    document.getElementById(
        "current-user"
    ).textContent =
        user.email || "Xvond Admin";

    loadDashboard();
}


async function showPage(
    name,
    button = null
) {

    document
        .querySelectorAll(".page")
        .forEach(
            item => item.classList.add(
                "hidden"
            )
        );

    const page =
        document.getElementById(
            `page-${name}`
        );

    if (page) {
        page.classList.remove("hidden");
    }

    document
        .querySelectorAll(".nav-item")
        .forEach(
            item => item.classList.remove(
                "active"
            )
        );

    if (button) {
        button.classList.add("active");
    }

    const titles = {
        dashboard: "Dashboard",
        companies: "Companies",
        agents: "AI Agents",
        templates: "Agent Factory",
        providers: "AI Providers",
        modules: "Modules",
        "company-detail": "Company",
    };

    document.getElementById(
        "page-title"
    ).textContent =
        titles[name] || "Xvond";

    if (name === "dashboard") {
        await loadDashboard();
    }

    if (name === "companies") {
        await loadCompanies();
    }

    if (name === "agents") {
        await loadAgentCompanies();
    }

    if (name === "templates") {
        await loadTemplates();
    }

    if (name === "providers") {
        await loadProviders();
    }

    if (name === "modules") {
        await loadModules();
    }
}


async function loadDashboard() {

    try {

        const data = await api(
            "/admin/dashboard/summary"
        );

        const cards = [
            ["Companies", data.companies],
            ["Active Companies", data.active_companies],
            ["Users", data.users],
            ["AI Agents", data.agents],
            ["Active Agents", data.active_agents],
            ["Conversations", data.conversations],
            ["AI Requests", data.ai_requests],
            ["Tokens", data.total_tokens],
            ["AI Provider Cost", data.provider_cost],
            ["Subscriptions", data.active_subscriptions],
        ];

        document.getElementById(
            "dashboard-cards"
        ).innerHTML =
            cards.map(
                ([label, value]) => `
                <div class="card">
                    <div class="card-label">
                        ${label}
                    </div>

                    <div class="card-value">
                        ${value ?? 0}
                    </div>
                </div>
                `
            ).join("");

    } catch (e) {
        console.error(e);
    }
}


async function loadCompanies() {

    const data = await api(
        "/admin/companies"
    );

    companiesCache =
        data.companies || [];

    const table =
        document.getElementById(
            "companies-table"
        );

    table.innerHTML =
        companiesCache.map(
            company => `
            <tr>
                <td>${company.id}</td>

                <td>
                    <strong>
                        ${escapeAdmin(company.name)}
                    </strong>
                </td>

                <td>
                    <span class="
                        status
                        ${
                            company.active
                            ? "status-active"
                            : "status-inactive"
                        }
                    ">
                        ${
                            company.active
                            ? "Active"
                            : "Inactive"
                        }
                    </span>
                </td>

                <td>
                    ${
                        company.created_at
                        ? new Date(
                            company.created_at
                        ).toLocaleDateString()
                        : ""
                    }
                </td>

                <td>
                    <button
                        class="table-button"
                        onclick="openCompany(${company.id})"
                    >
                        Open
                    </button>
                </td>
            </tr>
            `
        ).join("");
}


function openCreateCompany() {

    openModal(
        "Create Company",
        `
        <div class="form-group">
            <label>Company Name</label>
            <input id="company-name">
        </div>

        <div class="form-group">
            <label>Owner Full Name</label>
            <input id="owner-name">
        </div>

        <div class="form-group">
            <label>Owner Email</label>
            <input
                id="owner-email"
                type="email"
            >
        </div>

        <div class="form-group">
            <label>Owner Password</label>
            <input
                id="owner-password"
                type="password"
            >
        </div>

        <button
            class="modal-submit"
            onclick="createCompany()"
        >
            Create Company
        </button>
        `
    );
}


async function createCompany() {

    try {

        const data = await api(
            "/admin/companies",
            {
                method: "POST",

                body: JSON.stringify({
                    name:
                        document.getElementById(
                            "company-name"
                        ).value,

                    owner_full_name:
                        document.getElementById(
                            "owner-name"
                        ).value,

                    owner_email:
                        document.getElementById(
                            "owner-email"
                        ).value,

                    owner_password:
                        document.getElementById(
                            "owner-password"
                        ).value,
                }),
            }
        );

        closeModal();

        await loadCompanies();

        await openCompany(
            data.company.id
        );

    } catch (e) {
        alert(e.message);
    }
}


async function openCompany(
    companyId
) {

    const data = await api(
        `/admin/company-view/${companyId}`
    );

    document
        .querySelectorAll(".page")
        .forEach(
            item => item.classList.add(
                "hidden"
            )
        );

    document
        .getElementById(
            "page-company-detail"
        )
        .classList.remove("hidden");

    document.getElementById(
        "page-title"
    ).textContent =
        data.company.name;

    const html = `
        <div class="company-header">

            <h2>${escapeAdmin(data.company.name)}</h2>

            <span class="
                status
                ${
                    data.company.active
                    ? "status-active"
                    : "status-inactive"
                }
            ">
                ${
                    data.company.active
                    ? "Active"
                    : "Inactive"
                }
            </span>

        </div>


        <div class="cards">

            <div class="card">
                <div class="card-label">
                    Agents
                </div>

                <div class="card-value">
                    ${data.agents.length}
                </div>
            </div>

            <div class="card">
                <div class="card-label">
                    Conversations
                </div>

                <div class="card-value">
                    ${data.analytics.conversations}
                </div>
            </div>

            <div class="card">
                <div class="card-label">
                    AI Requests
                </div>

                <div class="card-value">
                    ${data.analytics.ai_requests}
                </div>
            </div>

            <div class="card">
                <div class="card-label">
                    Provider Cost
                </div>

                <div class="card-value">
                    ${data.analytics.provider_cost}
                </div>
            </div>

        </div>


        <div class="panel detail-section">

            <h3>Company Setup</h3>

            <div style="
                display:flex;
                gap:10px;
                flex-wrap:wrap;
                margin-top:15px;
            ">

                <button onclick="openCompanyService('knowledge', ${companyId})">
                    Knowledge
                </button>

                <button onclick="openCompanyService('tools-service', ${companyId})">
                    Tools
                </button>

                <button onclick="openCompanyService('channels-service', ${companyId})">
                    Channels
                </button>

                <button onclick="openCompanyService('integrations-service', ${companyId})">
                    Integrations
                </button>

                <button onclick="openCompanyOperation('billing-service', ${companyId})">
                    Billing
                </button>

                <button onclick="openCompanyBusiness(${companyId})">
                    Business Operations
                </button>

                <button
                    onclick="
                        openCompanyAIConfiguration(
                            ${companyId}
                        )
                    "
                >
                    AI Configuration
                </button>

            </div>

        </div>


        <div
            id="company-production-status"
            class="panel detail-section"
            style="margin-top:20px"
        >
            <p>Checking production readiness...</p>
        </div>


        <div
            class="panel detail-section"
            style="margin-top:20px"
        >
            <div class="section-header">

                <div>
                    <h3>Agents</h3>
                </div>

                <div style="display:flex; gap:8px;">

                    <button
                        onclick="openCreateAgentFromTemplate(${companyId})"
                    >
                        + From Template
                    </button>

                    <button
                        onclick="openCreateAgent(${companyId})"
                    >
                        + Custom Agent
                    </button>

                </div>

            </div>

            <div class="agent-grid">

                ${
                    data.agents.length
                    ? data.agents.map(
                        agent => `
                        <div class="agent-card">

                            <h3>
                                ${escapeAdmin(agent.name)}
                            </h3>

                            <div class="meta">
                                ${escapeAdmin(agent.provider)}
                                /
                                ${escapeAdmin(agent.model)}
                            </div>

                            <div class="meta">
                                ${
                                    agent.enabled
                                    ? "Enabled"
                                    : "Disabled"
                                }
                            </div>

                            <div class="agent-actions">
                                <button
                                    class="table-button"
                                    onclick="openAgentTestChat(${companyId}, ${agent.id})"
                                >
                                    Test Chat
                                </button>
                                <button
                                    class="table-button"
                                    onclick="openEditAgent(${companyId}, ${agent.id})"
                                >
                                    Edit Agent
                                </button>
                            </div>

                        </div>
                        `
                    ).join("")
                    : "<p>No agents yet.</p>"
                }

            </div>
        </div>


        <div class="panel detail-section">

            <h3>Modules</h3>

            ${
                data.modules.length
                ? data.modules.map(
                    item => `
                    <span
                        class="status ${
                            item.enabled
                            ? "status-active"
                            : "status-inactive"
                        }"
                        style="margin-right:7px"
                    >
                        ${item.name}
                    </span>
                    `
                ).join("")
                : "<p>No modules enabled.</p>"
            }

        </div>


        <div class="panel detail-section">

            <h3>Users</h3>

            ${
                data.users.map(
                    user => `
                    <div>
                        ${escapeAdmin(user.full_name)}
                        —
                        ${escapeAdmin(user.email)}
                        —
                        ${escapeAdmin(user.role)}
                    </div>
                    `
                ).join("")
            }

        </div>
    `;

    queueMicrotask(() => {
        loadCompanyProductionStatus(
            companyId
        );
    });


    document.getElementById(
        "company-detail"
    ).innerHTML = html;
}


async function loadAgentCompanies() {

    const data = await api(
        "/admin/companies"
    );

    companiesCache =
        data.companies || [];

    const select =
        document.getElementById(
            "agents-company-filter"
        );

    select.innerHTML =
        companiesCache.map(
            company => `
                <option value="${company.id}">
                    ${escapeAdmin(company.name)}
                </option>
            `
        ).join("");

    if (companiesCache.length) {
        await loadAgentsForSelectedCompany();
    }
}


async function loadAgentsForSelectedCompany() {

    const select =
        document.getElementById(
            "agents-company-filter"
        );

    const companyId =
        select.value;

    if (!companyId) {
        return;
    }

    const data = await api(
        `/admin/companies/${companyId}/agents`
    );

    const grid =
        document.getElementById(
            "agents-grid"
        );

    grid.innerHTML =
        data.agents.length
        ? data.agents.map(
            agent => `
            <div class="agent-card">

                <h3>${escapeAdmin(agent.name)}</h3>

                <p>
                    ${escapeAdmin(
                        agent.description
                        || "AI Agent"
                    )}
                </p>

                <div class="meta">
                    Provider:
                    ${escapeAdmin(agent.provider)}
                </div>

                <div class="meta">
                    Model:
                    ${escapeAdmin(agent.model)}
                </div>

                <div class="meta">
                    ${
                        agent.enabled
                        ? "Enabled"
                        : "Disabled"
                    }
                </div>

                <div class="agent-actions">
                    <button
                        class="table-button"
                        onclick="openAgentTestChat(${companyId}, ${agent.id})"
                    >
                        Test Chat
                    </button>
                    <button
                        class="table-button"
                        onclick="openEditAgent(${companyId}, ${agent.id})"
                    >
                        Edit Agent
                    </button>
                </div>

            </div>
            `
        ).join("")
        : "<p>No agents found.</p>";
}


async function openCreateAgent(
    forcedCompanyId = null
) {

    if (!companiesCache.length) {

        const data = await api(
            "/admin/companies"
        );

        companiesCache =
            data.companies || [];
    }

    const options =
        companiesCache.map(
            company => `
            <option
                value="${company.id}"
                ${
                    forcedCompanyId
                    == company.id
                    ? "selected"
                    : ""
                }
            >
                ${escapeAdmin(company.name)}
            </option>
            `
        ).join("");

    openModal(
        "Create Custom AI Agent",
        `
        <div class="form-group">
            <label>Company</label>

            <select id="agent-company">
                ${options}
            </select>
        </div>

        <div class="form-group">
            <label>Agent Name</label>
            <input id="agent-name">
        </div>

        <div class="form-group">
            <label>Description</label>
            <input id="agent-description">
        </div>

        <div class="form-group">
            <label>Agent Type</label>

            <input
                id="agent-type"
                value="custom"
            >
        </div>

        <div class="form-group">
            <label>System Prompt</label>

            <textarea
                id="agent-prompt"
            ></textarea>
        </div>

        <div class="form-group">
            <label>Provider</label>

            <input
                id="agent-provider"
                value="mock"
            >
        </div>

        <div class="form-group">
            <label>Model</label>

            <input
                id="agent-model"
                value="test-model"
            >
        </div>

        <button
            class="modal-submit"
            onclick="createAgent()"
        >
            Create Agent
        </button>
        `
    );
}


async function createAgent() {

    const companyId =
        document.getElementById(
            "agent-company"
        ).value;

    try {

        const data = await api(
            `/admin/agent-factory/companies/${companyId}/custom-agent`,
            {
                method: "POST",

                body: JSON.stringify({

                    name:
                        document.getElementById(
                            "agent-name"
                        ).value,

                    description:
                        document.getElementById(
                            "agent-description"
                        ).value,

                    system_prompt:
                        document.getElementById(
                            "agent-prompt"
                        ).value,

                    provider:
                        document.getElementById(
                            "agent-provider"
                        ).value,

                    model:
                        document.getElementById(
                            "agent-model"
                        ).value,

                    agent_type:
                        document.getElementById(
                            "agent-type"
                        ).value,

                    settings: {},

                    capabilities: {},

                    customer_controls: {
                        can_enable_disable: true,
                        can_view_conversations: true,
                        can_view_usage: true,
                        can_edit_prompt: false,
                        can_change_provider: false,
                        can_change_model: false,
                    }
                }),
            }
        );

        closeModal();

        alert(
            `Agent created: ${data.name}`
        );

        await openCompany(
            Number(companyId)
        );

    } catch (e) {
        alert(e.message);
    }
}


async function loadTemplates() {

    const data = await api(
        "/admin/agent-factory/templates"
    );

    const grid =
        document.getElementById(
            "templates-grid"
        );

    grid.innerHTML =
        data.templates.length
        ? data.templates.map(
            item => `
            <div class="agent-card">

                <h3>${item.name}</h3>

                <p>
                    ${
                        item.description
                        || ""
                    }
                </p>

                <div class="meta">
                    Category:
                    ${item.category}
                </div>

                <div class="meta">
                    ${item.provider}
                    /
                    ${item.model}
                </div>

            </div>
            `
        ).join("")
        : "<p>No templates yet.</p>";
}


function openCreateTemplate() {

    openModal(
        "Create Agent Template",
        `
        <div class="form-group">
            <label>Name</label>
            <input id="template-name">
        </div>

        <div class="form-group">
            <label>Category</label>
            <input id="template-category">
        </div>

        <div class="form-group">
            <label>Description</label>
            <input id="template-description">
        </div>

        <div class="form-group">
            <label>System Prompt</label>

            <textarea
                id="template-prompt"
            ></textarea>
        </div>

        <div class="form-group">
            <label>Provider</label>

            <input
                id="template-provider"
                value="mock"
            >
        </div>

        <div class="form-group">
            <label>Model</label>

            <input
                id="template-model"
                value="test-model"
            >
        </div>

        <button
            class="modal-submit"
            onclick="createTemplate()"
        >
            Create Template
        </button>
        `
    );
}


async function createTemplate() {

    try {

        await api(
            "/admin/agent-factory/templates",
            {
                method: "POST",

                body: JSON.stringify({

                    name:
                        document.getElementById(
                            "template-name"
                        ).value,

                    category:
                        document.getElementById(
                            "template-category"
                        ).value,

                    description:
                        document.getElementById(
                            "template-description"
                        ).value,

                    default_system_prompt:
                        document.getElementById(
                            "template-prompt"
                        ).value,

                    default_provider:
                        document.getElementById(
                            "template-provider"
                        ).value,

                    default_model:
                        document.getElementById(
                            "template-model"
                        ).value,

                    default_config: {},
                }),
            }
        );

        closeModal();

        await loadTemplates();

    } catch (e) {
        alert(e.message);
    }
}


async function loadProviders() {

    try {

        const [
            runtime,
            catalog,
            modelsResult
        ] = await Promise.all([

            api(
                "/admin/providers/runtime"
            ),

            api(
                "/admin/providers/"
            ),

            api(
                "/admin/providers/models"
            )
        ]);


        const providers =
            catalog.providers || [];

        const models =
            modelsResult.models || [];


        document.getElementById(
            "providers-list"
        ).innerHTML = `

            <div
                class="section-header"
                style="margin-bottom:20px"
            >

                <div>
                    <h3>
                        Runtime Providers
                    </h3>

                    <p>
                        ${
                            (
                                runtime.loaded_providers
                                || []
                            ).join(", ")
                            || "None"
                        }
                    </p>
                </div>

                <div
                    style="
                        display:flex;
                        gap:8px;
                    "
                >

                    <button
                        onclick="
                            openCreateProvider()
                        "
                    >
                        + Provider
                    </button>

                    <button
                        onclick="
                            openCreateAIModel()
                        "
                    >
                        + Model
                    </button>

                </div>

            </div>


            <div class="detail-section">

                <h3>
                    Provider Catalog
                </h3>

                <div class="agent-grid">

                    ${
                        providers.length
                        ?
                        providers
                        .map(
                            provider => {

                                const providerModels =
                                    models.filter(
                                        model =>
                                            model.provider_name
                                            === provider.name
                                    );

                                return `
                                <div class="agent-card">

                                    <h3>
                                        ${escapeProduction(
                                            provider.display_name
                                        )}
                                    </h3>

                                    <div class="meta">
                                        ${escapeProduction(
                                            provider.name
                                        )}
                                    </div>

                                    <div class="meta">
                                        Runtime:
                                        ${
                                            provider.runtime_loaded
                                            ? "Loaded"
                                            : "Not Loaded"
                                        }
                                    </div>

                                    <div class="meta">
                                        Priority:
                                        ${provider.priority}
                                    </div>

                                    <div class="meta">
                                        Models:
                                        ${providerModels.length}
                                    </div>

                                </div>
                                `;
                            }
                        )
                        .join("")
                        :
                        "<p>No providers configured.</p>"
                    }

                </div>

            </div>


            <div
                class="detail-section"
                style="margin-top:25px"
            >

                <h3>
                    Model Catalog
                </h3>

                <div class="agent-grid">

                    ${
                        models.length
                        ?
                        models
                        .map(
                            model => `
                            <div class="agent-card">

                                <h3>
                                    ${escapeProduction(
                                        model.display_name
                                    )}
                                </h3>

                                <div class="meta">
                                    Provider:
                                    ${escapeProduction(
                                        model.provider_name
                                    )}
                                </div>

                                <div class="meta">
                                    Model:
                                    ${escapeProduction(
                                        model.model_name
                                    )}
                                </div>

                                <div class="meta">
                                    Input / 1M:
                                    ${model.input_price_per_million}
                                </div>

                                <div class="meta">
                                    Output / 1M:
                                    ${model.output_price_per_million}
                                </div>

                                <div class="meta">
                                    ${
                                        model.enabled
                                        ? "Enabled"
                                        : "Disabled"
                                    }
                                </div>

                            </div>
                            `
                        )
                        .join("")
                        :
                        `
                        <p>
                            No models registered yet.
                        </p>
                        `
                    }

                </div>

            </div>
        `;

    } catch (error) {

        alert(
            error.message
        );
    }
}


function openCreateProvider() {

    openModal(
        "Add AI Provider",
        `

        <div class="form-group">

            <label>
                Internal Name
            </label>

            <input
                id="provider-new-name"
                placeholder="openai"
            >

        </div>


        <div class="form-group">

            <label>
                Display Name
            </label>

            <input
                id="provider-new-display"
                placeholder="OpenAI"
            >

        </div>


        <div class="form-group">

            <label>
                Priority
            </label>

            <input
                id="provider-new-priority"
                type="number"
                value="100"
            >

        </div>


        <button
            class="modal-submit"
            onclick="
                createAIProvider()
            "
        >
            Add Provider
        </button>
        `
    );
}


async function createAIProvider() {

    try {

        await api(
            "/admin/providers/",
            {
                method: "POST",

                body: JSON.stringify({

                    name:
                        document.getElementById(
                            "provider-new-name"
                        ).value.trim(),

                    display_name:
                        document.getElementById(
                            "provider-new-display"
                        ).value.trim(),

                    priority:
                        Number(
                            document.getElementById(
                                "provider-new-priority"
                            ).value
                            || 100
                        )
                })
            }
        );


        closeModal();

        await loadProviders();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function openCreateAIModel() {

    try {

        const providersResult =
            await api(
                "/admin/providers/"
            );


        const providers =
            providersResult.providers || [];


        if (!providers.length) {

            alert(
                "Create a provider first."
            );

            return;
        }


        openModal(
            "Add AI Model",
            `

            <div class="form-group">

                <label>
                    Provider
                </label>

                <select
                    id="model-new-provider"
                >

                    ${
                        providers
                        .map(
                            provider => `
                            <option
                                value="${escapeAdmin(provider.name)}"
                            >
                                ${escapeProduction(
                                    provider.display_name
                                )}
                            </option>
                            `
                        )
                        .join("")
                    }

                </select>

            </div>


            <div class="form-group">

                <label>
                    Model ID
                </label>

                <input
                    id="model-new-name"
                    placeholder="Exact API model name"
                >

            </div>


            <div class="form-group">

                <label>
                    Display Name
                </label>

                <input
                    id="model-new-display"
                >

            </div>


            <div class="form-group">

                <label>
                    Input Price / 1M Tokens
                </label>

                <input
                    id="model-new-input-price"
                    type="number"
                    step="0.000001"
                    value="0"
                >

            </div>


            <div class="form-group">

                <label>
                    Output Price / 1M Tokens
                </label>

                <input
                    id="model-new-output-price"
                    type="number"
                    step="0.000001"
                    value="0"
                >

            </div>


            <button
                class="modal-submit"
                onclick="
                    createAIModel()
                "
            >
                Add Model
            </button>
            `
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function createAIModel() {

    try {

        await api(
            "/admin/providers/models",
            {
                method: "POST",

                body: JSON.stringify({

                    provider_name:
                        document.getElementById(
                            "model-new-provider"
                        ).value,

                    model_name:
                        document.getElementById(
                            "model-new-name"
                        ).value.trim(),

                    display_name:
                        document.getElementById(
                            "model-new-display"
                        ).value.trim(),

                    input_price_per_million:
                        Number(
                            document.getElementById(
                                "model-new-input-price"
                            ).value
                            || 0
                        ),

                    output_price_per_million:
                        Number(
                            document.getElementById(
                                "model-new-output-price"
                            ).value
                            || 0
                        )
                })
            }
        );


        closeModal();

        await loadProviders();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function loadModules() {

    const data = await api(
        "/admin/modules/"
    );

    document.getElementById(
        "modules-grid"
    ).innerHTML =
        data.modules.map(
            item => `
            <div class="agent-card">

                <h3>${item.name}</h3>

                <p>
                    ${escapeAdmin(item.description || "")}
                </p>

                <div class="meta">
                    Version:
                    ${item.version}
                </div>

                <div class="meta">
                    Status:
                    ${item.status}
                </div>

            </div>
            `
        ).join("");
}


function openModal(
    title,
    body
) {

    document.getElementById(
        "modal-title"
    ).textContent = title;

    document.getElementById(
        "modal-body"
    ).innerHTML = body;

    document.getElementById(
        "modal"
    ).classList.remove("hidden");
}


function closeModal() {

    document.getElementById(
        "modal"
    ).classList.add("hidden");
}


if (token) {
    startApp();
}



async function openCompanyService(
    page,
    companyId
) {
    sessionStorage.setItem(
        "xvondServiceCompanyId",
        String(companyId)
    );

    const button =
        document.getElementById(
            `nav-${page}`
        );

    const titles = {
        "knowledge": "Knowledge",
        "tools-service": "Tools",
        "channels-service": "Channels",
        "integrations-service": "Integrations"
    };

    await openServicePage(
        page,
        titles[page],
        button
    );
}




async function openCompanyOperation(
    page,
    companyId
) {
    sessionStorage.setItem(
        "xvondServiceCompanyId",
        String(companyId)
    );

    const button =
        document.getElementById(
            `nav-${page}`
        );

    await openOperationsPage(
        page,
        "Billing",
        button
    );
}


async function openCompanyBusiness(
    companyId
) {
    sessionStorage.setItem(
        "xvondServiceCompanyId",
        String(companyId)
    );

    const button =
        document.getElementById(
            "nav-business"
        );

    await openBusinessPage(
        button
    );
}


async function openCreateAgentFromTemplate(
    companyId
) {

    try {

        const result =
            await api(
                "/admin/agent-factory/templates"
            );

        const templates =
            (result.templates || [])
            .filter(
                item => item.enabled
            );

        if (!templates.length) {
            alert(
                "No enabled agent templates found."
            );
            return;
        }

        openModal(
            "Create Agent from Template",
            `

            <div class="form-group">
                <label>Service Template</label>

                <select id="template-agent-template">
                    ${
                        templates.map(
                            item => `
                            <option value="${item.id}">
                                ${item.name}
                                — ${item.category}
                            </option>
                            `
                        ).join("")
                    }
                </select>
            </div>


            <div class="form-group">
                <label>Agent Name</label>

                <input
                    id="template-agent-name"
                    placeholder="Optional custom name"
                >
            </div>


            <button
                class="modal-submit"
                onclick="
                    createAgentFromTemplate(
                        ${companyId}
                    )
                "
            >
                Create Agent
            </button>

            `
        );

    } catch (error) {
        alert(error.message);
    }
}


async function createAgentFromTemplate(
    companyId
) {

    try {

        const templateId =
            Number(
                document.getElementById(
                    "template-agent-template"
                ).value
            );

        const name =
            document.getElementById(
                "template-agent-name"
            ).value.trim();


        await api(
            `/admin/agent-factory/companies/${companyId}/from-template`,
            {
                method: "POST",

                body: JSON.stringify({
                    template_id: templateId,
                    name: name || null,
                    system_prompt: null,
                    provider: null,
                    model: null,
                    settings: {}
                })
            }
        );

        closeModal();

        await openCompany(
            companyId
        );

    } catch (error) {
        alert(error.message);
    }
}



// ============================================================
// XVOND PRODUCTION CONTROL
// ============================================================

async function loadCompanyProductionStatus(companyId) {

    const container =
        document.getElementById(
            "company-production-status"
        );

    if (!container) return;

    container.innerHTML =
        "<p>Checking production readiness...</p>";

    try {

        const result =
            await api(
                `/admin/production/companies/${companyId}/readiness`
            );

        const readyAgents =
            (result.agents || [])
            .filter(agent => agent.ready)
            .length;

        const totalAgents =
            (result.agents || []).length;

        const agentHtml =
            (result.agents || [])
            .map(agent => {

                const issues =
                    (agent.issues || [])
                    .map(
                        issue =>
                            `<li>${escapeProduction(issue)}</li>`
                    )
                    .join("");

                const channels =
                    (agent.channels || [])
                    .map(channel => `
                        <div style="
                            padding:6px 0;
                            font-size:13px;
                        ">
                            ${escapeProduction(channel.type)}
                            ?
                            ${
                                channel.configured
                                ? "Configured"
                                : "Missing Configuration"
                            }
                        </div>
                    `)
                    .join("");

                return `
                    <div
                        class="panel"
                        style="
                            margin-top:12px;
                            padding:15px;
                        "
                    >
                        <div style="
                            display:flex;
                            justify-content:space-between;
                            gap:15px;
                            align-items:center;
                        ">
                            <strong>
                                ${escapeProduction(agent.name)}
                            </strong>

                            <span>
                                ${
                                    agent.ready
                                    ? "READY"
                                    : "NOT READY"
                                }
                            </span>
                        </div>

                        <div style="
                            margin-top:10px;
                            font-size:13px;
                            line-height:1.8;
                        ">
                            Provider:
                            ${escapeProduction(agent.provider)}
                            /
                            ${escapeProduction(agent.model)}

                            <br>

                            Knowledge:
                            ${agent.knowledge_count}

                            <br>

                            Tools:
                            ${agent.tool_count}

                            <br>

                            ${channels}
                        </div>

                        ${
                            issues
                            ? `
                                <ul style="
                                    margin-top:10px;
                                ">
                                    ${issues}
                                </ul>
                            `
                            : ""
                        }
                    </div>
                `;
            })
            .join("");

        const companyIssues =
            (result.issues || [])
            .map(
                issue =>
                    `<li>${escapeProduction(issue)}</li>`
            )
            .join("");

        container.innerHTML = `

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                gap:20px;
                flex-wrap:wrap;
            ">

                <div>
                    <h3 style="margin:0">
                        Production Status
                    </h3>

                    <div style="margin-top:8px">
                        ${
                            result.ready
                            ? "READY FOR PRODUCTION"
                            : "SETUP REQUIRED"
                        }
                    </div>
                </div>

                <button
                    ${
                        result.ready
                        ? ""
                        : "disabled"
                    }
                    onclick="
                        activateProductionCompany(
                            ${companyId}
                        )
                    "
                >
                    Activate
                </button>

            </div>

            <div style="
                display:grid;
                grid-template-columns:
                    repeat(auto-fit,minmax(150px,1fr));
                gap:12px;
                margin-top:20px;
            ">

                <div class="stat-card">
                    <div>Subscription</div>
                    <strong>
                        ${
                            result.subscription_ready
                            ? "READY"
                            : "MISSING"
                        }
                    </strong>
                </div>

                <div class="stat-card">
                    <div>Modules</div>
                    <strong>
                        ${(result.modules || []).length}
                    </strong>
                </div>

                <div class="stat-card">
                    <div>Agents</div>
                    <strong>
                        ${readyAgents}/${totalAgents}
                    </strong>
                </div>

                <div class="stat-card">
                    <div>Integrations</div>
                    <strong>
                        ${(result.integrations || []).length}
                    </strong>
                </div>

            </div>

            ${
                companyIssues
                ? `
                    <div style="margin-top:18px">
                        <strong>Required:</strong>
                        <ul>
                            ${companyIssues}
                        </ul>
                    </div>
                `
                : ""
            }

            <div style="margin-top:20px">
                ${agentHtml}
            </div>
        `;

    } catch (error) {

        container.innerHTML = `
            <p>
                Production check failed:
                ${escapeProduction(error.message)}
            </p>
        `;
    }
}


async function activateProductionCompany(
    companyId
) {

    if (
        !confirm(
            "Activate this company for production?"
        )
    ) {
        return;
    }

    try {

        await api(
            `/admin/production/companies/${companyId}/activate`,
            {
                method: "POST"
            }
        );

        alert(
            "Company activated for production."
        );

        await loadCompanyProductionStatus(
            companyId
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


function escapeProduction(value) {

    const element =
        document.createElement("div");

    element.textContent =
        value ?? "";

    return element.innerHTML;
}



// ============================================================
// XVOND COMPANY AI CONFIGURATION
// ============================================================

let xvondAIConfiguration = {
    companyId: null,
    agents: [],
    providers: [],
    models: []
};


async function openCompanyAIConfiguration(
    companyId
) {

    try {

        const [
            agentsResult,
            runtimeResult,
            modelsResult
        ] = await Promise.all([

            api(
                `/admin/companies/${companyId}/agents`
            ),

            api(
                "/admin/providers/runtime"
            ),

            api(
                "/admin/providers/models"
            )
        ]);


        xvondAIConfiguration = {
            companyId:
                Number(companyId),

            agents:
                agentsResult.agents || [],

            providers:
                runtimeResult.loaded_providers || [],

            models:
                modelsResult.models || []
        };


        if (
            !xvondAIConfiguration.agents.length
        ) {

            alert(
                "Create an AI agent first."
            );

            return;
        }


        const productionProviders =
            xvondAIConfiguration.providers
            .filter(
                name =>
                    name !== "mock"
            );


        openModal(
            "AI Configuration",
            `

            <div class="form-group">

                <label>
                    Agent
                </label>

                <select
                    id="ai-config-agent"
                    onchange="
                        loadSelectedAgentAI()
                    "
                >

                    ${
                        xvondAIConfiguration
                        .agents
                        .map(
                            item => `
                            <option
                                value="${item.id}"
                            >
                                ${escapeProduction(
                                    item.name
                                )}
                            </option>
                            `
                        )
                        .join("")
                    }

                </select>

            </div>


            <div class="form-group">

                <label>
                    AI Provider
                </label>

                <select
                    id="ai-config-provider"
                    onchange="
                        refreshAIModelOptions()
                    "
                >

                    ${
                        productionProviders.length
                        ?
                        productionProviders
                        .map(
                            name => `
                            <option
                                value="${name}"
                            >
                                ${name}
                            </option>
                            `
                        )
                        .join("")
                        :
                        `
                        <option value="">
                            No production provider loaded
                        </option>
                        `
                    }

                </select>

            </div>


            <div class="form-group">

                <label>
                    Model
                </label>

                <input
                    id="ai-config-model"
                    list="ai-config-model-list"
                    placeholder="Enter model name"
                    autocomplete="off"
                >

                <datalist
                    id="ai-config-model-list"
                ></datalist>

            </div>


            <div
                id="ai-config-runtime-status"
                style="
                    margin:15px 0;
                    font-size:13px;
                "
            ></div>


            <button
                class="modal-submit"
                onclick="
                    saveCompanyAgentAI()
                "
            >
                Save AI Configuration
            </button>
            `
        );


        loadSelectedAgentAI();

    } catch (error) {

        alert(
            error.message
        );
    }
}


function loadSelectedAgentAI() {

    const agentElement =
        document.getElementById(
            "ai-config-agent"
        );

    if (!agentElement) {
        return;
    }


    const agent =
        xvondAIConfiguration
        .agents
        .find(
            item =>
                Number(item.id)
                === Number(
                    agentElement.value
                )
        );


    if (!agent) {
        return;
    }


    const providerElement =
        document.getElementById(
            "ai-config-provider"
        );


    if (
        providerElement
        && xvondAIConfiguration
            .providers
            .includes(
                agent.provider
            )
        && agent.provider !== "mock"
    ) {

        providerElement.value =
            agent.provider;
    }


    refreshAIModelOptions();


    const modelElement =
        document.getElementById(
            "ai-config-model"
        );


    if (modelElement) {

        modelElement.value =
            agent.model === "test-model"
            ? ""
            : (
                agent.model || ""
            );
    }
}


function refreshAIModelOptions() {

    const providerElement =
        document.getElementById(
            "ai-config-provider"
        );

    const list =
        document.getElementById(
            "ai-config-model-list"
        );

    const status =
        document.getElementById(
            "ai-config-runtime-status"
        );


    if (
        !providerElement
        || !list
    ) {
        return;
    }


    const provider =
        providerElement.value;


    const models =
        xvondAIConfiguration
        .models
        .filter(
            item =>
                item.provider_name
                === provider
                && item.enabled
        );


    list.innerHTML =
        models
        .map(
            item => `
            <option
                value="${escapeProduction(
                    item.model_name
                )}"
            >
                ${escapeProduction(
                    item.display_name
                )}
            </option>
            `
        )
        .join("");


    if (status) {

        status.innerHTML =
            provider
            ? (
                models.length
                ? `${models.length} model(s) registered for ${escapeProduction(provider)}.`
                : `Provider ${escapeProduction(provider)} is loaded. Enter the exact model name, or add it to AI Providers first.`
            )
            : "No production AI provider is loaded.";
    }
}


async function saveCompanyAgentAI() {

    try {

        const agentId =
            Number(
                document.getElementById(
                    "ai-config-agent"
                ).value
            );


        const provider =
            document.getElementById(
                "ai-config-provider"
            ).value.trim();


        const model =
            document.getElementById(
                "ai-config-model"
            ).value.trim();


        if (!provider) {

            alert(
                "Configure an AI provider API key first."
            );

            return;
        }


        if (!model) {

            alert(
                "Model is required."
            );

            return;
        }


        await api(
            `/admin/companies/${xvondAIConfiguration.companyId}/agents/${agentId}`,
            {
                method: "PUT",

                body: JSON.stringify({
                    provider:
                        provider,

                    model:
                        model
                })
            }
        );


        const agent =
            xvondAIConfiguration
            .agents
            .find(
                item =>
                    Number(item.id)
                    === agentId
            );


        if (agent) {
            agent.provider = provider;
            agent.model = model;
        }


        closeModal();


        await openCompany(
            xvondAIConfiguration.companyId
        );


        alert(
            "AI configuration saved."
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}



async function openEditAgent(companyId, agentId) {
    try {
        const [agentData, providerData] = await Promise.all([
            api(`/admin/companies/${companyId}/agents`),
            api("/admin/ai/providers"),
        ]);
        const agent = (agentData.agents || []).find(
            item => Number(item.id) === Number(agentId)
        );

        if (!agent) {
            throw new Error("AI Agent not found");
        }

        const providers = providerData.providers || [];
        const options = providers.map(provider => `
            <option value="${escapeAdmin(provider)}"
                ${provider === agent.provider ? "selected" : ""}>
                ${escapeAdmin(provider)}
            </option>
        `).join("");

        openModal("Edit Agent", `
            <div class="form-group">
                <label>Name</label>
                <input id="edit-agent-name" value="${escapeAdmin(agent.name)}">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="edit-agent-description">${escapeAdmin(agent.description || "")}</textarea>
            </div>
            <div class="form-group">
                <label>Provider</label>
                <select id="edit-agent-provider">${options}</select>
            </div>
            <div class="form-group">
                <label>Model</label>
                <input id="edit-agent-model" value="${escapeAdmin(agent.model)}">
                <small>Groq recommended: openai/gpt-oss-20b</small>
            </div>
            <div class="form-group">
                <label>System Prompt</label>
                <textarea id="edit-agent-prompt">${escapeAdmin(agent.system_prompt)}</textarea>
            </div>
            <button class="modal-submit"
                onclick="saveAgentEdit(${companyId}, ${agentId})">
                Save Agent
            </button>
        `);
    } catch (error) {
        alert(error.message);
    }
}


async function saveAgentEdit(companyId, agentId) {
    try {
        await api(`/admin/companies/${companyId}/agents/${agentId}`, {
            method: "PUT",
            body: JSON.stringify({
                name: document.getElementById("edit-agent-name").value.trim(),
                description: document.getElementById("edit-agent-description").value.trim(),
                provider: document.getElementById("edit-agent-provider").value,
                model: document.getElementById("edit-agent-model").value.trim(),
                system_prompt: document.getElementById("edit-agent-prompt").value.trim(),
            }),
        });

        closeModal();
        await openCompany(companyId);
    } catch (error) {
        alert(error.message);
    }
}


let agentTestConversationId = null;


function openAgentTestChat(companyId, agentId) {
    agentTestConversationId = null;
    openModal("Test Chat", `
        <div id="agent-test-transcript" class="agent-test-transcript">
            <p class="meta">Send a message to test the configured AI provider.</p>
        </div>
        <div class="form-group">
            <label>Message</label>
            <textarea id="agent-test-message" placeholder="Type a test message"></textarea>
        </div>
        <button id="agent-test-send" class="modal-submit"
            onclick="sendAgentTestMessage(${companyId}, ${agentId})">
            Send Message
        </button>
    `);
}


async function sendAgentTestMessage(companyId, agentId) {
    const input = document.getElementById("agent-test-message");
    const button = document.getElementById("agent-test-send");
    const transcript = document.getElementById("agent-test-transcript");
    const message = input.value.trim();

    if (!message) {
        alert("Message is required.");
        return;
    }

    button.disabled = true;
    button.textContent = "Sending...";

    try {
        const result = await api(
            `/admin/companies/${companyId}/agents/${agentId}/test-chat`,
            {
                method: "POST",
                body: JSON.stringify({
                    message,
                    conversation_id: agentTestConversationId,
                }),
            }
        );

        agentTestConversationId = result.conversation_id;
        transcript.innerHTML += `
            <div class="test-message test-user">
                <strong>You</strong>
                <div>${escapeAdmin(message)}</div>
            </div>
            <div class="test-message test-assistant">
                <strong>Agent</strong>
                <div>${escapeAdmin(result.response.content)}</div>
                <small>
                    ${Number(result.usage.total_tokens || 0)} tokens ·
                    ${Number(result.usage.latency_ms || 0)} ms
                </small>
            </div>
        `;
        input.value = "";
        transcript.scrollTop = transcript.scrollHeight;
    } catch (error) {
        transcript.innerHTML += `
            <div class="test-message test-error">
                <strong>Error</strong>
                <div>${escapeAdmin(error.message)}</div>
            </div>
        `;
    } finally {
        button.disabled = false;
        button.textContent = "Send Message";
    }
}
