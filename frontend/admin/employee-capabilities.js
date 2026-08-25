function employeeForm(d={},edit=false){
  return `<div class="modal-intro"><strong>AI Employee Profile</strong><p>Configure only this employee's identity and conversation behavior. Company facts come from Company Profile and Knowledge; real work comes from Operations Setup.</p></div>
  <div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="${f(d.name||"AI Employee")}"><small>A display/internal name such as Sara, Reservations Assistant or Customer Service.</small></div>
  <div class="form-grid two"><div class="form-group"><label>Reply Language</label><select id="simple-language"><option value="auto">Automatic — match customer</option><option value="ar">Arabic</option><option value="en">English</option><option value="ar_en">Arabic & English</option></select></div><div class="form-group"><label>Conversation Style</label><select id="simple-conversation-style"><option value="professional_friendly">Professional & Friendly</option><option value="professional">Professional</option><option value="warm">Warm & Conversational</option><option value="concise">Concise</option></select></div></div>
  <div class="form-group"><label>Greeting</label><textarea id="simple-greeting" placeholder="Leave empty for a natural automatic greeting">${f(d.greeting)}</textarea><small>Optional. The company name is inherited automatically from Company Profile.</small></div>
  <div class="form-group"><label>Special Instructions</label><textarea id="simple-employee-instructions" placeholder="Behavior rules unique to this employee">${f(d.instructions)}</textarea><small>Behavior only. Do not put services, prices, hours, branches or policies here.</small></div>
  <div class="source-of-truth-box"><strong>Single source of truth</strong><div>Company Profile & Business Information → company facts</div><div>Knowledge → documents, FAQs, menus and additional knowledge</div><div>Operations Setup → what this employee can actually execute</div><div>Channels → where customers communicate with this employee</div></div>
  <button class="modal-submit" onclick="${edit?`saveAIEmployeeSettings(${d.agent_id})`:`createSimpleAIEmployee()`}">${edit?"Save Employee":"Create AI Employee"}</button>`
}

function collectEmployee(){
  const value=id=>document.getElementById(id)?.value.trim()||"";
  return {
    name:value("simple-employee-name"),
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
