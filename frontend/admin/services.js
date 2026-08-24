let serviceCompanyId = null;
let serviceAgentId = null;


function installServicesUI() {

    const nav =
        document.querySelector(
            ".sidebar nav"
        );

    if (!nav) {
        return;
    }


    const items = [
        ["knowledge", "Knowledge"],
        ["tools-service", "Tools"],
        ["channels-service", "Channels"],
        ["integrations-service", "Integrations"],
    ];


    for (const [id, title] of items) {

        if (
            document.getElementById(
                `nav-${id}`
            )
        ) {
            continue;
        }

        const button =
            document.createElement(
                "button"
            );

        button.id =
            `nav-${id}`;

        button.className =
            "nav-item";

        button.textContent =
            title;

        button.onclick =
            () => openServicePage(
                id,
                title,
                button
            );

        nav.appendChild(
            button
        );
    }


    const main =
        document.querySelector(
            ".main"
        );


    for (const [id, title] of items) {

        if (
            document.getElementById(
                `page-${id}`
            )
        ) {
            continue;
        }

        const section =
            document.createElement(
                "section"
            );

        section.id =
            `page-${id}`;

        section.className =
            "page hidden";

        section.innerHTML = `

            <div class="section-header">

                <div>
                    <h2>${title}</h2>

                    <p>
                        Manage ${title}
                        for Xvond customer companies.
                    </p>
                </div>

            </div>

            <div class="panel">

                <div class="form-group">

                    <label>
                        Company
                    </label>

                    <select
                        id="${id}-company"
                        onchange="
                            serviceCompanyChanged(
                                '${id}'
                            )
                        "
                    >
                    </select>

                </div>

            </div>

            <div
                id="${id}-content"
                style="margin-top:20px"
            >
            </div>
        `;

        main.appendChild(
            section
        );
    }
}


async function openServicePage(
    id,
    title,
    button
) {

    document
        .querySelectorAll(
            ".page"
        )
        .forEach(
            item =>
                item.classList.add(
                    "hidden"
                )
        );


    document
        .querySelectorAll(
            ".nav-item"
        )
        .forEach(
            item =>
                item.classList.remove(
                    "active"
                )
        );


    document.getElementById(
        `page-${id}`
    ).classList.remove(
        "hidden"
    );


    button.classList.add(
        "active"
    );


    document.getElementById(
        "page-title"
    ).textContent =
        title;


    await populateServiceCompanies(
        id
    );


    await serviceCompanyChanged(
        id
    );
}


async function populateServiceCompanies(
    id
) {

    const result =
        await api(
            "/admin/companies"
        );


    const companies =
        result.companies || [];


    const select =
        document.getElementById(
            `${id}-company`
        );


    select.innerHTML =
        companies.map(
            company => `

            <option value="${company.id}">
                ${escapeService(
                    company.name
                )}
            </option>

            `
        ).join("");


    if (companies.length) {

        const preferredCompanyId =
            sessionStorage.getItem(
                "xvondServiceCompanyId"
            );

        const exists =
            preferredCompanyId
            && companies.some(
                company =>
                    String(company.id)
                    === String(preferredCompanyId)
            );

        select.value =
            exists
            ? preferredCompanyId
            : companies[0].id;

        sessionStorage.removeItem(
            "xvondServiceCompanyId"
        );
    }
}


async function serviceCompanyChanged(
    id
) {

    const select =
        document.getElementById(
            `${id}-company`
        );


    if (
        !select
        || !select.value
    ) {
        return;
    }


    serviceCompanyId =
        Number(
            select.value
        );


    if (id === "knowledge") {
        await loadKnowledgePage();
    }


    if (id === "tools-service") {
        await loadToolsPage();
    }


    if (id === "channels-service") {
        await loadChannelsPage();
    }


    if (
        id
        === "integrations-service"
    ) {
        await loadIntegrationsPage();
    }
}


async function getCompanyAgents() {

    const result =
        await api(
            `/admin/companies/${serviceCompanyId}/agents`
        );


    return result.agents || [];
}


function agentOptions(
    agents
) {

    return agents.map(
        agent => `

        <option value="${agent.id}">
            ${escapeService(
                agent.name
            )}
        </option>

        `
    ).join("");
}


// ============================================================
// KNOWLEDGE PAGE
// ============================================================

