---
name: nfwl-image-render
description: "执行nfwl图片计划中的指定图位，使用宿主内置图像生成或编辑工具，保留真实结果和非覆盖版本，支持单图返工；不依赖个人API配置。"
---

# nfwl 图片生成与编辑

读取input.json、已补全prompt的image_plan.json和 [宿主工具约定](../nfwl-image-suite/references/host-tools.md)。

1. 只执行ready的选定图位。prompt为空、缺product参考或尺寸/比较证据不足时不生成。
2. 用宿主查看工具看本地本品图和编辑目标。按实际图像工具schema传本品参考，风格参考只用于风格；不得把其他SKU或竞品当本品。
3. 每个图位一调用，真实执行后记录生成结果、使用prompt和引擎。内置工具不支持的参数不杜撰。保持工具输出要求，能展示时展示结果。
4. 获取真实本地文件后运行主Skill的archive-image命令，记录实际像素与非覆盖revision。尺寸不符继续作为待修正，不伪称达标。
5. 返工只操作指定id，约束“只改用户要求的部分，其他产品身份保持”，parent_asset记录原图。不删除、不覆盖旧图或其他成功图。
6. 更新一个新的image_results.json，包含真实文件和待视觉审核状态，交nfwl-image-review。

任何图像内容编辑使用宿主允许的图像工具。不能用去角标脚本删除来源水印，不自动改用外部付费API。仅有prompt没有图片时必须报告未生成。
