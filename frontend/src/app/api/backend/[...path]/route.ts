import { NextRequest } from 'next/server';
export const maxDuration=120;
async function proxy(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const {path}=await context.params;
  if(path[0]!=='api'||path[1]!=='v1'||path.some(p=>p==='..'||p.includes('/')))return Response.json({detail:'Unknown API route.'},{status:404});
  const route='/'+path.join('/');
  const size=Number(request.headers.get('content-length')||0);
  if(process.env.VERCEL&&size>4250000)return Response.json({detail:'This deployment accepts requests up to 4 MB. Split or reduce the source file.'},{status:413});
  const upstreamRoute=['/api/v1/sources','/api/v1/generations','/api/v1/presets'].includes(route)?route+'/':route;
  const publicAuth=['status','login','setup','accept','logout'].some(name=>route==='/api/v1/auth/'+name);
  if(!request.cookies.get('traceform_session')&&!publicAuth)return Response.json({detail:'Sign in to your workspace.'},{status:401});
  const headers=new Headers();
  for(const name of ['content-type','cookie','origin','idempotency-key']) {const value=request.headers.get(name);if(value)headers.set(name,value);}
  if(route==='/api/v1/auth/setup') {const key=request.headers.get('x-installation-key');if(key)headers.set('X-API-Key',key);}
  try {
    if(process.env.VERCEL&&(!process.env.TRACEFORM_API_URL||!process.env.TRACEFORM_API_URL.startsWith('https://')))return Response.json({detail:'The hosted backend HTTPS URL has not been configured.'},{status:503});
    const upstream=await fetch((process.env.TRACEFORM_API_URL||'http://127.0.0.1:8000')+upstreamRoute+request.nextUrl.search,{method:request.method,headers,cache:'no-store',redirect:'manual',
      body:['GET','HEAD'].includes(request.method)?undefined:await request.arrayBuffer(),signal:AbortSignal.timeout(120000)});
    const output=new Headers({'Cache-Control':'no-store'});
    for(const name of ['content-type','content-disposition','set-cookie','x-request-id']) {const value=upstream.headers.get(name);if(value)output.set(name,value);}
    return new Response(upstream.body,{status:upstream.status,headers:output});
  } catch {return Response.json({detail:'The API is unavailable. Your saved work is kept. Retry when it is running.'},{status:503});}
}
export const GET=proxy;export const POST=proxy;export const PUT=proxy;export const DELETE=proxy;export const PATCH=proxy;
