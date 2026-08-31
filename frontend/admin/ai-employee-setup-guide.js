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

  window.openAIEmployeeSetupGuide=function(agentId){
    const d=xvondWorkspace.data;
    const row=(d.agentMeta||[]).find(x=>+x.agent.id===+agentId);
    if(!row)return;
    const s=setupState(row,d),companyId=d.view.company.id;
    const operational=s.profile&&s.knowledge&&s.actions&&s.channels;
    openModal(`Setup ${row.agent.name}`,`
      <div class="modal-intro"><strong>${operational?'Employee setup is operational':'Complete the employee setup'}</strong><p>Xvond keeps one employee brain across every channel. Configure the employee once, then attach only the knowledge, actions, channels and connected apps it needs.</p></div>
      <div class="readiness-list">
        ${step('1. Employee identity & behavior',s.profile,'Edit',`openEditAIEmployee(${companyId},${agentId})`)}
        ${step('2. Business knowledge',s.knowledge,'Knowledge',`openKnowledgeManager(${companyId},${agentId})`)}
        ${step('3. Allowed business actions',s.actions,'Actions',`openAgentActions(${companyId},${agentId})`)}
        ${step('4. Customer channels',s.channels,'Channels',`closeModal();switchWorkspaceTab('channels')`)}
        ${step('5. Connected apps for execution',s.apps,'Connected Apps',`closeModal();switchWorkspaceTab('integrations')`,true)}
      </div>
      <div class="workspace-metrics compact" style="margin-top:14px">
        <div class="metric-card"><span>Ready Actions</span><strong>${s.readyActions}</strong><small>${s.enabledActions} enabled</small></div>
        <div class="metric-card"><span>Channels</span><strong>${s.connectedChannels}</strong></div>
        <div class="metric-card"><span>Connected Apps</span><strong>${s.connectedApps}</strong></div>
      </div>
      <div class="source-of-truth-box"><strong>Execution rule</strong><div>The AI employee decides what action is allowed. Business side effects are executed only through the Workflow Engine. A customer must never be told an operation succeeded until execution returns success.</div></div>
      <div class="workspace-inline-actions" style="margin-top:14px"><button class="table-button" onclick="openAgentTestChat(${companyId},${agentId})">Test Employee</button><button class="primary-button" onclick="closeModal();switchWorkspaceTab('workflow')">Workflow Engine</button></div>
    `);
  };

  renderAgentsTab=function(){
    const html=baseRenderAgentsTab();
    const d=xvondWorkspace.data;
    if(!d||(d.agentMeta||[]).length===0)return html;
    const rows=d.agentMeta.map(row=>{
      const s=setupState(row,d);
      const operational=s.profile&&s.knowledge&&s.actions&&s.channels;
      return `<div class="integration-card"><div class="integration-card-head"><div><h4>${f(row.agent.name)}</h4><div class="meta">${operational?'Operational setup complete':'Setup still needs attention'}</div></div>${wsPill(operational?'Ready':'Setup',operational?'good':'neutral')}</div><div class="meta">${s.readyActions} ready actions · ${s.connectedChannels} connected channels · ${s.connectedApps} connected apps</div><div class="workspace-inline-actions"><button class="primary-button" onclick="openAIEmployeeSetupGuide(${row.agent.id})">Setup Guide</button></div></div>`;
    }).join('');
    const guide=`<div class="workspace-panel" style="margin-bottom:16px"><div class="workspace-panel-head"><div><h3>AI Employee Setup</h3><p>Create the employee core first, then complete knowledge, actions, channels and execution connections without touching code.</p></div><button class="primary-button" onclick="openAddAIEmployee(${d.view.company.id})">+ AI Employee</button></div><div class="integration-grid">${rows}</div></div>`;
    return guide+html;
  };
})();
