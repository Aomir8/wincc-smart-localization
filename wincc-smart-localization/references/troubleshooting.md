# 常见问题处理

先记录完整报错、使用的命令、WinCC 版本、LocalDB 版本，以及问题发生在扫描、写入还是打开工程时。`inventory.json` 可能包含工程文本、对象名和地址，分享前检查可公开的范围。

## 扫描和环境

| 提示或现象 | 处理方法 |
| --- | --- |
| 工程文件被占用或无法复制 | 确认工程已保存并关闭，或使用一份已保存且未被占用的工程副本。再用新的工作目录扫描。 |
| `Missing paired log` | 查找与 `.hmismart` 同名的 `_log.ldfsmart`，放在工程旁边。找不到时，从完整工程备份取得配套文件。 |
| `SQL Server Express LocalDB was not found` | 在 Windows 命令行运行 `SqlLocalDB versions`。如果工具存在但不在系统路径，使用 `scan --localdb-exe` 指定其完整路径。 |
| `Cannot create LocalDB instance` 或 `Cannot start LocalDB instance` | 核对 LocalDB 已安装且能以当前 Windows 用户运行。保留完整报错，交给熟悉该电脑环境的人员查看。 |
| `LocalDB upgraded this temporary copy ...` | 记录报错里的两个数据库格式版本，并用与该工程匹配的已安装 LocalDB 版本重新扫描，例如在 `scan` 加 `--localdb-version 16.0`。旧版工程若需要升级，先按该版本的官方流程生成升级副本。 |
| `outside the supported WinCC flexible SMART project schema` | 记录工程软件版本和错误。新工程可能使用不同版本标记或数据结构，需要检查工程结构后再适配。 |
| 找不到原语言，或提示 `Multiple English project languages` | 查看 `inventory.json` 能否生成，结合工程设置确定原版语言后，在 `scan` 指定 `--source en-IE` 等实际语言代码。严格使用指定来源时加 `--fallback none`。 |
| 工作目录或输出目录已存在 | 为本次任务选择新的工作目录或输出目录，再运行对应命令。 |

## 译文和写入

| 提示或现象 | 处理方法 |
| --- | --- |
| `unsupported` 或 `Unsupported project text records` | 查看 `inventory.json` 的 `unsupported` 条目和原因。需要根据该工程的文本结构处理，再重新扫描并生成译文。 |
| `Bulk scope mismatch` | 全量模式逐项对照清单的 `status: translate`，补齐缺失 ID 并移除多余 ID。指定条目任务使用 `selected` 模式。 |
| `translation segment count does not match` | 译文按清单 `segments` 的数量和顺序填写。一个片段可用字符串，多个片段用数组。 |
| `Expected ... text records, got ...` | 核对选中的记录 ID 和 `--expect-count`。同一句原文可能属于多个不同控件，需要结合上下文确定处理范围。 |
| `exceeds ... field limit` 或 `text object limit` | 根据对象和原文调整为更短且准确的译文，再执行写入。保留原有地址、占位符和格式。 |
| `A source record changed` 或其他写入不一致提示 | 保存报错并使用新的工作目录重新扫描，按新清单生成译文。若仍出现，请检查该工程的数据结构。 |
| 提示 JSON 格式错误或 ID 不在清单 | 用 UTF-8 保存合法 JSON，检查引号、逗号、重复键和记录 ID。ID 从本次扫描结果取得。 |

## 界面显示

在 WinCC 打开交付副本，确认查看的是本次目标语言和对应的画面或项目文本。若原文在多个控件中重复出现，按记录所在画面和对象定位。本次数据库写入结果、界面显示、保存重开、编译和触摸屏运行效果可分别记录，便于定位差异。

请求协助时，可先提供完整错误文字、软件版本、目标语言、扫描或写入的命令、相关对象的少量原文和译文，以及是否已经打开过输出副本。根据具体问题再决定是否提供经授权的工程样例。
