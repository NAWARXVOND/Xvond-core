const XVOND_CUSTOMER_LIFECYCLE_COPY={
  onboarding:{label:'Onboarding',title:'Your Xvond workspace is being prepared',body:'Complete your Business Profile, AI employee setup and knowledge while Xvond finishes channel and service setup.'},
  testing:{label:'Testing',title:'Your workspace is in testing',body:'Use the test tools and review business information. Live customer traffic stays off until production readiness passes.'},
  live:{label:'Live',title:'Your Xvond workspace is live',body:'AI runtime is enabled for production-ready employees and connected channels.'},
  paused:{label:'Paused',title:'Your Xvond service is paused',body:'Your configuration is preserved, but AI runtime is stopped until service resumes.'},
  suspended:{label:'Suspended',title:'Workspace suspended',body:'Contact Xvond support to restore service.'},
  cancelled:{label:'Cancelled',title:'Service cancelled',body:'Contact Xvond if you need to reactivate this workspace.'},
  archived:{label:'Archived',title:'Workspace archived',body:'This workspace is no longer active.'}
};

function xvondCustomerLifecycleKind(status){
  if(status==='live')return 'status-active';
  if(['suspended','cancelled','archived'].includes(status))return 'status-inactive';
  return 'status-pending';
}

async function loadCustomerLifecycleBanner(){
  const dashboard=document.getElementById('page-dashboard');
  if(!dashboard||dashboard.classList.contains('hidden'))return;
  try{
    const overview=portalOverview||await api('/customer/overview');
    const company=overview.company||{};
    const status=String(company.lifecycle_status||'onboarding').toLowerCase();
    const copy=XVOND_CUSTOMER_LIFECYCLE_COPY[status]||XVOND_CUSTOMER_LIFECYCLE_COPY.onboarding;
    let banner=document.getElementById('xvond-company-lifecycle-banner');
    if(!banner){
      banner=document.createElement('div');
      banner.id='xvond-company-lifecycle-banner';
      banner.className='panel';
      banner.style.marginBottom='22px';
      dashboard.insertBefore(banner,dashboard.firstChild);
    }
    const runtime=company.active===true;
    banner.innerHTML=`
      <div style="display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <div class="muted" style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Company status</div>
          <h2 style="margin:6px 0 8px">${safe(copy.title)}</h2>
          <p class="muted" style="margin:0">${safe(copy.body)}</p>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <span class="status ${xvondCustomerLifecycleKind(status)}">${safe(copy.label)}</span>
          <span class="status ${runtime?'status-active':'status-inactive'}">AI Runtime ${runtime?'Running':'Stopped'}</span>
        </div>
      </div>`;
  }catch(_error){
    // The regular portal loader owns authentication/error handling. This banner is additive.
  }
}

const xvondCustomerLifecycleObserver=new MutationObserver(()=>{
  const page=document.getElementById('page-dashboard');
  if(page&&!page.classList.contains('hidden')&&!document.getElementById('xvond-company-lifecycle-banner')){
    loadCustomerLifecycleBanner();
  }
});
window.addEventListener('DOMContentLoaded',()=>{
  const portal=document.getElementById('portal');
  if(portal)xvondCustomerLifecycleObserver.observe(portal,{attributes:true,childList:true,subtree:true});
  loadCustomerLifecycleBanner();
});
