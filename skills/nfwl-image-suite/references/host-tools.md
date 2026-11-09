# 宿主工具与后端接口

## Codex / WorkBuddy 测试

使用宿主真实可见的内置图像生成/编辑工具，按当前工具schema调用，不硬编码不存在的size、n、输出路径参数。先通过宿主图片查看工具读取本地参考，再传引用。Codex当前可用时使用image_gen；WorkBuddy在其工具目录寻找实际内置生图能力。找不到时说明宿主工具缺失，保留计划，不偷偷切到付费外部API。

一图一调用，不把多个图位拼成一张联系表来冒充完整组图。返回结果后获取真实本地文件；远程结果仅在宿主允许下载保存时使用。不要把base64长串写报告或日志，不从其他Skill读取.env。

先保留原始生成文件，再做非覆盖归档。工具只提供展示结果但无法获得文件时，明确说明文件交付未完成，不能自己造一个路径。

尺寸适配是画布/等比例导出，不是产品重绘。优先直接请求目标构图；宿主有精确尺寸工具时按用户要求使用。没有时记录未达标，不能使用非授权外部服务。任何进一步编辑遵守宿主图像工具规则。

本套件提供scripts/export_canvas.mjs用于已经生成的图片做最终尺寸导出；不裁切、不横纵拉伸，等比例缩放并用白色补齐画布，保留native原图。需要Node.js和sharp，可使用宿主依赖加载器返回的运行时与node_modules。命令：

```text
node <本Skill目录>/scripts/export_canvas.mjs --plan image_plan.json --id main01 --source native.png --output delivery.png --module-dir <宿主node_modules>
```

记录native_pixels、交付pixels和upscaled，不将放大图称为原生1600分辨率。未安装sharp时不擅自修改全局依赖；返回未完成尺寸适配，并给出具体缺失项。

## 未来后端适配接口（本批不实现服务）

生成请求：slot_id、revision、prompt、reference_asset_ids、expected_width、expected_height、copy、identity_constraints。

生成响应：provider_task_id、state、asset_id/本地文件、实际宽高、用量、错误、parent_asset。

宿主适配器负责API鉴权、队列、计费、存储和状态查询；Skill负责选择图位、写提示词与质量判断。请求超时先查询任务，不盲目重复提交。

本批的内置工具流程已经能在聊天中执行；没有开发HTTP客户端或后端数据库。
