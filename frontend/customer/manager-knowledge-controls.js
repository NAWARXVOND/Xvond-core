let customerManagedAgentId = null;
let customerManagedAgent = null;
let customerBusinessProfileCache = null;
let customerKnowledgeEditingId = null;

function managerTabButton(label, tab) {
    return `<button type="button" onclick="openCustomerManagerTab('${tab}')" style="margin-right:8px;margin-bottom:8px">${safe(label)}</button>`;
}

openCustomerAgentSettings = async function(agentId) {
    const target = document.getElementById("customer-agent-settings");
    if (!target) return;
    customerManagedAgentId = Number(agentId);
    try {
        customerManagedAgent = await api(`/customer/agents/${agentId}`);
        target.innerHTML = `
            <div class="panel" style="margin-top:18px">
                <div class="service-card-head">
                    <div><h2>Manage ${safe(customerManagedAgent.name)}</h2><p>Manage employee behavior, business information and knowledge.</p></div>
                </div>
                <div style="margin:14px 0">
                    ${managerTabButton("Behavior", "behavior")}
                    ${managerTabButton("Business Information", "business")}
                    ${managerTabButton("Knowledge", "knowledge")}
                </div>
                <div id="customer-manager-tab"></div>
            </div>
        `;
        await openCustomerManagerTab("behavior");
        target.scrollIntoView({behavior: "smooth", block: "start"});
    } catch (err) {
        target.innerHTML = `<div class="panel"><div class="error">${safe(err.message)}</div></div>`;
    }
};

async function openCustomerManagerTab(tab) {
    const target = document.getElementById("customer-manager-tab");
    if (!target || !customerManagedAgentId) return;
    if (tab === "behavior") renderCustomerBehaviorTab(target);
    else if (tab === "business") await renderCustomerBusinessTab(target);
    else if (tab === "knowledge") await renderCustomerKnowledgeTab(target);
}

function renderCustomerBehaviorTab(target) {
    const d = customerManagedAgent || {};
    const controls = d.controls || {};
    target.innerHTML = `
        ${customerSelect("ca-language", "Reply Language", [["auto","Automatic — match customer"],["ar","Arabic"],["en","English"],["ar_en","Arabic & English"]], d.reply_language || "auto")}
        ${customerSelect("ca-dialect", "Dialect", [["auto","Automatic — match customer"],["msa","Modern Standard Arabic"],["omani","Omani Arabic"],["gulf","Gulf Arabic"],["saudi","Saudi Arabic"],["emirati","Emirati Arabic"],["levantine","Levantine / Shami Arabic"],["egyptian","Egyptian Arabic"]], d.dialect || "auto")}
        ${customerSelect("ca-style", "Conversation Style", [["professional_friendly","Professional & Friendly"],["professional","Professional"],["warm","Warm & Conversational"],["concise","Concise"]], d.conversation_style || "professional_friendly")}
        ${customerSelect("ca-length", "Response Length", [["concise","Concise — recommended"],["balanced","Balanced"],["detailed","Detailed"]], d.response_length || "concise")}
        ${customerSelect("ca-clarification", "When a request is unclear", [["smart","Ask only when needed — recommended"],["ask_when_unclear","Ask one clarifying question"],["direct_first","Give a useful answer first"]], d.clarification_style || "smart")}
        ${customerSelect("ca-off-topic", "Personal or off-topic messages", [["business_redirect","Business focused — recommended"],["brief_friendly","Allow brief friendly small talk"]], d.off_topic_behavior || "business_redirect")}
        <div class="form-group"><label>Greeting</label><textarea id="ca-greeting" placeholder="Optional greeting">${safe(d.greeting || "")}</textarea></div>
        ${controls.can_edit_prompt ? `<div class="form-group"><label>Advanced Instructions</label><textarea id="ca-instructions">${safe(d.instructions || "")}</textarea></div>` : ""}
        ${controls.can_enable_disable ? `<label style="display:flex;gap:8px;align-items:center;margin:14px 0"><input id="ca-enabled" type="checkbox" ${d.enabled ? "checked" : ""}> AI Employee active</label>` : ""}
        <div id="ca-message" class="error"></div>
        <button onclick="saveCustomerAgentSettings(${Number(customerManagedAgentId)}, ${controls.can_edit_prompt ? "true" : "false"}, ${controls.can_enable_disable ? "true" : "false"})">Save Behavior</button>
    `;
}

function linesToList(value) {
    return String(value || "").split("\n").map(item => item.trim()).filter(Boolean);
}

function listToLines(value) {
    return Array.isArray(value) ? value.map(item => typeof item === "string" ? item : JSON.stringify(item)).join("\n") : "";
}

