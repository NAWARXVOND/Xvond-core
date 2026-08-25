function installCompanyWorkspace() {
    document.querySelectorAll('.sidebar .nav-item').forEach(button => {
        const action = button.getAttribute('onclick') || '';
        if (!action.includes("'dashboard'") && !action.includes("'companies'")) {
            button.style.display = 'none';
        }
    });
}


function serviceCard(title, description, action, statusText = 'Configure') {
    return `
        <div class="agent-card" style="min-height:180px;display:flex;flex-direction:column;justify-content:space-between">
            <div>
                <h3>${escapeAdmin(title)}</h3>
                <p>${escapeAdmin(description)}</p>
            </div>
            <button onclick="${action}">${escapeAdmin(statusText)}</button>
        </div>
    `;
}


async function openCompany(companyId) {
    const data = await api(`/admin/company-view/${companyId}`);

    document.querySelectorAll('.page').forEach(item => item.classList.add('hidden'));
    document.getElementById('page-company-detail').classList.remove('hidden');
    document.getElementById('page-title').textContent = data.company.name;

    const target = document.getElementById('company-detail');
    target.innerHTML = `
        <div class="company-header">
            <div>
                <h2>${escapeAdmin(data.company.name)}</h2>
                <p>Build and operate this customer from one workspace.</p>
            </div>
            <span class="status ${data.company.active ? 'status-active' : 'status-inactive'}">
                ${data.company.active ? 'Active' : 'Inactive'}
            </span>
        </div>

        <div class="cards">
            <div class="card"><div class="card-label">Agents</div><div class="card-value">${data.agents.length}</div></div>
            <div class="card"><div class="card-label">Conversations</div><div class="card-value">${data.analytics.conversations}</div></div>
            <div class="card"><div class="card-label">AI Requests</div><div class="card-value">${data.analytics.ai_requests}</div></div>
            <div class="card"><div class="card-label">Provider Cost</div><div class="card-value">${data.analytics.provider_cost}</div></div>
        </div>

        <div class="panel detail-section">
            <div class="section-header">
                <div>
                    <h3>Customer Services</h3>
                    <p>Only the four services Xvond configures from the platform.</p>
                </div>
            </div>
            <div class="agent-grid">
                ${serviceCard(
                    'AI Agents',
                    'Customer service, sales, booking and order agents across WhatsApp, website and voice.',
                    `openAgentsWorkspace(${companyId})`
                )}
                ${serviceCard(
                    'Automation',
                    'Build repeatable workflows triggered manually, by event, schedule or webhook.',
                    `openAutomationWorkspace(${companyId})`
                )}
                ${serviceCard(
                    'Data & Analytics',
                    'Connect business data sources and configure dashboards and AI analysis.',
                    `openAnalyticsWorkspace(${companyId})`
                )}
                ${serviceCard(
                    'Integrations',
                    'Connect POS, CRM, ERP, calendars, APIs and external business systems.',
                    `openCompanyService('integrations-service', ${companyId})`
                )}
            </div>
        </div>

        <div class="panel detail-section" style="margin-top:20px">
            <h3>Subscription & Usage</h3>
            <p>Monthly service plans, limits and usage are managed for this company.</p>
            <button onclick="openCompanyOperation('billing-service', ${companyId})">Manage Subscription</button>
        </div>

        <div id="company-production-status" class="panel detail-section" style="margin-top:20px">
            <p>Checking production readiness...</p>
        </div>
    `;

    if (typeof loadCompanyProductionStatus === 'function') {
        try { await loadCompanyProductionStatus(companyId); } catch (_) {}
    }
}


function showWorkspaceModal(title, body) {
    openModal(title, `<div id="workspace-modal-content">${body}</div>`);
}


async function openAgentsWorkspace(companyId) {
    const data = await api(`/admin/company-view/${companyId}`);
    const agents = data.agents || [];
    showWorkspaceModal('AI Agents', `
        <div class="section-header">
            <div><h3>Agents</h3><p>Create the employee, then configure knowledge, tools and channels.</p></div>
            <button onclick="closeModal();openCreateAgent(${companyId})">+ New Agent</button>
        </div>
        ${agents.length ? agents.map(agent => `
            <div class="agent-card" style="margin-bottom:10px">
                <strong>${escapeAdmin(agent.name)}</strong>
                <div class="meta">${escapeAdmin(agent.provider)} / ${escapeAdmin(agent.model)}</div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
                    <button class="table-button" onclick="closeModal();openEditAgent(${companyId},${agent.id})">Agent</button>
                    <button class="table-button" onclick="closeModal();openCompanyService('knowledge',${companyId})">Knowledge</button>
                    <button class="table-button" onclick="closeModal();openCompanyService('tools-service',${companyId})">Tools</button>
                    <button class="table-button" onclick="closeModal();openCompanyService('channels-service',${companyId})">Channels</button>
                </div>
            </div>
        `).join('') : '<p>No agents yet.</p>'}
    `);
}


