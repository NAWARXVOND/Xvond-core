let simpleCompanyId=null;
function simpleEscape(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}
function f(v){return simpleEscape(v||"")}
function businessTypeOptions(selected=""){const types=["Salon / Beauty","Restaurant / Cafe","Retail Store","E-commerce","Clinic / Medical Center","Dental Clinic","Pharmacy","Real Estate","Hotel / Hospitality","Travel / Tourism","Professional Services","Education / Training","Gym / Fitness","Automotive","Home Services","Maintenance / Contracting","Logistics / Delivery","Technology / Software","Marketing / Media","Financial / Accounting Services","Legal Services","Other"];return `<option value="">Select business type</option>`+types.map(t=>`<option value="${f(t)}" ${t===selected?"selected":""}>${f(t)}</option>`).join("")}

// Shared helpers retained for the current Company Control Center.
// Company rendering and AI Employee profile forms live in company-control-center.js
// and employee-capabilities.js. Do not reintroduce company facts or fixed booking/order
// switches into the employee profile here.

async function setSimpleChannelStatus(c,id,en){try{await api(`/admin/channels/${id}`,{method:"PUT",body:JSON.stringify({enabled:en})});await openSimpleCompany(c)}catch(e){alert(e.message)}}

async function takeOverConversation(c,conversationId,a){try{await api(`/admin/handoff/companies/${c}/conversations/${conversationId}/take-over`,{method:"POST"});await openHumanTakeover(c,a)}catch(e){alert(e.message)}}
async function returnConversationToAI(c,conversationId,a){try{await api(`/admin/handoff/companies/${c}/conversations/${conversationId}/return-ai`,{method:"POST"});await openHumanTakeover(c,a)}catch(e){alert(e.message)}}

function openPDFKnowledge(c,a){simpleCompanyId=+c;openModal("Add PDF Knowledge",`<p>Upload a menu, price list, services catalog, scanned PDF or company document.</p><div class="form-group"><label>PDF File</label><input id="simple-pdf-file" type="file" accept="application/pdf,.pdf"></div><button class="modal-submit" onclick="uploadPDFKnowledge(${a})">Upload & Learn</button>`)}
async function uploadPDFKnowledge(a){const input=document.getElementById("simple-pdf-file"),file=input.files&&input.files[0];if(!file){alert("Choose a PDF file first.");return}const fd=new FormData();fd.append("file",file);try{const token=localStorage.getItem("xvond_admin_token")||localStorage.getItem("token");const res=await fetch(`/admin/ai-employees/companies/${simpleCompanyId}/${a}/knowledge/pdf`,{method:"POST",headers:token?{Authorization:`Bearer ${token}`}:{},body:fd});const data=await res.json().catch(()=>({}));if(!res.ok)throw new Error(data.detail||"PDF upload failed");await openKnowledgeManager(simpleCompanyId,a)}catch(e){alert(e.message)}}

