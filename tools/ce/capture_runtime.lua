--[[----------------------------------------------------------------------
  刀剑封魔录外传：上古传说 —— 运行时结构抓取 (capture_runtime.lua)

  用法
    1. 游戏正常跑着，人物站在地图里（可见即可，别在菜单里）。
    2. Cheat Engine -> 菜单 Table -> Show Cheat Table Lua Script（Ctrl+Alt+L）
    3. 把本文件**全文**粘进 Lua Engine，点 Execute。
    4. 看到 "capture #1 done" 后，回到游戏窗口点一下。
    5. 之后每按一次 F6 抓一次快照（F6 是全局热键，焦点在游戏里也能用，
       不会把游戏踢出前台）。想抓几次抓几次。
    6. 抓完告诉我，我去读 out\ce\snapshot_*.txt。

  抓什么
    A. 进程/模块基址（确认 ddraw 用的是 cnc-ddraw 还是 dgVoodoo）
    B. 内存里所有 "lep\0" 图像对象（已解码的图），带 bpp / 宽高
    C. 所有 "lib 条目对象"（vtable = 0x005540A4 / 0x005540A8 / 0x00554104）
       —— 引擎把库条目解析出来的结果，我们要找的就是它们
    D. 每个条目对象的 +0x1C(类型) +0x24(数据指针) +0x28(子对象表) +0x2C(数量)
       以及它指向数据的前 24 个双字

  注意：只扫可写内存（+W），全盘扫太慢；CE 仍会卡几秒到几十秒，属正常。
------------------------------------------------------------------------]]

local OUTDIR = "D:\\DSH WORK SPACE\\Blade-and-Sword-Modernized\\out\\ce\\"
local MAX_IMG = 400      -- 图像对象最多记这么多条
local MAX_OBJ = 600      -- 条目对象最多记这么多条
local PREVIEW = 24       -- 每个对象预览多少个双字
local PROT = "+W"        -- 只扫可写内存

----------------------------------------------------------------- 小工具

local buf = {}

