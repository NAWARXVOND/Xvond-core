(() => {
    async function renderBusinessProfilePage() {
        const target = document.getElementById("customer-business-profile-content");
        if (!target) return;
        if (typeof renderCustomerBusinessTab !== "function") {
            target.innerHTML = '<div class="error">Business Profile is unavailable.</div>';
            return;
        }
        target.innerHTML = '<p class="muted">Loading business profile...</p>';
        await renderCustomerBusinessTab(target);
    }

    function accountPageRefresh() {
        if (typeof renderAccountInfo === "function") renderAccountInfo();
    }

    const baseOpenPage = window.openPage;
    if (typeof baseOpenPage === "function") {
        window.openPage = async function xvondStructuredOpenPage(name, button) {
            const result = await baseOpenPage.apply(this, arguments);
            const item = (portalNavigation || []).find(entry => entry.id === name) || {};
            const loader = item.loader || name;
            if (loader === "business-profile") await renderBusinessProfilePage();
            if (loader === "account") accountPageRefresh();
            return result;
        };
    }

    function openBusinessProfileFromEmployee() {
        const button = [...document.querySelectorAll("#portal-nav .nav-item")]
            .find(item => item.dataset.page === "business-profile");
        if (typeof window.openPage === "function") {
            window.openPage("business-profile", button || null);
        }
    }
    window.openBusinessProfileFromEmployee = openBusinessProfileFromEmployee;

    const baseOpenManagerTab = window.openCustomerManagerTab;
    if (typeof baseOpenManagerTab === "function") {
        window.openCustomerManagerTab = async function structuredManagerTab(tab) {
            if (tab === "business") {
                openBusinessProfileFromEmployee();
                return;
            }
            return baseOpenManagerTab.apply(this, arguments);
        };
    }

    const baseOpenAgentSettings = window.openCustomerAgentSettings;
    if (typeof baseOpenAgentSettings === "function") {
        window.openCustomerAgentSettings = async function structuredAgentSettings(agentId) {
            const result = await baseOpenAgentSettings.apply(this, arguments);
            const target = document.getElementById("customer-agent-settings");
            if (!target) return result;

            const description = target.querySelector(".service-card-head p");
            if (description) {
                description.textContent = "Manage this employee's behavior and employee-specific knowledge. Company facts are managed once in Business Profile.";
            }

            [...target.querySelectorAll("button")].forEach(button => {
                const onclick = button.getAttribute("onclick") || "";
                if (onclick.includes("openCustomerManagerTab('business')") || button.textContent.trim() === "Business Information") {
                    button.remove();
                }
            });

            const tabArea = target.querySelector("#customer-manager-tab")?.previousElementSibling;
            if (tabArea && !target.querySelector(".business-profile-source-note")) {
                const note = document.createElement("div");
                note.className = "business-profile-source-note muted";
                note.style.margin = "8px 0 14px";
                note.innerHTML = 'Need to change services, hours, branches, phone, policies or business rules? <button type="button" class="table-button" onclick="openBusinessProfileFromEmployee()">Open Business Profile</button>';
                tabArea.insertAdjacentElement("afterend", note);
            }
            return result;
        };
    }

    window.renderBusinessProfilePage = renderBusinessProfilePage;
})();
