"""Portable, stdlib-only selection gates and delivery. The Agent supplies research."""
import argparse,csv,hashlib,html,itertools,json,math,re,statistics,sys
from datetime import date,datetime
from pathlib import Path

ALIASES={
 'category_resolve':['category_search_from_product_name','category_name_search','category_search_from_top_node','search_categories_broadly'],
 'market_snapshot':['category_report','category_report_from_history'],'market_trend':['category_trend'],
 'keyword_pool':['category_keywords','keyword_extends'],'keyword_search':['keyword_search_results'],
 'keyword_metrics':['keyword_detail','keyword_trend'],'product_search':['product_search','potential_product'],
 'product_detail':['product_detail'],'product_history':['product_trend'],'reviews':['product_reviews'],
 'variants':['product_variations'],'traffic_terms':['product_traffic_terms','competitor_product_keywords'],'sourcing':['ali1688_similar_product']}
SCOPES=['industrial','parts','hardware','automotive']
STAGES=['摘要','输入与研究边界','市场与趋势','属性分布及交叉','竞品分类','关键词需求','VOC与失败排查','优势成本与风险','建议清单','证据与缺项']

def read(p):
 def bad(v):raise ValueError('Non-finite JSON number: '+v)
 return json.loads(Path(p).read_text(encoding='utf-8'),parse_constant=bad)
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:
  if isinstance(x,str):f.write(x)
  else:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def number(x):return type(x) in (int,float) and math.isfinite(x)
