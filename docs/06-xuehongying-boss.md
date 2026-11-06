# 薛红影是谁：3-17s 的三连 Boss 之一

结论先说：**薛红影是终盘一场"三连 Boss"战里的女性 Boss**，不是废案，
也不是可选角色。她在数据里只出现在一处，但那一处非常明确。

---

## 1. 她的全部数据

`Role.txt` 第 52 号：

| 列 | 值 |
| --- | --- |
| 角色名称 / 角色ID | 薛红影 / 52 |
| 头像ID / 图形ID | 43 / 408 |
| 组 | `10001`（与玩家同阵营） |
| 大小 / 脚数 / 平时速度 | 48 / 2 / 8 |
| 部位（`SprRole.h` 408） | `CA` 腿、`HD` 头、`TK` 躯干 + 各自影子（6 条表） |
| 技能（`Skill.ini`） | 16 条：普通攻击 / 跳 / 砍 / 刺 / 连击 1~4 / 连击强化若干 |

渲染出来是一个**双刀女战士**：

![薛红影](img/xuehongying.png)

（图注：见 `out/shots/xuehongying.png`，两帧，双手各持一把弯刀。）

## 2. 她在哪：`3-17s` 场景，事件名 `bossnv`

64 个场景的 `.ONT` 里，`ModelID=52` **只出现一次**，在 `3-17s.ONT`：

```ini
Type=12
ModelID=52
MapX=65
MapY=54
MoveLevel=4
EventID=bossnv        ← boss 女
Logic_Dir=7
```

同一个场景里还有另外两个非杂兵对象：

| EventID | ModelID | 角色 |
| --- | --- | --- |
| `sdyx` | 230 | **老英雄**（Boss 版，不是可玩的那个 1 号） |
| `bossnan` | 60 | **南霁云** |
| `bossnv` | **52** | **薛红影** |

外加 12 个杂兵（`bing1`~`bing12`：恶灵 / 爆弹兵 / 飞刀小妖头目）。

> 这也解释了为什么 `Role.txt` 里有**两个「老英雄」**：
> `角色ID=1` 是可玩角色，`角色ID=230` 是这场 Boss 战的版本（同一个图形ID 655）。

## 3. 触发器脚本怎么写的

`mb/trigger/scene/3-17s.txt` 里读得很清楚：

```text
IsScnIn          ResetObj bingN * SetFlagTable bingN 111 0 * AddFellow bingN 1 * TransToPlayer bingN 5
                 （进场：杂兵先被"加为同伴"并传送到玩家身边）

IsScnIn*IsFlag 3bq3 9 2*IsFlag 3bq3 100 1
                 SetGroup sdyx 3 * SetGroup bossnan 3 * SetGroup bossnv 3
                 SetPlayerID bossnan sdyx * SetPlayerID bossnv sdyx
                 （关键旗标触发：三人从阵营 10001 翻成 3，即变成敌对）

IsDead bossnan*IsDead bossnv*IsDead sdyx*IsFlag ... (一大堆前置旗标)
                 ShowHideRole
                 （三个都死了才过关）

IsDead ...*IsFlag 3bq3 100 1     SetFlag 3bq3 100 * ScreenEffect 5
IsBlack 1*IsFlag 3bq3 100        ShowJM 219
                 （黑屏 + 弹 UI 面板 219，结算/结局演出）
```

## 4. 所以「组 = 10001」不是"友军"，而是"初始不敌对"

上一版文档（05）里我把 `组=10001` 一律解释成友军 NPC，**这个说法要修正**：

- `组` 是**初始阵营**
- 剧情脚本可以用 `SetGroup <对象> <组>` 随时改写
- 所以同样是 `10001`：既有真正的剧情 NPC（沈万山、沈云、天将——他们在对话表里有台词），
  也有"一开始中立/友好、到某个旗标翻脸"的 Boss（老英雄230 / 南霁云 / 薛红影）

这三位是**同一场 Boss 战的三个人**，一起翻脸、必须全部击杀。

## 5. 顺带：`.ONT` 是一个新的、很好用的改造面

`cj.fol` 里的 `.ONT` 是**纯文本 INI**，字段一目了然：

```
All=225  Bld=87  CHA=138  PROP=0  Bea=0  BldMdl=
Type=12            ← 对象类型
ModelID=159        ← 角色ID（对应 Role.txt 的"角色ID"）
MapX=23  MapY=106  ← 地图格坐标
Logic=0  MoveLevel=4
MoveRangeX/Y/Cx/Cy ← 活动范围
EventID=bossjiang  ← 触发器里用的对象名
Group=0
data1..data3       ← 自由字段
Logic_Init=0
Logic_Dir=7        ← 初始朝向
```

也就是说：**改刷怪、改 NPC 位置、改 Boss 摆位，全是改文本**，
再用 `fol.py pack --from cj.fol` 打回去即可。

