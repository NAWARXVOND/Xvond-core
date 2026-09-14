(function installOperationalDashboard(){
  function n(value){const parsed=Number(value||0);return Number.isFinite(parsed)?parsed:0}
  function money(value){return n(value).toFixed(3)}
  function compact(value){return new Intl.NumberFormat(undefined,{notation:'compact',maximumFractionDigits:1}).format(n(value))}
  function dt(value){if(!value)return '—';try{return new Date(String(value).endsWith('Z')?value:`${value}Z`).toLocaleString()}catch(_e){return String(value)}}
  function attention(data){
    const a=data.attention||{};
    const rows=[
      ['Active companies without an active AI employee',a.active_companies_without_active_employee,'Production is enabled but no AI employee is enabled.','warn'],
      ['Active AI employees without an active channel',a.active_employees_without_active_channel,'The employee is enabled but has no enabled customer channel.','warn'],
      ['Failed AI requests in the last 24 hours',a.failed_ai_requests_24h,'Provider or runtime failures should be reviewed.','bad'],
      ['Active human handoffs',a.active_handoffs,'Conversations currently waiting for or controlled by a human.','warn'],
      ['Subscriptions expiring within 7 days',a.subscriptions_expiring_7d,'Active service subscriptions approaching period end.','warn'],
    ];
    const total=rows.reduce((sum,row)=>sum+n(row[1]),0);
    const badge=document.getElementById('dashboard-attention-count');if(badge)badge.textContent=String(total);
    const target=document.getElementById('dashboard-attention');
    if(target)target.innerHTML=total===0?'<div class="dashboard-empty-good">No operational alerts right now.</div>':rows.filter(row=>n(row[1])>0).map(([label,value,description,kind])=>`<div class="dashboard-attention-row"><div><strong>${escapeAdmin(label)}</strong><small>${escapeAdmin(description)}</small></div><div class="dashboard-attention-value ${kind}">${n(value)}</div></div>`).join('');
    return {total,critical:n(a.failed_ai_requests_24h)>0};
  }
  function activity(data){
    const a=data.last_24h||{},target=document.getElementById('dashboard-activity');if(!target)return;
    const items=[['AI requests',compact(a.ai_requests),`${n(a.failed_ai_requests)} failed`],['Tokens',compact(a.total_tokens),'input + output'],['Provider cost',money(a.provider_cost),'provider cost units'],['Average latency',`${Math.round(n(a.avg_latency_ms))} ms`,'AI request latency']];
    target.innerHTML=items.map(([label,value,meta])=>`<div class="dashboard-activity-item"><span>${escapeAdmin(label)}</span><strong>${escapeAdmin(value)}</strong><small>${escapeAdmin(meta)}</small></div>`).join('');
  }
  loadDashboard=async function loadOperationalDashboard(){
    const cards=document.getElementById('dashboard-cards'),health=document.getElementById('dashboard-health'),activityTarget=document.getElementById('dashboard-activity'),attentionTarget=document.getElementById('dashboard-attention');
    if(cards)cards.classList.add('dashboard-system-loading');
    if(health){health.className='dashboard-health loading';health.textContent='Loading platform health…'}
    try{
      const data=await api('/admin/dashboard/summary');
      const metrics=[['Companies',data.companies,`${n(data.active_companies)} active`],['AI Employees',data.agents,`${n(data.active_agents)} active · ${n(data.draft_agents)} draft`],['Channels',data.channels,`${n(data.active_channels)} active`],['Conversations',data.conversations,'all time'],['AI Requests',data.ai_requests,`${compact(data.last_24h?.ai_requests)} in 24h`],['Tokens',compact(data.total_tokens),`${compact(data.last_24h?.total_tokens)} in 24h`],['Provider Cost',money(data.provider_cost),`${money(data.last_24h?.provider_cost)} in 24h`],['Active Services',data.active_subscriptions,'current subscriptions']];
      if(cards)cards.innerHTML=metrics.map(([label,value,meta])=>`<div class="card"><div class="card-label">${escapeAdmin(label)}</div><div class="card-value">${value??0}</div><small>${escapeAdmin(meta)}</small></div>`).join('');
      const status=attention(data);activity(data);
      const generated=document.getElementById('dashboard-generated-at');if(generated)generated.textContent=`Updated ${dt(data.generated_at)}`;
      if(health){health.className=`dashboard-health ${status.critical?'critical':status.total?'attention':'healthy'}`;health.textContent=status.critical?'Provider/runtime failures detected in the last 24 hours.':status.total?`${status.total} operational item${status.total===1?'':'s'} need review.`:'Platform control-plane indicators are healthy.'}
    }catch(error){
      if(health){health.className='dashboard-health critical';health.textContent='Dashboard data could not be loaded.'}
      if(cards)cards.innerHTML=`<div class="dashboard-system-error">${escapeAdmin(error.message)}</div>`;
      if(activityTarget)activityTarget.innerHTML='';if(attentionTarget)attentionTarget.innerHTML='';
    }finally{if(cards)cards.classList.remove('dashboard-system-loading')}
  };
})();
