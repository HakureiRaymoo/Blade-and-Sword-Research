# `.fol` 容器：已完全解开

三个 `.fol` 是**带文件名的资源包**，格式与 `leyiLib2.0` 同源但多了两层混淆。
`tools/rekit/fol.py` 可以完整列出与解包。

| 文件 | 大小 | 条目数 | 内容 |
| --- | --- | --- | --- |
| `cj.fol` | 23,225,568 | **255** | 64 个场景 × `.MAP` / `.BNT` / `.ONT` / `.Scn` |
| `mb.fol` | 2,165,553 | **176** | **模板/模型包**：`Role.txt`、`Skill.ini`、`BLD_*.Mdl`、`player/`、`trigger/` |
| `slr.fol` | 444,201 | **151** | 150 个 `.PLI` + **`SprRole.h`** |

---

## 1. 格式

### 目录

```
u32  count_raw
     count     = count_raw & 0x7fffffff
     encrypted = (count_raw & 0x80000000) != 0      // 三个文件都是 1

count × 0x88 字节   目录记录（0x88 = 136 字节 = 34 个 dword）
```

每条 0x88 记录：

| 偏移 | 含义 |
| --- | --- |
| `+0x00` | 文件名（`\0` 结尾，GBK；`cj.fol` 里带子目录，如 `000\000_001.PLI`） |
| `+0x80` | 负载在文件内的偏移 |
| `+0x84` | 负载大小 |

### 目录解密（`encrypted` 为真时）

加密用的是 `FUN_004e9de0` 里这段：

```c
fseek(f, -(0x61 + count) * 4, SEEK_END);     // 末尾 0x61 个 dword 是尾巴，前面是种子表
fread(seeds, count * 4, 1, f);

for (i = 0; i < count; i++)
    for (j = 0; j < 34; j++)
        rec[i][j] -= j*j*j * 9 + seeds[i];    // mod 2^32
```

即每个 136 字节记录用**自己的种子**做三阶差分。

### 负载解密（`FUN_004e9d30`）

```c
for (i = 0; i < size >> 2; i++)
    dword[i] -= 99 * i*i + key;               // mod 2^32，尾部不足 4 字节的不管
```

`key` 就是该记录自己的种子 `seeds[i]`。

> 这两层就是之前"熵 8.0、标准压缩全失败"的原因，也是"存在长递增 dword 串、
> 二阶差分恒定"的原因 —— 那些串其实是**种子表**和加密后的标量数组。

### 引擎入口

| 函数 | 作用 |
| --- | --- |
| `FUN_004e25e0` | `InitGameFileProperty()`：拼 `<数据目录>\<名字>.fol`，逐个打开并解析 |
| `FUN_004e9de0` | 解析头部 + 目录 + 种子，按需解密目录 |
| `FUN_004e9c40` | 按文件名在目录里查 `(偏移, 大小)` |
| `FUN_004e9d30` | 按 `(偏移, 大小, 种子)` 读出并解密负载 |

名字表在 `.data`：`0x58d870`（`cj` / `slr` / `mb`）与 `0x58d88c`（`fol`），
由 `FUN_00401050` 启动时用 `CStringList::AddTail` 填进去的。

---

## 2. 内容清单

### `cj.fol` —— 场景（64 套，每套 4 个文件）

```
1-0s.MAP   201,086   头 "LeyiMap1.50"
1-0s.BNT     8,722
1-0s.ONT     2,555
1-0s.Scn       496   ← 纯文本 INI
```

`1-0s.Scn` 解出来是这样的：

```ini
MapFile=1-0s.MAP
BldFile=1-0s.BNT
ObjFile=1-0s.ONT
PortalNum=...
```

`.MAP` 头是 `LeyiMap1.50`，`.BNT` 推测是建筑层、`.ONT` 是物件层。

### `mb.fol` —— 模板 / 模型（这是意外之喜）

它是**开发期的数据目录**，整套原始工程文件都在里面：

