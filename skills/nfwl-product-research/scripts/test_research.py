"""Synthetic forward checks; no network and no real market conclusions."""
import copy,importlib.util,io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import research as r
import sorftime_bridge as bridge
import install as installer

SKILL=Path(__file__).resolve().parents[1]
def pack():return r.read(SKILL/'references/example-fixture.json')
def first(p):return r.evaluate(p)['recommendations'][0]
def gate(p,k):return first(p)['criteria_checks'][k]

class ResearchTests(unittest.TestCase):
 def test_nominal_go_is_not_real_recommendation(self):
  x=first(pack());self.assertEqual(x['decision'],'GO');self.assertFalse(x['eligible_for_confirmation']);self.assertEqual(x['recommendation_state'],'test_only')
 def test_ratings49_and50(self):
  p=pack();p['candidates'][0]['competitors'][0]['rating_count']=49;self.assertEqual(gate(p,'ratings')['state'],'pass')
  p['candidates'][0]['competitors'][0]['rating_count']=50;self.assertEqual(gate(p,'ratings')['state'],'fail')
 def test_fbm_high_ratings_not_hidden(self):
  p=pack();x=p['candidates'][0]['competitors'][0];x['fulfillment']='FBM';x['rating_count']=100
  self.assertEqual(gate(p,'ratings')['state'],'fail')
 def test_price_boundary(self):
  p=pack();p['candidates'][0]['price_usd']=50;self.assertEqual(gate(p,'price')['state'],'pass')
  p['candidates'][0]['price_usd']=49.99;self.assertEqual(gate(p,'price')['state'],'fail')
 def test_unweighted_star_mean(self):
  p=pack();a,b=p['candidates'][0]['competitors'][:2];a['stars']=2.2;a['rating_count']=1;b['stars']=5;b['rating_count']=49
  self.assertAlmostEqual(gate(p,'stars')['value'],3.6);self.assertEqual(gate(p,'stars')['state'],'pass')
  a['stars']=2.18;self.assertEqual(gate(p,'stars')['state'],'fail')
 def test_rating_count_not_review_count(self):
  p=pack();x=p['candidates'][0]['competitors'][0];x['rating_count']=None;x['review_count']=1;x['evidence']['review_count']=['sf']
  self.assertEqual(gate(p,'ratings')['state'],'unknown')
 def test_empty_pool_not_mean_zero(self):
  p=pack();p['candidates'][0]['competitors']=[];self.assertEqual(gate(p,'stars')['state'],'unknown');self.assertIsNone(gate(p,'ratings')['value'])
 def test_effective10_and11(self):
  p=pack();c=p['candidates'][0];original=copy.deepcopy(c['competitors'][0]);alternative=c['competitors'][2]
  c['competitors']=[{**copy.deepcopy(original),'asin':f'B0NF{i:06d}'} for i in range(10)]+[alternative]
  self.assertEqual(gate(p,'effective')['value'],10);self.assertEqual(gate(p,'effective')['state'],'pass')
  c['competitors'].append({**copy.deepcopy(original),'asin':'B0NF009999'});c['coverage']['effective_pool_complete']=False
  self.assertEqual(gate(p,'effective')['state'],'fail')
 def test_parent_variants_count_once(self):
  p=pack();a,b=p['candidates'][0]['competitors'][:2]
  for x in [a,b]:x['parent_asin']='B0NF999999';x['evidence']['parent_asin']=['sf'];x['stars']=4
  self.assertEqual(gate(p,'effective')['value'],1);self.assertEqual(gate(p,'stars')['value'],4)
 def test_conflicting_parent_star_not_cherry_picked(self):
  p=pack()
  for x in p['candidates'][0]['competitors'][:2]:x['parent_asin']='B0NF999999';x['evidence']['parent_asin']=['sf']
  self.assertEqual(gate(p,'stars')['state'],'unknown')
 def test_unknown_classification_not_zero(self):
  p=pack();p['candidates'][0]['competitors'][0]['fulfillment']=None
  self.assertEqual(gate(p,'effective')['state'],'unknown');self.assertIsNone(gate(p,'effective')['value'])
 def test_partial_search_is_not_complete(self):
  p=pack();p['candidates'][0]['coverage']['effective_pool_complete']=False
  self.assertEqual(gate(p,'effective')['state'],'unknown')
 def test_no_failure_definition_or_own_baseline(self):
  for field in ['failure_rule','own_listing_source_id']:
   p=pack();p['request'].pop(field);self.assertEqual(gate(p,'failure')['state'],'unknown');self.assertEqual(first(p)['decision'],'HOLD')
 def test_unexplained_failure_dominates_missing_case(self):
  p=pack();c=p['candidates'][0];c['coverage']['failure_scan_complete']=False
  case={'comparable_listing':True,'observed_units':2,'window_days':90,'reason_status':'unexplained','evidence':{k:['sf'] for k in ['comparable_listing','observed_units','window_days','reason_status']}}
  c['failure_cases']=[case,{'evidence':{}}];self.assertEqual(gate(p,'failure')['state'],'fail')
 def test_reason_needs_explanation_and_matching_window(self):
  p=pack();case={'comparable_listing':True,'observed_units':2,'window_days':90,'reason_status':'explained','evidence':{k:['sf'] for k in ['comparable_listing','observed_units','window_days','reason_status']}}
  p['candidates'][0]['failure_cases']=[case];self.assertEqual(gate(p,'failure')['state'],'unknown')
  case['reason_text']='Synthetic documented stockout';self.assertEqual(gate(p,'failure')['state'],'pass')
  case['window_days']=30;self.assertEqual(gate(p,'failure')['state'],'unknown')
 def test_single_form_not_enough(self):
  p=pack()
  for x in p['candidates'][0]['competitors']:x['form']='bracket'
  self.assertEqual(gate(p,'forms')['state'],'fail')
 def test_proposed_advantage_is_not_verified(self):
  p=pack();p['candidates'][0]['advantage']['state']='proposed';self.assertEqual(gate(p,'advantage')['state'],'unknown')
 def test_market_data_cannot_substitute_own_proof(self):
  p=pack();p['candidates'][0]['advantage']['own_source_ids']=['sf'];self.assertEqual(gate(p,'advantage')['state'],'unknown')
 def test_unrated_zero_star_is_unknown(self):
  p=pack();p['candidates'][0]['competitors'][0]['stars']=0;self.assertEqual(gate(p,'stars')['state'],'unknown')
 def test_cross_market_and_stale(self):
  p=pack();p['sources'][0]['marketplace']='DE';self.assertEqual(gate(p,'ratings')['state'],'unknown')
  p=pack();p['sources'][0]['collected_at']='2020-01-01';self.assertEqual(gate(p,'effective')['state'],'unknown')
 def test_fake_fixture_not_accepted_in_live_mode(self):
  p=pack();p['mode']='live';self.assertFalse(first(p)['eligible_for_confirmation']);self.assertEqual(first(p)['decision'],'HOLD')
 def test_insight_without_evidence_blocks_confirmation(self):
  p=pack();p['insights'][0]['kind']='data';result=r.evaluate(p);self.assertEqual(result['qa']['gate'],'revise');self.assertFalse(result['recommendations'][0]['eligible_for_confirmation'])
 def test_unreferenced_research_numbers_not_silently_rendered(self):
  p=pack();p['research_data']['keywords']=[{'term':'TEST','volume':100}];self.assertEqual(r.evaluate(p)['qa']['gate'],'revise')
  p['research_data']['keywords'][0]['source_ids']=['sf'];self.assertEqual(r.evaluate(p)['qa']['gate'],'pass')
 def test_gate_evidence_is_specific(self):
  p=pack();x=first(p);self.assertEqual(x['criteria_checks']['price']['evidence_ids'],['sf']);self.assertIn('own',x['criteria_checks']['advantage']['evidence_ids'])
 def test_normalize_preserves_zero_and_unknown(self):
  self.assertEqual(r.normalize({'data':[{'n':0}]},{'rows_path':'data','fields':{'rating_count':'n','sales':'absent'}}),[{'rating_count':0,'sales':None}])
 def test_selector_rejects_test_and_unknown_ids(self):
  result=r.evaluate(pack())
  for ids in [[],['demo-pass'],['not-present']]:
   with self.assertRaises(ValueError):r.selection(result,ids)
 def test_html_escapes_source_text_and_never_overwrites(self):
  p=pack();p['candidates'][0]['name']='</td><script>alert(1)</script>'
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'report';r.render(p,out);h=(out/'report.html').read_text(encoding='utf-8');self.assertNotIn('<script>alert(1)</script>',h);self.assertIn('&lt;script&gt;',h)
   with self.assertRaises(FileExistsError):r.render(p,out)
 def test_three_entry_plans(self):
  for req in r.read(SKILL/'references/example-requests.json'):
   self.assertEqual(r.plan(req)['status'],'awaiting_tool_discovery')
 def test_credential_url_not_rendered(self):
  p=pack();p['sources'][0]['raw_ref']='https://mcp.sorftime.com?key=SECRET'
  with self.assertRaises(ValueError):r.evaluate(p)
 def test_install_preflight_protects_both_hosts(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a';b=Path(d)/'b';old=b/'nfwl-product-research';old.mkdir(parents=True);(old/'sentinel').write_text('KEEP')
   with self.assertRaises(FileExistsError):installer.install(SKILL,[a,b],True)
   self.assertFalse((a/'nfwl-product-research').exists());self.assertEqual((old/'sentinel').read_text(),'KEEP')
 def test_schema_contracts(self):
  from jsonschema import Draft202012Validator
  for filename in ['example-fixture.json','example-unavailable.json']:
   p=r.read(SKILL/'references'/filename);Draft202012Validator(r.read(SKILL/'references/research-pack.schema.json')).validate(p)
   Draft202012Validator(r.read(SKILL/'references/output.schema.json')).validate(r.evaluate(p))

class BridgeTests(unittest.TestCase):
 def test_http_initialize_catalog_call_session_end_to_end(self):
  class Response(io.BytesIO):
   def __init__(self,obj,headers=None,status=200):super().__init__(json.dumps(obj).encode());self.headers=headers or {'Content-Type':'application/json'};self.status=status
  responses=[Response({'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-03-26'}},{'Content-Type':'application/json','Mcp-Session-Id':'TEST_SESSION'}),Response({},status=202),Response({'jsonrpc':'2.0','id':3,'result':{'tools':[{'name':'product_detail','inputSchema':{'type':'object','required':['asin'],'properties':{'asin':{'type':'string'}}}}]}}),Response({'jsonrpc':'2.0','id':4,'result':{'content':[{'type':'text','text':'synthetic test response'}]}})]
  class Opener:
   def __init__(self):self.requests=[]
   def open(self,req,timeout):self.requests.append(req);return responses.pop(0)
  c=bridge.Client('https://mcp.sorftime.com?key=TEST');c.opener=Opener();c.initialize();tools=c.catalog();result=c.call('product_detail','product_detail',{'asin':'B0NF000001'},tools)
  self.assertEqual(result['content'][0]['text'],'synthetic test response');self.assertEqual(len(c.opener.requests),4)
  bodies=[json.loads(req.data) for req in c.opener.requests];self.assertNotIn('id',bodies[1]);self.assertEqual(bodies[-1]['method'],'tools/call');self.assertEqual(c.opener.requests[-1].get_header('Mcp-session-id'),'TEST_SESSION')
 def test_credentials_not_echoed(self):
  x=bridge.redact({'authorization':'secret','text':'https://mcp.sorftime.com?key=ABC&x=1','key':'ABC'},['ABC']);self.assertNotIn('ABC',json.dumps(x))
 def test_official_endpoint_only(self):
  with patch.dict(os.environ,{'SORFTIME_MCP_URL':'https://evil.example?key=ABC'}):
   with self.assertRaises(ValueError):bridge.endpoint()
 def test_no_config_is_not_empty_data(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaises(ValueError):bridge.endpoint()
 def test_sse_events_and_rpc_correlation(self):
  lines=['event: message\n','data: {"jsonrpc":"2.0","method":"progress"}\n','\n','data: {"jsonrpc":"2.0",\n','data: "id":7,"result":{"ok":true}}\n','\n']
  self.assertTrue(bridge.parse_sse(lines,7)['result']['ok'])
 def test_server_request_not_ignored(self):
  with self.assertRaises(ValueError):bridge.parse_sse(['data: {"id":9,"method":"elicitation/create"}\n','\n'],7)
 def test_catalog_pagination_and_repeat_detection(self):
  c=bridge.Client('https://mcp.sorftime.com');c.rpc=lambda *args:{'tools':[],'nextCursor':'repeat'}
  with self.assertRaises(ValueError):c.catalog()
 def test_unknown_tool_and_schema_rejected_before_call(self):
  c=bridge.Client('https://mcp.sorftime.com');c.rpc=lambda *a:(_ for _ in ()).throw(AssertionError('Must not make network call'))
  tools=[{'name':'product_detail','inputSchema':{'type':'object','required':['asin'],'properties':{'asin':{'type':'string'}},'additionalProperties':False}}]
  with self.assertRaises(ValueError):c.call('delete_account','product_detail',{},tools)
  with self.assertRaises(ValueError):c.call('product_detail','product_detail',{},tools)
 def test_tool_iserror_not_success(self):
  c=bridge.Client('https://mcp.sorftime.com');c.rpc=lambda *a:{'isError':True,'content':[]}
  with self.assertRaises(ValueError):c.call('product_detail','product_detail',{},[{'name':'product_detail','inputSchema':{'type':'object'}}])
 def test_initialize_and_notification(self):
  c=bridge.Client('https://mcp.sorftime.com');calls=[]
  def rpc(name,*args,**kwargs):calls.append((name,kwargs));return {'protocolVersion':'2025-03-26'}
  c.rpc=rpc;c.initialize();self.assertEqual(calls[0][0],'initialize');self.assertTrue(calls[1][1]['notify'])

if __name__=='__main__':unittest.main(verbosity=2)
