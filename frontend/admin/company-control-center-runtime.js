loadCompanyControlCenter=async function(companyId,tab=null){
  simpleCompanyId=Number(companyId);
  xvondWorkspace.companyId=Number(companyId);
  if(tab)xvondWorkspace.tab=tab;

  const [view,channelResult,moduleResult,catalog,integrations,requests,conversations,usage,profile,setup,handoffs,audit,billing,plans,users]=await Promise.all([
    api(`/admin/company-view/${companyId}`),
    api(`/admin/channels/companies/${companyId}`),
    api(`/admin/companies/${companyId}/modules`),
    api('/admin/agent-actions/templates/catalog'),
    api(`/admin/integrations/companies/${companyId}`),
    api(`/admin/agent-actions/companies/${companyId}/requests`),
    api(`/admin/operations/companies/${companyId}/conversations`),
    api(`/admin/operations/companies/${companyId}/usage`),
    api(`/admin/company-profile/${companyId}`),
    api('/admin/setup/catalog'),
    wsOptional(`/admin/handoff/companies/${companyId}/sessions`,{sessions:[]}),
    wsOptional(`/admin/audit/?company_id=${companyId}&limit=100`,{logs:[],total:0}),
    wsOptional(`/admin/billing/companies/${companyId}/subscription`,{subscription:null}),
    wsOptional('/admin/billing/plans',{plans:[]}),
    wsOptional(`/admin/company-users/companies/${companyId}`,{users:[]})
  ]);

  const agentMeta=await Promise.all((view.agents||[]).map(async agent=>{
    const [agentProfile,knowledge,actions]=await Promise.all([
      wsOptional(`/admin/ai-employee-profile/companies/${companyId}/${agent.id}`,{name:agent.name}),
      wsOptional(`/admin/ai-employees/companies/${companyId}/${agent.id}/knowledge`,{items:[]}),
      wsOptional(`/admin/agent-actions/${agent.id}`,{actions:[],ready:false})
    ]);
    return {
      agent,
      profile:agentProfile,
      knowledge:knowledge.items||[],
      actions:actions.actions||[],
      operationsReady:!!actions.ready
    };
  }));

  xvondWorkspace.data={
    view,
    channels:channelResult.channels||[],
    modules:moduleResult.modules||[],
    catalog,
    integrations:integrations.integrations||[],
    requests:requests.requests||[],
    conversations:conversations.conversations||[],
    usage,
    profile,
    setup,
    handoffs:handoffs.sessions||[],
    audit:audit.logs||[],
    billing:billing.subscription||null,
    plans:plans.plans||[],
    users:(users.users&&users.users.length?users.users:view.users)||[],
    agentMeta
  };
  renderCompanyControlCenter();
};

openSimpleCompany=loadCompanyControlCenter;
window.openCompany=loadCompanyControlCenter;
