---
name: nfwl-image-suite
description: "根据产品实拍、SKU事实和已确认图片需求生成亚马逊商品组图与A+。支持客户十二类图位、内置生图、逐图质检及单图非覆盖返工，交付成图、提示词和结果清单；不管理图片需求表或图库数据库。"
---

# nfwl 组图主 Skill

当前Agent负责看图、规划、调用内置生图和查看结果。脚本只负责计划、实际像素检查、文件归档。不要把空计划或占位图当作已生成。

## 输入

读取 [input.schema.json](references/input.schema.json)、[图位规范](references/image-types.md)、[宿主执行](references/host-tools.md)。接收自然语言、图片和图片需求表确认结果，整理input.json。产品图和核心产品信息必需；请求未说明图位时询问范围，不强制默认13张。已有明确图位数量时直接执行，不重复要求确认。

reference_assets按product/style/competitor/dimension/usage区分。至少一张product为本品外观依据；竞品/风格只影响构图、视觉语言，不迁移其品牌、参数、形状或部件。尺寸只能从已确认事实取，不从比例估测。SKU事实、限制和source_ids同其他nfwl套件。

reference_assets里的相对路径以input.json所在目录为基准。当前宿主需要绝对路径时在调用查看/生图工具前解析；不因工作目录不同而换用其他图片。

## 流程

1. 将结果放新 `output/nfwl/<sku>/images/<修订>/`，用户指定目录优先。prepare检查事实与来源。
2. 执行 [nfwl-image-plan](../nfwl-image-plan/SKILL.md)，得到有完整提示词的image_plan.json、逐图观察、视觉身份与可选风格。blocked图位不发起生图。
3. 执行 [nfwl-image-render](../nfwl-image-render/SKILL.md)，仅使用宿主真实内置生图，一图一请求；保存供应商原图，不伪造脚本可调用工具的能力。
4. 执行 [nfwl-image-review](../nfwl-image-review/SKILL.md)，查看真实成图与参考；完成技术+视觉检查。失败明确原因与建议，只返工指定图位。
5. 输出image_results.json（见 [output.schema.json](references/output.schema.json)）、prompts.json、qa.json和可读结果，展示成图并给完整路径。未产生图位保留gaps，不改计划来伪装全套完成。

子Skill由当前Agent按需读取执行，或由宿主真正的Skill调用能力调度；不假定存在后端skill.invoke。不要为了执行本流程改其他Skills或连接配置。

## 返工与结果

用户给单图修改要求时读取原输入、图位、提示词、原图、视觉身份；明确改变与保持项，调用内置编辑。每次生成新文件和revision，parent_asset指向原版本。其他已生成图不重做。

```text
python <本Skill目录>/scripts/nfwl.py plan-images --input input.json --output image_plan.json
python <本Skill目录>/scripts/nfwl.py archive-image --plan image_plan.json --id main01 --source <真实生成图> --out-dir <任务目录>/assets
python <本Skill目录>/scripts/nfwl.py check-images --input input.json --plan image_plan.json --manifest image_results.json --output qa.json
```

输出必须实际测量1600×1600或970×600，不把prompt请求当作已达标。内置工具不支持精确像素时按宿主允许能力处理；没有得到正确尺寸则报告未通过，不能拉伸产品、裁掉部件或删除水印来凑验收。对本项目已授权的尺寸适配仅处理画布与等比例导出，不改产品外观，保留原图。

最终图片为待人工审核资产。事实、图位、语言、尺寸和视觉身份均绑定输入快照，交后端保存；无建库、发消息或上架动作。
