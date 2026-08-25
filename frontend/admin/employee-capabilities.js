function employeeForm(d={},edit=false){
  return `<p style="margin-top:0">Configure only the employee identity and conversation behavior here. Business facts belong in Knowledge; bookings, orders and leads belong in Actions.</p>
  <div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="${f(d.name||"AI Employee")}"><small>Internal/display name for this employee. It does not replace the business identity.</small></div>
  <div class="form-group"><label>Business Name</label><input id="simple-business-name" value="${f(d.business_name)}"><small>The verified business identity the employee represents.</small></div>
  <div class="form-group"><label>Business Type</label><select id="simple-business-type">${businessTypeOptions(d.business_type||"")}</select></div>
  <div class="form-group"><label>Reply Language</label><select id="simple-language"><option value="auto">Automatic — match customer</option><option value="ar">Arabic</option><option value="en">English</option><option value="ar_en">Arabic & English</option></select></div>
  <div class="form-group"><label>Conversation Style</label><select id="simple-conversation-style"><option value="professional_friendly">Professional & Friendly</option><option value="professional">Professional</option><option value="warm">Warm & Conversational</option><option value="concise">Concise</option></select><small>Controls tone only. It never changes business facts.</small></div>
  <div class="form-group"><label>Greeting</label><textarea id="simple-greeting" placeholder="Leave empty for a natural automatic greeting">${f(d.greeting)}</textarea><small>Optional. If empty, Xvond greets naturally using the Business Name and customer language.</small></div>
  <div class="form-group"><label>Special Instructions</label><textarea id="simple-employee-instructions" placeholder="Behavior rules that are unique to this employee">${f(d.instructions)}</textarea><small>Behavior only. Do not put prices, hours, services, menu, policies or other business facts here — add those once in Knowledge.</small></div>
  <div style="padding:12px;border:1px solid #e5e7eb;border-radius:10px;margin:12px 0"><strong>Where do the other settings go?</strong><div class="meta" style="margin-top:6px">Knowledge: description, hours, website, services, prices, menu, products, branches, policies, FAQs and other business facts.</div><div class="meta">Actions: booking, orders/requests, leads, required customer details and execution mode.</div><div class="meta">Channels: Website Chat, WhatsApp and other delivery channels.</div></div>
  <button class="modal-submit" onclick="${edit?`saveAIEmployeeSettings(${d.agent_id})`:`createSimpleAIEmployee()`}">${edit?"Save Profile":"Create AI Employee"}</button>`
}

function collectEmployee(){
  const value=id=>document.getElementById(id)?.value.trim()||"";
  return {
    channel:"whatsapp",
    name:value("simple-employee-name"),
    business_name:value("simple-business-name"),
    business_type:value("simple-business-type"),
    reply_language:document.getElementById("simple-language")?.value||"auto",
    conversation_style:document.getElementById("simple-conversation-style")?.value||"professional_friendly",
    greeting:value("simple-greeting")||null,
    instructions:value("simple-employee-instructions")||null
  }
}