async function renderCustomerBusinessTab(target) {
    try {
        const d = await api("/customer/agents/manage/business-information");
        customerBusinessProfileCache = d;
        target.innerHTML = `
            <p class="muted">These facts are shared with all AI employees in your company and become protected Business Information knowledge.</p>
            <div class="form-group"><label>Business Name</label><input id="cb-name" value="${safe(d.company_name || "")}"></div>
            <div class="form-group"><label>Business Type</label><input id="cb-type" value="${safe(d.business_type || "")}" placeholder="Restaurant, clinic, store..."></div>
            <div class="form-group"><label>Description</label><textarea id="cb-description">${safe(d.description || "")}</textarea></div>
            <div class="form-group"><label>Phone</label><input id="cb-phone" value="${safe(d.phone || "")}"></div>
            <div class="form-group"><label>Email</label><input id="cb-email" type="email" value="${safe(d.email || "")}"></div>
            <div class="form-group"><label>Website</label><input id="cb-website" value="${safe(d.website || "")}"></div>
            <div class="form-group"><label>Services / Products</label><textarea id="cb-services" placeholder="One item per line">${safe(listToLines(d.services))}</textarea></div>
            <div class="form-group"><label>Locations / Branches</label><textarea id="cb-locations" placeholder="One item per line">${safe(listToLines(d.locations))}</textarea></div>
            <div class="form-group"><label>Service Areas</label><textarea id="cb-areas" placeholder="One item per line">${safe(listToLines(d.service_areas))}</textarea></div>
            <div class="form-group"><label>Policies</label><textarea id="cb-policies" placeholder="One policy per line">${safe(listToLines(d.policies))}</textarea></div>
            <div class="form-group"><label>Business Rules</label><textarea id="cb-rules" placeholder="One rule per line">${safe(listToLines(d.business_rules))}</textarea></div>
            <div id="cb-message" class="error"></div>
            <button onclick="saveCustomerBusinessInformation()">Save Business Information</button>
        `;
    } catch (err) {
        target.innerHTML = `<div class="error">${safe(err.message)}</div>`;
    }
}

async function saveCustomerBusinessInformation() {
    const d = customerBusinessProfileCache || {};
    const value = id => document.getElementById(id)?.value?.trim() || "";
    const payload = {
        company_name: value("cb-name"),
        business_type: value("cb-type") || null,
        description: value("cb-description") || null,
        country: d.country || null,
        currency: d.currency || null,
        timezone: d.timezone || null,
        primary_language: d.primary_language || null,
        additional_languages: d.additional_languages || [],
        phone: value("cb-phone") || null,
        email: value("cb-email") || null,
        website: value("cb-website") || null,
        working_hours: d.working_hours || {},
        locations: linesToList(value("cb-locations")),
        services: linesToList(value("cb-services")),
        service_areas: linesToList(value("cb-areas")),
        policies: linesToList(value("cb-policies")),
        business_rules: linesToList(value("cb-rules"))
    };
    const message = document.getElementById("cb-message");
    try {
        customerBusinessProfileCache = await api("/customer/agents/manage/business-information", {method: "PUT", body: JSON.stringify(payload)});
        if (message) message.textContent = "Saved. AI knowledge was updated automatically.";
    } catch (err) {
        if (message) message.textContent = err.message;
    }
}

