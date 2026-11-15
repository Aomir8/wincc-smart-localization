# 运行与交接

## 发给同事后怎么用

解压整个 `wincc-smart-localization` 文件夹，保留 `SKILL.md`、`scripts` 和 `references` 的相对位置。支持技能加载的助手可加载该目录。支持本地 Windows 文件和命令工具的助手也可先读取 `SKILL.md`，再按下面的命令运行脚本。用户可以直接说：

> 把 `D:\Projects\包装机.hmismart` 增加法语（法国），项目文本按英文原文全部翻译，已有法语保留，另存为新工程。

> 把 `D:\Projects\包装机.hmismart` 的 Monitor 和 Positioning photoelectric switch failure 翻译成俄语（俄罗斯），只处理这两条。

GPT、Claude、Kimi、DeepSeek 的执行能力由所用客户端决定。能调用本机 Windows 工具时，可让助手端到端执行。只有网页对话或云端沙箱时，在本机运行 `scan`，把 `SKILL.md` 的“工程译文”标准、目标语言以及 `inventory.json` 中需翻译的文本和上下文交给模型。取回 `translations.json` 后在本机运行 `apply`。请模型把术语出处和待确认项列在译文文件之外。脚本本身无需 API 密钥，读写工程和数据库检查都在本机进行。

接收技能包后，可按以下顺序开始：

1. 在 Windows 解压完整技能包。准备 Python 3.10 或更新版、PowerShell 和与工程兼容的 SQL Server Express LocalDB。命令行运行 `python --version` 和 `SqlLocalDB versions`，确认这两个工具能够启动。LocalDB 工具若未加入系统路径，可在扫描时用 `--localdb-exe` 指定路径。
2. 准备已保存的 `.hmismart` 和同名 `_log.ldfsmart`，以及该工程相关的 `.data`。工程在压缩包里时，先解压到工作目录，再选择需要处理的工程文件。工程和配套日志需要放在同一文件夹。
3. 在支持本机文件与命令的 AI 客户端中，向助手提供技能目录和工程路径，让助手先读 `SKILL.md`。同时说明原语言、目标语言、翻译全部文本还是指定条目，以及新工程的保存位置。不同客户端加载技能的入口可能不同，可直接要求助手读取技能目录中的 `SKILL.md`。
4. 在网页对话中，先在 Windows 上按下方命令运行 `scan`。把需要处理的清单内容和 `SKILL.md` 的“工程译文”部分交给模型，请模型按下面的 JSON 格式返回译文。将返回结果保存为 UTF-8 的 `translations.json`，再运行 `apply`。清单可能包含设备名称、报警文本或地址，分享前由工程持有人确认可分享的范围。
5. 遇到报错时，把完整报错、WinCC 和 LocalDB 版本、执行的命令与已完成的步骤提供给助手。诊断信息的整理方法见 [常见问题处理](troubleshooting.md)。

## 命令

在解压后的技能目录里运行。用实际工程路径和全新的工作目录、交付目录替换下面的示例。原工程需已保存。数据库和日志被 WinCC 占用时，关闭项目后再复制，或改用一份已保存且未占用的工程副本。

```powershell
python .\scripts\localize.py scan --project 'D:\Projects\包装机.hmismart' --work-dir 'D:\Work\包装机-fr' --target fr-FR --source en-IE --mode all
python .\scripts\localize.py apply --work-dir 'D:\Work\包装机-fr' --translations 'D:\Work\包装机-fr\translations.json' --output-dir 'D:\Delivery\包装机-fr'
```

指定条目时，把 `scan` 改为 `--mode selected`，再用 `apply --expect-count 2` 等参数核对选定记录的数量。同一句若对应多处画面对象，数量以记录 ID 为准。目标语言已启用时，脚本沿用工程原有槽位。法语（法国）用 `fr-FR`，俄语（俄罗斯）用 `ru-RU`。英语来源应以扫描到的地区为准。`--fallback none` 可禁用中文回退。

同一份工程要加多种目标语言时，每种语言单独运行一次，用上一轮交付的工程副本作为下一轮输入。逐条请求都指向同一种语言时，可用同一个 `selected` 任务处理。

## 怎样查找专业术语

以下步骤适用于俄语、法语、西班牙语及其他目标语言。翻译前先确认工程的原版语言，结合画面名称、控件和报警对象理解短句的用途。

1. **整理关键术语。** 从清单中找重复出现的按钮、状态、报警、传感器和机构名称。保留原文、目标语言和所在对象，区分同一英文词在不同位置的含义。
2. **查 HMI 用语。** 优先搜索西门子对应产品系列与版本的目标语手册。可组合 `WinCC flexible SMART`、目标语名称、原文或目标语候选词搜索。查到同类 WinCC 手册时，记录产品和版本，将其用于核对通用用语。
3. **查设备部件。** 有厂商和型号时，先查该设备的目标语手册或数据表。型号未知时，查相关厂商对同类传感器、阀门、电机或机构的目标语资料。将资料里的部件定义与工程实际动作对照。
4. **记录依据并统一用词。** 对关键术语记下原文、译法、适用对象和资料链接。工程原文有多种解释时，列出所在对象和候选含义，交给设备人员确认。后续相同部件和动作沿用确认过的叫法。

