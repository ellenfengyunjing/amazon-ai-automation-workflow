---
name: nfwl-listing-review
description: "检查nfwl Listing的事实证据、标题字符、关键词重复、五点结构、内容禁用项、多语种和策略组合完整性，定位问题并提出局部修正。"
---

# nfwl Listing 复核

读取input.json、listing_variants.json以及 [客户规则](../nfwl-listing/references/customer-rules.json)。

1. 运行 `python <nfwl-listing目录>/scripts/nfwl.py validate --input input.json --result listing_variants.json --output qa.json`。退出2表示需改，不能忽略。
2. 独立语义复核事实→声明强度、禁用能力、单主题、重复冗余、竞品抄写和英文/本地语言自然度。数字预检不证明完整语义；也要检查“不糊底”“更快”“安全”等无数字声明。
3. 检查多策略实际差异、本地关键词真实性、单位转换和产品/站点适配；确认所有目标组合均存在。
4. 写semantic_review.json，包含reviewer、逐字段observations、issues、state（pass/revise）、market_data_limits。不要只抄qa.json或打一个总分。
5. 返回精确字段、原文、原因、证据和建议。主Skill可局部修正一轮并用新文件名重验；未解问题保留。不得把人工审批设为通过。

机械、语义和人工审核是三件事。MCP不可用不是“已完成市场验证”。
