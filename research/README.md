# 研究记录 / Recon notes

本目录存放对《刀剑封魔录外传：上古传说》（Steam app `2924510`，build `21003896`）安装目录的实地勘察结果。
所有结论都标注了证据来源（十六进制、字符串偏移、统计量），可以按文档里的命令复现。

## 结论速览

| 项 | 结论 | 可信度 |
| --- | --- | --- |
| 引擎 | 自研 "Leyi" 引擎（`leyiLib2.0` / `LeyiMap1.50` / `LeyiInit1.00` / `leyibld1.50`） | 已验证（exe 字符串） |
| 可执行文件 | `ComeOn.exe`，32 位 MSVC，链接时间 2003-07-29，DirectDraw 7 + GDI | 已验证（PE 头） |
| 主资源配置 | `zy/*.Lib`，自定义容器 `leyiLib2.0`：0x100 头 + 8N 索引表 + 连续负载 | 已验证（5 个库全部严格连续） |
| 图像 | 库内条目为 `lep` 私有图片格式（含帧偏移表） | 部分（头结构已定位，像素编码未解） |
| 音频 | `sy/*.sy` 实为 RIFF WAV（44.1kHz/16bit/单声道） | 已验证（484/486） |
| 视频 | `dhp/*.dhp` 实为 MPEG-1 Program Stream | 已验证（32/33） |
| 数据表 | `bdh/<lang>/*.txt` 是 GBK 制表符分隔的纯文本表格 | 已验证 |
| 存档 | `save/*.sav` 是长度前缀字符串流，版本串 "1.5" | 已验证 |
| 未知 | `cj.fol` / `mb.fol` / `slr.fol` 三个高熵容器 | 未解（疑似压缩或加密） |

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [01-install-layout.md](01-install-layout.md) | 目录语义、体积构成、运行环境与兼容层 |
| [02-container-formats.md](02-container-formats.md) | `leyiLib2.0` / `lep` / `.sy` / `.dhp` / `.fol` 逐字节分析 |
| [03-data-tables.md](03-data-tables.md) | 物品、角色、任务、对话表的字段结构 |
| [04-engine-runtime.md](04-engine-runtime.md) | PE 结构、初始化时序、存档格式、待办逆向清单 |

## 复现方式

```powershell
$py = "<python.exe>"
$g  = "D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"

& $py tools\rekit\leylib.py info "$g\zy\*.Lib"     # 校验全部库结构
& $py tools\rekit\leylib.py list "$g\zy\Spr.lib"   # 列出条目并嗅探类型
& $py tools\rekit\probe.py "$g\zy\idx.lib"         # 任意文件头十六进制转储
```

> 注意：原始资源不进入本仓库。所有路径均指向本地安装目录，仓库只保存解析代码与分析结论。
