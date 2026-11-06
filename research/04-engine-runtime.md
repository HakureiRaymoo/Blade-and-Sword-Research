# 引擎与运行时

## 1. 可执行文件

`ComeOn.exe`，1,548,288 字节。

| 项 | 值 |
| --- | --- |
| 格式 | PE32（i386），4 个节 |
| 链接时间 | 2003-07-29 14:41:57 UTC |
| 编译器 | MSVC（存在 `Rich` 头） |
| 节 | `.text` 1.37 MB / `.rdata` 77 KB / `.data` 249 KB / `.rsrc` 3.5 KB |
| 版本资源 | 已被剥离（无 CompanyName / FileVersion） |
| 基址特性 | 无 ASLR / 无 DEP 标记，标准 2003 年构建 |

### 导入表（信息量最大的一处）

| DLL | 关键导入 | 说明 |
| --- | --- | --- |
| `DDRAW.dll` | `DirectDrawCreateEx` | **唯一的图形入口**，纯 DirectDraw 7 表面 blit |
| `GDI32.dll` | `BitBlt` `CreateDIBSection` 系 `GetDIBColorTable` `TextOutA` 等 33 项 | 位图与文字渲染 |
| `DSOUND.dll` | 序号 `#11`（DirectSoundCreate） | 音频 |
| `WINMM.dll` | `mmioOpenA` `mmioDescend` `mmioRead` `mmioCreateChunk` … | **RIFF/WAV/AVI 容器读写**，正好对应 `.sy`=WAV、`.dhp`=MPEG 的事实 |
| `ole32.dll` | `CoCreateInstance` | 推测用于 DirectShow 播放过场 |
| `USER32/GDI32` | 经典 Win32 UI | 窗口、消息循环、字体 |

文件中**没有**任何 D3D8/D3D9 导入 —— 目录里的 `D3D8.dll`、`D3DImm.dll` 只是 dgVoodoo2 的转译件，不是游戏自己在用。这一点很重要：**渲染层是二维软件 blit，没有 3D 管线**，所以"高清化"本质是替换 blit 与纹理采样，不存在网格/着色器重构的负担。

## 2. 引擎身份

`.rdata` 中并存的一组字面量（偏移 `0x175528` 起）：

```
LeyiMap1.50      # 地图构建器版本
LeyiInit1.00     # 初始化库版本
leyibld1.50      # 构建器
leyiLib2.0       # 资源库格式版本
Font.txt         # 字体描述文件
MapFile / BuildMap / LoadMap
%s%s.lib         # 库名拼接模板（名字 + .Lib + 语言后缀）
Zy\PixelGame.lib
idx.lib
%s\dhp\begin.dhp
%sdhp\%s.dhp
```

`0x17411c` 处还紧邻排列着 `cj\0slr\0mb\0fol\0`，即三个 `.fol` 文件的拼接常量。

所以这是一个自研引擎族，代号 **Leyi**，至少包含 Map 1.50 / Init 1.00 / Lib 2.0 三个子系统，且被同一公司复用到其他作品。找同引擎的其它游戏，是拿现成解析器的捷径。

## 3. 启动时序

`BugLog.ini` 记录了一次完整启动，按顺序：

```
InitGameFileProperty()     读 set.ini / ComeOn.ini
EndInitInstance
SetCooperativeLevel  DD_OK
SetDisplayMode       DD_OK
Set DirectDraw SetDisplayEnd
Init CombineLibEnd         合并 zy/idx.lib 里的 14 个库
SoundInitEnd               声音子系统
MdlInitEnd                 模型/数据表
Slr Init End               Slr 子系统（对应 slr.fol）
3DEffect Init End          2D 特效
InitJM()                   界面（ResJM.Lib）
StartAppEnd()
LogAVI                     过场（begin.dhp）
```

给逆向的启示：想定位任意子系统，从 `InitGameFileProperty` 之后的调用链按日志顺序断点即可，日志字符串本身就在 exe 里可搜索。

## 4. 存档格式

`save\剑客.sav`，144 字节。结构是 **u32 长度前缀 + 以 `\0` 结尾的字符串**：

```
0000  02 00 00 00            整数 2
0004  04 00 00 00 "1.5\0"    长度 4 的字符串：存档版本 "1.5"
000c  e9 07 00 00            0x7E9（可能是年份/校验值）
0010  0c 00 00 00 02 00 00 00 09 00 00 00 23 00 00 00 12 00 00 00
0030  22 00 00 00  ...       变长记录区
0040  04 00 00 00 "901\0"    ← 与 Role.txt 的"图形ID"一致
0048  04 00 00 00 "001\0"    ← 与"动作"一致
0050  24 00 00 00 "001*001*005*000*000*000*000*000*005*001\0"
```

`901` / `001` / `001*001*005*…` 与 `Role.txt` 中剑客一行（`图形ID=901`、`动作=001`、`属性=001*001*…`）同构，说明**存档存的是角色表的运行时副本**。同目录下 `剑客.000/.001/.002`、`长老.*`、`剣豪.*` 是分槽位/分章节的附属文件。

这给出了一条低成本的 mod 路径：不碰内存，直接改存档里的字符串字段。

## 5. 兼容层现状

官方版本已经在用两层"外挂"解决现代系统问题：

```
ComeOn.exe ──> DDRAW.dll (dgVoodoo2)  ──> D3D11/12  ──> 现代 GPU
           └─> ddraw.dll  (cnc-ddraw) ──> GDI/OpenGL ──> 窗口化、缩放、着色器
```

`cnc-ddraw` 提供了窗口化、整数缩放、CRT/scanline/xBR/FSR 等后处理（`Shaders\` 目录）。这意味着**分辨率与后处理已经有了可配置的出口**，改造时不必从零写渲染层。

## 6. 逆向待办（按性价比排序）

| # | 目标 | 方法 | 产出 |
| --- | --- | --- | --- |
| 1 | `lep` 像素解码 | Ghidra 载入 exe，从 `leyiLib2.0` 字符串交叉引用找到库解析函数，再跟到 `lep` 的解压/调色板设置 | 可导出 PNG，验证方式：解码 `map_nanfang` 的 6,300 张等长瓦片，看是否形成连续地图 |
| 2 | `.fol` 容器 | 从 `cj`/`slr`/`mb` 字面量交叉引用找到加载函数，看是否有解压调用 | 解开 23 MB 的 `cj.fol` |
| 3 | 输入处理 | 从 `GetAsyncKeyState`/`GetCursorPos` 的调用点回溯到战斗输入状态机 | 得到输入缓冲与招式判定逻辑，服务于现代化输入层 |
| 4 | 战斗数值 | 交叉引用 `Role.txt` 的读取函数，定位结构体内存布局 | 得到硬直/浮空/取消窗口的真实语义 |
| 5 | 渲染坐标 | 找 `SetDisplayMode` 附近的视口计算 | 得到宽屏改造的切入点 |

工具准备：工作区已有 Ghidra（`D:\DSH WORK SPACE\ghidra_home`），可直接做 headless 反编译。上述 #1 与 #2 目标明确、收益最高，建议作为下一轮的主攻方向。
