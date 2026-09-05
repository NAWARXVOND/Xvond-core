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
                return result;
            } finally {
                mutationState.busy = false;
            }
        };
        wrapped.__xvondCanonicalWrapped = true;
        window[name] = wrapped;
    }

    const baseStartPortal = window.startPortal;
    if (typeof baseStartPortal === "function") {
        window.startPortal = async function(...args) {
            const result = await baseStartPortal.apply(this, args);
            if (currentUser && portalOverview) {
                setSyncNote("This portal uses the same company, AI employee, knowledge, subscription and usage records as Xvond Admin.");
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
