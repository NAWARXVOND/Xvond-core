let activeInboxConversationId = null;

function inboxModeBadge(mode) {
    const human = String(mode || "ai").toLowerCase() === "human";
    return `<span class="inbox-badge ${human ? "handoff-human" : "handoff-ai"}"><span class="mode-dot"></span>${human ? "Human active" : "AI active"}</span>`;
}

function inboxChannelIcon(channelType) {
    const type = String(channelType || "unknown").toLowerCase();
    if (type === "whatsapp") return "WA";
    if (type === "instagram") return "IG";
    if (type === "website") return "WEB";
    if (type === "voice") return "CALL";
    if (type === "portal_test") return "TEST";
    return "MSG";
}

function inboxMessageLabel(role) {
    if (role === "assistant") return "AI Employee";
    if (role === "human") return "Human Employee";
    return "Customer";
}

function inboxMessageClass(role) {
    if (role === "assistant") return "assistant";
    if (role === "human") return "human";
    return "user";
}

ensureInboxMarkup = function() {
    const page = document.getElementById("page-conversations");
    if (!page || page.dataset.inboxV2Ready === "1") return;
    page.dataset.inboxReady = "1";
    page.dataset.inboxV2Ready = "1";
    page.innerHTML = `
        <div class="inbox-v2-shell">
            <div class="inbox-v2-toolbar">
                <div>
                    <h2>Customer Inbox</h2>
                    <p>Monitor AI conversations and take over whenever a human response is needed.</p>
                </div>
                <button class="inbox-refresh-button" onclick="loadConversations()">Refresh</button>
            </div>
            <div class="inbox-v2-filters">
                <select id="conversation-agent" onchange="loadConversations()" aria-label="Filter by AI employee">
                    <option value="">All AI Employees</option>
                </select>
                <select id="conversation-channel" onchange="loadConversations()" aria-label="Filter by channel">
                    <option value="">All Channels</option>
                </select>
                <div class="inbox-v2-search">
                    <input id="conversation-search" placeholder="Search customer or conversation..." onkeydown="if(event.key==='Enter') loadConversations()">
                    <button onclick="loadConversations()">Search</button>
                </div>
            </div>
            <div class="inbox-v2-layout">
                <aside class="inbox-v2-sidebar">
                    <div class="inbox-v2-sidebar-head">
                        <strong>Conversations</strong>
                        <span id="conversation-count">0</span>
                    </div>
                    <div id="conversation-list" class="inbox-list"></div>
                </aside>
                <section id="conversation-messages" class="conversation-messages inbox-thread inbox-v2-thread">
                    <div class="inbox-v2-empty">
                        <div class="inbox-v2-empty-icon">↗</div>
                        <strong>Select a conversation</strong>
                        <p>Messages, AI status and human takeover controls will appear here.</p>
                    </div>
                </section>
            </div>
        </div>
    `;
};

async function customerTakeOverConversation(conversationId) {
    const button = document.getElementById("takeover-button");
    if (button) {
        button.disabled = true;
        button.textContent = "Taking over...";
    }
    try {
        await api(`/customer/inbox/${conversationId}/take-over`, {method: "POST", body: "{}"});
        activeInboxConversationId = conversationId;
        await loadInboxConversation(conversationId);
        await loadConversations({preserveThread: true});
    } catch (error) {
        alert(error.message);
    } finally {
        if (button) button.disabled = false;
    }
}

async function customerReturnConversationToAI(conversationId) {
    if (!confirm("Return this conversation to the AI employee?")) return;
    const button = document.getElementById("return-ai-button");
    if (button) {
        button.disabled = true;
        button.textContent = "Returning...";
    }
    try {
        await api(`/customer/inbox/${conversationId}/return-ai`, {method: "POST", body: "{}"});
        activeInboxConversationId = conversationId;
        await loadInboxConversation(conversationId);
        await loadConversations({preserveThread: true});
    } catch (error) {
        alert(error.message);
    } finally {
        if (button) button.disabled = false;
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
        if (input) input.value = "";
        activeInboxConversationId = conversationId;
        await loadInboxConversation(conversationId);
        await loadConversations({preserveThread: true});
    } catch (error) {
        alert(error.message);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Send";
        }
    }
}

