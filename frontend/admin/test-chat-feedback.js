async function sendAgentTestMessage(companyId,agentId){
  const input=document.getElementById("agent-test-message");
  const button=document.getElementById("agent-test-send");
  const transcript=document.getElementById("agent-test-transcript");
  const message=input.value.trim();
  if(!message){alert("Message is required.");return}

  button.disabled=true;
  button.textContent="Sending...";
  input.disabled=true;
  transcript.innerHTML+=`<div class="test-message test-user"><strong>You</strong><div>${escapeAdmin(message)}</div></div><div id="agent-test-pending" class="test-message test-assistant"><strong>AI Employee</strong><div>Thinking...</div></div>`;
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
      pending.innerHTML=`<strong>AI Employee</strong><div>${escapeAdmin(result.response?.content||"")}</div><small>${Number(result.usage?.total_tokens||0)} tokens · ${Number(result.usage?.latency_ms||0)} ms</small>`;
      pending.removeAttribute("id");
    }
  }catch(error){
    const pending=document.getElementById("agent-test-pending");
    if(pending){
      pending.className="test-message test-error";
      pending.innerHTML=`<strong>Error</strong><div>${escapeAdmin(error.message)}</div>`;
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