| 类别 | 文件 |
| --- | --- |
| 数据表 | `Role.txt`、`PropMdl.txt`、`RoleQuest.txt`、`TriggerQuest.txt`、`Text.txt`、`Dialog_Public1..3.txt`、`ScnInfo.txt`、`RoleEffectMdl.txt`、`RolePrivate.txt`、`RandProp.txt`、`PropUpgrade.txt`、`MethodPoint.txt` |
| 技能 | `Skill.ini`(330 KB)、`SkillChild.ini`、`methodgroup.txt`、`Skill.gop`、`Role.rmd` |
| 字体 | `Font.txt`、`Font2000.txt`、`Font98.txt`、`define.ini` |
| **模型** | `BLD_Diyu.Mdl`、`BLD_Grave.Mdl`、`BLD_icecave.Mdl`、`BLD_Nanfang.Mdl`、`BLD_Ren.Mdl`、`BLD_Snow.Mdl` —— 头是 **`leyibld1.50`** |
| 玩家 | `player/Init.txt`（角色基础属性表）、`player/skill.txt`（技能表）、`player/skill.xls`、`player/Init.xls`、`player/InitWWW.xls`、`player/vssver.scc` |
| 触发 | `trigger/scene/`（61 个）、`trigger/talk/`（65 个）、`trigger/flag.txt` |

`player/Init.txt` 是一张很干净的属性表：

```
名称  ID  AT  AT升级增加值  DF  DF升级增加值  ...  HP  HP升级增加值  回血率 ...
男主角  4  40   4            30   4             ...  800  80  1.4
女主角 30  30   3            40   5             ...  600  60  1
```

`trigger/scene/1-0s.txt` 是**触发器脚本**，一门小 DSL：

```
触发条件	触发结果	是否循环
IsScnIn	ChangeAct 0
IsScnIn*IsFlag Act1 0	ShowActForeword 123 1447 0*SetFlag Act1 1
IsScnIn*IsFlag SY1 100 1	RemItem sws
IsScnIn*IsFlag bq1 70 1	RemItem zhs
```

条件用 `*` 串联，动词有 `IsScnIn` / `IsFlag` / `SetFlag` / `SetFlagTable` / `ChangeAct` /
`ShowActForeword` / `RemItem` / `ResetObj`。

### `slr.fol` —— 精灵角色 + **名字映射表**

150 个 `NNN\NNN_001.PLI`，头 `PLI\0`，正文里带 `Author : Seraph`。

**真正值钱的是 `SprRole.h`（35 KB）** —— 一张生成的 C 头文件，
把 `Spr` 库里的每个条目都起了名字：

```c
#define SPR_ROLE_000_TKS_001_001   639
#define SPR_ROLE_000_TK_001_001    618
#define SPR_ROLE_001_CAS_001_001     5
#define SPR_ROLE_001_CA_001_001      4
#define SPR_ROLE_001_HDS_001_001     3
#define SPR_ROLE_001_LA_001_001    339
#define SPR_ROLE_001_RA_001_001    341
```

名字结构是 `角色编号_部位_动作_变体`，部位缩写里能认出
`TK`（躯干）/`HD`（头）/`LA`·`RA`（左右臂）/`CA`（?）/`S` 后缀（推测是朝向或带武器版本）。

**这直接解决了"`Spr` 条目语义不明"的问题**：之前靠尺寸和帧数猜部件，
现在可以直接按名字归类。

---

## 3. 复现

```powershell
cd tools\rekit
python fol.py info    slr.fol
python fol.py list    mb.fol  --limit 200
python fol.py extract cj.fol  --out ..\..\out\fol\cj
python fol.py extract mb.fol  --out ..\..\out\fol\mb
python fol.py extract slr.fol --out ..\..\out\fol\slr
```

解包结果在 `out/fol/`（不进仓库）。

---

## 4. 由此打开的新问题

1. **`SprRole.h` 与 `Spr` 库对号**：宏值是 `Spr` 的条目下标吗？抽样核对一下
   （`SPR_ROLE_001_RA_001_001 = 341`，而 `Spr#34` 是腿…… 需要用真实名字反查）。
2. **`.Mdl`（`leyibld1.50`）与 `.MAP`（`LeyiMap1.50`）格式**：建筑层与地图层的
   二进制结构，是以后做地图/场景重制的关键。
3. **`.PLI` 结构**：150 个文件，`PLI\0` 头，里面应该就是 `Spr` 之外的那一层
   "角色装配"数据。
4. `player/*.xls` 是真正的 Excel 文件，里面可能有比 `txt` 更全的设计数据。
5. `trigger/` 的 DSL 可以整理成文档，这是重制版做任务系统时的现成规格。