loadConversations = async function(options = {}) {
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
        const count = document.getElementById("conversation-count");
        if (count) count.textContent = String(items.length);

        list.innerHTML = items.length ? items.map(item => {
            const preview = item.last_message?.content || item.title || "No messages";
            const selected = Number(item.id) === Number(activeInboxConversationId) ? " selected" : "";
            const title = item.external_contact_id || item.title || `Conversation ${item.id}`;
            return `
                <button class="inbox-item${selected}" data-conversation-id="${item.id}" onclick="loadInboxConversation(${item.id}, this)">
                    <div class="inbox-item-avatar">${safe(inboxChannelIcon(item.channel_type))}</div>
                    <div class="inbox-item-body">
                        <div class="inbox-item-top">
                            <strong>${safe(title)}</strong>
                            <span>${formatDate(item.last_message?.created_at || item.created_at)}</span>
                        </div>
                        <p>${safe(preview)}</p>
                        <div class="inbox-badges">
                            ${inboxBadge(item.agent_name, "agent-badge")}
                            ${inboxBadge(item.channel_label, `channel-${item.channel_type || "unknown"}`)}
                            ${inboxModeBadge(item.mode)}
                        </div>
                    </div>
                </button>
            `;
        }).join("") : '<div class="empty-state">No conversations match these filters.</div>';

        if (!options.preserveThread && activeInboxConversationId && !items.some(item => Number(item.id) === Number(activeInboxConversationId))) {
            activeInboxConversationId = null;
            const target = document.getElementById("conversation-messages");
            if (target) target.innerHTML = '<div class="inbox-v2-empty"><strong>Select a conversation</strong><p>Choose a conversation from the list to view it.</p></div>';
        }
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${safe(error.message)}</div>`;
    }
};

loadInboxConversation = async function(conversationId, button = null) {
    activeInboxConversationId = conversationId;
    document.querySelectorAll(".inbox-item").forEach(item => item.classList.remove("selected"));
    const selectedButton = button || document.querySelector(`.inbox-item[data-conversation-id="${conversationId}"]`);
    if (selectedButton) selectedButton.classList.add("selected");

    const target = document.getElementById("conversation-messages");
    if (!target) return;
    target.innerHTML = '<div class="empty-state">Loading messages...</div>';
    try {
        const result = await api(`/customer/inbox/${conversationId}`);
        const conversation = result.conversation || {};
        const messages = result.messages || [];
        const human = String(conversation.mode || "ai").toLowerCase() === "human";
        const contact = conversation.external_contact_id || conversation.title || `Conversation ${conversationId}`;

        const controls = human ? `
            <div class="handoff-controls human-active">
                <div class="handoff-copy">
                    <span class="handoff-kicker">Human control</span>
                    <strong>You are replying to this customer</strong>
                    <p>The AI employee remains paused until you return control.</p>
                </div>
                <button id="return-ai-button" class="secondary-button" onclick="customerReturnConversationToAI(${conversationId})">Return to AI</button>
            </div>
        ` : `
            <div class="handoff-controls ai-active">
                <div class="handoff-copy">
                    <span class="handoff-kicker">AI control</span>
                    <strong>AI employee is handling this conversation</strong>
                    <p>Take over only when a human response is required.</p>
                </div>
                <button id="takeover-button" class="takeover-button" onclick="customerTakeOverConversation(${conversationId})">Take Over</button>
            </div>
        `;

        const composer = human ? `
            <div class="human-reply-box">
                <textarea id="human-reply-message" rows="2" maxlength="12000" placeholder="Type your reply..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();customerSendHumanReply(${conversationId})}"></textarea>
                <div class="human-reply-actions">
                    <span>Enter to send · Shift+Enter for new line</span>
                    <button id="human-reply-send" onclick="customerSendHumanReply(${conversationId})">Send</button>
                </div>
            </div>
        ` : `
            <div class="ai-reply-lock">
                <span>AI is currently responding automatically.</span>
                <button onclick="customerTakeOverConversation(${conversationId})">Take over to reply</button>
            </div>
        `;

        target.innerHTML = `
            <div class="inbox-thread-head">
                <div class="inbox-thread-identity">
                    <div class="inbox-thread-avatar">${safe(inboxChannelIcon(conversation.channel_type))}</div>
                    <div>
                        <h3>${safe(contact)}</h3>
                        <div class="inbox-badges">
                            ${inboxBadge(conversation.agent_name, "agent-badge")}
                            ${inboxBadge(conversation.channel_label, `channel-${conversation.channel_type || "unknown"}`)}
                            ${inboxModeBadge(conversation.mode)}
                        </div>
                    </div>
                </div>
                <div class="inbox-thread-meta">${safe(conversation.message_count || messages.length)} messages</div>
            </div>
            ${controls}
            <div class="inbox-message-list">
                ${messages.length ? messages.map(message => `
                    <div class="inbox-message-row ${safe(inboxMessageClass(message.role))}">
                        <div class="inbox-message ${safe(inboxMessageClass(message.role))}">
                            <div class="inbox-message-author">${safe(inboxMessageLabel(message.role))}</div>
                            <div class="inbox-message-content">${safe(message.content)}</div>
                            <small>${formatDate(message.created_at)}</small>
                        </div>
                    </div>
                `).join("") : '<div class="empty-state">No messages in this conversation.</div>'}
            </div>
            ${composer}
        `;
        const messageList = target.querySelector(".inbox-message-list");
        if (messageList) messageList.scrollTop = messageList.scrollHeight;
    } catch (error) {
        target.innerHTML = `<div class="empty-state">${safe(error.message)}</div>`;
    }
};
