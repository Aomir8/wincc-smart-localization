# WinCC SMART 工程离线翻译

协助为 Siemens WinCC flexible SMART 工程新增项目语言，并将画面文字、用户报警和其他可见项目文本翻译到目标语言。支持翻译整份工程，也支持按指定条目处理。

本项目面向 AI 助手，提供 `SKILL.md`、操作说明和本地脚本。脚本在 Windows 上读取已保存的 `.hmismart` 工程副本，生成文本清单，再将译文写入新的工程文件夹。

**快速开始** 请先阅读 [技能说明](wincc-smart-localization/SKILL.md)，然后按照 [运行与交接](wincc-smart-localization/references/runbook.md) 准备环境并处理工程。

## 解决的问题

工程中的多语言文字分布在不同画面、控件和报警对象中。手动逐条定位和录入需要花费时间，WinCC 的文本导出结果也需要按文本类别和导出范围检查。本工具按工程中的文本记录读取原文和对象位置，支持按清单翻译并写回，便于处理重复文字和指定条目。

工程关闭后，可以在文件副本上完成语言配置与文字写入，适合多份工程的离线处理。脚本负责读写工程文件，翻译内容由 AI 助手或使用者提供。

## 功能

- 读取项目现有语言、文本和对象位置，确定目标语言对应的槽位。
- 根据请求添加项目语言，或使用工程中已有的目标语言。
- 支持批量翻译和指定文本翻译，默认保留已有目标语言译文。
- 按原文保留文本格式、变量地址、占位符和换行。
- 生成新的工程副本，并提供数据库检查与写入结果报告。
- 为故障排查、工程术语查找和不同 AI 客户端提供操作说明。

## 环境要求

- Windows，Python 3.10 或更新版本，PowerShell。
- 与工程数据库格式匹配的 SQL Server Express LocalDB。
- 已保存并关闭的 `.hmismart` 工程、同名 `_log.ldfsmart` 及该工程相关的 `.data` 文件。

## 使用

将完整的 `wincc-smart-localization` 目录提供给能够访问本机文件和运行命令的 AI 助手，并说明工程路径、原文语言、目标语言和翻译范围。例如：

> 给这个工程增加法语（法国），按英文原文翻译项目文本，另存为新工程。

> 把这个工程中的指定两条报警翻译成俄语（俄罗斯）。

支持本机工具的客户端可以按照 `SKILL.md` 的流程处理。使用网页对话时，可先在 Windows 上运行扫描，把所需的文本清单和翻译标准提供给模型，再用生成的译文文件运行写入命令。具体步骤和命令见 [运行与交接](wincc-smart-localization/references/runbook.md)。

在技能目录下，扫描和写入的基本命令如下。路径和语言代码需要换成实际工程的值。

```powershell
python .\scripts\localize.py scan --project 'D:\Projects\project.hmismart' --work-dir 'D:\Work\project-fr' --target fr-FR --source en-IE --mode all
python .\scripts\localize.py apply --work-dir 'D:\Work\project-fr' --translations 'D:\Work\project-fr\translations.json' --output-dir 'D:\Delivery\project-fr'
```

第一步生成 `inventory.json` 清单。按清单生成 `translations.json` 后执行第二步。指定文本时可使用 `--mode selected`。具体 JSON 格式及多语言、多工程的操作见运行说明。

翻译时参考工程原文及上下文。HMI 通用术语优先查对应的西门子目标语资料，设备部件优先查厂商手册或数据表。关键术语和存在歧义的原文应记录出处及待确认内容。

## 实现原理

1. 将已保存工程和配套日志复制到独立目录，通过本机 LocalDB 读取副本。
2. 查询工程的项目语言、文字和对象关系，生成包含原文、记录 ID、所属对象和待翻译片段的清单。
3. 按语言代码查找已有槽位。需要新增语言时，为项目及相关字体配置创建目标语言记录。
4. 根据记录 ID 更新目标语言字段及文本数据，同时按当前语言顺序更新文本索引。脚本检查格式标签、地址和占位符等内容。
5. 正式写入流程会重新读取工程副本，检查预期文字、语言配置和数据库完整性，然后输出新工程文件夹。

涉及 `HmiTextTable`、`HmiBasicTable`、`TextHashtable` 等内部数据结构。具体结构和兼容性以工程版本为准。项目语言与面板的运行语言分别配置。

## 验证情况

在一份 WinCC flexible SMART V5 SP2 Update 1 工程上，完成了俄语批量处理 180 条、法语指定三条、西语指定两条，以及更新已有法语的离线测试。数据库写入及重新读取检查通过。较早的法语三条原型已由用户在 WinCC 中确认显示。

另一份 V5 SP2 工程已完成扫描，并写入三条法语，界面验收结果待确认。V4 工程的数据库格式兼容处理仍需在匹配版本的 LocalDB 上验证。不同工程的实际效果需要结合软件版本、工程结构、界面显示和编译结果确认。

## 说明与问题排查

项目语言、设备运行语言和运行时语言切换需要分别配置。工程翻译完成后，可在对应的 WinCC 软件中检查译文显示与排版。

遇到数据库、语言槽位或译文格式问题，可查阅 [常见问题处理](wincc-smart-localization/references/troubleshooting.md)。

本项目是独立工具，与 Siemens 官方的产品支持和发布渠道无从属关系。Siemens、SIMATIC 和 WinCC 等名称用于标识兼容对象，相关名称及商标的权利属于其各自权利人。

仓库包含技能说明和脚本。运行本工具需自行准备 LocalDB 和工程文件。文本索引计算的实现参考了对相关 Siemens 程序集的反编译分析，发布权限和适用的软件许可条款有待确认。仓库当前尚未选定开源许可证。
