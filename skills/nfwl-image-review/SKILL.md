---
name: nfwl-image-review
description: "逐张检查nfwl真实成图的产品保真、文字、图位规则和实际像素，提供定位明确的返工指令。技术检查、视觉检查与人工确认分别记录。"
---

# nfwl 图片质检

读取input.json、image_plan.json、image_results.json和 [图位规则](../nfwl-image-suite/references/image-types.md)。

1. 查看每张真实成图与本品参考，不能从prompt判断已合格。记录形状、部件、颜色、标识、数量、尺度、背景、文字和操作的具体观察。
2. 有文字时核对每个数字和原文；OCR可用时辅助，无法确认时转待审，不能默认正确。
3. 每张visual_review填写state、reviewer、notes、issues；问题含code、path、message、severity。只有实际观察支持才能填pass，不给虚假总分。
4. `python <nfwl-image-suite目录>/scripts/nfwl.py check-images --input input.json --plan image_plan.json --manifest image_results.json --output qa.json`。检查真实文件宽高、颜色、缺图；技术通过不能代替视觉通过。
5. 每个失败图位给返工原因、准确修改、参考需求，保留keep图；交主Skill汇总。blocked图位仍缺资料时说明，而不是说全套通过。

主图额外检查纯白、完整、居中、约85%视觉占幅、无附加文字模特配件；A+检查970×600布局、自然操作和不误导配件。不能靠视觉估算证明真实尺寸。human_approval保持pending。
