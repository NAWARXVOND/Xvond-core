let xvondAutomationCompanyId = null;
let xvondAutomationAgents = [];
let xvondAutomationIntegrations = [];


async function openAutomationWorkspace(companyId) {
    xvondAutomationCompanyId = companyId;
    const [data, runsData] = await Promise.all([
        api(`/admin/automation/companies/${companyId}`),
        api(`/admin/automation/companies/${companyId}/runs`),
    ]);
    const workflows = data.workflows || [];
    const runs = runsData.runs || [];

    showWorkspaceModal('Automation', `
        <div class="section-header">
            <div>
                <h3>Workflows</h3>
                <p>Create the process once, then run it whenever the business needs it.</p>
            </div>
            <button onclick="openNewAutomation(${companyId})">+ New Workflow</button>
        </div>
        ${workflows.length ? workflows.map(item => `
            <div class="agent-card" style="margin-bottom:10px">
                <strong>${escapeAdmin(item.name)}</strong>
                <div class="meta">
                    ${escapeAdmin(item.trigger_type)} · ${(item.steps || []).length} steps · ${item.enabled ? 'Enabled' : 'Disabled'}
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
                    <button class="table-button" onclick="toggleAutomation(${item.id},${!item.enabled},${companyId})">
                        ${item.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button class="table-button" ${item.enabled ? '' : 'disabled'} onclick="runAutomationNow(${item.id},${companyId})">
                        Run now
                    </button>
                </div>
            </div>
        `).join('') : '<p>No automations configured.</p>'}

        <div class="section-header" style="margin-top:24px">
            <div><h3>Recent Runs</h3></div>
        </div>
        ${runs.length ? runs.slice(0, 15).map(run => `
            <div class="meta" style="padding:7px 0;border-bottom:1px solid rgba(255,255,255,.08)">
                Run #${run.id} · Workflow #${run.workflow_id} · ${escapeAdmin(run.status)}
                ${run.error_message ? ` · ${escapeAdmin(run.error_message)}` : ''}
            </div>
        `).join('') : '<p class="meta">No runs yet.</p>'}
    `);
}


async function openNewAutomation(companyId) {
    xvondAutomationCompanyId = companyId;
    xvondAutomationDraftSteps = [];

    const [companyData, integrationsData] = await Promise.all([
        api(`/admin/company-view/${companyId}`),
        api(`/admin/integrations/companies/${companyId}`),
    ]);
    xvondAutomationAgents = companyData.agents || [];
    xvondAutomationIntegrations = integrationsData.integrations || [];

    showWorkspaceModal('New Automation', `
        <div class="form-group">
            <label>Workflow name</label>
            <input id="automation-name" placeholder="Process supplier invoice">
        </div>
        <div class="form-group">
            <label>Starts when</label>
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
            <button type="button" style="margin-top:10px" onclick="openAddAutomationStep()">+ Add Step</button>
        </div>

        <button class="modal-submit" onclick="saveAutomation(${companyId})">Create Workflow</button>
    `);
}


function openAddAutomationStep() {
    openModal('Add Automation Step', `
        <div class="form-group">
            <label>Step type</label>
            <select id="automation-step-type" onchange="renderAutomationStepFields()">
                <option value="ai">AI task</option>
                <option value="tool">Business action</option>
                <option value="webhook">Send webhook</option>
                <option value="condition">Condition</option>
                <option value="transform">Set / transform value</option>
            </select>
        </div>
        <div id="automation-step-fields"></div>
        <button class="modal-submit" onclick="saveAutomationDraftStep()">Add Step</button>
    `);
    renderAutomationStepFields();
}


function automationAgentOptions() {
    return xvondAutomationAgents.map(agent => `
        <option value="${agent.id}">${escapeAdmin(agent.name)}</option>
    `).join('');
}


function automationWebhookOptions() {
    return xvondAutomationIntegrations
        .filter(item => item.integration_type === 'webhook' && item.enabled)
        .map(item => `<option value="${item.id}">${escapeAdmin(item.name)}</option>`)
        .join('');
}


function renderAutomationStepFields() {
    const type = document.getElementById('automation-step-type')?.value;
    const target = document.getElementById('automation-step-fields');
    if (!target) return;

    if (type === 'ai') {
        target.innerHTML = `
            <div class="form-group"><label>AI Agent</label>
                <select id="automation-step-agent">${automationAgentOptions()}</select>
            </div>
            <div class="form-group"><label>Instruction</label>
                <textarea id="automation-step-prompt" placeholder="Read the input and extract the invoice details"></textarea>
            </div>
        `;
        return;
    }

    if (type === 'tool') {
        target.innerHTML = `
            <div class="form-group"><label>Agent</label>
                <select id="automation-step-agent">${automationAgentOptions()}</select>
            </div>
            <div class="form-group"><label>Business action</label>
                <select id="automation-step-tool">
                    <option value="lead">Create / update lead</option>
                    <option value="booking">Booking</option>
                    <option value="order">Order</option>
                    <option value="human_handoff">Human handoff</option>
                    <option value="webhook">Webhook tool</option>
                    <option value="custom_api">Custom API tool</option>
                </select>
            </div>
            <div class="form-group"><label>Action values</label>
                <input id="automation-step-arguments" placeholder="name=Ali, phone=968..., status=new">
            </div>
            <p class="meta">Write values as key=value separated by commas. No JSON needed.</p>
        `;
        return;
    }

    if (type === 'webhook') {
        target.innerHTML = `
            <div class="form-group"><label>Webhook integration</label>
                <select id="automation-step-integration">${automationWebhookOptions()}</select>
            </div>
        `;
        return;
    }

    if (type === 'condition') {
        target.innerHTML = `
            <div class="form-group"><label>Field</label><input id="automation-step-field" placeholder="status"></div>
            <div class="form-group"><label>Must equal</label><input id="automation-step-equals" placeholder="approved"></div>
        `;
        return;
    }

    target.innerHTML = `
        <div class="form-group"><label>Field</label><input id="automation-step-field" placeholder="department"></div>
        <div class="form-group"><label>Value</label><input id="automation-step-value" placeholder="Sales"></div>
    `;
}


function parseAutomationPairs(raw) {
    const result = {};
    for (const part of String(raw || '').split(',')) {
        const index = part.indexOf('=');
        if (index < 1) continue;
        const key = part.slice(0, index).trim();
        const value = part.slice(index + 1).trim();
        if (key) result[key] = value;
    }
    return result;
}


function saveAutomationDraftStep() {
    const type = document.getElementById('automation-step-type').value;
    let step = {type};

    if (type === 'ai') {
        const agentId = Number(document.getElementById('automation-step-agent').value);
        const prompt = document.getElementById('automation-step-prompt').value.trim();
        if (!agentId || !prompt) return alert('Select an agent and enter an instruction.');
        step = {type, agent_id: agentId, prompt, label: prompt};
    }

    if (type === 'tool') {
        const agentId = Number(document.getElementById('automation-step-agent').value);
        const toolName = document.getElementById('automation-step-tool').value;
        if (!agentId || !toolName) return alert('Select an agent and business action.');
        step = {
            type,
            agent_id: agentId,
            tool_name: toolName,
            arguments: parseAutomationPairs(document.getElementById('automation-step-arguments').value),
            label: `Business action: ${toolName}`,
        };
    }

    if (type === 'webhook') {
        const integrationId = Number(document.getElementById('automation-step-integration').value);
        if (!integrationId) return alert('Create or select a webhook integration first.');
        step = {type, integration_id: integrationId, label: 'Send webhook'};
    }

    if (type === 'condition') {
        const field = document.getElementById('automation-step-field').value.trim();
        const equals = document.getElementById('automation-step-equals').value.trim();
        if (!field) return alert('Condition field is required.');
        step = {type, field, equals, label: `${field} = ${equals}`};
    }

    if (type === 'transform') {
        const field = document.getElementById('automation-step-field').value.trim();
        const value = document.getElementById('automation-step-value').value.trim();
        if (!field) return alert('Field is required.');
        step = {type, values: {[field]: value}, label: `Set ${field}`};
    }

    xvondAutomationDraftSteps.push(step);
    closeModal();
    reopenAutomationDraft();
}


function reopenAutomationDraft() {
    const companyId = xvondAutomationCompanyId;
    showWorkspaceModal('New Automation', `
        <div class="form-group">
            <label>Workflow name</label>
            <input id="automation-name" value="${escapeAttributeService(window.xvondAutomationName || '')}" oninput="window.xvondAutomationName=this.value">
        </div>
        <div class="form-group">
            <label>Starts when</label>
            <select id="automation-trigger" onchange="window.xvondAutomationTrigger=this.value">
                ${['manual','webhook','schedule','event'].map(value => `<option value="${value}" ${(window.xvondAutomationTrigger || 'manual') === value ? 'selected' : ''}>${value}</option>`).join('')}
            </select>
        </div>
        <div class="panel" style="margin:15px 0">
            <h3>Steps</h3>
            <div id="automation-step-list"></div>
            <button type="button" style="margin-top:10px" onclick="openAddAutomationStep()">+ Add Step</button>
        </div>
        <button class="modal-submit" onclick="saveAutomation(${companyId})">Create Workflow</button>
    `);
    renderAutomationDraftSteps();
}


async function saveAutomation(companyId) {
    const nameElement = document.getElementById('automation-name');
    const triggerElement = document.getElementById('automation-trigger');
    const name = (nameElement?.value || window.xvondAutomationName || '').trim();
    const trigger = triggerElement?.value || window.xvondAutomationTrigger || 'manual';

    if (!name) return alert('Workflow name is required.');
    if (!xvondAutomationDraftSteps.length) return alert('Add at least one step.');

    try {
        await api(`/admin/automation/companies/${companyId}`, {
            method: 'POST',
            body: JSON.stringify({
                name,
                trigger_type: trigger,
                trigger_config: {},
                steps: xvondAutomationDraftSteps,
            }),
        });
        window.xvondAutomationName = '';
        window.xvondAutomationTrigger = 'manual';
        await openAutomationWorkspace(companyId);
    } catch (error) {
        alert(error.message);
    }
}


async function toggleAutomation(workflowId, enabled, companyId) {
    try {
        await api(`/admin/automation/${workflowId}`, {
            method: 'PATCH',
            body: JSON.stringify({enabled}),
        });
        await openAutomationWorkspace(companyId);
    } catch (error) {
        alert(error.message);
    }
}


async function runAutomationNow(workflowId, companyId) {
    try {
        const result = await api(`/admin/automation/${workflowId}/run`, {
            method: 'POST',
            body: JSON.stringify({input_data: {}}),
        });
        alert(`Run ${result.status}.`);
        await openAutomationWorkspace(companyId);
    } catch (error) {
        alert(error.message);
        await openAutomationWorkspace(companyId);
    }
}