async function openWhatsAppSetup(a,c){
  try{
    const result=await api(`/admin/channels/companies/${simpleCompanyId}`);
    const channel=(result.channels||[]).find(x=>+x.id===+c)||{};
    const cfg=channel.config||{};
    const secrets=new Set(channel.configured_secret_fields||[]);
    openModal("WhatsApp Settings",`<div class="modal-intro"><strong>Meta WhatsApp Business</strong><p>Connection credentials and WhatsApp-only conversation behavior. Leave an existing secret blank to keep it unchanged. Activation remains a separate readiness-gated step.</p></div>
    <div class="form-group"><label>Phone Number ID</label><input id="simple-wa-phone-id" value="${f(cfg.phone_number_id||'')}"></div>
    <div class="form-grid two"><div class="form-group"><label>Access Token</label><input id="simple-wa-access-token" type="password" placeholder="${secrets.has('access_token')?'Already configured — leave blank to keep':'Required'}"></div><div class="form-group"><label>Verify Token</label><input id="simple-wa-verify-token" type="password" placeholder="${secrets.has('verify_token')?'Already configured — leave blank to keep':'Required'}"></div></div>
    <div class="form-grid two"><div class="form-group"><label>App Secret</label><input id="simple-wa-app-secret" type="password" placeholder="${secrets.has('app_secret')?'Already configured — leave blank to keep':'Required'}"></div><div class="form-group"><label>Graph API Version</label><input id="simple-wa-version" value="${f(cfg.graph_api_version||'v23.0')}"></div></div>
    <div class="modal-intro"><strong>WhatsApp behavior</strong><p>These settings apply only to text conversations on WhatsApp.</p></div>
    <div class="form-grid two"><div class="form-group"><label>Language</label><select id="simple-wa-language"><option value="auto">Automatic</option><option value="ar">Arabic</option><option value="en">English</option></select></div><div class="form-group"><label>Dialect</label><select id="simple-wa-dialect"><option value="auto">Automatic</option><option value="omani">Omani Arabic</option><option value="gulf">Gulf Arabic</option><option value="levantine">Levantine Arabic</option><option value="egyptian">Egyptian Arabic</option><option value="msa">Modern Standard Arabic</option></select></div></div>
    <div class="form-grid two"><div class="form-group"><label>Tone</label><select id="simple-wa-tone"><option value="professional_friendly">Professional & Friendly</option><option value="professional">Professional</option><option value="warm">Warm</option><option value="concise">Concise</option></select></div><div class="form-group"><label>Response Length</label><select id="simple-wa-length"><option value="concise">Concise</option><option value="short">Short</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option></select></div></div>
    <div class="form-grid two"><div class="form-group"><label>Response Style</label><select id="simple-wa-style"><option value="conversational">Conversational</option><option value="professional">Professional</option><option value="direct">Direct</option></select></div><div class="form-group"><label>Emoji Style</label><select id="simple-wa-emoji"><option value="minimal">Minimal</option><option value="none">None</option><option value="natural">Natural</option></select></div></div>
    <div class="form-group"><label>WhatsApp-only Instructions</label><textarea id="simple-wa-instructions" placeholder="Behavior rules for WhatsApp only">${f(cfg.channel_instructions||'')}</textarea></div>
    <button class="modal-submit" onclick="saveSimpleWhatsApp(${c})">Save WhatsApp Settings</button>`);
    document.getElementById('simple-wa-language').value=cfg.language||'auto';
    document.getElementById('simple-wa-dialect').value=cfg.dialect||'auto';
    document.getElementById('simple-wa-tone').value=cfg.tone||'professional_friendly';
    document.getElementById('simple-wa-length').value=cfg.response_length||'concise';
    document.getElementById('simple-wa-style').value=cfg.response_style||'conversational';
    document.getElementById('simple-wa-emoji').value=cfg.emoji_style||'minimal';
  }catch(e){alert(e.message)}
}

async function saveSimpleWhatsApp(c){
  try{
    const value=id=>document.getElementById(id)?.value?.trim()||"";
    const payload={
      phone_number_id:value("simple-wa-phone-id")||null,
      access_token:value("simple-wa-access-token")||null,
      verify_token:value("simple-wa-verify-token")||null,
      app_secret:value("simple-wa-app-secret")||null,
      graph_api_version:value("simple-wa-version")||"v23.0",
      language:document.getElementById("simple-wa-language")?.value||"auto",
      dialect:document.getElementById("simple-wa-dialect")?.value||"auto",
      tone:document.getElementById("simple-wa-tone")?.value||"professional_friendly",
      response_style:document.getElementById("simple-wa-style")?.value||"conversational",
      response_length:document.getElementById("simple-wa-length")?.value||"concise",
      emoji_style:document.getElementById("simple-wa-emoji")?.value||"minimal",
      channel_instructions:value("simple-wa-instructions")||null
    };
    const result=await api(`/admin/channels/${c}/whatsapp-config`,{method:"PUT",body:JSON.stringify(payload)});
    closeModal();await openSimpleCompany(simpleCompanyId);
    if(result&&!result.ready&&result.blockers?.length)alert("WhatsApp saved. Before activation: "+result.blockers.join("; "));
  }catch(e){alert(e.message)}
}
