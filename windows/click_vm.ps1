param([double]$fx = 0.496, [double]$fy = 0.066)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$p = Get-Process vmware -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 1
if (-not $p) { Write-Host "no vmware window"; exit 1 }
[W32]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
[W32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 700
$r = New-Object W32+RECT
[W32]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
$x = [int]($r.Left + $w * $fx); $y = [int]($r.Top + $h * $fy)
Write-Host "window ${w}x${h} at ($($r.Left),$($r.Top)) -> click ($x,$y)"
[W32]::SetCursorPos($x, $y) | Out-Null
Start-Sleep -Milliseconds 250
[W32]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)   # left down
Start-Sleep -Milliseconds 80
[W32]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)   # left up
Write-Host "clicked"
