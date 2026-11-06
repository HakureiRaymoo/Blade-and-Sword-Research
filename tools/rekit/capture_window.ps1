# capture_window.ps1 -- grab a window's pixels with plain GDI.
#
# The agent sandbox runs at Low integrity and cannot OpenProcess, but window
# capture only needs the HWND, which EnumWindows provides. PrintWindow returns
# black for this DirectDraw game; BitBlt against GetWindowDC works.
#
#   pwsh -ExecutionPolicy Bypass -File capture_window.ps1 [-Title DaojianServer] [-Out shot.bmp] [-Count 1] [-IntervalMs 200]

param(
    [string]$Title = 'DaojianServer',
    [string]$Out = 'shot.bmp',
    [int]$Count = 1,
    [int]$IntervalMs = 200
)

$ErrorActionPreference = 'Stop'

$src = @'
using System;
using System.Text;
using System.IO;
using System.Runtime.InteropServices;
public class WinCap {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr GetWindowDC(IntPtr h);
  [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr h, IntPtr dc);
  [DllImport("gdi32.dll")] public static extern IntPtr CreateCompatibleDC(IntPtr h);
  [DllImport("gdi32.dll")] public static extern IntPtr CreateDIBSection(IntPtr h, ref BIH b, uint usage, out IntPtr bits, IntPtr sec, uint off);
  [DllImport("gdi32.dll")] public static extern IntPtr SelectObject(IntPtr dc, IntPtr obj);
  [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr o);
  [DllImport("gdi32.dll")] public static extern bool DeleteDC(IntPtr dc);
  [DllImport("gdi32.dll")] public static extern bool BitBlt(IntPtr d,int x,int y,int w,int h,IntPtr s,int sx,int sy,int rop);

  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct BIH {
    public uint biSize; public int biWidth; public int biHeight; public ushort biPlanes;
    public ushort biBitCount; public uint biCompression; public uint biSizeImage;
    public int biXPelsPerMeter; public int biYPelsPerMeter; public uint biClrUsed; public uint biClrImportant;
  }

  public static IntPtr Find(string title) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h,l) => {
      var sb = new StringBuilder(512);
      GetWindowTextW(h, sb, 512);
      if (sb.ToString().IndexOf(title, StringComparison.OrdinalIgnoreCase) >= 0) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }

  public static string Grab(IntPtr h, string path) {
    RECT r; GetWindowRect(h, out r);
    int w = r.Right - r.Left, ht = r.Bottom - r.Top;
    if (w <= 0 || ht <= 0) return "bad rect " + w + "x" + ht;
    var bih = new BIH();
    bih.biSize = 40; bih.biWidth = w; bih.biHeight = -ht;   // top-down
    bih.biPlanes = 1; bih.biBitCount = 32; bih.biCompression = 0;
    IntPtr bits;
    IntPtr dc = CreateCompatibleDC(IntPtr.Zero);
    IntPtr dib = CreateDIBSection(dc, ref bih, 0, out bits, IntPtr.Zero, 0);
    IntPtr old = SelectObject(dc, dib);
    IntPtr src = GetWindowDC(h);
    bool ok = BitBlt(dc, 0, 0, w, ht, src, 0, 0, 0x00CC0020);
    ReleaseDC(h, src);
    byte[] buf = new byte[w * ht * 4];
    Marshal.Copy(bits, buf, 0, buf.Length);
    SelectObject(dc, old); DeleteObject(dib); DeleteDC(dc);

    using (var fs = new FileStream(path, FileMode.Create))
    using (var bw = new BinaryWriter(fs)) {
      int imgSize = w * ht * 4;
      bw.Write((ushort)0x4D42); bw.Write(14 + 40 + imgSize); bw.Write((uint)0); bw.Write(14 + 40);
      bw.Write((uint)40); bw.Write(w); bw.Write(-ht);
      bw.Write((ushort)1); bw.Write((ushort)32); bw.Write((uint)0); bw.Write(imgSize);
      bw.Write(2835); bw.Write(2835); bw.Write((uint)0); bw.Write((uint)0);
      bw.Write(buf);
    }
    return (ok ? "ok" : "bitblt-failed") + " " + w + "x" + ht;
  }
}
'@

Add-Type -TypeDefinition $src -Language CSharp

$hwnd = [WinCap]::Find($Title)
if ($hwnd -eq [IntPtr]::Zero) {
    Write-Host "!! no window matching '$Title'" -ForegroundColor Red
    exit 1
}
Write-Host "hwnd: $hwnd"

for ($i = 0; $i -lt $Count; $i++) {
    $path = if ($Count -eq 1) { $Out } else {
        [System.IO.Path]::Combine(
            [System.IO.Path]::GetDirectoryName((Resolve-Path -LiteralPath '.').Path),
            [System.IO.Path]::GetFileNameWithoutExtension($Out) + "_$i.bmp")
    }
    $res = [WinCap]::Grab($hwnd, $path)
    Write-Host "  $res -> $path"
    if ($i -lt $Count - 1) { Start-Sleep -Milliseconds $IntervalMs }
}