function knowledgeCategoryOptions(selected) {
    const options = [
        ["custom","Custom"],["general","General"],["services_prices","Services & Prices"],["menu","Menu"],
        ["products","Products"],["faq","FAQ"],["policies","Policies"],["branches","Branches"],["hours","Hours"],
        ["delivery_payment","Delivery & Payment"],["booking_rules","Booking Rules"],["order_rules","Order Rules"]
    ];
    return options.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${safe(label)}</option>`).join("");
}

async function renderCustomerKnowledgeTab(target) {
    customerKnowledgeEditingId = null;
    try {
        const result = await api(`/customer/agents/manage/${customerManagedAgentId}/knowledge`);
        const items = result.items || [];
        target.innerHTML = `
            <p class="muted">Add information specific to this AI employee. Business Information is shared and protected.</p>
            <div id="ck-list">
                ${items.map(item => `
                    <div class="agent">
                        <div class="service-card-head">
                            <div><strong>${safe(item.title)}</strong><p>${safe(item.category)} · ${safe(item.characters)} characters</p></div>
                            <span class="status">${item.enabled ? "Active" : "Inactive"}</span>
                        </div>
                        <p>${safe(item.preview || "")}</p>
                        ${item.protected ? '<p class="muted">Managed from Business Information.</p>' : `
                            ${!["pdf","website"].includes(item.category) ? `<button onclick="editCustomerKnowledge(${Number(item.id)})">Edit</button>` : ""}
                            <button onclick="toggleCustomerKnowledge(${Number(item.id)})">${item.enabled ? "Disable" : "Enable"}</button>
                            <button onclick="deleteCustomerKnowledge(${Number(item.id)})">Delete</button>
                        `}
                    </div>
                `).join("") || '<p>No knowledge added yet.</p>'}
            </div>
            <hr style="margin:24px 0">
            <h3>Add Text Knowledge</h3>
            <div class="form-group"><label>Title</label><input id="ck-title"></div>
            <div class="form-group"><label>Category</label><select id="ck-category">${knowledgeCategoryOptions("custom")}</select></div>
            <div class="form-group"><label>Information</label><textarea id="ck-content" placeholder="Menu, prices, FAQs, policies, product information..."></textarea></div>
            <div id="ck-message" class="error"></div>
            <button onclick="saveCustomerKnowledge()">Add Knowledge</button>
            <hr style="margin:24px 0">
            <h3>Add Website</h3>
            <div class="form-group"><label>Page URL</label><input id="ck-url" placeholder="https://example.com/menu"></div>
            <div class="form-group"><label>Optional Title</label><input id="ck-url-title"></div>
            <button onclick="addCustomerKnowledgeUrl()">Import Website Page</button>
            <hr style="margin:24px 0">
            <h3>Add PDF</h3>
            <div class="form-group"><input id="ck-pdf" type="file" accept="application/pdf"></div>
            <button onclick="uploadCustomerKnowledgePdf()">Upload PDF</button>
        `;
    } catch (err) {
        target.innerHTML = `<div class="error">${safe(err.message)}</div>`;
    }
}

async function saveCustomerKnowledge() {
    const message = document.getElementById("ck-message");
    const payload = {
        title: document.getElementById("ck-title")?.value?.trim() || "",
        category: document.getElementById("ck-category")?.value || "custom",
        content: document.getElementById("ck-content")?.value?.trim() || "",
        enabled: true
    };
    try {
        const path = customerKnowledgeEditingId
            ? `/customer/agents/manage/${customerManagedAgentId}/knowledge/${customerKnowledgeEditingId}`
            : `/customer/agents/manage/${customerManagedAgentId}/knowledge`;
        await api(path, {method: customerKnowledgeEditingId ? "PUT" : "POST", body: JSON.stringify(payload)});
        await openCustomerManagerTab("knowledge");
    } catch (err) {
        if (message) message.textContent = err.message;
    }
}

async function editCustomerKnowledge(documentId) {
    try {
        const d = await api(`/customer/agents/manage/${customerManagedAgentId}/knowledge/${documentId}`);
        customerKnowledgeEditingId = Number(documentId);
        document.getElementById("ck-title").value = d.title || "";
        document.getElementById("ck-category").value = d.category || "custom";
        document.getElementById("ck-content").value = d.content || "";
        document.getElementById("ck-title").scrollIntoView({behavior: "smooth", block: "center"});
    } catch (err) { alert(err.message); }
}

async function toggleCustomerKnowledge(documentId) {
    try {
        await api(`/customer/agents/manage/${customerManagedAgentId}/knowledge/${documentId}/toggle`, {method: "PATCH", body: "{}"});
        await openCustomerManagerTab("knowledge");
    } catch (err) { alert(err.message); }
}

async function deleteCustomerKnowledge(documentId) {
    if (!confirm("Delete this knowledge item?")) return;
    try {
        await api(`/customer/agents/manage/${customerManagedAgentId}/knowledge/${documentId}`, {method: "DELETE"});
        await openCustomerManagerTab("knowledge");
    } catch (err) { alert(err.message); }
}

async function addCustomerKnowledgeUrl() {
    const url = document.getElementById("ck-url")?.value?.trim() || "";
    const title = document.getElementById("ck-url-title")?.value?.trim() || null;
    try {
        await api(`/customer/agents/manage/${customerManagedAgentId}/knowledge/url`, {method: "POST", body: JSON.stringify({url, title})});
        await openCustomerManagerTab("knowledge");
    } catch (err) { alert(err.message); }
}

async function uploadCustomerKnowledgePdf() {
    const file = document.getElementById("ck-pdf")?.files?.[0];
    if (!file) return alert("Choose a PDF first.");
    const form = new FormData();
    form.append("file", file);
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    try {
        const response = await fetch(`/customer/agents/manage/${customerManagedAgentId}/knowledge/pdf`, {method: "POST", headers, body: form});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "PDF upload failed");
        await openCustomerManagerTab("knowledge");
    } catch (err) { alert(err.message); }
}
