const XVOND_BILLING_SERVICE_LABELS = {
    ai_agents: 'AI Agents',
    automation: 'Business Automation',
    analytics: 'Data & AI Analytics',
    integrations: 'AI Integrations',
};

const XVOND_BILLING_PLAN_LIMIT_FIELDS = {
    ai_agents: [
        ['agents', 'Active AI Employees'],
        ['channels', 'Active Channels'],
        ['tokens', 'AI tokens / month'],
        ['requests', 'AI requests / month'],
    ],
    automation: [
        ['workflows', 'Workflows'],
        ['runs', 'Workflow runs / month'],
    ],
    analytics: [
        ['data_sources', 'Data sources'],
        ['dashboards', 'Dashboards'],
        ['records_ingested', 'Records ingested / month'],
    ],
    integrations: [
        ['integrations', 'Connected systems'],
    ],
};

function billingAttr(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('"', '&quot;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
}

function billingPlanLimitFields(serviceCode, limits = {}, prefix = 'billing-plan-limit') {
    return (XVOND_BILLING_PLAN_LIMIT_FIELDS[serviceCode] || []).map(([key, label]) => `
        <div class="form-group">
            <label>${f(label)}</label>
            <input
                type="number"
                min="0"
                step="1"
                id="${prefix}-${key}"
                value="${billingAttr(limits[key] ?? 0)}"
                placeholder="0 = unlimited"
            >
        </div>
    `).join('');
}

function billingReadLimits(serviceCode, prefix = 'billing-plan-limit') {
    const limits = {};
    for (const [key] of XVOND_BILLING_PLAN_LIMIT_FIELDS[serviceCode] || []) {
        const raw = Number(document.getElementById(`${prefix}-${key}`)?.value || 0);
        limits[key] = Number.isFinite(raw) && raw >= 0 ? raw : 0;
    }
    return limits;
}

function billingPlanLimitsSummary(plan) {
    const entries = Object.entries(plan.limits || {});
    if (!entries.length) return 'No monthly limits';
    return entries.map(([key, value]) => {
        const label = (XVOND_BILLING_PLAN_LIMIT_FIELDS[plan.service_code] || [])
            .find(([metric]) => metric === key)?.[1] || key;
        const shown = value === 0 || value === '0' ? 'Unlimited' : value;
        return `${f(label)}: ${f(shown)}`;
    }).join(' · ');
}

function renderBillingTab() {
    const d = xvondWorkspace.data;
    const services = d.billingServices || [];
    const plans = (d.plans || []).filter(item => item.enabled);

    return `
        <div class="workspace-panel">
            <div class="workspace-panel-head">
                <div>
                    <h3>Service Billing</h3>
                    <p>Create Xvond packages, then assign the purchased service plan to this company.</p>
                </div>
                <div class="workspace-inline-actions">
                    <button class="table-button" onclick="openWorkspaceCreateServicePlan()">+ Create Package</button>
                    <button class="primary-button" onclick="openWorkspaceServiceForm()">+ Assign Service</button>
                </div>
            </div>

            ${services.length ? `
                <div class="integration-grid">
                    ${services.map(service => `
                        <div class="integration-card">
                            <div class="integration-card-head">
                                <div>
                                    <h4>${f(service.service_name || XVOND_BILLING_SERVICE_LABELS[service.service_code] || service.service_code)}</h4>
                                    <div class="meta">
                                        ${f(service.plan?.name || 'No plan')} · ${f(service.plan?.tier || '')} · ${f(service.plan?.currency || '')} ${f(service.plan?.monthly_price || 0)}
                                    </div>
                                </div>
                                ${wsPill(service.status, service.status === 'active' ? 'good' : service.status === 'expired' ? 'bad' : 'neutral')}
                            </div>
                            <div class="meta">Period: ${wsDate(service.current_period_start)} → ${wsDate(service.current_period_end)}</div>
                            <div class="info-stack">
                                ${Object.entries(service.usage || {}).map(([metric, row]) => `
                                    <div>
                                        <span>${f(metric)}</span>
                                        <strong>${f(row.used)} / ${row.limit === 0 || row.limit === '0' ? '∞' : f(row.limit)}</strong>
                                    </div>
                                `).join('')}
                            </div>
                            <div class="workspace-inline-actions">
                                <button class="table-button" onclick="openWorkspaceServiceForm('${service.service_code}')">Change Plan</button>
                                ${service.status === 'active'
                                    ? `<button class="table-button" onclick="setWorkspaceServiceStatus('${service.service_code}','paused')">Pause</button>`
                                    : `<button class="table-button" onclick="setWorkspaceServiceStatus('${service.service_code}','active')">Activate</button>`}
                                ${service.status !== 'cancelled'
                                    ? `<button class="table-button" onclick="setWorkspaceServiceStatus('${service.service_code}','cancelled')">Cancel</button>`
                                    : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : wsEmpty(
                'No services assigned',
                plans.length
                    ? 'Choose Assign Service to attach one of the available packages.'
                    : 'Create the first monthly package, then assign it to this company.'
            )}

            <div class="workspace-panel-head" style="margin-top:20px">
                <div>
                    <h3>Service Packages</h3>
                    <p>${plans.length ? `${plans.length} enabled package${plans.length === 1 ? '' : 's'} available.` : 'No packages created yet.'}</p>
                </div>
            </div>
            ${plans.length ? `
                <div class="integration-grid">
                    ${plans.map(plan => `
                        <div class="integration-card">
                            <div class="integration-card-head">
                                <div>
                                    <h4>${f(plan.name)}</h4>
                                    <div class="meta">${f(XVOND_BILLING_SERVICE_LABELS[plan.service_code] || plan.service_code)} · ${f(plan.tier)}</div>
                                </div>
                                ${wsPill(`${plan.currency} ${plan.monthly_price}`, 'neutral')}
                            </div>
                            <div class="meta">${billingPlanLimitsSummary(plan)}</div>
                            <div class="workspace-inline-actions">
                                <button class="table-button" onclick="openWorkspaceEditServicePlan(${plan.id})">Edit Package</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        </div>
    `;
}

function openWorkspaceCreateServicePlan() {
    const defaultCurrency = xvondWorkspace.data?.profile?.currency || 'OMR';
    openModal('Create Service Package', `
        <div class="form-group">
            <label>Service</label>
            <select id="billing-package-service" onchange="renderWorkspacePackageLimits()">
                ${Object.entries(XVOND_BILLING_SERVICE_LABELS)
                    .map(([code, label]) => `<option value="${code}">${f(label)}</option>`)
                    .join('')}
            </select>
        </div>
        <div class="form-group">
            <label>Package Tier</label>
            <select id="billing-package-tier">
                <option value="starter">Starter</option>
                <option value="business">Business</option>
                <option value="enterprise">Enterprise</option>
            </select>
        </div>
        <div class="form-group">
            <label>Display Name</label>
            <input id="billing-package-name" placeholder="Starter">
        </div>
        <div class="form-grid two">
            <div class="form-group">
                <label>Monthly Price</label>
                <input type="number" min="0" step="0.001" id="billing-package-price" value="0">
            </div>
            <div class="form-group">
                <label>Currency</label>
                <input id="billing-package-currency" value="${billingAttr(defaultCurrency)}">
            </div>
        </div>
        <div id="billing-package-limits"></div>
        <button class="modal-submit" onclick="saveWorkspaceNewServicePlan()">Create Package</button>
    `);
    renderWorkspacePackageLimits();
}

function renderWorkspacePackageLimits() {
    const serviceCode = document.getElementById('billing-package-service')?.value;
    const target = document.getElementById('billing-package-limits');
    if (!serviceCode || !target) return;
    target.innerHTML = `
        <h3 style="margin-top:16px">Monthly Limits</h3>
        <p class="meta">Use 0 for unlimited. Employee/channel limits are active-capacity limits; token/request limits reset each billing period.</p>
        ${billingPlanLimitFields(serviceCode)}
    `;
}

async function saveWorkspaceNewServicePlan() {
    const serviceCode = document.getElementById('billing-package-service').value;
    const tierElement = document.getElementById('billing-package-tier');
    const name = document.getElementById('billing-package-name').value.trim()
        || tierElement.selectedOptions[0].text;

    try {
        await api('/admin/service-billing/plans', {
            method: 'POST',
            body: JSON.stringify({
                service_code: serviceCode,
                tier: tierElement.value,
                name,
                monthly_price: Number(document.getElementById('billing-package-price').value || 0),
                currency: document.getElementById('billing-package-currency').value.trim() || 'OMR',
                limits: billingReadLimits(serviceCode),
            }),
        });
        closeModal();
        await loadCompanyControlCenter(xvondWorkspace.companyId, 'billing');
    } catch (error) {
        alert(error.message);
    }
}

function openWorkspaceEditServicePlan(planId) {
    const plan = (xvondWorkspace.data?.plans || []).find(item => Number(item.id) === Number(planId));
    if (!plan) {
        alert('Package not found.');
        return;
    }
    openModal(`Edit ${plan.name}`, `
        <div class="form-group">
            <label>Service</label>
            <input value="${billingAttr(XVOND_BILLING_SERVICE_LABELS[plan.service_code] || plan.service_code)}" disabled>
        </div>
        <div class="form-group">
            <label>Tier</label>
            <input value="${billingAttr(plan.tier)}" disabled>
        </div>
        <div class="form-group">
            <label>Display Name</label>
            <input id="billing-edit-name" value="${billingAttr(plan.name)}">
        </div>
        <div class="form-grid two">
            <div class="form-group">
                <label>Monthly Price</label>
                <input type="number" min="0" step="0.001" id="billing-edit-price" value="${billingAttr(plan.monthly_price)}">
            </div>
            <div class="form-group">
                <label>Currency</label>
                <input id="billing-edit-currency" value="${billingAttr(plan.currency)}">
            </div>
        </div>
        <h3 style="margin-top:16px">Monthly Limits</h3>
        <p class="meta">Use 0 for unlimited. Employee/channel limits are active-capacity limits; token/request limits reset each billing period.</p>
        ${billingPlanLimitFields(plan.service_code, plan.limits || {}, 'billing-edit-limit')}
        <button class="modal-submit" onclick="saveWorkspaceServicePlanEdit(${plan.id},'${plan.service_code}')">Save Package</button>
    `);
}

async function saveWorkspaceServicePlanEdit(planId, serviceCode) {
    try {
        await api(`/admin/service-billing/plans/${planId}`, {
            method: 'PATCH',
            body: JSON.stringify({
                name: document.getElementById('billing-edit-name').value.trim(),
                monthly_price: Number(document.getElementById('billing-edit-price').value || 0),
                currency: document.getElementById('billing-edit-currency').value.trim() || 'OMR',
                limits: billingReadLimits(serviceCode, 'billing-edit-limit'),
            }),
        });
        closeModal();
        await loadCompanyControlCenter(xvondWorkspace.companyId, 'billing');
    } catch (error) {
        alert(error.message);
    }
}

function openWorkspaceServiceForm(serviceCode = null) {
    const d = xvondWorkspace.data;
    const plans = (d.plans || []).filter(item => item.enabled);
    if (!plans.length) {
        openWorkspaceCreateServicePlan();
        return;
    }

    const codes = [...new Set(plans.map(item => item.service_code))];
    const selected = serviceCode
        || codes.find(code => !d.billingServices.some(service => service.service_code === code))
        || codes[0];

    openModal('Assign Service Plan', `
        <div class="form-group">
            <label>Service</label>
            <select id="wb-service" ${serviceCode ? 'disabled' : ''} onchange="renderWorkspaceServicePlans()">
                ${codes.map(code => wsOption(
                    code,
                    selected,
                    XVOND_BILLING_SERVICE_LABELS[code] || code
                )).join('')}
            </select>
        </div>
        <div class="form-group">
            <label>Plan</label>
            <select id="wb-plan"></select>
        </div>
        <button class="modal-submit" onclick="saveWorkspaceServicePlan()">Save Service Plan</button>
    `);
    renderWorkspaceServicePlans();
}

function renderWorkspaceServicePlans() {
    const code = document.getElementById('wb-service')?.value;
    if (!code) return;
    const current = xvondWorkspace.data.billingServices.find(item => item.service_code === code);
    const plans = xvondWorkspace.data.plans.filter(item => item.enabled && item.service_code === code);
    document.getElementById('wb-plan').innerHTML = plans.map(item => wsOption(
        item.id,
        current?.plan?.id,
        `${item.name} · ${item.currency} ${item.monthly_price}`
    )).join('');
}