local function w(s)
    buf[#buf + 1] = s
end

local function u32(a)
    local ok, v = pcall(readInteger, a)
    if ok and v then return v end
    return nil
end

local function u16(a)
    local ok, v = pcall(readSmallInteger, a)
    if ok and v then return v & 0xFFFF end
    return nil
end

local function u8(a)
    local ok, v = pcall(readByte, a)
    if ok and v then return v end
    return nil
end

local function ptr(a)
    local ok, v = pcall(readPointer, a)
    if ok and v then return v end
    return nil
end

local function modbase(name)
    local ok, v = pcall(getAddress, name)
    if ok and v then return v end
    return nil
end

local function hx(v)
    if v == nil then return "??" end
    if v < 0 then v = v + 4294967296 end
    return string.format("%08X", v)
end

local function dec(v)
    if v == nil then return "??" end
    return tostring(v)
end

-- AOB 扫描，返回 (前 cap 个地址, 命中总数)
local function scan(pat, cap)
    local out = {}
    local ok, sl = pcall(AOBScan, pat, PROT)
    if not ok or sl == nil then return out, 0 end
    local total = sl.Count
    for i = 0, math.min(total, cap) - 1 do
        local a = tonumber(sl[i], 16)
        if a then out[#out + 1] = a end
    end
    sl.destroy()
    return out, total
end

local function le32(v)
    v = v & 0xFFFFFFFF
    return string.format("%02X %02X %02X %02X",
        v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF)
end

local function preview(a, n)
    local t = {}
    for i = 0, n - 1 do
        t[#t + 1] = dec(u32(a + i * 4))
    end
    return table.concat(t, " ")
end

-------------------------------------------------------------- 抓取主体

local captureCount = 0

local function capture()
    buf = {}
    captureCount = captureCount + 1

    local pid = getOpenedProcessID()
    if pid == nil or pid == 0 then
        local p = getProcessIDFromProcessName("ComeOn.exe")
        if p == nil or p == 0 then
            print("[capture] 没找到 ComeOn.exe，先在 CE 里附加进程")
            return
        end
        openProcess(p)
        pid = p
    end

    w("== Blade&Sword runtime snapshot ==")
    w("time      : " .. tostring(os.date("%Y-%m-%d %H:%M:%S")))
    w("capture # : " .. captureCount)
    w("pid       : " .. tostring(pid))
    w("ComeOn.exe: " .. hx(modbase("ComeOn.exe")))
    w("ddraw.dll : " .. hx(modbase("ddraw.dll")))
    w("DDRAW.dll : " .. hx(modbase("DDRAW.dll")))
    w("d3d9.dll  : " .. hx(modbase("d3d9.dll")))
    w("")
    print(string.format("[capture] #%d 开始，扫描中，CE 会卡一会儿……", captureCount))

    ---------------------------------------------------- B. lep 图像对象
    w("---- B. lep 图像对象 (magic 'lep\\0') ----")
    local imgs, nimg = scan("6C 65 70 00", MAX_IMG)
    w(string.format("total hits: %d (recorded %d)", nimg, #imgs))
    for _, a in ipairs(imgs) do
        -- +0x15 bpp, +0x16 flags, +0x1C / +0x20 宽高, +0x28/+0x2C/+0x30 行表
        w(string.format("  img %s bpp=%s f16=%s d1C=%s d20=%s d24=%s d28=%s d2C=%s d30=%s",
            hx(a), dec(u8(a + 0x15)), dec(u8(a + 0x16)),
            dec(u32(a + 0x1C)), dec(u32(a + 0x20)), dec(u32(a + 0x24)),
            dec(u32(a + 0x28)), dec(u32(a + 0x2C)), dec(u32(a + 0x30))))
    end
    w("")

    ------------------------------------------------- C. lib 条目对象
    local vtables = {
        { name = "PTR_FUN_005540A4 (普通图)", va = 0x005540A4 },
        { name = "PTR_FUN_005540A8 (帧包)",   va = 0x005540A8 },
        { name = "PTR_FUN_00554104 (扩展)",   va = 0x00554104 },
    }
    w("---- C. lib 条目对象 (vtable 扫描) ----")
    for _, vt in ipairs(vtables) do
        local hits, total = scan(le32(vt.va), MAX_OBJ)
        w(string.format("vtable %s  0x%08X  total=%d recorded=%d",
            vt.name, vt.va, total, #hits))
        for _, a in ipairs(hits) do
            local data = ptr(a + 0x24)
            local sub = ptr(a + 0x28)
            local cnt = u16(a + 0x2C)
            w(string.format("  obj %s type=%s flag1D=%s cnt=%s data=%s sub=%s",
                hx(a), dec(u8(a + 0x1C)), dec(u8(a + 0x1D)),
                dec(cnt), hx(data), hx(sub)))
            if data then
                w("      data[]: " .. preview(data, PREVIEW))
            end
            if sub and cnt and cnt > 0 and cnt < 200 then
                local t = {}
                for i = 0, math.min(cnt, 8) - 1 do
                    t[#t + 1] = hx(ptr(sub + i * 4))
                end
                w("      sub[] : " .. table.concat(t, " "))
            end
        end
        w("")
    end

    local path = OUTDIR .. string.format("snapshot_%s_%02d.txt",
        os.date("%Y%m%d_%H%M%S"), captureCount)
    local f = io.open(path, "w")
    if f == nil then
        print("[capture] 写不了文件，下面直接打印：")
        print(table.concat(buf, "\n"))
        return
    end
    f:write(table.concat(buf, "\n"))
    f:write("\n")
    f:close()
    print(string.format("[capture] #%d done -> %s  (%d 行)", captureCount, path, #buf))
end

------------------------------------------------------------------ 入口

local VK = VK_F6 or 0x75

capture()                       -- 立刻抓一次
createHotkey(capture, VK)       -- 之后按 F6 再抓
print("[capture] F6 热键已装好。别关这个 Lua Engine 窗口，关了热键就没了。")
