let xvondAutomationDraftSteps = [];

const XVOND_SERVICE_LABELS = {
    ai_agents: "AI Agents",
    automation: "Automation",
    analytics: "Data & Analytics",
    integrations: "Integrations",
};


function installCompanyWorkspace() {
    document.querySelectorAll('.sidebar .nav-item').forEach(button => {
        const action = button.getAttribute('onclick') || '';
        if (!action.includes("'dashboard'") && !action.includes("'companies'")) {
            button.style.display = 'none';
        }
    });
}


function serviceCard(title, description, action) {
    return `
        <div class="agent-card" style="min-height:180px;display:flex;flex-direction:column;justify-content:space-between">
            <div>
                <h3>${escapeAdmin(title)}</h3>
                <p>${escapeAdmin(description)}</p>
            </div>
            <button onclick="${action}">Open</button>
        </div>
    `;
}


async function openCompany(companyId) {
    const [data, billing] = await Promise.all([
        api(`/admin/company-view/${companyId}`),
        api(`/admin/service-billing/companies/${companyId}`).catch(() => ({services: []})),
    ]);

    const subscriptions = new Map(
        (billing.services || []).map(item => [item.service_code, item])
    );

    document.querySelectorAll('.page').forEach(item => item.classList.add('hidden'));
    document.getElementById('page-company-detail').classList.remove('hidden');
    document.getElementById('page-title').textContent = data.company.name;

    const target = document.getElementById('company-detail');
    target.innerHTML = `
        <div class="company-header">
            <div>
                <h2>${escapeAdmin(data.company.name)}</h2>
                <p>Everything for this customer is managed here.</p>
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
                    <h3>Services</h3>
                    <p>Choose the service you want to build or manage for this customer.</p>
                </div>
                <button class="table-button" onclick="openServiceSubscriptions(${companyId})">Plans & Limits</button>
            </div>
            <div class="agent-grid">
                ${serviceCard(
                    `AI Agents${servicePlanSuffix(subscriptions.get('ai_agents'))}`,
                    'Customer service, sales, booking and order agents on WhatsApp, website and voice.',
                    `openAgentsWorkspace(${companyId})`
                )}
                ${serviceCard(
                    `Automation${servicePlanSuffix(subscriptions.get('automation'))}`,
                    'Create business workflows from a trigger to actions without rebuilding the project.',
                    `openAutomationWorkspace(${companyId})`
                )}
                ${serviceCard(
                    `Data & Analytics${servicePlanSuffix(subscriptions.get('analytics'))}`,
                    'Connect business data sources, dashboards and AI analysis.',
                    `openAnalyticsWorkspace(${companyId})`
                )}
                ${serviceCard(
                    `Integrations${servicePlanSuffix(subscriptions.get('integrations'))}`,
                    'Connect POS, CRM, ERP, calendars, APIs and other business systems.',
                    `openCompanyService('integrations-service', ${companyId})`
                )}
            </div>
        </div>

        <div id="company-production-status" class="panel detail-section" style="margin-top:20px">
            <p>Checking production readiness...</p>
        </div>
    `;

    if (typeof loadCompanyProductionStatus === 'function') {
        try { await loadCompanyProductionStatus(companyId); } catch (_) {}
    }
}


function servicePlanSuffix(subscription) {
    if (!subscription) return ' · No plan';
    return ` · ${subscription.plan?.name || subscription.plan?.tier || 'Active'}`;
}


function showWorkspaceModal(title, body) {
    openModal(title, `<div id="workspace-modal-content">${body}</div>`);
}


async function openServiceSubscriptions(companyId) {
    const [plansData, currentData] = await Promise.all([
        api('/admin/service-billing/plans'),
        api(`/admin/service-billing/companies/${companyId}`),
    ]);

    const plans = plansData.plans || [];
    const current = new Map((currentData.services || []).map(x => [x.service_code, x]));

    showWorkspaceModal('Plans & Monthly Limits', `
        <p>Select one monthly plan for each service the customer buys.</p>
        ${Object.entries(XVOND_SERVICE_LABELS).map(([serviceCode, label]) => {
            const servicePlans = plans.filter(plan => plan.service_code === serviceCode && plan.enabled);
            const subscription = current.get(serviceCode);
            return `
                <div class="agent-card" style="margin-bottom:12px">
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
                        <div>
                            <h3>${escapeAdmin(label)}</h3>
                            <div class="meta">
                                ${subscription
                                    ? `Current: ${escapeAdmin(subscription.plan?.name || subscription.plan?.tier || '')} · ${escapeAdmin(subscription.status)}`
                                    : 'Not subscribed'}
                            </div>
                            ${subscription ? renderUsageSummary(subscription.usage || {}) : ''}
                        </div>
                    </div>
                    <div class="form-row" style="margin-top:12px">
                        <select id="service-plan-${serviceCode}">
                            <option value="">Select plan</option>
                            ${servicePlans.map(plan => `
                                <option value="${plan.id}" ${subscription?.plan?.id === plan.id ? 'selected' : ''}>
                                    ${escapeAdmin(plan.name)} · ${escapeAdmin(plan.monthly_price)} ${escapeAdmin(plan.currency)} / month
                                </option>
                            `).join('')}
                        </select>
                        <button onclick="applyServicePlan(${companyId},'${serviceCode}')">Apply</button>
                    </div>
                    ${servicePlans.length ? '' : '<p class="meta">No package has been created for this service yet.</p>'}
                </div>
            `;
        }).join('')}
    `);
}


