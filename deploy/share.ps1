# Puts the app on a temporary public URL so teammates can try it without a deploy.
#
# This is for review, not for hosting. A Cloudflare quick tunnel needs no account
# and no DNS, and in exchange the hostname is random and changes every time this
# script runs, so the link has to be re-sent after each restart. Both processes
# die with this window: closing it takes the URL down, which is the behaviour you
# want from something handed to a group chat.
#
# The server binds loopback only. The tunnel is the sole way in, so there is no
# moment where the machine is listening on the network without it.
#
# For anything that should outlive an afternoon, use README.md in this folder
# instead: a real subdomain behind Caddy on the Hetzner box.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$port = if ($env:RESPITE_PORT) { $env:RESPITE_PORT } else { '8020' }

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "No virtualenv at $python. Run the setup in the top-level README first." }

$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
if (-not (Test-Path $cloudflared)) {
    $found = Get-Command cloudflared -ErrorAction SilentlyContinue
    if (-not $found) { throw 'cloudflared not found. Install it with: winget install Cloudflare.cloudflared' }
    $cloudflared = $found.Source
}

# An OpenAI key is optional. Without one the map, the charts and every
# measurement still work; only the agent answers return 503, and saying so up
# front beats a teammate reporting the page as broken.
if (-not (Test-Path (Join-Path $root '.env'))) {
    Write-Host 'No .env found. The page will work except for agent answers.' -ForegroundColor Yellow
}

# A previous run may still hold the port. Reusing it would mean tunnelling to
# stale code, which reads as a caching bug and wastes an hour.
$held = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($held) {
    Write-Host "Port $port is already serving (PID $($held.OwningProcess))." -ForegroundColor Yellow
    $reply = Read-Host 'Stop it and start fresh? [y/N]'
    if ($reply -eq 'y') {
        Stop-Process -Id $held.OwningProcess -Force
        Start-Sleep -Seconds 2
    } else {
        throw 'Left the existing server alone. Nothing started.'
    }
}

Write-Host 'Starting the server on loopback...' -ForegroundColor Cyan
$env:RESPITE_HOST = '127.0.0.1'
$env:RESPITE_PORT = $port
$server = Start-Process -FilePath $python -ArgumentList '-m', 'api.main' `
    -WorkingDirectory $root -PassThru -WindowStyle Hidden

# Poll rather than sleep a fixed interval: loading the tract layer takes a
# variable moment, and tunnelling to a server that is not up yet shows a 502.
$up = $false
foreach ($i in 1..30) {
    Start-Sleep -Seconds 1
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 3
        if ($h.status -eq 'ok') { $up = $true; break }
    } catch { }
}
if (-not $up) {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    throw "Server did not come up on port $port. Run '.venv\Scripts\python.exe -m api.main' by hand to see why."
}
Write-Host "  serving $($h.tracts) tracts. Agent key configured: $($h.llm_key_configured)." -ForegroundColor Green
Write-Host "  agent questions capped at $($h.agent_calls_limit) for this process, $($h.per_caller_hourly_limit) per person per hour." -ForegroundColor DarkGray

Write-Host 'Opening the tunnel...' -ForegroundColor Cyan
$log = Join-Path $env:TEMP 'respite-tunnel.log'
if (Test-Path $log) { Remove-Item $log -Force }
$tunnel = Start-Process -FilePath $cloudflared `
    -ArgumentList 'tunnel', '--no-autoupdate', '--url', "http://127.0.0.1:$port" `
    -PassThru -WindowStyle Hidden -RedirectStandardError $log

$url = $null
foreach ($i in 1..40) {
    Start-Sleep -Seconds 1
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue
        if ($m) { $url = $m.Matches[0].Value; break }
    }
}
if (-not $url) {
    Stop-Process -Id $tunnel.Id, $server.Id -Force -ErrorAction SilentlyContinue
    throw "The tunnel never reported a hostname. See $log."
}

# cloudflared prints the hostname as soon as the tunnel registers, which is
# before the name resolves. A quick tunnel has also been seen to register, lose
# its control stream, and leave a hostname that never resolves at all. Handing
# that address to the team wastes their afternoon and looks like a broken app, so
# it is checked from the public side before being printed.
Write-Host 'Waiting for the address to answer...' -ForegroundColor Cyan
$live = $false
foreach ($i in 1..24) {
    try {
        $probe = Invoke-RestMethod "$url/health" -TimeoutSec 6
        if ($probe.status -eq 'ok') { $live = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}

Write-Host ''
Write-Host "  $url" -ForegroundColor Green
Write-Host ''
if ($live) {
    Write-Host '  Answering from the public side. Send it to the team.' -ForegroundColor DarkGray
} else {
    Write-Host '  The tunnel registered but the address is not answering yet.' -ForegroundColor Yellow
    Write-Host '  Give it a few minutes. If it stays dead, Ctrl+C and run this again:' -ForegroundColor Yellow
    Write-Host '  a fresh hostname is usually quicker than waiting for a stuck one.' -ForegroundColor Yellow
}
Write-Host '  It stops working when this window closes, and a new run gets a' -ForegroundColor DarkGray
Write-Host '  different address.' -ForegroundColor DarkGray
Write-Host ''
Set-Clipboard -Value $url -ErrorAction SilentlyContinue
Write-Host 'Copied to the clipboard. Ctrl+C here to take it down.' -ForegroundColor DarkGray

try {
    Wait-Process -Id $tunnel.Id
} finally {
    Write-Host 'Shutting down.' -ForegroundColor Cyan
    Stop-Process -Id $tunnel.Id, $server.Id -Force -ErrorAction SilentlyContinue
}
