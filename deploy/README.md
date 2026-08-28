# Deploying Respite to the Hetzner box

Target: `https://respite.samtechpk.com`, fronted by the Caddy instance already
running there, with uvicorn bound to loopback.

**Everything here is additive.** A new subdomain, a new port, a new Caddy site
block, a new scheduled task. Nothing modifies an existing site, binding, or
certificate. If any step looks like it would touch a live service, stop.

Budget about 25 minutes, most of it waiting for DNS.

---

## Sharing it before any of this

To let a teammate look at the page without deploying anything:

```powershell
.\deploy\share.ps1
```

That starts the server on loopback, opens a Cloudflare quick tunnel to it, waits
until the address answers from the public side, and prints it. No account, no
DNS, no certificate.

The address is random and a new run gets a different one, so it cannot be
bookmarked, and it stops working when the window closes. Quick tunnels have also
been seen to register and then never resolve, which is why the script probes
before handing you the link.

Use the rest of this document for anything that needs to stay up.

---

## What the deployment actually needs

| Needs | Why |
|---|---|
| Python 3.11+ | the app |
| Outbound HTTPS from the box | nothing at request time; only `pip install` and `git` |
| Outbound HTTPS from the *visitor's* browser | basemap tiles come from `basemaps.cartocdn.com` |
| `OPENAI_API_KEY` | only `/api/agent`, `/api/briefing`, `/api/explain` |
| Ports 80 and 443 reaching the box | Caddy's certificate, already true for the existing sites |

`FORTYGUARD_API_KEY` is **not** needed to serve the site. The tract layer is
committed and the request path never calls the vendor, so no page load can spend
credits or break when the Temperature API is down. The key is only for offline
layer rebuilds.

---

## 1. DNS

Add one record at whoever hosts `samtechpk.com` DNS:

| Type | Name | Value |
|---|---|---|
| A | `respite` | *the box's public IPv4* |

Confirm it resolves **before** touching Caddy. The certificate request fails if
the name does not yet point at the machine, and a failed attempt is rate limited:

```powershell
Resolve-DnsName respite.samtechpk.com -Type A
```

Wait until that returns the box's address. Do not continue on faith.

## 2. Get the code onto the box

```powershell
mkdir C:\apps -Force; cd C:\apps
git clone https://github.com/samranahmad09/hackathon-fortyguard.git respite
cd C:\apps\respite
git config core.hooksPath .githooks
```

That last line matters: the hook that blocks a staged `.env` or an API key is
repo-local config and does not survive a clone.

## 3. Python environment

```powershell
cd C:\apps\respite
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

## 4. Secrets

```powershell
cd C:\apps\respite
Copy-Item .env.example .env
notepad .env
```

Put the OpenAI key in and save. `.env` is gitignored and must stay that way. The
app reads keys from the environment and never returns their values; `/health`
reports only whether each one is *present*.

Real environment variables take precedence over the file, so if you would rather
set them at machine scope the file is unnecessary.

## 5. Check it runs before wiring anything to it

```powershell
cd C:\apps\respite
.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8020
```

In a second PowerShell window on the box:

```powershell
Invoke-RestMethod http://127.0.0.1:8020/health | ConvertTo-Json
```

Expect `status: ok`, `layer_present: true`, `tracts: 134`,
`llm_key_configured: true`. If `llm_key_configured` is false the page still
works apart from agent answers, which is worth knowing now rather than after
Caddy is pointed at it.

Then stop it with Ctrl+C.

## 6. Run it as a service

A scheduled task needs no extra software. Note `-MultipleInstances IgnoreNew`,
which stops a second copy fighting for port 8020 after a restart:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\apps\respite\.venv\Scripts\python.exe" `
           -Argument "-m uvicorn api.main:app --host 127.0.0.1 --port 8020" `
           -WorkingDirectory "C:\apps\respite"
$trigger = New-ScheduledTaskTrigger -AtStartup
$set     = New-ScheduledTaskSettingsSet -RestartCount 3 `
           -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew `
           -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
Register-ScheduledTask -TaskName "respite-api" -Action $action -Trigger $trigger `
  -Settings $set -RunLevel Highest -User "SYSTEM"
