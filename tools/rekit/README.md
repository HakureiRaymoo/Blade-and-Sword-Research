# rekit —— 刀剑封魔录资源工具箱

针对 Steam 版《刀剑封魔录外传：上古传说》的勘察、解包与导出工具。纯标准库 + Pillow（仅导出 PNG 时需要）。

> 本目录不包含任何游戏资产。所有工具都指向你本地的安装目录，输出也留在本地。

## 快速开始

```powershell
$py = "python"
$g  = "D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"

# 校验资源库结构
& $py leylib.py info "$g\zy\Spr.lib" "$g\zy\ResJM.Lib.chs"

# 批量导出成 PNG（自动拆分精灵帧包）
& $py export_assets.py --game $g --out .\out\assets --libs ResJM ResPlayer1 --limit 40

# 单张 lep 解码（先 leylib extract 得到 .bin 再改名为 .lep）
& $py lep.py .\out\assets\ResJM\00000.png
```

## 模块

| 文件 | 作用 |
| --- | --- |
| `leylib.py` | `leyiLib2.0` 容器：`info` 校验 / `list` 列举 / `extract` 导出 |
| `lep.py` | `lep` 位图解码：行段解析、RGB565、PNG 输出 |
| `export_assets.py` | 批量导出：遍历库 → 拆帧 → PNG + `index.json` |
| `probe.py` | 未知文件头十六进制勘察 |

## 格式速查

### `leyiLib2.0`

```
0x000  10B   "leyiLib2.0"
0x00A   6B   00 CC CC CC CC CC
0x010   4B   条目数 N（u32 LE）
0x014  0xEC  保留（全 0）
0x100  8N    条目表：N × (u32 offset, u32 size)
0x100+8N     负载，条目首尾相接
```

`info` 校验三条：表尾等于首条目偏移、条目严格连续、末条末尾等于文件长度。

### `lep`

```
0x00   4B   "lep\0"
0x04  44B   头部（部分字段未定；含常量 0x1010、色键 0xF81F）
0x30   4N   行偏移表，相对 0x30
0x30+4N     行数据
```

行数据是重复的 `gap:u16 count:u16 pixels[count]`，末尾再跟一个 `gap`。
`Σgap + Σcount` 在同一图内恒定 = 扫描线字节数 W ⇒ 画布 = W/2 × 行数。
像素为 **RGB565 小端**。

### 精灵帧包

```
0x00  u32 count
0x04  u32 offset[count]     首个必为 4 + 4*count
...   lep 帧
```

## 已补齐（原先列在"尚未实现"里）

- **帧锚点**：每层子图自带 `(A, B, C, D)`，绘制偏移 = `(A−C, B−D)`
  → `scan_composite.py` / `render_composite.py` / `render_character.py`
- **资源 ID → 名称映射**：`slr.fol` 里的 `SprRole.h`（`fol.py extract slr.fol` 取）
- **重打包写回 `.Lib`**：`leylib.py pack`（往返逐字节一致）
- **`.fol` 容器**：`fol.py` info / list / extract / pack（往返逐字节一致）
- **数据表编辑与画像**：`table_edit.py`、`table_profile.py`

## 尚未实现

- 数据表 `txt` ↔ JSON 无损转换
- `.MAP` / `.Mdl` / `.BNT` / `.PLI` 四种二进制的解析
- `lep` **编码器**（目前只能解码；换图要借用现成条目的字节）

## 约定

- 一切 `uint32 / uint16` 均为小端，除非另有说明。
- 格式假设必须先在**全部** `.Lib` 上验证，再写进代码。
- 不修改安装目录内的原始文件。
