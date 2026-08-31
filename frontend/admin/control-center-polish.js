const xvondPolish={customerQuery:'',customerChannel:'all',conversationMode:'all',conversationChannel:'all',notificationType:'all',notificationSeverity:'all',analyticsComparison:null};

function xpChannelState(channel){
  if(!channel)return {label:'Not connected',kind:'bad'};
  if(channel.enabled)return {label:'Active',kind:'good'};
  if(channel.configured)return {label:'Configured',kind:'neutral'};
  return {label:'Needs setup',kind:'bad'};
}
function xpPercent(used,limit){
  const l=Number(limit||0),u=Number(used||0);if(!l)return 0;return Math.max(0,Math.min(100,(u/l)*100));
}
function xpDelta(current,previous,suffix=''){
  const c=Number(current||0),p=Number(previous||0);
  if(!p)return c?`+100% vs previous`:'No change';
  const d=((c-p)/p)*100;return `${d>=0?'+':''}${d.toFixed(0)}% vs previous${suffix}`;
}
function xpNeedsAttention(){
  const d=xvondWorkspace.data||{},items=[];
  const activeServices=(d.billingServices||[]).filter(x=>x.status==='active');
  for(const s of activeServices){
    for(const [metric,row] of Object.entries(s.usage||{})){
      const limit=Number(row.limit||0),used=Number(row.used||0);
      if(limit>0&&used>=limit)items.push({kind:'bad',title:`${s.service_name||s.service_code}: ${metric} limit exceeded`,body:`${used} / ${limit} · renews ${wsDate(s.current_period_end)}`,tab:'billing'});
      else if(limit>0&&used/limit>=0.8)items.push({kind:'neutral',title:`${s.service_name||s.service_code}: ${metric} at ${Math.round((used/limit)*100)}%`,body:`${used} / ${limit}`,tab:'billing'});
    }
  }
  for(const x of (d.channels||[])){
    if(x.configured&&!x.enabled)items.push({kind:'neutral',title:`${wsAgentName(x.agent_id)}: ${x.channel_type} configured but inactive`,body:'Channel is not currently serving customers.',tab:'channels'});
  }
  const pending=(d.handoffs||[]).filter(x=>['pending','in_progress'].includes(String(x.status||x.mode||'').toLowerCase())||x.mode==='human');
  if(pending.length)items.push({kind:'bad',title:`${pending.length} human handoff${pending.length===1?'':'s'} need attention`,body:'Customers are waiting for a human response.',tab:'conversations'});
  if((d.unresolved||[]).length)items.push({kind:'bad',title:`${d.unresolved.length} external operation${d.unresolved.length===1?'':'s'} unresolved`,body:'Verify the external system outcome before closing.',tab:'operations'});
  const failures=(d.usage?.usage||[]).filter(x=>x.status==='failed');
  if(failures.length)items.push({kind:'neutral',title:`${failures.length} recent AI request failure${failures.length===1?'':'s'}`,body:'Review runtime logs and provider status.',tab:'usage'});
  return items.slice(0,8);
}
function xpAttentionHtml(){
  const items=xpNeedsAttention();
  return `<div class="workspace-panel" id="xvond-needs-attention"><div class="workspace-panel-head"><div><h3>Needs Attention</h3><p>Only issues that require an action from the company or Xvond team.</p></div>${wsPill(items.length?`${items.length} open`:'All clear',items.length?'neutral':'good')}</div>${items.length?`<div class="operation-list">${items.map(x=>`<div class="request-card"><div class="request-card-head"><div><strong>${f(x.title)}</strong><div class="meta">${f(x.body)}</div></div>${wsPill(x.kind==='bad'?'Action needed':'Review',x.kind)}</div><button class="table-button" onclick="switchWorkspaceTab('${x.tab}')">Open</button></div>`).join('')}</div>`:wsEmpty('Nothing needs attention','Active services, channels and operations look healthy.')}</div>`;
}

