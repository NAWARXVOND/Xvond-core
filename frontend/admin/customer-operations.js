const xvondCustomerOps={customers:null,notifications:null,analytics:null};

function coEmpty(v){return v===null||v===undefined||v===''?'—':v}
function coMetric(label,value,small=''){return `<div class="metric-card"><span>${f(label)}</span><strong>${f(coEmpty(value))}</strong>${small?`<small>${f(small)}</small>`:''}</div>`}

const _xvondRenderWorkspaceTab=renderWorkspaceTab;
renderWorkspaceTab=function(){
  if(xvondWorkspace.tab==='customers')return renderCustomersTab();
  if(xvondWorkspace.tab==='notifications')return renderNotificationsTab();
  if(xvondWorkspace.tab==='business-analytics')return renderBusinessAnalyticsTab();
  return _xvondRenderWorkspaceTab();
};

const _xvondRenderCompanyControlCenter=renderCompanyControlCenter;
renderCompanyControlCenter=function(){
  _xvondRenderCompanyControlCenter();
  const tabs=document.querySelector('.workspace-tabs');
  if(!tabs)return;
  const additions=[['customers','Customers'],['notifications','Notifications'],['business-analytics','Analytics']];
  for(const [key,label] of additions){
    if(tabs.querySelector(`[data-customer-ops-tab="${key}"]`))continue;
    const button=document.createElement('button');
    button.className=`workspace-tab ${xvondWorkspace.tab===key?'active':''}`;
    button.dataset.customerOpsTab=key;
    button.textContent=label;
    button.onclick=()=>switchWorkspaceTab(key);
    tabs.appendChild(button);
  }
};

const _xvondSwitchWorkspaceTab=switchWorkspaceTab;
switchWorkspaceTab=async function(tab){
  if(tab==='customers')await loadCustomersOps();
  if(tab==='notifications')await loadNotificationOps();
  if(tab==='business-analytics')await loadBusinessAnalyticsOps();
  if(['customers','notifications','business-analytics'].includes(tab)){
    xvondWorkspace.tab=tab;renderCompanyControlCenter();return;
  }
  return _xvondSwitchWorkspaceTab(tab);
};

