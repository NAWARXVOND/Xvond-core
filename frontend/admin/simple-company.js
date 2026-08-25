let simpleCompanyId = null;

function simpleEscape(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

async function openSimpleCompany(companyId) {
    simpleCompanyId = Number(companyId);
    const data = await api(`/admin/company-view/${companyId}`);
    const channelsResult = await api(`/admin/channels/companies/${companyId}`);
    const channels = channelsResult.channels || [];
    const whatsappEmployees = (data.agents || []).map(agent => {
        const channel = channels.find(item => Number(item.agent_id) === Number(agent.id) && item.channel_type === "whatsapp");
        return channel ? {agent, channel} : null;
    }).filter(Boolean);
    document.querySelectorAll(".page").forEach(item => item.classList.add("hidden"));
    document.getElementById("page-company-detail").classList.remove("hidden");
    document.getElementById("page-title").textContent = data.company.name;
    document.getElementById("company-detail").innerHTML = `
        <div class="company-header"><div><h2>${simpleEscape(data.company.name)}</h2><p>Services provided by Xvond</p></div><span class="status ${data.company.active ? "status-active" : "status-inactive"}">${data.company.active ? "Active" : "Inactive"}</span></div>
        <div class="panel detail-section"><div class="section-header"><div><h3>AI Employees</h3><p>Add and manage the AI employees provided to this customer.</p></div><button onclick="openAddAIEmployee(${companyId})">+ Add AI Employee</button></div>
        <div class="agent-grid">${whatsappEmployees.length ? whatsappEmployees.map(({agent, channel}) => `<div class="agent-card"><h3>WhatsApp AI</h3><div class="meta">${simpleEscape(agent.name)}</div><div class="meta">${channel.configured ? "WhatsApp connected" : "WhatsApp connection required"}</div><div class="meta">Questions · Sales · Bookings · Orders · Human handoff</div><div class="agent-actions"><button class="table-button" onclick="openWhatsAppSetup(${agent.id}, ${channel.id})">${channel.configured ? "WhatsApp Settings" : "Connect WhatsApp"}</button><button class="table-button" onclick="openAgentTestChat(${companyId}, ${agent.id})">Test</button></div></div>`).join("") : `<p>No AI employee has been added to this company yet.</p>`}</div></div>`;
}

function openAddAIEmployee(companyId) {
    simpleCompanyId = Number(companyId);
    openModal("Add AI Employee", `
        <div class="form-group"><label>Service</label><select id="simple-employee-channel"><option value="whatsapp">WhatsApp AI</option></select></div>
        <div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="WhatsApp AI Employee"></div>
        <div class="form-group"><label>Business Name</label><input id="simple-business-name" placeholder="Customer business name"></div>
        <div class="form-group"><label>Business Type</label><select id="simple-business-type"><option value="">Select business type</option><option>Salon / Beauty</option><option>Restaurant / Cafe</option><option>Retail Store</option><option>E-commerce</option><option>Clinic</option><option>Real Estate</option><option>Hotel / Hospitality</option><option>Professional Services</option><option>Education</option><option>Other</option></select></div>
        <div class="form-group"><label>Business Description</label><textarea id="simple-business-description" placeholder="What does the business offer?"></textarea></div>
        <div class="form-group"><label>Working Hours</label><input id="simple-working-hours" placeholder="Example: Sun-Thu 9:00 AM - 9:00 PM"></div>
        <div class="form-group"><label>Reply Language</label><select id="simple-language"><option value="auto">Automatic - match customer language</option><option value="ar">Arabic</option><option value="en">English</option><option value="ar_en">Arabic & English</option></select></div>
        <div class="form-group"><label>Business Information</label><textarea id="simple-business-info" placeholder="Services, products, prices, policies, branches and delivery information."></textarea></div>
        <div class="form-group"><label>Website (optional)</label><input id="simple-website" placeholder="https://"></div>
        <div class="form-group"><label>Human Handoff</label><input id="simple-handoff" placeholder="Phone, WhatsApp number, team or transfer instructions"></div>
        <div class="form-group"><label>Booking System (optional)</label><input id="simple-booking-system" placeholder="System/API reference. Leave empty if none."></div>
        <div class="form-group"><label>Orders / Store System (optional)</label><input id="simple-order-system" placeholder="POS/store/API reference. Leave empty if none."></div>
        <div class="form-group"><label>Other Connected System (optional)</label><input id="simple-other-system" placeholder="CRM, ERP or another system"></div>
        <div class="form-group"><label>Monthly Usage Limit</label><input id="simple-monthly-limit" type="number" min="1" placeholder="Example: 5000"></div>
        <div class="form-group"><label>Special Instructions (optional)</label><textarea id="simple-employee-instructions" placeholder="Only customer-specific rules or instructions."></textarea></div>
        <p class="meta">WhatsApp AI is full-service by default: questions, sales, bookings, orders and human handoff.</p>
        <button class="modal-submit" onclick="createSimpleAIEmployee()">Create WhatsApp AI</button>`);
}

async function createSimpleAIEmployee() {
    try {
        const value = id => document.getElementById(id).value.trim();
        const businessName = value("simple-business-name");
        const businessType = value("simple-business-type");
        const description = value("simple-business-description");
        const businessInfo = value("simple-business-info");
        const website = value("simple-website");
        if (!businessName) throw new Error("Business name is required");
        if (!businessType) throw new Error("Business type is required");
        if (!description && !businessInfo && !website) throw new Error("Add business information, a description, or a website");
        const rawLimit = value("simple-monthly-limit");
        await api(`/admin/ai-employees/companies/${simpleCompanyId}`, {
            method: "POST",
            body: JSON.stringify({
                channel: "whatsapp",
                name: value("simple-employee-name") || "WhatsApp AI Employee",
                business_name: businessName,
                business_type: businessType,
                business_description: description || null,
                working_hours: value("simple-working-hours") || null,
                reply_language: document.getElementById("simple-language").value,
                business_information: businessInfo || null,
                website: website || null,
                human_handoff: value("simple-handoff") || null,
                booking_system: value("simple-booking-system") || null,
                order_system: value("simple-order-system") || null,
                other_system: value("simple-other-system") || null,
                monthly_usage_limit: rawLimit ? Number(rawLimit) : null,
                instructions: value("simple-employee-instructions") || null
            })
        });
        closeModal();
        await openSimpleCompany(simpleCompanyId);
    } catch (error) { alert(error.message); }
}

function openWhatsAppSetup(agentId, channelId) {
    openModal("Connect WhatsApp", `<p class="meta">Connect the customer's Meta WhatsApp Business account.</p><div class="form-group"><label>Phone Number ID</label><input id="simple-wa-phone-id"></div><div class="form-group"><label>Access Token</label><input id="simple-wa-access-token" type="password"></div><div class="form-group"><label>Verify Token</label><input id="simple-wa-verify-token" type="password"></div><div class="form-group"><label>App Secret</label><input id="simple-wa-app-secret" type="password"></div><div class="form-group"><label>Graph API Version</label><input id="simple-wa-version" value="v23.0"></div><button class="modal-submit" onclick="saveSimpleWhatsApp(${channelId})">Connect & Activate</button>`);
}

async function saveSimpleWhatsApp(channelId) {
    try {
        await api(`/admin/channels/${channelId}/whatsapp-config`, {method:"PUT", body:JSON.stringify({phone_number_id:document.getElementById("simple-wa-phone-id").value,access_token:document.getElementById("simple-wa-access-token").value,verify_token:document.getElementById("simple-wa-verify-token").value,app_secret:document.getElementById("simple-wa-app-secret").value,graph_api_version:document.getElementById("simple-wa-version").value})});
        closeModal(); await openSimpleCompany(simpleCompanyId);
    } catch (error) { alert(error.message); }
}

const originalOpenCompany = window.openCompany;
window.openCompany = openSimpleCompany;