const _xpRenderCompanyControlCenter=renderCompanyControlCenter;
renderCompanyControlCenter=function(){
  _xpRenderCompanyControlCenter();
  if(xvondWorkspace.tab==='overview'){
    const content=document.getElementById('workspace-content');
    if(content&&!document.getElementById('xvond-needs-attention'))content.insertAdjacentHTML('afterbegin',xpAttentionHtml());
  }
  if(xvondWorkspace.tab==='agents')xpPatchEmployeeChannelCounts();
};
function xpPatchEmployeeChannelCounts(){
  const cards=[...document.querySelectorAll('#workspace-content .employee-card')],rows=xvondWorkspace.data?.agentMeta||[],channels=xvondWorkspace.data?.channels||[];
  cards.forEach((card,index)=>{
    const agent=rows[index]?.agent;if(!agent)return;
    const active=channels.filter(x=>+x.agent_id===+agent.id&&x.enabled===true).length;
    const stat=[...card.querySelectorAll('.employee-stats > div')].find(x=>/Channels/i.test(x.textContent||''));
    if(stat)stat.innerHTML=`<strong>${active}</strong><span>Active Channel${active===1?'':'s'}</span>`;
    const flow=card.querySelector('.employee-flow-label');
    if(flow){
      const all=channels.filter(x=>+x.agent_id===+agent.id);
      const labels=['website','whatsapp','voice'].map(type=>{const s=xpChannelState(all.find(x=>x.channel_type===type));return `${type[0].toUpperCase()+type.slice(1)}: ${s.label}`});
      flow.insertAdjacentHTML('afterend',`<div class="meta" style="margin-top:8px">${labels.map(f).join(' · ')}</div>`);
    }
  });
}

renderBillingTab=function(){
  const d=xvondWorkspace.data,services=d.billingServices||[],plans=(d.plans||[]).filter(x=>x.enabled),serviceCodes=[...new Set(plans.map(x=>x.service_code))];
  return `<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Service Billing</h3><p>Plan status, renewal date and real usage against each limit.</p></div><button class="primary-button" onclick="openWorkspaceServiceForm()">+ Assign Service</button></div>${services.length?`<div class="integration-grid">${services.map(s=>{const limits=Object.entries(s.usage||{}),exceeded=limits.some(([,r])=>Number(r.limit||0)>0&&Number(r.used||0)>=Number(r.limit||0));return `<div class="integration-card"><div class="integration-card-head"><div><h4>${f(s.service_name||s.service_code)}</h4><div class="meta">${f(s.plan?.name||'No plan')} · ${f(s.plan?.tier||'')} · ${f(s.plan?.currency||'')} ${f(s.plan?.monthly_price||0)}</div></div>${wsPill(exceeded?'Limit exceeded':s.status,exceeded?'bad':s.status==='active'?'good':s.status==='expired'?'bad':'neutral')}</div><div class="meta">Period: ${wsDate(s.current_period_start)} → ${wsDate(s.current_period_end)}</div><div class="info-stack">${limits.map(([metric,row])=>{const limit=Number(row.limit||0),used=Number(row.used||0),pct=xpPercent(used,limit),state=limit&&used>=limit?'Limit exceeded':limit&&pct>=80?'Near limit':'';return `<div style="display:block"><div style="display:flex;justify-content:space-between;gap:12px"><span>${f(metric)}</span><strong>${f(row.used)} / ${limit?f(row.limit):'∞'}${state?` · ${f(state)}`:''}</strong></div>${limit?`<div style="height:6px;background:#e5e7eb;border-radius:999px;overflow:hidden;margin-top:7px"><div style="height:100%;width:${pct}% ;background:currentColor"></div></div>`:''}</div>`}).join('')}</div><div class="workspace-inline-actions"><button class="table-button" onclick="openWorkspaceServiceForm('${s.service_code}')">Change Plan</button>${s.status==='active'?`<button class="table-button" onclick="setWorkspaceServiceStatus('${s.service_code}','paused')">Pause</button>`:`<button class="table-button" onclick="setWorkspaceServiceStatus('${s.service_code}','active')">Activate</button>`}${s.status!=='cancelled'?`<button class="table-button" onclick="setWorkspaceServiceStatus('${s.service_code}','cancelled')">Cancel</button>`:''}</div></div>`}).join('')}</div>`:wsEmpty('No services assigned')}${serviceCodes.length?`<div class="workspace-panel-head"><div><h3>Available Service Plans</h3><p>${plans.length} enabled plans across ${serviceCodes.length} services.</p></div></div>`:''}</div>`;
};