async function loadKnowledgePage() {

    try {

        const [result, status] = await Promise.all([
            api(
                `/admin/knowledge/companies/${serviceCompanyId}/documents`
            ),
            api(
                `/admin/knowledge/companies/${serviceCompanyId}/status`
            )
        ]);

        const documents = result.documents || [];

        const content =
            document.getElementById(
                "knowledge-content"
            );

        content.innerHTML = `

            <div class="panel">

                <div class="section-header">

                    <div>
                        <h3>Company Knowledge</h3>

                        <p>
                            ${status.enabled_documents || 0}
                            enabled documents ?
                            ${status.chunks || 0}
                            indexed chunks
                        </p>
                    </div>

                    <div
                        style="
                            display:flex;
                            gap:8px;
                            flex-wrap:wrap;
                        "
                    >
                        <button
                            class="table-button"
                            onclick="reindexCompanyKnowledge()"
                        >
                            Reindex
                        </button>

                        <button
                            onclick="createCompanyKnowledge()"
                        >
                            + Add Knowledge
                        </button>
                    </div>

                </div>

                ${
                    documents.length
                    ?
                    documents.map(item => `

                        <div
                            class="agent-card"
                            style="margin-bottom:12px"
                        >

                            <div
                                style="
                                    display:flex;
                                    justify-content:space-between;
                                    gap:12px;
                                    align-items:flex-start;
                                "
                            >
                                <div>
                                    <h3>
                                        ${escapeService(item.title)}
                                    </h3>

                                    <div class="meta">
                                        Type:
                                        ${escapeService(item.source_type)}
                                        ?
                                        Status:
                                        <strong>
                                            ${item.enabled ? "Enabled" : "Disabled"}
                                        </strong>
                                    </div>
                                </div>
                            </div>

                            <p
                                style="
                                    white-space:pre-wrap;
                                    max-height:180px;
                                    overflow:auto;
                                "
                            >
                                ${escapeService(item.content)}
                            </p>

                            <div
                                style="
                                    display:flex;
                                    gap:8px;
                                    flex-wrap:wrap;
                                "
                            >

                                <button
                                    class="table-button"
                                    onclick="
                                        editCompanyKnowledge(${item.id})
                                    "
                                >
                                    Edit
                                </button>

                                <button
                                    class="table-button"
                                    onclick="
                                        connectKnowledgeToAgent(${item.id})
                                    "
                                >
                                    Connect to Agent
                                </button>

                                <button
                                    class="table-button"
                                    onclick="
                                        showKnowledgeConnections(
                                            ${item.id},
                                            '${escapeAttributeService(item.title)}'
                                        )
                                    "
                                >
                                    Connections
                                </button>

                                <button
                                    class="table-button"
                                    onclick="
                                        toggleCompanyKnowledge(
                                            ${item.id},
                                            ${!item.enabled}
                                        )
                                    "
                                >
                                    ${
                                        item.enabled
                                        ? "Disable"
                                        : "Enable"
                                    }
                                </button>

                                <button
                                    class="table-button"
                                    onclick="
                                        deleteCompanyKnowledge(${item.id})
                                    "
                                >
                                    Delete
                                </button>

                            </div>

                        </div>

                    `).join("")
                    :
                    `
                        <p>
                            No company knowledge yet.
                        </p>
                    `
                }

            </div>
        `;

    } catch (error) {
        alert(error.message);
    }
}


function createCompanyKnowledge() {

    openModal(
        "Add Knowledge",
        `

        <div class="form-group">

            <label>
                Title
            </label>

            <input
                id="service-knowledge-title"
            >

        </div>


        <div class="form-group">

            <label>
                Content
            </label>

            <textarea
                id="service-knowledge-content"
                style="min-height:250px"
            ></textarea>

        </div>


        <button
            class="modal-submit"
            onclick="
                saveCompanyKnowledge()
            "
        >
            Save
        </button>
        `
    );
}


