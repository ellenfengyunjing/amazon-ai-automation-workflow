# research_pack与字段证据

request：task_id/revision安全标识、marketplace、as_of(YYYY-MM-DD)、input:{kind:category/keyword/asin/url/sku,value}。可选budget.max_tool_calls、failure_rule:{max_units,window_days}、own_listing_source_id、max_source_age_days（默认30天，数据时效建议，不是客户选品条件）。

research_pack：schema_version=1.0、request、mode(live/export/unavailable/test_fixture)、sources、candidates、insights，可选research_data。结构见JSON Schema及examples.json。

source：id、kind(sorftime_mcp/sorftime_export/user/fixture)、marketplace、collected_at、raw_ref，建议period、tool_name、供应商估算说明。mcp必须真实tool_name/raw_ref，export必须文件sha256；fixture不能混入live。当前脚本仅核对声明和时效，无法证明外部数据真实，Agent还须检查实际调用记录。

用于本品优势与自身Listing基准的source必须明确`role=own_product`，不能拿普通市场竞品来源冒充。测试来源可加synthetic=true，该标志在非test_fixture模式不可用于证明事实。未评分的0星不参与均值，按未知处理；真实rating_count=0仍为0。

候选：id,name,category_name,scope_category(industrial/parts/hardware/automotive)，price_usd,price_currency=USD，competitors、coverage、advantage、failure_cases、action_plan、evidence。美元计划价可以是用户确认或市场有依据的建议，必须在action_plan解释，不自行把低于50的市场硬写成50。

每个参与计算的字段通过`evidence:{字段名:[source_id]}`绑定。缺字段或引用无效/过期/跨站→unknown。AI标注same_function等也引用所据的真实详情；不是假装供应商直接输出该布尔值。

competitor：asin、parent_asin可选；same_function、same_shape、same_material、listing_complete、competes_function为true/false/null；fulfillment为FBA/FBM/DOMESTIC_SELF/AMAZON/null；stars、rating_count、price_usd、sales_units数值或null；form、material及evidence。rating_count与review_count分开，后者不能替代。

coverage：scope_note说明实际研究边界；same_type_complete/effective_pool_complete/forms_complete/failure_scan_complete及逐字段evidence。只取Top100/第一页不能直接设完整；说明扩展查询、分页/变体检查与终止条件。

advantage：state=verified/proposed/disproven、claim、own_source_ids、baseline_source_ids及evidence.state。verified必须有自有产品/测试/已确认能力和竞品对照；设计设想为proposed。

failure_cases：comparable_listing、observed_units、window_days、reason_status=explained/unexplained/null、reason_text及字段evidence。实际观察窗口需等于任务failure_rule.window_days；销量不大于max_units视作低销，均为用户定义而非客户默认阈值。没有定义时保持null/HOLD。

insights：section=1..10、kind=data/inference/hypothesis/proposal、finding、meaning、action、evidence_ids。data/inference须有有效证据，假设不得写成确定事实。research_data可保存market/keywords/voc_and_failures/risks_and_economics结构，各数值仍须在内容内保留来源/分母/窗口；Agent语义检查是必要项。

research_data中的数字记录必须在所在对象或祖先对象提供source_ids/evidence_ids；否则QA拒绝可确认输出。建议用表格数组，例如`keywords:[{term,volume,period,source_ids}]`，每列按真实可用字段填写。脚本渲染为HTML表格，不让Agent手拼不一致表格；字段来源只证明声明的关联，不证明供应商确有该数值，仍须对原始响应核对。

评价输出将每候选每关卡state、value、reason、evidence_ids列出；没有数据为null，HTML显示获取不到。GO只是筛选通过；人工确认pending，test_fixture不可选。输出列名与前端约定见frontend-contract.md。
