---
name: wincc-smart-localization
description: Enable a project language and translate all or selected text directly in a saved Siemens WinCC flexible SMART .hmismart project. Use for offline localization, batch projects, or requests such as adding French or translating a list of labels into Russian.
---

# WinCC flexible SMART 离线翻译

在 Windows 上用本目录的 `scripts/localize.py` 处理已保存的 `.hmismart`、配套 `_log.ldfsmart` 和项目相关的 `.data`。从文件复制、读库、翻译、写入到验证都可在 WinCC 关闭时完成。每个工程交付一个新文件夹，原始工程保留作回退。脚本需要 Python 3.10+、PowerShell 和与工程数据库版本匹配的 SQL Server Express LocalDB。

## 执行流程

1. 从用户请求确定工程文件、目标语言地区和翻译范围。整套项目用 `--mode all`。用户逐条点名时用 `--mode selected`。多工程分别运行，每个工程使用独立的工作目录、译文表和交付目录。
2. 运行 `scan`，读取 `inventory.json`。数据库里的项目语言映射决定语言槽位。`fr-FR`、`ru-RU` 之类的代码需要与用户意图对应。中文和英文同时存在且未指定源语言时，默认用唯一的英文项目语言，英文空白时才用 `zh-CN`。用户指定源语言时传 `--source`，需要严格单一来源时传 `--fallback none`。出现多个英文地区、项目文件重名或无法判断原文时，提出具体候选请用户确认。
3. 按清单的记录 ID 生成 UTF-8 `translations.json`。`segments` 是应翻译的片段。可用 `source_layout`、`source_text`、`context` 和 `active_texts` 理解控件、画面、报警及术语。用户按原文点名时，先用这些字段定位。如果同一句对应多个对象，结合画面和对象名选定，或在用户要求全改时列入全部匹配 ID。全量模式为每条 `translate` 提供译文，脚本会处理 `copy_literal`。已有目标文本默认保留，全量重译需要用户明确要求并传 `--overwrite`。
4. 运行 `apply`。指定条目时用 `--expect-count` 锁定记录数。脚本会在同一个事务内新增项目语言和字体配置、写入目标文本和重算文本哈希。重新附加数据库，核对目标语言、文本、字体以及数据库完整性后才发布工程副本。WinCC 界面的实际显示由用户按需要验收。
5. 交付 `.hmismart` 所在的完整文件夹和 `localization-report.json`。汇报启用语言、实际处理的记录数、回退来源、已有译文和需要用户确认的术语。涉及面板运行语言、运行时切换按钮或下载时，先理解用户另外提出的需求。

## 工程译文

以下标准适用于所有目标语言和地区，也适用于全量翻译和指定条目。按用户确认的原文和术语表翻译，同一设备、动作和报警状态在整个工程里使用一致的叫法。

- HMI 界面、权限和报警通用术语，优先核对目标语言的西门子官方资料。先查对应的 WinCC 产品系列和版本。需要引用同类产品的手册时，将其作为术语参考。
- 传感器、执行机构和机械部件，优先核对本机设备厂商的目标语手册、技术数据表和用户词表。结合工程对象、变量和动作判断具体含义。短按钮用适合屏幕的短标签，报警准确区分状态、故障和设备动作。
- 汇报时附上已核对的关键术语和出处。缺少匹配资料时，使用目标语工业自动化和 HMI 的通行用语，标明关键译法的依据。设备含义仍有歧义时，列出原文、所在对象和备选解释供用户核对。
- 变量地址、型号、缩写、文本格式标签、占位符和换行按清单保留。只提交 `segments` 的译文，脚本按原布局重组。发现源文与另一语言的设备动作或地址冲突时，按已确认的源语言翻译，并列出足以影响使用的冲突供核对。
- 全量模式发现未知记录格式或缺失译文会停止发布。根据具体条目修正后再运行。

命令、译文 JSON 示例、术语查找方法、不同客户端的使用方式和兼容范围见 [运行与交接](references/runbook.md)。遇到环境、工程或译文报错时，查阅 [常见问题处理](references/troubleshooting.md)。
