# Sorftime能力与连接

官方：https://www.sorftime.com/en-US/mcp 。官方Streamable HTTP示例为`https://mcp.sorftime.com?key=...`。真实地址/权限以账户为准；不把凭证写入任务文件。

优先宿主工具目录发现和schema调用；下列别名来自参考仓库，**未经当前Sorftime账户实机确认**，只用于发现线索：

|能力|别名|
|---|---|
|category_resolve|category_search_from_product_name, category_name_search, category_search_from_top_node, search_categories_broadly|
|market_snapshot|category_report, category_report_from_history|
|market_trend|category_trend|
|keyword_pool|category_keywords, keyword_extends|
|keyword_search|keyword_search_results|
|keyword_metrics|keyword_detail, keyword_trend|
|product_search|product_search, potential_product|
|product_detail|product_detail|
|product_history|product_trend|
|reviews|product_reviews|
|variants|product_variations|
|traffic_terms|product_traffic_terms, competitor_product_keywords|
|sourcing|ali1688_similar_product|

参数country/nodeId/trendIndex等全部读真实schema，不复制旧示例枚举。工具不支持Listing内容就标unknown；BSR不是销量，关键词排名不是搜索量，review_count不是rating_count，卖家国籍不是发货模式。

## 可选HTTP桥

仅从`SORFTIME_MCP_URL`或`SORFTIME_API_KEY`环境变量读取。未配置则列为未连接，不搜索他人.env或全局配置。只支持官方HTTPS域名，拒绝跨域重定向。

```text
python scripts/sorftime_bridge.py catalog --output catalog.json
python scripts/sorftime_bridge.py call --capability product_detail --tool <真实name> --args-file args.json --output response.json
```

initialize→initialized→tools/list（含分页），call先验证发现的工具及参数schema再tools/call。只读白名单；别名不能匹配时改用宿主明确绑定，不能猜调用。认证、配额、分页中断、MCP isError、旧SSE服务不伪装空结果。桥支持JSON与POST SSE响应，不实现长时通知流或服务端交互。

写出的响应脱敏，记录实际工具、采集时间、摘要与真实结果。结果为文本JSON时先解析，再按实际字段建mapping：

```text
python scripts/research.py normalize --raw parsed_payload.json --mapping mapping.json --output normalized_rows.json
```

mapping使用`rows_path`及`fields`（目标字段→点路径），没有默认供应商字段猜测。缺字段为null，归一化后逐字段填evidence及实际记录定位。原始响应保留，Agent属性标注不可冒充供应商字段。

真实联调必须覆盖三个入口、分页、变体、履约/rating字段、配额失败和前端结果。mock仅验证协议及程序，不证明服务已连接。凭证由后端管理；本包不安装MCP配置。
