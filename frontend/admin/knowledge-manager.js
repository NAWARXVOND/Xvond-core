const KNOWLEDGE_CATEGORIES=[
  ["general","General Information"],
  ["services_prices","Services & Prices"],
  ["menu","Menu"],
  ["products","Products"],
  ["faq","FAQ"],
  ["policies","Policies"],
  ["branches","Branches & Locations"],
  ["hours","Working Hours"],
  ["delivery_payment","Delivery & Payment"],
  ["booking_rules","Booking Rules"],
  ["order_rules","Order Rules"],
  ["custom","Custom Information"]
];
function knowledgeCategoryOptions(selected="custom"){return KNOWLEDGE_CATEGORIES.map(([v,l])=>`<option value="${v}" ${v===selected?"selected":""}>${l}</option>`).join("")}
async function openKnowledgeManager(companyId,agentId){
  simpleCompanyId=+companyId;
  try{
    const r=await api(`/admin/ai-employees/companies/${companyId}/${agentId}/knowledge`);
    const items=r.items||[];
    openModal("Knowledge",`<div class="section-header"><div><p>Everything this AI employee is allowed to know about the business.</p></div><div class="agent-actions"><button class="table-button" onclick="openKnowledgeEditor(${companyId},${agentId})">+ Add Information</button><button class="table-button" onclick="openPDFKnowledge(${companyId},${agentId})">+ Add PDF</button></div></div><div style="margin-top:14px">${items.length?items.map(x=>`<div class="agent-card" style="margin-bottom:10px"><div class="section-header"><div><strong>${f(x.title)}</strong><div class="meta">${f(x.category)} · ${x.characters} chars · ${x.enabled?"Active":"Disabled"}</div></div><div class="agent-actions">${x.protected?`<span class="meta">Managed in Edit</span>`:`<button class="table-button" onclick="openKnowledgeEditor(${companyId},${agentId},${x.id})">Edit</button><button class="table-button" onclick="toggleKnowledgeItem(${companyId},${agentId},${x.id})">${x.enabled?"Disable":"Enable"}</button><button class="table-button" onclick="deleteKnowledgeItem(${companyId},${agentId},${x.id})">Delete</button>`}</div></div><div class="meta" style="white-space:pre-wrap;margin-top:8px">${f(x.preview)}</div></div>`).join(""):`<p>No knowledge has been added yet.</p>`}</div>`)
  }catch(e){alert(e.message)}
}
async function openKnowledgeEditor(companyId,agentId,documentId=null){
  let d={title:"",category:"general",content:"",enabled:true};
  if(documentId){try{d=await api(`/admin/ai-employees/companies/${companyId}/${agentId}/knowledge/${documentId}`)}catch(e){alert(e.message);return}}
  openModal(documentId?"Edit Knowledge":"Add Knowledge",`<div class="form-group"><label>Category</label><select id="km-category">${knowledgeCategoryOptions(d.category||"custom")}</select></div><div class="form-group"><label>Title</label><input id="km-title" value="${f(d.title)}" placeholder="e.g. Hair Services and Prices"></div><div class="form-group"><label>Information</label><textarea id="km-content" style="min-height:280px" placeholder="Enter exact business information. Prices, names, conditions and details should match the real business.">${f(d.content)}</textarea></div><button class="modal-submit" onclick="saveKnowledgeItem(${companyId},${agentId},${documentId||"null"})">${documentId?"Save Changes":"Add to Knowledge"}</button>`)
}
async function saveKnowledgeItem(companyId,agentId,documentId){
  const title=document.getElementById("km-title").value.trim(),content=document.getElementById("km-content").value.trim(),category=document.getElementById("km-category").value;
  if(!title||!content){alert("Title and information are required.");return}
  try{
    const path=documentId?`/admin/ai-employees/companies/${companyId}/${agentId}/knowledge/${documentId}`:`/admin/ai-employees/companies/${companyId}/${agentId}/knowledge`;
    await api(path,{method:documentId?"PUT":"POST",body:JSON.stringify({title,category,content,enabled:true})});
    await openKnowledgeManager(companyId,agentId)
  }catch(e){alert(e.message)}
}
async function toggleKnowledgeItem(companyId,agentId,documentId){try{await api(`/admin/ai-employees/companies/${companyId}/${agentId}/knowledge/${documentId}/toggle`,{method:"PATCH"});await openKnowledgeManager(companyId,agentId)}catch(e){alert(e.message)}}
async function deleteKnowledgeItem(companyId,agentId,documentId){if(!confirm("Delete this knowledge item permanently?"))return;try{await api(`/admin/ai-employees/companies/${companyId}/${agentId}/knowledge/${documentId}`,{method:"DELETE"});await openKnowledgeManager(companyId,agentId)}catch(e){alert(e.message)}}