def safe_id(x):return isinstance(x,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',x)
def request_check(r):
 for k in ['task_id','revision','marketplace','as_of','input']:
  if k not in r:raise ValueError('request missing '+k)
 if not safe_id(r['task_id']) or not safe_id(r['revision']):raise ValueError('Unsafe task/revision identifier')
 date.fromisoformat(r['as_of'])
 if not isinstance(r['marketplace'],str) or not r['marketplace']:raise ValueError('marketplace required')
 if r['input'].get('kind') not in ['category','keyword','asin','url','sku']:raise ValueError('Unknown input kind')
 if not str(r['input'].get('value','')).strip():raise ValueError('Empty input')
 if r['input']['kind']=='asin' and not re.fullmatch('[A-Z0-9]{10}',r['input']['value']):raise ValueError('ASIN must be10 characters')
 if r.get('failure_rule') is not None:
  f=r['failure_rule']
  if not number(f.get('max_units')) or f['max_units']<0 or type(f.get('window_days')) is not int or f['window_days']<=0:raise ValueError('Invalid failure_rule')
 if type(r.get('max_source_age_days',30)) is not int or r.get('max_source_age_days',30)<0:raise ValueError('Invalid freshness window')

def plan(r):
 request_check(r);kind=r['input']['kind']
 caps=['product_detail','variants','category_resolve'] if kind in ['asin','url','sku'] else ['category_resolve','keyword_search']
 caps+=['market_snapshot','market_trend','keyword_pool','keyword_metrics','product_detail','product_history','reviews','variants']
 return {'schema_version':'1.0','task_id':r['task_id'],'revision':r['revision'],'input_sha256':digest(r),
  'capabilities':[{'capability':x,'discovery_hints':ALIASES[x],'schema_verified':False} for x in dict.fromkeys(caps)],
  'max_tool_calls':r.get('budget',{}).get('max_tool_calls',40),'status':'awaiting_tool_discovery',
  'needs_evidence':['Own listing baseline and failure_rule required for failure gate'] if not r.get('failure_rule') or not r.get('own_listing_source_id') else [],
  'note':'Tool names are discovery hints. This plan has not made any MCP call.'}

class Evidence:
 def __init__(self,p):
  self.p=p;self.r=p['request'];self.mode=p['mode'];self.sources={};self.issues=[]
  for s in p['sources']:
   if s['id'] in self.sources:raise ValueError('Duplicate source ID')
   self.sources[s['id']]=s
 def valid(self,ids,own=False):
  if not isinstance(ids,list) or not ids:return False
  for sid in ids:
   s=self.sources.get(sid)
   if not s:return False
   kind=s.get('kind')
   if s.get('synthetic') is True and self.mode!='test_fixture':return False
   allowed=['sorftime_mcp','sorftime_export']+(['user'] if own else [])+(['fixture'] if self.mode=='test_fixture' else [])
   if kind not in allowed:return False
   if kind=='sorftime_mcp' and (not s.get('tool_name') or not s.get('raw_ref')):return False
   if kind=='sorftime_export' and (not s.get('raw_ref') or not s.get('sha256')):return False
   if kind not in ['user'] and s.get('marketplace')!=self.r['marketplace']:return False
   try:age=(date.fromisoformat(self.r['as_of'])-date.fromisoformat(s['collected_at'][:10])).days
   except (KeyError,ValueError,TypeError):return False
   if age<0 or age>self.r.get('max_source_age_days',30):return False
  return True
 def get(self,obj,key,own=False):
  return obj.get(key) if self.valid(obj.get('evidence',{}).get(key),own) else None
 def coverage(self,obj,key):
  return obj.get(key) is True and self.valid(obj.get('evidence',{}).get(key)) and bool(obj.get('scope_note'))

def tri_and(values):
 if any(v is False for v in values):return False
 return True if all(v is True for v in values) else None
def check(state,value,reason,ids=None):return {'state':state,'value':value,'reason':reason,'evidence_ids':ids or []}
def threshold(value,predicate,reason):return check('unknown' if value is None else ('pass' if predicate(value) else 'fail'),value,reason)
def pack_check(p):
 if p.get('schema_version')!='1.0' or p.get('mode') not in ['live','export','unavailable','test_fixture']:raise ValueError('Invalid schema_version/mode')
 request_check(p['request'])
 if re.search(r'https?://[^\s\"]*[?&](?:key|api_key|token)=[^\s\"]+',json.dumps(p,ensure_ascii=False),re.I):raise ValueError('Credential-bearing URL refused; redact it before building research outputs')
 for key in ['sources','candidates','insights']:
  if not isinstance(p.get(key),list):raise ValueError(key+' must be array')
 ids=[]
 for c in p['candidates']:
  if not safe_id(c.get('id')):raise ValueError('Unsafe candidate ID')
  ids.append(c['id'])
  for key in ['name','category_name','competitors','coverage','evidence','advantage','failure_cases','action_plan']:
   if key not in c:raise ValueError('candidate missing '+key)
  for x in c['competitors']:
   if not re.fullmatch('[A-Z0-9]{10}',str(x.get('asin',''))):raise ValueError('Invalid competitor ASIN')
   if x.get('parent_asin') and not re.fullmatch('[A-Z0-9]{10}',str(x['parent_asin'])):raise ValueError('Invalid parent ASIN')
   for f in ['same_function','same_shape','same_material','listing_complete','competes_function']:
    if x.get(f) is not None and type(x[f]) is not bool:raise ValueError('Tri-state field must be boolean/null: '+f)
   if x.get('fulfillment') not in ['FBA','FBM','DOMESTIC_SELF','AMAZON',None]:raise ValueError('Unknown fulfillment')
   for f in ['stars','rating_count','price_usd','sales_units']:
    if x.get(f) is not None and (not number(x[f]) or x[f]<0):raise ValueError('Invalid number: '+f)
   if x.get('stars') is not None and x['stars']>5:raise ValueError('Invalid star range')
   if x.get('rating_count') is not None and type(x['rating_count']) is not int:raise ValueError('rating_count must be integer')
 if len(set(ids))!=len(ids):raise ValueError('Duplicate candidate ID')

def candidate_eval(c,ev):
 comps=c['competitors'];groups={};classified=[]
 for x in comps:
  flags=[ev.get(x,k) for k in ['same_function','same_shape','same_material']]
  same=tri_and(flags);mode=ev.get(x,'fulfillment');listing=ev.get(x,'listing_complete')
  effective=tri_and([same,None if mode is None else mode=='FBA',listing])
  parent=ev.get(x,'parent_asin');gid=parent or x['asin']
  groups.setdefault(gid,[]).append((x,same,effective))
  classified.append({'asin':x['asin'],'family_id':gid,'same_type':same,'effective':effective,'fulfillment':mode,'listing_complete':listing,'source_ids':sorted(set(itertools.chain.from_iterable(x.get('evidence',{}).values())))})
 effective=[];unknown_groups=[];same_unknown=False;same_records=[];family_stars=[]
 for gid,rows in groups.items():
  known=[x for x,s,e in rows if e is True]
  if known:
   effective.append(gid);values=[ev.get(x,'stars') for x in known]
   family_stars.append(values[0] if all(number(v) and 1<=v<=5 for v in values) and len(set(values))==1 else None)
  elif any(e is None for x,s,e in rows):unknown_groups.append(gid)
  same_unknown|=any(s is None for x,s,e in rows)
  same_records += [x for x,s,e in rows if s is True]
 cover=c['coverage'];eff_complete=ev.coverage(cover,'effective_pool_complete') and not unknown_groups
 same_complete=ev.coverage(cover,'same_type_complete') and not same_unknown
 avg=statistics.mean(family_stars) if eff_complete and family_stars and all(number(v) for v in family_stars) else None
 counts=[ev.get(x,'rating_count') for x in same_records]
 max_r=max(counts) if same_complete and counts and all(type(v) is int for v in counts) else None
 price=ev.get(c,'price_usd',own=True);price=price if number(price) and c.get('price_currency')=='USD' else None
 scope=ev.get(c,'scope_category',own=True)
 forms=set();forms_unknown=False
 for x in comps:
  competes=ev.get(x,'competes_function')
  if competes is True:
   f=ev.get(x,'form');forms_unknown|=not bool(f)
   if f:forms.add(f)
  elif competes is None:forms_unknown=True
 form_n=len(forms) if ev.coverage(cover,'forms_complete') and not forms_unknown else None
 failure_n=None;failure_lower=0;rule=ev.r.get('failure_rule');baseline=ev.r.get('own_listing_source_id')
 if rule and baseline and ev.valid([baseline],own=True) and ev.sources[baseline].get('role')=='own_product':
  failure_unknown=False
  for case in c['failure_cases']:
   comparable=ev.get(case,'comparable_listing')
   if comparable is False:continue
   units=ev.get(case,'observed_units');days=ev.get(case,'window_days')
   if comparable is None or not number(units) or days!=rule['window_days']:
    failure_unknown=True;continue
   if units<=rule['max_units']:
    reason=ev.get(case,'reason_status')
    if reason=='unexplained':failure_lower+=1
    elif reason!='explained' or not case.get('reason_text'):
     failure_unknown=True
  if failure_lower>0:failure_n=failure_lower
  elif not failure_unknown and ev.coverage(cover,'failure_scan_complete'):failure_n=0
 adv=c['advantage'];adv_state=ev.get(adv,'state',own=True)
 own_ids=adv.get('own_source_ids',[])
 own_proof=ev.valid(own_ids,own=True) and all(ev.sources[sid].get('role')=='own_product' for sid in own_ids)
 adv_ok=True if adv_state=='verified' and adv.get('claim') and own_proof and ev.valid(adv.get('baseline_source_ids')) else None
 if adv_state=='disproven':adv_ok=False
 gates={
 'scope':threshold(None if scope is None else scope in SCOPES,lambda x:x,'限定工业用品/配件/五金/汽配'),
 'stars':threshold(avg,lambda x:x>=3.6,'有效同款星级简单平均≥3.6，产品族每组一次'),
 'failure':threshold(failure_n,lambda x:x==0,'可比低销且原因未解案例为0；无口径/基准不能判0'),
 'ratings':threshold(max_r,lambda x:x<50,'全部同款最高rating_count<50，不以review_count替代'),
 'price':threshold(price,lambda x:x>=50,'售价≥50 USD（以上含50），保留价格及换算依据'),
 'effective':threshold(len(effective) if eff_complete else None,lambda x:x<=10,'同款且FBA、Listing齐全，产品族去重≤10'),
 'forms':threshold(form_n,lambda x:x>=2,'至少2种有证据的功能竞争形态'),
 'advantage':threshold(adv_ok,lambda x:x,'本品及对照证据支撑的明显优势')}
 # A known disqualifier is decisive even when coverage is incomplete.
 known_max=[v for v in counts if type(v) is int]
 if known_max and max(known_max)>=50:gates['ratings']=check('fail',max(known_max),'已发现同款rating_count≥50，无需等补全才拒绝')
 if len(effective)>10:gates['effective']=check('fail',len(effective),'已知有效竞品已超过10，覆盖不足不能抵消已知失败')
 def refs(obj,fields):
  return [sid for field in fields for sid in obj.get('evidence',{}).get(field,[]) if ev.valid([sid],own=True)]
 class_fields=['same_function','same_shape','same_material','fulfillment','listing_complete','parent_asin']
 classification_ids=[sid for x in comps for sid in refs(x,class_fields)]
 gate_ids={
  'scope':refs(c,['scope_category']),
  'stars':classification_ids+[sid for x in comps for sid in refs(x,['stars'])]+refs(cover,['effective_pool_complete']),
  'ratings':[sid for x in comps for sid in refs(x,['same_function','same_shape','same_material','rating_count'])]+refs(cover,['same_type_complete']),
  'price':refs(c,['price_usd']),
  'effective':classification_ids+refs(cover,['effective_pool_complete']),
  'forms':[sid for x in comps for sid in refs(x,['competes_function','form'])]+refs(cover,['forms_complete']),
  'failure':[sid for x in c['failure_cases'] for sid in refs(x,['comparable_listing','observed_units','window_days','reason_status'])]+refs(cover,['failure_scan_complete'])+([baseline] if baseline and ev.valid([baseline],own=True) else []),
  'advantage':refs(adv,['state'])+[sid for sid in adv.get('own_source_ids',[])+adv.get('baseline_source_ids',[]) if ev.valid([sid],own=True)]}
 for key,g in gates.items():g['evidence_ids']=sorted(set(gate_ids[key]))
 all_ids=sorted(set(itertools.chain.from_iterable(gate_ids.values())))
 verdict='NO_GO' if any(g['state']=='fail' for g in gates.values()) else ('HOLD' if any(g['state']=='unknown' for g in gates.values()) else 'GO')
 state='rejected' if verdict=='NO_GO' else ('needs_evidence' if verdict=='HOLD' else 'recommended')
 if ev.mode=='test_fixture':state='test_only'
 if ev.mode=='unavailable' and state=='recommended':state='needs_evidence';verdict='HOLD'
 return {'candidate_id':c['id'],'name':c['name'],'category_name':c['category_name'],'decision':verdict,'recommendation_state':state,
  'eligible_for_confirmation':state=='recommended' and ev.mode in ['live','export'],'human_approval':'pending','price_usd':price,
  'metrics':{'effective_known':len(effective),'effective_unknown_families':len(unknown_groups),'effective_count':gates['effective']['value'],'average_stars':avg,'max_rating_count':gates['ratings']['value'],'competing_form_count':form_n},
  'criteria_checks':gates,'competitor_classification':classified,'action_plan':c['action_plan'],
  'evidence_ids':all_ids,'needs_evidence':[k for k,g in gates.items() if g['state']=='unknown']}

def evaluate(p):
 pack_check(p);ev=Evidence(p);rows=[candidate_eval(c,ev) for c in p['candidates']]
 issues=[]
 def check_numbers(node,path,inherited=None):
  if isinstance(node,dict):
   local=node.get('evidence_ids',node.get('source_ids',inherited))
   for k,v in node.items():
    if k not in ['source_ids','evidence_ids']:check_numbers(v,path+'/'+k,local)
  elif isinstance(node,list):
   for n,v in enumerate(node):check_numbers(v,path+'/'+str(n),inherited)
  elif number(node) and not ev.valid(inherited,own=True):issues.append({'path':path,'message':'Research numeric data needs source_ids/evidence_ids'})
 check_numbers(p.get('research_data',{}),'research_data')
 for i,s in enumerate(p['insights']):
  if s.get('kind') not in ['data','inference','hypothesis','proposal']:issues.append({'path':f'insights/{i}','message':'Unknown insight kind'})
  if s.get('kind') in ['data','inference'] and not ev.valid(s.get('evidence_ids',[]),own=True):issues.append({'path':f'insights/{i}','message':'Data/inference needs valid evidence'})
  if type(s.get('section')) is not int or not 1<=s['section']<=10:issues.append({'path':f'insights/{i}','message':'section must be1..10'})
 if issues:
  for row in rows:row['eligible_for_confirmation']=False
 return {'schema_version':'1.0','module':'product-research','task_id':p['request']['task_id'],'revision':p['request']['revision'],
  'input_sha256':digest(p),'mode':p['mode'],'as_of':p['request']['as_of'],'marketplace':p['request']['marketplace'],
  'recommendations':rows,'sources':p['sources'],'insights':p['insights'],'research_data':p.get('research_data',{}),
  'qa':{'gate':'revise' if issues else 'pass','issues':issues,'semantic_review':'required','human_approval':'pending','live_mcp_verified':False,'verification_scope':'Declared evidence and rules only; real collection must be verified separately by the Agent',
  'limits':'Gate checks validate declared evidence and thresholds, not source authenticity, market exhaustiveness or causal claims.'}}

def selection(result,ids):
 rows={r['candidate_id']:r for r in result['recommendations']}
 if not ids or len(set(ids))!=len(ids) or any(i not in rows or not rows[i]['eligible_for_confirmation'] for i in ids):raise ValueError('Only eligible, unique candidate IDs can be proposed for confirmation')
 return {'type':'nfwl.research.selection','task_id':result['task_id'],'revision':result['revision'],'input_sha256':result['input_sha256'],'candidate_ids':ids,'human_approval':'pending'}

def at(obj,path):
 for k in path.split('.') if path else []:
  if not isinstance(obj,dict) or k not in obj:return None
  obj=obj[k]
 return obj
def normalize(raw,mapping):
 rows=at(raw,mapping['rows_path'])
 if not isinstance(rows,list):raise ValueError('rows_path is not an array; inspect actual tool result')
 return [{target:at(row,path) for target,path in mapping['fields'].items()} for row in rows]

def show(v):return '获取不到' if v is None else str(v)
def esc(v):return html.escape(show(v),quote=True)
def table(headers,rows):return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in r)+'</tr>' for r in rows)+'</tbody></table></div>'

