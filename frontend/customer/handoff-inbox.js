let activeInboxConversationId = null;
let activeInboxFingerprint = null;
let inboxRefreshTimer = null;
let inboxRefreshBusy = false;
let inboxListRequest = 0;
let inboxThreadRequest = 0;

function inboxModeBadge(mode) {
    const human = String(mode || "ai").toLowerCase() === "human";
    return `<span class="inbox-badge ${human ? "handoff-human" : "handoff-ai"}"><span class="mode-dot"></span>${human ? "Human active" : "AI active"}</span>`;
}

function inboxAssignmentBadge(conversation) {
    if (String(conversation.mode || "ai").toLowerCase() !== "human") return "";
    if (conversation.handoff_assigned_to_me === true) return inboxBadge("Assigned to you", "handoff-human");
    if (conversation.handoff_claimable === true) return inboxBadge("Needs owner", "handoff-human");
    if (conversation.handoff_assigned_user_id) return inboxBadge("Owned by teammate", "handoff-human");
    return "";
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

function inboxThreadFingerprint(result) {
    const conversation = result?.conversation || {};
    const messages = result?.messages || [];
    const last = messages.length ? messages[messages.length - 1] : null;
    return [
        conversation.id || "",
        conversation.mode || "ai",
        conversation.handoff_supported ? "handoff" : "monitor",
        conversation.human_reply_supported ? "reply" : "readonly",
        conversation.handoff_assigned_user_id || "unassigned",
        conversation.handoff_assigned_to_me ? "mine" : "not-mine",
        conversation.handoff_claimable ? "claimable" : "claimed",
        conversation.handoff_can_return_ai ? "can-return" : "cannot-return",
        conversation.message_count ?? messages.length,
        last?.id || 0,
        last?.role || ""
    ].join(":");
}

function inboxPageVisible() {
    const portal = document.getElementById("portal");
    const page = document.getElementById("page-conversations");
    return Boolean(
        portal && !portal.classList.contains("hidden") &&
        page && !page.classList.contains("hidden")
    );
}

function startInboxLiveRefresh() {
    if (inboxRefreshTimer) return;
    inboxRefreshTimer = window.setInterval(async () => {
        if (!inboxPageVisible() || inboxRefreshBusy) return;
        inboxRefreshBusy = true;
        try {
            await loadConversations({preserveThread: true, silent: true});
            if (activeInboxConversationId) {
                await loadInboxConversation(
                    activeInboxConversationId,
                    null,
                    {silent: true}
                );
            }
        } catch (_) {
            // Individual loaders already surface meaningful errors and session expiry.
        } finally {
            inboxRefreshBusy = false;
        }
    }, 2500);
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
                    <p>One operating queue for every supported channel. Human conversations are claimed by one teammate at a time to prevent duplicate replies.</p>
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
                        <p>Messages, AI status, ownership and available human controls will appear here.</p>
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
        button.textContent = "Claiming...";
    }
    try {
        await api(`/customer/inbox/${conversationId}/take-over`, {method: "POST", body: "{}"});
        activeInboxConversationId = conversationId;
        activeInboxFingerprint = null;
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
        activeInboxFingerprint = null;
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
        activeInboxFingerprint = null;
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
    const requestVersion = ++inboxListRequest;
    ensureInboxMarkup();
    startInboxLiveRefresh();
    const list = document.getElementById("conversation-list");
    if (!list) return;

    const agentId = document.getElementById("conversation-agent")?.value || "";
    const channelType = document.getElementById("conversation-channel")?.value || "";
    const search = document.getElementById("conversation-search")?.value.trim() || "";
    const params = new URLSearchParams();
    if (agentId) params.set("agent_id", agentId);
    if (channelType) params.set("channel_type", channelType);
    if (search) params.set("search", search);

    if (!options.silent) {
        list.innerHTML = '<div class="empty-state">Loading conversations...</div>';
    }
    try {
        const result = await api(`/customer/inbox${params.toString() ? `?${params}` : ""}`);
        if (requestVersion !== inboxListRequest) return;
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
                            ${inboxAssignmentBadge(item)}
                        </div>
                    </div>
                </button>
            `;
        }).join("") : '<div class="empty-state">No conversations match these filters.</div>';

        if (activeInboxConversationId && !items.some(item => Number(item.id) === Number(activeInboxConversationId))) {
            activeInboxConversationId = null;
            activeInboxFingerprint = null;
            const target = document.getElementById("conversation-messages");
            if (target) target.innerHTML = '<div class="inbox-v2-empty"><strong>Select a conversation</strong><p>Choose a conversation from the list to view it.</p></div>';
        }
    } catch (error) {
        if (!options.silent) {
            list.innerHTML = `<div class="empty-state">${safe(error.message)}</div>`;
        }
    }
};

function handoffControls(conversation, conversationId) {
    const human = String(conversation.mode || "ai").toLowerCase() === "human";
    const supported = conversation.handoff_supported === true;
    const assignedToMe = conversation.handoff_assigned_to_me === true;
    const claimable = conversation.handoff_claimable === true;
    const canReturn = conversation.handoff_can_return_ai === true;

    if (human && claimable) {
        return `
            <div class="handoff-controls human-active">
                <div class="handoff-copy">
                    <span class="handoff-kicker">Human requested</span>
                    <strong>This conversation needs a teammate</strong>
                    <p>The AI employee is paused. Claim the conversation before replying so two teammates cannot answer the same customer.</p>
                </div>
                <button id="takeover-button" class="takeover-button" onclick="customerTakeOverConversation(${conversationId})">Claim Conversation</button>
            </div>
        `;
    }

    if (human && assignedToMe) {
        return `
            <div class="handoff-controls human-active">
                <div class="handoff-copy">
                    <span class="handoff-kicker">Your conversation</span>
                    <strong>You own this human handoff</strong>
                    <p>The AI employee remains paused while you reply from this workspace.</p>
                </div>
                ${canReturn ? `<button id="return-ai-button" class="secondary-button" onclick="customerReturnConversationToAI(${conversationId})">Return to AI</button>` : ""}
            </div>
        `;
    }

    if (human) {
        return `
            <div class="handoff-controls human-active">
                <div class="handoff-copy">
                    <span class="handoff-kicker">Owned by teammate</span>
                    <strong>Another teammate is handling this conversation</strong>
                    <p>You can monitor the thread, but Xvond locks the composer to prevent duplicate replies.</p>
                </div>
                ${canReturn ? `<button id="return-ai-button" class="secondary-button" onclick="customerReturnConversationToAI(${conversationId})">Manager: Return to AI</button>` : ""}
            </div>
        `;
    }

    if (supported) {
        return `
            <div class="handoff-controls ai-active">
                <div class="handoff-copy">
                    <span class="handoff-kicker">AI control</span>
                    <strong>AI employee is handling this conversation</strong>
                    <p>Claim it when a human response is required. AI stays paused until control is explicitly returned.</p>
                </div>
                <button id="takeover-button" class="takeover-button" onclick="customerTakeOverConversation(${conversationId})">Take Over</button>
            </div>
        `;
    }

    return `
        <div class="handoff-controls ai-active">
            <div class="handoff-copy">
                <span class="handoff-kicker">Monitor only</span>
                <strong>AI employee is handling this conversation</strong>
                <p>Live human takeover is not connected for ${safe(conversation.channel_label || "this channel")} yet. Xvond will not show a fake reply control.</p>
            </div>
        </div>
    `;
}

function handoffComposer(conversation, conversationId) {
    const human = String(conversation.mode || "ai").toLowerCase() === "human";
    const takeoverSupported = conversation.handoff_supported === true;
    const replySupported = conversation.human_reply_supported === true;
    const assignedToMe = conversation.handoff_assigned_to_me === true;
    const claimable = conversation.handoff_claimable === true;

    if (human && replySupported && assignedToMe) {
        return `
            <div class="human-reply-box">
                <textarea id="human-reply-message" rows="2" maxlength="12000" placeholder="Type your reply..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();customerSendHumanReply(${conversationId})}"></textarea>
                <div class="human-reply-actions">
                    <span>Enter to send · Shift+Enter for new line</span>
                    <button id="human-reply-send" onclick="customerSendHumanReply(${conversationId})">Send</button>
                </div>
            </div>
        `;
    }

    if (human && claimable && replySupported) {
        return `
            <div class="ai-reply-lock">
                <span>A human response is required. Claim this conversation before replying.</span>
                <button onclick="customerTakeOverConversation(${conversationId})">Claim conversation</button>
            </div>
        `;
    }

    if (human && replySupported) {
        return `
            <div class="ai-reply-lock">
                <span>This conversation is assigned to another teammate. The composer is locked to prevent duplicate replies.</span>
            </div>
        `;
    }

    if (human) {
        return `
            <div class="ai-reply-lock">
                <span>This conversation is under human control, but Xvond has no live reply adapter for this channel. Return control to AI or continue in the channel's native operator tool.</span>
            </div>
        `;
    }

    if (takeoverSupported && replySupported) {
        return `
            <div class="ai-reply-lock">
                <span>AI is currently responding automatically.</span>
                <button onclick="customerTakeOverConversation(${conversationId})">Take over to reply</button>
            </div>
        `;
    }

    return `
        <div class="ai-reply-lock">
            <span>Conversation monitoring is available. Live human reply is not connected for this channel.</span>
        </div>
    `;
}

loadInboxConversation = async function(conversationId, button = null, options = {}) {
    const requestVersion = ++inboxThreadRequest;
    activeInboxConversationId = conversationId;
    document.querySelectorAll(".inbox-item").forEach(item => item.classList.remove("selected"));
    const selectedButton = button || document.querySelector(`.inbox-item[data-conversation-id="${conversationId}"]`);
    if (selectedButton) selectedButton.classList.add("selected");

    const target = document.getElementById("conversation-messages");
    if (!target) return;
    if (!options.silent) {
        target.innerHTML = '<div class="empty-state">Loading messages...</div>';
    }
    try {
        const result = await api(`/customer/inbox/${conversationId}`);
        if (requestVersion !== inboxThreadRequest || Number(activeInboxConversationId) !== Number(conversationId)) return;
        const fingerprint = inboxThreadFingerprint(result);
        if (options.silent && fingerprint === activeInboxFingerprint) return;
        activeInboxFingerprint = fingerprint;

        const conversation = result.conversation || {};
        const messages = result.messages || [];
        const contact = conversation.external_contact_id || conversation.title || `Conversation ${conversationId}`;
        const previousList = target.querySelector(".inbox-message-list");
        const replyDraft = options.silent ? document.getElementById("human-reply-message")?.value : "";
        const keepBottom = !previousList || (previousList.scrollHeight - previousList.scrollTop - previousList.clientHeight < 80);

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
                            ${inboxAssignmentBadge(conversation)}
                        </div>
                    </div>
                </div>
                <div class="inbox-thread-meta">${safe(conversation.message_count || messages.length)} messages</div>
            </div>
            ${handoffControls(conversation, conversationId)}
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
            ${handoffComposer(conversation, conversationId)}
        `;
        const messageList = target.querySelector(".inbox-message-list");
        const composer = document.getElementById("human-reply-message");
        if (composer && replyDraft) composer.value = replyDraft;
        if (messageList && keepBottom) messageList.scrollTop = messageList.scrollHeight;
    } catch (error) {
        if (!options.silent && requestVersion === inboxThreadRequest && Number(activeInboxConversationId) === Number(conversationId)) {
            target.innerHTML = `<div class="empty-state">${safe(error.message)}</div>`;
        }
    }
};
