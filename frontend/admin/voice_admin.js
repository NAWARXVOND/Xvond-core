async function xvondLoadVoiceAdminPanel() {
    const content = document.getElementById('channels-service-content');
    if (!content || !serviceCompanyId) return;

    let panel = document.getElementById('xvond-voice-admin-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'xvond-voice-admin-panel';
        panel.className = 'panel';
        panel.style.marginBottom = '20px';
        content.prepend(panel);
    }

    panel.innerHTML = '<p>Loading Voice Agent setup...</p>';

    try {
        const [agentsResult, channelsResult] = await Promise.all([
            getCompanyAgents(),
            api(`/admin/channels/companies/${serviceCompanyId}`)
        ]);

        const agents = agentsResult || [];
        const voiceChannels = (channelsResult.channels || []).filter(
            item => item.channel_type === 'voice'
        );

        if (!agents.length) {
            panel.innerHTML = `
                <div class="section-header"><div><h3>Voice Agent</h3></div></div>
                <p>Create an AI Agent first.</p>
            `;
            return;
        }

        panel.innerHTML = `
            <div class="section-header">
                <div>
                    <h3>Voice Agent</h3>
                    <p>Create a real voice channel, configure its dialect and connect a real Vapi phone number.</p>
                </div>
            </div>

            <div class="form-group">
                <label>AI Agent</label>
                <select id="voice-admin-agent">
                    ${agents.map(agent => `
                        <option value="${Number(agent.id)}">${escapeService(agent.name)}</option>
                    `).join('')}
                </select>
            </div>

            <div class="form-group">
                <label>Language</label>
                <select id="voice-admin-language">
                    <option value="ar">Arabic</option>
                    <option value="en">English</option>
                    <option value="auto">Auto</option>
                </select>
            </div>

            <div class="form-group">
                <label>Dialect</label>
                <select id="voice-admin-dialect">
                    <option value="omani">Omani</option>
                    <option value="gulf">Gulf</option>
                    <option value="levantine">Levantine</option>
                    <option value="egyptian">Egyptian</option>
                    <option value="msa">Modern Standard Arabic</option>
                    <option value="auto">Auto</option>
                </select>
            </div>

            <div class="form-group">
                <label>Tone</label>
                <select id="voice-admin-tone">
                    <option value="professional_friendly">Professional + Friendly</option>
                    <option value="professional">Professional</option>
                    <option value="friendly">Friendly</option>
                    <option value="luxury">Luxury</option>
                </select>
            </div>

            <div class="form-group">
                <label>Greeting</label>
                <input id="voice-admin-greeting" placeholder="مثال: أهلًا وسهلًا، كيف أقدر أخدمك؟">
            </div>

            <div class="form-group">
                <label>Voice ID (optional)</label>
                <input id="voice-admin-voice-id" placeholder="Leave blank to use provider default">
            </div>

            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">
                <button onclick="xvondCreateOrUpdateVoiceChannel()">Save Voice Settings</button>
                <button onclick="xvondRefreshVoiceProvisioning()">Refresh Vapi Numbers</button>
            </div>

            <div id="voice-admin-provisioning"></div>
        `;

        const selectedAgentId = Number(document.getElementById('voice-admin-agent').value);
        const existing = voiceChannels.find(
            item => Number(item.agent_id) === selectedAgentId
        );
        xvondApplyExistingVoiceConfig(existing);

        document.getElementById('voice-admin-agent').addEventListener('change', event => {
            const channel = voiceChannels.find(
                item => Number(item.agent_id) === Number(event.target.value)
            );
            xvondApplyExistingVoiceConfig(channel);
            xvondRenderVoiceProvisioning(channel);
        });

        await xvondRenderVoiceProvisioning(existing);
    } catch (error) {
        panel.innerHTML = `<p>${escapeService(error.message || String(error))}</p>`;
    }
}

function xvondApplyExistingVoiceConfig(channel) {
    const config = channel && channel.config ? channel.config : {};
    const setValue = (id, value, fallback) => {
        const el = document.getElementById(id);
        if (el) el.value = value || fallback || '';
    };

    setValue('voice-admin-language', config.language, 'ar');
    setValue('voice-admin-dialect', config.dialect, 'omani');
    setValue('voice-admin-tone', config.tone, 'professional_friendly');
    setValue('voice-admin-greeting', config.greeting_message, '');
    setValue('voice-admin-voice-id', config.voice_id, '');
}

