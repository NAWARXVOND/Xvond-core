function capabilityModeOptions(selected=""){
  const value=selected==="xvond_internal"?"xvond_internal":"";
  return `<option value="" ${value===""?"selected":""}>Not enabled — transfer requests to human</option><option value="xvond_internal" ${value==="xvond_internal"?"selected":""}>Xvond Internal — execute and save automatically</option>`
}

function employeeForm(d={},edit=false){
  return `<div class="form-group"><label>Employee Name</label><input id="simple-employee-name" value="${f(d.name||"WhatsApp AI Employee")}"></div>
  <div class="form-group"><label>Business Name</label><input id="simple-business-name" value="${f(d.business_name)}"></div>
  <div class="form-group"><label>Business Type</label><select id="simple-business-type">${businessTypeOptions(d.business_type||"")}</select></div>
  <div class="form-group"><label>Business Description</label><textarea id="simple-business-description">${f(d.business_description)}</textarea></div>
  <div class="form-group"><label>Working Hours</label><input id="simple-working-hours" value="${f(d.working_hours)}"></div>
  <div class="form-group"><label>Reply Language</label><select id="simple-language"><option value="auto">Automatic</option><option value="ar">Arabic</option><option value="en">English</option><option value="ar_en">Arabic & English</option></select></div>
  <div class="form-group"><label>Business Information</label><textarea id="simple-business-info">${f(d.business_information)}</textarea><small>General facts only. Put services, prices, menu, policies and FAQs in Knowledge so they stay structured and maintainable.</small></div>
  <div class="form-group"><label>Website</label><input id="simple-website" value="${f(d.website)}"></div>
  <div class="form-group"><label>Booking</label><select id="simple-booking-system">${capabilityModeOptions(d.booking_system||"")}</select><small>Xvond Internal creates real booking records and checks availability. If disabled, booking requests are transferred to a human.</small></div>
  <div class="form-group"><label>Orders</label><select id="simple-order-system">${capabilityModeOptions(d.order_system||"")}</select><small>Xvond Internal creates real order records. Requested items must exist in Knowledge.</small></div>
  <div class="form-group"><label>Special Instructions</label><textarea id="simple-employee-instructions">${f(d.instructions)}</textarea></div>
  <button class="modal-submit" onclick="${edit?`saveAIEmployeeSettings(${d.agent_id})`:`createSimpleAIEmployee()`}">${edit?"Save Changes":"Create WhatsApp AI"}</button>`
}

function collectEmployee(){
  const value=id=>document.getElementById(id).value.trim();
  return {
    channel:"whatsapp",
    name:value("simple-employee-name"),
    business_name:value("simple-business-name"),
    business_type:value("simple-business-type"),
    business_description:value("simple-business-description")||null,
    working_hours:value("simple-working-hours")||null,
    reply_language:document.getElementById("simple-language").value,
    business_information:value("simple-business-info")||null,
    website:value("simple-website")||null,
    booking_system:value("simple-booking-system")||null,
    order_system:value("simple-order-system")||null,
    instructions:value("simple-employee-instructions")||null
  }
}
