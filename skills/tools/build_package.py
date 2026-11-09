"""Build only generated resources belonging to the new nfwl directories."""
from pathlib import Path
import importlib.util
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["nfwl-selling-points", "nfwl-listing", "nfwl-listing-research", "nfwl-listing-strategy",
         "nfwl-listing-write", "nfwl-listing-review", "nfwl-image-suite", "nfwl-image-plan", "nfwl-image-render", "nfwl-image-review"]
MAINS = ["nfwl-selling-points", "nfwl-listing", "nfwl-image-suite"]

def build():
    spec = importlib.util.spec_from_file_location("nfwl_contracts", ROOT/"_shared/contracts.py")
    c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
    for name in NAMES:
        target = ROOT/name
        if not (target/"SKILL.md").is_file():
            raise RuntimeError("Missing authored skill: " + name)
        target.joinpath("agents").mkdir(exist_ok=True)
        label = {"nfwl-selling-points": "nfwl 卖点生成", "nfwl-listing": "nfwl Listing 生成", "nfwl-image-suite": "nfwl 组图生成"}.get(name, name)
        short = "基于产品资料执行本模块步骤并输出可追溯结果，支持明确缺项与局部修改"
        yaml = "interface:\n  display_name: " + json.dumps(label,ensure_ascii=False) + "\n  short_description: " + json.dumps(short,ensure_ascii=False) + "\n  default_prompt: " + json.dumps("使用 $" + name + "，根据我提供的产品资料完成任务，保留来源并标明缺项。",ensure_ascii=False) + "\n"
        (target/"agents/openai.yaml").write_text(yaml,encoding="utf-8")
    for name in MAINS:
        target = ROOT/name
        (target/"references").mkdir(exist_ok=True)
        (target/"scripts").mkdir(exist_ok=True)
        shutil.copyfile(ROOT/"_shared/nfwl_core.py", target/"scripts/_nfwl_core.py")
        (target/"scripts/nfwl.py").write_text('from pathlib import Path\nfrom _nfwl_core import cli\n\nif __name__ == "__main__":\n    raise SystemExit(cli(Path(__file__).resolve().parents[1]))\n',encoding="utf-8")
        for schema, filename in zip(c.SCHEMAS[name], ["input.schema.json", "output.schema.json"]):
            (target/"references"/filename).write_text(json.dumps(schema,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (target/"references/customer-rules.json").write_text(json.dumps(c.RULES,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"nfwl-skillset.json").write_text(json.dumps({"version":"1.0.0","skills":NAMES,"entrypoints":MAINS,
         "backend_changes":False,"external_credentials_required":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Built resources for",len(NAMES),"new skills")

if __name__ == "__main__":
    build()
