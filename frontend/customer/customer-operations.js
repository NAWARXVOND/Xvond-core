(() => {
    const state = {
        customers: [],
        customerQuery: "",
        selectedCustomer: null,
        notifications: null,
        analytics: null,
        analyticsDays: 30,
    };

    function pageTarget(id) {
        const page = document.getElementById(`page-${id}`);
        return page?.querySelector(".dynamic-page-content") || page;
    }

    function customerDisplayName(item) {
        return item.name || item.phone || item.email || item.external_contact_id || `Customer #${item.id}`;
    }

    function customerMatches(item, query) {
        const q = String(query || "").trim().toLowerCase();
        if (!q) return true;
        return [
            item.name,
            item.phone,
            item.email,
            item.external_contact_id,
            item.channel,
            ...(item.tags || []),
        ].some(value => String(value || "").toLowerCase().includes(q));
    }

    function metricCard(label, value, note = "") {
        return `<div class="card"><span>${safe(label)}</span><strong>${safe(value)}</strong>${note ? `<small>${safe(note)}</small>` : ""}</div>`;
    }

    async function loadCustomersWorkspace() {
        const target = pageTarget("customers");
        if (!target) return;
        target.innerHTML = '<div class="panel"><p class="muted">Loading customers…</p></div>';
        try {
            const result = await api("/customer/operations/customers");
            state.customers = result.customers || [];
            renderCustomersWorkspace();
        } catch (error) {
            target.innerHTML = `<div class="panel"><p>${safe(error.message)}</p></div>`;
        }
    }

    function renderCustomersWorkspace() {
        const target = pageTarget("customers");
        if (!target) return;
        const visible = state.customers.filter(item => customerMatches(item, state.customerQuery));
        const bookings = visible.reduce((sum, item) => sum + Number(item.metrics?.bookings || 0), 0);
        const orders = visible.reduce((sum, item) => sum + Number(item.metrics?.orders || 0), 0);
        const leads = visible.reduce((sum, item) => sum + Number(item.metrics?.leads || 0), 0);
        target.innerHTML = `
            <div class="cards" style="margin-bottom:20px">
                ${metricCard("Customers", visible.length, visible.length !== state.customers.length ? `${state.customers.length} total` : "")}
                ${metricCard("Bookings", bookings)}
                ${metricCard("Orders", orders)}
                ${metricCard("Leads", leads)}
            </div>
            <div class="panel" style="margin-bottom:20px">
                <div class="service-card-head">
                    <div>
                        <h2>Customer 360</h2>
                        <p class="muted">Customer identity and history stay inside your company workspace.</p>
                    </div>
                    <button type="button" onclick="refreshCustomerWorkspace()">Refresh</button>
                </div>
                <div class="chat-input" style="margin-top:14px">
                    <input id="customer-ops-search" value="${safe(state.customerQuery)}" placeholder="Search name, phone, email or tag" oninput="filterCustomerWorkspace(this.value)">
                </div>
                <div style="margin-top:16px">
                    ${visible.length ? visible.map(item => `
                        <div class="agent" style="cursor:pointer" onclick="openCustomerWorkspaceDetail(${item.id})">
                            <div class="service-card-head">
                                <div>
                                    <strong>${safe(customerDisplayName(item))}</strong>
                                    <p>${safe(item.phone || item.email || item.external_contact_id || "No contact detail")}</p>
                                </div>
                                <span class="pill">${safe(item.channel || "multi-channel")}</span>
                            </div>
                            <p class="muted">Bookings ${Number(item.metrics?.bookings || 0)} · Orders ${Number(item.metrics?.orders || 0)} · Leads ${Number(item.metrics?.leads || 0)} · Conversations ${Number(item.metrics?.conversations || 0)}</p>
                            ${(item.tags || []).length ? `<p>${(item.tags || []).map(tag => `<span class="pill">${safe(tag)}</span>`).join(" ")}</p>` : ""}
                        </div>
                    `).join("") : '<p class="muted">No customers match this search.</p>'}
                </div>
            </div>
            <div id="customer-ops-detail"></div>
        `;
        if (state.selectedCustomer) renderCustomerDetail(state.selectedCustomer);
    }

    async function openCustomerWorkspaceDetail(customerId) {
        const host = document.getElementById("customer-ops-detail");
        if (host) host.innerHTML = '<div class="panel"><p class="muted">Loading customer…</p></div>';
        try {
            const result = await api(`/customer/operations/customers/${customerId}`);
            state.selectedCustomer = result;
            renderCustomerDetail(result);
        } catch (error) {
            if (host) host.innerHTML = `<div class="panel"><p>${safe(error.message)}</p></div>`;
        }
    }

    function activityRows(data) {
        const rows = [];
        for (const item of (data.bookings || []).slice(0, 8)) {
            rows.push(["Booking", item.service || `#${item.id}`, item.status, item.created_at]);
        }
        for (const item of (data.orders || []).slice(0, 8)) {
            rows.push(["Order", `#${item.id}`, item.status, item.created_at]);
        }
        for (const item of (data.leads || []).slice(0, 8)) {
            rows.push(["Lead", item.interest || `#${item.id}`, item.status, item.created_at]);
        }
        for (const item of (data.conversations || []).slice(0, 8)) {
            rows.push(["Conversation", item.title || `#${item.id}`, item.channel || "internal", item.created_at]);
        }
        return rows
            .sort((a, b) => new Date(b[3] || 0) - new Date(a[3] || 0))
            .slice(0, 12);
    }

    function renderCustomerDetail(data) {
        const host = document.getElementById("customer-ops-detail");
        if (!host || !data?.customer) return;
        const customer = data.customer;
        const rows = activityRows(data);
        host.innerHTML = `
            <div class="panel" style="margin-bottom:20px">
                <div class="service-card-head">
                    <div><h2>${safe(customerDisplayName(customer))}</h2><p class="muted">Customer profile</p></div>
                    <span class="pill">${safe(customer.channel || "multi-channel")}</span>
                </div>
                <div class="service-grid" style="margin-top:16px">
                    <label>Name<input id="customer-edit-name" value="${safe(customer.name || "")}"></label>
                    <label>Phone<input id="customer-edit-phone" value="${safe(customer.phone || "")}"></label>
                    <label>Email<input id="customer-edit-email" value="${safe(customer.email || "")}"></label>
                    <label>Tags<input id="customer-edit-tags" value="${safe((customer.tags || []).join(", "))}" placeholder="VIP, Repeat customer"></label>
                </div>
                <label style="display:block;margin-top:12px">Notes<textarea id="customer-edit-notes">${safe(customer.notes || "")}</textarea></label>
                <div class="chat-input" style="margin-top:12px"><button type="button" onclick="saveCustomerWorkspaceDetail(${customer.id})">Save customer</button></div>
            </div>
            <div class="panel">
                <h2>Recent activity</h2>
                ${rows.length ? rows.map(row => `
                    <div class="billing-row">
                        <span><strong>${safe(row[0])}</strong> · ${safe(row[1])}</span>
                        <strong>${safe(row[2] || "-")} · ${formatDate(row[3])}</strong>
                    </div>
                `).join("") : '<p class="muted">No linked activity yet.</p>'}
            </div>
        `;
        host.scrollIntoView({behavior: "smooth", block: "start"});
    }

    async function saveCustomerWorkspaceDetail(customerId) {
        const payload = {
            name: document.getElementById("customer-edit-name")?.value?.trim() || null,
            phone: document.getElementById("customer-edit-phone")?.value?.trim() || null,
            email: document.getElementById("customer-edit-email")?.value?.trim() || null,
            tags: String(document.getElementById("customer-edit-tags")?.value || "")
                .split(",").map(item => item.trim()).filter(Boolean),
            notes: document.getElementById("customer-edit-notes")?.value?.trim() || null,
        };
        try {
            await api(`/customer/operations/customers/${customerId}`, {
                method: "PUT",
                body: JSON.stringify(payload),
            });
            await loadCustomersWorkspace();
            await openCustomerWorkspaceDetail(customerId);
        } catch (error) {
            alert(error.message);
        }
    }

    async function loadCustomerNotifications() {
        const target = pageTarget("notifications");
        if (!target) return;
        target.innerHTML = '<div class="panel"><p class="muted">Loading notifications…</p></div>';
        try {
            state.notifications = await api("/customer/operations/notifications");
            renderCustomerNotifications();
        } catch (error) {
            target.innerHTML = `<div class="panel"><p>${safe(error.message)}</p></div>`;
        }
    }

    function renderCustomerNotifications() {
        const target = pageTarget("notifications");
        if (!target) return;
        const data = state.notifications || {events: [], unread: 0, preferences: {}};
        const pref = data.preferences || {};
        const selected = new Set(pref.event_types || []);
        const eventTypes = [
            ["booking_new", "New booking"],
            ["order_new", "New order"],
            ["lead_new", "New lead"],
            ["handoff_pending", "Human handoff"],
            ["operation_attention", "Operation needs attention"],
            ["ai_failure", "AI failure"],
        ];
        target.innerHTML = `
            <div class="cards" style="margin-bottom:20px">
                ${metricCard("Unread", data.unread || 0)}
                ${metricCard("Events", (data.events || []).length)}
                ${metricCard("Delivery", "Dashboard", "External delivery is not enabled yet")}
            </div>
            <div class="service-grid">
                <div class="panel">
                    <div class="service-card-head"><div><h2>Notification Center</h2><p class="muted">Operational events for your company.</p></div><button type="button" onclick="markCustomerNotificationsRead()">Mark all read</button></div>
                    ${(data.events || []).length ? (data.events || []).map(item => `
                        <div class="agent">
                            <div class="service-card-head">
                                <div><strong>${safe(item.title)}</strong><p>${safe(String(item.event_type || "").replaceAll("_", " "))} · ${formatDate(item.created_at)}</p></div>
                                <span class="pill">${safe(item.severity || "info")}${item.read ? "" : " · new"}</span>
                            </div>
                            ${item.message ? `<p>${safe(item.message)}</p>` : ""}
                        </div>
                    `).join("") : '<p class="muted">No notifications.</p>'}
                </div>
                <div class="panel">
                    <h2>Notification Rules</h2>
                    <p class="muted">Dashboard delivery is active. Email, WhatsApp and webhook delivery are intentionally hidden until a delivery service is implemented.</p>
                    <label><input id="customer-notifications-enabled" type="checkbox" ${pref.enabled !== false ? "checked" : ""}> Notifications enabled</label>
                    <div style="margin-top:14px">
                        ${eventTypes.map(([value, label]) => `<label style="display:block;margin:8px 0"><input class="customer-notification-event" type="checkbox" value="${safe(value)}" ${selected.has(value) ? "checked" : ""}> ${safe(label)}</label>`).join("")}
                    </div>
                    <button type="button" onclick="saveCustomerNotificationPreferences()">Save rules</button>
                </div>
            </div>
        `;
    }

    async function saveCustomerNotificationPreferences() {
        const eventTypes = [...document.querySelectorAll(".customer-notification-event")]
            .filter(item => item.checked)
            .map(item => item.value);
        try {
            await api("/customer/operations/notification-preferences", {
                method: "PUT",
                body: JSON.stringify({
                    enabled: Boolean(document.getElementById("customer-notifications-enabled")?.checked),
                    event_types: eventTypes,
                    destinations: ["dashboard"],
                }),
            });
            await loadCustomerNotifications();
        } catch (error) {
            alert(error.message);
        }
    }

    async function markCustomerNotificationsRead() {
        try {
            await api("/customer/operations/notifications/read-all", {method: "POST", body: "{}"});
            await loadCustomerNotifications();
        } catch (error) {
            alert(error.message);
        }
    }

    async function loadCustomerAnalytics(days = state.analyticsDays) {
        const target = pageTarget("business-analytics");
        if (!target) return;
        state.analyticsDays = Number(days) || 30;
        target.innerHTML = '<div class="panel"><p class="muted">Loading analytics…</p></div>';
        try {
            state.analytics = await api(`/customer/operations/analytics?days=${state.analyticsDays}`);
            renderCustomerAnalytics();
        } catch (error) {
            target.innerHTML = `<div class="panel"><p>${safe(error.message)}</p></div>`;
        }
    }

    function renderCustomerAnalytics() {
        const target = pageTarget("business-analytics");
        if (!target) return;
        const data = state.analytics || {kpis: {}, channels: [], agents: [], daily: []};
        const kpi = data.kpis || {};
        target.innerHTML = `
            <div class="panel" style="margin-bottom:20px">
                <div class="service-card-head">
                    <div><h2>Business Analytics</h2><p class="muted">Customer and operational outcomes, separate from raw AI usage.</p></div>
                    <select onchange="changeCustomerAnalyticsRange(this.value)">
                        ${[7, 30, 90, 365].map(days => `<option value="${days}" ${Number(data.days) === days ? "selected" : ""}>${days} days</option>`).join("")}
                    </select>
                </div>
                <div class="cards" style="margin-top:16px">
                    ${metricCard("Conversations", kpi.conversations || 0)}
                    ${metricCard("Bookings", kpi.bookings || 0)}
                    ${metricCard("Orders", kpi.orders || 0)}
                    ${metricCard("Leads", kpi.leads || 0)}
                    ${metricCard("Conversion", `${Number(kpi.conversion_rate || 0).toFixed(1)}%`)}
                    ${metricCard("Handoff rate", `${Number(kpi.handoff_rate || 0).toFixed(1)}%`)}
                    ${metricCard("AI failures", kpi.ai_failures || 0)}
                    ${metricCard("Provider cost", Number(kpi.provider_cost || 0).toFixed(3))}
                </div>
            </div>
            <div class="service-grid" style="margin-bottom:20px">
                <div class="panel"><h2>Channels</h2>${(data.channels || []).length ? data.channels.map(item => `<div class="billing-row"><span>${safe(item.channel)}</span><strong>${Number(item.conversations || 0)}</strong></div>`).join("") : '<p class="muted">No channel activity.</p>'}</div>
                <div class="panel"><h2>AI Employee Load</h2>${(data.agents || []).length ? data.agents.map(item => `<div class="billing-row"><span>${safe(item.name)}</span><strong>${Number(item.conversations || 0)}</strong></div>`).join("") : '<p class="muted">No employee activity.</p>'}</div>
            </div>
            <div class="panel">
                <h2>Daily Activity</h2>
                ${(data.daily || []).length ? `<div style="overflow:auto"><table><thead><tr><th>Date</th><th>Conversations</th><th>Bookings</th><th>Orders</th><th>Leads</th></tr></thead><tbody>${data.daily.map(item => `<tr><td>${safe(item.date)}</td><td>${Number(item.conversations || 0)}</td><td>${Number(item.bookings || 0)}</td><td>${Number(item.orders || 0)}</td><td>${Number(item.leads || 0)}</td></tr>`).join("")}</tbody></table></div>` : '<p class="muted">No activity in this period.</p>'}
            </div>
        `;
    }

    const baseOpenPage = window.openPage;
    window.openPage = async function customerOperationsOpenPage(name, button) {
        await baseOpenPage(name, button);
        const item = portalNavigation.find(entry => entry.id === name) || {};
        if (item.loader === "customers") await loadCustomersWorkspace();
        if (item.loader === "customer-notifications") await loadCustomerNotifications();
        if (item.loader === "customer-analytics") await loadCustomerAnalytics();
    };

    window.filterCustomerWorkspace = function filterCustomerWorkspace(value) {
        state.customerQuery = value || "";
        renderCustomersWorkspace();
        const input = document.getElementById("customer-ops-search");
        if (input) {
            input.focus();
            input.setSelectionRange(input.value.length, input.value.length);
        }
    };
    window.refreshCustomerWorkspace = loadCustomersWorkspace;
    window.openCustomerWorkspaceDetail = openCustomerWorkspaceDetail;
    window.saveCustomerWorkspaceDetail = saveCustomerWorkspaceDetail;
    window.saveCustomerNotificationPreferences = saveCustomerNotificationPreferences;
    window.markCustomerNotificationsRead = markCustomerNotificationsRead;
    window.changeCustomerAnalyticsRange = loadCustomerAnalytics;
})();
