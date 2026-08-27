const API="";
let token=null;
let companiesCache=[];
let agentTestConversationId=null;

// Remove browser-readable bearer tokens left by older Xvond builds.
localStorage.removeItem("xvond_admin_token");
localStorage.removeItem("xvond_admin_user");

function escapeAdmin(value){return String(value??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
function escapeProduction(value){return escapeAdmin(value)}
function authHeaders(){return {"Content-Type":"application/json"}}
function clearAdminSession(){token=null;document.getElementById("app")?.classList.add("hidden");document.getElementById("login-screen")?.classList.remove("hidden")}

async function api(url,options={}){
  const response=await fetch(API+url,{...options,credentials:"same-origin",headers:{...(options.headers||{}),"Content-Type":"application/json"}});
  let data={};try{data=await response.json()}catch(_e){}
  if(response.status===401){clearAdminSession();throw new Error("Authentication expired")}
  if(!response.ok){const detail=typeof data.detail==='string'?data.detail:(data.detail?.message||"Request failed");throw new Error(detail)}
  return data;
}

async function login(){
  const email=document.getElementById("login-email").value.trim(),password=document.getElementById("login-password").value,error=document.getElementById("login-error");error.textContent="";
  try{
    const data=await api("/auth/login",{method:"POST",body:JSON.stringify({email,password})});
    if(!["super_admin","xvond_admin"].includes(data.user?.role)){
      try{await api("/auth/logout",{method:"POST",body:"{}"})}catch(_e){}
      throw new Error("Xvond admin account required");
    }
    startApp(data.user);
  }catch(e){error.textContent=e.message}
}

async function logout(){try{await api("/auth/logout",{method:"POST",body:"{}"})}catch(_e){}finally{clearAdminSession()}}

function startApp(user={}){
  document.getElementById("login-screen").classList.add("hidden");document.getElementById("app").classList.remove("hidden");
  document.getElementById("current-user").textContent=user.email||"Xvond Admin";showPage("dashboard",document.querySelector('.nav-item'));
}

async function resumeAdminSession(){
  try{
    const user=await api("/users/me");
    if(!["super_admin","xvond_admin"].includes(user?.role)){clearAdminSession();return}
    startApp(user);
  }catch(_e){clearAdminSession()}
}

async function showPage(name,button=null){
  document.querySelectorAll(".page").forEach(item=>item.classList.add("hidden"));const page=document.getElementById(`page-${name}`);if(page)page.classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach(item=>item.classList.remove("active"));if(button)button.classList.add("active");
  document.getElementById("page-title").textContent=name==="companies"?"Companies":name==="company-detail"?"Company":"Dashboard";
  if(name==="dashboard")await loadDashboard();if(name==="companies")await loadCompanies();
}

async function loadDashboard(){
  try{const data=await api("/admin/dashboard/summary");const cards=[["Companies",data.companies],["Active Companies",data.active_companies],["Users",data.users],["AI Employees",data.agents],["Active Employees",data.active_agents],["Conversations",data.conversations],["AI Requests",data.ai_requests],["Tokens",data.total_tokens],["AI Provider Cost",data.provider_cost],["Active Services",data.active_subscriptions]];document.getElementById("dashboard-cards").innerHTML=cards.map(([label,value])=>`<div class="card"><div class="card-label">${escapeAdmin(label)}</div><div class="card-value">${value??0}</div></div>`).join("")}catch(e){console.error(e)}
}

async function loadCompanies(){
  try{const data=await api("/admin/companies");companiesCache=data.companies||[];document.getElementById("companies-table").innerHTML=companiesCache.map(company=>`<tr><td>${company.id}</td><td><strong>${escapeAdmin(company.name)}</strong></td><td><span class="status ${company.active?'status-active':'status-inactive'}">${company.active?'Active':'Inactive'}</span></td><td>${company.created_at?new Date(company.created_at).toLocaleDateString():''}</td><td><button class="table-button" onclick="openCompany(${company.id})">Open</button></td></tr>`).join("")}catch(e){alert(e.message)}
}

function openCreateCompany(){openModal("Create Company",`<div class="form-group"><label>Company Name</label><input id="company-name"></div><div class="form-group"><label>Owner Full Name</label><input id="owner-name"></div><div class="form-group"><label>Owner Email</label><input id="owner-email" type="email"></div><div class="form-group"><label>Owner Password</label><input id="owner-password" type="password"></div><button class="modal-submit" onclick="createCompany()">Create Company</button>`)}
async function createCompany(){try{const data=await api("/admin/companies",{method:"POST",body:JSON.stringify({name:document.getElementById("company-name").value.trim(),owner_full_name:document.getElementById("owner-name").value.trim(),owner_email:document.getElementById("owner-email").value.trim(),owner_password:document.getElementById("owner-password").value})});closeModal();await loadCompanies();await openCompany(data.company.id)}catch(e){alert(e.message)}}

function openAddAIEmployee(companyId){simpleCompanyId=Number(companyId);openModal("Create AI Employee",employeeForm({},false));const language=document.getElementById("simple-language"),style=document.getElementById("simple-conversation-style");if(language)language.value="auto";if(style)style.value="professional_friendly"}

function openModal(title,body){document.getElementById("modal-title").textContent=title;document.getElementById("modal-body").innerHTML=body;document.getElementById("modal").classList.remove("hidden")}
function closeModal(){document.getElementById("modal").classList.add("hidden")}

function openAgentTestChat(companyId,agentId){agentTestConversationId=null;openModal("Test AI Employee",`<div id="agent-test-transcript" class="agent-test-transcript"><p class="meta">Internal test conversation. Real provider usage is recorded.</p></div><div class="form-group"><label>Message</label><textarea id="agent-test-message" placeholder="Type a test message"></textarea></div><button id="agent-test-send" class="modal-submit" onclick="sendAgentTestMessage(${companyId},${agentId})">Send Message</button>`)}
async function sendAgentTestMessage(companyId,agentId){
  const input=document.getElementById("agent-test-message"),button=document.getElementById("agent-test-send"),transcript=document.getElementById("agent-test-transcript"),message=input.value.trim();if(!message){alert("Message is required.");return}button.disabled=true;button.textContent="Sending...";
  try{const result=await api(`/admin/companies/${companyId}/agents/${agentId}/test-chat`,{method:"POST",body:JSON.stringify({message,conversation_id:agentTestConversationId})});agentTestConversationId=result.conversation_id;transcript.innerHTML+=`<div class="test-message test-user"><strong>You</strong><div>${escapeAdmin(message)}</div></div><div class="test-message test-assistant"><strong>AI Employee</strong><div>${escapeAdmin(result.response?.content||"")}</div><small>${Number(result.usage?.total_tokens||0)} tokens · ${Number(result.usage?.latency_ms||0)} ms</small></div>`;input.value="";transcript.scrollTop=transcript.scrollHeight}catch(error){transcript.innerHTML+=`<div class="test-message test-error"><strong>Error</strong><div>${escapeAdmin(error.message)}</div></div>`}finally{button.disabled=false;button.textContent="Send Message"}
}

resumeAdminSession();
