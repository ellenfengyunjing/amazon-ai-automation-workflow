# 卖点方法与交接

## 六个维度

- pain_point：用户场景里的困难；区分真实VOC和基于场景的假设。
- function：已确认的主功能，不把“保温”扩成“煮制”。
- material：已确认材质、工艺；不从不锈钢推导304、食品级、永不生锈。
- operation：有依据的安装、调节、拆洗、体积与重量体验。
- accessory：随货清单及其作用；不暗示另售用品包含在内。
- extra：经确认的收纳、携带、兼容和场景优势。

一条示意结构：在[场景]需要[目标]时，[本品确认特性]可用于[适度结果]。语言自然，不必把“痛点”三个字硬写进文案。禁止用无依据时间、效率百分比和比较级增强句子。

## 事实约定

来源与事实编号不可由竞品数据替换。每条text里的数字必须属于其fact_ids声明的事实且单位一致。换算要先形成带公式和原字段的已核对派生事实，不能只因为数值接近就放行。限制词patterns用于已确认的产品禁用能力；必须人工检查否定、引用和跨语言语义，脚本检查可能保守。

## 测试和后端交接

项目源码 `skills/tests/fixtures/` 提供输入；安装到宿主后的主Skill examples/ 提供相同可携带样本。先复制样本到新的任务目录再生成。

输出 selling_points 保留 id、theme、dimension、text、pain_point、feature、benefit、fact_ids。状态draft不可自动用于“已确认卖点”通道；若用户明确确认，由宿主生成经确认的输入副本交给nfwl-listing。Skill不建SKU、不发通知、不提交电商平台。

## 参考来源

本套规则根据用户的卖点开发要求重新编写；方法参考现有 seller-sprite-listing-generator 与 listing-qa-compliance。没有导入旧Skill的固定路径、旧市场强制规则或配置。
