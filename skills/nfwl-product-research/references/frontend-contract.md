# 前端与后端契约

后端接收request，路由`nfwl-product-research`，向Agent提供Sorftime工具及已授权SKU快照。任务事件可用task.started、stage.progress、source.collected、analysis.updated、artifact.created、task.completed/partial；进度依据实际步骤。Skill安装不等于已存在skill.invoke后端服务。

- research_result.json：报告结构、规则评估、来源、洞察、统计和缺项。
- recommendations.json：recommended/needs_evidence/rejected/test_only，只有真实来源且全条件pass才eligible_for_confirmation=true；人工仍pending。
- report.html：离线报告，可在受控iframe中渲染。建议sandbox允许本页脚本但不给同源或任意导航；下载由后端封装。
- selection_contract.json：选择消息type=nfwl.research.selection，payload含task_id、revision、input_sha256、candidate_ids。页面可下载JSON或postMessage到父窗口，**不会直接写入业务数据**。

父窗口核验event.source、任务和输入摘要、版本及候选资格；sandbox origin可能为null，不能只信origin。后端重新校验候选及用户确认，不信任浏览器上传passed=true。凭证不进消息。

确认后输出research_selection及source_task_id；正式SKU还需自有资料，研究里的竞品规格、建议设计不能变成confirmed事实。后续卖点/Listing/组图读取客户确认SKU，研究仅作上下文。

后端承担存储、任务队列/恢复、认证、MCP凭证、状态与事件流、前端列表和确认；Skill承担研究、方法论、规则及结果文件。本批不改这些既有工程。
