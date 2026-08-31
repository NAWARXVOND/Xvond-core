let xvondMetaSignupState=null;
let xvondMetaSignupMessage=null;
let xvondMetaSdkPromise=null;

function xvondTrustedMetaOrigin(origin){
  try{
    const u=new URL(origin);
    const h=(u.hostname||'').toLowerCase();
    return u.protocol==='https:'&&(h==='facebook.com'||h.endsWith('.facebook.com'));
  }catch(_){return false}
}

function xvondLoadMetaSdk(appId,graphVersion){
  if(window.FB){FB.init({appId,cookie:true,xfbml:false,version:graphVersion||'v23.0'});return Promise.resolve()}
  if(xvondMetaSdkPromise)return xvondMetaSdkPromise;
  xvondMetaSdkPromise=new Promise((resolve,reject)=>{
    window.fbAsyncInit=function(){FB.init({appId,cookie:true,xfbml:false,version:graphVersion||'v23.0'});resolve()};
    const existing=document.getElementById('facebook-jssdk');
    if(existing){existing.addEventListener('load',()=>resolve(),{once:true});return}
    const script=document.createElement('script');
    script.id='facebook-jssdk';script.async=true;script.defer=true;script.crossOrigin='anonymous';
    script.src='https://connect.facebook.net/en_US/sdk.js';
    script.onerror=()=>reject(new Error('Could not load Meta SDK'));
    document.head.appendChild(script);
  });
  return xvondMetaSdkPromise
}

window.addEventListener('message',event=>{
  if(!xvondTrustedMetaOrigin(event.origin))return;
  let payload=event.data;
  if(typeof payload==='string'){try{payload=JSON.parse(payload)}catch(_){return}}
  if(!payload||payload.type!=='WA_EMBEDDED_SIGNUP')return;
  const completedEvents=new Set(['FINISH','FINISH_ONLY_WABA','FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING']);
  if(completedEvents.has(payload.event))xvondMetaSignupMessage={...(payload.data||{}),event:payload.event};
});

window.openMetaWhatsAppConnect=async function(agentId){
  try{
    const config=await api(`/admin/meta/whatsapp/embedded-signup/config?agent_id=${Number(agentId)}`);
    if(!config.ready){alert('Meta Embedded Signup is not configured on the Xvond server yet.');return}
    xvondMetaSignupState={agentId:Number(agentId)};xvondMetaSignupMessage=null;
    await xvondLoadMetaSdk(config.app_id,config.graph_api_version);
    FB.login(response=>{
      const code=response?.authResponse?.code;
      if(!code){if(response?.status!=='unknown')alert('Meta did not return an authorization code.');return}
      xvondFinishMetaWhatsAppSignup(code);
    },{
      config_id:config.config_id,
      response_type:'code',
      override_default_response_type:true,
      extras:{
        setup:{},
        featureType:'whatsapp_business_app_onboarding',
        sessionInfoVersion:config.session_info_version||'3'
      }
    });
  }catch(e){alert(e.message||String(e))}
};

async function xvondFinishMetaWhatsAppSignup(code){
  try{
    for(let attempt=0;attempt<40&&!xvondMetaSignupMessage;attempt+=1)await new Promise(r=>setTimeout(r,250));
    const data=xvondMetaSignupMessage||{};
    const wabaId=data.waba_id||data.wabaId;
    const phoneNumberId=data.phone_number_id||data.phoneNumberId||null;
    const businessId=data.business_id||data.businessId||null;
    if(!wabaId){alert('Meta authorization succeeded, but the WhatsApp Business Account was not returned. Finish the Meta setup window completely and try again.');return}
    const result=await api('/admin/meta/whatsapp/embedded-signup/complete',{
      method:'POST',
      body:JSON.stringify({
        agent_id:xvondMetaSignupState.agentId,
        code:String(code),
        waba_id:String(wabaId),
        phone_number_id:phoneNumberId?String(phoneNumberId):null,
        business_id:businessId?String(businessId):null,
        connection_mode:data.event==='FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING'?'coexistence':'embedded_signup'
      })
    });
    closeModal();
    await openSimpleCompany(simpleCompanyId);
    if(result.ready)alert(`WhatsApp connected successfully.\n${result.display_phone_number||result.phone_number_id}`);
    else alert(`WhatsApp account connected. Complete setup before activation:\n${(result.blockers||[]).join('\n')}`);
  }catch(e){alert(e.message||String(e))}
  finally{xvondMetaSignupState=null;xvondMetaSignupMessage=null}
}
