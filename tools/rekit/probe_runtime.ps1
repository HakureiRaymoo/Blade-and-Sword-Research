# probe_runtime.ps1 -- dump live "lep" headers out of the running game.
#
# Run this from a NORMAL PowerShell (not the agent sandbox, which is Low
# integrity and cannot open other processes). It needs the same user as the
# game; if the game runs elevated, run this elevated too.
#
#   pwsh -ExecutionPolicy Bypass -File probe_runtime.ps1
#
# Output: runtime_lep.txt in the current directory.

$ErrorActionPreference = 'Stop'

$src = @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public class Rt {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);

    [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, IntPtr size, out IntPtr read);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MEMINFO mbi, IntPtr len);

    [StructLayout(LayoutKind.Sequential)]
    public struct MEMINFO {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public uint align1;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
        public uint align2;
    }

    public static uint FindByTitle(string title) {
        uint found = 0;
        EnumWindows((h,l) => {
            var sb = new StringBuilder(512);
            GetWindowTextW(h, sb, 512);
            if (sb.ToString().IndexOf(title, StringComparison.OrdinalIgnoreCase) >= 0) {
                uint pid; GetWindowThreadProcessId(h, out pid);
                found = pid;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }

    public static List<string> Scan(uint pid, out string err) {
        var outLines = new List<string>();
        err = null;
        IntPtr h = OpenProcess(0x0410, false, pid);   // QUERY_INFORMATION | VM_READ
        if (h == IntPtr.Zero) {
            err = "OpenProcess failed, Win32 error " + Marshal.GetLastWin32Error();
            return outLines;
        }
        try {
            IntPtr addr = IntPtr.Zero;
            long limit = (long)IntPtr.MaxValue.ToInt64();
            int hits = 0;
            var buf = new byte[4 * 1024 * 1024];
            while (addr.ToInt64() < limit) {
                MEMINFO mbi;
                if (VirtualQueryEx(h, addr, out mbi, (IntPtr)Marshal.SizeOf(typeof(MEMINFO))) == IntPtr.Zero) break;
                long baseAddr = mbi.BaseAddress.ToInt64();
                long size = mbi.RegionSize.ToInt64();
                bool readable = mbi.State == 0x1000 &&
                    (mbi.Protect == 0x04 || mbi.Protect == 0x02 || mbi.Protect == 0x20 ||
                     mbi.Protect == 0x08 || mbi.Protect == 0x40 || mbi.Protect == 0x80);
                if (readable && size > 0) {
                    for (long off = 0; off < size; off += buf.Length) {
                        int chunk = (int)Math.Min(buf.Length, size - off);
                        IntPtr rd;
                        if (!ReadProcessMemory(h, (IntPtr)(baseAddr + off), buf, (IntPtr)chunk, out rd)) break;
                        for (int i = 0; i + 64 < chunk; i++) {
                            if (buf[i] == 0x6C && buf[i+1] == 0x65 && buf[i+2] == 0x70 && buf[i+3] == 0x00) {
                                var hex = new StringBuilder();
                                for (int k = 0; k < 0x40; k++) hex.Append(buf[i+k].ToString("x2"));
                                outLines.Add((baseAddr + off + i).ToString("x8") + " " + hex);
                                hits++;
                                if (hits > 4000) return outLines;
                            }
                        }
                    }
                }
                if (size <= 0) break;
                addr = (IntPtr)(baseAddr + size);
            }
        } finally {
            CloseHandle(h);
        }
        return outLines;
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp

$pid2 = [Rt]::FindByTitle('DaojianServer')
if ($pid2 -eq 0) { $pid2 = [Rt]::FindByTitle('ComeOn') }
if ($pid2 -eq 0) {
    Write-Host "!! could not find a window titled 'DaojianServer' / 'ComeOn'." -ForegroundColor Red
    exit 1
}
Write-Host "game pid: $pid2"

$err = $null
$hits = [Rt]::Scan($pid2, [ref]$err)
if ($err) {
    Write-Host "!! $err" -ForegroundColor Red
    Write-Host "   (run this script in a normal shell; if the game is elevated, elevate this too)"
    exit 1
}

$out = Join-Path (Get-Location) 'runtime_lep.txt'
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# live lep headers, pid $pid2, $(Get-Date -Format o)")
$lines.Add("# addr     header[0..0x3f] in hex")
$lines.AddRange([string[]]$hits)
Set-Content -LiteralPath $out -Value $lines -Encoding ascii

Write-Host "found $($hits.Count) 'lep' occurrences -> $out"


