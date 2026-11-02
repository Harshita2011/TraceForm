"""Safe structured HTTP events: route templates, never bodies, cookies or query strings."""
import json,logging,re,time
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
log=logging.getLogger('traceform.requests')
if not log.handlers:
    handler=logging.StreamHandler();handler.setFormatter(logging.Formatter('%(message)s'));log.addHandler(handler)
log.propagate=False;log.setLevel(logging.INFO)
class RequestEvents(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        supplied=request.headers.get('x-request-id','')
        rid=supplied if re.fullmatch(r'[A-Za-z0-9_-]{8,64}',supplied) else uuid4().hex
        start=time.perf_counter();code=500
        try:
            response=await call_next(request);code=response.status_code;response.headers['X-Request-ID']=rid
            return response
        finally:
            route=request.scope.get('route')
            log.info(json.dumps({'event':'http_request','request_id':rid,'method':request.method,
                'route':getattr(route,'path','unmatched'),'status':code,'elapsed_ms':round((time.perf_counter()-start)*1000,3)}))
