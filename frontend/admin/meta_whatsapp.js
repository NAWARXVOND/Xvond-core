let xvondMetaSignupState = null;
let xvondMetaSignupMessage = null;
let xvondMetaSdkPromise = null;

function xvondLoadMetaSdk(appId) {
    if (window.FB) {
        FB.init({
            appId: appId,
            cookie: true,
            xfbml: false,
            version: 'v23.0'
        });
        return Promise.resolve();
    }

    if (xvondMetaSdkPromise) {
        return xvondMetaSdkPromise;
    }

    xvondMetaSdkPromise = new Promise((resolve, reject) => {
        window.fbAsyncInit = function () {
            FB.init({
                appId: appId,
                cookie: true,
                xfbml: false,
                version: 'v23.0'
            });
            resolve();
        };

        const existing = document.getElementById('facebook-jssdk');
        if (existing) {
            existing.addEventListener('load', () => resolve(), {once: true});
            return;
        }

        const script = document.createElement('script');
        script.id = 'facebook-jssdk';
        script.async = true;
        script.defer = true;
        script.crossOrigin = 'anonymous';
        script.src = 'https://connect.facebook.net/en_US/sdk.js';
        script.onerror = () => reject(new Error('Could not load Meta SDK'));
        document.head.appendChild(script);
    });

    return xvondMetaSdkPromise;
}

window.addEventListener('message', (event) => {
    if (!event.origin || !event.origin.endsWith('facebook.com')) {
        return;
    }

    let payload = event.data;

    if (typeof payload === 'string') {
        try {
            payload = JSON.parse(payload);
        } catch (_) {
            return;
        }
    }

    if (!payload || payload.type !== 'WA_EMBEDDED_SIGNUP') {
        return;
    }

    if (payload.event === 'FINISH' || payload.event === 'FINISH_ONLY_WABA') {
        xvondMetaSignupMessage = payload.data || {};
    }
});

async function openMetaWhatsAppConnect(agentId) {
    try {
        const config = await api(
            `/admin/meta/whatsapp/embedded-signup/config?agent_id=${Number(agentId)}`
        );

        if (!config.ready) {
            alert('Meta Embedded Signup is not configured on the Xvond server yet.');
            return;
        }

        xvondMetaSignupState = {
            agentId: Number(agentId),
            graphApiVersion: config.graph_api_version
        };
        xvondMetaSignupMessage = null;

        await xvondLoadMetaSdk(config.app_id);

        FB.login(
            async function (response) {
                const code = response && response.authResponse
                    ? response.authResponse.code
                    : null;

                if (!code) {
                    if (response && response.status === 'unknown') {
                        return;
                    }
                    alert('Meta did not return an authorization code.');
                    return;
                }

                await xvondFinishMetaWhatsAppSignup(code);
            },
            {
                config_id: config.config_id,
                response_type: 'code',
                override_default_response_type: true,
                extras: {
                    setup: {},
                    sessionInfoVersion: config.session_info_version || '3'
                }
            }
        );
    } catch (error) {
        alert(error.message || String(error));
    }
}

async function xvondFinishMetaWhatsAppSignup(code) {
    try {
        for (let attempt = 0; attempt < 20 && !xvondMetaSignupMessage; attempt += 1) {
            await new Promise(resolve => setTimeout(resolve, 250));
        }

        const data = xvondMetaSignupMessage || {};
        const wabaId = data.waba_id || data.wabaId;
        const phoneNumberId = data.phone_number_id || data.phoneNumberId;
        const businessId = data.business_id || data.businessId || null;

        if (!wabaId || !phoneNumberId) {
            alert('Meta authorization succeeded, but the WhatsApp account details were not returned. Please finish the WhatsApp setup window completely and try again.');
            return;
        }

        const result = await api(
            '/admin/meta/whatsapp/embedded-signup/complete',
            {
                method: 'POST',
                body: JSON.stringify({
                    agent_id: xvondMetaSignupState.agentId,
                    code: code,
                    waba_id: String(wabaId),
                    phone_number_id: String(phoneNumberId),
                    business_id: businessId ? String(businessId) : null
                })
            }
        );

        alert(
            `WhatsApp connected successfully.\n${result.display_phone_number || result.phone_number_id}`
        );

        if (typeof loadChannelsPage === 'function') {
            await loadChannelsPage();
        }
    } catch (error) {
        alert(error.message || String(error));
    } finally {
        xvondMetaSignupState = null;
        xvondMetaSignupMessage = null;
    }
}

async function xvondRenderMetaWhatsAppConnectPanel() {
    const content = document.getElementById('channels-service-content');

    if (!content || content.dataset.metaWhatsappPanel === '1') {
        return;
    }

    if (typeof getCompanyAgents !== 'function' || !serviceCompanyId) {
        return;
    }

    try {
        const agents = await getCompanyAgents();

        if (!agents.length) {
            return;
        }

        const panel = document.createElement('div');
        panel.className = 'panel';
        panel.style.marginBottom = '20px';
        panel.innerHTML = `
            <div class="section-header">
                <div>
                    <h3>Connect WhatsApp</h3>
                    <p>Connect a client's WhatsApp Business account through Meta Embedded Signup.</p>
                </div>
            </div>
            <div class="form-group">
                <label>AI Agent</label>
                <select id="meta-whatsapp-agent-select">
                    ${agents.map(agent => `
                        <option value="${Number(agent.id)}">
                            ${typeof escapeService === 'function' ? escapeService(agent.name) : agent.name}
                        </option>
                    `).join('')}
                </select>
            </div>
            <button onclick="openMetaWhatsAppConnect(document.getElementById('meta-whatsapp-agent-select').value)">
                Connect WhatsApp with Meta
            </button>
        `;

        content.prepend(panel);
        content.dataset.metaWhatsappPanel = '1';
    } catch (_) {
        // The normal Channels page handles API errors itself.
    }
}

const xvondMetaObserver = new MutationObserver(() => {
    const page = document.getElementById('page-channels-service');
    if (page && !page.classList.contains('hidden')) {
        xvondRenderMetaWhatsAppConnectPanel();
    }
});

window.addEventListener('DOMContentLoaded', () => {
    xvondMetaObserver.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
    });
});
