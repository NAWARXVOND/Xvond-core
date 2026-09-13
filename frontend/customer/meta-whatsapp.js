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
    // Embedded Signup needs config_id and a code response, which Meta's FedCM
    // credential request does not forward. Keep the configured OAuth popup flow.
    if (window.FB) {
        FB.init({appId, cookie: true, xfbml: false, version: graphVersion || "v26.0", fedCM: false});
        return Promise.resolve();
    }
    if (xvondCustomerMetaSdkPromise) return xvondCustomerMetaSdkPromise;
    xvondCustomerMetaSdkPromise = new Promise((resolve, reject) => {
        window.fbAsyncInit = function () {
            FB.init({appId, cookie: true, xfbml: false, version: graphVersion || "v26.0", fedCM: false});
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

function xvondCustomerWhatsAppStatus(config) {
    if (!config.connected) {
        const invalidToken = config.connection_status === "invalid_token";
        return {
            title: invalidToken ? "WhatsApp مفصول · رمز Meta غير صالح" : "WhatsApp غير مربوط",
            detail: safe(config.connection_issue || "اربط رقم WhatsApp Business بهذا الموظف ليبدأ بالرد على العملاء."),
            label: config.configured ? "إعادة ربط WhatsApp" : "ربط WhatsApp",
        };
    }
    const phone = safe(config.display_phone_number || "الرقم متصل");
    const name = config.verified_name ? ` · ${safe(config.verified_name)}` : "";
    if (config.runtime_ready) {
        return {
            title: `WhatsApp جاهز · ${phone}${name}`,
            detail: config.coexistence
                ? "الوضع المشترك مفعّل: الموظف AI وموظفو WhatsApp Business يعملون على نفس الرقم."
                : "الموظف AI مفعّل ويستقبل الرسائل على هذا الرقم.",
            label: "إعادة ربط WhatsApp",
        };
    }
    return {
        title: `WhatsApp مربوط لكنه غير جاهز · ${phone}${name}`,
        detail: "أكمل المتطلبات الظاهرة أدناه ثم أعد تحميل الصفحة.",
        label: "إعادة ربط WhatsApp",
    };
}

function xvondCustomerWhatsAppBlockers(config) {
    const blockers = Array.isArray(config.blockers) ? config.blockers.filter(Boolean) : [];
    if (!config.connected || blockers.length === 0) return "";
    return `<ul class="muted" style="margin:8px 0 0;padding-inline-start:20px">${blockers.map(item => `<li>${safe(item)}</li>`).join("")}</ul>`;
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
            alert(`إعداد WhatsApp غير مكتمل على خادم Xvond: ${(config.missing_settings || []).join(", ")}`);
            return;
        }
        xvondCustomerMetaSignupState = {agentId: Number(agentId)};
        xvondCustomerMetaSignupMessage = null;
        await xvondCustomerLoadMetaSdk(config.app_id, config.graph_api_version);
        FB.login(response => {
            const code = response?.authResponse?.code;
            if (!code) {
                if (response?.status !== "unknown") alert("Meta لم تُرجع رمز التفويض.");
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
            alert("تم تفويض Meta، لكن حساب WhatsApp Business لم يصل إلى Xvond. أكمل نافذة Meta بالكامل ثم حاول مجددًا.");
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
        if (result.runtime_ready) {
            const mode = result.coexistence ? "الوضع المشترك مع WhatsApp Business مفعّل." : "الموظف AI أصبح مفعّلًا على WhatsApp.";
            alert(`تم ربط WhatsApp بنجاح.\n${result.display_phone_number || result.phone_number_id}\n${mode}`);
        } else {
            alert(`تم ربط WhatsApp، لكن الموظف لم يصبح جاهزًا بعد:\n${(result.blockers || []).join("\n")}`);
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
        box.innerHTML = `<p class="muted" style="margin:0 0 8px">WhatsApp: جاري فحص الحالة...</p>`;
        card.appendChild(box);
        try {
            const config = await api(`/customer/meta/whatsapp/embedded-signup/config?agent_id=${Number(agent.id)}`);
            const status = xvondCustomerWhatsAppStatus(config);
            box.innerHTML = `
                <p style="margin:0 0 6px"><strong>${status.title}</strong></p>
                <p class="muted" style="margin:0 0 8px">${status.detail}</p>
                ${xvondCustomerWhatsAppBlockers(config)}
                <button type="button" style="margin-top:10px" onclick="openCustomerMetaWhatsAppConnect(${Number(agent.id)})" ${config.ready ? "" : "disabled"}>${status.label}</button>
                ${config.ready ? "" : `<p class="muted" style="margin:8px 0 0">إعداد Meta على Xvond ناقص: ${safe((config.missing_settings || []).join(", ") || "إعدادات الخادم")}</p>`}
            `;
        } catch (error) {
            box.innerHTML = `<p class="muted" style="margin:0">تعذر قراءة حالة WhatsApp: ${safe(error.message || String(error))}</p>`;
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
