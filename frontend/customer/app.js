let token = localStorage.getItem("xvond_customer_token");
let currentUser = null;
let agents = [];
let chatConversationId = null;


async function api(path, options = {}) {

    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(path, {
        ...options,
        headers
    });

    if (response.status === 401) {
        logout();
        throw new Error("Unauthorized");
    }

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.detail || "Request failed"
        );
    }

    return data;
}


async function login() {

    const email =
        document.getElementById("login-email").value.trim();

    const password =
        document.getElementById("login-password").value;

    const error =
        document.getElementById("login-error");

    error.textContent = "";

    try {

        const response = await fetch(
            "/auth/login",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email,
                    password
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Login failed"
            );
        }

        token =
            typeof data === "string"
                ? data
                : (
                    data.access_token ||
                    data.token
                );

        if (!token) {
            throw new Error(
                "Login token not returned"
            );
        }

        localStorage.setItem(
            "xvond_customer_token",
            token
        );

        await startPortal();

    } catch (err) {
        error.textContent = err.message;
    }
}


function logout() {

    localStorage.removeItem(
        "xvond_customer_token"
    );

    token = null;
    currentUser = null;
    agents = [];
    chatConversationId = null;

    document
        .getElementById("portal")
        .classList.add("hidden");

    document
        .getElementById("login-screen")
        .classList.remove("hidden");
}


async function startPortal() {

    try {

        currentUser =
            await api("/users/me");

        if (!currentUser.company_id) {
            throw new Error(
                "This account is not attached to a customer company."
            );
        }

        document
            .getElementById("login-screen")
            .classList.add("hidden");

        document
            .getElementById("portal")
            .classList.remove("hidden");

        document.getElementById(
            "user-email"
        ).textContent = currentUser.email;

        document.getElementById(
            "account-info"
        ).innerHTML = `
            <p><strong>Name:</strong>
            ${safe(currentUser.full_name || "-")}</p>

            <p><strong>Email:</strong>
            ${safe(currentUser.email)}</p>

            <p><strong>Role:</strong>
            ${safe(currentUser.role)}</p>

            <p><strong>Company ID:</strong>
            ${currentUser.company_id}</p>
        `;

        await loadAgents();
        await loadUsage();

    } catch (err) {
        logout();
        document.getElementById(
            "login-error"
        ).textContent = err.message;
    }
}


async function loadAgents() {

    const result =
        await api("/ai-agents/");

    agents = result.agents || [];

    document.getElementById(
        "dash-agents"
    ).textContent = agents.length;

    document.getElementById(
        "dash-active"
    ).textContent =
        agents.filter(x => x.enabled).length;

    const list =
        document.getElementById("agents-list");

    list.innerHTML =
        agents.length
            ? agents.map(agent => `
                <div class="agent">

                    <h3>${safe(agent.name)}</h3>

                    <p>
                        ${safe(agent.description || "")}
                    </p>

                    <p>
                        <span class="status">
                            ${agent.enabled ? "Active" : "Inactive"}
                        </span>
                    </p>

                </div>
            `).join("")
            : "<p>No agents available.</p>";

    fillAgentSelects();
}


function fillAgentSelects() {

    const html =
        agents.map(agent => `
            <option value="${agent.id}">
                ${safe(agent.name)}
            </option>
        `).join("");

    document.getElementById(
        "chat-agent"
    ).innerHTML = html;

    document.getElementById(
        "conversation-agent"
    ).innerHTML = html;
}


async function loadUsage() {

    const usage =
        await api("/usage/");

    document.getElementById(
        "usage-requests"
    ).textContent = usage.requests || 0;

    document.getElementById(
        "usage-input"
    ).textContent = usage.input_tokens || 0;

    document.getElementById(
        "usage-output"
    ).textContent = usage.output_tokens || 0;

    document.getElementById(
        "usage-total"
    ).textContent = usage.total_tokens || 0;

    document.getElementById(
        "dash-requests"
    ).textContent = usage.requests || 0;

    document.getElementById(
        "dash-tokens"
    ).textContent = usage.total_tokens || 0;
}


async function sendChat() {

    const agentId =
        document.getElementById("chat-agent").value;

    const input =
        document.getElementById("chat-message");

    const message =
        input.value.trim();

    if (!agentId || !message) return;

    addChat("You", message);

    input.value = "";

    try {

        const result =
            await api(
                `/ai-agents/${agentId}/chat`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        message,
                        conversation_id:
                            chatConversationId
                    })
                }
            );

        chatConversationId =
            result.conversation_id;

        addChat(
            "Agent",
            result.response.content
        );

        await loadUsage();

    } catch (err) {
        addChat("Error", err.message);
    }
}


function addChat(role, message) {

    const box =
        document.getElementById("chat-box");

    box.innerHTML += `
        <div class="chat-row">
            <strong>${safe(role)}</strong>
            <div>${safe(message)}</div>
        </div>
    `;

    box.scrollTop = box.scrollHeight;
}


