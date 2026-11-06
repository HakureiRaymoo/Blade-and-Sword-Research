# rekit —— 刀剑封魔录资源工具箱

针对 Steam 版《刀剑封魔录外传：上古传说》的只读勘察与解包工具。纯标准库，Python 3.10+。

> 本目录不包含任何游戏资产。所有工具都指向你本地的安装目录，输出也留在本地。

## 快速开始

```powershell
$py = "python"   # 或你的解释器路径
$g  = "D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"

# 1. 校验所有资源库结构
& $py leylib.py info "$g\zy\Spr.lib" "$g\zy\ResJM.Lib.chs"

# 2. 查看条目（含类型嗅探）
& $py leylib.py list "$g\zy\Spr.lib" --limit 40

# 3. 导出（建议先小批量试）
& $py leylib.py extract "$g\zy\ResJM.Lib.chs" .\out\jm --count 50

# 4. 任意文件头转储
& $py probe.py "$g\zy\idx.lib"
```

## 模块

| 文件 | 作用 |
| --- | --- |
| `leylib.py` | `leyiLib2.0` 容器读写：`info` 校验 / `list` 列举 / `extract` 导出 |
| `probe.py` | 未知文件头十六进制勘察，输出魔数、u32 视图、ASCII 列 |

## `leyiLib2.0` 格式速查

```
0x000  10B   "leyiLib2.0"
0x00A   6B   00 CC CC CC CC CC
0x010   4B   条目数 N（u32 LE）
0x014  0xEC  保留（全 0）
0x100  8N    条目表：N × (u32 offset, u32 size)
0x100+8N     负载，条目首尾相接
```

`info` 子命令执行的校验（任一不满足即报错）：

1. `0x100 + 8N` 等于第 0 条 offset；
2. 每条 offset 等于上一条的 offset + size；
3. 末条末尾等于文件长度。

## 已知但**尚未实现**的能力

按优先级排列，对应 `docs/00-roadmap.md` 的 M1 / M2：

- [ ] `lep` 位图解码 → PNG
- [ ] 精灵帧包（`[count][offsets][lep...]`）拆分
- [ ] 资源 ID → 名称映射（从 `Role.txt` / `PropMdl.txt` / `SoundMdl.sy` 构建）
- [ ] **重打包**：改图后写回 `.Lib`，需要保持索引表偏移连续
- [ ] `.fol` 容器解析（格式未解）
- [ ] 数据表 `txt` ↔ JSON 无损转换

## 约定

- 一切都用 `uint32 little-endian`，除非另有说明。
- 遇到格式假设，先在**全部** `.Lib` 上跑 `info` 验证，再写进代码。
- 不修改安装目录内的原始文件；导出与回写都走独立输出目录。