async function openAutomationWorkspace(companyId) {
    const data = await api(`/admin/automation/companies/${companyId}`);
    const workflows = data.workflows || [];
    showWorkspaceModal('Automation', `
        <div class="section-header">
            <div><h3>Workflows</h3><p>Trigger → Steps → Actions.</p></div>
            <button onclick="openNewAutomation(${companyId})">+ New Workflow</button>
        </div>
        ${workflows.length ? workflows.map(item => `
            <div class="agent-card" style="margin-bottom:10px">
                <strong>${escapeAdmin(item.name)}</strong>
                <div class="meta">Trigger: ${escapeAdmin(item.trigger_type)} · Steps: ${(item.steps || []).length} · ${item.enabled ? 'Enabled' : 'Disabled'}</div>
            </div>
        `).join('') : '<p>No automations configured.</p>'}
    `);
}


function openNewAutomation(companyId) {
    showWorkspaceModal('New Automation', `
        <div class="form-group"><label>Name</label><input id="automation-name"></div>
        <div class="form-group"><label>Trigger</label>
            <select id="automation-trigger">
                <option value="manual">Manual</option>
                <option value="webhook">Webhook</option>
                <option value="schedule">Schedule</option>
                <option value="event">Business Event</option>
            </select>
        </div>
        <div class="form-group"><label>Steps JSON</label><textarea id="automation-steps" rows="10">[]</textarea></div>
        <button class="modal-submit" onclick="saveAutomation(${companyId})">Create Workflow</button>
    `);
}


async function saveAutomation(companyId) {
    try {
        const steps = JSON.parse(document.getElementById('automation-steps').value || '[]');
        await api(`/admin/automation/companies/${companyId}`, {
            method: 'POST',
            body: JSON.stringify({
                name: document.getElementById('automation-name').value,
                trigger_type: document.getElementById('automation-trigger').value,
                trigger_config: {},
                steps,
            }),
        });
        await openAutomationWorkspace(companyId);
    } catch (error) { alert(error.message); }
}


async function openAnalyticsWorkspace(companyId) {
    const data = await api(`/admin/analytics-builder/companies/${companyId}`);
    showWorkspaceModal('Data & Analytics', `
        <div class="section-header">
            <div><h3>Data Sources</h3><p>Sources connected to this customer's analytics workspace.</p></div>
            <button onclick="openNewAnalyticsSource(${companyId})">+ Data Source</button>
        </div>
        ${(data.sources || []).length ? data.sources.map(item => `
            <div class="agent-card" style="margin-bottom:10px"><strong>${escapeAdmin(item.name)}</strong><div class="meta">${escapeAdmin(item.source_type)}</div></div>
        `).join('') : '<p>No data sources.</p>'}
        <div class="section-header" style="margin-top:20px"><div><h3>Dashboards</h3></div><button onclick="openNewAnalyticsDashboard(${companyId})">+ Dashboard</button></div>
        ${(data.dashboards || []).length ? data.dashboards.map(item => `
            <div class="agent-card" style="margin-bottom:10px"><strong>${escapeAdmin(item.name)}</strong><div class="meta">Metrics: ${(item.metrics || []).length}</div></div>
        `).join('') : '<p>No dashboards.</p>'}
    `);
}


function openNewAnalyticsSource(companyId) {
    showWorkspaceModal('New Data Source', `
        <div class="form-group"><label>Name</label><input id="analytics-source-name"></div>
        <div class="form-group"><label>Type</label><select id="analytics-source-type"><option value="integration">Integration</option><option value="database">Database</option><option value="csv">CSV</option><option value="api">API</option><option value="manual">Manual</option></select></div>
        <button class="modal-submit" onclick="saveAnalyticsSource(${companyId})">Add Source</button>
    `);
}


async function saveAnalyticsSource(companyId) {
    try {
        await api(`/admin/analytics-builder/companies/${companyId}/sources`, {
            method: 'POST',
            body: JSON.stringify({
                name: document.getElementById('analytics-source-name').value,
                source_type: document.getElementById('analytics-source-type').value,
                config: {},
            }),
        });
        await openAnalyticsWorkspace(companyId);
    } catch (error) { alert(error.message); }
}


function openNewAnalyticsDashboard(companyId) {
    showWorkspaceModal('New Dashboard', `
        <div class="form-group"><label>Name</label><input id="analytics-dashboard-name"></div>
        <div class="form-group"><label>Metrics JSON</label><textarea id="analytics-dashboard-metrics" rows="8">[]</textarea></div>
        <button class="modal-submit" onclick="saveAnalyticsDashboard(${companyId})">Create Dashboard</button>
    `);
}


async function saveAnalyticsDashboard(companyId) {
    try {
        const metrics = JSON.parse(document.getElementById('analytics-dashboard-metrics').value || '[]');
        await api(`/admin/analytics-builder/companies/${companyId}/dashboards`, {
            method: 'POST',
            body: JSON.stringify({
                name: document.getElementById('analytics-dashboard-name').value,
                metrics,
                configuration: {},
            }),
        });
        await openAnalyticsWorkspace(companyId);
    } catch (error) { alert(error.message); }
}


document.addEventListener('DOMContentLoaded', installCompanyWorkspace);
