"""Optional read-only Sorftime Streamable HTTP client. Never reads global configs."""
import argparse,hashlib,json,os,re,sys
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs,urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from research import ALIASES,read,write

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):raise ValueError('MCP endpoint redirect refused; configure the final official endpoint')

def endpoint():
 url=os.environ.get('SORFTIME_MCP_URL')
 if not url:
  key=os.environ.get('SORFTIME_API_KEY')
  if not key:raise ValueError('Sorftime is not configured: provide host MCP or local SORFTIME_MCP_URL/SORFTIME_API_KEY')
  url='https://mcp.sorftime.com?'+urlencode({'key':key})
 u=urlparse(url)
 if u.scheme!='https' or u.hostname!='mcp.sorftime.com' or u.username or u.password or u.port not in [None,443]:raise ValueError('Only the official HTTPS Sorftime endpoint is supported')
 return url

def redact(value,secrets=()):
 if isinstance(value,dict):return {k:('[REDACTED]' if re.search(r'(?i)^(key|token|secret|authorization|api.?key|access.?token)$',k) else redact(v,secrets)) for k,v in value.items()}
 if isinstance(value,list):return [redact(v,secrets) for v in value]
 if isinstance(value,str):
  for s in secrets:
   if s:value=value.replace(s,'[REDACTED]')
  return re.sub(r'https?://[^\s<>\"]*[?&](?:key|token|api_key)=[^\s<>\"]*','[REDACTED MCP URL]',value,flags=re.I)
 return value

def canonical(name):return re.split(r'__|[.:/]',name)[-1]
def parse_sse(lines,request_id):
 data=[];size=0
 for line in lines:
  if isinstance(line,bytes):line=line.decode('utf-8')
  size+=len(line.encode('utf-8'))
  if size>20*1024*1024:raise ValueError('SSE response exceeds20MiB; narrow query')
  line=line.rstrip('\r\n')
  if line.startswith('data:'):data.append(line[5:].lstrip(' '))
  if not line and data:
   message=json.loads('\n'.join(data));data=[]
   if message.get('method') and 'id' in message:raise ValueError('Server interaction is unsupported; use host MCP')
   if message.get('id')==request_id:return message
 if data:
  message=json.loads('\n'.join(data))
  if message.get('id')==request_id:return message
 raise ValueError('No matching JSON-RPC result in SSE response')

class Client:
 def __init__(self,url):self.url=url;self.session=None;self.protocol='2025-03-26';self.seq=0;self.opener=build_opener(NoRedirect)
 def rpc(self,method,params=None,notify=False):
  self.seq+=1;rid=self.seq
  body={'jsonrpc':'2.0','method':method}
  if not notify:body['id']=rid
  if params is not None:body['params']=params
  headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':self.protocol}
  if self.session:headers['Mcp-Session-Id']=self.session
  req=Request(self.url,data=json.dumps(body).encode(),headers=headers,method='POST')
  try:
   with self.opener.open(req,timeout=45) as resp:
    if resp.headers.get('Mcp-Session-Id'):self.session=resp.headers['Mcp-Session-Id']
    if notify and resp.status in [200,202,204]:return None
    typ=resp.headers.get('Content-Type','')
    if 'text/event-stream' in typ:msg=parse_sse(resp,rid)
    else:
     data=resp.read(20*1024*1024+1)
     if len(data)>20*1024*1024:raise ValueError('MCP response exceeds20MiB; narrow query')
     msg=json.loads(data)
  except HTTPError as ex:raise ValueError('Sorftime HTTP status '+str(ex.code)) from None
  if msg.get('id')!=rid:raise ValueError('JSON-RPC id mismatch')
  if 'error' in msg:raise ValueError('Sorftime returned a JSON-RPC error; use host tool diagnostics')
  return msg.get('result')
 def initialize(self):
  r=self.rpc('initialize',{'protocolVersion':self.protocol,'capabilities':{},'clientInfo':{'name':'nfwl-product-research','version':'1.0.0'}})
  version=r.get('protocolVersion')
  if version not in ['2025-03-26','2025-06-18','2025-11-25']:raise ValueError('Unsupported negotiated MCP version')
  self.protocol=version;self.rpc('notifications/initialized',notify=True)
 def catalog(self):
  tools=[];cursor=None;seen=set()
  while True:
   p=self.rpc('tools/list',{'cursor':cursor} if cursor else {})
   if not isinstance(p.get('tools'),list):raise ValueError('Malformed tool catalog')
   tools.extend(p['tools']);cursor=p.get('nextCursor')
   if not cursor:break
   if cursor in seen:raise ValueError('Repeated tool pagination cursor')
   seen.add(cursor)
   if len(seen)>100:raise ValueError('Tool pagination exceeded bounded limit')
  return tools
 def call(self,name,cap,args,tools):
  matches=[x for x in tools if x['name']==name]
  if len(matches)!=1 or canonical(name) not in ALIASES[cap]:raise ValueError('Tool not discovered/bound to approved read-only capability')
  tool=matches[0]
  if tool.get('annotations',{}).get('destructiveHint') is True:raise ValueError('Destructive tool refused')
  try:from jsonschema import Draft202012Validator
  except ImportError:raise ValueError('Direct HTTP call validation needs jsonschema; use host MCP or install scripts/requirements.txt') from None
  errors=list(Draft202012Validator(tool.get('inputSchema',{})).iter_errors(args))
  if errors:raise ValueError('Arguments do not match discovered tool schema')
  result=self.rpc('tools/call',{'name':name,'arguments':args})
  if not isinstance(result,dict) or result.get('isError'):raise ValueError('Sorftime tool failed; no research data recorded')
  return result

def main():
 p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='cmd',required=True)
 a=sp.add_parser('catalog');a.add_argument('--output',required=True)
 a=sp.add_parser('call');a.add_argument('--capability',choices=list(ALIASES),required=True);a.add_argument('--tool',required=True);a.add_argument('--args-file',required=True);a.add_argument('--output',required=True)
 args=p.parse_args();secrets=[]
 try:
  if os.path.lexists(args.output):raise FileExistsError('Refusing existing output')
  url=endpoint();secrets=[v for k,vs in parse_qs(urlparse(url).query).items() for v in vs if k.lower() in ['key','token','api_key']]
  client=Client(url);client.initialize();tools=client.catalog()
  result=tools if args.cmd=='catalog' else client.call(args.tool,args.capability,read(args.args_file),tools)
  clean=redact(result,secrets)
  record={'mode':'live','kind':'sorftime_mcp','provider':'Sorftime','collected_at':datetime.now(timezone.utc).isoformat(),'endpoint_origin':'https://mcp.sorftime.com','tool_name':'tools/list' if args.cmd=='catalog' else args.tool,'result':clean,'response_sha256':hashlib.sha256(json.dumps(clean,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'redaction':'Credentials removed before persistence; hash is of sanitized result.'}
  write(args.output,record);print(json.dumps({'status':'collected','output':args.output,'tool_count':len(tools)}))
 except Exception as ex:
  print(redact(str(ex),secrets),file=sys.stderr);return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
