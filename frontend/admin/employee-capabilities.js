function businessTypeOptions(selected=""){
  const types=["Catering / Events","Salon / Beauty","Restaurant / Cafe","Hotel / Hospitality","Clinic / Medical Center","Dental Clinic","Pharmacy","Retail Store","E-commerce","Real Estate","Travel / Tourism","Professional Services","Education / Training","Gym / Fitness","Automotive","Home Services","Maintenance / Contracting","Logistics / Delivery","Technology / Software","Marketing / Media","Financial / Accounting Services","Legal Services","Other"];
  return `<option value="">Select business type</option>`+types.map(t=>`<option value="${f(t)}" ${t===selected?"selected":""}>${f(t)}</option>`).join("")
}

function employeeForm(d={},edit=false){
  return `<p style="margin-top:0">Configure only the employee identity and conversation behavior here. Business facts belong in Knowledge; real business operations belong in Operations Setup.</p>
  <div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="${f(d.name||"AI Employee")}"><small>Internal/display name for this employee. It does not replace the business identity.</small></div>
  <div class="form-group"><label>Business Name</label><input id="simple-business-name" value="${f(d.business_name)}"><small>The verified business identity the employee represents.</small></div>
  <div class="form-group"><label>Business Type</label><select id="simple-business-type">${businessTypeOptions(d.business_type||"")}</select><small>This selects the best starting template only. You can add, remove or change any operation later.</small></div>
  <div class="form-group"><label>Reply Language</label><select id="simple-language"><option value="auto">Automatic — match customer</option><option value="ar">Arabic</option><option value="en">English</option><option value="ar_en">Arabic & English</option></select></div>
  <div class="form-group"><label>Conversation Style</label><select id="simple-conversation-style"><option value="professional_friendly">Professional & Friendly</option><option value="professional">Professional</option><option value="warm">Warm & Conversational</option><option value="concise">Concise</option></select><small>Controls tone only. It never changes business facts.</small></div>
  <div class="form-group"><label>Greeting</label><textarea id="simple-greeting" placeholder="Leave empty for a natural automatic greeting">${f(d.greeting)}</textarea><small>Optional. If empty, Xvond greets naturally using the Business Name and customer language.</small></div>
  <div class="form-group"><label>Special Instructions</label><textarea id="simple-employee-instructions" placeholder="Behavior rules that are unique to this employee">${f(d.instructions)}</textarea><small>Behavior only. Put services, prices, hours, policies, menu and other facts once in Knowledge.</small></div>
  <div style="padding:12px;border:1px solid #e5e7eb;border-radius:10px;margin:12px 0"><strong>Single source of truth</strong><div class="meta" style="margin-top:6px">Knowledge: everything the employee knows about the business.</div><div class="meta">Operations Setup: everything the employee can actually do and where it executes.</div><div class="meta">Channels: Website Chat, WhatsApp and future communication surfaces only.</div></div>
  <button class="modal-submit" onclick="${edit?`saveAIEmployeeSettings(${d.agent_id})`:`createSimpleAIEmployee()`}">${edit?"Save Profile":"Create AI Employee"}</button>`
}

function collectEmployee(){
  const value=id=>document.getElementById(id)?.value.trim()||"";
  return {
    name:value("simple-employee-name"),
    business_name:value("simple-business-name"),
    business_type:value("simple-business-type")||null,
    reply_language:document.getElementById("simple-language")?.value||"auto",
    conversation_style:document.getElementById("simple-conversation-style")?.value||"professional_friendly",
    greeting:value("simple-greeting")||null,
    instructions:value("simple-employee-instructions")||null
  }
}

async function openEditAIEmployee(c,a){try{simpleCompanyId=Number(c);const d=await api(`/admin/ai-employee-profile/companies/${c}/${a}`);d.agent_id=a;openModal("AI Employee Profile",employeeForm(d,true));document.getElementById("simple-language").value=d.reply_language||"auto";document.getElementById("simple-conversation-style").value=d.conversation_style||"professional_friendly"}catch(e){alert(e.message)}}
async function saveAIEmployeeSettings(a){try{const payload=collectEmployee();await api(`/admin/ai-employee-profile/companies/${simpleCompanyId}/${a}`,{method:"PUT",body:JSON.stringify(payload)});closeModal();await openSimpleCompany(simpleCompanyId)}catch(e){alert(e.message)}}
async function createSimpleAIEmployee(){try{const payload=collectEmployee();await api(`/admin/ai-employee-profile/companies/${simpleCompanyId}`,{method:"POST",body:JSON.stringify(payload)});closeModal();await openSimpleCompany(simpleCompanyId)}catch(e){alert(e.message)}}

async function createWhatsAppChannelForEmployee(companyId,agentId){try{const created=await api(`/admin/channels/agents/${agentId}`,{method:'POST',body:JSON.stringify({channel_type:'whatsapp',config:{}})});await openSimpleCompany(companyId);openWhatsAppSetup(agentId,created.id)}catch(e){alert(e.message)}}

const xvondChannelIndependentCompanyOpen=openSimpleCompany;
openSimpleCompany=async function(companyId){
  const result=await xvondChannelIndependentCompanyOpen(companyId);
  try{
    const [view,channelResult]=await Promise.all([api(`/admin/company-view/${companyId}`),api(`/admin/channels/companies/${companyId}`)]);
    const channels=channelResult.channels||[],cards=[...document.querySelectorAll('#company-detail .agent-card')];
    (view.agents||[]).forEach((agent,index)=>{
      if(channels.some(ch=>+ch.agent_id===+agent.id&&ch.channel_type==='whatsapp'))return;
      const card=cards[index];if(!card)return;
      const channelHeading=[...card.querySelectorAll('strong')].find(x=>x.textContent.trim()==='Channels');
      const area=channelHeading?.parentElement;if(!area||area.querySelector('.xvond-add-whatsapp'))return;
      const row=document.createElement('div');row.className='agent-actions xvond-add-whatsapp';row.innerHTML=`<button class="table-button">Connect WhatsApp</button>`;row.querySelector('button').onclick=()=>createWhatsAppChannelForEmployee(companyId,agent.id);area.appendChild(row);
    });
  }catch(_e){}
  return result;
};
window.openCompany=openSimpleCompany;