Start-ScheduledTask -TaskName "respite-api"
```

`-ExecutionTimeLimit 0` means no limit. Without it Windows kills the task after
its default limit, which for a long-running server shows up as the site dying
after a few days for no visible reason.

Confirm it took:

```powershell
Get-ScheduledTask respite-api | Select-Object State
Invoke-RestMethod http://127.0.0.1:8020/health | ConvertTo-Json
```

If NSSM is already on the box, prefer it. It gives real service semantics and
log redirection.

## 7. Caddy

Find the live Caddyfile and **back it up first**:

```powershell
Copy-Item C:\caddy\Caddyfile C:\caddy\Caddyfile.bak-$(Get-Date -Format yyyyMMdd-HHmm)
```

Append the contents of [`Caddyfile.snippet`](Caddyfile.snippet):

```powershell
Get-Content C:\apps\respite\deploy\Caddyfile.snippet | Add-Content C:\caddy\Caddyfile
```

Validate **before** reloading, so a syntax error cannot take the live sites down:

```powershell
caddy validate --config C:\caddy\Caddyfile
```

Only if that passes:

```powershell
caddy reload --config C:\caddy\Caddyfile
```

`reload` is graceful and the existing sites keep serving. If validate fails,
restore the backup and change nothing else.

Adjust the log path in the snippet if the Caddy log directory differs on the box.

## 8. Verify from outside

From a machine that is **not** the box:

```powershell
Invoke-RestMethod https://respite.samtechpk.com/health | ConvertTo-Json
```

Then open `https://respite.samtechpk.com` in a browser and check:

- the agent console is the first thing on screen, and the briefing arrives on its own
- asking a question returns an answer with a list of sources under it
- the map draws tracts **over a street basemap**, with place names on top
- the two charts render, and the scatter shows the dashed ceiling row
- the browser console is clean
- the existing sites on the box still load

The basemap is the one part that depends on the visitor's network reaching
`basemaps.cartocdn.com`. If tiles are blocked the tracts still draw, just with
nothing underneath.

---

## Updating a deployed copy

```powershell
cd C:\apps\respite
git pull
.venv\Scripts\python -m pip install -r requirements.txt
Restart-ScheduledTask -TaskName "respite-api"
```

The tract layer is cached in memory on first request, so a restart is required
for any data change to appear. The page itself is served `no-store`, so a
visitor's reload picks up new markup without a cache-buster.

## Spend, and why the site cannot brick itself

`api/limits.py` bounds what the agent endpoints can cost, checked before the
model is reached so a blocked request spends nothing:

| Env var | Default | Meaning |
|---|---|---|
| `RESPITE_LIMIT_PER_IP` | 25 | questions per caller per hour |
| `RESPITE_LIMIT_TOTAL` | 300 | questions from everyone, per window |
| `RESPITE_LIMIT_TOTAL_WINDOW_SECONDS` | 86400 | that window, 24 hours |

Both are **rolling** windows, so a busy day cannot leave the agent permanently
refusing. `/health` reports current usage. Raise the total for judging week if
you would rather not risk a limit during a demo:

```powershell
[Environment]::SetEnvironmentVariable('RESPITE_LIMIT_TOTAL','1200','Machine')
Restart-ScheduledTask -TaskName "respite-api"
```

Running out is not a broken page. The map, the charts and every measurement keep
working, and the agent says what happened and when it recovers.

## Rebuilding the data layer

```powershell
cd C:\apps\respite
.venv\Scripts\python scripts\build_layer.py
Restart-ScheduledTask -TaskName "respite-api"
```

Rebuilds cost FortyGuard credits and need `FORTYGUARD_API_KEY`, so do them
deliberately and never on a schedule. Raw responses cache under `data/raw/`
(gitignored) and are reused, so re-running without changing parameters is free.

## If something breaks

| Symptom | Likely cause |
|---|---|
| Caddy cannot get a certificate | DNS not resolving yet, or 80/443 not reaching the box |
| `caddy validate` fails | restore the backup from step 7 and re-check the appended block |
| 502 from Caddy | uvicorn not running. `Get-ScheduledTask respite-api`, then check Event Viewer |
| Site dies after a few days | `-ExecutionTimeLimit` was not set to 0 on the task |
| `layer_present: false` | `data/processed/tracts_recovery.geojson` missing; run `build_layer.py` |
| Page loads, no tracts | browser console; `/api/tracts` should return 134 features |
| Map has no streets under the tracts | the visitor's network is blocking `basemaps.cartocdn.com` |
| Agent returns 503 | no `OPENAI_API_KEY` in the environment the task runs under |
| Agent returns 429 | the spend budget. See the table above |
| Stale numbers after a pull | the in-memory layer cache. Restart the task |