async function saveCompanyKnowledge() {

    try {

        await api(
            `/admin/knowledge/companies/${serviceCompanyId}/documents`,
            {
                method: "POST",

                body: JSON.stringify({

                    title:
                        document.getElementById(
                            "service-knowledge-title"
                        ).value,

                    source_type:
                        "text",

                    content:
                        document.getElementById(
                            "service-knowledge-content"
                        ).value
                })
            }
        );


        closeModal();

        await loadKnowledgePage();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function editCompanyKnowledge(
    documentId
) {

    try {

        const item =
            await api(
                `/admin/knowledge/companies/${serviceCompanyId}/documents/${documentId}`
            );


        openModal(
            "Edit Knowledge",
            `

            <div class="form-group">

                <label>
                    Title
                </label>

                <input
                    id="service-edit-title"
                    value="${escapeAttributeService(
                        item.title
                    )}"
                >

            </div>


            <div class="form-group">

                <label>
                    Content
                </label>

                <textarea
                    id="service-edit-content"
                    style="min-height:250px"
                >${escapeTextareaService(
                    item.content
                )}</textarea>

            </div>


            <button
                class="modal-submit"
                onclick="
                    saveCompanyKnowledgeEdit(
                        ${documentId}
                    )
                "
            >
                Save Changes
            </button>
            `
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function saveCompanyKnowledgeEdit(
    documentId
) {

    try {

        await api(
            `/admin/knowledge/companies/${serviceCompanyId}/documents/${documentId}`,
            {
                method: "PATCH",

                body: JSON.stringify({

                    title:
                        document.getElementById(
                            "service-edit-title"
                        ).value,

                    content:
                        document.getElementById(
                            "service-edit-content"
                        ).value
                })
            }
        );


        closeModal();

        await loadKnowledgePage();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function deleteCompanyKnowledge(
    documentId
) {

    if (
        !confirm(
            "Delete this knowledge permanently?"
        )
    ) {
        return;
    }


    try {

        await api(
            `/admin/knowledge/companies/${serviceCompanyId}/documents/${documentId}`,
            {
                method: "DELETE"
            }
        );


        await loadKnowledgePage();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function connectKnowledgeToAgent(
    documentId
) {

    const agents =
        await getCompanyAgents();


    if (!agents.length) {

        alert(
            "Create an agent first."
        );

        return;
    }


    openModal(
        "Connect Knowledge to Agent",
        `

        <div class="form-group">

            <label>
                Agent
            </label>

            <select
                id="knowledge-agent-select"
            >
                ${agentOptions(
                    agents
                )}
            </select>

        </div>


        <button
            class="modal-submit"
            onclick="
                confirmConnectKnowledge(
                    ${documentId}
                )
            "
        >
            Connect
        </button>
        `
    );
}


async function confirmConnectKnowledge(
    documentId
) {

    try {

        const agentId =
            document.getElementById(
                "knowledge-agent-select"
            ).value;


        await api(
            `/admin/knowledge/agents/${agentId}/documents/${documentId}`,
            {
                method: "POST"
            }
        );


        closeModal();

        alert(
            "Knowledge connected."
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}




// ============================================================
// KNOWLEDGE PRODUCTION CONTROLS
// ============================================================

async function toggleCompanyKnowledge(documentId, enabled) {
    try {
        await api(
            `/admin/knowledge/companies/${serviceCompanyId}/documents/${documentId}`,
            {
                method: "PATCH",
                body: JSON.stringify({
                    enabled: enabled
                })
            }
        );

        await loadKnowledgePage();

    } catch (error) {
        alert(error.message);
    }
}


async function reindexCompanyKnowledge() {
    try {
        const result = await api(
            `/admin/knowledge/companies/${serviceCompanyId}/reindex`,
            {
                method: "POST"
            }
        );

        alert(
            `Knowledge reindexed.\nDocuments: ${result.documents}\nChunks: ${result.chunks}`
        );

        await loadKnowledgePage();

    } catch (error) {
        alert(error.message);
    }
}


async function showKnowledgeConnections(documentId, title) {
    try {
        const agents = await getCompanyAgents();

        const rows = [];

        for (const agent of agents) {
            const result = await api(
                `/admin/knowledge/agents/${agent.id}/documents`
            );

            const found = (result.documents || []).find(
                item => Number(item.id) === Number(documentId)
            );

            if (found && found.connected) {
                rows.push(agent);
            }
        }

        openModal(
            "Knowledge Connections",
            `
                <h3>${escapeService(title)}</h3>

                ${
                    rows.length
                    ?
                    rows.map(agent => `
                        <div
                            class="agent-card"
                            style="margin-bottom:10px"
                        >
                            <strong>
                                ${escapeService(agent.name)}
                            </strong>

                            <div style="margin-top:8px">
                                <button
                                    class="table-button"
                                    onclick="
                                        disconnectKnowledgeFromAgent(
                                            ${agent.id},
                                            ${documentId}
                                        )
                                    "
                                >
                                    Disconnect
                                </button>
                            </div>
                        </div>
                    `).join("")
                    :
                    `<p>No agents connected.</p>`
                }
            `
        );

    } catch (error) {
        alert(error.message);
    }
}


async function disconnectKnowledgeFromAgent(agentId, documentId) {
    if (!confirm("Disconnect this knowledge from the agent?")) {
        return;
    }

    try {
        await api(
            `/admin/knowledge/agents/${agentId}/documents/${documentId}`,
            {
                method: "DELETE"
            }
        );

        closeModal();
        await loadKnowledgePage();

    } catch (error) {
        alert(error.message);
    }
}


// ============================================================
// TOOLS PAGE
// ============================================================


async function loadToolsPage() {

    try {

        const toolsResult =
            await api("/admin/tools/");

        const agents =
            await getCompanyAgents();

        const content =
            document.getElementById(
                "tools-service-content"
            );

        if (!agents.length) {

            content.innerHTML = `
                <div class="panel">
                    <p>
                        Create an AI Agent for this company first.
                    </p>
                </div>
            `;

            return;
        }

        const selected =
            document.getElementById(
                "tools-agent-select"
            );

        const previousAgentId =
            selected
            ? Number(selected.value)
            : serviceAgentId;

        serviceAgentId =
            agents.some(
                a => Number(a.id) === Number(previousAgentId)
            )
            ? Number(previousAgentId)
            : Number(agents[0].id);

        content.innerHTML = `

            <div class="panel">

                <div class="form-group">

                    <label>Agent</label>

                    <select
                        id="tools-agent-select"
                        onchange="
                            serviceAgentId =
                                Number(this.value);
                            loadAgentToolAssignments();
                        "
                    >
                        ${agents.map(agent => `
                            <option
                                value="${agent.id}"
                                ${
                                    Number(agent.id)
                                    === Number(serviceAgentId)
                                    ? "selected"
                                    : ""
                                }
                            >
                                ${escapeService(agent.name)}
                            </option>
                        `).join("")}
                    </select>

                </div>

                <div id="tools-assignment-content">
                    Loading tools...
                </div>

            </div>
        `;

        await loadAgentToolAssignments();

    } catch (error) {
        alert(error.message);
    }
}


async function loadAgentToolAssignments() {

    try {

        const [
            toolsResult,
            assignmentsResult
        ] = await Promise.all([
            api("/admin/tools/"),
            api(
                `/admin/tools/agents/${serviceAgentId}/assignments`
            )
        ]);

        const tools =
            toolsResult.tools || [];

        const assignments =
            assignmentsResult.tools || [];

        const assignmentMap =
            new Map(
                assignments.map(
                    item => [
                        item.tool_name,
                        item
                    ]
                )
            );

        const content =
            document.getElementById(
                "tools-assignment-content"
            );

        content.innerHTML = `

            <div class="section-header">
                <div>
                    <h3>Available Tools</h3>
                    <p>
                        Give an agent abilities
                        to perform business actions.
                    </p>
                </div>
            </div>

            <div class="agent-grid">

                ${tools.map(tool => {

                    const assignment =
                        assignmentMap.get(
                            tool.name
                        );

                    return `

                        <div class="agent-card">

                            <h3>
                                ${escapeService(tool.name)}
                            </h3>

                            <p>
                                ${escapeService(
                                    tool.description || ""
                                )}
                            </p>

                            ${
                                assignment
                                ?
                                `
                                    <div class="meta">
                                        Status:
                                        <strong>
                                            ${
                                                assignment.enabled
                                                ? "Enabled"
                                                : "Disabled"
                                            }
                                        </strong>
                                    </div>

                                    <div class="meta">
                                        Config:
                                        ${escapeService(
                                            JSON.stringify(
                                                assignment.config || {}
                                            )
                                        )}
                                    </div>

                                    <div
                                        style="
                                            display:flex;
                                            gap:8px;
                                            flex-wrap:wrap;
                                            margin-top:12px;
                                        "
                                    >

                                        <button
                                            class="table-button"
                                            onclick="
                                                toggleAgentTool(
                                                    '${escapeAttributeService(tool.name)}',
                                                    ${!assignment.enabled}
                                                )
                                            "
                                        >
                                            ${
                                                assignment.enabled
                                                ? "Disable"
                                                : "Enable"
                                            }
                                        </button>

                                        <button
                                            class="table-button"
                                            onclick="
                                                openToolConfig(
                                                    '${escapeAttributeService(tool.name)}'
                                                )
                                            "
                                        >
                                            Edit Config
                                        </button>

                                        <button
                                            class="table-button"
                                            onclick="
                                                unassignAgentTool(
                                                    '${escapeAttributeService(tool.name)}'
                                                )
                                            "
                                        >
                                            Unassign
                                        </button>

                                    </div>
                                `
                                :
                                `
                                    <button
                                        onclick="
                                            assignAgentTool(
                                                '${escapeAttributeService(tool.name)}'
                                            )
                                        "
                                    >
                                        Assign to Agent
                                    </button>
                                `
                            }

                        </div>
                    `;

                }).join("")}

            </div>
        `;

    } catch (error) {
        alert(error.message);
    }
}


async function assignAgentTool(toolName) {

    try {

        await api(
            `/admin/tools/agents/${serviceAgentId}/${encodeURIComponent(toolName)}`,
            {
                method: "POST",
                body: JSON.stringify({
                    config: {}
                })
            }
        );

        await loadAgentToolAssignments();

    } catch (error) {
        alert(error.message);
    }
}


async function toggleAgentTool(
    toolName,
    enabled
) {

    try {

        await api(
            `/admin/tools/agents/${serviceAgentId}/${encodeURIComponent(toolName)}`,
            {
                method: "PATCH",
                body: JSON.stringify({
                    enabled: enabled
                })
            }
        );

        await loadAgentToolAssignments();

    } catch (error) {
        alert(error.message);
    }
}


async function openToolConfig(toolName) {

    try {

        const result =
            await api(
                `/admin/tools/agents/${serviceAgentId}/assignments`
            );

        const assignment =
            (result.tools || []).find(
                item =>
                    item.tool_name === toolName
            );

        if (!assignment) {
            alert("Tool is not assigned.");
            return;
        }

        openModal(
            `Tool Config: ${escapeService(toolName)}`,
            `

                <div class="form-group">

                    <label>
                        Configuration JSON
                    </label>

                    <textarea
                        id="tool-config-json"
                        rows="12"
                        spellcheck="false"
                    >${escapeService(
                        JSON.stringify(
                            assignment.config || {},
                            null,
                            2
                        )
                    )}</textarea>

                </div>

                <button
                    class="modal-submit"
                    onclick="
                        saveToolConfig(
                            '${escapeAttributeService(toolName)}'
                        )
                    "
                >
                    Save Configuration
                </button>
            `
        );

    } catch (error) {
        alert(error.message);
    }
}


async function saveToolConfig(toolName) {

    try {

        const raw =
            document.getElementById(
                "tool-config-json"
            ).value.trim();

        let config = {};

        if (raw) {
            try {
                config = JSON.parse(raw);
            } catch {
                alert(
                    "Configuration must be valid JSON."
                );
                return;
            }
        }

        await api(
            `/admin/tools/agents/${serviceAgentId}/${encodeURIComponent(toolName)}`,
            {
                method: "PATCH",
                body: JSON.stringify({
                    config: config
                })
            }
        );

        closeModal();

        await loadAgentToolAssignments();

    } catch (error) {
        alert(error.message);
    }
}


async function unassignAgentTool(
    toolName
) {

    if (
        !confirm(
            `Unassign ${toolName} from this agent?`
        )
    ) {
        return;
    }

    try {

        await api(
            `/admin/tools/agents/${serviceAgentId}/${encodeURIComponent(toolName)}`,
            {
                method: "DELETE"
            }
        );

        await loadAgentToolAssignments();

    } catch (error) {
        alert(error.message);
    }
}


// ============================================================
// CHANNELS PAGE - PRODUCTION CONFIGURATION
// ============================================================

let xvondLoadedChannels = [];

const XVOND_CHANNELS = {
    website: {
        label: "Website Chat",
        fields: [
            ["site_url", "Website URL", "text"],
            ["widget_key", "Widget Key", "text"]
        ]
    },

    whatsapp: {
        label: "WhatsApp",
        fields: [
            ["phone_number_id", "Phone Number ID", "text"],
            ["access_token", "Access Token", "password"],
            ["verify_token", "Verify Token", "password"],
            ["app_secret", "App Secret", "password"]
        ]
    },

    voice: {
        label: "Voice",
        fields: [
            ["provider", "Voice Provider", "text"],
            ["phone_number", "Phone Number", "text"],
            ["account_id", "Account / Project ID", "text"],
            ["auth_token", "Auth Token", "password"]
        ]
    },

    telegram: {
        label: "Telegram",
        fields: [
            ["bot_token", "Bot Token", "password"]
        ]
    },

    custom: {
        label: "Custom Channel",
        fields: [
            ["endpoint", "Endpoint URL", "text"],
            ["auth_token", "Authentication Token", "password"]
        ]
    }
};


function productionFieldsHtml(
    definition,
    prefix,
    values = {}
) {

    return (definition.fields || [])
        .map(field => {

            const [
                key,
                label,
                type
            ] = field;

            const value =
                values[key] || "";

            return `
                <div class="form-group">
                    <label>
                        ${escapeService(label)}
                    </label>

                    <input
                        id="${prefix}-${key}"
                        type="${type}"
                        value="${escapeAttributeService(
                            value
                        )}"
                        autocomplete="off"
                    >
                </div>
            `;
        })
        .join("");
}


function readProductionFields(
    definition,
    prefix
) {

    const config = {};

    for (
        const [key] of definition.fields || []
    ) {

        const element =
            document.getElementById(
                `${prefix}-${key}`
            );

        if (
            element
            && element.value.trim()
        ) {
            config[key] =
                element.value.trim();
        }
    }

    return config;
}


function safeProductionConfig(
    config
) {

    const hiddenWords = [
        "token",
        "secret",
        "password",
        "key",
        "auth"
    ];

    const safe = {};

    for (
        const [key, value]
        of Object.entries(config || {})
    ) {

        const lower =
            key.toLowerCase();

        safe[key] =
            hiddenWords.some(
                word =>
                    lower.includes(word)
            )
            ? (
                value
                ? "Configured"
                : "Missing"
            )
            : value;
    }

    return safe;
}


async function refreshProductionStatusIfVisible() {

    if (
        typeof loadCompanyProductionStatus
        === "function"
        && serviceCompanyId
    ) {
        try {
            await loadCompanyProductionStatus(
                serviceCompanyId
            );
        } catch (_) {}
    }
}



async function loadChannelsPage() {

    try {

        const agents =
            await getCompanyAgents();

        const result =
            await api(
                `/admin/channels/companies/${serviceCompanyId}`
            );

        const channels =
            result.channels || [];

        const content =
            document.getElementById(
                "channels-service-content"
            );

        content.innerHTML = `

            <div class="panel">

                <div class="section-header">

                    <div>
                        <h3>Agent Channels</h3>
                        <p>
                            Configure customer
                            communication channels.
                        </p>
                    </div>

                    <button
                        onclick="openCreateChannel()"
                        ${agents.length ? "" : "disabled"}
                    >
                        + Add Channel
                    </button>

                </div>

                ${
                    !agents.length
                    ?
                    `
                        <p>
                            Create an AI Agent
                            for this company first.
                        </p>
                    `
                    :
                    channels.length
                    ?
                    `
                        <div class="agent-grid">

                            ${channels.map(item => {

                                const agent =
                                    agents.find(
                                        a =>
                                            Number(a.id)
                                            === Number(item.agent_id)
                                    );

                                const type =
                                    String(
                                        item.channel_type || ""
                                    ).toLowerCase();

                                return `

                                    <div class="agent-card">

                                        <h3>
                                            ${escapeService(
                                                item.channel_type
                                            )}
                                        </h3>

                                        <div class="meta">
                                            Agent:
                                            <strong>
                                                ${escapeService(
                                                    agent
                                                    ? agent.name
                                                    : `#${item.agent_id}`
                                                )}
                                            </strong>
                                        </div>

                                        <div class="meta">
                                            Status:
                                            <strong>
                                                ${
                                                    item.enabled
                                                    ? "Enabled"
                                                    : "Disabled"
                                                }
                                            </strong>
                                        </div>

                                        <div class="meta">
                                            Config:
                                            ${escapeService(
                                                JSON.stringify(
                                                    item.config || {}
                                                )
                                            )}
                                        </div>

                                        <div
                                            style="
                                                display:flex;
                                                gap:8px;
                                                flex-wrap:wrap;
                                                margin-top:12px;
                                            "
                                        >

                                            <button
                                                class="table-button"
                                                onclick="
                                                    toggleChannel(
                                                        ${item.id},
                                                        ${!item.enabled}
                                                    )
                                                "
                                            >
                                                ${
                                                    item.enabled
                                                    ? "Disable"
                                                    : "Enable"
                                                }
                                            </button>

                                            <button
                                                class="table-button"
                                                onclick="
                                                    openChannelConfig(
                                                        ${item.id},
                                                        ${JSON.stringify(
                                                            item.config || {}
                                                        ).replace(/"/g, '&quot;')}
                                                    )
                                                "
                                            >
                                                Edit Config
                                            </button>

                                            ${
                                                type === "whatsapp"
                                                ?
                                                `
                                                    <button
                                                        class="table-button"
                                                        onclick="
                                                            openWhatsAppConfig(
                                                                ${item.id}
                                                            )
                                                        "
                                                    >
                                                        WhatsApp Setup
                                                    </button>
                                                `
                                                :
                                                ""
                                            }

                                            <button
                                                class="table-button"
                                                onclick="
                                                    deleteChannel(
                                                        ${item.id}
                                                    )
                                                "
                                            >
                                                Delete
                                            </button>

                                        </div>

                                    </div>
                                `;

                            }).join("")}

                        </div>
                    `
                    :
                    `
                        <p>
                            No channels configured.
                        </p>
                    `
                }

            </div>
        `;

    } catch (error) {
        alert(error.message);
    }
}


async function openCreateChannel() {

    try {

        const agents =
            await getCompanyAgents();

        if (!agents.length) {
            alert("Create an AI Agent first.");
            return;
        }

        openModal(
            "Add Agent Channel",
            `

                <div class="form-group">
                    <label>Agent</label>

                    <select id="channel-agent">
                        ${agentOptions(agents)}
                    </select>
                </div>

                <div class="form-group">
                    <label>Channel Type</label>

                    <select id="channel-type">
                        <option value="whatsapp">
                            WhatsApp
                        </option>

                        <option value="webchat">
                            Web Chat
                        </option>

                        <option value="api">
                            API
                        </option>

                        <option value="telegram">
                            Telegram
                        </option>
                    </select>
                </div>

                <div class="form-group">
                    <label>
                        Initial Config JSON
                    </label>

                    <textarea
                        id="channel-config"
                        rows="7"
                        spellcheck="false"
                    >{}</textarea>
                </div>

                <button
                    class="modal-submit"
                    onclick="createChannel()"
                >
                    Create Channel
                </button>
            `
        );

    } catch (error) {
        alert(error.message);
    }
}


async function createChannel() {

    try {

        const agentId =
            Number(
                document.getElementById(
                    "channel-agent"
                ).value
            );

        const channelType =
            document.getElementById(
                "channel-type"
            ).value;

        const raw =
            document.getElementById(
                "channel-config"
            ).value.trim();

        let config = {};

        if (raw) {
            try {
                config = JSON.parse(raw);
            } catch {
                alert(
                    "Configuration must be valid JSON."
                );
                return;
            }
        }

        await api(
            `/admin/channels/agents/${agentId}`,
            {
                method: "POST",
                body: JSON.stringify({
                    channel_type: channelType,
                    config: config
                })
            }
        );

        closeModal();

        await loadChannelsPage();

    } catch (error) {
        alert(error.message);
    }
}


async function toggleChannel(
    channelId,
    enabled
) {

    try {

        await api(
            `/admin/channels/${channelId}`,
            {
                method: "PUT",
                body: JSON.stringify({
                    enabled: enabled
                })
            }
        );

        await loadChannelsPage();

    } catch (error) {
        alert(error.message);
    }
}


function openChannelConfig(
    channelId,
    config
) {

    openModal(
        "Channel Configuration",
        `

            <div class="form-group">

                <label>
                    Configuration JSON
                </label>

                <textarea
                    id="channel-edit-config"
                    rows="12"
                    spellcheck="false"
                >${escapeService(
                    JSON.stringify(
                        config || {},
                        null,
                        2
                    )
                )}</textarea>

            </div>

            <button
                class="modal-submit"
                onclick="
                    saveChannelConfig(
                        ${channelId}
                    )
                "
            >
                Save Configuration
            </button>
        `
    );
}


async function saveChannelConfig(
    channelId
) {

    try {

        const raw =
            document.getElementById(
                "channel-edit-config"
            ).value.trim();

        let config = {};

        if (raw) {
            try {
                config = JSON.parse(raw);
            } catch {
                alert(
                    "Configuration must be valid JSON."
                );
                return;
            }
        }

        await api(
            `/admin/channels/${channelId}`,
            {
                method: "PUT",
                body: JSON.stringify({
                    config: config
                })
            }
        );

        closeModal();

        await loadChannelsPage();

    } catch (error) {
        alert(error.message);
    }
}


function openWhatsAppConfig(
    channelId
) {

    openModal(
        "WhatsApp Configuration",
        `

            <p>
                Enter the Meta WhatsApp Cloud API
                credentials for this channel.
            </p>

            <div class="form-group">
                <label>Phone Number ID</label>
                <input
                    id="wa-phone-number-id"
                    autocomplete="off"
                >
            </div>

            <div class="form-group">
                <label>Access Token</label>
                <input
                    id="wa-access-token"
                    type="password"
                    autocomplete="new-password"
                >
            </div>

            <div class="form-group">
                <label>Verify Token</label>
                <input
                    id="wa-verify-token"
                    type="password"
                    autocomplete="new-password"
                >
            </div>

            <div class="form-group">
                <label>App Secret</label>
                <input
                    id="wa-app-secret"
                    type="password"
                    autocomplete="new-password"
                >
            </div>

            <div class="form-group">
                <label>Graph API Version</label>
                <input
                    id="wa-graph-version"
                    value="v23.0"
                >
            </div>

            <button
                class="modal-submit"
                onclick="
                    saveWhatsAppConfig(
                        ${channelId}
                    )
                "
            >
                Save WhatsApp Configuration
            </button>
        `
    );
}


async function saveWhatsAppConfig(
    channelId
) {

    try {

        const phoneNumberId =
            document.getElementById(
                "wa-phone-number-id"
            ).value.trim();

        const accessToken =
            document.getElementById(
                "wa-access-token"
            ).value.trim();

        const verifyToken =
            document.getElementById(
                "wa-verify-token"
            ).value.trim();

        const appSecret =
            document.getElementById(
                "wa-app-secret"
            ).value.trim();

        const graphVersion =
            document.getElementById(
                "wa-graph-version"
            ).value.trim() || "v23.0";

        if (
            !phoneNumberId
            || !accessToken
            || !verifyToken
            || !appSecret
        ) {
            alert(
                "All WhatsApp credentials are required."
            );
            return;
        }

        await api(
            `/admin/channels/${channelId}/whatsapp-config`,
            {
                method: "PUT",
                body: JSON.stringify({
                    phone_number_id:
                        phoneNumberId,
                    access_token:
                        accessToken,
                    verify_token:
                        verifyToken,
                    app_secret:
                        appSecret,
                    graph_api_version:
                        graphVersion
                })
            }
        );

        closeModal();

        await loadChannelsPage();

        alert(
            "WhatsApp configuration saved."
        );

    } catch (error) {
        alert(error.message);
    }
}


async function deleteChannel(
    channelId
) {

    if (
        !confirm(
            "Delete this channel permanently?"
        )
    ) {
        return;
    }

    try {

        await api(
            `/admin/channels/${channelId}`,
            {
                method: "DELETE"
            }
        );

        await loadChannelsPage();

    } catch (error) {
        alert(error.message);
    }
}


// ============================================================
// INTEGRATIONS PAGE - PRODUCTION CONFIGURATION
// ============================================================

const XVOND_INTEGRATIONS = {

    pos: {
        label: "POS",
        fields: [
            ["base_url", "POS API URL", "text"],
            ["api_key", "API Key", "password"],
            ["location_id", "Location / Branch ID", "text"]
        ]
    },

    crm: {
        label: "CRM",
        fields: [
            ["base_url", "CRM API URL", "text"],
            ["api_key", "API Key", "password"]
        ]
    },

    erp: {
        label: "ERP",
        fields: [
            ["base_url", "ERP API URL", "text"],
            ["api_key", "API Key", "password"],
            ["company_code", "Company Code", "text"]
        ]
    },

    calendar: {
        label: "Calendar",
        fields: [
            ["provider", "Calendar Provider", "text"],
            ["calendar_id", "Calendar ID", "text"],
            ["access_token", "Access Token", "password"]
        ]
    },

    booking: {
        label: "Booking System",
        fields: [
            ["base_url", "Booking API URL", "text"],
            ["api_key", "API Key", "password"]
        ]
    },

    webhook: {
        label: "Webhook",
        fields: [
            ["url", "Webhook URL", "text"],
            ["secret", "Webhook Secret", "password"]
        ]
    },

    custom_api: {
        label: "Custom API",
        fields: [
            ["base_url", "API Base URL", "text"],
            ["api_key", "API Key", "password"]
        ]
    }
};


async function loadIntegrationsPage() {

    try {

        const result =
            await api(
                `/admin/integrations/companies/${serviceCompanyId}`
            );

        const integrations =
            result.integrations || [];

        const content =
            document.getElementById(
                "integrations-service-content"
            );

        content.innerHTML = `
            <div class="panel">

                <div class="section-header">

                    <div>
                        <h3>
                            Company Integrations
                        </h3>

                        <p>
                            Connect Xvond to external business systems.
                        </p>
                    </div>

                    <button
                        onclick="
                            openCreateIntegration()
                        "
                    >
                        + Add Integration
                    </button>

                </div>

                <div class="agent-grid">

                    ${
                        integrations.length
                        ?
                        integrations.map(item => {

                            const definition =
                                XVOND_INTEGRATIONS[
                                    item.integration_type
                                ];

                            const label =
                                definition
                                ? definition.label
                                : item.integration_type;

                            return `
                                <div class="agent-card">

                                    <h3>
                                        ${escapeService(
                                            item.name
                                        )}
                                    </h3>

                                    <div class="meta">
                                        Type:
                                        ${escapeService(
                                            label
                                        )}
                                    </div>

                                    <div class="meta">
                                        ${
                                            item.enabled
                                            ? "Enabled"
                                            : "Disabled"
                                        }
                                    </div>

                                    <div class="meta">
                                        Configuration:
                                        ${
                                            Object.keys(
                                                item.config || {}
                                            ).length
                                            ? "Configured"
                                            : "Missing"
                                        }
                                    </div>

                                    <div
                                        class="meta"
                                        style="
                                            margin-top:8px;
                                            white-space:pre-wrap;
                                        "
                                    >${escapeService(
                                        JSON.stringify(
                                            safeProductionConfig(
                                                item.config
                                            ),
                                            null,
                                            2
                                        )
                                    )}</div>

                                    ${
                                        definition
                                        ? `
                                            <button
                                                style="margin-top:12px"
                                                onclick='
                                                    openConfigureIntegration(
                                                        ${item.id},
                                                        ${JSON.stringify(
                                                            item.name
                                                        )},
                                                        ${JSON.stringify(
                                                            item.integration_type
                                                        )},
                                                        ${JSON.stringify(
                                                            item.config || {}
                                                        ).replace(
                                                            /</g,
                                                            "\\u003c"
                                                        )}
                                                    )
                                                '
                                            >
                                                Configure
                                            </button>
                                        `
                                        : ""
                                    }

                                </div>
                            `;
                        }).join("")
                        :
                        `
                            <p>
                                No integrations configured.
                            </p>
                        `
                    }

                </div>
            </div>
        `;

    } catch (error) {

        alert(error.message);
    }
}


function openCreateIntegration() {

    openModal(
        "Add Integration",
        `
        <div class="form-group">
            <label>Name</label>

            <input
                id="integration-name"
                placeholder="Restaurant POS"
            >
        </div>

        <div class="form-group">
            <label>
                Integration Type
            </label>

            <select
                id="integration-type"
                onchange="
                    renderIntegrationConfiguration()
                "
            >
                ${
                    Object.entries(
                        XVOND_INTEGRATIONS
                    )
                    .map(
                        ([key, item]) => `
                            <option value="${key}">
                                ${escapeService(
                                    item.label
                                )}
                            </option>
                        `
                    )
                    .join("")
                }
            </select>
        </div>

        <div
            id="integration-production-fields"
        ></div>

        <button
            class="modal-submit"
            onclick="
                createServiceIntegration()
            "
        >
            Save Integration
        </button>
        `
    );

    renderIntegrationConfiguration();
}


function renderIntegrationConfiguration() {

    const type =
        document.getElementById(
            "integration-type"
        );

    const container =
        document.getElementById(
            "integration-production-fields"
        );

    if (!type || !container) {
        return;
    }

    container.innerHTML =
        productionFieldsHtml(
            XVOND_INTEGRATIONS[
                type.value
            ],
            "integration-new"
        );
}


async function createServiceIntegration() {

    try {

        const type =
            document.getElementById(
                "integration-type"
            ).value;

        const definition =
            XVOND_INTEGRATIONS[type];

        const config =
            readProductionFields(
                definition,
                "integration-new"
            );

        const name =
            document.getElementById(
                "integration-name"
            ).value.trim();

        if (!name) {
            alert(
                "Integration name is required."
            );
            return;
        }

        await api(
            `/admin/integrations/companies/${serviceCompanyId}`,
            {
                method: "POST",

                body: JSON.stringify({
                    integration_type:
                        type,

                    name:
                        name,

                    config:
                        config
                })
            }
        );

        closeModal();

        await loadIntegrationsPage();
        await refreshProductionStatusIfVisible();

    } catch (error) {

        alert(error.message);
    }
}


function openConfigureIntegration(
    integrationId,
    name,
    type,
    config
) {

    const definition =
        XVOND_INTEGRATIONS[type];

    if (!definition) {
        alert(
            "Unsupported integration type."
        );
        return;
    }

    openModal(
        `Configure ${name}`,
        `
        ${productionFieldsHtml(
            definition,
            "integration-edit",
            config || {}
        )}

        <button
            class="modal-submit"
            onclick="
                saveIntegrationConfiguration(
                    ${integrationId},
                    '${escapeJsService(type)}'
                )
            "
        >
            Save Configuration
        </button>
        `
    );
}


async function saveIntegrationConfiguration(
    integrationId,
    type
) {

    try {

        const config =
            readProductionFields(
                XVOND_INTEGRATIONS[type],
                "integration-edit"
            );

        await api(
            `/admin/integrations/${integrationId}`,
            {
                method: "PATCH",

                body: JSON.stringify({
                    config:
                        config,
                    enabled:
                        true
                })
            }
        );

        closeModal();

        await loadIntegrationsPage();
        await refreshProductionStatusIfVisible();

    } catch (error) {

        alert(error.message);
    }
}


// ============================================================
// ESCAPE HELPERS
// ============================================================

function escapeService(
    value
) {

    const div =
        document.createElement(
            "div"
        );

    div.textContent =
        value ?? "";

    return div.innerHTML;
}


function escapeJsService(
    value
) {

    return String(
        value ?? ""
    )
    .replaceAll(
        "\\",
        "\\\\"
    )
    .replaceAll(
        "'",
        "\\'"
    );
}


function escapeAttributeService(
    value
) {

    return String(
        value ?? ""
    )
    .replaceAll(
        "&",
        "&amp;"
    )
    .replaceAll(
        '"',
        "&quot;"
    )
    .replaceAll(
        "<",
        "&lt;"
    )
    .replaceAll(
        ">",
        "&gt;"
    );
}


function escapeTextareaService(
    value
) {

    return String(
        value ?? ""
    )
    .replaceAll(
        "&",
        "&amp;"
    )
    .replaceAll(
        "<",
        "&lt;"
    )
    .replaceAll(
        ">",
        "&gt;"
    );
}


document.addEventListener(
    "DOMContentLoaded",
    installServicesUI
);


setTimeout(
    installServicesUI,
    500
);

