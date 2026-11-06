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

## 2. `lep` —— 库内图片条目（已解）

`ResJM` / `map_*` / 角色帧的条目都以 `6C 65 70 00`（`"lep\0"`）开头。

```
0x00   4B   "lep\0"
0x04  44B   头部。部分字段已识别（见下），其余语义待定
0x30   4N   行偏移表：N 个 u32，值是相对 0x30 的偏移
0x30+4N     行数据
```

判定表长的办法：`N = 表首值 / 4`，且 `0x30 + 4N` 必等于首行起点。

### 行编码

每行是一个"间隙—像素"三元组的重复序列，末尾再跟一个收尾间隙：

```
row := gap:u16  count:u16  pixels[count]  ...  gap:u16
```

- `gap` 是相对上一段末尾的**字节**距离（即透明留白的宽度）
- `count` 是本段像素数据的字节数
- 同一行可以有**多段**，对应同一扫描线上的多个不透明区间
- 恒等式：`Σgap + Σcount` 在同一张图内**所有行都相等**，等于扫描线字节数 W

于是画布尺寸 = `W / 2` × `行数`，每段按累计 gap 直接落到 x 坐标上，不需要任何居中猜测。

### 像素编码

**16 位 RGB565，小端，2 字节/像素**，无调色板、无压缩、无 alpha 通道。

透明由"未被任何段覆盖"隐式表达；头部另有一个 `0xF81F`（洋红）常量，疑似色键，但按段裁剪后已无必要。

### 验证

对 5 个库共 120 张图逐行套用恒等式：

```
ResJM.Lib.chs      uniform-rows: 40    inconsistent: 0
map_nanfang.lib    uniform-rows: 40    inconsistent: 0   (W = 128B = 64px)
map_snow.lib       uniform-rows: 40    inconsistent: 0
map_grave.lib      uniform-rows: 40    inconsistent: 0
```

`map_nanfang` 的 6,300 张瓦片全部为 64×32、W=128，行宽 4→64→4 像素对称变化，即等距菱形地砖。

### 踩过的坑（方法论备忘）

最初把行首的 `gap` 当成像素一起渲染，结果每块地砖都带一圈**蓝色描边**——`gap` 值 0x3C/0x38/0x34… 在 RGB565 下正好解成深蓝。蓝色描边不是美术，是解析错误的签名。后来又把"每行只有一段"当成前提，UI 图标被切成碎片，才发现在同一扫描行里可以有多个段。

## 3. 精灵帧包 —— 角色动画

`Spr.lib` / `ResPlayer*.lib` / `ResBoss.lib` 的条目外层还有一层：

```
0x00  u32 count
0x04  u32 offset[count]     相对条目起点，单调递增
...   每段都是一张完整的 "lep" 图片
```

关键不变量：`offset[0] == 4 + 4*count`，即帧表紧贴条目头部。

例：`ResPlayer1.lib` 第 0 条 68,392 字节 = 32 帧，首帧偏移 `0x84`（= 4 + 32×4）。

每帧都是独立裁切过的 `lep`，所以帧的画布尺寸并不一致（同一段奔跑动画里可能是 45×45、42×48、40×50……）。**这意味着帧锚点必须来自头部某个尚未识别的字段**，否则回放会抖动。当前导出的 PNG 是"每帧自身包围盒"，拼合动画时需另行对齐 —— 这是 `lep` 剩余的唯一硬缺口。

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
