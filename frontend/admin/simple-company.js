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
        <div class="company-header">
            <div><h2>${simpleEscape(data.company.name)}</h2><p>Services provided by Xvond</p></div>
            <span class="status ${data.company.active ? "status-active" : "status-inactive"}">${data.company.active ? "Active" : "Inactive"}</span>
        </div>
        <div class="panel detail-section">
            <div class="section-header">
                <div><h3>AI Employees</h3><p>Add and manage the AI employees provided to this customer.</p></div>
                <button onclick="openAddAIEmployee(${companyId})">+ Add AI Employee</button>
            </div>
            <div class="agent-grid">
                ${whatsappEmployees.length ? whatsappEmployees.map(({agent, channel}) => `
                    <div class="agent-card">
                        <h3>WhatsApp AI</h3>
                        <div class="meta">${simpleEscape(agent.name)}</div>
                        <div class="meta">${channel.configured ? "WhatsApp connected" : "WhatsApp connection required"}</div>
                        <div class="meta">Questions · Sales · Bookings · Orders · Human handoff</div>
                        <div class="agent-actions">
                            <button class="table-button" onclick="openWhatsAppSetup(${agent.id}, ${channel.id})">${channel.configured ? "WhatsApp Settings" : "Connect WhatsApp"}</button>
                            <button class="table-button" onclick="openAgentTestChat(${companyId}, ${agent.id})">Test</button>
                        </div>
                    </div>
                `).join("") : `<p>No AI employee has been added to this company yet.</p>`}
            </div>
        </div>`;
}

function openAddAIEmployee(companyId) {
    simpleCompanyId = Number(companyId);
    openModal("Add AI Employee", `
        <div class="form-group"><label>Service</label><select id="simple-employee-channel"><option value="whatsapp">WhatsApp AI</option></select></div>
        <div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="WhatsApp AI Employee"></div>
        <div class="form-group"><label>Business Name</label><input id="simple-business-name" placeholder="Customer business name"></div>
        <div class="form-group"><label>Business Type</label><select id="simple-business-type"><option value="">Select business type</option><option>Salon / Beauty</option><option>Restaurant / Cafe</option><option>Retail Store</option><option>E-commerce</option><option>Clinic</option><option>Real Estate</option><option>Hotel / Hospitality</option><option>Professional Services</option><option>Education</option><option>Other</option></select></div>
        <div class="form-group"><label>Business Description</label><textarea id="simple-business-description" placeholder="What does the business offer? Add the important context the employee should understand."></textarea></div>
        <div class="form-group"><label>Working Hours</label><input id="simple-working-hours" placeholder="Example: Sun-Thu 9:00 AM - 9:00 PM"></div>
        <div class="form-group"><label>Reply Language</label><select id="simple-language"><option value="auto">Automatic - match customer language</option><option value="ar">Arabic</option><option value="en">English</option><option value="ar_en">Arabic & English</option></select></div>
        <div class="form-group"><label>Business Information</label><textarea id="simple-business-info" placeholder="Services, products, prices, policies, branches, delivery information or other important details."></textarea></div>
        <div class="form-group"><label>Website (optional)</label><input id="simple-website" placeholder="https://"></div>
        <div class="form-group"><label>Human Handoff</label><input id="simple-handoff" placeholder="Phone, WhatsApp number, team or instructions for human transfer"></div>
        <div class="form-group"><label>Booking System (optional)</label><input id="simple-booking-system" placeholder="System name or API/integration details. Leave empty if none."></div>
        <div class="form-group"><label>Orders / Store System (optional)</label><input id="simple-order-system" placeholder="POS, store, order system or API. Leave empty if none."></div>
        <div class="form-group"><label>Other Connected System (optional)</label><input id="simple-other-system" placeholder="CRM, ERP or another system"></div>
        <div class="form-group"><label>Monthly Usage Limit</label><input id="simple-monthly-limit" type="number" min="1" placeholder="Example: 5000"></div>
        <div class="form-group"><label>Special Instructions (optional)</label><textarea id="simple-employee-instructions" placeholder="Only customer-specific rules or instructions."></textarea></div>
        <p class="meta">WhatsApp AI is full-service by default: questions, sales, bookings, orders and human handoff. Booking and order actions run only when the required system is available.</p>
        <button class="modal-submit" onclick="createSimpleAIEmployee()">Create WhatsApp AI</button>`);
}

async function createSimpleAIEmployee() {
    try {
        const businessName = document.getElementById("simple-business-name").value.trim();
        const businessType = document.getElementById("simple-business-type").value;
        const workingHours = document.getElementById("simple-working-hours").value.trim();
        const language = document.getElementById("simple-language").value;
        const businessInfo = document.getElementById("simple-business-info").value.trim();
        const website = document.getElementById("simple-website").value.trim();
        const handoff = document.getElementById("simple-handoff").value.trim();
        const bookingSystem = document.getElementById("simple-booking-system").value.trim();
        const orderSystem = document.getElementById("simple-order-system").value.trim();
        const otherSystem = document.getElementById("simple-other-system").value.trim();
        const monthlyLimit = document.getElementById("simple-monthly-limit").value;
        const description = document.getElementById("simple-business-description").value.trim();
        const instructions = document.getElementById("simple-employee-instructions").value.trim();
        if (!businessName) throw new Error("Business name is required");
        if (!businessType) throw new Error("Business type is required");
        if (!description && !businessInfo && !website) throw new Error("Add business information, a description, or a website");

        const setup = [
            `Business name: ${businessName}`,
            `Business type: ${businessType}`,
            workingHours ? `Working hours: ${workingHours}` : "",
            `Reply language: ${language}`,
            businessInfo ? `Business information: ${businessInfo}` : "",
            website ? `Website: ${website}` : "",
            handoff ? `Human handoff: ${handoff}` : "",
            bookingSystem ? `Booking system: ${bookingSystem}` : "No booking system connected.",
            orderSystem ? `Orders/store system: ${orderSystem}` : "No order system connected.",
            otherSystem ? `Other system: ${otherSystem}` : "",
            monthlyLimit ? `Monthly usage limit: ${monthlyLimit}` : ""
        ].filter(Boolean).join("\n");

        await api(`/admin/ai-employees/companies/${simpleCompanyId}`, {
            method: "POST",
            body: JSON.stringify({
                channel: "whatsapp",
                name: document.getElementById("simple-employee-name").value.trim() || "WhatsApp AI Employee",
                business_description: [description, setup].filter(Boolean).join("\n\n"),
                instructions: instructions || null
            })
        });
        closeModal();
        await openSimpleCompany(simpleCompanyId);
    } catch (error) { alert(error.message); }
}

function openWhatsAppSetup(agentId, channelId) {
    openModal("Connect WhatsApp", `
        <p class="meta">Connect the customer's Meta WhatsApp Business account. The employee will stay inactive on WhatsApp until these details are valid.</p>
        <div class="form-group"><label>Phone Number ID</label><input id="simple-wa-phone-id"></div>
        <div class="form-group"><label>Access Token</label><input id="simple-wa-access-token" type="password"></div>
        <div class="form-group"><label>Verify Token</label><input id="simple-wa-verify-token" type="password"></div>
        <div class="form-group"><label>App Secret</label><input id="simple-wa-app-secret" type="password"></div>
        <div class="form-group"><label>Graph API Version</label><input id="simple-wa-version" value="v23.0"></div>
        <button class="modal-submit" onclick="saveSimpleWhatsApp(${channelId})">Connect & Activate</button>`);
}

async function saveSimpleWhatsApp(channelId) {
    try {
        await api(`/admin/channels/${channelId}/whatsapp-config`, {method:"PUT", body:JSON.stringify({phone_number_id:document.getElementById("simple-wa-phone-id").value,access_token:document.getElementById("simple-wa-access-token").value,verify_token:document.getElementById("simple-wa-verify-token").value,app_secret:document.getElementById("simple-wa-app-secret").value,graph_api_version:document.getElementById("simple-wa-version").value})});
        closeModal(); await openSimpleCompany(simpleCompanyId);
    } catch (error) { alert(error.message); }
}

const originalOpenCompany = window.openCompany;
window.openCompany = openSimpleCompany;
