# Deploying Respite to the Hetzner box

Target: `https://respite.samtechpk.com`, fronted by the Caddy instance already
running there, with uvicorn bound to loopback.

**Everything here is additive.** A new subdomain, a new port, a new Caddy site
block, a new scheduled task. Nothing modifies an existing site, binding, or
certificate. If any step looks like it would touch a live service, stop.

---

## Sharing it before any of this

To let a teammate look at the page without deploying anything:

```powershell
.\deploy\share.ps1
```

That starts the server on loopback, opens a Cloudflare quick tunnel to it, and
prints a `*.trycloudflare.com` address it also copies to the clipboard. No
account, no DNS, no certificate.

Two things to know before sending the link. The address is random and a new run
gets a different one, so it cannot be bookmarked. And it stops working when the
window closes, which is the right property for a URL that ends up pasted into a
group chat.

Anyone with the address can ask the agent questions, and every question spends
money on the OpenAI key. `api/limits.py` caps that: 25 questions per caller per
hour, 300 for the process, checked before the model is reached so a blocked
request costs nothing. `/health` reports the current count. Nothing on the page
can spend FortyGuard credits, because the request path reads the committed data
layer and never calls the vendor.

Use the rest of this document for anything that needs to stay up.

---

## 1. DNS

Add one record at whoever hosts `samtechpk.com` DNS:

| Type | Name | Value |
|---|---|---|
| A | `respite` | *the box's public IPv4* |

Confirm it resolves before touching Caddy. Its certificate request will fail
if the name does not yet point at the machine:

```powershell
Resolve-DnsName respite.samtechpk.com -Type A
```

## 2. Get the code onto the box

```powershell
cd C:\apps
git clone https://github.com/samranahmad09/hackathon-fortyguard.git respite
cd respite
git config core.hooksPath .githooks     # the key guard does not survive a clone
```

The processed tract layer is committed, so there is nothing to fetch from the
Temperature API on the server. That is deliberate: the FortyGuard API went down
three times in four days during the sprint, and no page load should depend on it.

## 3. Python environment

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## 4. Secrets

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` is gitignored and must stay that way. The app reads keys from the
environment and never returns their values. `/health` reports only whether each
one is *present*.

The map does not need any key at all. Only `/api/agent` needs `OPENAI_API_KEY`,
and only offline layer rebuilds need `FORTYGUARD_API_KEY`. The app loads `.env`
at import, and real environment variables take precedence, so a host that sets
them directly does not need the file.

## 5. Run it as a service

Bind to loopback so the app is reachable only through Caddy:

```powershell
.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8020
```

Verify locally on the box before wiring Caddy:

```powershell
Invoke-RestMethod http://127.0.0.1:8020/health | ConvertTo-Json
```

Expect `status: ok`, `layer_present: true`, `tracts: 134`.

Then make it survive reboots. A scheduled task needs no extra software:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\apps\respite\.venv\Scripts\python.exe" `
           -Argument "-m uvicorn api.main:app --host 127.0.0.1 --port 8020" `
           -WorkingDirectory "C:\apps\respite"
$trigger = New-ScheduledTaskTrigger -AtStartup
$set     = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
           -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "respite-api" -Action $action -Trigger $trigger `
  -Settings $set -RunLevel Highest -User "SYSTEM"
Start-ScheduledTask -TaskName "respite-api"
```

If NSSM is already installed on the box, prefer it. It gives real service
semantics and log redirection.

## 6. Caddy

Append [`Caddyfile.snippet`](Caddyfile.snippet) to the existing Caddyfile, then
validate *before* reloading so a syntax error cannot take the live sites down:

```powershell
caddy validate --config C:\caddy\Caddyfile
caddy reload   --config C:\caddy\Caddyfile
```

`reload` is graceful and existing sites keep serving. Adjust the log path in
the snippet if the Caddy log directory differs.

## 7. Verify from outside

From a machine that is *not* the box:

```powershell
Invoke-RestMethod https://respite.samtechpk.com/health | ConvertTo-Json
```

Then open the page and confirm the tracts draw, the panel reads
**18 tracts** with no relief, and the browser console is clean.

---

## Rebuilding the data layer

The layer is cached in memory on first request, so a rebuild needs a restart:

```powershell
.venv\Scripts\python scripts\build_layer.py
Restart-ScheduledTask -TaskName "respite-api"
```

Rebuilds cost FortyGuard credits and hit the API, so do them deliberately, never
on a schedule. The raw responses cache under `data/raw/` (gitignored) and are
reused, so re-running the script without changing parameters costs nothing.

## If something breaks

| Symptom | Likely cause |
|---|---|
| Caddy cannot get a certificate | DNS not resolving yet, or 80/443 blocked |
| 502 from Caddy | uvicorn not running. Check the scheduled task |
| `layer_present: false` | `data/processed/tracts_recovery.geojson` missing; run `build_layer.py` |
| Page loads, no tracts | check the browser console; `/api/tracts` should return 134 features |
| Stale numbers | the in-memory layer cache. Restart the task |
