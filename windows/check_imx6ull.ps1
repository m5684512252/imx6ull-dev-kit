# 正点原子 I.MX6ULL 开发板连接检测（串口 + USB + 以太网）
# 用法： powershell -NoProfile -ExecutionPolicy Bypass -File .\check_imx6ull.ps1
# 持续监视： .\check_imx6ull.ps1 -Watch 60
param(
    [int]$Watch = 0,          # 监视秒数，0 = 只查一次
    [int]$IntervalMs = 1000
)

[Console]::OutputEncoding = [Text.Encoding]::UTF8

$SerialVids = @{
    'VID_1A86' = 'WCH CH340/CH341 (正点原子板载USB转串口常用)'
    'VID_10C4' = 'Silicon Labs CP2102/CP2104'
    'VID_0403' = 'FTDI FT232'
    'VID_067B' = 'Prolific PL2303'
    'VID_04D8' = 'Microchip CDC'
}

function Get-SerialPorts {
    Get-CimInstance Win32_PnPEntity |
        Where-Object { $_.Name -match '\(COM\d+\)' -and $_.InstanceId -notmatch '^BTHENUM' } |
        ForEach-Object {
            $com = [regex]::Match($_.Name, 'COM\d+').Value
            [pscustomobject]@{
                COM  = $com
                Name = $_.Name -replace '\s*\(COM\d+\)', ''
                Id   = $_.InstanceId
            }
        }
}

function Get-UsbSerialChips {
    Get-PnpDevice -PresentOnly |
        Where-Object {
            $id = $_.InstanceId
            ($SerialVids.Keys | Where-Object { $id -like "*$_*" }) -or
            $_.FriendlyName -match 'CH34|CP210|FT232|PL2303|USB-SERIAL|USB Serial|Serial Port'
        } |
        Select-Object Status, Class, FriendlyName, InstanceId, @{n='Chip';e={
            $id = $_.InstanceId
            $k = $SerialVids.Keys | Where-Object { $id -like "*$_*" } | Select-Object -First 1
            if ($k) { $SerialVids[$k] } else { 'USB 串口类设备' }
        }}
}

function Show-Report {
    Write-Host "`n===== 1. 真实串口 (非蓝牙) =====" -ForegroundColor Cyan
    $ports = Get-SerialPorts
    if ($ports) { $ports | Format-Table -AutoSize | Out-String | Write-Host }
    else { Write-Host "  未发现任何真实串口 (COMx 只有蓝牙虚拟口)" -ForegroundColor Yellow }

    Write-Host "===== 2. USB 串口芯片扫描 =====" -ForegroundColor Cyan
    $chips = Get-UsbSerialChips
    if ($chips) { $chips | Format-List | Out-String | Write-Host }
    else { Write-Host "  未发现 CH340 / CP210x / FTDI / PL2303 等 USB 转串口芯片" -ForegroundColor Yellow }

    Write-Host "===== 3. 异常(未装驱动)设备 =====" -ForegroundColor Cyan
    $bad = Get-PnpDevice -PresentOnly | Where-Object { $_.Status -ne 'OK' }
    if ($bad) { $bad | Select-Object Status, Class, FriendlyName, InstanceId | Format-List | Out-String | Write-Host }
    else { Write-Host "  无 (说明设备连枚举都没发生，不是驱动问题)" -ForegroundColor Yellow }

    Write-Host "===== 4. 可疑网卡/链路(板子网口直连?) =====" -ForegroundColor Cyan
    Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -match 'USB|Ethernet|以太' } |
        Select-Object Name, InterfaceDescription, LinkSpeed, MacAddress | Format-Table -AutoSize | Out-String | Write-Host
}

if ($Watch -le 0) { Show-Report; exit 0 }

Write-Host "监视 $Watch 秒：现在插上板子的 USB_UART 口（或给板子上电）..." -ForegroundColor Green
$before = (Get-SerialPorts | ForEach-Object { $_.COM }) -join ','
$beforeUsb = (Get-UsbSerialChips | ForEach-Object { $_.InstanceId }) -join ','
$deadline = (Get-Date).AddSeconds($Watch)
while ((Get-Date) -lt $deadline) {
    $now = (Get-SerialPorts | ForEach-Object { $_.COM }) -join ','
    $nowUsb = (Get-UsbSerialChips | ForEach-Object { $_.InstanceId }) -join ','
    if ($now -ne $before -or $nowUsb -ne $beforeUsb) {
        Write-Host "`n[变化检测] $(Get-Date -Format 'HH:mm:ss') 串口: [$before] -> [$now]" -ForegroundColor Green
        Show-Report
        exit 0
    }
    Start-Sleep -Milliseconds $IntervalMs
}
Write-Host "`n$Watch 秒内没有任何新串口/USB 串口芯片出现。" -ForegroundColor Yellow