查找示例中，西门子俄文 WinCC 手册可用于核对报警术语，SICK 法文数据表可用于核对光电传感器名称。具体设备仍应结合其型号和动作确定整句译文。 [西门子俄文 WinCC 手册](https://cache.industry.siemens.com/dl/files/933/17356933/att_103491/v1/hmi_wincc_v6_2_getting_started_ru.pdf) · [SICK 法文传感器数据表](https://www.sick.com/media/pdf/2/72/172/dataSheet_WT2S-F261_1043913_fr.pdf)

`inventory.json` 中的每条记录带有原文、原语言、所属对象、当前目标文字和可译片段。`translations.json` 是按 ID 索引的对象。示例 ID 需换成当前清单里的真实 ID。一个可译片段可以填字符串。多个片段按清单顺序填数组。指定条目中的纯代码可填空数组，由脚本按源文原样复制。

```json
{
  "11111111-1111-4111-8111-111111111111": "Surveillance",
  "22222222-2222-4222-8222-222222222222": ["Réglage", "Vitesse"]
}
```

全量模式只提供 `status: translate` 的 ID。脚本会检查缺漏、多余 ID、片段数和目标字段长度。`keep_existing` 使用已有译文，`copy_literal` 使用原有代码或符号，所有候选源语言均空白的记录保留空白。既有俄语等其他语言的数据随工程保留。发现 `unsupported` 时，按清单中的原因处理。`snapshot.json` 和 `snapshot` 是脚本的本机工作文件，后续 `apply` 需要它们。

`--localdb-version 16.0` 可指定已安装的 LocalDB 版本。`--localdb-exe` 可传已安装的 `SqlLocalDB.exe` 路径。脚本会比较附加前后的数据库格式版本，发现升级就停止。交付时保留同一目录里的 `.hmismart`、`_log.ldfsmart` 和相关 `.data`。发现源文件有更新时，使用新的工作目录重新扫描。 [Microsoft LocalDB 工具说明](https://learn.microsoft.com/en-us/sql/tools/sqllocaldb-utility)

## 工程内写入的内容

- `.hmismart` 通过配套日志在临时 LocalDB 实例中附加副本。项目语言对象与 `HmiProjectLanguageTable` 联接确定槽位。新增语言时从现有对象读取项目父节点和类型信息，并给各设备的语言字体目录写入对应文化记录。字体列表以项目参考语言为首选回退来源。
- `HmiTextTable.Id` 对应 `HmiBasicTable.ObjId`。`TextHashtable` 存各语言原文，`LanguageN` 存界面索引用的文本。脚本同时写两处。只处理支持原样解码、再编码的 Utah 文本结构。原有语言和格式标签按原值保留。项目语言有变化时，按槽号排序的语言名称和文本一起参与 WinCC 的 MD5 文本索引计算，结果保存为四个有符号整数。
- 处理范围是项目中可见的用户文本，如画面、用户报警、文本列表和权限名称。隐藏文本、系统报警文案、PLC 地址配置、面板运行语言及运行时切换按钮属于其他配置。新增项目语言后，只有设备运行语言也配置了该语言，面板运行时才有对应的语言选项。 [西门子 WinCC flexible SMART 手册，第 5.15 节](https://cache.industry.siemens.com/dl/files/417/109978417/att_1311187/v1/WCFWinCCInformationSystemzhCN_zh-CHS.pdf)

## 验证边界

脚本对输出副本运行数据库完整性检查，并在重新附加后核对项目语言、目标文本、字体和原有项目文本。首次用于另一版 WinCC 或另一种项目结构时，建议先做少量代表性文本，包含画面短标签、报警和带格式的文字，再运行全量。WinCC 界面渲染、保存重开、编译及真机显示需要实际在相应软件和面板上验收。旧版本数据库如果需要升级，应先按该版本的官方流程生成可用的升级副本。

本包在 WinCC flexible SMART V5 SP2 Update 1 工程和 LocalDB 16.0 上跑通了四种情况。原本仅有中英的工程新增法语并翻译三条、批量新增俄语并处理 180 条、独立新增西语并翻译指定两条，以及已有法语的工程更新指定一条。以上均通过离线数据库验收。前期同工程的法语三条原型已在 WinCC 中确认显示。原始 V4 样本的数据库格式为 782，使用 LocalDB 16.0 会升级为 957，试跑在版本检查处停止。该样本使用匹配版本的 LocalDB 进行全流程写入仍待验证。

另一份 V5 SP2 工程在扫描时暴露过版本标记识别问题，脚本已修正，并在该工程副本写入三条法语。该次按用户要求交由用户进行界面验收，验收结果需另行确认。
