---
name: nfwl-listing-strategy
description: "为已有nfwl Listing研究包建立相关性筛选、关键词机会分、埋词矩阵与用户指定策略。用于研究到写作的交接，不自行采集数据或发布商品。"
---

# nfwl Listing 策略

读取 [执行契约](../nfwl-listing/references/workflow.md)、主任务input.json和研究包。

1. 检查目标站点/语言匹配，不从US流量推导DE或JP流量。
2. 运行 `python <nfwl-listing目录>/scripts/nfwl.py strategy --input input.json --output strategy.json`。读取排除项、缺失指标与重归一权重。
3. 将高相关词分为核心、属性、人群/场景、长尾；对无市场数据任务只用产品相关词并标待验证，不生成分数或假流量。
4. 按用户strategies建立定位差异、主卖点、关键词角色和风险。无指定时主Skill建立一个推荐策略；有多套则保留全部，不机械固定三套。
5. 输出strategy_notes.md和keyword_placement.json，字段为marketplace、language、strategy_id、target_field、keywords、reason、source_ids。每个事实性差异点须符合SKU。

分数辅助排序，不代表销售预测。来源或关键指标不足时降低结论强度，仍保留缺项。
