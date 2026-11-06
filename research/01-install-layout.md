# 安装目录结构

- 样本：`D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说`
- Steam appid `2924510`，depot `2924511`，build `21003896`，`SizeOnDisk` 2,409,354,731 字节
- 安装后 `ComeOn.ini` 中 `Version=1.02`、`current_language=chs`

## 目录语义

目录名全部是中文拼音首字母，这是理解整套资源结构的第一把钥匙：

| 目录/文件 | 拼音 | 含义 | 体量 |
| --- | --- | --- | --- |
| `zy\` | 资源 zīyuán | 图像/精灵大库，25 个 `.Lib` | 1,829 MB |
| `sy\` | 声音 shēngyīn | 音效，486 个 `.sy`（实为 WAV） | 51 MB |
| `yy\` | 音乐 yīnyuè | 25 首 BGM（MP3） | 41 MB |
| `th\` | 贴图 tiētú | 少量 BMP 特效图（如 `fog.bmp`） | <1 MB |
| `dhp\` | 动画片 dònghuàpiàn | 过场动画，29 个（实为 MPEG-1） | 83 MB |
| `bdh\` | 本地化 běndìhuà | 四种语言各自的数据表 + 片头动画 | 各 ~65 MB |
| `save\` | — | 存档 | 极小 |
| `ScreenShot\` | — | 截图输出目录 | — |

`bdh` 下四套语言：`chs` / `cht` / `eng` / `jpn`，每套 10 个文件，结构完全一致：

```
begin.dhp           片头动画（MPEG-1），chs/cht 各 68,384,768B，eng/jpn 各 67,598,336B
PropMdl.txt         物品表（18 列）
Role.txt            角色表（47 列）
RoleQuest.txt       怪物图鉴（5 列）
Dialog_Public1..3.txt / Dialog_private.txt   对话与称谓表
TriggerQuest.txt    任务触发器
Text.txt            UI 字符串表（id → 文本）
```

同一份 `begin.dhp` 在 chs/cht 下字节数完全相同，说明视频流复用、只替换音轨或字幕轨 —— 做多语言剥离时可以直接比对。

## 程序与运行环境

| 文件 | 说明 |
| --- | --- |
| `ComeOn.exe` | 主程序，1.5 MB，32 位 MSVC，链接时间 2003-07-29，导入 `DDRAW.dll` / `GDI32.dll` |
| `ComeOn.dll` | 288 KB，角色未定（可能是输入/加密辅助），待逆向 |
| `launcher.exe` | 5.7 MB，含 libcurl 字符串，负责启动与联网（更新/统计），不是游戏本体 |
| `D3D8.dll` / `D3DImm.dll` / `ddraw.dll` / `dgVoodoo.conf` | **dgVoodoo2** 转译层，把 D3D8/DirectDraw 调用转到现代图形 API |
| `cnc-ddraw config.exe` / `ddraw.ini` | **cnc-ddraw**，另一套 DirectDraw 兼容层，与 dgVoodoo 叠用 |
| `Shaders\` | cnc-ddraw 的后处理着色器：`crt` / `scanlines` / `xbr` / `xbrz` / `sharpen` / `interpolation`（含 FSR、jinc2、lanczos） |
| `TestDX.exe` | DirectX 能力检测，输出 `DisplayCapability.INI` |

也就是说：**官方 2025 年的"移植"本质是原版 exe + 外部兼容层 + 着色器**，引擎代码几乎未改（exe 时间戳仍是 2003 年）。这带来两个直接结论：

1. 现代化改造不必从"重写渲染"起步，兼容层已经把画面管线接出来了；
2. 但分辨率、帧率、输入、UI 都还是 2003 年的逻辑，真正的现代化空间在**上层**。

`DisplayCapability.INI` 示例（本机）：

```ini
3dFunc=0
VedioMemory=523922688
ZoomCap=1
AlphaCap=1
DXVersion=8.1
```

`BugLog.ini` 保留了一次启动的完整时序，是理解引擎初始化顺序的免费线索：

```
comeon begin
InitGameFileProperty() 1
System:9200 6 2 2
EndInitInstance
SetCooperativeLevel:DD_OK
SetDisplayMode:DD_OK
780  Set DirectDraw SetDisplayEnd
1  Init CombineLibEnd
136  SoundInitEnd
1421  MdlInitEnd
135  Slr Init End
0  3DEffect Init End
Begin InitJM()  /  End InitJM()
47  StartAppEnd()
LogAVI
```

注意 `Slr Init End` 与根目录 `slr.fol` 同名，`CombinedLib` 对应 `zy\idx.lib` 的库清单 —— 初始化阶段就是"合并库 → 声音 → 模型 → Slr → 3D 特效 → 界面(JM)"。

## 体积构成

| 类别 | 文件数 | 大小 |
| --- | --- | --- |
| `zy/*.Lib` | 25 | 1,829 MB |
| `dhp/*.dhp` | 29 | 83 MB |
| `bdh/<lang>`（四语言） | 40 | 260 MB |
| `sy/*.sy` | 486 | 51 MB |
| `yy/*.mp3` | 25 | 41 MB |
| 兼容层 + 着色器 | 21 | 6 MB |
| 程序与配置 | 9 | 8 MB |

## 已知异常

- 根目录 `dhp\begin.dhp` 为 **0 字节**，实际生效的是 `bdh\<lang>\begin.dhp`（exe 中路径模板为 `%s\dhp\begin.dhp`，说明引擎会在语言目录下重新拼接路径）。
- `zy\ResExPlayer2.Lib` 只有 256 字节、条目数为 0 —— 空的占位库，打包时可能漏了内容，值得和正传比对。
- `zy\PixelGame.lib` 仅 1 字节（内容 `0x31`，即字符 `1`），像是版本标记文件。
