function renderChannelsTab(){
  const d=xvondWorkspace.data;
  return `<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Channels</h3><p>Configuration, local activation and provider connection are reported separately.</p></div></div>${d.agentMeta.length?d.agentMeta.map(row=>{
    const a=row.agent,web=wsChannel(a.id,'website'),wa=wsChannel(a.id,'whatsapp');
    const webState=wsChannelPresentation(web),waState=wsChannelPresentation(wa);
    return `<div class="channel-employee"><div class="channel-employee-head"><strong>${f(a.name)}</strong><span class="meta">Shared brain, knowledge and actions</span></div><div class="channel-grid"><div class="channel-card"><div><span class="channel-name">Website Chat</span>${wsPill(webState.label,webState.kind)}</div><p>${f(wsChannelDetail(web))}</p><div class="agent-actions"><button class="table-button" onclick="openWebsiteChannel(${d.view.company.id},${a.id})">${web?'Website Settings':'Connect Website'}</button>${web?`<button class="danger-link" onclick="deleteWorkspaceChannel(${web.id},'Website Chat')">Delete Channel</button>`:''}</div></div><div class="channel-card"><div><span class="channel-name">WhatsApp</span>${wsPill(waState.label,waState.kind)}</div><p>${f(wsChannelDetail(wa))}</p><div class="meta">Credentials: ${wa?.configured?'Configured':'Incomplete'} · Local state: ${wa?.enabled?'Active':'Inactive'}</div><div class="agent-actions">${wa?`<button class="table-button" onclick="openWhatsAppSetup(${a.id},${wa.id})">Settings</button>${wa.connected===true?'':`<button class="primary-button" onclick="openMetaWhatsAppConnect(${a.id})">Connect with Meta</button>`}${wa.configured?`<button class="table-button" onclick="setWorkspaceChannelStatus(${wa.id},${!wa.enabled})">${wa.enabled?'Deactivate':'Activate'}</button>`:''}<button class="danger-link" onclick="deleteWorkspaceChannel(${wa.id},'WhatsApp')">Delete Channel</button>`:`<button class="table-button" onclick="createWhatsAppChannelForEmployee(${d.view.company.id},${a.id})">Connect WhatsApp</button>`}</div></div></div></div>`;
  }).join(''):wsEmpty('Create an AI employee first')}</div>`;
}

async function deleteWorkspaceChannel(channelId, channelLabel){
  const label=channelLabel||'channel';
  if(!confirm(`Permanently delete ${label} from this AI employee?\n\nThis removes the channel and its saved Xvond connection. For WhatsApp, it does not delete the phone number from Meta.`))return;
  try{
    await api(`/admin/channels/${channelId}`,{method:'DELETE'});
    await loadCompanyControlCenter(xvondWorkspace.companyId,'channels');
  }catch(e){
    alert(e.message||'Failed to delete channel');
  }
}
