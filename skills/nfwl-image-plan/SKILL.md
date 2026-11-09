---
name: nfwl-image-plan
description: "为nfwl组图任务读取本品照片、确认需求和SKU事实，建立视觉身份、十二类图位执行计划与逐图提示词。只规划，不管理需求表或调用生图。"
---

# nfwl 图片规划

读取相邻 [主Skill图位规范](../nfwl-image-suite/references/image-types.md)、input.json和全部参考图。必须真实看图，不能只读文件名推断外观。

1. 逐图标明product/style/competitor/dimension/usage角色，写observations.json，不能遗漏。无法确认处标unknown。
2. 建立visual_identity.json，锁定产品常规形态与真实使用形态、部件、标识、配件和禁止变化。未知结构、认证、精确比例不猜。
3. `python <nfwl-image-suite目录>/scripts/nfwl.py plan-images --input input.json --output plan_draft.json`。检查blocked原因；只阻塞相关图位。默认不主动补充图位。
4. 按规范与用户风格编写每个ready图位的完整prompt。准确文字单独保留copy，语言按输入，不放无依据参数。
5. 将新计划保存image_plan.json，同时保存prompts.json。脚本生成的空prompt不是执行完成，必须由你补充。不得解除缺证据阻塞来凑数量。

后续交nfwl-image-render。已确认需求改变时先明确改变内容，不能静默替换图位或数量。
