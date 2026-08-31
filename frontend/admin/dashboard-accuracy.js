(function(){
  function data(){return typeof xvondWorkspace!=='undefined'?(xvondWorkspace?.data||null):null}
  function metricCard(label){
    return [...document.querySelectorAll('.metric-card')].find(card=>card.querySelector('span')?.textContent?.trim()===label)||null;
  }
  function finite(v){const n=Number(v);return Number.isFinite(n)?n:0}
  function limitState(service){
    let reached=false,exceeded=false;
    for(const row of Object.values(service?.usage||{})){
      const limit=finite(row?.limit),used=finite(row?.used);
      if(limit<=0)continue;
      if(used>limit)exceeded=true;
      else if(used>=limit)reached=true;
    }
    return exceeded?'exceeded':reached?'reached':null;
  }

  function fixOverview(d){
    if(typeof xvondWorkspace==='undefined'||xvondWorkspace.tab!=='overview')return;
    const channels=d.channels||[];
    const active=channels.filter(x=>x.enabled===true).length;
    const configured=channels.filter(x=>x.configured===true).length;
    const card=metricCard('Channels');
    if(card){
      const strong=card.querySelector('strong'),small=card.querySelector('small');
      if(strong)strong.textContent=String(active);
      if(small)small.textContent=`${configured} configured · ${channels.length} created`;
    }
    const connected=channels.some(x=>x.enabled===true&&x.configured===true);
    for(const row of document.querySelectorAll('.readiness-row')){
      const spans=row.querySelectorAll('span');
      if(![...spans].some(x=>x.textContent?.trim()==='Connected channel'))continue;
      const dot=row.querySelector('.readiness-dot'),status=row.querySelector('strong');
      if(dot){dot.classList.toggle('ok',connected);dot.classList.toggle('missing',!connected)}
      if(status)status.textContent=connected?'Ready':'Needs setup';
    }
  }

  function fixEmployeeCards(d){
    if(typeof xvondWorkspace==='undefined'||xvondWorkspace.tab!=='agents')return;
    const cards=[...document.querySelectorAll('.employee-grid .employee-card')];
    (d.agentMeta||[]).forEach((row,index)=>{
      const card=cards[index];if(!card)return;
      const active=(d.channels||[]).filter(x=>+x.agent_id===+row.agent.id&&x.enabled===true).length;
      const stat=card.querySelector('.employee-stats > div:nth-child(3)');
      if(stat){
        const strong=stat.querySelector('strong'),label=stat.querySelector('span');
        if(strong)strong.textContent=String(active);
        if(label)label.textContent='Active Channels';
      }
    });
  }

  function fixBilling(d){
    if(typeof xvondWorkspace==='undefined'||xvondWorkspace.tab!=='billing')return;
    const cards=[...document.querySelectorAll('#workspace-content .integration-grid .integration-card')];
    (d.billingServices||[]).forEach((service,index)=>{
      const card=cards[index],state=limitState(service);if(!card||!state)return;
      const pill=card.querySelector('.workspace-pill');
      if(pill){
        pill.textContent=state==='exceeded'?'Limit exceeded':'Limit reached';
        pill.classList.remove('good','neutral');
        pill.classList.add('bad');
      }
      for(const row of card.querySelectorAll('.info-stack > div')){
        const strong=row.querySelector('strong');if(!strong)continue;
        const parts=strong.textContent.split('/').map(x=>x.trim());
        if(parts.length!==2||parts[1]==='∞')continue;
        const used=finite(parts[0]),limit=finite(parts[1]);
        if(limit>0&&used>=limit)strong.textContent+=used>limit?' · exceeded':' · reached';
      }
    });
  }

  function fixNotificationDestinations(){
    if(typeof xvondWorkspace==='undefined'||xvondWorkspace.tab!=='notifications')return;
    const boxes=[...document.querySelectorAll('.co-destination')];
    for(const input of boxes){
      if(input.value==='dashboard')continue;
      input.checked=false;input.disabled=true;
      const label=input.closest('label');
      if(label&&!label.textContent.includes('Not connected'))label.append(' — Not connected');
    }
    for(const id of ['co-notify-email','co-notify-whatsapp','co-notify-webhook']){
      const input=document.getElementById(id);if(input)input.disabled=true;
    }
    const rules=[...document.querySelectorAll('#workspace-content h3')].find(x=>x.textContent.trim()==='Notification Rules')?.closest('.workspace-panel');
    if(rules&&!rules.querySelector('.notification-delivery-note')){
      const note=document.createElement('div');note.className='workspace-empty notification-delivery-note';
      note.innerHTML='<strong>Dashboard delivery is active.</strong><p>Email, WhatsApp and Webhook delivery will be enabled only after their outbound delivery services are connected.</p>';
      rules.insertBefore(note,rules.querySelector('.source-of-truth-box'));
    }
  }

  function apply(){const d=data();if(!d)return;fixOverview(d);fixEmployeeCards(d);fixBilling(d);fixNotificationDestinations()}
  const base=renderCompanyControlCenter;
  if(typeof base==='function')renderCompanyControlCenter=function(){const result=base.apply(this,arguments);apply();return result};
})();
