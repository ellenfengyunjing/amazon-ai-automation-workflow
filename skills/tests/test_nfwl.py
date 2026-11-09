import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'_shared'))
import nfwl_core as n
from contracts import RULES,SCHEMAS

def fixture(name): return n.read_json(ROOT/'tests/fixtures'/name)
def selling_result(req):
    base=fixture('listing_multilingual.json')['selling_points']
    points=copy.deepcopy(base)
    for p in points: p['status']='draft'
    return {'schema_version':'1.0','module':'selling-points','sku_id':req['product']['sku_id'],
            'input_sha256':n.digest(req),'selling_points':points,'gaps':[]}
def variant_result(req):
    variants=[]
    for target in req['targets']:
        for strategy in req['strategies']:
            de=target['language']=='de'
            title=('Aufbewahrungsbox mit Deckel für Regale' if de else 'Storage Box with Removable Lid for Shelves')
            if strategy['id']=='access': title='Box mit abnehmbarem Deckel zur Aufbewahrung' if de else 'Box with Removable Lid for Accessible Shelf Storage'
            text_de=['Der abnehmbare Deckel lässt sich zum Zugriff auf den Inhalt anheben.',
                     'Geschlossene Boxen lassen sich aufeinander stapeln.',
                     'Der Korpus besteht aus Polypropylen.',
                     'Die Oberfläche kann mit einem feuchten Tuch abgewischt werden.',
                     'Kleine Gegenstände lassen sich für die Aufbewahrung auf Innenregalen gruppieren.']
            texts=text_de if de else [p['text'] for p in req['selling_points']]
            refs=[['f-lid','f-use'],['f-stack'],['f-material'],['f-clean'],['f-use']]
            variants.append({'id':target['marketplace']+'-'+target['language']+'-'+strategy['id'],**target,'strategy_id':strategy['id'],
              'title':title,'bullets':[{'theme':p['theme'],'text':t,'selling_point_ids':[p['id']]} for p,t in zip(req['selling_points'],texts)],
              'description':'Für kleine Gegenstände auf Regalen in Innenräumen vorgesehen.' if de else 'Intended for organizing small belongings on indoor shelves.',
              'search_terms':'kleinteile ordnung' if de else 'small belongings organization',
              'evidence_map':{'title':['f-lid','f-use'],'description':['f-use'],**{f'bullets/{i}':r for i,r in enumerate(refs)}},
              'strategy_rationale':strategy['focus']})
    return {'schema_version':'1.0','module':'listing','sku_id':req['product']['sku_id'],'input_sha256':n.digest(req),'listing_variants':variants,'gaps':['Market data missing']}

