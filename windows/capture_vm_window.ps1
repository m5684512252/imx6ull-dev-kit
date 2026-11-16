Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Cap {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int cmd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hwnd);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

$out = $args[0]
if (-not $out) { $out = "C:\Users\38368\OneDrive\文档\deepseek-harness\default-workspace\linux\vm_window.png" }

# 找 VMware 主窗口（MainWindowTitle 非空，且进程是 vmware 或 vmware-vmx）
$procs = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -match 'vmware' }
foreach ($p in $procs) {
    Write-Host ("[{0}] pid={1} hwnd={2} title='{3}'" -f $p.ProcessName, $p.Id, $p.MainWindowHandle, $p.MainWindowTitle)
}

$target = $procs | Where-Object { $_.MainWindowTitle -match 'VMware|Ubuntu' } | Select-Object -First 1
if (-not $target) { Write-Host "没找到 VMware 窗口"; exit 1 }

[Win32Cap]::ShowWindow($target.MainWindowHandle, 9) | Out-Null   # SW_RESTORE
Start-Sleep -Milliseconds 400

$r = New-Object Win32Cap+RECT
[Win32Cap]::GetWindowRect($target.MainWindowHandle, [ref]$r) | Out-Null
$w = $r.Right - $r.Left
$h = $r.Bottom - $r.Top
Write-Host "窗口尺寸: ${w}x${h} at ($($r.Left),$($r.Top))"

$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
$ok = [Win32Cap]::PrintWindow($target.MainWindowHandle, $hdc, 2)   # PW_RENDERFULLCONTENT
$g.ReleaseHdc($hdc)
$g.Dispose()
if (-not $ok) { Write-Host "PrintWindow 返回 false（可能被遮挡），改用屏幕抓取" }

$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "已保存: $out"
