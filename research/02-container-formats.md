# 容器格式分析

## 1. `leyiLib2.0` —— 主资源库（已验证）

`zy\` 下 25 个 `.Lib` 全部是同一格式，魔数 `leyiLib2.0`（引擎名 Leyi，版本 2.0）。

```
0x000  10B   6C 65 79 69 4C 69 62 32 2E 30      "leyiLib2.0"
0x00A   6B   00 CC CC CC CC CC                 填充
0x010   4B   u32 LE  条目数 N
0x014  0xEC  全 0 保留区
0x100  8N    条目表：N × (u32 offset, u32 size)
0x100+8N     ...                              负载区，条目首尾相接
```

判定依据（5 个库全部命中的三条硬性约束）：

1. 表尾 `0x100 + 8N` 恒等于第 0 个条目的 `offset`；
2. 对任意 `i`，`offset[i] == offset[i-1] + size[i-1]`，**零处例外**；
3. 最后一个条目末尾恒等于文件长度。

| 库 | 条目数 | 表尾 | 文件长度 |
| --- | --- | --- | --- |
| `Spr.lib` | 1,790 | `0x38f0` | 41,335,164 |
| `ResJM.Lib.chs` | 2,183 | `0x4538` | 94,835,558 |
| `map_nanfang.lib` | 6,300 | `0xc5e0` | 15,233,656 |
| `ResPlayer1.lib` | 5,248 | `0xa500` | 63,711,177 |
| `ResExNpc1.lib` | 2,182 | `0x4530` | 185,100,483 |

最小复现（40 行内可完成解包）：

```python
head = f.read(0x14)
assert head[:10] == b"leyiLib2.0"
n = struct.unpack_from("<I", head, 0x10)[0]
f.seek(0x100)
table = f.read(8 * n)
for i in range(n):
    off, size = struct.unpack_from("<II", table, i * 8)
```

**库内没有文件名。** 条目只按序号寻址，序号语义由游戏侧数据表（`Role.txt` 的"图形ID"列、`PropMdl.txt` 的"图标ID"列）和代码共同决定。这一点决定了改 mod 的路线：改名无用，改数据表里的 ID 才有效。

`zy\idx.lib` 是纯文本清单，即 `BugLog` 里的 `CombineLibEnd`：

```
num=14
name=Spr
name=Res00
name=ResPrior
name=ResPlayer1
name=ResBoss
name=ResNpc2
name=ResJM
name=ResPlayer2
name=ResPlayer3
name=ResNpc3
name=ResExNpc1
name=ResExPlayer1
...
```

引擎按此表把 14 个库合并成一个虚拟命名空间（`%s%s.lib` 模板 + 语言后缀拼出 `ResJM.Lib.chs`）。

## 2. `lep` —— 库内图片条目

`ResJM` / `map_*` 的条目以 `6C 65 70 00`（`"lep\0"`）开头。头部已定位的字段：

```
0x00  "lep\0"
0x04  u32        条目自身的长度/校验值（随条目变化，语义待定）
0x08  u32,u32    与语言/尺寸相关的一组值
0x10  ...        标志位区，多条目共享 00 10 10 01 00 00 00 00 00 1F F8 00 的特征序列
0x30  u32[]      子图偏移表，单调递增，最后一项 + 末块长度 == 条目长度
```

`map_nanfang.lib` 的 6,300 个条目全部是 2,410 字节、头部字节序列完全一致 —— 这是**等尺寸地图瓦片**，非常适合作为第一个完整解码目标（结构规整、可穷举验证）。

`ResJM`（界面）条目尺寸在 60B–2.6MB 之间浮动，头部同样是 `lep`，说明 `lep` 是通用的位图容器，内部按子图切块。

**未解部分**：像素编码（疑似 8bit 调色板 + RLE，或 16bit RGB565）。判定方法见 [04-engine-runtime.md](04-engine-runtime.md) 的逆向待办。

## 3. `lep` 包 —— 精灵帧组

`Spr.lib` / `ResPlayer*.lib` 的条目外层还有一层：

```
0x00  u32 count
0x04  u32 offset[count]     相对条目起点，单调递增
...   每段都是一张 "lep" 图片
```

例：`ResPlayer1.lib` 第 0 条 68,392 字节，前缀 `20 00 00 00 | 84 00 00 00 | EA 08 00 00 ...`，即 32 帧、首帧偏移 `0x84`，`0x84` 处正是 `lep\0`。这层结构就是"角色动画帧序列"。

## 4. `.sy` —— 音效（实为 WAV）

486 个文件中 484 个 `RIFF` 头，采样格式 `01 00 01 00 44 AC 00 00` = PCM / 单声道 / 44100 Hz / 16 bit，带 `cue ` 块。剩下两个特例：

- `SoundMdl.sy`：纯文本索引表（`id <TAB> 文件名 <TAB> 参数`），把逻辑音效 ID 映射到文件；
- `vssver.sy`：64 字节版本标记。

结论：音效不需要解码器，改后缀为 `.wav` 即可直接进任何现代管线。

## 5. `.dhp` —— 过场动画（实为 MPEG-1 PS）

33 个 `.dhp` 中 32 个以 `00 00 01 BA` 开头（MPEG Program Stream pack header），紧跟 `00 00 01 BB` 系统头。唯一例外是根目录那个 0 字节文件。

直接用 ffmpeg 即可转码；`TestDX.exe` / `LogAVI` 说明播放走的是 DirectShow/AVI 路径。

## 6. `.fol` —— 未解容器

三个文件：`cj.fol`（23.2 MB）、`mb.fol`（2.17 MB）、`slr.fol`（444 KB）。
`ComeOn.exe` 偏移 `0x17411c` 处紧邻存放着字面量 `cj\0slr\0mb\0fol`，说明扩展名由"名字 + .fol"拼接。

已排除的可能：

| 假设 | 反证 |
| --- | --- |
| 未压缩 PCM 音频 | 相邻 16bit 样点差均值 / 绝对偏差 = **1.32**（音频应远小于 1），不符合波形连续性 |
| zlib/gzip 流 | 全片段扫描未见合法 `78 9C/01/DA` 头，也无 `1F 8B` |
| `leyiLib2.0` 改名 | 头部不是 ASCII 魔数，且尾部无索引表 |

现有证据：整体熵 7.91–7.96 bit/byte（接近随机），零字节占比仅 0.4%，头部 4 字节恒为 `0x800000NN`（NN 分别为 `0xFF` / `0xB0` / `0x97`）。

`BugLog` 里的 `Slr Init End` 与 `slr.fol` 同名，说明它是某个独立子系统（Slr）的数据包；`cj` 与 `mb` 推测为场景与模板类数据。**下一步只能靠逆向 `ComeOn.exe` 中读取 `fol` 的那条路径**，见待办清单。

## 7. 存档 `.sav`

长度前缀字符串流，见 [04-engine-runtime.md](04-engine-runtime.md#存档格式)。
