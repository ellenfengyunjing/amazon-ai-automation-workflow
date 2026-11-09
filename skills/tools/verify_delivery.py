"""Verify delivered skills, protected originals, installed helpers and samples."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import re
import runpy
import subprocess
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parent
OUT=PROJECT/'output/nfwl-tests/initial'

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    # Optional dev-only packages are provided by the caller in an isolated path,
    # not installed into the project or existing skill environments.
    if len(sys.argv)>1:sys.path.insert(0,sys.argv[1])
    sys.path.insert(0,str(ROOT/'_shared'))
    import nfwl_core as n
    from contracts import SCHEMAS
    from jsonschema import Draft202012Validator
    import yaml
    manifest=n.read_json(ROOT/'nfwl-skillset.json')
    names=manifest['skills']
    validator=runpy.run_path(str(Path.home()/'.codex/skills/.system/skill-creator/scripts/quick_validate.py'))
    checks=[]
    for name in names:
        folder=ROOT/name
        good,msg=validator['validate_skill'](folder)
        if not good:raise AssertionError((name,msg))
        meta=yaml.safe_load((folder/'agents/openai.yaml').read_text(encoding='utf-8'))
        assert 25<=len(meta['interface']['short_description'])<=64
        assert '$'+name in meta['interface']['default_prompt']
        for p in folder.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if not re.match(r'^[a-z]+:',link) and not link.startswith('#'):
                    assert (p.parent/link.split('#')[0]).exists(),(p,link)
        checks.append({'skill':name,'frontmatter':'pass','metadata':'pass','relative_links':'pass'})
    for pair in SCHEMAS.values():
        for schema in pair:Draft202012Validator.check_schema(schema)
    for name,file in [('nfwl-selling-points','selling_complete.json'),('nfwl-selling-points','selling_sauce.json'),
                      ('nfwl-listing','listing_multilingual.json'),('nfwl-listing','listing_scoring_synthetic.json'),('nfwl-image-suite','images_sauce.json')]:
        Draft202012Validator(SCHEMAS[name][0]).validate(n.read_json(ROOT/'tests/fixtures'/file))
    for module,name,file in [('selling','nfwl-selling-points','selling_points.json'),('listing','nfwl-listing','listing_variants.json'),('images','nfwl-image-suite','image_results.json')]:
        Draft202012Validator(SCHEMAS[name][1]).validate(n.read_json(OUT/module/file))
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    n.write_new(OUT/'unittest-final.txt',stream.getvalue())
    assert result.wasSuccessful(),stream.getvalue()
    installer=load_module('nfwl_installer',ROOT/'tools/install_skills.py')
    installed=n.read_json(OUT/'install-result.json')
    expected=installer.hashes(ROOT,names)
    hosts=[]
    for idx,target in enumerate(installed['targets']):
        target=Path(target)
        assert installer.hashes(target,names)==expected,'Installed package mismatch: '+str(target)
        rows=[]
        commands=[
          ('selling-prepare',target/'nfwl-selling-points/scripts/nfwl.py',['prepare','--input',ROOT/'tests/fixtures/selling_complete.json']),
          ('selling-validate',target/'nfwl-selling-points/scripts/nfwl.py',['validate','--input',OUT/'selling/input.json','--result',OUT/'selling/selling_points.json']),
          ('listing-prepare',target/'nfwl-listing/scripts/nfwl.py',['prepare','--input',ROOT/'tests/fixtures/listing_multilingual.json']),
          ('listing-validate',target/'nfwl-listing/scripts/nfwl.py',['validate','--input',OUT/'listing/input.json','--result',OUT/'listing/listing_variants.json']),
          ('image-plan',target/'nfwl-image-suite/scripts/nfwl.py',['plan-images','--input',OUT/'images/input.json']),
        ]
        for label,script,args in commands:
            output=OUT/'installed-helpers'/str(idx)/(label+'.json')
            p=subprocess.run([sys.executable,'-B','-X','utf8',str(script),*[str(x) for x in args],'--output',str(output)],capture_output=True,text=True,encoding='utf-8')
            assert p.returncode==0,(label,p.stdout,p.stderr)
            rows.append({'step':label,'exit_code':p.returncode,'output':str(output)})
        hosts.append({'host':'Codex' if idx==0 else 'WorkBuddy','path':str(target),'files':'hash_match',
                      'helper_tests':rows,'host_ui_discovery':'not_verified_in_current_session',
                      'native_agent_runtime':'current Agent used skill workflow' if idx==0 else 'not_run'})
    baseline=n.read_json(OUT/'protected-files.json')
    changed=[p for p,sha in baseline.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=sha]
    assert not changed,changed
    record={
      'skills':checks,'formal_schema':'pass','unittests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},
      'hosts':hosts,'protected_files':{'count':len(baseline),'changed':changed},
      'live_tools':{'selling_points':'Agent sample completed','listing':'4 variants completed; no market validation',
                    'images':'2 real generations and exact-size exports completed',
                    'image_revision':'2 transport failures; no live revision verified',
                    'sellersprite_sif':'not_connected'},
      'image_quality':'Candidates: dial lettering needs correction; A+ detail needs high-resolution reference review; dimension slot blocked',
      'backend_frontend_configs':'unchanged'}
    n.write_new(OUT/'verification-final.json',record)
    zip_path=OUT/'nfwl-skills-v1.0.0.zip'
    with zipfile.ZipFile(zip_path,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                z.write(p,str(Path('skills')/p.relative_to(ROOT)))
    md=f'''# nfwl 首批 Skills 测试报告

## 交付

三套业务Skills，十个目录，已安装Codex和WorkBuddy。源码与安装文件逐一哈希一致。提供输入输出Schema、规则、示例、脚本、HTML报告及源码压缩包。

## 已通过

- {result.testsRun}项自动化回归，无失败或错误。
- 十个Skill的skill-creator验证、UI元数据、相对资源链接通过。
- 输入输出使用正式Draft 2020-12验证器验证通过。
- 两端安装副本各运行五项实际脚本检查通过。
- {len(baseline)}个原有项目/参考Skill文件哈希未变化。
- 卖点：酱汁机五条可追溯候选，保留水位等缺项。
- Listing：合成收纳盒，英德双语×两策略，共四条；没有虚构关键词指标。
- 组图：两次真实内置生图；交付文件分别1600×1600与970×600，原生文件保留。放大导出不冒充原生分辨率。
- 三份HTML经浏览器打开和截图检查，无脚本错误、无横向溢出。

## 未通过或未验证

- 白底候选图表盘微小文字有生成瑕疵，需要修正；A+连接细节需高清实拍核对，均未记为用户审核通过。
- 因缺少实测尺寸，尺寸图被正确阻塞，未生成假尺寸。
- 真实单图编辑连续两次连接失败，已停止；没有修订图，不能标为实时返工通过。文件非覆盖与版本保留已通过自动化测试。
- 卖家精灵/Sif未连接：没有真实市场采集测试，没有假装live。
- WorkBuddy安装和脚本通过；尚未在WorkBuddy原生Agent/内置生图中端到端运行。
- 当前聊天的宿主Skill自动发现未验证；可按安装路径读取SKILL.md测试。
- 多语种样例由当前Agent审阅，没有另请母语审核人，也没有独立盲测。

## 结果入口

- [使用指南](../../../skills/测试指南.md)
- [卖点报告](selling/report.html)
- [Listing报告](listing/report.html)
- [组图报告](images/report.html)
- [完整机器记录](verification-final.json)
- [源码包](nfwl-skills-v1.0.0.zip)

本批未开发其他业务Skills、后端或前端，未修改已有配置。详细调用示例见使用指南。
'''
    n.write_new(OUT/'测试报告.md',md)
    print(json.dumps({'tests':result.testsRun,'protected_files':len(baseline),'skills':len(names),'installed_hosts':len(hosts),'report':str((OUT/'测试报告.md').resolve())},ensure_ascii=False))

if __name__=='__main__':main()
