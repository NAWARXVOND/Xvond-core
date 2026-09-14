(() => {
    const mutationState = {busy: false};

    function setSyncNote(text, ok = true) {
        let note = document.getElementById("canonical-sync-note");
        const main = document.querySelector(".main");
        if (!main) return;
        if (!note) {
            note = document.createElement("div");
            note.id = "canonical-sync-note";
            note.className = "canonical-sync-note";
            const topbar = main.querySelector(".topbar");
            if (topbar?.nextSibling) main.insertBefore(note, topbar.nextSibling);
            else main.prepend(note);
        }
        note.innerHTML = `<span><strong>${ok ? "Live workspace" : "Sync notice"}</strong> · ${safe(text)}</span><span>${ok ? "Server-backed" : "Check connection"}</span>`;
    }

    function serviceAlertLabel(alert) {
        if (alert?.type === "usage_limit") {
            const metric = String(alert.metric || "usage").replaceAll("_", " ");
            const percent = Math.round(Number(alert.ratio || 0) * 100);
            return `${alert.service_name || alert.service_code}: ${metric} is at ${percent}% (${alert.used}/${alert.limit}).`;
        }
        if (alert?.type === "subscription_expiring") {
            const end = alert.period_end ? new Date(alert.period_end).toLocaleString() : "soon";
            return `${alert.service_name || alert.service_code}: current service period ends ${end}.`;
        }
        return "Service needs attention.";
    }

    function renderCanonicalHealth() {
        const page = document.getElementById("page-dashboard");
        const cardTarget = document.getElementById("dashboard-cards");
        if (!page || !cardTarget) return;

        let panel = document.getElementById("customer-operational-health");
        const health = portalOverview?.health;
        if (!health || portalOverview?.portal?.access_level !== "manager") {
            panel?.remove();
            return;
        }
        if (!panel) {
            panel = document.createElement("div");
            panel.id = "customer-operational-health";
            panel.className = "panel customer-health-panel";
            cardTarget.insertAdjacentElement("afterend", panel);
        }

        const alerts = [];
        if (Number(health.failed_ai_requests_24h || 0) > 0) {
            alerts.push(`${health.failed_ai_requests_24h} AI request failure${Number(health.failed_ai_requests_24h) === 1 ? "" : "s"} in the last 24 hours.`);
        }
        if (Number(health.active_handoffs || 0) > 0) {
            alerts.push(`${health.active_handoffs} conversation${Number(health.active_handoffs) === 1 ? "" : "s"} currently need human handling.`);
        }
        if (Number(health.active_agents_without_channel || 0) > 0) {
            alerts.push(`${health.active_agents_without_channel} active AI employee${Number(health.active_agents_without_channel) === 1 ? " has" : "s have"} no active customer channel.`);
        }
        for (const item of health.service_alerts || []) alerts.push(serviceAlertLabel(item));

        const status = String(health.status || "healthy");
        const statusLabel = status === "critical" ? "Action required" : status === "attention" ? "Needs attention" : "Healthy";
        const runtime = health.last_24h || {};
        panel.innerHTML = `
            <div class="customer-health-head">
                <div>
                    <span class="customer-health-eyebrow">Operational status</span>
                    <h2>Your Xvond workspace</h2>
                    <p>Runtime health, human handoffs, channel readiness and service limits.</p>
                </div>
                <span class="customer-health-status ${safe(status)}">${safe(statusLabel)}</span>
            </div>
            <div class="customer-health-metrics">
                <div><span>AI requests · 24h</span><strong>${safe(runtime.ai_requests || 0)}</strong></div>
                <div><span>Tokens · 24h</span><strong>${safe(runtime.tokens || 0)}</strong></div>
                <div><span>Average latency</span><strong>${safe(Math.round(Number(runtime.avg_latency_ms || 0)))} ms</strong></div>
                <div><span>Active handoffs</span><strong>${safe(health.active_handoffs || 0)}</strong></div>
            </div>
            <div class="customer-health-alerts ${alerts.length ? "has-alerts" : "healthy"}">
                ${alerts.length
                    ? alerts.map(item => `<div class="customer-health-alert"><span></span><p>${safe(item)}</p></div>`).join("")
                    : '<div class="customer-health-ok">No operational issues or service-limit warnings right now.</div>'}
            </div>
        `;
    }

    async function refreshCanonicalOverview({render = true} = {}) {
        if (!currentUser) return null;
        portalOverview = await api("/customer/overview");
        portalNavigation = portalOverview?.portal?.navigation || fallbackPortalNavigation();
        if (render) {
            renderPortalNavigation();
            renderAccountInfo();
            renderDashboard();
        }
        setSyncNote("Business information, AI employee settings, knowledge, services and usage are read from Xvond's canonical backend.");
        return portalOverview;
    }

    function wrapMutation(name, {refreshOverview = true, refreshAgent = false} = {}) {
        const original = window[name];
        if (typeof original !== "function" || original.__xvondCanonicalWrapped) return;
        const wrapped = async function(...args) {
            if (mutationState.busy) return;
            mutationState.busy = true;
            try {
                const result = await original.apply(this, args);
                if (refreshOverview && currentUser) await refreshCanonicalOverview({render: false});
                if (refreshAgent && customerManagedAgentId) {
                    customerManagedAgent = await api(`/customer/agents/${customerManagedAgentId}`);
                }
                setSyncNote("Latest saved values were confirmed from the server and are shared with Xvond Admin.");
                renderCanonicalHealth();
                return result;
            } finally {
                mutationState.busy = false;
            }
        };
        wrapped.__xvondCanonicalWrapped = true;
        window[name] = wrapped;
    }

    const baseRenderDashboard = window.renderDashboard;
    if (typeof baseRenderDashboard === "function") {
        window.renderDashboard = function(...args) {
            const result = baseRenderDashboard.apply(this, args);
            renderCanonicalHealth();
            return result;
        };
    }

    const baseStartPortal = window.startPortal;
    if (typeof baseStartPortal === "function") {
        window.startPortal = async function(...args) {
            const result = await baseStartPortal.apply(this, args);
            if (currentUser && portalOverview) {
                setSyncNote("This portal uses the same company, AI employee, knowledge, subscription and usage records as Xvond Admin.");
                renderCanonicalHealth();
            }
            return result;
        };
    }

    const baseRenderCustomerBehaviorTab = window.renderCustomerBehaviorTab;
    if (typeof baseRenderCustomerBehaviorTab === "function") {
        window.renderCustomerBehaviorTab = function(target) {
            baseRenderCustomerBehaviorTab(target);
            target?.querySelector("#ca-message")?.classList.add("customer-save-message");
        };
    }

    const baseOpenManagerSettings = window.openCustomerAgentSettings;
    if (typeof baseOpenManagerSettings === "function") {
        window.openCustomerAgentSettings = async function(agentId) {
            await baseOpenManagerSettings(agentId);
            const tabHost = document.querySelector("#customer-agent-settings .panel > div:nth-of-type(2)");
            if (tabHost) tabHost.classList.add("manager-tabs");
        };
    }

    wrapMutation("saveCustomerAgentSettings", {refreshOverview: true, refreshAgent: true});
    wrapMutation("saveCustomerBusinessInformation", {refreshOverview: true});
    wrapMutation("saveCustomerKnowledge", {refreshOverview: true});
    wrapMutation("toggleCustomerKnowledge", {refreshOverview: true});
    wrapMutation("deleteCustomerKnowledge", {refreshOverview: true});
    wrapMutation("addCustomerKnowledgeUrl", {refreshOverview: true});
    wrapMutation("uploadCustomerKnowledgePdf", {refreshOverview: true});
    wrapMutation("createCompanyUser", {refreshOverview: true});
    wrapMutation("setCompanyUserStatus", {refreshOverview: true});

    window.refreshCanonicalOverview = refreshCanonicalOverview;
})();