async function xvondCreateOrUpdateVoiceChannel() {
    try {
        const agentId = Number(document.getElementById('voice-admin-agent').value);
        const channelsResult = await api(`/admin/channels/companies/${serviceCompanyId}`);
        const existing = (channelsResult.channels || []).find(
            item => item.channel_type === 'voice' && Number(item.agent_id) === agentId
        );

        const config = {
            provider: 'vapi',
            phone_number: existing && existing.config ? (existing.config.phone_number || '') : '',
            language: document.getElementById('voice-admin-language').value,
            dialect: document.getElementById('voice-admin-dialect').value,
            tone: document.getElementById('voice-admin-tone').value,
            response_length: 'short',
            allow_interruption: true,
            greeting_message: document.getElementById('voice-admin-greeting').value.trim(),
            voice_id: document.getElementById('voice-admin-voice-id').value.trim(),
            channel_instructions: 'Respond naturally for a live phone conversation. Keep spoken answers concise and easy to understand.'
        };

        if (existing) {
            await api(`/admin/channels/${existing.id}`, {
                method: 'PUT',
                body: JSON.stringify({config, enabled: true})
            });
        } else {
            await api(`/admin/channels/agents/${agentId}`, {
                method: 'POST',
                body: JSON.stringify({channel_type: 'voice', config})
            });
        }

        alert('Voice settings saved.');
        await xvondLoadVoiceAdminPanel();
        if (typeof loadChannelsPage === 'function') await loadChannelsPage();
    } catch (error) {
        alert(error.message || String(error));
    }
}

async function xvondRefreshVoiceProvisioning() {
    try {
        const agentId = Number(document.getElementById('voice-admin-agent').value);
        const channelsResult = await api(`/admin/channels/companies/${serviceCompanyId}`);
        const channel = (channelsResult.channels || []).find(
            item => item.channel_type === 'voice' && Number(item.agent_id) === agentId
        );
        await xvondRenderVoiceProvisioning(channel, true);
    } catch (error) {
        alert(error.message || String(error));
    }
}

async function xvondRenderVoiceProvisioning(channel) {
    const target = document.getElementById('voice-admin-provisioning');
    if (!target) return;

    if (!channel) {
        target.innerHTML = '<p>Save Voice Settings first, then connect a real phone number.</p>';
        return;
    }

    target.innerHTML = '<p>Loading Vapi provisioning status...</p>';

    try {
        const [status, phonesResult] = await Promise.all([
            api(`/admin/voice/channels/${channel.id}/vapi/status`),
            api('/admin/voice/vapi/phone-numbers')
        ]);
        const phones = phonesResult.phone_numbers || [];

        target.innerHTML = `
            <div class="agent-card">
                <h3>Live Phone Connection</h3>
                <p>Status: <strong>${status.provisioned ? 'CONNECTED' : 'NOT CONNECTED'}</strong></p>
                ${status.phone_number ? `<p>Phone: ${escapeService(status.phone_number)}</p>` : ''}
                ${status.vapi_assistant_id ? `<p>Assistant ID: ${escapeService(status.vapi_assistant_id)}</p>` : ''}

                <div class="form-group" style="margin-top:14px">
                    <label>Real Vapi Phone Number</label>
                    <select id="voice-admin-phone">
                        ${phones.length ? phones.map(phone => `
                            <option value="${escapeService(phone.id)}" ${
                                String(status.vapi_phone_number_id || '') === String(phone.id) ? 'selected' : ''
                            }>
                                ${escapeService(phone.number || phone.name || phone.id)}
                            </option>
                        `).join('') : '<option value="">No phone numbers found in Vapi</option>'}
                    </select>
                </div>

                <button ${phones.length ? '' : 'disabled'} onclick="xvondProvisionVoiceChannel(${Number(channel.id)})">
                    ${status.provisioned ? 'Update Live Voice Connection' : 'Connect Live Voice Number'}
                </button>
            </div>
        `;
    } catch (error) {
        target.innerHTML = `
            <div class="agent-card">
                <h3>Live Phone Connection</h3>
                <p>${escapeService(error.message || String(error))}</p>
                <p>VAPI_API_KEY and XVOND_PUBLIC_BASE_URL must be configured on the server before provisioning.</p>
            </div>
        `;
    }
}

async function xvondProvisionVoiceChannel(channelId) {
    const select = document.getElementById('voice-admin-phone');
    const phoneNumberId = select ? select.value : '';

    if (!phoneNumberId) {
        alert('Choose a real Vapi phone number first.');
        return;
    }

    try {
        const result = await api(`/admin/voice/channels/${channelId}/vapi/provision`, {
            method: 'POST',
            body: JSON.stringify({phone_number_id: phoneNumberId})
        });

        alert(`Voice Agent connected.\nPhone: ${result.phone_number || phoneNumberId}`);
        await xvondRefreshVoiceProvisioning();
        if (typeof loadChannelsPage === 'function') await loadChannelsPage();
    } catch (error) {
        alert(error.message || String(error));
    }
}

const xvondVoiceAdminObserver = new MutationObserver(() => {
    const page = document.getElementById('page-channels-service');
    if (page && !page.classList.contains('hidden')) {
        xvondLoadVoiceAdminPanel();
    }
});

window.addEventListener('DOMContentLoaded', () => {
    xvondVoiceAdminObserver.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
    });
});