def data_view(data):
 if data is None:return '<p class="missing">获取不到</p>'
 if isinstance(data,list):
  if not data:return '<p class="missing">无已取得记录</p>'
  if all(isinstance(v,dict) for v in data):
   keys=list(dict.fromkeys(k for v in data for k in v))
   return table(keys,[[json.dumps(v.get(k),ensure_ascii=False) if isinstance(v.get(k),(list,dict)) else v.get(k) for k in keys] for v in data])
  return '<ul>'+''.join('<li>'+esc(v)+'</li>' for v in data)+'</ul>'
 if isinstance(data,dict):
  scalars={k:v for k,v in data.items() if not isinstance(v,(dict,list))}
  return (table(['字段','数值/状态'],list(scalars.items())) if scalars else '')+''.join('<details open><summary>'+esc(k)+'</summary>'+data_view(v)+'</details>' for k,v in data.items() if isinstance(v,(dict,list)))
 return '<p>'+esc(data)+'</p>'

def render(p,out):
 result=evaluate(p);out=Path(out)
 if out.exists():raise FileExistsError('Use a new deliverable directory')
 out.mkdir(parents=True)
 rows=result['recommendations'];ev=Evidence(p)
 contract={'type':'nfwl.research.selection','required':['task_id','revision','input_sha256','candidate_ids'],'human_approval':'pending','backend_must_revalidate':True}
 write(out/'research_result.json',result);write(out/'recommendations.json',rows);write(out/'qa.json',result['qa']);write(out/'selection_contract.json',contract)
 with (out/'recommendations.csv').open('x',encoding='utf-8-sig',newline='') as f:
  fields=['candidate_id','name','category_name','decision','recommendation_state','price_usd','eligible_for_confirmation','needs_evidence']
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:(';'.join(r[k]) if isinstance(r[k],list) else r[k]) for k in fields} for r in rows)
 template=(Path(__file__).resolve().parents[1]/'assets/report.html').read_text(encoding='utf-8')
 sections=[];md=[f'# nfwl选品报告 / {result["task_id"]}',f'模式：{result["mode"]}；站点：{result["marketplace"]}；日期：{result["as_of"]}。人工待确认。']
 for n,title in enumerate(STAGES,1):
  body=''
  if n==1:
   counts={s:sum(r['recommendation_state']==s for r in rows) for s in ['recommended','needs_evidence','rejected','test_only']}
   body=table(['建议做','待验证','不建议','测试行'],[[counts[s] for s in counts]])
  if n==2:body=table(['输入类型','输入','站点','模式'],[[p['request']['input']['kind'],p['request']['input']['value'],result['marketplace'],result['mode']]])+''.join('<p>'+esc(c.get('coverage',{}).get('scope_note'))+'</p>' for c in p['candidates'])
  if n==4:
   pairs=[]
   for c in p['candidates']:
    # ASIN-level declared sample distribution, explicitly distinct from family gates.
    distinct={x['asin']:x for x in c['competitors']}
    vals={}
    for x in distinct.values():
     key=(ev.get(x,'form'),ev.get(x,'material'));vals[key]=vals.get(key,0)+1
    pairs.extend([c['name'],form,mat,count] for (form,mat),count in vals.items())
   body=table(['方案','形态','材质','已读ASIN样本数'],pairs)+'<p>这是已读样本的交叉计数，未知属性单独显示；不等于市场份额或真实需求缺口。</p>'
  if n==5:
   cr=[]
   for c,r in zip(p['candidates'],rows):
    idx={x['asin']:x for x in c['competitors']}
    cr.extend([r['name'],x['asin'],x['family_id'],x['same_type'],x['effective'],x['fulfillment'],ev.get(idx[x['asin']],'stars'),ev.get(idx[x['asin']],'rating_count')] for x in r['competitor_classification'])
   body=table(['方案','ASIN','产品族','同款','有效','履约','星级','rating数'],cr)
  if n in [3,6,7,8]:
   key={3:'market',6:'keywords',7:'voc_and_failures',8:'risks_and_economics'}[n]
   data=p.get('research_data',{}).get(key)
   body=data_view(data)
  if n==9:
   body='<div class="filters"><label>筛选 <select id="filter"><option value="all">全部</option>'+''.join('<option>'+s+'</option>' for s in ['recommended','needs_evidence','rejected','test_only'])+'</select></label><button id="download">下载选择JSON</button><button id="send">提交给父页面确认</button><span id="notice">离线预览，不会写入SKU库</span></div><div class="scroll"><table><thead><tr><th>选择</th><th>方案/类目</th><th>判断</th><th>价格USD</th><th>待验证</th></tr></thead><tbody>'
   for r in rows:
    body+=f'<tr data-state="{esc(r["recommendation_state"])}"><td><input type="checkbox" value="{esc(r["candidate_id"])}" '+('' if r['eligible_for_confirmation'] else 'disabled')+f'></td><td>{esc(r["name"])} / {esc(r["category_name"])}</td><td>{esc(r["decision"])} · {esc(r["recommendation_state"])}</td><td>{esc(r["price_usd"])}</td><td>{esc(", ".join(r["needs_evidence"]))}</td></tr>'
   body+='</tbody></table></div>'
   for r in rows:
    body+='<details><summary>'+esc(r['name'])+' / 逐条关卡与执行方案</summary>'+table(['条件','状态','值','说明'],[[k,g['state'],g['value'],g['reason']] for k,g in r['criteria_checks'].items()])+'<pre>'+esc(json.dumps(r['action_plan'],ensure_ascii=False,indent=2))+'</pre></details>'
  if n==10:body=table(['来源ID','来源类型','工具','采集时间','周期','文件/链接'],[[s['id'],s.get('kind'),s.get('tool_name'),s.get('collected_at'),s.get('period'),s.get('raw_ref')] for s in p['sources']])+'<p>未覆盖、未知、未返回不能当0；原始来源含供应商估算时须标注。凭证不得进入报告。</p>'
  insights=[s for s in p['insights'] if s.get('section')==n]
  body+=''.join('<article class="insight"><strong>'+esc(s['kind'])+'</strong><p>'+esc(s.get('finding'))+'</p><p>含义：'+esc(s.get('meaning'))+'</p><p>行动：'+esc(s.get('action'))+'</p><small>依据：'+esc(', '.join(s.get('evidence_ids',[])))+'</small></article>' for s in insights)
  if not insights:body+='<p class="missing">此节尚无已完成的Agent洞察；数据不足时应补来源或说明获取不到，不能把空白视为研究结论。</p>'
  sections.append('<section id="s'+str(n)+'"><h2>'+str(n)+'. '+title+'</h2>'+body+'</section>')
  md+=['## '+str(n)+'. '+title]+[f"- [{s['kind']}] {s.get('finding')} → {s.get('meaning')} → {s.get('action')}；证据：{s.get('evidence_ids',[])}" for s in insights]
  if not insights:md+=['获取不到已完成的分析洞察，需补研究。']
 md+=['## 方案明细','```json',json.dumps(rows,ensure_ascii=False,indent=2),'```','完整来源、结构表及证据见research_result.json；最终统计以该JSON为准。']
 safe_json=json.dumps({'task_id':result['task_id'],'revision':result['revision'],'input_sha256':result['input_sha256']},ensure_ascii=False).replace('<','\\u003c').replace('&','\\u0026')
 page=template.replace('@@TITLE@@',esc(result['task_id'])).replace('@@MODE@@',esc(result['mode'])).replace('@@BODY@@',''.join(sections)).replace('@@META@@',safe_json)
 write(out/'report.html',page);write(out/'report.md','\n\n'.join(md))
 return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);sp=ap.add_subparsers(dest='cmd',required=True)
 for cmd in ['plan','evaluate']:
  a=sp.add_parser(cmd);a.add_argument('--input',required=True);a.add_argument('--output',required=True)
 a=sp.add_parser('render');a.add_argument('--input',required=True);a.add_argument('--out-dir',required=True)
 a=sp.add_parser('normalize');a.add_argument('--raw',required=True);a.add_argument('--mapping',required=True);a.add_argument('--output',required=True)
 a=sp.add_parser('select');a.add_argument('--input',required=True);a.add_argument('--candidate',action='append',required=True);a.add_argument('--output',required=True)
 args=ap.parse_args()
 try:
  if args.cmd=='plan':write(args.output,plan(read(args.input)))
  elif args.cmd=='evaluate':write(args.output,evaluate(read(args.input)))
  elif args.cmd=='render':render(read(args.input),args.out_dir)
  elif args.cmd=='normalize':write(args.output,normalize(read(args.raw),read(args.mapping)))
  elif args.cmd=='select':write(args.output,selection(read(args.input),args.candidate))
  print(json.dumps({'command':args.cmd,'status':'completed','live_collection_performed':False}))
 except (ValueError,KeyError,TypeError,OSError) as exc:print(str(exc),file=sys.stderr);return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