function xpSetConversationFilter(name,value){xvondPolish[name]=value;renderCompanyControlCenter()}
renderConversationsTab=function(){
  const d=xvondWorkspace.data,sessions=new Map((d.handoffs||[]).map(x=>[+x.conversation_id,x]));
  const channels=[...new Set((d.conversations||[]).map(x=>sessions.get(+x.id)?.channel||x.channel_type).filter(Boolean))];
  const items=(d.conversations||[]).filter(x=>{const s=sessions.get(+x.id),mode=s?.mode==='human'||['pending','in_progress'].includes(String(s?.status||'').toLowerCase())?'human':'ai',channel=s?.channel||x.channel_type||'internal';return (xvondPolish.conversationMode==='all'||mode===xvondPolish.conversationMode)&&(xvondPolish.conversationChannel==='all'||channel===xvondPolish.conversationChannel)});
  return `<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Conversations</h3><p>Central inbox across channels, with AI and human handoff filtering.</p></div><div class="workspace-inline-actions"><select onchange="xpSetConversationFilter('conversationMode',this.value)"><option value="all">All modes</option><option value="ai" ${xvondPolish.conversationMode==='ai'?'selected':''}>AI</option><option value="human" ${xvondPolish.conversationMode==='human'?'selected':''}>Human / Handoff</option></select><select onchange="xpSetConversationFilter('conversationChannel',this.value)"><option value="all">All channels</option>${channels.map(x=>`<option value="${f(x)}" ${xvondPolish.conversationChannel===x?'selected':''}>${f(x)}</option>`).join('')}</select></div></div>${items.length?`<div class="table-wrap"><table><thead><tr><th>Conversation</th><th>AI Employee</th><th>Mode</th><th>Channel</th><th>Created</th><th></th></tr></thead><tbody>${items.map(x=>{const s=sessions.get(+x.id),human=s?.mode==='human'||['pending','in_progress'].includes(String(s?.status||'').toLowerCase()),channel=s?.channel||x.channel_type||'—';return `<tr><td><strong>#${x.id}</strong><div class="meta">${f(x.title||'Conversation')}</div></td><td>${f(wsAgentName(x.agent_id))}</td><td>${wsPill(human?'Human / Handoff':'AI',human?'bad':'good')}</td><td>${f(channel)}</td><td>${wsDate(x.created_at)}</td><td><button class="table-button" onclick="openHumanConversation(${d.view.company.id},${x.agent_id},${x.id})">Open</button></td></tr>`}).join('')}</tbody></table></div>`:wsEmpty('No conversations match these filters')}</div>`;
};

