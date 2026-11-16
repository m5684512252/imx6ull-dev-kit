# 板子链路检测：不关心是网线 / USB转RJ45 / 光纤收发器，只看"电口这一层通没通"
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File .\check_board_link.ps1
#      加上 -BoardMac 'AA-6C-F9-2E-48-3D' 可精确认板子（默认已内置）
param(
    [string]$BoardMac = 'AA-6C-F9-2E-48-3D',
    [int[]]$Ports = @(22, 23, 111, 80)
)
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Host "`n===== 1. 物理网卡（Link Up 的才可能通板子）=====" -ForegroundColor Cyan
$phys = Get-NetAdapter -Physical | Sort-Object Status, Name
$phys | Select-Object Name, InterfaceDescription, Status, LinkSpeed, MacAddress | Format-Table -AutoSize -Wrap | Out-String | Write-Host

$up = $phys | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -notmatch 'Wi-?Fi|Wireless|802\.11' }
if (-not $up) { Write-Host "没有 Up 状态的有线网卡 —— 先把板子那条链路接上（网线/USB转RJ45/光纤收发器都行）。" -ForegroundColor Yellow; exit 0 }

foreach ($a in $up) {
    Write-Host "`n===== 2. $($a.Name) 上的地址和邻居 =====" -ForegroundColor Cyan
    Write-Host "链路: $($a.LinkSpeed)   MTU: $($a.MtuSize)"
    Get-NetIPAddress -InterfaceIndex $a.ifIndex -ErrorAction SilentlyContinue |
        Select-Object IPAddress, PrefixLength, AddressFamily, PrefixOrigin |
        Format-Table -AutoSize | Out-String | Write-Host

    $nb = Get-NetNeighbor -InterfaceIndex $a.ifIndex -ErrorAction SilentlyContinue |
          Where-Object { $_.LinkLayerAddress -and $_.LinkLayerAddress -ne 'FF-FF-FF-FF-FF-FF' -and $_.IPAddress -notmatch '^(224|239)\.' }
    if ($nb) { $nb | Select-Object IPAddress, LinkLayerAddress, State | Format-Table -AutoSize | Out-String | Write-Host }
    else { Write-Host "  邻居表为空（对端还没发过任何包）" -ForegroundColor DarkGray }

    # 6. 顺手把所有 IPv6 链路本地邻居都探一遍
    Write-Host "`n===== 3. IPv6 链路本地探测 =====" -ForegroundColor Cyan
    $ll = Get-NetNeighbor -InterfaceIndex $a.ifIndex -AddressFamily IPv6 -ErrorAction SilentlyContinue |
          Where-Object { $_.IPAddress -like 'fe80::*' -and $_.LinkLayerAddress }
    if (-not $ll) {
        Write-Host "  没发现链路本地邻居。发一次全节点组播试试..." -ForegroundColor DarkGray
        ping -6 -n 2 -w 800 "ff02::1%$($a.ifIndex)" 2>&1 | Out-Null
        $ll = Get-NetNeighbor -InterfaceIndex $a.ifIndex -AddressFamily IPv6 -ErrorAction SilentlyContinue |
              Where-Object { $_.IPAddress -like 'fe80::*' -and $_.LinkLayerAddress }
    }
    foreach ($n in $ll) {
        $target = "$($n.IPAddress)%$($a.ifIndex)"
        $hit = ($n.LinkLayerAddress.ToUpper() -eq $BoardMac)
        $tag = if ($hit) { '  <== 板子(MAC命中)' } else { '' }
        $col = if ($hit) { 'Green' } else { 'Yellow' }
        Write-Host ("  {0,-42} {1}{2}" -f $target, $n.LinkLayerAddress, $tag) -ForegroundColor $col
        $r = ping -6 -n 2 -w 600 $target 2>&1 | Select-String 'Reply from'
        if ($r) { Write-Host "      ping6 OK" -ForegroundColor Green } else { Write-Host "      ping6 无应答" -ForegroundColor DarkGray }
        foreach ($p in $Ports) {
            $c = New-Object System.Net.Sockets.TcpClient
            $addr = [System.Net.IPAddress]::Parse($target)
            $iar = $c.BeginConnect($addr, $p, $null, $null)
            if ($iar.AsyncWaitHandle.WaitOne(900, $false) -and $c.Connected) {
                try { $c.EndConnect($iar) } catch {}
                Write-Host "      tcp/$p OPEN" -ForegroundColor Green
            }
            $c.Close()
        }
    }
}

Write-Host "`n提示：光纤/网线只是物理层，PC 里看到的永远是"以太网适配器"，不会出现"开发板"这种设备。" -ForegroundColor Cyan
Write-Host "      判定标准就是：Link Up + 邻居 MAC + ping 通 + 22 端口 OPEN。" -ForegroundColor Cyan
