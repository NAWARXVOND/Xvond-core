function customerManagerAccess() {
    return portalOverview?.portal?.access_level === "manager";
}

function customerRoleLabel(role) {
    return role === "employee" ? "Staff" : "Manager";
}

const customerBaseFallbackNavigation = fallbackPortalNavigation;
fallbackPortalNavigation = function() {
    if (!["owner", "admin", "manager"].includes(currentUser?.role)) {
        return [
            {id: "dashboard", label: "Overview", loader: "dashboard", group: "Workspace"}
        ];
    }
    return customerBaseFallbackNavigation();
};

const customerBaseRenderDashboard = renderDashboard;
renderDashboard = function() {
    if (customerManagerAccess()) {
        customerBaseRenderDashboard();
        return;
    }
    const summary = portalOverview?.summary || {};
    const cardTarget = document.getElementById("dashboard-cards");
    if (cardTarget) {
        cardTarget.innerHTML = `
            <div class="card"><span>Active AI Employees</span><strong>${safe(summary.active_agents || 0)}</strong></div>
            <div class="card"><span>Connected Channels</span><strong>${safe(summary.active_channels || 0)}</strong></div>
        `;
    }
    const serviceTarget = document.getElementById("dashboard-services");
    if (serviceTarget) {
        serviceTarget.innerHTML = '<p class="muted">Management details are available to authorized managers.</p>';
    }
};

loadAgents = async function() {
    const result = await api("/ai-agents/");
    agents = result.agents || [];
    const target = document.getElementById("agents-list");
    if (target) {
        target.innerHTML = agents.length
            ? agents.map(agent => `
                <div class="agent">
                    <div class="service-card-head">
                        <div>
                            <h3>${safe(agent.name)}</h3>
                            <p>${safe(agent.description || "")}</p>
                        </div>
                        <span class="status">${agent.enabled ? "Active" : "Inactive"}</span>
                    </div>
                    <button onclick="openCustomerAgentSettings(${Number(agent.id)})">Manage</button>
                </div>
            `).join("") + '<div id="customer-agent-settings"></div>'
            : "<p>No AI employees available.</p>";
    }
    fillAgentSelects();
};