async function loadConversations() {

    const agentId =
        document.getElementById(
            "conversation-agent"
        ).value;

    if (!agentId) return;

    const result =
        await api(
            `/ai-agents/${agentId}/conversations`
        );

    const items =
        result.conversations || [];

    document.getElementById(
        "conversation-list"
    ).innerHTML =
        items.length
            ? items.map(item => `
                <div
                    class="conversation-item"
                    onclick="loadConversation(
                        ${agentId},
                        ${item.id}
                    )">

                    <strong>
                        ${safe(item.title || `Conversation ${item.id}`)}
                    </strong>

                </div>
            `).join("")
            : "<p>No conversations yet.</p>";
}


async function loadConversation(
    agentId,
    conversationId
) {

    const result =
        await api(
            `/ai-agents/${agentId}/conversations/${conversationId}`
        );

    const messages =
        result.messages || [];

    document.getElementById(
        "conversation-messages"
    ).innerHTML =
        messages.map(message => `
            <div class="chat-row">
                <strong>
                    ${safe(message.role)}
                </strong>
                <div>
                    ${safe(message.content)}
                </div>
            </div>
        `).join("");
}


async function openPage(name, button) {

    document.querySelectorAll(".page")
        .forEach(
            page => page.classList.add("hidden")
        );

    document.querySelectorAll(".nav-item")
        .forEach(
            item => item.classList.remove("active")
        );

    document.getElementById(
        `page-${name}`
    ).classList.remove("hidden");

    if (button) {
        button.classList.add("active");
    }

    document.getElementById(
        "page-title"
    ).textContent =
        button
            ? button.textContent.trim()
            : "Dashboard";

    if (name === "usage") {
        await loadUsage();
    }

    if (name === "business") {
        await loadCustomerBusiness();
    }

    if (name === "conversations") {
        await loadConversations();
    }
}


function safe(value) {

    const element =
        document.createElement("div");

    element.textContent =
        value ?? "";

    return element.innerHTML;
}


if (token) {
    startPortal();
}

async function loadCustomerBusiness() {

    try {

        const [leads, bookings, orders, handoffs] =
            await Promise.all([
                api("/customer/business/leads"),
                api("/customer/business/bookings"),
                api("/customer/business/orders"),
                api("/customer/business/handoffs")
            ]);

        document.getElementById(
            "customer-leads-count"
        ).textContent = leads.length;

        document.getElementById(
            "customer-bookings-count"
        ).textContent = bookings.length;

        document.getElementById(
            "customer-orders-count"
        ).textContent = orders.length;

        document.getElementById(
            "customer-handoffs-count"
        ).textContent = handoffs.length;


        document.getElementById(
            "customer-business-content"
        ).innerHTML = `

            ${customerBusinessSection(
                "Leads",
                leads,
                item => `
                    <strong>${safe(item.name || "Lead #" + item.id)}</strong>
                    <p>Status: ${safe(item.status)}</p>
                    <p>Phone: ${safe(item.phone || "-")}</p>
                    <p>Interest: ${safe(item.interest || "-")}</p>
                `
            )}

            ${customerBusinessSection(
                "Bookings",
                bookings,
                item => `
                    <strong>${safe(item.customer_name || "Booking #" + item.id)}</strong>
                    <p>Service: ${safe(item.service || "-")}</p>
                    <p>Date: ${safe(item.booking_date || "-")}</p>
                    <p>Time: ${safe(item.booking_time || "-")}</p>
                    <p>Status: ${safe(item.status)}</p>
                `
            )}

            ${customerBusinessSection(
                "Orders",
                orders,
                item => `
                    <strong>${safe(item.customer_name || "Order #" + item.id)}</strong>
                    <p>Status: ${safe(item.status)}</p>
                    <p>Phone: ${safe(item.phone || "-")}</p>
                    <p>Delivery: ${safe(item.delivery_address || "-")}</p>
                `
            )}

            ${customerBusinessSection(
                "Human Handoffs",
                handoffs,
                item => `
                    <strong>Handoff #${item.id}</strong>
                    <p>Reason: ${safe(item.reason || "-")}</p>
                    <p>Department: ${safe(item.department || "-")}</p>
                    <p>Priority: ${safe(item.priority || "-")}</p>
                    <p>Status: ${safe(item.status)}</p>
                `
            )}
        `;

    } catch (err) {

        document.getElementById(
            "customer-business-content"
        ).innerHTML =
            `<div class="panel">
                ${safe(err.message)}
             </div>`;
    }
}


function customerBusinessSection(
    title,
    items,
    renderer
) {

    return `
        <div class="panel" style="margin-bottom:20px">

            <h2>${title}</h2>

            ${
                items.length
                    ? items.map(item => `
                        <div class="agent">
                            ${renderer(item)}
                        </div>
                    `).join("")
                    : `<p>No ${title.toLowerCase()} yet.</p>`
            }

        </div>
    `;
}



