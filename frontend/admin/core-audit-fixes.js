function xaNumber(value){
  const raw=String(value??'0').trim();
  const n=Number(raw);
  if(!Number.isFinite(n))return raw||'0';
  return Number.isInteger(n)?n.toLocaleString():n.toLocaleString(undefined,{maximumFractionDigits:3});
}
function xaMetricState(metric,row){
  const limit=Number(row?.limit||0),used=Number(row?.used||0);
  if(!limit)return {label:'',kind:'neutral',pct:0};
  const pct=Math.max(0,Math.min(100,(used/limit)*100));
  const capacity=['agents','channels'].includes(String(metric).toLowerCase());
  if(used>limit)return {label:'Exceeded',kind:'bad',pct};
  if(used===limit)return {label:capacity?'Capacity full':'Limit reached',kind:capacity?'neutral':'bad',pct};
  if(pct>=80)return {label:'Near limit',kind:'neutral',pct};
  return {label:'',kind:'neutral',pct};
}
function xaServiceBlockingState(service){
  for(const [metric,row] of Object.entries(service.usage||{})){
    const state=xaMetricState(metric,row);
    if(!['agents','channels'].includes(String(metric).toLowerCase())&&state.kind==='bad')return state.label;
  }
  return '';
}

renderBillingTab=function(){
  const d=xvondWorkspace.data,services=d.billingServices||[],plans=(d.plans||[]).filter(x=>x.enabled);
  const assigned=new Set(services.map(x=>x.service_code));
  const unassigned=[...new Set(plans.map(x=>x.service_code))].filter(code=>!assigned.has(code));
  return `<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Service Billing</h3><p>One active subscription per service. Change plan or renew the current billing period explicitly.</p></div>${unassigned.length?`<button class="primary-button" onclick="openWorkspaceServiceForm()">+ Assign Service</button>`:''}</div>${services.length?`<div class="integration-grid">${services.map(s=>{const blocking=xaServiceBlockingState(s),limits=Object.entries(s.usage||{});return `<div class="integration-card"><div class="integration-card-head"><div><h4>${f(s.service_name||s.service_code)}</h4><div class="meta">${f(s.plan?.name||'No plan')} · ${f(s.plan?.tier||'')} · ${f(s.plan?.currency||'')} ${f(xaNumber(s.plan?.monthly_price||0))}</div></div>${wsPill(blocking||s.status,blocking?'bad':s.status==='active'?'good':s.status==='expired'?'bad':'neutral')}</div><div class="meta">Current period: ${wsDate(s.current_period_start)} → ${wsDate(s.current_period_end)}</div><div class="info-stack">${limits.map(([metric,row])=>{const state=xaMetricState(metric,row),limit=Number(row.limit||0);return `<div style="display:block"><div style="display:flex;justify-content:space-between;gap:12px"><span>${f(metric)}</span><strong>${f(xaNumber(row.used))} / ${limit?f(xaNumber(row.limit)):'∞'}${state.label?` · ${f(state.label)}`:''}</strong></div>${limit?`<div style="height:6px;background:#e5e7eb;border-radius:999px;overflow:hidden;margin-top:7px"><div style="height:100%;width:${state.pct}%;background:currentColor"></div></div>`:''}</div>`}).join('')}</div><div class="workspace-inline-actions"><button class="table-button" onclick="openWorkspaceServiceForm('${s.service_code}')">Change Plan</button><button class="table-button" onclick="renewWorkspaceService('${s.service_code}')">Renew</button>${s.status==='active'?`<button class="table-button" onclick="setWorkspaceServiceStatus('${s.service_code}','paused')">Pause</button>`:`<button class="table-button" onclick="setWorkspaceServiceStatus('${s.service_code}','active')">Activate</button>`}${s.status!=='cancelled'?`<button class="table-button" onclick="setWorkspaceServiceStatus('${s.service_code}','cancelled')">Cancel</button>`:''}</div></div>`}).join('')}</div>`:wsEmpty('No services assigned')}${plans.length?`<div class="workspace-panel-head"><div><h3>Service Plans</h3><p>Plans are alternatives for each service, not simultaneous packages. A company can have only one subscription per service.</p></div></div>`:''}</div>`;
};

openWorkspaceServiceForm=function(serviceCode=null){
  const d=xvondWorkspace.data,plans=(d.plans||[]).filter(x=>x.enabled),assigned=new Set((d.billingServices||[]).map(x=>x.service_code));
  const codes=[...new Set(plans.map(x=>x.service_code))].filter(code=>serviceCode||!assigned.has(code));
  const selected=serviceCode||codes[0]||'';
  if(!selected){alert('All available services are already assigned. Use Change Plan on the existing service.');return;}
  const current=(d.billingServices||[]).find(x=>x.service_code===selected);
  openModal(current?'Change Service Plan':'Assign Service Plan',`<div class="form-group"><label>Service</label><select id="wb-service" ${serviceCode?'disabled':''} onchange="renderWorkspaceServicePlans()">${codes.map(code=>wsOption(code,selected,code)).join('')}</select></div><div class="form-group"><label>Plan</label><select id="wb-plan"></select></div><div class="source-of-truth-box"><strong>${current?'Plan change':'New subscription'}</strong><div>${current?'Changing to a different plan starts the new plan immediately with a new monthly usage period. Selecting the current plan does not reset usage.':'Only one subscription can exist for this service.'}</div></div><button class="modal-submit" onclick="saveWorkspaceServicePlan()">${current?'Change Plan':'Assign Service'}</button>`);
  renderWorkspaceServicePlans();
};

saveWorkspaceServicePlan=async function(){
  const service=document.getElementById('wb-service').value,plan_id=Number(document.getElementById('wb-plan').value);
  const current=(xvondWorkspace.data.billingServices||[]).find(x=>x.service_code===service);
  if(current&&Number(current.plan?.id)===plan_id){closeModal();return;}
  try{
    await api(`/admin/service-billing/companies/${xvondWorkspace.companyId}/services/${service}`,{method:'PUT',body:JSON.stringify({plan_id,renew:false})});
    closeModal();await loadCompanyControlCenter(xvondWorkspace.companyId,'billing');
  }catch(e){alert(e.message)}
};

async function renewWorkspaceService(service){
  const current=(xvondWorkspace.data.billingServices||[]).find(x=>x.service_code===service);
  if(!current)return;
  if(!confirm(`Renew ${current.service_name||service} now? This starts a new monthly period and resets period usage.`))return;
  try{
    await api(`/admin/service-billing/companies/${xvondWorkspace.companyId}/services/${service}/renew`,{method:'POST',body:'{}'});
    await loadCompanyControlCenter(xvondWorkspace.companyId,'billing');
  }catch(e){alert(e.message)}
}
