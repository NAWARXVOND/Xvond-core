(function(){
  if(typeof renderAgentsTab!=='function')return;

  const baseRenderAgentsTab=renderAgentsTab;

  function setupState(row,d){
    const channels=(d.channels||[]).filter(x=>+x.agent_id===+row.agent.id);
    const enabledActions=(row.actions||[]).filter(x=>x.enabled===true);
    const readyActions=enabledActions.filter(x=>!(x.readiness_issues||[]).length);
    const connectedChannels=channels.filter(x=>x.configured||x.enabled);
    const connectedApps=(d.integrations||[]).filter(x=>x.enabled&&x.configured);
    return {
      profile:true,
      knowledge:(row.knowledge||[]).some(x=>x.enabled),
      actions:readyActions.length>0,
      channels:connectedChannels.length>0,
      apps:connectedApps.length>0,
      enabledActions:enabledActions.length,
      readyActions:readyActions.length,
      connectedChannels:connectedChannels.length,
      connectedApps:connectedApps.length,
    };
  }

  function step(label,done,buttonLabel,onclick,optional=false){
    const state=done?'Ready':optional?'Optional':'Needs setup';
    const kind=done?'good':optional?'neutral':'bad';
    return `<div class="readiness-row"><span class="readiness-dot ${done?'ok':'missing'}"></span><span>${f(label)}${optional?' · optional':''}</span><strong>${wsPill(state,kind)}</strong><button class="table-button" onclick="${onclick}">${f(buttonLabel)}</button></div>`;
  }

  function deliverySummary(readiness){
    const live=readiness?.ready_for_customer===true;
    const setupReady=readiness?.setup_ready===true;
    const mode=readiness?.mode==='conversational_and_operational'?'Conversation + Actions':'Conversation';
    const blockers=Array.isArray(readiness?.setup_blockers)?readiness.setup_blockers:[];
    const title=live?'Live for customer':setupReady?'Ready to go live':'Not ready to go live';
    const detail=live?'This employee passed the delivery checks and is active.':setupReady?'All setup checks passed. Activate only when you are ready for real customer traffic.':'';
    return `<div class="source-of-truth-box" style="margin-bottom:14px"><strong>${title}</strong><div>${f(mode)}${detail?' · '+f(detail):''}</div>${blockers.length?`<div class="meta" style="margin-top:8px">${blockers.map(x=>`• ${f(x)}`).join('<br>')}</div>`:''}</div>`;
  }

  async function refreshDeliveryGuide(companyId,agentId){
    await openSimpleCompany(companyId);
    await openAIEmployeeSetupGuide(agentId);
  }

  window.goLiveAIEmployee=async function(companyId,agentId){
    try{
      await api(`/admin/delivery-readiness/companies/${companyId}/agents/${agentId}/go-live`,{method:'POST',body:'{}'});
      await refreshDeliveryGuide(companyId,agentId);
    }catch(error){alert(error.message)}
  };

  window.deactivateAIEmployee=async function(companyId,agentId){
    try{
      await api(`/admin/delivery-readiness/companies/${companyId}/agents/${agentId}/deactivate`,{method:'POST',body:'{}'});
      await refreshDeliveryGuide(companyId,agentId);
    }catch(error){alert(error.message)}
  };

  window.openAIEmployeeSetupGuide=async function(agentId){
    const d=xvondWorkspace.data;
    const row=(d.agentMeta||[]).find(x=>+x.agent.id===+agentId);
    if(!row)return;
    const s=setupState(row,d),companyId=d.view.company.id;
    openModal(`Setup ${row.agent.name}`,`<div class="modal-intro"><strong>Checking customer delivery readiness...</strong></div>`);
    let readiness=null;
    try{
      readiness=await api(`/admin/delivery-readiness/companies/${companyId}/agents/${agentId}`);
    }catch(error){
      readiness={ready_for_customer:false,setup_ready:false,mode:'unknown',setup_blockers:[error.message||'Could not check delivery readiness']};
    }
    const actionsOptional=s.enabledActions===0;
    const lifecycleAction=readiness?.ready_for_customer
      ? `<button class="table-button" onclick="deactivateAIEmployee(${companyId},${agentId})">Deactivate</button>`
      : readiness?.setup_ready
        ? `<button class="primary-button" onclick="goLiveAIEmployee(${companyId},${agentId})">Go Live</button>`
        : '';
    openModal(`Setup ${row.agent.name}`,`
      ${deliverySummary(readiness)}
      <div class="modal-intro"><strong>Configure this employee for the customer's requested service</strong><p>New employees stay in Draft until all required setup passes and you explicitly choose Go Live.</p></div>
      <div class="readiness-list">
        ${step('1. Employee identity & behavior',Boolean(readiness?.checks?.profile),'Edit',`openEditAIEmployee(${companyId},${agentId})`)}
        ${step('2. Business knowledge',Boolean(readiness?.checks?.knowledge),'Knowledge',`openKnowledgeManager(${companyId},${agentId})`)}
        ${step('3. Allowed business actions',actionsOptional||Boolean(readiness?.checks?.actions),'Actions',`openAgentActions(${companyId},${agentId})`,actionsOptional)}
        ${step('4. Customer channels',Boolean(readiness?.checks?.channels),'Channels',`closeModal();switchWorkspaceTab('channels')`)}
        ${step('5. Connected apps for execution',Boolean(readiness?.checks?.connected_apps),'Connected Apps',`closeModal();switchWorkspaceTab('integrations')`,actionsOptional)}
      </div>
      <div class="workspace-metrics compact" style="margin-top:14px">
        <div class="metric-card"><span>Knowledge</span><strong>${Number(readiness?.counts?.knowledge_sources||0)}</strong></div>
        <div class="metric-card"><span>Channels</span><strong>${Number(readiness?.counts?.channels||0)}</strong></div>
        <div class="metric-card"><span>Enabled Actions</span><strong>${Number(readiness?.counts?.enabled_actions||0)}</strong></div>
      </div>
      <div class="source-of-truth-box"><strong>Execution rule</strong><div>The AI employee decides what action is allowed. Business side effects are executed only through the Workflow Engine. A customer must never be told an operation succeeded until execution returns success.</div></div>
      <div class="workspace-inline-actions" style="margin-top:14px"><button class="table-button" onclick="openAgentTestChat(${companyId},${agentId})">Test Employee</button>${readiness?.checks?.workflow_engine===false?`<button class="primary-button" onclick="closeModal();switchWorkspaceTab('workflow')">Workflow Engine</button>`:''}${lifecycleAction}</div>
    `);
  };

  renderAgentsTab=function(){
    const html=baseRenderAgentsTab();
    const d=xvondWorkspace.data;
    if(!d||(d.agentMeta||[]).length===0)return html;
    const rows=d.agentMeta.map(row=>{
      const s=setupState(row,d);
      const configured=s.profile&&s.knowledge&&s.channels&&(s.enabledActions===0||s.readyActions===s.enabledActions);
      const live=row.agent.enabled===true;
      return `<div class="integration-card"><div class="integration-card-head"><div><h4>${f(row.agent.name)}</h4><div class="meta">${live?'Live':configured?'Draft · configuration complete':'Draft · setup still needs attention'}</div></div>${wsPill(live?'Live':configured?'Draft Ready':'Draft',live?'good':'neutral')}</div><div class="meta">${s.readyActions} ready actions · ${s.connectedChannels} connected channels · ${s.connectedApps} connected apps</div><div class="workspace-inline-actions"><button class="primary-button" onclick="openAIEmployeeSetupGuide(${row.agent.id})">Check Delivery Readiness</button></div></div>`;
    }).join('');
    const guide=`<div class="workspace-panel" style="margin-bottom:16px"><div class="workspace-panel-head"><div><h3>AI Employee Delivery</h3><p>Create in Draft, configure what the customer ordered, test it, then Go Live only after delivery readiness passes.</p></div><button class="primary-button" onclick="openAddAIEmployee(${d.view.company.id})">+ AI Employee</button></div><div class="integration-grid">${rows}</div></div>`;
    return guide+html;
  };
})();
