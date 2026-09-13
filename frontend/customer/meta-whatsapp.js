let xvondCustomerMetaSignupState = null;
let xvondCustomerMetaSignupMessage = null;
let xvondCustomerMetaSdkPromise = null;

function xvondCustomerTrustedMetaOrigin(origin) {
    try {
        const url = new URL(origin);
        const host = (url.hostname || "").toLowerCase();
        return url.protocol === "https:" && (host === "facebook.com" || host.endsWith(".facebook.com"));
    } catch (_) {
        return false;
    }
}

function xvondCustomerLoadMetaSdk(appId, graphVersion) {
    if (window.FB) {
        FB.init({appId, cookie: true, xfbml: false, version: graphVersion || "v26.0"});
        return Promise.resolve();
    }
    if (xvondCustomerMetaSdkPromise) return xvondCustomerMetaSdkPromise;
    xvondCustomerMetaSdkPromise = new Promise((resolve, reject) => {
        window.fbAsyncInit = function () {
            FB.init({appId, cookie: true, xfbml: false, version: graphVersion || "v26.0"});
            resolve();
        };
        const existing = document.getElementById("facebook-jssdk");
        if (existing) {
            existing.addEventListener("load", () => resolve(), {once: true});
            return;
        }
        const script = document.createElement("script");
        script.id = "facebook-jssdk";
        script.async = true;
        script.defer = true;
        script.crossOrigin = "anonymous";
        script.src = "https://connect.facebook.net/en_US/sdk.js";
        script.onerror = () => reject(new Error("Could not load Meta SDK"));
        document.head.appendChild(script);
    });
    return xvondCustomerMetaSdkPromise;
}

function xvondCustomerMetaLoginOptions(config) {
    const extras = {setup: {}};
    if (config.feature_type) extras.featureType = config.feature_type;
    if (config.session_info_version) extras.sessionInfoVersion = String(config.session_info_version);
    return {
        config_id: config.config_id,
        response_type: "code",
        override_default_response_type: true,
        extras,
    };
}

window.addEventListener("message", event => {
    if (!xvondCustomerTrustedMetaOrigin(event.origin)) return;
    let payload = event.data;
    if (typeof payload === "string") {
        try { payload = JSON.parse(payload); } catch (_) { return; }
    }
    if (!payload || payload.type !== "WA_EMBEDDED_SIGNUP") return;
    const completedEvents = new Set([
        "FINISH",
        "FINISH_ONLY_WABA",
        "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING"
    ]);
    if (completedEvents.has(payload.event)) {
        xvondCustomerMetaSignupMessage = {...(payload.data || {}), event: payload.event};
    }
});

window.openCustomerMetaWhatsAppConnect = async function (agentId) {
    try {
        const config = await api(`/customer/meta/whatsapp/embedded-signup/config?agent_id=${Number(agentId)}`);
        if (!config.ready) {
            alert("WhatsApp connection is not configured on the Xvond server yet.");
            return;
        }
        xvondCustomerMetaSignupState = {agentId: Number(agentId)};
        xvondCustomerMetaSignupMessage = null;
        await xvondCustomerLoadMetaSdk(config.app_id, config.graph_api_version);
        FB.login(response => {
            const code = response?.authResponse?.code;
            if (!code) {
                if (response?.status !== "unknown") alert("Meta did not return an authorization code.");
                return;
            }
            xvondCustomerFinishMetaWhatsAppSignup(code);
        }, xvondCustomerMetaLoginOptions(config));
    } catch (error) {
        alert(error.message || String(error));
    }
};

async function xvondCustomerFinishMetaWhatsAppSignup(code) {
    try {
        for (let attempt = 0; attempt < 40 && !xvondCustomerMetaSignupMessage; attempt += 1) {
            await new Promise(resolve => setTimeout(resolve, 250));
        }
        const data = xvondCustomerMetaSignupMessage || {};
        const wabaId = data.waba_id || data.wabaId;
        const phoneNumberId = data.phone_number_id || data.phoneNumberId || null;
        const businessId = data.business_id || data.businessId || null;
        if (!wabaId) {
            alert("Meta authorization succeeded, but the WhatsApp Business Account was not returned. Finish the Meta setup window completely and try again.");
            return;
        }
        const result = await api("/customer/meta/whatsapp/embedded-signup/complete", {
            method: "POST",
            body: JSON.stringify({
                agent_id: xvondCustomerMetaSignupState.agentId,
                code: String(code),
                waba_id: String(wabaId),
                phone_number_id: phoneNumberId ? String(phoneNumberId) : null,
                business_id: businessId ? String(businessId) : null,
                connection_mode: data.event === "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING"
                    ? "coexistence"
                    : "embedded_signup"
            })
        });
        if (result.ready) {
            alert(`WhatsApp connected successfully.\n${result.display_phone_number || result.phone_number_id}`);
        } else {
            alert(`WhatsApp connected. Xvond still needs: ${(result.blockers || []).join("; ")}`);
        }
        await loadAgents();
    } catch (error) {
        alert(error.message || String(error));
    } finally {
        xvondCustomerMetaSignupState = null;
        xvondCustomerMetaSignupMessage = null;
    }
}

async function xvondDecorateCustomerAgentsWithWhatsApp() {
    if (!currentUser || !["owner", "admin", "manager"].includes(currentUser.role)) return;
    const cards = Array.from(document.querySelectorAll("#agents-list .agent"));
    await Promise.all((agents || []).map(async (agent, index) => {
        const card = cards[index];
        if (!card || card.querySelector(".xvond-whatsapp-connect")) return;
        const box = document.createElement("div");
        box.className = "xvond-whatsapp-connect";
        box.style.marginTop = "14px";
        box.style.paddingTop = "12px";
        box.style.borderTop = "1px solid rgba(148,163,184,.25)";
        box.innerHTML = `<p class="muted" style="margin:0 0 8px">WhatsApp: checking connection...</p>`;
        card.appendChild(box);
        try {
            const config = await api(`/customer/meta/whatsapp/embedded-signup/config?agent_id=${Number(agent.id)}`);
            const status = config.connected
                ? `WhatsApp: ${safe(config.display_phone_number || "Connected")}${config.verified_name ? ` · ${safe(config.verified_name)}` : ""}`
                : "Connect this AI employee to your WhatsApp Business number.";
            const label = config.connected ? "Reconnect WhatsApp" : "Connect WhatsApp";
            box.innerHTML = `
                <p class="muted" style="margin:0 0 8px">${status}</p>
                <button type="button" onclick="openCustomerMetaWhatsAppConnect(${Number(agent.id)})" ${config.ready ? "" : "disabled"}>${label}</button>
                ${config.ready ? "" : '<p class="muted" style="margin:8px 0 0">WhatsApp onboarding is not configured on the Xvond server yet.</p>'}
            `;
        } catch (error) {
            box.innerHTML = `<p class="muted" style="margin:0">WhatsApp connection status unavailable: ${safe(error.message || String(error))}</p>`;
        }
    }));
}

if (typeof loadAgents === "function") {
    const xvondOriginalCustomerLoadAgents = loadAgents;
    loadAgents = async function (...args) {
        const result = await xvondOriginalCustomerLoadAgents(...args);
        await xvondDecorateCustomerAgentsWithWhatsApp();
        return result;
    };
}
