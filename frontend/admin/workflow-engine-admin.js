(function(){
  const originalLoadCompanyControlCenter=loadCompanyControlCenter;
  const originalRenderCompanyControlCenter=renderCompanyControlCenter;
  const originalRenderWorkspaceTab=renderWorkspaceTab;
  const originalRenderOverviewTab=renderOverviewTab;
  const originalRenderOperationsTab=renderOperationsTab;
  const originalRenderIntegrationsTab=renderIntegrationsTab;

  function workflowStatus(){
    return xvondWorkspace.data?.workflowEngine||{status:'unknown',enabled:false,configured:false};
  }

  function workflowPill(){
    const s=workflowStatus();
    if(s.status==='ready')return wsPill('Ready','good');
    if(s.status==='needs_setup')return wsPill('Needs setup','bad');
    if(s.status==='disabled')return wsPill('Disabled','neutral');
    return wsPill('Unknown','neutral');
  }

  function renderWorkflowEngineTab(){
    const d=xvondWorkspace.data||{};
    const s=workflowStatus();
    const enabledActions=(d.agentMeta||[]).reduce((count,row)=>count+(row.actions||[]).filter(action=>action.enabled===true).length,0);
    const connectedApps=(d.integrations||[]).filter(item=>item.enabled&&item.configured).length;
    const unresolved=(d.unresolved||[]).length;
    return `<div class="workspace-grid two-col">
      <div class="workspace-panel">
        <div class="workspace-panel-head"><div><h3>Workflow Engine</h3><p>Authoritative execution runtime for business actions.</p></div>${workflowPill()}</div>
        <div class="info-grid">
          <div><span>Runtime</span><strong>${f(s.status||'unknown')}</strong></div>
          <div><span>Gateway</span><strong>${s.configured?'Configured':'Not configured'}</strong></div>
          <div><span>Authentication</span><strong>${s.authentication_configured?'Configured':'Not configured'}</strong></div>
          <div><span>Webhook</span><strong>${s.webhook_configured?'Configured':'Not configured'}</strong></div>
          <div><span>Timeout</span><strong>${f(s.timeout_seconds||'—')}s</strong></div>
          <div><span>Retry limit</span><strong>${f(s.max_retries??'—')}</strong></div>
        </div>
      </div>
      <div class="workspace-panel">
        <div class="workspace-panel-head"><div><h3>Execution Summary</h3><p>Xvond decides; the workflow runtime executes.</p></div></div>
        <div class="workspace-metrics compact">
          <div class="metric-card"><span>Enabled Actions</span><strong>${enabledActions}</strong></div>
          <div class="metric-card"><span>Connected Apps</span><strong>${connectedApps}</strong></div>
          <div class="metric-card"><span>Open Operations</span><strong>${wsActiveOperations().length}</strong></div>
          <div class="metric-card"><span>Needs Reconciliation</span><strong>${unresolved}</strong></div>
        </div>
        <div class="architecture-flow"><span>Xvond Decision</span><b>→</b><span>Workflow Engine</span><b>→</b><span>Connected App</span><b>→</b><span>Result</span><b>→</b><span>Xvond</span></div>
      </div>
    </div>`;
  }

  loadCompanyControlCenter=async function(companyId,tab=null){
    await originalLoadCompanyControlCenter(companyId,tab);
    xvondWorkspace.data.workflowEngine=await wsOptional('/admin/workflow-engine/status',{status:'unknown',enabled:false,configured:false,webhook_configured:false,authentication_configured:false});
    renderCompanyControlCenter();
  };

  renderCompanyControlCenter=function(){
    originalRenderCompanyControlCenter();
    const tabs=document.querySelector('.workspace-tabs');
    if(!tabs)return;
    const integrations=[...tabs.querySelectorAll('.workspace-tab')].find(button=>button.getAttribute('onclick')?.includes("'integrations'"));
    if(integrations)integrations.textContent='Connected Apps';
    if(!tabs.querySelector('[data-workflow-engine-tab]')){
      const button=document.createElement('button');
      button.className=`workspace-tab ${xvondWorkspace.tab==='workflow'?'active':''}`;
      button.dataset.workflowEngineTab='1';
      button.textContent='Workflow Engine';
      button.onclick=()=>switchWorkspaceTab('workflow');
      if(integrations?.nextSibling)tabs.insertBefore(button,integrations.nextSibling);else tabs.appendChild(button);
    }
  };

  renderWorkspaceTab=function(){
    if(xvondWorkspace.tab==='workflow')return renderWorkflowEngineTab();
    return originalRenderWorkspaceTab();
  };

  renderOverviewTab=function(){
    const html=originalRenderOverviewTab();
    const s=workflowStatus();
    const engineCard=`<div class="workspace-panel"><div class="workspace-panel-head"><div><h3>Execution Runtime</h3><p>Business side effects are delegated to the Workflow Engine.</p></div>${workflowPill()}</div><div class="info-grid"><div><span>Connected Apps</span><strong>${(xvondWorkspace.data?.integrations||[]).filter(x=>x.enabled&&x.configured).length}</strong></div><div><span>Unresolved executions</span><strong>${(xvondWorkspace.data?.unresolved||[]).length}</strong></div></div><div class="workspace-inline-actions"><button class="table-button" onclick="switchWorkspaceTab('workflow')">Workflow Engine</button><button class="table-button" onclick="switchWorkspaceTab('integrations')">Connected Apps</button></div></div>`;
    return html.replace('</div><div class="workspace-panel"><div class="architecture-flow">',`</div>${engineCard}<div class="workspace-panel"><div class="architecture-flow">`).replace('Knowledge + Actions</span><b>→</b><span>Channels','Knowledge + Actions</span><b>→</b><span>Workflow Engine</span><b>→</b><span>Connected Apps</span><b>→</b><span>Channels');
  };

  renderOperationsTab=function(){
    return originalRenderOperationsTab()
      .replace('Actual results created by configured AI actions.','Business action requests and execution results returned by the Workflow Engine.')
      .replace('Verify the external CRM/POS/API before choosing an outcome. Xvond will not retry automatically.','Reconcile the Workflow Engine result with the connected app before choosing an outcome. Xvond will not claim success while execution is unresolved.')
      .replaceAll('External unresolved','Execution unresolved');
  };

  renderIntegrationsTab=function(){
    return originalRenderIntegrationsTab()
      .replace('<h3>Integrations</h3>','<h3>Connected Apps</h3>')
      .replace('External systems that configured actions can actually call.','Business systems used by Workflow Engine actions. Credentials and execution stay outside Xvond Core.')
      .replace('+ Integration','+ Connected App')
      .replace('No integrations connected','No connected apps yet');
  };
})();
