import type { components } from "./schema";
export type Models = components["schemas"];
export class ApiError extends Error {
  constructor(public code:string, message:string, public retryable:boolean, public status:number) {super(message);}
}
let csrf="", generation=0;
const requests=new Set<AbortController>();
export function clearSession(){csrf=""; clearProject();}
export function clearProject(){generation++; for(const controller of requests)controller.abort(); requests.clear();}
export function setCsrf(value:string){csrf=value;}
export async function api<T>(path:string, method="GET",body?:unknown):Promise<T>{
 const controller=new AbortController(), current=generation; requests.add(controller);
 const headers:Record<string,string>={};
 if(method!=="GET")headers["X-CSRF-Token"]=csrf;
 const multipart=body instanceof FormData;
 if(body!==undefined&&!multipart)headers["Content-Type"]="application/json";
 try {
  const response=await fetch(path,{method,credentials:"same-origin",cache:"no-store",headers,
   body:body===undefined?undefined:multipart?body:JSON.stringify(body),signal:controller.signal});
  if(current!==generation)throw new DOMException("Stale project response","AbortError");
  if(!response.ok){const payload=await response.json();throw new ApiError(payload.error?.code||"internal_error",payload.error?.message||"Request failed",!!payload.error?.retryable,response.status);}
  return response.status===204?undefined as T:await response.json() as T;
 }finally{requests.delete(controller);}
}
