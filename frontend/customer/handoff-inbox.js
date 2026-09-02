function inboxModeBadge(mode) {
    const human = String(mode || "ai").toLowerCase() === "human";
    return `<span class="inbox-badge ${human ? "handoff-human" : "handoff-ai"}">${human ? "Human" : "AI"}</span>`;
}

async function customerTakeOverConversation(conversationId) {
    try {
        await api(`/customer/inbox/${conversationId}/take-over`, {method: "POST", body: "{}"});
        await loadInboxConversation(conversationId);
        await loadConversations();
    } catch (error) {
        alert(error.message);
    }
}

async function customerReturnConversationToAI(conversationId) {
    if (!confirm("Return this conversation to the AI employee?")) return;
    try {
        await api(`/customer/inbox/${conversationId}/return-ai`, {method: "POST", body: "{}"});
        await loadInboxConversation(conversationId);
        await loadConversations();
    } catch (error) {
        alert(error.message);
    }
}

async function customerSendHumanReply(conversationId) {
    const input = document.getElementById("human-reply-message");
    const button = document.getElementById("human-reply-send");
    const message = input?.value?.trim() || "";
    if (!message) return;
    if (button) {
        button.disabled = true;
        button.textContent = "Sending...";
    }
    try {
        await api(`/customer/inbox/${conversationId}/message`, {
            method: "POST",
            body: JSON.stringify({message})
        });
        await loadInboxConversation(conversationId);
        await loadConversations();
    } catch (error) {
        alert(error.message);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Send Reply";
        }
    }
}

loadConversations = async function() {
    ensureInboxMarkup();
    const list = document.getElementById("conversation-list");
    if (!list) return;

    const agentId = document.getElementById("conversation-agent")?.value || "";
    const channelType = document.getElementById("conversation-channel")?.value || "";
    const search = document.getElementById("conversation-search")?.value.trim() || "";
    const params = new URLSearchParams();
    if (agentId) params.set("agent_id", agentId);
    if (channelType) params.set("channel_type", channelType);
    if (search) params.set("search", search);

    list.innerHTML = '<div class="empty-state">Loading conversations...</div>';
    try {
        const result = await api(`/customer/inbox${params.toString() ? `?${params}` : ""}`);
        populateInboxFilters(result.filters || {});
        const items = result.conversations || [];
        list.innerHTML = items.length ? items.map(item => {
            const preview = item.last_message?.content || item.title || "No messages";
            const contact = item.external_contact_id
                ? `<div class="inbox-contact">${safe(item.external_contact_id)}</div>`
                : "";
            return `
                <button class="inbox-item" onclick="loadInboxConversation(${item.id}, this)">
                    <div class="inbox-item-top">
                        <strong>${safe(item.title || `Conversation ${item.id}`)}</strong>
                        <span>${formatDate(item.last_message?.created_at || item.created_at)}</span>
                    </div>
                    <div class="inbox-badges">
                        ${inboxBadge(item.agent_name, "agent-badge")}
                        ${inboxBadge(item.channel_label, `channel-${item.channel_type || "unknown"}`)}
                        ${inboxModeBadge(item.mode)}
                    </div>
                    ${contact}
                    <p>${safe(preview)}</p>
                </button>
            `;
        }).join("") : '<div class="empty-state">No conversations match these filters.</div>';
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${safe(error.message)}</div>`;
    }
};

loadInboxConversation = async function(conversationId, button = null) {
    document.querySelectorAll(".inbox-item").forEach(item => item.classList.remove("selected"));
    if (button) button.classList.add("selected");
    const target = document.getElementById("conversation-messages");
    if (!target) return;
    target.innerHTML = '<div class="empty-state">Loading messages...</div>';
    try {
        const result = await api(`/customer/inbox/${conversationId}`);
        const conversation = result.conversation || {};
        const messages = result.messages || [];
        const human = String(conversation.mode || "ai").toLowerCase() === "human";
        const controls = human ? `
            <div class="handoff-controls human-active">
                <div>
                    <strong>Human employee is in control</strong>
                    <p class="muted">The AI employee stays paused until you return this conversation to AI.</p>
                </div>
                <button class="secondary-button" onclick="customerReturnConversationToAI(${conversationId})">Return to AI</button>
            </div>
            <div class="human-reply-box">
                <textarea id="human-reply-message" placeholder="Reply to the customer..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();customerSendHumanReply(${conversationId})}"></textarea>
                <button id="human-reply-send" onclick="customerSendHumanReply(${conversationId})">Send Reply</button>
            </div>
        ` : `
            <div class="handoff-controls ai-active">
                <div>
                    <strong>AI employee is handling this conversation</strong>
                    <p class="muted">Take over only when a human needs to reply directly.</p>
                </div>
                <button class="secondary-button" onclick="customerTakeOverConversation(${conversationId})">Take Over</button>
            </div>
        `;

        target.innerHTML = `
            <div class="inbox-thread-head">
                <div>
                    <h3>${safe(conversation.title || `Conversation ${conversationId}`)}</h3>
                    <div class="inbox-badges">
                        ${inboxBadge(conversation.agent_name, "agent-badge")}
                        ${inboxBadge(conversation.channel_label, `channel-${conversation.channel_type || "unknown"}`)}
                        ${inboxModeBadge(conversation.mode)}
                    </div>
                </div>
                ${conversation.external_contact_id ? `<strong>${safe(conversation.external_contact_id)}</strong>` : ""}
            </div>
            ${controls}
            <div class="inbox-message-list">
                ${messages.length ? messages.map(message => `
                    <div class="inbox-message ${safe(message.role)}">
                        <strong>${safe(message.role === "assistant" ? "AI Employee" : message.role === "human" ? "Human Employee" : "Customer")}</strong>
                        <div>${safe(message.content)}</div>
                        <small>${formatDate(message.created_at)}</small>
                    </div>
                `).join("") : '<div class="empty-state">No messages in this conversation.</div>'}
            </div>
        `;
        const messageList = target.querySelector(".inbox-message-list");
        if (messageList) messageList.scrollTop = messageList.scrollHeight;
    } catch (error) {
        target.innerHTML = `<div class="empty-state">${safe(error.message)}</div>`;
    }
};
