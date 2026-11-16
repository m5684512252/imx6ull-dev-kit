# 找出板子的 IPv4 地址（需要管理员权限）
# 用法（管理员 PowerShell）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\find_board_ipv4.ps1
# 原理：把 USB 网卡临时放进板子可能所在的网段 -> 并发 ping 扫整个 /24 -> 读 ARP 表比对 MAC
#       扫完自动把网卡恢复成原来的 DHCP 状态

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Alias      = '以太网 3'
$BoardMac   = 'AA-6C-F9-2E-48-3D'      # 已知板子 MAC（IPv6 LL 邻居表里拿到的）
$Subnets    = @('192.168.1','192.168.0','192.168.4','192.168.5','192.168.10',
                '192.168.100','192.168.137','10.0.0','10.10.10','172.16.0')
$HostIp     = 200                       # 本机在该网段用的地址：x.x.x.200
$TimeoutMs  = 250

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "需要管理员权限，请右键 PowerShell -> 以管理员身份运行，再执行本脚本。" -ForegroundColor Red
    exit 1
}

$adapter = Get-NetAdapter -Name $Alias -ErrorAction Stop
Write-Host "网卡: $($adapter.Name)  $($adapter.InterfaceDescription)  $($adapter.Status) $($adapter.LinkSpeed)" -ForegroundColor Cyan
Write-Host "目标 MAC: $BoardMac`n"

function Scan-Subnet {
    param([string]$Net, [string]$Alias, [int]$HostIp, [int]$TimeoutMs)

    $addr = "$Net.$HostIp"
    netsh interface ipv4 add address name="$Alias" address=$addr mask=255.255.255.0 2>&1 | Out-Null
    Start-Sleep -Milliseconds 700
    arp -d * 2>&1 | Out-Null

    $pings = @()
    $ips = 1..254 | ForEach-Object { "$Net.$_" } | Where-Object { $_ -ne $addr }
    foreach ($ip in $ips) {
        $p = New-Object System.Net.NetworkInformation.Ping
        $pings += [pscustomobject]@{ IP = $ip; Task = $p.SendPingAsync($ip, $TimeoutMs) }
    }
    try { [Threading.Tasks.Task]::WaitAll(($pings.Task), 6000) | Out-Null } catch {}

    $live = @()
    foreach ($item in $pings) {
        if ($item.Task.IsCompleted -and -not $item.Task.IsFaulted -and $item.Task.Result.Status -eq 'Success') {
            $live += $item.IP
        }
    }
    Start-Sleep -Milliseconds 300

    $arpLines = (arp -a) -join "`n"
    $found = @()
    foreach ($ip in $live) {
        $m = [regex]::Match($arpLines, [regex]::Escape($ip) + '\s+([0-9a-fA-F-]{17})')
        if ($m.Success) { $found += [pscustomobject]@{ IP = $ip; MAC = $m.Groups[1].Value.ToUpper() } }
    }

    netsh interface ipv4 delete address name="$Alias" address=$addr 2>&1 | Out-Null
    return $found
}

$all = @()
try {
    foreach ($net in $Subnets) {
        Write-Host "扫描 $net.0/24 ..." -NoNewline
        $r = Scan-Subnet -Net $net -Alias $Alias -HostIp $HostIp -TimeoutMs $TimeoutMs
        if ($r.Count -eq 0) {
            Write-Host " 无应答" -ForegroundColor DarkGray
        } else {
            Write-Host ""
            foreach ($x in $r) {
                $tag = if ($x.MAC -eq $BoardMac) { '  <== 这就是板子！' } else { '' }
                $color = if ($x.MAC -eq $BoardMac) { 'Green' } else { 'Yellow' }
                Write-Host ("   {0,-15} {1}{2}" -f $x.IP, $x.MAC, $tag) -ForegroundColor $color
                $all += $x
            }
        }
    }
}
finally {
    # 恢复 DHCP（这块网卡原本就是 DHCP + APIPA）
    netsh interface ipv4 set address name="$Alias" source=dhcp 2>&1 | Out-Null
    netsh interface ipv4 set dnsservers name="$Alias" source=dhcp 2>&1 | Out-Null
    Start-Sleep -Milliseconds 500
    Write-Host "`n已恢复 $Alias 为 DHCP 自动获取。当前地址：" -ForegroundColor Cyan
    Get-NetIPAddress -InterfaceAlias $Alias -AddressFamily IPv4 | Select-Object IPAddress, PrefixOrigin | Format-Table -AutoSize | Out-String | Write-Host
}

$hit = $all | Where-Object { $_.MAC -eq $BoardMac }
if ($hit) {
    Write-Host "`n>>> 板子 IPv4 = $($hit.IP -join ', ')" -ForegroundColor Green
    Write-Host "    现在把网卡手动设成静态 $(([string]($hit[0].IP) -replace '\.\d+$','.200'))/24，就能 ssh / tftp / nfs 了。" -ForegroundColor Green
} else {
    Write-Host "`n上面这些网段都没找到板子（板子可能没配 IPv4，只跑 IPv6；用 IPv6 链路本地照样能连）。" -ForegroundColor Yellow
}