// ============================================================
// CUSTOMER PASSWORD SECURITY
// ============================================================

function hidePasswordScreens() {

    const ids = [
        "normal-login-form",
        "forgot-password-form",
        "reset-password-form"
    ];

    for (const id of ids) {

        const element =
            document.getElementById(id);

        if (element) {
            element.classList.add(
                "hidden"
            );
        }
    }
}


function showNormalLogin() {

    hidePasswordScreens();

    const normal =
        document.getElementById(
            "normal-login-form"
        );

    if (normal) {
        normal.classList.remove(
            "hidden"
        );
    }
}


function showForgotPassword() {

    hidePasswordScreens();

    const form =
        document.getElementById(
            "forgot-password-form"
        );

    if (form) {
        form.classList.remove(
            "hidden"
        );
    }

    const loginEmail =
        document.getElementById(
            "login-email"
        );

    const forgotEmail =
        document.getElementById(
            "forgot-email"
        );

    if (
        loginEmail
        && forgotEmail
        && loginEmail.value.trim()
    ) {
        forgotEmail.value =
            loginEmail.value.trim();
    }
}


function showResetPassword(
    email
) {

    hidePasswordScreens();

    document
        .getElementById(
            "reset-password-form"
        )
        .classList.remove(
            "hidden"
        );

    document.getElementById(
        "reset-email"
    ).value = email;
}


async function publicAuthRequest(
    path,
    body
) {

    const response =
        await fetch(
            path,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(
                        body
                    )
            }
        );

    let data = {};

    try {
        data = await response.json();
    } catch (_) {}

    if (!response.ok) {

        throw new Error(
            data.detail
            || "Request failed"
        );
    }

    return data;
}


async function requestPasswordCode() {

    const email =
        document.getElementById(
            "forgot-email"
        ).value.trim();

    const message =
        document.getElementById(
            "forgot-message"
        );

    message.textContent = "";

    if (!email) {

        message.textContent =
            "Email is required.";

        return;
    }


    try {

        await publicAuthRequest(
            "/auth/customer/forgot-password",
            {
                email:
                    email
            }
        );


        showResetPassword(
            email
        );


        document.getElementById(
            "reset-message"
        ).textContent =
            "If this email belongs to a customer account, a verification code was sent.";

    } catch (error) {

        message.textContent =
            error.message;
    }
}


async function resetCustomerPassword() {

    const email =
        document.getElementById(
            "reset-email"
        ).value.trim();

    const code =
        document.getElementById(
            "reset-code"
        ).value.trim();

    const password =
        document.getElementById(
            "reset-new-password"
        ).value;

    const confirmPassword =
        document.getElementById(
            "reset-confirm-password"
        ).value;

    const message =
        document.getElementById(
            "reset-message"
        );

    message.textContent = "";


    if (
        !email
        || !code
        || !password
    ) {

        message.textContent =
            "Complete all fields.";

        return;
    }


    if (password !== confirmPassword) {

        message.textContent =
            "Passwords do not match.";

        return;
    }


    try {

        await publicAuthRequest(
            "/auth/customer/reset-password",
            {
                email:
                    email,

                code:
                    code,

                new_password:
                    password
            }
        );


        showNormalLogin();


        document.getElementById(
            "login-email"
        ).value = email;


        document.getElementById(
            "login-password"
        ).value = "";


        document.getElementById(
            "login-error"
        ).textContent =
            "Password changed. You can log in now.";

    } catch (error) {

        message.textContent =
            error.message;
    }
}


async function changeCustomerPassword() {

    const currentPassword =
        document.getElementById(
            "current-password"
        ).value;

    const newPassword =
        document.getElementById(
            "new-password"
        ).value;

    const confirmPassword =
        document.getElementById(
            "confirm-new-password"
        ).value;

    const message =
        document.getElementById(
            "change-password-message"
        );

    message.textContent = "";


    if (
        !currentPassword
        || !newPassword
        || !confirmPassword
    ) {

        message.textContent =
            "Complete all password fields.";

        return;
    }


    if (
        newPassword
        !== confirmPassword
    ) {

        message.textContent =
            "New passwords do not match.";

        return;
    }


    try {

        await api(
            "/auth/customer/change-password",
            {
                method: "POST",

                body:
                    JSON.stringify({
                        current_password:
                            currentPassword,

                        new_password:
                            newPassword
                    })
            }
        );


        document.getElementById(
            "current-password"
        ).value = "";

        document.getElementById(
            "new-password"
        ).value = "";

        document.getElementById(
            "confirm-new-password"
        ).value = "";


        message.textContent =
            "Password changed successfully.";

    } catch (error) {

        message.textContent =
            error.message;
    }
}