async function loadCustomersOps(){xvondCustomerOps.customers=await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/customers`)}
async function loadNotificationOps(){xvondCustomerOps.notifications=await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/notifications`)}
async function loadBusinessAnalyticsOps(days=30){xvondCustomerOps.analytics=await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/analytics?days=${Number(days)||30}`)}

function renderCustomersTab(){
  const items=xvondCustomerOps.customers?.customers||[];
  const totalBookings=items.reduce((n,x)=>n+Number(x.metrics?.bookings||0),0),totalOrders=items.reduce((n,x)=>n+Number(x.metrics?.orders||0),0),totalLeads=items.reduce((n,x)=>n+Number(x.metrics?.leads||0),0);
  return `<div class="workspace-metrics compact">${coMetric('Customers',items.length)}${coMetric('Bookings',totalBookings)}${coMetric('Orders',totalOrders)}${coMetric('Leads',totalLeads)}</div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Customer 360</h3><p>One customer record across conversations, bookings, orders and leads.</p></div><button class="table-button" onclick="refreshCustomerOps()">Refresh</button></div>${items.length?`<div class="operation-list">${items.map(x=>`<div class="request-card"><div class="request-card-head"><div><strong>${f(x.name||x.phone||x.email||x.external_contact_id||`Customer #${x.id}`)}</strong><div class="meta">${f(x.phone||x.email||x.external_contact_id||'No contact detail')} · ${f(x.channel||'multi-channel')} · Last seen ${wsDate(x.last_seen_at)}</div></div>${wsPill((x.tags||[])[0]||'Customer','neutral')}</div><div class="customer-metric-line">Bookings ${Number(x.metrics?.bookings||0)} · Orders ${Number(x.metrics?.orders||0)} · Leads ${Number(x.metrics?.leads||0)} · Conversations ${Number(x.metrics?.conversations||0)}</div>${x.notes?`<div class="request-summary">${f(x.notes)}</div>`:''}<div class="workspace-inline-actions"><button class="table-button" onclick="openCustomer360(${x.id})">Open 360</button><button class="table-button" onclick="editCustomer360(${x.id})">Edit</button></div></div>`).join('')}</div>`:wsEmpty('No customers yet','Customer records are created automatically from WhatsApp contacts, leads, bookings and orders.')}</div>`;
}
async function refreshCustomerOps(){await loadCustomersOps();renderCompanyControlCenter()}

async function openCustomer360(id){
  try{
    const d=await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/customers/${id}`),c=d.customer;
    openModal('Customer 360',`<div class="info-grid"><div><span>Name</span><strong>${f(coEmpty(c.name))}</strong></div><div><span>Phone</span><strong>${f(coEmpty(c.phone))}</strong></div><div><span>Email</span><strong>${f(coEmpty(c.email))}</strong></div><div><span>Channel</span><strong>${f(coEmpty(c.channel))}</strong></div><div class="span-2"><span>Tags</span><strong>${f((c.tags||[]).join(', ')||'—')}</strong></div><div class="span-2"><span>Notes</span><strong>${f(coEmpty(c.notes))}</strong></div></div><div class="workspace-metrics compact">${coMetric('Bookings',d.bookings.length)}${coMetric('Orders',d.orders.length)}${coMetric('Leads',d.leads.length)}${coMetric('Conversations',d.conversations.length)}</div><div class="source-of-truth-box"><strong>Recent activity</strong>${d.bookings.slice(0,5).map(x=>`<div>Booking · ${f(x.service||'Service')} · ${f(x.status)}</div>`).join('')}${d.orders.slice(0,5).map(x=>`<div>Order #${x.id} · ${f(x.status)}</div>`).join('')}${d.leads.slice(0,5).map(x=>`<div>Lead · ${f(x.interest||'General')} · ${f(x.status)}</div>`).join('')}${d.conversations.slice(0,5).map(x=>`<div>Conversation #${x.id} · ${f(x.channel||'internal')} · ${wsDate(x.created_at)}</div>`).join('')}</div>`);
  }catch(e){alert(e.message)}
}
async function editCustomer360(id){
  const x=(xvondCustomerOps.customers?.customers||[]).find(v=>+v.id===+id);if(!x)return;
  openModal('Edit Customer',`<div class="form-grid two"><div class="form-group"><label>Name</label><input id="co-name" value="${f(x.name||'')}"></div><div class="form-group"><label>Phone</label><input id="co-phone" value="${f(x.phone||'')}"></div></div><div class="form-group"><label>Email</label><input id="co-email" value="${f(x.email||'')}"></div><div class="form-group"><label>Tags</label><input id="co-tags" value="${f((x.tags||[]).join(', '))}" placeholder="VIP, Repeat customer"></div><div class="form-group"><label>Notes</label><textarea id="co-notes">${f(x.notes||'')}</textarea></div><button class="modal-submit" onclick="saveCustomer360(${x.id})">Save Customer</button>`);
}
async function saveCustomer360(id){try{const value=n=>document.getElementById(n)?.value?.trim()||null;await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/customers/${id}`,{method:'PUT',body:JSON.stringify({name:value('co-name'),phone:value('co-phone'),email:value('co-email'),tags:String(value('co-tags')||'').split(',').map(x=>x.trim()).filter(Boolean),notes:value('co-notes')})});closeModal();await refreshCustomerOps()}catch(e){alert(e.message)}}

function renderNotificationsTab(){
  const d=xvondCustomerOps.notifications||{events:[],unread:0,preferences:{}},p=d.preferences||{};
  return `<div class="workspace-metrics compact">${coMetric('Unread',d.unread)}${coMetric('Events',(d.events||[]).length)}${coMetric('Delivery',(p.destinations||[]).join(', ')||'Dashboard')}</div><div class="workspace-grid two-col"><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Notification Center</h3><p>Bookings, orders, leads, handoffs and system attention.</p></div><button class="table-button" onclick="markAllNotificationsRead()">Mark all read</button></div>${(d.events||[]).length?`<div class="operation-list">${d.events.map(x=>`<div class="request-card ${x.read?'':'notification-unread'}"><div class="request-card-head"><div><strong>${f(x.title)}</strong><div class="meta">${f(x.event_type.replaceAll('_',' '))} · ${wsDate(x.created_at)}</div></div>${wsPill(x.severity,x.severity==='critical'?'bad':x.severity==='warning'?'neutral':'good')}</div>${x.message?`<div class="request-summary">${f(x.message)}</div>`:''}</div>`).join('')}</div>`:wsEmpty('No notifications')}</div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Notification Rules</h3><p>Choose which events matter and where Xvond should route them.</p></div></div>${notificationPreferenceForm(p)}</div></div>`;
}
function notificationPreferenceForm(p){const events=[['booking_new','New booking'],['order_new','New order'],['lead_new','New lead'],['handoff_pending','Human handoff'],['operation_attention','Operation needs attention'],['ai_failure','AI failure']],dest=[['dashboard','Dashboard'],['email','Email'],['whatsapp','WhatsApp'],['webhook','Webhook']];const checked=new Set(p.event_types||[]),dests=new Set(p.destinations||[]);return `<label><input id="co-notify-enabled" type="checkbox" ${p.enabled!==false?'checked':''}> Notifications enabled</label><div class="source-of-truth-box"><strong>Events</strong>${events.map(([v,l])=>`<label><input type="checkbox" class="co-event" value="${v}" ${checked.has(v)?'checked':''}> ${l}</label>`).join('')}</div><div class="source-of-truth-box"><strong>Destinations</strong>${dest.map(([v,l])=>`<label><input type="checkbox" class="co-destination" value="${v}" ${dests.has(v)?'checked':''}> ${l}</label>`).join('')}</div><div class="form-group"><label>Email destination</label><input id="co-notify-email" value="${f(p.email||'')}"></div><div class="form-group"><label>WhatsApp destination</label><input id="co-notify-whatsapp" value="${f(p.whatsapp||'')}"></div><div class="form-group"><label>Webhook URL</label><input id="co-notify-webhook" value="${f(p.webhook_url||'')}"></div><button class="modal-submit" onclick="saveNotificationPreferences()">Save Notification Rules</button>`}
async function saveNotificationPreferences(){try{const list=s=>[...document.querySelectorAll(s)].filter(x=>x.checked).map(x=>x.value);await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/notification-preferences`,{method:'PUT',body:JSON.stringify({enabled:!!document.getElementById('co-notify-enabled')?.checked,event_types:list('.co-event'),destinations:list('.co-destination'),email:document.getElementById('co-notify-email')?.value?.trim()||null,whatsapp:document.getElementById('co-notify-whatsapp')?.value?.trim()||null,webhook_url:document.getElementById('co-notify-webhook')?.value?.trim()||null})});await loadNotificationOps();renderCompanyControlCenter()}catch(e){alert(e.message)}}
async function markAllNotificationsRead(){try{await api(`/admin/customer-operations/companies/${xvondWorkspace.companyId}/notifications/read-all`,{method:'POST',body:'{}'});await loadNotificationOps();renderCompanyControlCenter()}catch(e){alert(e.message)}}