function renderUsageSummary(usage) {
    const rows = Object.entries(usage || {});
    if (!rows.length) return '';
    return `<div class="meta" style="margin-top:8px">${rows.map(([metric, item]) =>
        `${escapeAdmin(metric)}: ${escapeAdmin(item.used)} / ${escapeAdmin(item.limit)}`
    ).join(' · ')}</div>`;
}


async function applyServicePlan(companyId, serviceCode) {
    const planId = Number(document.getElementById(`service-plan-${serviceCode}`).value);
    if (!planId) {
        alert('Select a plan first.');
        return;
    }
    try {
        await api(`/admin/service-billing/companies/${companyId}/services/${serviceCode}`, {
            method: 'PUT',
            body: JSON.stringify({plan_id: planId}),
        });
        await openServiceSubscriptions(companyId);
    } catch (error) {
        alert(error.message);
    }
}


async function openAgentsWorkspace(companyId) {
    const data = await api(`/admin/company-view/${companyId}`);
    const agents = data.agents || [];
    showWorkspaceModal('AI Agents', `
        <div class="section-header">
            <div><h3>Agents</h3><p>Create the employee, then give it knowledge, abilities and channels.</p></div>
            <button onclick="closeModal();openCreateAgent(${companyId})">+ New Agent</button>
        </div>
        ${agents.length ? agents.map(agent => `
            <div class="agent-card" style="margin-bottom:10px">
                <strong>${escapeAdmin(agent.name)}</strong>
                <div class="meta">${escapeAdmin(agent.provider)} / ${escapeAdmin(agent.model)}</div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
                    <button class="table-button" onclick="closeModal();openEditAgent(${companyId},${agent.id})">Settings</button>
                    <button class="table-button" onclick="closeModal();openCompanyService('knowledge',${companyId})">Knowledge</button>
                    <button class="table-button" onclick="closeModal();openCompanyService('tools-service',${companyId})">Abilities</button>
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
            <div><h3>Workflows</h3><p>Each workflow is Trigger → Steps → Result.</p></div>
            <button onclick="openNewAutomation(${companyId})">+ New Workflow</button>
        </div>
        ${workflows.length ? workflows.map(item => `
            <div class="agent-card" style="margin-bottom:10px">
                <strong>${escapeAdmin(item.name)}</strong>
                <div class="meta">${escapeAdmin(item.trigger_type)} · ${(item.steps || []).length} steps · ${item.enabled ? 'Enabled' : 'Disabled'}</div>
            </div>
        `).join('') : '<p>No automations configured.</p>'}
    `);
}


function openNewAutomation(companyId) {
    xvondAutomationDraftSteps = [];
    showWorkspaceModal('New Automation', `
        <div class="form-group"><label>Workflow name</label><input id="automation-name" placeholder="Process supplier invoice"></div>
        <div class="form-group"><label>Starts when</label>
            <select id="automation-trigger">
                <option value="manual">Run manually</option>
                <option value="webhook">Webhook received</option>
                <option value="schedule">On a schedule</option>
                <option value="event">Business event happens</option>
            </select>
        </div>
        <div class="panel" style="margin:15px 0">
            <h3>Steps</h3>
            <div id="automation-step-list"><p>No steps yet.</p></div>
            <div class="form-row" style="margin-top:12px">
                <select id="automation-step-type">
                    <option value="ai">AI task</option>
                    <option value="integration">Use integration</option>
                    <option value="tool">Business action</option>
                    <option value="condition">Condition</option>
                    <option value="webhook">Send webhook</option>
                    <option value="transform">Transform data</option>
                </select>
                <input id="automation-step-label" placeholder="What should this step do?">
                <button type="button" onclick="addAutomationDraftStep()">Add step</button>
            </div>
        </div>
        <button class="modal-submit" onclick="saveAutomation(${companyId})">Create Workflow</button>
    `);
}


function addAutomationDraftStep() {
    const type = document.getElementById('automation-step-type').value;
    const label = document.getElementById('automation-step-label').value.trim();
    if (!label) {
        alert('Describe the step first.');
        return;
    }
    xvondAutomationDraftSteps.push({type, label});
    document.getElementById('automation-step-label').value = '';
    renderAutomationDraftSteps();
}


function renderAutomationDraftSteps() {
    const target = document.getElementById('automation-step-list');
    if (!target) return;
    target.innerHTML = xvondAutomationDraftSteps.length
        ? xvondAutomationDraftSteps.map((step, index) => `
            <div class="agent-card" style="margin:8px 0;padding:10px">
                <strong>${index + 1}. ${escapeAdmin(step.label)}</strong>
                <span class="meta">${escapeAdmin(step.type)}</span>
                <button class="table-button" style="float:right" onclick="removeAutomationDraftStep(${index})">Remove</button>
            </div>
        `).join('')
        : '<p>No steps yet.</p>';
}


function removeAutomationDraftStep(index) {
    xvondAutomationDraftSteps.splice(index, 1);
    renderAutomationDraftSteps();
}


async function saveAutomation(companyId) {
    const name = document.getElementById('automation-name').value.trim();
    if (!name) {
        alert('Workflow name is required.');
        return;
    }
    if (!xvondAutomationDraftSteps.length) {
        alert('Add at least one step.');
        return;
    }
    try {
        await api(`/admin/automation/companies/${companyId}`, {
            method: 'POST',
            body: JSON.stringify({
                name,
                trigger_type: document.getElementById('automation-trigger').value,
                trigger_config: {},
                steps: xvondAutomationDraftSteps,
            }),
        });
        await openAutomationWorkspace(companyId);
    } catch (error) {
        alert(error.message);
    }
}


async function openAnalyticsWorkspace(companyId) {
    const data = await api(`/admin/analytics-builder/companies/${companyId}`);
    showWorkspaceModal('Data & Analytics', `
        <div class="section-header">
            <div><h3>Data Sources</h3><p>Connect the data this customer wants Xvond to analyze.</p></div>
            <button onclick="openNewAnalyticsSource(${companyId})">+ Data Source</button>
        </div>
        ${(data.sources || []).length ? data.sources.map(item => `
            <div class="agent-card" style="margin-bottom:10px"><strong>${escapeAdmin(item.name)}</strong><div class="meta">${escapeAdmin(item.source_type)}</div></div>
        `).join('') : '<p>No data sources.</p>'}
        <div class="section-header" style="margin-top:20px">
            <div><h3>Dashboards</h3><p>Choose which business metrics should be visible.</p></div>
            <button onclick="openNewAnalyticsDashboard(${companyId})">+ Dashboard</button>
        </div>
        ${(data.dashboards || []).length ? data.dashboards.map(item => `
            <div class="agent-card" style="margin-bottom:10px"><strong>${escapeAdmin(item.name)}</strong><div class="meta">${(item.metrics || []).map(m => escapeAdmin(m.name || m)).join(' · ')}</div></div>
        `).join('') : '<p>No dashboards.</p>'}
    `);
}


function openNewAnalyticsSource(companyId) {
    showWorkspaceModal('New Data Source', `
        <div class="form-group"><label>Name</label><input id="analytics-source-name" placeholder="Sales data"></div>
        <div class="form-group"><label>Source type</label>
            <select id="analytics-source-type">
                <option value="integration">Connected system</option>
                <option value="database">Database</option>
                <option value="csv">CSV file</option>
                <option value="api">API</option>
                <option value="manual">Manual data</option>
            </select>
        </div>
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
    } catch (error) {
        alert(error.message);
    }
}


function openNewAnalyticsDashboard(companyId) {
    showWorkspaceModal('New Dashboard', `
        <div class="form-group"><label>Dashboard name</label><input id="analytics-dashboard-name" placeholder="Management overview"></div>
        <div class="form-group"><label>Metrics</label><input id="analytics-dashboard-metrics" placeholder="Sales, Orders, Conversion rate"></div>
        <p class="meta">Separate metric names with commas.</p>
        <button class="modal-submit" onclick="saveAnalyticsDashboard(${companyId})">Create Dashboard</button>
    `);
}


async function saveAnalyticsDashboard(companyId) {
    const metrics = document.getElementById('analytics-dashboard-metrics').value
        .split(',')
        .map(value => value.trim())
        .filter(Boolean)
        .map(name => ({name}));
    try {
        await api(`/admin/analytics-builder/companies/${companyId}/dashboards`, {
            method: 'POST',
            body: JSON.stringify({
                name: document.getElementById('analytics-dashboard-name').value,
                metrics,
                configuration: {},
            }),
        });
        await openAnalyticsWorkspace(companyId);
    } catch (error) {
        alert(error.message);
    }
}


document.addEventListener('DOMContentLoaded', installCompanyWorkspace);
