# 来源与改写边界

- 客户：《选品要求.docx》，用户确认星级简单平均及失败口径待验证，2026-11-09。
- 方法参考：https://github.com/zach22-1999/amazon-skills/tree/main/skills/zach-product-research ，及references/analysis_patterns.md、payload_schema_v2.md、html_report_spec.md。读取日期2026-11-09。上游main是可变引用；GitHub API限流，未验证commit SHA，不伪造版本钉选。
- 上游MIT License已保留在upstream-MIT-license.txt。业务脚本与前端模板为本项目独立实现，没有运行或复制上游脚本，也不继承其其他Skill依赖。
- Sorftime官方能力/连接说明：https://www.sorftime.com/en-US/mcp 。实际工具参数仍须运行时发现。
- MCP协议参考：https://modelcontextprotocol.io/specification/2025-03-26/basic/transports 。可选桥的JSON/SSE协议测试不代表Sorftime实机通过。

本包只提供一个业务入口及配套资源；不改原有Skill集合清单、旧安装器、前后端或MCP配置。
