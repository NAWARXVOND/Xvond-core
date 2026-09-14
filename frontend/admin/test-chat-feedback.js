function adminChatDirection(text){
  const value=String(text||"");
  const arabic=(value.match(/[\u0600-\u06ff]/g)||[]).length;
  const latin=(value.match(/[A-Za-z]/g)||[]).length;
  return arabic>latin?"rtl":"ltr";
}

function adminChatCleanText(text){
  return String(text||"")
    .replace(/\*\*(.*?)\*\*/gs,"$1")
    .replace(/__(.*?)__/gs,"$1")
    .replace(/`([^`]+)`/g,"$1")
    .replace(/^#{1,6}\s+/gm,"")
    .trim();
}

function ensureAdminChatQualityStyles(){
  if(document.getElementById("xvond-admin-chat-quality"))return;
  const style=document.createElement("style");
  style.id="xvond-admin-chat-quality";
  style.textContent=`
    #agent-test-transcript{max-height:48vh;scroll-behavior:smooth;overflow-x:hidden}
    #agent-test-transcript .test-message{overflow:hidden;overflow-wrap:anywhere;word-break:normal;line-height:1.65}
    #agent-test-transcript .test-message>strong{display:block;margin-bottom:5px;direction:ltr;text-align:left;unicode-bidi:isolate}
    #agent-test-transcript .test-chat-body{white-space:pre-wrap;unicode-bidi:plaintext;overflow-wrap:anywhere;word-break:normal}
    #agent-test-transcript .test-chat-body[dir="rtl"]{text-align:right}
    #agent-test-transcript .test-chat-body[dir="ltr"]{text-align:left}
    #agent-test-transcript .test-message small{direction:ltr;text-align:left;unicode-bidi:isolate;font-variant-numeric:tabular-nums}
    #agent-test-message{direction:auto;text-align:start;unicode-bidi:plaintext;resize:vertical;min-height:105px}
    .modal-card:has(#agent-test-transcript){width:min(720px,calc(100vw - 24px));max-width:720px}
    @media(max-width:640px){.modal{padding:12px}.modal-card:has(#agent-test-transcript){padding:16px;border-radius:14px}#agent-test-transcript{max-height:50vh;padding:9px}.test-message{padding:9px}}
  `;
  document.head.appendChild(style);
}

function adminChatMessageHtml(kind,title,text,meta=""){
  const clean=adminChatCleanText(text);
  const dir=adminChatDirection(clean);
  return `<div class="test-message ${kind}"><strong>${escapeAdmin(title)}</strong><div class="test-chat-body" dir="${dir}">${escapeAdmin(clean)}</div>${meta?`<small>${escapeAdmin(meta)}</small>`:""}</div>`;
}

async function sendAgentTestMessage(companyId,agentId){
  ensureAdminChatQualityStyles();
  const input=document.getElementById("agent-test-message");
  const button=document.getElementById("agent-test-send");
  const transcript=document.getElementById("agent-test-transcript");
  const message=input.value.trim();
  if(!message){alert("Message is required.");return}

  button.disabled=true;
  button.textContent="Sending...";
  input.disabled=true;
  transcript.insertAdjacentHTML("beforeend",adminChatMessageHtml("test-user","You",message));
  transcript.insertAdjacentHTML("beforeend",`<div id="agent-test-pending" class="test-message test-assistant"><strong>AI Employee</strong><div class="test-chat-body" dir="ltr">Thinking...</div></div>`);
  input.value="";
  transcript.scrollTop=transcript.scrollHeight;

  try{
    const result=await api(`/admin/companies/${companyId}/agents/${agentId}/test-chat`,{
      method:"POST",
      body:JSON.stringify({message,conversation_id:agentTestConversationId})
    });
    agentTestConversationId=result.conversation_id;
    const pending=document.getElementById("agent-test-pending");
    if(pending){
      const meta=`${Number(result.usage?.total_tokens||0)} tokens · ${Number(result.usage?.latency_ms||0)} ms`;
      const response=adminChatCleanText(result.response?.content||"");
      pending.innerHTML=`<strong>AI Employee</strong><div class="test-chat-body" dir="${adminChatDirection(response)}">${escapeAdmin(response)}</div><small>${escapeAdmin(meta)}</small>`;
      pending.removeAttribute("id");
    }
  }catch(error){
    const pending=document.getElementById("agent-test-pending");
    if(pending){
      pending.className="test-message test-error";
      const clean=adminChatCleanText(error.message);
      pending.innerHTML=`<strong>Error</strong><div class="test-chat-body" dir="${adminChatDirection(clean)}">${escapeAdmin(clean)}</div>`;
      pending.removeAttribute("id");
    }
  }finally{
    input.disabled=false;
    input.focus();
    button.disabled=false;
    button.textContent="Send Message";
    transcript.scrollTop=transcript.scrollHeight;
  }
}
