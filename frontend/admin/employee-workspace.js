// Final AI Employee workspace surface.
// Stable setup model: Information → Knowledge → Actions → Channels → Conversations.
function renderAgentsTab(){
  const d=xvondWorkspace.data;
  return `<div class="workspace-panel">
    <div class="workspace-panel-head">
      <div><h3>AI Employees</h3><p>Each employee inherits company facts, then gets its own behavior, knowledge, actions, channels and conversations.</p></div>
      <button class="primary-button" onclick="openAddAIEmployee(${d.view.company.id})">+ AI Employee</button>
    </div>
    ${d.agentMeta.length?`<div class="employee-grid">${d.agentMeta.map(row=>{
      const a=row.agent;
      const channels=d.channels.filter(x=>+x.agent_id===+a.id);
      const live=channels.some(x=>x.enabled);
      const readyActions=row.actions.filter(x=>x.enabled===true&&!(x.readiness_issues||[]).length).length;
      return `<div class="employee-card">
        <div class="employee-card-top">
          <div class="employee-avatar">${f((a.name||'A').slice(0,1).toUpperCase())}</div>
          <div><h4>${f(a.name)}</h4><div class="meta">${a.enabled?'Active AI Employee':'Paused AI Employee'}</div></div>
          ${wsPill(a.enabled?'Active':'Paused',a.enabled?'good':'neutral')}
        </div>
        <div class="employee-stats">
          <div><strong>${row.knowledge.filter(x=>x.enabled).length}</strong><span>Knowledge</span></div>
          <div><strong>${readyActions}</strong><span>Ready Actions</span></div>
          <div><strong>${channels.length}</strong><span>Channels</span></div>
        </div>
        <div class="employee-flow-label">Information → Knowledge → Actions → Channels → Conversations</div>
        <div class="employee-actions employee-primary-actions">
          <button onclick="openEditAIEmployee(${d.view.company.id},${a.id})">Information</button>
          <button onclick="openKnowledgeManager(${d.view.company.id},${a.id})">Knowledge</button>
          <button onclick="openAgentActions(${d.view.company.id},${a.id})">Actions</button>
          <button onclick="switchWorkspaceTab('channels')">Channels</button>
          <button onclick="openHumanTakeover(${d.view.company.id},${a.id})">Conversations</button>
        </div>
        <div class="employee-actions employee-secondary-actions">
          <button class="table-button" onclick="openAgentTestChat(${d.view.company.id},${a.id})">Test Employee</button>
          <button class="danger" onclick="deleteWorkspaceEmployee(${a.id},${live})">Delete</button>
        </div>
      </div>`;
    }).join('')}</div>`:wsEmpty('No AI employees yet','Create the employee core first. Company facts live in Company, while channels and actions are connected separately.')}
  </div>`;
}
