# Blade & Fairy: Reforged

> Merging *Blade & Fairy* (刀剑封魔录) and its expansion *Blade & Fairy: Legend of the Ancient* (刀剑封魔录·上古传说) into a single unified project — with rebuilt input logic, refined interactions, and full gamepad support.

将《刀剑封魔录》正传与《上古传说》合二为一的现代化项目：重构操作逻辑、优化交互、完整支持手柄。

## Status

**勘察阶段完成，工具链起步。** 尚未可玩。

已完成对 Steam 版《上古传说》（app `2924510`）安装目录的逐字节勘察：资源容器、音频、视频、数据表、存档、引擎结构均已定位，其中 `leyiLib2.0` 容器已写出可用解析器并通过全部 5 个库的结构校验。

## 目录

| 路径 | 内容 |
| --- | --- |
| [`research/`](research/README.md) | 原始勘察记录：容器格式、数据表、引擎与运行时 |
| [`docs/`](docs/00-roadmap.md) | 设计与计划：路线图、现代化策略 |
| [`tools/rekit/`](tools/rekit/README.md) | 资源工具箱（Python，无第三方依赖） |

## 已勘察到的关键事实

- **引擎**：自研 Leyi 引擎（`leyiLib2.0` / `LeyiMap1.50` / `LeyiInit1.00`），`ComeOn.exe` 为 2003 年构建的 32 位 MSVC 程序，图形走 **纯 DirectDraw**，音频 DirectSound，RIFF/AVI 经 WINMM。
- **官方"移植"= 原版 exe + 兼容层**：随包附带 dgVoodoo2 与 cnc-ddraw，加 CRT/xBR/FSR 等后处理着色器。引擎本身几乎未改 —— 现代化的空间在上层。
- **资源库**：`zy/*.Lib` 共 25 个，格式为 `0x100 头 + 8N 索引表 + 连续负载`，库内**无文件名**，只按序号寻址。
- **图像**：库内为私有 `lep` 位图格式，头部与子图偏移表已定位，像素编码待解。
- **音频**：`sy/*.sy` 实为 WAV（44.1kHz/16bit/单声道），486 个。
- **视频**：`dhp/*.dhp` 实为 MPEG-1 程序流，32 个。
- **数据表**：`bdh/<lang>/*.txt` 是 GBK 制表符分隔的纯文本（物品 18 列、角色 47 列、任务、对话、字符串表），四语言各一套 —— **核心数值天生可编辑**。
- **存档**：长度前缀字符串流，与 `Role.txt` 的字段同构。

细节与复现命令见 [`research/`](research/README.md)。

## Goals

- **Unified entry** — one launcher, two campaigns (base game + expansion), shared settings and input layer
- **Rebuilt controls** — modern input buffering, dual-track special-move input (mouse gesture for KB/M, right-stick tracing or radial wheel for gamepad)
- **Gamepad-first UI** — focus navigation for inventory, gem synthesis, quest log, and the combo editor
- **Visual combo editor** — timeline/slot-based editing with live preview of frames and cancel windows
- **Preserved core** — the combo-editing depth and semi-manual combat feel of the original are non-negotiable

## Non-goals

- 3D remake / engine-level visual overhaul (out of scope for now)
- Altering the original's combat balance or combo mechanics
- Redistributing original assets

## Strategy

采用双轨推进，详见 [docs/01-modernization-strategy.md](docs/01-modernization-strategy.md)：

- **Track A（外挂式现代化）** — 保留原版程序，注入改造输入/显示，外部编辑器改数据。快、可验证。
- **Track B（重制）** — Godot 4 + 导出资产 + 重新实现战斗。

Track A 的真正价值不只是"能玩"，而是**把原版当作 oracle**：hook 战斗状态机，采样帧级轨迹，作为重制版手感的验收标准。

## Tech

- 工具链：Python（标准库）、Ghidra（逆向）
- 重制目标：Godot 4（待 M5 启动）

## Legal

*Blade & Fairy* and its expansion are © Pixel Software (像素软件). This is a non-commercial fan modernization project. No original assets are redistributed in this repository. If you are a rights holder with concerns, please open an issue.