function xpSetCustomerFilter(name,value){xvondPolish[name]=value;renderCompanyControlCenter()}
renderCustomersTab=function(){
  const all=xvondCustomerOps.customers?.customers||[],query=String(xvondPolish.customerQuery||'').toLowerCase(),channels=[...new Set(all.map(x=>x.channel).filter(Boolean))];
  const items=all.filter(x=>{const text=[x.name,x.phone,x.email,x.external_contact_id,(x.tags||[]).join(' ')].join(' ').toLowerCase();return (!query||text.includes(query))&&(xvondPolish.customerChannel==='all'||x.channel===xvondPolish.customerChannel)});
  const totalBookings=items.reduce((n,x)=>n+Number(x.metrics?.bookings||0),0),totalOrders=items.reduce((n,x)=>n+Number(x.metrics?.orders||0),0),totalLeads=items.reduce((n,x)=>n+Number(x.metrics?.leads||0),0);
  return `<div class="workspace-metrics compact">${coMetric('Customers',items.length,items.length!==all.length?`${all.length} total`:'')}${coMetric('Bookings',totalBookings)}${coMetric('Orders',totalOrders)}${coMetric('Leads',totalLeads)}</div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Customer 360</h3><p>Searchable customer history across conversations and operations.</p></div><div class="workspace-inline-actions"><input value="${f(xvondPolish.customerQuery)}" oninput="xpSetCustomerFilter('customerQuery',this.value)" placeholder="Search name, phone, email, tag"><select onchange="xpSetCustomerFilter('customerChannel',this.value)"><option value="all">All sources</option>${channels.map(x=>`<option value="${f(x)}" ${xvondPolish.customerChannel===x?'selected':''}>${f(x)}</option>`).join('')}</select><button class="table-button" onclick="refreshCustomerOps()">Refresh</button></div></div>${items.length?`<div class="operation-list">${items.map(x=>`<div class="request-card"><div class="request-card-head"><div><strong>${f(x.name||x.phone||x.email||x.external_contact_id||`Customer #${x.id}`)}</strong><div class="meta">${f(x.phone||x.email||x.external_contact_id||'No contact detail')} · Source: ${f(x.channel||'multi-channel')} · Last contact ${wsDate(x.last_seen_at)}</div></div>${wsPill((x.tags||[])[0]||'Customer','neutral')}</div><div class="customer-metric-line">Bookings ${Number(x.metrics?.bookings||0)} · Orders ${Number(x.metrics?.orders||0)} · Leads ${Number(x.metrics?.leads||0)} · Conversations ${Number(x.metrics?.conversations||0)}</div>${x.notes?`<div class="request-summary">${f(x.notes)}</div>`:''}<div class="workspace-inline-actions"><button class="table-button" onclick="openCustomer360(${x.id})">Open 360</button><button class="table-button" onclick="editCustomer360(${x.id})">Edit</button></div></div>`).join('')}</div>`:wsEmpty('No customers match these filters','Try another search or source filter.')}</div>`;
};

function xpSetNotificationFilter(name,value){xvondPolish[name]=value;renderCompanyControlCenter()}
renderNotificationsTab=function(){
  const d=xvondCustomerOps.notifications||{events:[],unread:0,preferences:{}},p=d.preferences||{},all=d.events||[],types=[...new Set(all.map(x=>x.event_type))];
  const items=all.filter(x=>(xvondPolish.notificationType==='all'||x.event_type===xvondPolish.notificationType)&&(xvondPolish.notificationSeverity==='all'||x.severity===xvondPolish.notificationSeverity));
  return `<div class="workspace-metrics compact">${coMetric('Unread',d.unread)}${coMetric('Visible',items.length,`${all.length} total`)}${coMetric('Delivery','Dashboard','External delivery not connected')}</div><div class="workspace-grid two-col"><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Notification Center</h3><p>Bookings, orders, leads, handoffs and system attention.</p></div><div class="workspace-inline-actions"><select onchange="xpSetNotificationFilter('notificationType',this.value)"><option value="all">All types</option>${types.map(x=>`<option value="${f(x)}" ${xvondPolish.notificationType===x?'selected':''}>${f(x.replaceAll('_',' '))}</option>`).join('')}</select><select onchange="xpSetNotificationFilter('notificationSeverity',this.value)"><option value="all">All severity</option><option value="info" ${xvondPolish.notificationSeverity==='info'?'selected':''}>Info</option><option value="warning" ${xvondPolish.notificationSeverity==='warning'?'selected':''}>Warning</option><option value="critical" ${xvondPolish.notificationSeverity==='critical'?'selected':''}>Critical</option></select><button class="table-button" onclick="markAllNotificationsRead()">Mark all read</button></div></div>${items.length?`<div class="operation-list">${items.map(x=>`<div class="request-card ${x.read?'':'notification-unread'}"><div class="request-card-head"><div><strong>${f(x.title)}</strong><div class="meta">${f(x.event_type.replaceAll('_',' '))} · ${wsDate(x.created_at)}</div></div>${wsPill(x.severity,x.severity==='critical'?'bad':x.severity==='warning'?'neutral':'good')}</div>${x.message?`<div class="request-summary">${f(x.message)}</div>`:''}</div>`).join('')}</div>`:wsEmpty('No notifications match these filters')}</div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Notification Rules</h3><p>Dashboard notifications are live. Email, WhatsApp and Webhook delivery remain unavailable until connected.</p></div></div>${notificationPreferenceForm(p)}</div></div>`;
};

const _xpNotificationPreferenceForm=notificationPreferenceForm;
notificationPreferenceForm=function(p){
  const html=_xpNotificationPreferenceForm({...p,destinations:['dashboard']});
  return html.replace(/<label><input type="checkbox" class="co-destination" value="email"[^<]*<\/label>/g,'<label title="Not connected"><input type="checkbox" disabled> Email — Not connected</label>').replace(/<label><input type="checkbox" class="co-destination" value="whatsapp"[^<]*<\/label>/g,'<label title="Not connected"><input type="checkbox" disabled> WhatsApp — Not connected</label>').replace(/<label><input type="checkbox" class="co-destination" value="webhook"[^<]*<\/label>/g,'<label title="Not connected"><input type="checkbox" disabled> Webhook — Not connected</label>');
};

loadBusinessAnalyticsOps=async function(days=30){
  const safe=Math.max(1,Math.min(Number(days)||30,365));
  xvondCustomerOps.analytics=await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/analytics?days=${safe}`);
  xvondPolish.analyticsComparison=null;
  if(safe<365){
    const expanded=await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/analytics?days=${Math.min(safe*2,365)}`),cutoff=new Date(Date.now()-safe*86400000);
    const prev=(expanded.daily||[]).filter(x=>new Date(x.date)<cutoff).reduce((a,x)=>{a.conversations+=Number(x.conversations||0);a.bookings+=Number(x.bookings||0);a.orders+=Number(x.orders||0);a.leads+=Number(x.leads||0);return a},{conversations:0,bookings:0,orders:0,leads:0});
    prev.conversion_rate=prev.conversations?((prev.bookings+prev.orders+prev.leads)/prev.conversations)*100:0;
    xvondPolish.analyticsComparison=prev;
  }
};
renderBusinessAnalyticsTab=function(){
  const d=xvondCustomerOps.analytics||{kpis:{},channels:[],agents:[],daily:[]},k=d.kpis||{},p=xvondPolish.analyticsComparison;
  const small=(key,val)=>p?xpDelta(val,p[key]):'';
  return `<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Business Analytics</h3><p>Operational results with previous-period comparison.</p></div><select onchange="changeBusinessAnalyticsRange(this.value)"><option value="7" ${d.days===7?'selected':''}>7 days</option><option value="30" ${d.days===30?'selected':''}>30 days</option><option value="90" ${d.days===90?'selected':''}>90 days</option><option value="365" ${d.days===365?'selected':''}>365 days</option></select></div><div class="workspace-metrics">${coMetric('Conversations',k.conversations,small('conversations',k.conversations))}${coMetric('Bookings',k.bookings,small('bookings',k.bookings))}${coMetric('Orders',k.orders,small('orders',k.orders))}${coMetric('Leads',k.leads,small('leads',k.leads))}${coMetric('Conversion',`${Number(k.conversion_rate||0).toFixed(1)}%`,p?xpDelta(k.conversion_rate,p.conversion_rate):'')}${coMetric('Human handoff',`${Number(k.handoff_rate||0).toFixed(1)}%`)}${coMetric('AI Requests',k.ai_requests)}${coMetric('AI Cost',Number(k.provider_cost||0).toFixed(3))}</div></div><div class="workspace-grid two-col"><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Channels</h3><p>Conversation volume by source.</p></div></div>${(d.channels||[]).map(x=>`<div class="readiness-row"><span>${f(x.channel)}</span><strong>${x.conversations}</strong></div>`).join('')||wsEmpty('No channel activity')}</div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>AI Employee Performance</h3><p>Conversation load by employee.</p></div></div>${(d.agents||[]).map(x=>`<div class="readiness-row"><span>${f(x.name)}</span><strong>${x.conversations}</strong></div>`).join('')||wsEmpty('No employee activity')}</div></div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Daily Activity</h3></div></div>${(d.daily||[]).length?`<table><thead><tr><th>Date</th><th>Conversations</th><th>Bookings</th><th>Orders</th><th>Leads</th></tr></thead><tbody>${d.daily.map(x=>`<tr><td>${f(x.date)}</td><td>${x.conversations}</td><td>${x.bookings}</td><td>${x.orders}</td><td>${x.leads}</td></tr>`).join('')}</tbody></table>`:wsEmpty('No activity in this period')}</div>`;
};
