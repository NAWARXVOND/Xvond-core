function xvondCustomerChannelLabel(type){
    const value=String(type||'').toLowerCase();
    if(value==='whatsapp')return 'WhatsApp';
    if(value==='website')return 'Website Chat';
    if(value==='voice')return 'Voice';
    return value?value.replaceAll('_',' ').replace(/\b\w/g,letter=>letter.toUpperCase()):'Channel';
}

function xvondCustomerChannelStatusMarkup(agentId){
    const channels=(portalOverview?.channels||[]).filter(item=>Number(item.agent_id)===Number(agentId));
    if(!channels.length){
        return `
            <div class="xvond-agent-channels" style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(148,163,184,.25)">
                <strong>Customer Channels</strong>
                <p class="muted" style="margin:6px 0 0">No customer channel is assigned to this AI Employee yet.</p>
            </div>
        `;
    }
    return `
        <div class="xvond-agent-channels" style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(148,163,184,.25)">
            <strong>Customer Channels</strong>
            <p class="muted" style="margin:6px 0 0">The same employee identity, knowledge and allowed actions are used across these channels.</p>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:9px">
                ${channels.map(channel=>`<span style="display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;border:1px solid rgba(148,163,184,.28);font-size:13px;font-weight:700"><span style="width:8px;height:8px;border-radius:50%;background:${channel.enabled?'#16a34a':'#94a3b8'}"></span>${safe(xvondCustomerChannelLabel(channel.type))} · ${channel.enabled?'Live':'Inactive'}</span>`).join('')}
            </div>
        </div>
    `;
}

function xvondDecorateCustomerAgentsWithChannels(){
    const cards=Array.from(document.querySelectorAll('#agents-list .agent'));
    (agents||[]).forEach((agent,index)=>{
        const card=cards[index];
        if(!card||card.querySelector('.xvond-agent-channels'))return;
        card.insertAdjacentHTML('beforeend',xvondCustomerChannelStatusMarkup(agent.id));
    });
}

if(typeof loadAgents==='function'){
    const xvondChannelStatusOriginalLoadAgents=loadAgents;
    loadAgents=async function(...args){
        const result=await xvondChannelStatusOriginalLoadAgents(...args);
        xvondDecorateCustomerAgentsWithChannels();
        return result;
    };
}
