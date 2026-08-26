(function(){
  function esc(v){return typeof f==='function'?f(v):String(v??'')}
  function currentVoiceChannels(){return (xvondWorkspace?.data?.channels||[]).filter(x=>x.channel_type==='voice')}
  function voiceChannel(agentId){return currentVoiceChannels().find(x=>+x.agent_id===+agentId)}

  function renderVoiceCards(){
    const agents=xvondWorkspace?.data?.view?.agents||[];
    if(!agents.length)return '';
    return `<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Voice Agent</h3><p>Use the same AI Employee with voice-specific language, dialect, tone and Vapi telephony.</p></div></div><div class="employee-grid">${agents.map(a=>{const ch=voiceChannel(a.id);const cfg=ch?.config||{};return `<div class="employee-card"><div class="employee-card-top"><div class="employee-avatar">☎</div><div><h4>${esc(a.name)}</h4><div class="meta">${ch?(ch.enabled?'Connected voice channel':'Voice channel created'):'No voice channel yet'}</div></div></div><div class="info-stack"><div><span>Provider</span><strong>${esc(cfg.provider||'vapi')}</strong></div><div><span>Phone</span><strong>${esc(cfg.phone_number||'Not connected')}</strong></div><div><span>Language</span><strong>${esc(cfg.language||'auto')}</strong></div><div><span>Dialect</span><strong>${esc(cfg.dialect||'auto')}</strong></div></div><div class="employee-actions">${ch?`<button onclick="openVoiceSettings(${a.id},${ch.id})">Voice Settings</button><button onclick="openVoiceNumberSetup(${ch.id})">Connect Live Number</button>`:`<button class="primary-button" onclick="createVoiceChannel(${a.id})">+ Voice Channel</button>`}</div></div>`}).join('')}</div></div>`;
  }

  const base=window.renderChannelsTab;
  if(typeof base==='function'){
    window.renderChannelsTab=function(){return base()+renderVoiceCards()}
  }

  window.createVoiceChannel=async function(agentId){
    try{
      await api(`/admin/channels/agents/${agentId}`,{method:'POST',body:JSON.stringify({channel_type:'voice',config:{provider:'vapi',language:'auto',dialect:'auto',tone:'professional_friendly',response_length:'concise',allow_interruption:true}})});
      await loadCompanyControlCenter(xvondWorkspace.companyId,'channels');
    }catch(e){alert(e.message)}
  };

  window.openVoiceSettings=function(agentId,channelId){
    const ch=(xvondWorkspace.data.channels||[]).find(x=>+x.id===+channelId);const c=ch?.config||{};
    openModal('Voice Settings',`<div class="modal-intro"><strong>Voice behavior</strong><p>These settings apply only to calls for this AI Employee.</p></div><div class="form-grid two"><div class="form-group"><label>Language</label><select id="voice-language"><option value="auto">Automatic</option><option value="ar">Arabic</option><option value="en">English</option></select></div><div class="form-group"><label>Dialect</label><select id="voice-dialect"><option value="auto">Automatic</option><option value="omani">Omani Arabic</option><option value="gulf">Gulf Arabic</option><option value="levantine">Levantine Arabic</option><option value="egyptian">Egyptian Arabic</option><option value="msa">Modern Standard Arabic</option></select></div></div><div class="form-group"><label>Tone</label><select id="voice-tone"><option value="professional_friendly">Professional & Friendly</option><option value="professional">Professional</option><option value="warm">Warm</option><option value="concise">Concise</option></select></div><div class="form-group"><label>Greeting</label><textarea id="voice-greeting">${esc(c.greeting_message||'')}</textarea></div><div class="form-group"><label>Voice ID</label><input id="voice-id" value="${esc(c.voice_id||'')}"></div><div class="form-group"><label>Voice-only instructions</label><textarea id="voice-instructions">${esc(c.channel_instructions||'')}</textarea></div><label><input id="voice-interrupt" type="checkbox" ${c.allow_interruption===false?'':'checked'}> Allow interruption while speaking</label><button class="modal-submit" onclick="saveVoiceSettings(${channelId})">Save Voice Settings</button>`);
    document.getElementById('voice-language').value=c.language||'auto';document.getElementById('voice-dialect').value=c.dialect||'auto';document.getElementById('voice-tone').value=c.tone||'professional_friendly';
  };

  window.saveVoiceSettings=async function(channelId){
    try{
      const config={provider:'vapi',language:document.getElementById('voice-language').value,dialect:document.getElementById('voice-dialect').value,tone:document.getElementById('voice-tone').value,response_length:'concise',greeting_message:document.getElementById('voice-greeting').value.trim()||null,voice_id:document.getElementById('voice-id').value.trim()||null,channel_instructions:document.getElementById('voice-instructions').value.trim()||null,allow_interruption:document.getElementById('voice-interrupt').checked};
      await api(`/admin/channels/${channelId}`,{method:'PUT',body:JSON.stringify({config})});closeModal();await loadCompanyControlCenter(xvondWorkspace.companyId,'channels');
    }catch(e){alert(e.message)}
  };

  window.openVoiceNumberSetup=async function(channelId){
    try{
      const result=await api('/admin/voice/vapi/phone-numbers');const items=result.phone_numbers||[];
      if(!items.length){alert('No real phone numbers are connected in the Vapi account yet. Import/connect one in Vapi first.');return}
      openModal('Connect Live Voice Number',`<div class="form-group"><label>Vapi Phone Number</label><select id="voice-phone-number">${items.map(x=>`<option value="${esc(x.id)}">${esc(x.name||x.number)}${x.number?` — ${esc(x.number)}`:''}</option>`).join('')}</select></div><button class="modal-submit" onclick="provisionVoiceNumber(${channelId})">Connect Number</button>`);
    }catch(e){alert(e.message)}
  };

  window.provisionVoiceNumber=async function(channelId){
    try{
      const phone_number_id=document.getElementById('voice-phone-number').value;await api(`/admin/voice/channels/${channelId}/vapi/provision`,{method:'POST',body:JSON.stringify({phone_number_id})});closeModal();await loadCompanyControlCenter(xvondWorkspace.companyId,'channels');
    }catch(e){alert(e.message)}
  };
})();
