# Listing 输入输出与工具适配

## 数据模式

- live：当前任务真实MCP/API结果；sources至少记录provider、工具名、查询市场/时间、采集时间及数据范围。
- export：用户提供的真实CSV/JSON；记录文件哈希、供应商、日期/周期及字段映射。
- missing：没有可验证市场数据。keywords为空，gaps说明影响；文案仍可基于产品事实，但市场验证为false。
- test_fixture：明确的合成测试数据，不是真实搜索量，报告必须显式标记。

“工具成功”不等于“样本覆盖完整”。支持字段和国家以当前工具发现为准。过期或口径不匹配数据不可静默复用。模型不能自己填入流量数字、CPC或购买率。

## 无凭证的MCP发现

优先查询宿主工具目录，按名称和能力寻找卖家精灵/SellerSprite和Sif；先读参数schema再调用，登记真实工具名。适配所需能力为：竞品检索、ASIN详情、关键词反查/扩展、搜索/购买/竞价/SPR、评论、流量结构。此列表是能力要求，不是假定存在的API名称。

官方参考入口：https://open.sellersprite.com/mcp 与 https://blog.sif.com/article/mcp-install/Sif-MCP安装文档 。接入与凭证由宿主配置；不能读取其他Skill的.env或将密钥写进报告。工具未连接就使用真实导出或missing模式。

导入命令：

```text
python <本Skill目录>/scripts/nfwl.py import-keywords --file keywords.csv --provider sellersprite --marketplace US --language en --output research.json
```

CSV可用term/keyword/关键词、volume/search_volume/月搜索量、relevance/相关性、purchase_rate/购买率、cpc/CPC、spr/SPR。相关性0–1，未提供为0即待审核，不自动假设相关；百分比带%才按百分比解析。字段不明时先让用户确认映射，不猜本地化数字。将结果作为input.research，保留来源字段。

## 方法

清洗：同功能、形态、场景和购买意图为直接样本；邻近样本分开；排除噪音并记录。研究包保留竞品品牌仅供分析，不得进入本品文案。

关键词：相关性<0.5或无来源不计分。按站点与语言分别归一，默认volume .35/relevance .30/purchase_rate .15/inverse SPR .10/inverse CPC .10。缺失项剔除后对已有项重新归一并显示effective_weights，不把缺失当零竞争。高流量不抵消低相关性。此为建议基线，可用keyword_weights显式替换。

策略：按用户指定策略；多方案在目标人群/场景/主卖点/关键词落位上有实际区别。不要固定强制三套。覆盖表包含Title/BP1–5/Description/Search Terms，并说明缺失关键词的原因。对日语、德语复合词和词形做人工语义覆盖检查，脚本子串检查只作预检。

## 输出

listing_variants[].id唯一；每个目标组合有一条，五点用{text,theme,selling_point_ids}。事实引用与文字分离，不能把证据编号渲染进买家文案。input_sha256锁定输入快照。没有正式品牌、尺寸、保修时不生成假数据或外显占位词。

生成HTML及列表是Skill责任；业务入库、选中采用版本、审批、下载权限及阶段推进由后端负责。

## 复用来源

方法参考现有seller-sprite-listing-generator（样本清洗、机会评分、策略矩阵）和listing-qa-compliance（证据/内容复核）。未修改或复制其个人配置；没有继承固定三方案、未核验的Item Highlights条数或全球统一字节上限。
