"""Create explicitly labelled test inputs, not fabricated market observations."""
from pathlib import Path
import copy
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'_shared'))
from nfwl_core import digest

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def fact(fid,key,value,source='fixture',unit='',claims=None,status='confirmed'):
    return {'id':fid,'key':key,'value':value,'unit':unit,'status':status,'source_ids':[source], 'allowed_claims':claims or []}

def create():
    d=ROOT/'tests/fixtures'
    product={'sku_id':'NFTEST-BOX-01','name':'Lidded Storage Box','category':'storage', 'sample_kind':'synthetic',
      'sources':[{'id':'fixture','type':'test_fixture','ref':'Synthetic complete product for workflow testing; not a real item or market dataset'}],
      'facts':[
       fact('f-material','material','polypropylene',claims=['Polypropylene box body']),
       fact('f-lid','lid','removable lid',claims=['Removable lid provides access to the contents']),
       fact('f-stack','stacking','stackable when closed',claims=['Closed boxes can be stacked']),
       fact('f-clean','cleaning','wipe with a damp cloth',claims=['Wipe the surface with a damp cloth']),
       fact('f-use','use','indoor shelf storage',claims=['Organize small items on indoor shelves']),
       fact('f-volume','capacity',3,unit='L'),
       fact('f-size','dimensions','25 x 18 x 10',unit='cm'),
      ], 'restrictions':[{'message':'Not certified food-contact or waterproof','patterns':['food[ -]grade','waterproof']}], 'competitor_brands':['CompetitorExample']}
    sp=[
     {'id':'sp-lid','theme':'Accessible contents','dimension':'operation','text':'Keep small items together under a removable lid that lifts away for access.','pain_point':'Small items need a defined place.','feature':'Removable lid','benefit':'Access stored items','fact_ids':['f-lid','f-use'],'status':'confirmed'},
     {'id':'sp-stack','theme':'Stacking layout','dimension':'extra','text':'Stack closed boxes to organize shelf space vertically.','pain_point':'Shelf layouts need organization.','feature':'Stackable closed boxes','benefit':'Arrange boxes vertically','fact_ids':['f-stack','f-use'],'status':'confirmed'},
     {'id':'sp-body','theme':'Box material','dimension':'material','text':'A polypropylene body provides a dedicated container for indoor organization.','pain_point':'Loose items need a container.','feature':'Polypropylene body','benefit':'Dedicated storage','fact_ids':['f-material','f-use'],'status':'confirmed'},
     {'id':'sp-care','theme':'Surface care','dimension':'operation','text':'Wipe the surface with a damp cloth as part of routine care.','pain_point':'Storage surfaces need cleaning.','feature':'Damp-cloth surface care','benefit':'Defined cleaning method','fact_ids':['f-clean'],'status':'confirmed'},
     {'id':'sp-placement','theme':'Shelf placement','dimension':'function','text':'Group small items in a box intended for indoor shelves.','pain_point':'Small objects can become scattered.','feature':'Indoor shelf storage','benefit':'Group belongings','fact_ids':['f-use'],'status':'confirmed'},
    ]
    selling={'schema_version':'1.0','product':product,'language':'en','desired_count':5}
    listing={'schema_version':'1.0','product':product,'selling_points':sp,
      'targets':[{'marketplace':'US','language':'en'},{'marketplace':'DE','language':'de'}],
      'strategies':[{'id':'organization','name':'Shelf organization','focus':'Lead with grouping small items','primary_keywords':['storage box']},
                    {'id':'access','name':'Accessible storage','focus':'Lead with removable lid and access','primary_keywords':['box with lid']}],
      'research':{'mode':'missing','sources':[],'keywords':[],'gaps':['No live MCP or user market export in this test']},
      'field_limits':{'US':{'search_terms_bytes':249},'DE':{'search_terms_bytes':249}}}
    save(d/'selling_complete.json',selling)
    save(d/'listing_multilingual.json',listing)
    reference='reference.png'  # resolved relative to the input JSON, not a personal workspace
    sauce={'sku_id':'JZJ600W-25','name':'Electric Sauce Warmer','category':'commercial sauce warmer', 'sample_kind':'real',
      'sources':[{'id':'manual-p2','type':'manual','ref':'酱汁机产品说明书.pdf page 2'},
                 {'id':'manual-p3','type':'manual','ref':'酱汁机产品说明书.pdf page 3'},
                 {'id':'manual-p4','type':'manual','ref':'酱汁机产品说明书.pdf page 4'},
                 {'id':'manual-cover','type':'manual','ref':'酱汁机产品说明书.pdf page 1 image; visual reference, capacity marking'}],
      'facts':[
       fact('s-voltage','voltage',110,'manual-p2','V'),fact('s-power','power',600,'manual-p2','W'),
       fact('s-material','material','stainless steel','manual-p2'),
       fact('s-temp','temperature_settings',[35,60,85],'manual-p2','°C',status='needs_review'),
       fact('s-heat','heating','water bath warming','manual-p2',claims=['Water bath warming']),
       fact('s-pump','dispensing','manual pump','manual-p3',claims=['Manual pump dispensing']),
       fact('s-clean','cleaning','pump parts can be disassembled and washed with mild soap and warm water','manual-p3'),
       fact('s-use','use','indoor commercial countertop use by trained personnel','manual-p4'),
       fact('s-capacity','capacity',2.65,'manual-cover','QT',status='needs_review'),
       fact('s-water','water_level','1 inch depth versus 0.5 inch below rim','manual-p2',status='conflict'),
       fact('s-dim','dimensions',None,'manual-p2',status='missing'),
      ], 'restrictions':[{'message':'No evidence for household use, timer, automatic dosing or full immersion',
                         'patterns':['household','timer','automatic dosing','fully submerg']}], 'competitor_brands':[]}
    save(d/'selling_sauce.json',{'schema_version':'1.0','product':sauce,'language':'en','desired_count':5})
    image={'schema_version':'1.0','product':sauce,'reference_assets':[{'id':'own-cover','path':reference,'role':'product'}],
           'languages':['en'],'image_requirements':[
            {'id':'main01','type':'main','objective':'White background, actual main unit only; preserve controls and pump','fact_ids':['s-material','s-pump']},
            {'id':'detail01','type':'a_plus_detail','objective':'Show actual pump connection and stainless surface; no added text','fact_ids':['s-material','s-pump'],'copy':{'en':''}},
            {'id':'size01','type':'size','objective':'Dimensions require measurement before generation','fact_ids':['s-dim']},
           ]}
    save(d/'images_sauce.json',image)
    # A synthetic market fixture is only for deterministic scoring regression.
    synthetic=copy.deepcopy(listing)
    synthetic['research']={'mode':'test_fixture','synthetic':True,'sources':[{'id':'kw-fixture','provider':'test_fixture','note':'Invented values for tests only'}],
      'keywords':[{'term':'storage box','marketplace':'US','language':'en','volume':100,'relevance':.95,'purchase_rate':None,'cpc':1,'spr':None,'source_ids':['kw-fixture']},
                  {'term':'box with lid','marketplace':'US','language':'en','volume':80,'relevance':.9,'source_ids':['kw-fixture']},
                  {'term':'wireless headphones','marketplace':'US','language':'en','volume':999999,'relevance':.1,'source_ids':['kw-fixture']}]}
    save(d/'listing_scoring_synthetic.json',synthetic)
    for name in ['nfwl-selling-points','nfwl-listing','nfwl-image-suite']:
        e=ROOT/name/'examples'
        samples={'nfwl-selling-points':['selling_complete.json','selling_sauce.json'],
                 'nfwl-listing':['listing_multilingual.json','listing_scoring_synthetic.json'],
                 'nfwl-image-suite':['images_sauce.json']}[name]
        for sample in samples:
            save(e/sample,json.loads((d/sample).read_text(encoding='utf-8')))
    print('Created labelled fixtures and portable examples')

if __name__=='__main__': create()
