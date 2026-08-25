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
  <div class="form-group"><label>Other Connected System</label><input id="simple-other-system" value="${f(d.other_system)}"></div>
  <div class="form-group"><label>Monthly Usage Limit</label><input id="simple-monthly-limit" type="number" min="1" value="${f(d.monthly_usage_limit)}"></div>
  <div class="form-group"><label>Special Instructions</label><textarea id="simple-employee-instructions">${f(d.instructions)}</textarea></div>
  <button class="modal-submit" onclick="${edit?`saveAIEmployeeSettings(${d.agent_id})`:`createSimpleAIEmployee()`}">${edit?"Save Changes":"Create WhatsApp AI"}</button>`
}
