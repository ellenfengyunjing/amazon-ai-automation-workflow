---
name: nfwl-listing-write
description: "按已确认SKU、卖点、关键词策略生成多语种多方案标题、五点、详情与后台词，输出结构化nfwl Listing候选。不负责研究数据采集或人工审核。"
---

# nfwl Listing 文案

读取 [输入](../nfwl-listing/references/input.schema.json)、[输出](../nfwl-listing/references/output.schema.json)、[客户规则](../nfwl-listing/references/customer-rules.json) 与主任务策略。

按每个targets×strategies组合生成，不翻译模板后冒充本地搜索研究。目标语言支持en/de/fr/es/it/ja；结合站点表达、单位及词形，产品事实不得变化。

- 标题：主体+关键属性+场景/对象，含空格≤75字符，核心相关词前置；无促销、装饰符号、emoji或无关修饰，同一关键词不超过2次。
- 五点：5条独立主题，从status=confirmed卖点选取改写，每条痛点/需求+特性+收益。不得为凑5条发明特性；资料不足时返回缺项。
- 详情：补使用流程、规格和场景，不复制整条五点，不添加无依据兼容/保修。
- Search Terms：只用相关词，去重，无竞品品牌、ASIN、促销，不为了字节限制篡改产品；限制来自当前目标配置。
- evidence_map为每个字段声明fact_ids；所有数字、认证、性能和效果必须有相应证据。卖点编号与证据不出现在买家文案。

输出listing_variants.json，每条有策略理由；全部为候选。明确market缺口。按需写中文审阅解释，不混入目标语言字段。交由nfwl-listing-review，不自行宣布审核通过。
