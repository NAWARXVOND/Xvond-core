function employeeForm(d={},edit=false){
  return `<div class="modal-intro"><strong>AI Employee Profile</strong><p>Configure this employee's identity and behavior. Company facts come from Company Profile and Knowledge; real work comes from Operations Setup.</p></div>
  <div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="${f(d.name||"AI Employee")}"><small>A display/internal name such as Sara, Reservations Assistant or Customer Service.</small></div>

  <div class="modal-intro"><strong>Language</strong><p>How this employee speaks with customers across every connected channel.</p></div>
  <div class="form-grid two"><div class="form-group"><label>Reply Language</label><select id="simple-language"><option value="auto">Automatic — match customer</option><option value="ar">Arabic</option><option value="en">English</option><option value="ar_en">Arabic & English</option></select></div><div class="form-group"><label>Dialect</label><select id="simple-dialect"><option value="auto">Automatic — match customer</option><option value="msa">Modern Standard Arabic (Fusha)</option><option value="omani">Omani Arabic</option><option value="gulf">Gulf Arabic</option><option value="saudi">Saudi Arabic</option><option value="emirati">Emirati Arabic</option><option value="levantine">Levantine / Shami Arabic</option><option value="egyptian">Egyptian Arabic</option></select></div></div>

  <div class="modal-intro"><strong>Behavior</strong><p>Simple global behavior. These settings follow the same employee on Website, WhatsApp, Voice and future channels.</p></div>
  <div class="form-grid two"><div class="form-group"><label>Tone</label><select id="simple-conversation-style"><option value="professional_friendly">Professional & Friendly</option><option value="professional">Professional</option><option value="warm">Warm & Conversational</option><option value="concise">Concise & Direct</option></select></div><div class="form-group"><label>Response Length</label><select id="simple-response-length"><option value="concise">Concise — recommended</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option></select></div></div>
  <div class="form-grid two"><div class="form-group"><label>When a request is unclear</label><select id="simple-clarification-style"><option value="smart">Smart — answer when clear, ask one question when needed</option><option value="ask_when_unclear">Ask one question before recommending</option><option value="direct_first">Give a useful answer first, then one follow-up</option></select></div><div class="form-group"><label>Personal / off-topic messages</label><select id="simple-off-topic"><option value="business_redirect">Business focused — recommended</option><option value="brief_friendly">Brief friendly reply, then return to business</option></select></div></div>
  <div class="source-of-truth-box"><strong>Business-focused behavior</strong><div>With the recommended setting, the employee does not analyze customer emotions or turn into a therapist/general assistant. It acknowledges briefly and returns naturally to its business role.</div></div>

  <div class="form-group"><label>Greeting</label><textarea id="simple-greeting" placeholder="Leave empty for a natural automatic greeting">${f(d.greeting)}</textarea><small>Optional. The company name is inherited automatically from Company Profile.</small></div>
  <div class="form-group"><label>Advanced Instructions</label><textarea id="simple-employee-instructions" placeholder="Optional rules unique to this employee">${f(d.instructions)}</textarea><small>Use this only for special behavior rules. Do not put services, prices, hours, branches or policies here.</small></div>
  <div class="source-of-truth-box"><strong>Single source of truth</strong><div>Company Profile & Business Information → company facts</div><div>Knowledge → documents, FAQs, menus and additional knowledge</div><div>Operations Setup → what this employee can actually execute</div><div>Channels → where customers communicate with this employee</div></div>
  <button class="modal-submit" onclick="${edit?`saveAIEmployeeSettings(${d.agent_id})`:`createSimpleAIEmployee()`}">${edit?"Save Employee":"Create AI Employee"}</button>`
}

function collectEmployee(){
  const value=id=>document.getElementById(id)?.value.trim()||"";
  return {
    name:value("simple-employee-name"),
    reply_language:document.getElementById("simple-language")?.value||"auto",
    dialect:document.getElementById("simple-dialect")?.value||"auto",
    conversation_style:document.getElementById("simple-conversation-style")?.value||"professional_friendly",
    response_length:document.getElementById("simple-response-length")?.value||"concise",
    clarification_style:document.getElementById("simple-clarification-style")?.value||"smart",
    off_topic_behavior:document.getElementById("simple-off-topic")?.value||"business_redirect",
    greeting:value("simple-greeting")||null,
    instructions:value("simple-employee-instructions")||null
  }
}

function applyEmployeeFormValues(d={}){
  const values={
    "simple-language":d.reply_language||"auto",
    "simple-dialect":d.dialect||"auto",
    "simple-conversation-style":d.conversation_style||"professional_friendly",
    "simple-response-length":d.response_length||"concise",
    "simple-clarification-style":d.clarification_style||"smart",
    "simple-off-topic":d.off_topic_behavior||"business_redirect"
  };
  for(const [id,value] of Object.entries(values)){
    const element=document.getElementById(id);
    if(element)element.value=value;
  }
}

async function openEditAIEmployee(c,a){try{simpleCompanyId=Number(c);const d=await api(`/admin/ai-employee-profile/companies/${c}/${a}`);d.agent_id=a;openModal("AI Employee Profile",employeeForm(d,true));applyEmployeeFormValues(d)}catch(e){alert(e.message)}}
async function saveAIEmployeeSettings(a){try{const payload=collectEmployee();await api(`/admin/ai-employee-profile/companies/${simpleCompanyId}/${a}`,{method:"PUT",body:JSON.stringify(payload)});closeModal();await openSimpleCompany(simpleCompanyId)}catch(e){alert(e.message)}}
async function createSimpleAIEmployee(){try{const payload=collectEmployee();await api(`/admin/ai-employee-profile/companies/${simpleCompanyId}`,{method:"POST",body:JSON.stringify(payload)});closeModal();await openSimpleCompany(simpleCompanyId)}catch(e){alert(e.message)}}

async function createWhatsAppChannelForEmployee(companyId,agentId){try{const created=await api(`/admin/channels/agents/${agentId}`,{method:'POST',body:JSON.stringify({channel_type:'whatsapp',config:{}})});await openSimpleCompany(companyId);openWhatsAppSetup(agentId,created.id)}catch(e){alert(e.message)}}