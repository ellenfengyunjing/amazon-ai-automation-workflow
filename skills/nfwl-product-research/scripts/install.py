"""Install only this new Skill, preflighting all hosts; never merge or overwrite."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
NAME='nfwl-product-research'
def tree_hash(root):return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
def install(source,targets,apply=False):
 source=Path(source).resolve()
 if source.name!=NAME or not (source/'SKILL.md').is_file():raise ValueError('Unexpected source Skill')
 if any(p.is_symlink() for p in source.rglob('*')):raise ValueError('Source links refused')
 destinations=[]
 for target in targets:
  root=Path(target).resolve();dest=root/NAME
  if os.path.lexists(dest):raise FileExistsError('Refusing pre-existing target: '+str(dest))
  if dest.parent!=root:raise ValueError('Target escapes root')
  destinations.append(dest)
 if len(set(destinations))!=len(destinations):raise ValueError('Duplicate resolved targets')
 result={'mode':'install' if apply else 'dry_run','skill':NAME,'targets':[str(p) for p in destinations]}
 if apply:
  expected=tree_hash(source)
  for dest in destinations:
   dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  result['hash_verified']={str(p):tree_hash(p)==expected for p in destinations}
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--target',action='append',required=True);p.add_argument('--apply',action='store_true');p.add_argument('--report',required=True);a=p.parse_args()
 try:
  if os.path.lexists(a.report):raise FileExistsError('Report exists')
  result=install(Path(__file__).resolve().parents[1],a.target,a.apply);Path(a.report).parent.mkdir(parents=True,exist_ok=True)
  with Path(a.report).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
  print(json.dumps(result,ensure_ascii=False))
 except (OSError,ValueError) as ex:print(str(ex),file=sys.stderr);return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
