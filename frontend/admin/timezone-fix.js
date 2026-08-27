function xvondNormalizeUtcTimestamp(value){
  const raw=String(value||'').trim();
  if(!raw)return raw;
  return /([zZ]|[+-]\d{2}:\d{2})$/.test(raw)?raw:`${raw}Z`;
}

function wsDate(value){
  if(!value)return '—';
  try{
    const date=new Date(xvondNormalizeUtcTimestamp(value));
    const timeZone=window.xvondWorkspace?.data?.profile?.timezone||'Asia/Muscat';
    return date.toLocaleString(undefined,{timeZone});
  }catch(_error){
    return String(value);
  }
}
