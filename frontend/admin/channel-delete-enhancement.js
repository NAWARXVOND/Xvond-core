function xvondInjectChannelDeleteButtons(){
  if(!xvondWorkspace?.data||xvondWorkspace.tab!=='channels')return;
  const d=xvondWorkspace.data;
  const employeeSections=Array.from(document.querySelectorAll('#workspace-content .channel-employee'));
  (d.agentMeta||[]).forEach((row,index)=>{
    const section=employeeSections[index];
    if(!section)return;
    const cards=Array.from(section.querySelectorAll('.channel-card'));
    const channels=(d.channels||[]).filter(x=>Number(x.agent_id)===Number(row.agent.id));
    for(const card of cards){
      if(card.querySelector('.xvond-delete-channel'))continue;
      const name=(card.querySelector('.channel-name')?.textContent||'').trim().toLowerCase();
      const type=name.includes('whatsapp')?'whatsapp':name.includes('website')?'website':null;
      if(!type)continue;
      const channel=channels.find(x=>x.channel_type===type);
      if(!channel)continue;
      const actions=card.querySelector('.agent-actions')||card;
      const button=document.createElement('button');
      button.type='button';
      button.className='danger-link xvond-delete-channel';
      button.textContent='Delete Channel';
      button.addEventListener('click',()=>deleteWorkspaceChannel(channel.id,type==='whatsapp'?'WhatsApp':'Website Chat'));
      actions.appendChild(button);
    }
  });
}

async function deleteWorkspaceChannel(channelId,channelLabel){
  const label=channelLabel||'channel';
  if(!confirm(`Permanently delete ${label} from this AI employee?\n\nThis removes the channel and its saved Xvond connection. For WhatsApp, it does not delete the phone number from Meta.`))return;
  try{
    await api(`/admin/channels/${channelId}`,{method:'DELETE'});
    await loadCompanyControlCenter(xvondWorkspace.companyId,'channels');
  }catch(e){
    alert(e.message||'Failed to delete channel');
  }
}

if(typeof renderCompanyControlCenter==='function'){
  const xvondOriginalRenderCompanyControlCenter=renderCompanyControlCenter;
  renderCompanyControlCenter=function(...args){
    const result=xvondOriginalRenderCompanyControlCenter(...args);
    xvondInjectChannelDeleteButtons();
    return result;
  };
}
