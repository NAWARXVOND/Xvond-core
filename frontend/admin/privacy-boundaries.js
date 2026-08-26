// Xvond Admin is the operator/configuration control plane.
// Customer conversations and customer-created business request payloads belong
// to the tenant Customer Portal (or the tenant's connected external system).

(function installAdminPrivacyBoundaries() {
    const originalRenderCompanyControlCenter = renderCompanyControlCenter;
    const originalRenderOverviewTab = renderOverviewTab;
    const originalRenderAgentActionsEditor = renderAgentActionsEditor;

    function removePrivateCustomerControls() {
        document.querySelectorAll('.workspace-tab').forEach(button => {
            const label = (button.textContent || '').trim();
            if (label === 'Operations' || label === 'Conversations') {
                button.remove();
            }
        });

        document.querySelectorAll('.employee-actions button').forEach(button => {
            const action = button.getAttribute('onclick') || '';
            if (action.includes('openHumanTakeover') || action.includes('openHumanConversation')) {
                button.remove();
            }
        });

        document.querySelectorAll('.metric-card').forEach(card => {
            const label = (card.querySelector('span')?.textContent || '').trim();
            if (label === 'Open Operations' || label === 'Conversations') {
                card.remove();
            }
        });
    }

    renderOverviewTab = function renderPrivacyAwareOverview() {
        const readiness = xvondWorkspace.data?.readiness;
        if (readiness) {
            // Backend canonical field. Keep this compatibility assignment until
            // every old admin renderer has migrated off profile_ready.
            readiness.profile_ready = readiness.company_profile_ready;
        }
        return originalRenderOverviewTab();
    };

    renderCompanyControlCenter = function renderPrivacyAwareCompanyControlCenter() {
        if (xvondWorkspace.tab === 'operations' || xvondWorkspace.tab === 'conversations') {
            xvondWorkspace.tab = 'overview';
        }
        originalRenderCompanyControlCenter();
        removePrivateCustomerControls();
    };

    renderAgentActionsEditor = function renderPrivacyAwareAgentActionsEditor() {
        originalRenderAgentActionsEditor();
        document.querySelectorAll('#modal-body .modal-section-divider').forEach(section => {
            const heading = (section.querySelector('h3')?.textContent || '').trim();
            if (heading === 'Real Customer Operations') {
                section.remove();
            }
        });
    };

    loadCompanyControlCenter = async function loadPrivacyAwareCompanyControlCenter(companyId, tab = null) {
        simpleCompanyId = Number(companyId);
        xvondWorkspace.companyId = Number(companyId);
        if (tab && !['operations', 'conversations'].includes(tab)) {
            xvondWorkspace.tab = tab;
        } else if (['operations', 'conversations'].includes(xvondWorkspace.tab)) {
            xvondWorkspace.tab = 'overview';
        }

        const [
            view,
            channelResult,
            moduleResult,
            catalog,
            integrations,
            usage,
            profile,
            setup,
            audit,
            serviceBilling,
            servicePlans,
            users,
            readiness,
        ] = await Promise.all([
            api(`/admin/company-view/${companyId}`),
            api(`/admin/channels/companies/${companyId}`),
            api(`/admin/companies/${companyId}/modules`),
            api('/admin/agent-actions/templates/catalog'),
            api(`/admin/integrations/companies/${companyId}`),
            api(`/admin/operations/companies/${companyId}/usage`),
            api(`/admin/company-profile/${companyId}`),
            api('/admin/setup/catalog'),
            wsOptional(`/admin/audit/?company_id=${companyId}&limit=100`, {logs: [], total: 0}),
            wsOptional(`/admin/service-billing/companies/${companyId}`, {services: []}),
            wsOptional('/admin/service-billing/plans', {plans: []}),
            wsOptional(`/admin/company-users/companies/${companyId}`, {users: []}),
            wsOptional(`/admin/production/companies/${companyId}/readiness`, null),
        ]);

        const agentMeta = await Promise.all((view.agents || []).map(async agent => {
            const [agentProfile, knowledge, actions] = await Promise.all([
                wsOptional(`/admin/ai-employee-profile/companies/${companyId}/${agent.id}`, {name: agent.name}),
                wsOptional(`/admin/ai-employees/companies/${companyId}/${agent.id}/knowledge`, {items: []}),
                wsOptional(`/admin/agent-actions/${agent.id}`, {actions: [], ready: false}),
            ]);
            return {
                agent,
                profile: agentProfile,
                knowledge: knowledge.items || [],
                actions: actions.actions || [],
                operationsReady: !!actions.ready,
            };
        }));

        const billingServices = serviceBilling.services || [];
        xvondWorkspace.data = {
            view,
            channels: channelResult.channels || [],
            modules: moduleResult.modules || [],
            catalog,
            integrations: integrations.integrations || [],
            // Customer-created content is intentionally not loaded into Admin.
            requests: [],
            conversations: [],
            handoffs: [],
            unresolved: [],
            usage,
            profile,
            setup,
            audit: audit.logs || [],
            billingServices,
            plans: servicePlans.plans || [],
            users: (users.users && users.users.length ? users.users : view.users) || [],
            readiness,
            agentMeta,
        };

        renderCompanyControlCenter();
    };

    openAgentActions = async function openPrivacyAwareAgentActions(companyId, agentId) {
        try {
            const [cfg, templates, integrations, profile, companyModules] = await Promise.all([
                api(`/admin/agent-actions/${agentId}`),
                api('/admin/agent-actions/templates/catalog'),
                api(`/admin/integrations/companies/${companyId}`),
                api(`/admin/ai-employee-profile/companies/${companyId}/${agentId}`),
                api(`/admin/companies/${companyId}/modules`),
            ]);
            xvondActionEditor = {
                companyId: Number(companyId),
                agentId: Number(agentId),
                templateId: cfg.template_id || null,
                actions: deepClone(cfg.actions || []),
                templates: templates.templates || [],
                businessModules: templates.business_modules || [],
                companyModules: companyModules.modules || [],
                integrations: integrations.integrations || [],
                requests: [],
                businessType: profile.business_type || '',
            };
            renderAgentActionsEditor();
        } catch (error) {
            alert(error.message);
        }
    };

    openSimpleCompany = loadCompanyControlCenter;
    window.openCompany = loadCompanyControlCenter;
})();
