# 刀剑封魔录 · 上古传说 —— 逆向与研究

> Knowledge base for *Blade & Fairy* / *Blade & Fairy: Legend of the Ancient*
> (Steam app `2924510`). Formats, engine structure, asset pipeline, and the
> reproducible tools that produced every claim.

本仓库**只做知识与文档**：记录逆向结论、保存可复现的解析工具、不放任何游戏原始资源。

**做 MOD 在另一个仓库**（另行开启）：`Blade-and-Sword-Modernized`。

---

## 状态

| 层 | 结论 | 可信度 |
| --- | --- | --- |
| `leyiLib2.0` 容器（`zy/*.Lib`，25 个 / 约 2 GB） | 已解 | 逐字节 + 5 库结构校验 |
| `lep` 位图（RGB565、行内"间隙+段"） | 已解 | 120 张图逐行验证 |
| `.fol` 容器（`cj` / `mb` / `slr`） | 已解，可完整解包与重打包 | 三份解包→打包逐字节一致 |
| `Spr` 组合动作表（角色分层） | 已解 | 1786/1786 条精确对齐字节数 |
| 角色装配（部件 / 帧号 / 绘制偏移） | 已解，可离线重建完整角色 | 代码 + 文件 + 内存三方 |
| 文本表 / 技能 / 触发器 / 场景摆位 | 已解（多为 GBK 纯文本） | 解包后可读 |
| 音频 / 视频 | `sy`=WAV、`dhp`=MPEG-1 | 抽样全部通过 |
| `.MAP` / `.Mdl` / `.BNT` / `.PLI` 内部结构 | **未解** | 见 [待办](docs/02-open-tasks.md) |
| 失焦继续运行 | 未解 | 见 [待办](docs/02-open-tasks.md) |

---

## 目录

| 路径 | 内容 |
| --- | --- |
| [`research/`](research/README.md) | 逐项勘察记录（容器、位图、数据表、引擎、运行时、组合表、`.fol`） |
| [`docs/`](docs/00-roadmap.md) | 路线图、[待办与未解项](docs/02-open-tasks.md)、[改造面地图](docs/03-modding-on-original.md)、[可玩角色](docs/05-playable-characters.md)、[Boss/剧本](docs/06-xuehongying-boss.md) |
| [`tools/rekit/`](tools/rekit/README.md) | 解析/导出/重打包工具（Python 标准库，无第三方依赖） |
| [`tools/ce/`](tools/ce/README.md) | 在 Cheat Engine 里手动执行的运行时抓取脚本 |

> `tools/` 保留在这边的理由：文档里每一条结论都注明"用哪条命令复现"，
> 工具本身就是证据链的一部分。MOD 工程那边会直接引用/复制这些工具。

---

## 关键事实

- **引擎**：自研 Leyi 引擎（`leyiLib2.0` / `LeyiMap1.50` / `LeyiInit1.00` / `leyibld1.50`），
  `ComeOn.exe` 是 2003 年的 32 位 MSVC 程序，图形走**纯 DirectDraw**，音频 DirectSound。
- **官方"移植" = 原版 exe + 兼容层**（随包附 dgVoodoo2 / cnc-ddraw + 后处理着色器），
  引擎几乎没改 —— 现代化的空间全在上层。
- **内建 client/server**：导入表里没有任何 socket，但存在 `ClientCreate` /
  `Packet_Create_Client` / `OnlyServer` / `DaojianServer`，主窗口标题就是 `DaojianServer`
  —— 逻辑与渲染同进程，用内部消息包通信。
- **全局编号空间**：`zy/idx.lib` 列出 14 个库，条目表首尾相接成 **46527 条**的全局编号；
  引用编码 `ref = 帧号<<24 | 库下标<<20 | 库内条目号`。
- **角色合成**：`Spr` 是组合动作表（帧 × 层），每层 `ref + (A,B,C,D)`，
  绘制偏移 = `A−C, B−D`；帧号 = `时间步×8 + 朝向`。
  角色 = 同一"帧包块 % 8"的一组部件表，按层序叠加。
- **`.fol` 是带文件名的资源包**，两层差分混淆：
  `目录: rec[i][j] -= j³·9 + seed[i]`、`负载: dword[i] -= 99·i² + seed[i]`。
- **`mb.fol` 里几乎是整套开发数据**：`Role.txt`、`Skill.ini`(330 KB)、`player/`（含 `.xls`）、
  `trigger/`（126 个脚本）、`BLD_*.Mdl`（建筑模型）。
- **`slr.fol` 里有 `SprRole.h`**：933 条 `#define SPR_ROLE_<角色>_<部位>_<动作>_<变体> <下标>`,
  等于 `Spr` 库的官方命名表 —— 角色编号就是 `Role.txt` 的 `图形ID`。
- **5 个可玩角色**：剑客(4) / 女侠(30) / 力士(40) / 和尚(223) / 老英雄(1)，
  前四个分层可换装，老英雄是整图烘焙（所以没有装备外观）。
- **数据表是 GBK 纯文本**（`Role.txt` 47 列、`PropMdl.txt` 18 列、`TriggerQuest.txt`…），
  **核心数值天生可编辑**；`Role.txt` 的 `组` 是初始阵营，`脚数` 区分人形/野兽/飞行。

---

## 复现

```powershell
$g = "D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"
cd tools\rekit

# 容器
python leylib.py info "$g\zy\*.Lib"
python leylib.py list "$g\zy\Spr.lib" --limit 20

# .fol（解包到 out/fol）
python fol.py info    mb.fol
python fol.py extract mb.fol --out ..\..\out\fol\mb

# 单张 lep / 组合表 / 整角色重建
python lep_probe.py   --lib Res00 --entry 5943
python scan_composite.py --lib Spr --limit 200 --show 2
python render_character.py --frames 0,16,48,80 --cols 4 --out ..\..\out\shots\char.png

# 数据表画像与单元格编辑
python table_profile.py --file "$g\bdh\chs\Role.txt" --out ..\..\docs\04-role-columns.md
python table_edit.py    --file "$g\bdh\chs\Role.txt" --row 角色名称=剑客 --get 平时速度
```

---

## 免责

*Blade & Fairy*（刀剑封魔录）及其外传 © 像素软件。本项目是非商业的爱好者研究，
仓库内**不包含游戏原始资源文件**（`zy/`、`sy/`、`dhp/`、`bdh/`、`*.fol` 均不入库）；所有路径都指向本地安装目录，仓库只保存解析代码与文字结论。`docs/img/` 下有少量由解析工具从本地资源重建的示例图，仅用于说明结论，权利方如有异议可随时移除。
如权利方有异议，请开 issue。
