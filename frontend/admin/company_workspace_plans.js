const XVOND_PLAN_LIMIT_FIELDS = {
    ai_agents: [
        ['agents', 'AI Agents'],
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


async function openServiceSubscriptions(companyId) {
    const [plansData, currentData] = await Promise.all([
        api('/admin/service-billing/plans'),
        api(`/admin/service-billing/companies/${companyId}`),
    ]);

    const plans = plansData.plans || [];
    const current = new Map((currentData.services || []).map(x => [x.service_code, x]));

    showWorkspaceModal('Plans & Monthly Limits', `
        <div class="section-header">
            <div>
                <h3>Customer Plans</h3>
                <p>Each service has its own monthly package and usage limits.</p>
            </div>
            <button class="table-button" onclick="openCreateServicePlan(${companyId})">+ Create Package</button>
        </div>

        ${Object.entries(XVOND_SERVICE_LABELS).map(([serviceCode, label]) => {
            const servicePlans = plans.filter(plan => plan.service_code === serviceCode && plan.enabled);
            const subscription = current.get(serviceCode);
            return `
                <div class="agent-card" style="margin-bottom:12px">
                    <div>
                        <h3>${escapeAdmin(label)}</h3>
                        <div class="meta">
                            ${subscription
                                ? `Current: ${escapeAdmin(subscription.plan?.name || subscription.plan?.tier || '')} · ${escapeAdmin(subscription.status)}`
                                : 'Not subscribed'}
                        </div>
                        ${subscription ? renderUsageSummary(subscription.usage || {}) : ''}
                    </div>
                    <div class="form-row" style="margin-top:12px">
                        <select id="service-plan-${serviceCode}">
                            <option value="">Select package</option>
                            ${servicePlans.map(plan => `
                                <option value="${plan.id}" ${subscription?.plan?.id === plan.id ? 'selected' : ''}>
                                    ${escapeAdmin(plan.name)} · ${escapeAdmin(plan.monthly_price)} ${escapeAdmin(plan.currency)} / month
                                </option>
                            `).join('')}
                        </select>
                        <button onclick="applyServicePlan(${companyId},'${serviceCode}')">Apply</button>
                    </div>
                    ${servicePlans.length ? `
                        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
                            ${servicePlans.map(plan => `
                                <button class="table-button" onclick="openEditServicePlan(${companyId},${plan.id})">
                                    Edit ${escapeAdmin(plan.name)}
                                </button>
                            `).join('')}
                        </div>
                    ` : '<p class="meta">No package created for this service yet.</p>'}
                </div>
            `;
        }).join('')}
    `);
}


function planLimitFields(serviceCode, limits = {}) {
    return (XVOND_PLAN_LIMIT_FIELDS[serviceCode] || []).map(([key, label]) => `
        <div class="form-group">
            <label>${escapeAdmin(label)}</label>
            <input type="number" min="0" id="plan-limit-${key}" value="${escapeAttributeService(limits[key] ?? '')}" placeholder="0 = unlimited">
        </div>
    `).join('');
}


function openCreateServicePlan(companyId) {
    showWorkspaceModal('Create Monthly Package', `
        <div class="form-group"><label>Service</label>
            <select id="plan-service" onchange="renderPlanLimitFields()">
                ${Object.entries(XVOND_SERVICE_LABELS).map(([code, label]) => `<option value="${code}">${escapeAdmin(label)}</option>`).join('')}
            </select>
        </div>
        <div class="form-group"><label>Package</label>
            <select id="plan-tier">
                <option value="starter">Starter</option>
                <option value="business">Business</option>
                <option value="enterprise">Enterprise</option>
            </select>
        </div>
        <div class="form-group"><label>Display name</label><input id="plan-name" placeholder="Business"></div>
        <div class="form-row">
            <div class="form-group"><label>Monthly price</label><input type="number" min="0" step="0.001" id="plan-price" value="0"></div>
            <div class="form-group"><label>Currency</label><input id="plan-currency" value="OMR"></div>
        </div>
        <div id="plan-limits-fields"></div>
        <button class="modal-submit" onclick="saveNewServicePlan(${companyId})">Create Package</button>
    `);
    renderPlanLimitFields();
}


function renderPlanLimitFields() {
    const serviceCode = document.getElementById('plan-service')?.value;
    const target = document.getElementById('plan-limits-fields');
    if (!serviceCode || !target) return;
    target.innerHTML = `<h3 style="margin-top:15px">Monthly limits</h3>${planLimitFields(serviceCode)}`;
}


function readPlanLimits(serviceCode) {
    const limits = {};
    for (const [key] of XVOND_PLAN_LIMIT_FIELDS[serviceCode] || []) {
        const element = document.getElementById(`plan-limit-${key}`);
        const value = Number(element?.value || 0);
        limits[key] = Number.isFinite(value) && value >= 0 ? value : 0;
    }
    return limits;
}


async function saveNewServicePlan(companyId) {
    const serviceCode = document.getElementById('plan-service').value;
    try {
        await api('/admin/service-billing/plans', {
            method: 'POST',
            body: JSON.stringify({
                service_code: serviceCode,
                tier: document.getElementById('plan-tier').value,
                name: document.getElementById('plan-name').value.trim() || document.getElementById('plan-tier').selectedOptions[0].text,
                monthly_price: Number(document.getElementById('plan-price').value || 0),
                currency: document.getElementById('plan-currency').value.trim() || 'OMR',
                limits: readPlanLimits(serviceCode),
            }),
        });
        await openServiceSubscriptions(companyId);
    } catch (error) {
        alert(error.message);
    }
}


async function openEditServicePlan(companyId, planId) {
    const data = await api('/admin/service-billing/plans');
    const plan = (data.plans || []).find(item => Number(item.id) === Number(planId));
    if (!plan) return alert('Package not found.');

    showWorkspaceModal(`Edit ${plan.name}`, `
        <div class="form-group"><label>Name</label><input id="plan-edit-name" value="${escapeAttributeService(plan.name)}"></div>
        <div class="form-row">
            <div class="form-group"><label>Monthly price</label><input type="number" min="0" step="0.001" id="plan-edit-price" value="${escapeAttributeService(plan.monthly_price)}"></div>
            <div class="form-group"><label>Currency</label><input id="plan-edit-currency" value="${escapeAttributeService(plan.currency)}"></div>
        </div>
        <h3>Monthly limits</h3>
        ${planLimitFields(plan.service_code, plan.limits || {})}
        <button class="modal-submit" onclick="saveServicePlanEdit(${companyId},${plan.id},'${plan.service_code}')">Save Package</button>
    `);
}


async function saveServicePlanEdit(companyId, planId, serviceCode) {
    try {
        await api(`/admin/service-billing/plans/${planId}`, {
            method: 'PATCH',
            body: JSON.stringify({
                name: document.getElementById('plan-edit-name').value,
                monthly_price: Number(document.getElementById('plan-edit-price').value || 0),
                currency: document.getElementById('plan-edit-currency').value,
                limits: readPlanLimits(serviceCode),
            }),
        });
        await openServiceSubscriptions(companyId);
    } catch (error) {
        alert(error.message);
    }
}
