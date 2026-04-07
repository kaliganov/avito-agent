# Запуск API на localhost и публичный HTTPS-туннель для вебхуков Avito.
# Требуется: cloudflared в PATH (см. ниже) или ngrok.
#
# Установка cloudflared (Windows):
#   winget install Cloudflare.cloudflared
# или: https://github.com/cloudflare/cloudflared/releases
#
# Запуск из корня проекта:
#   .\scripts\start_local_tunnel.ps1
#
# В консоли появится URL вида https://....trycloudflare.com — его укажите в Avito:
#   https://....trycloudflare.com/webhooks/avito
#
# Важно: URL меняется при каждом перезапуске (quick tunnel). Для постоянного адреса — ngrok paid или Cloudflare Named Tunnel.
#
# Если ошибки QUIC или TLS на порту 7844 (i/o timeout) — см. scripts\test_tunnel_connectivity.ps1
# Часто режут исходящий порт 7844 до Cloudflare; тогда используйте: -Backend ngrok

param(
    [ValidateSet("cloudflared", "ngrok")]
    [string] $Backend = "cloudflared",
    [int] $Port = 8000,
    [ValidateSet("http2", "quic")]
    [string] $Protocol = "http2"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Не найден .venv. Создайте: python -m venv .venv && .\.venv\Scripts\python -m pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port")
$proc = Start-Process -FilePath $python -ArgumentList $uvicornArgs -WorkingDirectory $Root -PassThru -WindowStyle Minimized
Write-Host "Uvicorn PID $($proc.Id) на http://127.0.0.1:$Port/health" -ForegroundColor Green
Start-Sleep -Seconds 2

try {
    if ($Backend -eq "cloudflared") {
        $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
        if (-not $cf) {
            Write-Host "cloudflared не найден в PATH. Установите: winget install Cloudflare.cloudflared" -ForegroundColor Red
            exit 1
        }
        $cfArgs = @("tunnel", "--url", "http://127.0.0.1:$Port", "--protocol", $Protocol)
        Write-Host "cloudflared: $($cfArgs -join ' ')" -ForegroundColor DarkGray
        & cloudflared @cfArgs
    }
    else {
        $ng = Get-Command ngrok -ErrorAction SilentlyContinue
        if (-not $ng) {
            Write-Host "ngrok не найден в PATH. Установите: https://ngrok.com/download" -ForegroundColor Red
            exit 1
        }
        & ngrok http $Port
    }
}
finally {
    if (-not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "`nUvicorn остановлен." -ForegroundColor Gray
    }
}
