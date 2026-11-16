# 对 IPv6 链路本地地址做端口探测（无需管理员）
param(
    [string]$Target = 'fe80::a86c:f9ff:fe2e:483d%58',
    [int[]]$Ports = @(22, 23, 80, 443, 8080, 502, 21, 111, 2049),
    [int]$TimeoutMs = 1200
)
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$addr = [System.Net.IPAddress]::Parse($Target)
Write-Host "目标: $Target  (ScopeId=$($addr.ScopeId))" -ForegroundColor Cyan

foreach ($p in $Ports) {
    $client = New-Object System.Net.Sockets.TcpClient
    $ep = New-Object System.Net.IPEndPoint($addr, $p)
    $iar = $client.BeginConnect($ep, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
    $state = 'filtered/closed'
    $banner = ''
    if ($ok -and $client.Connected) {
        try { $client.EndConnect($iar) } catch {}
        $state = 'OPEN'
        # 尝试读 banner（ssh/telnet 会主动打招呼）
        try {
            $client.ReceiveTimeout = 800
            $st = $client.GetStream()
            $buf = New-Object byte[] 128
            if ($st.CanRead -and $st.DataAvailable -eq $false) { Start-Sleep -Milliseconds 300 }
            $n = $st.Read($buf, 0, $buf.Length)
            if ($n -gt 0) { $banner = ([Text.Encoding]::ASCII.GetString($buf, 0, $n)) -replace '[^\x20-\x7e]', '.' }
        } catch {}
    }
    $client.Close()
    if ($state -eq 'OPEN') {
        Write-Host ("  {0,-6} {1,-12} {2}" -f $p, $state, $banner) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-6} {1}" -f $p, $state) -ForegroundColor DarkGray
    }
}
