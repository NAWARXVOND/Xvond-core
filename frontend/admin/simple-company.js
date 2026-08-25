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
                <div><h3>AI Employees</h3><p>Add the service the customer purchased. Xvond handles the technical setup behind the scenes.</p></div>
                <button onclick="openAddAIEmployee(${companyId})">+ Add AI Employee</button>
            </div>
            <div class="agent-grid">
                ${whatsappEmployees.length ? whatsappEmployees.map(({agent, channel}) => `
                    <div class="agent-card">
                        <h3>WhatsApp AI</h3>
                        <div class="meta">${simpleEscape(agent.name)}</div>
                        <div class="meta">${channel.configured ? "WhatsApp connected" : "WhatsApp setup required"}</div>
                        <div class="meta">Full customer service: questions, sales, bookings and orders when the required business system is available.</div>
                        <div class="agent-actions">
                            <button class="table-button" onclick="openWhatsAppSetup(${agent.id}, ${channel.id})">${channel.configured ? "WhatsApp Settings" : "Connect WhatsApp"}</button>
                            <button class="table-button" onclick="openAgentTestChat(${companyId}, ${agent.id})">Test</button>
                        </div>
                    </div>
                `).join("") : `<p>No AI employee has been added to this company yet.</p>`}
            </div>
        </div>
    `;
}

function openAddAIEmployee(companyId) {
    simpleCompanyId = Number(companyId);
    openModal("Add AI Employee", `
        <div class="form-group"><label>Service</label><select id="simple-employee-channel"><option value="whatsapp">WhatsApp AI</option></select></div>
        <div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="WhatsApp AI Employee"></div>
        <div class="form-group"><label>About the Business</label><textarea id="simple-business-description" placeholder="What does this company do? Add any important context."></textarea></div>
        <div class="form-group"><label>Special Instructions (optional)</label><textarea id="simple-employee-instructions" placeholder="Only add instructions specific to this customer."></textarea></div>
        <p class="meta">The employee is full-service by default. It can answer questions, sell, book and handle orders. Booking/order actions are used only when the required system is connected.</p>
        <button class="modal-submit" onclick="createSimpleAIEmployee()">Create WhatsApp AI</button>
    `);
}

async function createSimpleAIEmployee() {
    try {
        await api(`/admin/ai-employees/companies/${simpleCompanyId}`, {
            method: "POST",
            body: JSON.stringify({
                channel: document.getElementById("simple-employee-channel").value,
                name: document.getElementById("simple-employee-name").value,
                business_description: document.getElementById("simple-business-description").value,
                instructions: document.getElementById("simple-employee-instructions").value
            })
        });
        closeModal();
        await openSimpleCompany(simpleCompanyId);
    } catch (error) {
        alert(error.message);
    }
}

function openWhatsAppSetup(agentId, channelId) {
    openModal("Connect WhatsApp", `
        <p class="meta">Enter the Meta WhatsApp Business connection details for this customer.</p>
        <div class="form-group"><label>Phone Number ID</label><input id="simple-wa-phone-id"></div>
        <div class="form-group"><label>Access Token</label><input id="simple-wa-access-token" type="password"></div>
        <div class="form-group"><label>Verify Token</label><input id="simple-wa-verify-token" type="password"></div>
        <div class="form-group"><label>App Secret</label><input id="simple-wa-app-secret" type="password"></div>
        <div class="form-group"><label>Graph API Version</label><input id="simple-wa-version" value="v23.0"></div>
        <button class="modal-submit" onclick="saveSimpleWhatsApp(${channelId})">Connect & Activate</button>
    `);
}

async function saveSimpleWhatsApp(channelId) {
    try {
        await api(`/admin/channels/${channelId}/whatsapp-config`, {
            method: "PUT",
            body: JSON.stringify({
                phone_number_id: document.getElementById("simple-wa-phone-id").value,
                access_token: document.getElementById("simple-wa-access-token").value,
                verify_token: document.getElementById("simple-wa-verify-token").value,
                app_secret: document.getElementById("simple-wa-app-secret").value,
                graph_api_version: document.getElementById("simple-wa-version").value
            })
        });
        closeModal();
        await openSimpleCompany(simpleCompanyId);
    } catch (error) {
        alert(error.message);
    }
}

const originalOpenCompany = window.openCompany;
window.openCompany = openSimpleCompany;
