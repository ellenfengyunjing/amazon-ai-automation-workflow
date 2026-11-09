"""Materialize the current Agent-authored smoke candidates and replay checks.

Not a general LLM generator. The text below is an explicitly authored sample;
normal skill usage asks the host Agent to create new content from new inputs.
"""
from pathlib import Path
import copy
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'_shared'))
import nfwl_core as n
from contracts import RULES

OUT=ROOT.parent/'output/nfwl-tests/initial'

def save(path,value): return n.write_new(path,value)

def main():
    selling=n.read_json(ROOT/'tests/fixtures/selling_sauce.json')
    save(OUT/'selling/input.json',selling)
    context=n.prepare(selling);save(OUT/'selling/context.json',context)
    rows=[
      ('water-bath','Water-bath warming','function','Warm hot condiments with a water-bath system for commercial countertop service.','Condiments need warming during service.','Water-bath warming','Warm condiments during service',['s-heat','s-use']),
      ('manual-pump','Manual dispensing','operation','Press the manual pump to dispense warmed sauce at the service counter.','Service calls for controlled manual dispensing.','Manual pump','Dispense sauce by hand',['s-pump','s-heat','s-use']),
      ('steel','Stainless construction','material','Stainless steel construction provides the body of this countertop sauce warmer.','A dedicated warmer is needed at the counter.','Stainless steel construction','Dedicated countertop equipment',['s-material','s-use']),
      ('pump-care','Pump cleaning','operation','Disassemble the pump parts for washing with mild soap and warm water.','Pump parts require cleaning after use.','Disassemblable pump parts','Follow a defined cleaning procedure',['s-clean']),
      ('commercial','Defined operating setting','extra','Intended for indoor commercial countertop use by trained personnel.','Equipment needs a clearly defined operating setting.','Indoor commercial use','Match the product to its intended setting',['s-use']),
    ]
    points=[dict(id=i,theme=t,dimension=d,text=x,pain_point=p,feature=f,benefit=b,fact_ids=refs,status='draft') for i,t,d,x,p,f,b,refs in rows]
    result={'schema_version':'1.0','module':'selling-points','sku_id':selling['product']['sku_id'],
            'input_sha256':n.digest(selling),'selling_points':points,
            'gaps':['Water fill instructions conflict in the source manual; do not resolve automatically.',
                    'Dimensions, weight, certifications and preheating time are missing.',
                    'Capacity and temperature unit require review; no values used in these selling points.',
                    'Pain points are scenario assumptions, not claims about sampled reviews.']}
    qa=n.selling_review(selling,result,RULES)
    save(OUT/'selling/selling_points.json',result);save(OUT/'selling/qa.json',qa)
    save(OUT/'selling/report.html',n.render_report('selling',selling,result,qa))
    save(OUT/'selling/selling_points.md','# 酱汁机卖点审阅稿\n\n'+'\n\n'.join(f"{i+1}. **{p['theme']}** {p['text']}\n   证据：{', '.join(p['fact_ids'])}" for i,p in enumerate(points))+'\n\n待确认：\n'+ '\n'.join('- '+g for g in result['gaps']))
    save(OUT/'selling/semantic_review.json',{'reviewer':'Codex current Agent','state':'pass_with_gaps','observations':['Each point has a single theme and declared confirmed facts.','No timing, certification, grade or comparison claim is added.','Scenario pain points are not presented as customer research.'],'independent_review':False,'human_approval':'pending'})

    listing=n.read_json(ROOT/'tests/fixtures/listing_multilingual.json')
    save(OUT/'listing/input.json',listing);save(OUT/'listing/context.json',n.prepare(listing))
    save(OUT/'listing/strategy.json',n.keyword_strategy(listing))
    variants=[]
    en=[('lid','Lift-Off Access','Lift the removable lid to reach small items stored inside the box.','sp-lid',['f-lid','f-use']),
        ('stack','Closed-Box Stacking','Stack the boxes when closed to arrange an indoor shelf vertically.','sp-stack',['f-stack','f-use']),
        ('body','Polypropylene Body','The box body is made from polypropylene for a dedicated storage container.','sp-body',['f-material']),
        ('care','Damp-Cloth Care','Wipe the surface with a damp cloth during routine cleaning.','sp-care',['f-clean']),
        ('placement','Indoor Shelf Use','Group small belongings in a box intended for indoor shelves.','sp-placement',['f-use'])]
    de=[('lid','Abnehmbarer Deckel','Den Deckel zum Zugriff auf die aufbewahrten Kleinteile abheben.','sp-lid',['f-lid','f-use']),
        ('stack','Geschlossen stapelbar','Geschlossene Boxen aufeinander stapeln und das Innenregal vertikal ordnen.','sp-stack',['f-stack','f-use']),
        ('body','Korpus aus Polypropylen','Der Korpus besteht aus Polypropylen und dient als eigener Aufbewahrungsbehälter.','sp-body',['f-material']),
        ('care','Mit feuchtem Tuch reinigen','Die Oberfläche bei der regelmäßigen Pflege mit einem feuchten Tuch abwischen.','sp-care',['f-clean']),
        ('placement','Für Innenregale','Kleine Gegenstände in einer für Innenregale vorgesehenen Box zusammen aufbewahren.','sp-placement',['f-use'])]
    for target in listing['targets']:
        german=target['language']=='de'
        for strategy in listing['strategies']:
            organization=strategy['id']=='organization'
            order=[1,4,0,2,3] if organization else [0,2,4,1,3]
            pool=de if german else en
            chosen=[pool[i] for i in order]
            if german:
                title='Stapelbare Aufbewahrungsbox mit abnehmbarem Deckel, 3 L' if organization else 'Box mit abnehmbarem Deckel für Innenregale'
                desc=('Für ein geordnetes Innenregal: Die Box nimmt Kleinteile auf. Geschlossene Boxen können gestapelt werden. ' if organization else 'Für den Zugriff auf aufbewahrte Gegenstände wird der Deckel abgehoben. ')+ 'Das Fassungsvermögen beträgt 3 L. Die Maße sind 25 x 18 x 10 cm.'
            else:
                title='Stackable Storage Box with Removable Lid, 3 L' if organization else 'Storage Box with Removable Lid for Indoor Shelves'
                desc=('Arrange small belongings on an indoor shelf and stack closed boxes to suit the layout. ' if organization else 'Remove the lid to reach stored belongings, then replace it for storage. ')+ 'The capacity is 3 L and the dimensions are 25 x 18 x 10 cm.'
            v={'id':target['marketplace']+'-'+target['language']+'-'+strategy['id'],**target,'strategy_id':strategy['id'],'title':title,
               'bullets':[{'theme':t,'text':x,'selling_point_ids':[p]} for _,t,x,p,_ in chosen],
               'description':desc,'search_terms':'kleinteile aufbewahren ordnung' if german else 'small belongings organization',
               'evidence_map':{'title':['f-stack','f-lid','f-volume','f-use'],'description':['f-use','f-stack','f-lid','f-volume','f-size'],
                               **{f'bullets/{i}':refs for i,(_,_,_,_,refs) in enumerate(chosen)}},
               'strategy_rationale':strategy['focus']}
            variants.append(v)
    lr={'schema_version':'1.0','module':'listing','sku_id':listing['product']['sku_id'],
        'input_sha256':n.digest(listing),'listing_variants':variants,
        'gaps':['Synthetic product for workflow testing only.','No live keyword or competitor data; market validation is incomplete.']}
    lqa=n.listing_review(listing,lr,RULES)
    save(OUT/'listing/listing_variants.json',lr);save(OUT/'listing/qa.json',lqa)
    save(OUT/'listing/report.html',n.render_report('listing',listing,lr,lqa))
    save(OUT/'listing/listing.md','# 多语种多策略测试\n\n合成产品；市场未验证。\n\n'+'\n\n'.join('## '+v['id']+'\n\n'+v['title']+'\n\n'+'\n'.join('- '+b['text'] for b in v['bullets'])+'\n\n'+v['description'] for v in variants))
    save(OUT/'listing/semantic_review.json',{'reviewer':'Codex current Agent','state':'pass_with_market_gap','observations':['Four US/en and DE/de strategy combinations are present.','Organization and access strategies use different titles, bullet ordering and description lead.','No market metrics were invented; capacities and dimensions belong to the synthetic input only.'],'independent_review':False,'native_reviewer':'not performed','human_approval':'pending'})

    image=n.read_json(ROOT/'tests/fixtures/images_sauce.json')
    save(OUT/'images/input.json',image);save(OUT/'images/context.json',n.prepare(image))
    plan=n.image_plan(image)
    prompts={
      'main01':'为参考图中的商用台式酱汁保温机制作一张独立亚马逊白底商品照片。目标最终画布1600×1600正方形。只保留参考图左侧完整主机及其已经装好的桶盖和手动泵，不展示右侧额外独立酱桶、食物碗、酱料拼贴、说明书标题和页脚品牌字样。严格保留主机方箱轮廓、不锈钢表面、顶部圆形盖、黑色按压头和细长弯曲金属出料管，以及前面板左数字显示窗、中红色电源开关、右圆形灰色旋钮与红黑表盘；不得删除或增加控制件。保留本体上已有的标记，不新增任何文字或认证。不把产品改成数显设定机。完整主机居中、约85%占幅，白色RGB255背景，柔和自然接触阴影，专业真实产品摄影。不得裁切泵管，无模特、无手、无道具、无水印、无外加图形。',
      'detail01_en':'根据参考图片中的同一商用不锈钢酱汁机，生成一张横向A+工艺细节图，目标最终画布970×600。近距离真实产品摄影，主要展示顶部泵头与不锈钢桶盖连接、黑色按压头和弯曲金属出料管连接关系；左下适度露出原机方形上缘，保持真实部件数量、连接和比例。干净浅灰白背景，柔和侧光，真实不锈钢细纹。画面以产品细节为主，不需展示完整机器。不要增加分解零件或透明剖面，不画蒸汽或酱料效果。不要模特、手、食物、额外配件、认证、广告文字、品牌标题和水印。这里只表现可见结构，不声称任何钢号、容量、预热时间或性能。'
    }
    for p in plan['images']:
        if p['id'] in prompts:p['prompt']=prompts[p['id']]
    save(OUT/'images/image_plan.json',plan);save(OUT/'images/prompts.json',prompts)
    save(OUT/'images/observations.json',{'reference':'sauce-manual-cover.png','role':'product','observations':['Reference is a manufacturer-manual composite, not an isolated main image.','Square stainless steel body; top circular lid; black press head; long bent dispensing spout.','Front shows a dark rectangular display, red rocker and circular knob.','Separate bucket, food collages and manual typography are not part of the requested main image.'],'uncertain':['Steel grade, exact dimensions, display function and fill-level conflict are not resolved by the image.']})
    save(OUT/'images/visual_identity.json',{'must_keep':['Square body','Circular top lid','Black manual press head','Bent metal spout','Display/rocker/knob layout'], 'must_avoid':['Additional controls','Automatic dispensing action','Food props','Certification or grade claims'], 'confirmed_dimensions':None})
    print(json.dumps({'selling':qa['gate'],'listing':lqa['gate'],'variants':len(variants),'image_slots':len(plan['images'])}))

if __name__=='__main__':main()