class ContentTests(unittest.TestCase):
    def setUp(self):
        self.s=fixture('selling_complete.json'); self.l=fixture('listing_multilingual.json')
    def codes(self,qa): return {x['code'] for x in qa['issues']}
    def test_complete_selling_without_competitors(self):
        r=selling_result(self.s)
        self.assertEqual(n.selling_review(self.s,r,RULES)['gate'],'pass')
        self.assertFalse(n.schema_errors(r,SCHEMAS['nfwl-selling-points'][1]))
    def test_missing_source_cannot_support_fact(self):
        self.s['product']['facts'][0]['source_ids']=[]
        self.assertIn('missing_source',self.codes(n.selling_review(self.s,selling_result(self.s),RULES)))
    def test_invented_certification_absolute_claim(self):
        r=selling_result(self.s); r['selling_points'][0]['text']='Best FDA 304 food-grade waterproof box forever'
        codes=self.codes(n.selling_review(self.s,r,RULES))
        self.assertTrue({'forbidden_term','unsupported_claim','product_restriction'}.issubset(codes))
    def test_localized_absolute_claim(self):
        r=variant_result(self.l);r['listing_variants'][2]['title']='Beste Box für immer'
        self.assertIn('forbidden_term',self.codes(n.listing_review(self.l,r,RULES)))
    def test_wrong_unit_same_number_is_rejected(self):
        req=fixture('selling_sauce.json')
        issues=n.check_claim('600 ml capacity',['s-power'],req,RULES,'text')
        self.assertIn('unsupported_quantity',{i['code'] for i in issues})
    def test_ingress_rating_cannot_be_upgraded(self):
        req=copy.deepcopy(self.s)
        req['product']['facts'].append({'id':'ip','key':'ingress','value':'IP44','status':'confirmed','source_ids':['fixture']})
        self.assertIn('unsupported_claim',{x['code'] for x in n.check_claim('IP67',['ip'],req,RULES,'text')})
    def test_certifications_are_not_interchangeable(self):
        req=copy.deepcopy(self.s)
        req['product']['facts'].append({'id':'cert','key':'certification','value':'FCC','status':'confirmed','source_ids':['fixture']})
        self.assertIn('unsupported_claim',{x['code'] for x in n.check_claim('FDA',['cert'],req,RULES,'text')})
    def test_temperature_unit_is_not_emoji(self):
        req=fixture('selling_sauce.json')
        next(f for f in req['product']['facts'] if f['id']=='s-temp')['status']='confirmed'
        codes={x['code'] for x in n.check_claim('35 °C',['s-temp'],req,RULES,'text')}
        self.assertNotIn('decorative_symbol',codes);self.assertNotIn('unsupported_quantity',codes)
    def test_invented_number_rejected(self):
        r=selling_result(self.s); r['selling_points'][0]['text']='Stores 200 items'
        self.assertIn('unsupported_number',self.codes(n.selling_review(self.s,r,RULES)))
    def test_confirmed_by_model_rejected(self):
        r=selling_result(self.s); r['selling_points'][0]['status']='confirmed'
        self.assertIn('unauthorized_approval',self.codes(n.selling_review(self.s,r,RULES)))
    def test_benefit_cannot_smuggle_unsupported_certification(self):
        r=selling_result(self.s);r['selling_points'][0]['benefit']='FDA food-grade assurance'
        self.assertIn('unsupported_claim',self.codes(n.selling_review(self.s,r,RULES)))
    def test_input_binding_rejected(self):
        r=selling_result(self.s); r['sku_id']='other'
        self.assertIn('sku_mismatch',self.codes(n.selling_review(self.s,r,RULES)))
        r['sku_id']=self.s['product']['sku_id']; r['input_sha256']='outdated'
        self.assertIn('input_version_mismatch',self.codes(n.selling_review(self.s,r,RULES)))
    def test_four_language_strategy_variants(self):
        r=variant_result(self.l)
        self.assertEqual(len(r['listing_variants']),4)
        q=n.listing_review(self.l,r,RULES)
        self.assertEqual(q['gate'],'pass',q)
        self.assertFalse(q['market_validated'])
    def test_title_boundaries(self):
        r=variant_result(self.l); r['listing_variants'][0]['title']='x'*75
        self.assertNotIn('title_length',self.codes(n.listing_review(self.l,r,RULES)))
        r['listing_variants'][0]['title']='x'*76
        self.assertIn('title_length',self.codes(n.listing_review(self.l,r,RULES)))
    def test_repeated_keyword_and_four_bullets(self):
        r=variant_result(self.l); v=r['listing_variants'][0]
        v['title']='Box box box'; v['bullets'].pop()
        codes=self.codes(n.listing_review(self.l,r,RULES))
        self.assertTrue({'title_repeat','bullet_count'}.issubset(codes))
    def test_description_copy_rejected(self):
        r=variant_result(self.l); r['listing_variants'][0]['description']=r['listing_variants'][0]['bullets'][0]['text']
        self.assertIn('description_copy',self.codes(n.listing_review(self.l,r,RULES)))
    def test_unconfirmed_selling_points_rejected(self):
        self.l['selling_points'][0]['status']='draft'
        self.assertIn('unapproved_selling_point',self.codes(n.listing_review(self.l,variant_result(self.l),RULES)))
    def test_missing_duplicate_combinations(self):
        r=variant_result(self.l); r['listing_variants'][1]=copy.deepcopy(r['listing_variants'][0])
        codes=self.codes(n.listing_review(self.l,r,RULES))
        self.assertTrue({'duplicate_variant','missing_variant'}.issubset(codes))
    def test_duplicate_frontend_id_is_rejected(self):
        r=variant_result(self.l);r['listing_variants'][1]['id']=r['listing_variants'][0]['id']
        self.assertIn('duplicate_variant_id',self.codes(n.listing_review(self.l,r,RULES)))
    def test_utf8_byte_limit(self):
        r=variant_result(self.l); r['listing_variants'][0]['search_terms']='ä'*125
        self.assertIn('search_terms_bytes',self.codes(n.listing_review(self.l,r,RULES)))
    def test_research_missing_and_fixture_not_verified(self):
        self.assertFalse(n.research_valid(self.l['research']))
        f=fixture('listing_scoring_synthetic.json')
        self.assertFalse(n.keyword_strategy(f)['market_validated'])
        self.assertEqual(n.keyword_strategy(f)['excluded'][0]['term'],'wireless headphones')
    def test_unknown_source_not_market_verified(self):
        p=fixture('listing_scoring_synthetic.json')['research']; p['mode']='export'; p['synthetic']=False
        p['keywords'][0]['source_ids']=['invented']
        self.assertFalse(n.research_valid(p))
    def test_missing_metrics_weights_are_renormalized(self):
        row=n.keyword_strategy(fixture('listing_scoring_synthetic.json'))['groups'][0]['keywords'][0]
        self.assertIn('purchase_rate',row['missing_metrics'])
        self.assertAlmostEqual(sum(row['effective_weights'].values()),1,places=3)
    def test_html_escapes_injected_markup(self):
        r=variant_result(self.l); r['listing_variants'][0]['title']='<script>alert(1)</script>'
        report=n.render_report('listing',self.l,r,n.listing_review(self.l,r,RULES))
        self.assertNotIn('<script>',report); self.assertIn('&lt;script&gt;',report)
    def test_schema_rejects_malformed_evidence_map(self):
        r=variant_result(self.l); r['listing_variants'][0]['evidence_map']['title']='not-an-array'
        self.assertTrue(n.schema_errors(r,SCHEMAS['nfwl-listing'][1]))
    def test_import_export_relevance_not_invented(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'keywords.csv'; p.write_text('关键词,月搜索量,购买率\nbox,100,12%\n',encoding='utf-8')
            pack=n.import_keywords(p,'user-export','US','en')
            self.assertEqual(pack['keywords'][0]['purchase_rate'],.12)
            self.assertEqual(pack['keywords'][0]['relevance'],0)
    def test_nonfinite_metric_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'keywords.csv';p.write_text('keyword,volume\nbox,NaN\n',encoding='utf-8')
            with self.assertRaises(ValueError):n.import_keywords(p,'user-export','US','en')
    def test_sauce_conflicts_stay_unresolved(self):
        context=n.prepare(fixture('selling_sauce.json'))
        self.assertNotIn('s-water',{f['id'] for f in context['usable_facts']})
        self.assertNotIn('s-dim',{f['id'] for f in context['usable_facts']})

class ImageTests(unittest.TestCase):
    def setUp(self): self.req=fixture('images_sauce.json')
    def test_size_slot_blocked_other_slots_ready(self):
        p=n.image_plan(self.req); states={i['slot_id']:i['state'] for i in p['images']}
        self.assertEqual(states,{'main01':'ready','detail01':'ready','size01':'blocked'})
        detail=next(i for i in p['images'] if i['slot_id']=='detail01')
        self.assertEqual([detail['width'],detail['height']],[970,600])
    def test_main_not_duplicated_for_languages(self):
        self.req['languages']=['en','de']
        p=n.image_plan(self.req)
        self.assertEqual(len([x for x in p['images'] if x['type']=='main']),1)
    def test_no_product_reference_blocks_generation(self):
        self.req['reference_assets'][0]['role']='competitor'
        self.assertTrue(all(x['state']=='blocked' for x in n.image_plan(self.req)['images']))
    def test_unsafe_slot_identifier_blocked(self):
        self.req['image_requirements'][0]['id']='../escaped'
        self.assertEqual(n.image_plan(self.req)['images'][0]['state'],'blocked')
    def test_a_plus_unnamed_competitor_still_blocked(self):
        self.req['image_requirements']=[{'id':'compare','type':'a_plus_comparison','objective':'Anonymous competitor','fact_ids':['s-material'],'comparison_scope':'alternative'}]
        self.assertEqual(n.image_plan(self.req)['images'][0]['state'],'blocked')
    def test_revision_preserves_original_and_other_images(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source.png'; Image.new('RGB',(1600,1600),'white').save(source)
            plan=n.image_plan(self.req)
            a=n.archive_image(plan,'main01',source,root/'out')
            b=n.archive_image(plan,'main01',source,root/'out',a['path'])
            self.assertEqual(b['revision'],2); self.assertEqual(Path(a['path']).read_bytes(),source.read_bytes())
            self.assertNotEqual(a['path'],b['path'])
    def test_wrong_pixels_and_visual_pending(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wrong.png'; Image.new('RGB',(1024,1024)).save(path)
            plan=n.image_plan(self.req)
            manifest={'sku_id':self.req['product']['sku_id'],'input_sha256':n.digest(self.req),'images':[{'id':'main01','path':str(path)}]}
            q=n.image_technical_review(self.req,plan,manifest)
            self.assertIn('pixel_size',{i['code'] for i in q['issues']})
            self.assertIn('visual_review_pending',{i['code'] for i in q['issues']})
            self.assertFalse(q['complete'])

class InstallationTests(unittest.TestCase):
    def test_no_overwrite_and_cross_target_preflight(self):
        spec=importlib.util.spec_from_file_location('installer',ROOT/'tools/install_skills.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'codex',Path(d)/'workbuddy'
            existing=b/'nfwl-listing';existing.mkdir(parents=True); sentinel=existing/'sentinel';sentinel.write_text('preserve')
            with self.assertRaises(FileExistsError):m.install(ROOT,[a,b],True)
            self.assertFalse(a.exists());self.assertEqual(sentinel.read_text(),'preserve')

if __name__=='__main__': unittest.main(verbosity=2)
