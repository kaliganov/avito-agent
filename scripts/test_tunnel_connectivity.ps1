# Быстрая проверка доступности портов до Cloudflare Edge (cloudflared).
# Запуск: .\scripts\test_tunnel_connectivity.ps1

Write-Host "Проверка TCP до edge (пример IP из лога Cloudflare)..." -ForegroundColor Cyan
$hosts = @(
    @{ Name = "Cloudflare edge (пример)"; IP = "198.41.192.57"; Port = 7844 },
    @{ Name = "HTTPS (интернет)"; IP = "1.1.1.1"; Port = 443 }
)
foreach ($h in $hosts) {
    $r = Test-NetConnection -ComputerName $h.IP -Port $h.Port -WarningAction SilentlyContinue
    $ok = $r.TcpTestSucceeded
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("  {0} {1}:{2} -> {3}" -f $h.Name, $h.IP, $h.Port, $(if ($ok) { "OK" } else { "НЕ ДОСТУПНО" })) -ForegroundColor $color
}
Write-Host ""
Write-Host "Если 7844 недоступен, cloudflared quick tunnel часто не поднимется." -ForegroundColor Yellow
Write-Host "Варианты: разрешить исходящий TCP/UDP 7844 в фаерволе/роутере, другой интернет (раздача с телефона), VPN, или ngrok." -ForegroundColor Gray
