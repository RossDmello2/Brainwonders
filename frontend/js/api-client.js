const DEADLINES={transcribe:210000,document:150000};
export class ApiClient{
  constructor(base){this.base=base.replace(/\/$/,"");this.controller=null}
  cancel(){this.controller?.abort();this.controller=null}
  async request(path,form,{key,kind="document"}={}){
    this.cancel();const controller=new AbortController();this.controller=controller;
    const timer=setTimeout(()=>controller.abort(),DEADLINES[kind]);
    try{
      const headers={};if(key)headers["X-Provider-Key"]=key;
      const response=await fetch(this.base+path,{method:"POST",body:form,headers,credentials:"omit",cache:"no-store",redirect:"error",signal:controller.signal});
      if(!response.ok){let payload;try{payload=await response.json()}catch{payload=null}const error=new Error(payload?.error?.message||"The request failed. Your work is still here.");error.code=payload?.error?.code||"REQUEST_FAILED";throw error}
      return response;
    }catch(error){if(error.name==="AbortError")throw Object.assign(new Error("The request was canceled or timed out. Your work is still here."),{code:"REQUEST_CANCELED"});throw error}
    finally{clearTimeout(timer);if(this.controller===controller)this.controller=null}
  }
  async validate(docx,json){const f=new FormData();f.append("template_docx",docx,"template.docx");f.append("template_json",json,"template.json");return (await this.request("/v1/templates/validate",f)).json()}
  async transcribe(audio,metadata,key){const f=new FormData();f.append("audio",audio,"audio.bin");Object.entries(metadata).forEach(([k,v])=>{if(v!==null&&v!==undefined&&v!=="")f.append(k,String(v))});return (await this.request("/v1/transcriptions",f,{key,kind:"transcribe"})).json()}
  async docx(pair,fingerprint,values){const f=new FormData();f.append("template_docx",pair.docx,"template.docx");f.append("template_json",pair.json,"template.json");f.append("values_json",new Blob([JSON.stringify(values)],{type:"application/json"}),"values.json");f.append("expected_fingerprint",fingerprint);f.append("review_confirmed","true");return this.request("/v1/documents/docx",f)}
}
