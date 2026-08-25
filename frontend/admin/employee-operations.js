async function openBusinessOperations(companyId,agentId){
  try{
    const [bookings,orders,leads]=await Promise.all([
      api(`/admin/business/bookings?company_id=${companyId}`),
      api(`/admin/business/orders?company_id=${companyId}`),
      api(`/admin/business/leads?company_id=${companyId}`)
    ]);
    const b=(bookings||[]).filter(x=>+x.agent_id===+agentId);
    const o=(orders||[]).filter(x=>+x.agent_id===+agentId);
    const l=(leads||[]).filter(x=>+x.agent_id===+agentId);
    openModal("Operations",`<div class="cards" style="margin-bottom:14px"><div class="card"><span>Bookings</span><strong>${b.length}</strong></div><div class="card"><span>Orders</span><strong>${o.length}</strong></div><div class="card"><span>Leads</span><strong>${l.length}</strong></div></div>
    <h3>Bookings</h3>${b.length?b.map(x=>`<div class="agent-card" style="margin-bottom:8px"><strong>#${x.id} · ${f(x.service||"")}</strong><div class="meta">${f(x.customer_name||"")} · ${f(x.phone||"")}</div><div class="meta">${f(x.date||"")} ${f(x.time||"")} · ${f(x.status)}</div><div class="agent-actions">${operationStatusButtons("booking",x.id,x.status,companyId,agentId)}</div></div>`).join(""):`<p>No bookings yet.</p>`}
    <h3 style="margin-top:18px">Orders</h3>${o.length?o.map(x=>`<div class="agent-card" style="margin-bottom:8px"><strong>#${x.id} · ${f(x.customer_name||"Customer")}</strong><div class="meta">${f(x.phone||"")} · ${f(x.status)}</div><div class="meta">${f(formatOrderItems(x.items||[]))}</div>${x.delivery_address?`<div class="meta">Delivery: ${f(x.delivery_address)}</div>`:""}<div class="agent-actions">${operationStatusButtons("order",x.id,x.status,companyId,agentId)}</div></div>`).join(""):`<p>No orders yet.</p>`}
    <h3 style="margin-top:18px">Leads</h3>${l.length?l.map(x=>`<div class="agent-card" style="margin-bottom:8px"><strong>#${x.id} · ${f(x.name||"Lead")}</strong><div class="meta">${f(x.phone||x.email||"")} · ${f(x.status)}</div><div class="meta">${f(x.interest||"")}</div><div class="agent-actions">${operationStatusButtons("lead",x.id,x.status,companyId,agentId)}</div></div>`).join(""):`<p>No leads yet.</p>`}`)
  }catch(e){alert(e.message)}
}
function formatOrderItems(items){return items.map(x=>`${x.quantity||1}× ${x.name||"Item"}${x.variant?` (${x.variant})`:""}`).join(" · ")}
function operationStatusButtons(type,id,current,c,a){
 const map={booking:["confirmed","completed","cancelled","no_show"],order:["new","confirmed","processing","completed","cancelled"],lead:["new","contacted","qualified","won","lost","closed"]};
 return (map[type]||[]).filter(s=>s!==current).slice(0,4).map(s=>`<button class="table-button" onclick="setOperationStatus('${type}',${id},'${s}',${c},${a})">${s.replaceAll("_"," ")}</button>`).join("")
}
async function setOperationStatus(type,id,status,c,a){try{const plural=type==="booking"?"bookings":type==="order"?"orders":"leads";await api(`/admin/business/${plural}/${id}/status/${status}`,{method:"PATCH"});await openBusinessOperations(c,a)}catch(e){alert(e.message)}}

const xvondBaseOpenSimpleCompany=openSimpleCompany;
openSimpleCompany=async function(companyId){
  await xvondBaseOpenSimpleCompany(companyId);
  try{
    const data=await api(`/admin/company-view/${companyId}`);
    const cards=[...document.querySelectorAll("#company-detail .agent-card")];
    (data.agents||[]).forEach((agent,index)=>{
      const actions=cards[index]&&cards[index].querySelector(".agent-actions");
      if(actions&&!actions.querySelector(".xvond-operations-button")){
        const button=document.createElement("button");button.className="table-button xvond-operations-button";button.textContent="Operations";button.onclick=()=>openBusinessOperations(companyId,agent.id);actions.insertBefore(button,actions.firstChild)
      }
    })
  }catch(_e){}
};
window.openCompany=openSimpleCompany;