function customerSelect(id, label, options, selected) {
    return `<div class="form-group"><label>${safe(label)}</label><select id="${id}">${options.map(([value, text]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${safe(text)}</option>`).join("")}</select></div>`;
}

async function openCustomerAgentSettings(agentId) {
    const target = document.getElementById("customer-agent-settings");
    if (!target) return;
    try {
        const d = await api(`/customer/agents/${agentId}`);
        const controls = d.controls || {};
        target.innerHTML = `
            <div class="panel" style="margin-top:18px">
                <div class="service-card-head"><div><h2>Manage ${safe(d.name)}</h2><p>Conversation behavior only. Business facts and integrations remain managed by Xvond.</p></div></div>
                ${customerSelect("ca-language", "Reply Language", [["auto","Automatic — match customer"],["ar","Arabic"],["en","English"],["ar_en","Arabic & English"]], d.reply_language || "auto")}
                ${customerSelect("ca-dialect", "Dialect", [["auto","Automatic — match customer"],["msa","Modern Standard Arabic"],["omani","Omani Arabic"],["gulf","Gulf Arabic"],["saudi","Saudi Arabic"],["emirati","Emirati Arabic"],["levantine","Levantine / Shami Arabic"],["egyptian","Egyptian Arabic"]], d.dialect || "auto")}
                ${customerSelect("ca-style", "Conversation Style", [["professional_friendly","Professional & Friendly"],["professional","Professional"],["warm","Warm & Conversational"],["concise","Concise"]], d.conversation_style || "professional_friendly")}
                ${customerSelect("ca-length", "Response Length", [["concise","Concise — recommended"],["balanced","Balanced"],["detailed","Detailed"]], d.response_length || "concise")}
                ${customerSelect("ca-clarification", "When a request is unclear", [["smart","Ask only when needed — recommended"],["ask_when_unclear","Ask one clarifying question"],["direct_first","Give a useful answer first"]], d.clarification_style || "smart")}
                ${customerSelect("ca-off-topic", "Personal or off-topic messages", [["business_redirect","Business focused — recommended"],["brief_friendly","Allow brief friendly small talk"]], d.off_topic_behavior || "business_redirect")}
                <div class="form-group"><label>Greeting</label><textarea id="ca-greeting" placeholder="Optional greeting">${safe(d.greeting || "")}</textarea></div>
                ${controls.can_edit_prompt ? `<div class="form-group"><label>Advanced Instructions</label><textarea id="ca-instructions">${safe(d.instructions || "")}</textarea></div>` : ""}
                ${controls.can_enable_disable ? `<label style="display:flex;gap:8px;align-items:center;margin:14px 0"><input id="ca-enabled" type="checkbox" ${d.enabled ? "checked" : ""}> AI Employee active</label>` : ""}
                <div id="ca-message" class="error"></div>
                <button onclick="saveCustomerAgentSettings(${Number(agentId)}, ${controls.can_edit_prompt ? "true" : "false"}, ${controls.can_enable_disable ? "true" : "false"})">Save Changes</button>
            </div>
        `;
        target.scrollIntoView({behavior: "smooth", block: "start"});
    } catch (err) {
        target.innerHTML = `<div class="panel"><div class="error">${safe(err.message)}</div></div>`;
    }
}

async function saveCustomerAgentSettings(agentId, canEditPrompt, canEnableDisable) {
    const value = id => document.getElementById(id)?.value ?? "";
    const payload = {
        reply_language: value("ca-language"),
        dialect: value("ca-dialect"),
        conversation_style: value("ca-style"),
        response_length: value("ca-length"),
        clarification_style: value("ca-clarification"),
        off_topic_behavior: value("ca-off-topic"),
        greeting: value("ca-greeting")
    };
    if (canEditPrompt) payload.instructions = value("ca-instructions");
    if (canEnableDisable) payload.enabled = !!document.getElementById("ca-enabled")?.checked;
    const message = document.getElementById("ca-message");
    if (message) message.textContent = "";
    try {
        await api(`/customer/agents/${agentId}`, {method: "PATCH", body: JSON.stringify(payload)});
        if (message) message.textContent = "Saved.";
        await loadAgents();
    } catch (err) {
        if (message) message.textContent = err.message;
    }
}

async function loadCompanyUsers() {
    const page = document.getElementById("page-users");
    const target = page?.querySelector(".dynamic-page-content");
    if (!target) return;
    try {
        const result = await api("/users/");
        const users = result.users || [];
        target.innerHTML = `
            <div class="panel" style="margin-bottom:20px">
                <h2>Company Users</h2>
                <p class="muted">Staff sees Overview only. Manager can access the authorized management areas.</p>
                <div id="company-user-list">
                    ${users.map(user => `
                        <div class="agent">
                            <div class="service-card-head">
                                <div><strong>${safe(user.full_name || user.email)}</strong><p>${safe(user.email)} · ${customerRoleLabel(user.role)}</p></div>
                                <span class="status">${user.active ? "Active" : "Inactive"}</span>
                            </div>
                            ${user.id !== currentUser?.id && !["owner","admin"].includes(user.role) ? `<button onclick="setCompanyUserStatus(${Number(user.id)}, ${user.active ? "false" : "true"})">${user.active ? "Disable" : "Activate"}</button>` : ""}
                        </div>
                    `).join("") || '<p>No users found.</p>'}
                </div>
            </div>
            <div class="panel">
                <h2>Add User</h2>
                <div class="form-group"><label>Full Name</label><input id="cu-name"></div>
                <div class="form-group"><label>Email</label><input id="cu-email" type="email"></div>
                <div class="form-group"><label>Temporary Password</label><input id="cu-password" type="password"></div>
                <div class="form-group"><label>Access</label><select id="cu-role"><option value="employee">Staff — Overview only</option><option value="manager">Manager — Management access</option></select></div>
                <div id="cu-message" class="error"></div>
                <button onclick="createCompanyUser()">Add User</button>
            </div>
        `;
    } catch (err) {
        target.innerHTML = `<div class="panel"><div class="error">${safe(err.message)}</div></div>`;
    }
}

async function createCompanyUser() {
    const message = document.getElementById("cu-message");
    try {
        await api("/users/", {
            method: "POST",
            body: JSON.stringify({
                full_name: document.getElementById("cu-name").value.trim(),
                email: document.getElementById("cu-email").value.trim(),
                password: document.getElementById("cu-password").value,
                role: document.getElementById("cu-role").value
            })
        });
        await loadCompanyUsers();
    } catch (err) {
        if (message) message.textContent = err.message;
    }
}

async function setCompanyUserStatus(userId, active) {
    try {
        await api(`/users/${userId}/status`, {method: "PATCH", body: JSON.stringify({active})});
        await loadCompanyUsers();
    } catch (err) {
        alert(err.message);
    }
}

const customerBaseOpenPage = openPage;
openPage = async function(name, button) {
    await customerBaseOpenPage(name, button);
    const item = portalNavigation.find(entry => entry.id === name) || {};
    if ((item.loader || name) === "users") await loadCompanyUsers();
};