function renderBusinessAnalyticsTab(){
  const d=xvondCustomerOps.analytics||{kpis:{},channels:[],agents:[],daily:[]},k=d.kpis||{};
  return `<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Business Analytics</h3><p>Operational results, not just AI token usage.</p></div><select onchange="changeBusinessAnalyticsRange(this.value)"><option value="7" ${d.days===7?'selected':''}>7 days</option><option value="30" ${d.days===30?'selected':''}>30 days</option><option value="90" ${d.days===90?'selected':''}>90 days</option><option value="365" ${d.days===365?'selected':''}>365 days</option></select></div><div class="workspace-metrics">${coMetric('Conversations',k.conversations)}${coMetric('Bookings',k.bookings)}${coMetric('Orders',k.orders)}${coMetric('Leads',k.leads)}${coMetric('Conversion',`${Number(k.conversion_rate||0).toFixed(1)}%`)}${coMetric('Human handoff',`${Number(k.handoff_rate||0).toFixed(1)}%`)}${coMetric('AI Requests',k.ai_requests)}${coMetric('AI Cost',Number(k.provider_cost||0).toFixed(3))}</div></div><div class="workspace-grid two-col"><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Channels</h3><p>Conversation volume by source.</p></div></div>${(d.channels||[]).map(x=>`<div class="readiness-row"><span>${f(x.channel)}</span><strong>${x.conversations}</strong></div>`).join('')||wsEmpty('No channel activity')}</div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>AI Employee Performance</h3><p>Conversation load by employee.</p></div></div>${(d.agents||[]).map(x=>`<div class="readiness-row"><span>${f(x.name)}</span><strong>${x.conversations}</strong></div>`).join('')||wsEmpty('No employee activity')}</div></div><div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Daily Activity</h3></div></div>${(d.daily||[]).length?`<table><thead><tr><th>Date</th><th>Conversations</th><th>Bookings</th><th>Orders</th><th>Leads</th></tr></thead><tbody>${d.daily.map(x=>`<tr><td>${f(x.date)}</td><td>${x.conversations}</td><td>${x.bookings}</td><td>${x.orders}</td><td>${x.leads}</td></tr>`).join('')}</tbody></table>`:wsEmpty('No activity in this period')}</div>`;
}
async function changeBusinessAnalyticsRange(days){await loadBusinessAnalyticsOps(days);renderCompanyControlCenter()}
