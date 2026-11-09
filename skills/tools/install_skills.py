"""Install only the ten new nfwl skills; refuse every pre-existing target.

Two targets are preflighted together. No global configs, aliases or old skills
are modified. A completed install includes hashes for later comparison.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"nfwl-selling-points", "nfwl-listing", "nfwl-listing-research", "nfwl-listing-strategy",
           "nfwl-listing-write", "nfwl-listing-review", "nfwl-image-suite", "nfwl-image-plan", "nfwl-image-render", "nfwl-image-review"}

def preflight(source, targets):
    names = json.loads((source/"nfwl-skillset.json").read_text(encoding="utf-8"))["skills"]
    if set(names) != ALLOWED or len(names) != len(ALLOWED):
        raise ValueError("Manifest must contain exactly the approved ten names")
    for name in names:
        skill = source/name
        if skill.is_symlink() or not (skill/"SKILL.md").is_file():
            raise ValueError("Invalid source skill: " + name)
        if any(p.is_symlink() for p in skill.rglob('*')):
            raise ValueError("Source symlinks are not portable")
    for root in targets:
        if root.is_symlink():
            raise ValueError("Target root must not be a symlink")
        for name in names:
            dest = root/name
            if dest.exists() or dest.is_symlink():
                raise FileExistsError("Refusing to overwrite: " + str(dest))
            if dest.resolve().parent != root.resolve():
                raise ValueError("Target escaped installation root")
    return names

def hashes(root, names):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for name in names for p in sorted((root/name).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}

def install(source, targets, apply=False):
    names = preflight(source, targets)
    report = {"mode":"install" if apply else "dry_run", "skills": names,
              "targets":[str(p.resolve()) for p in targets]}
    if apply:
        for root in targets:
            root.mkdir(parents=True,exist_ok=True)
            for name in names:
                # dirs_exist_ok remains False: a target appearing after preflight
                # stops the operation rather than merging into existing files.
                shutil.copytree(source/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        expected = hashes(source,names)
        report['verified'] = {str(root):hashes(root,names)==expected for root in targets}
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply',action='store_true')
    p.add_argument('--target',action='append',type=Path)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    targets=a.target or [Path.home()/'.codex/skills',Path.home()/'.workbuddy/skills']
    try:
        if a.report.exists(): raise FileExistsError('Report already exists')
        report=install(ROOT,targets,a.apply)
        a.report.parent.mkdir(parents=True,exist_ok=True)
        with a.report.open('x',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
        print(json.dumps({"mode":report['mode'],"count":len(report['skills']),"targets":report['targets']},ensure_ascii=False))
    except (OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr); return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
