<#
.SYNOPSIS
  Start the StockPilot AI backend and frontend together with one command.

.DESCRIPTION
  Launches:
    - Backend : uvicorn app.main:app on http://127.0.0.1:8000 (uses .\venv when present)
    - Frontend: Vite dev server on http://localhost:5173 (uses the local npm installation)

  Behaviour:
    * All paths are resolved relative to this script (works from any directory,
      including paths containing spaces).
    * Checks prerequisites first (venv/python, uvicorn importable, node/npm,
      frontend\node_modules) and reports exactly what is missing. It never
      installs packages, never creates or recreates a virtual environment.
    * Refuses to start when port 8000 or 5173 is already occupied, and names
      the owning process, so no duplicate servers are launched.
    * Both services run inside THIS terminal. Their output is piped back and
      relayed here with [backend] / [frontend] prefixes; no extra console
      windows are opened.
    * Verifies each service actually answers over HTTP before reporting it
      ready; server errors and early process exits are reported, not hidden.
    * Runs both services concurrently until Ctrl+C or until one of them
      exits, then stops ONLY the processes this script started: the tracked
      process trees (verified against a pre-kill descendant snapshot) plus
      any listener left on the ports this script claimed. Unrelated
      processes are left alone.

  This script never modifies stockpilot.db, .env, source files, or user data.

.EXAMPLE
  .\start-stockpilot.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\start-stockpilot.ps1
#>

# Native command failures are inspected via $LASTEXITCODE, not thrown.
$ErrorActionPreference = 'Continue'

# Fixed by the app configuration (Vite strictPort + proxy target + CORS),
# not configurable here on purpose.
$BackendPort = 8000
$FrontendPort = 5173
$ReadyTimeoutSec = 30
$StartedAt = Get-Date

# --- Paths (relative to this script; no machine-specific paths) ---
$Root = $PSScriptRoot
if (-not $Root) { $Root = Split-Path -Parent $MyInvocation.MyCommand.Path }
$FrontendDir = Join-Path $Root 'frontend'
$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'

# --- Console helpers ---
function Say([string]$Message) { Write-Host $Message }
function Ok([string]$Message) { Write-Host "[ok]   $Message" -ForegroundColor Green }
function Warn([string]$Message) { Write-Host "[warn] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[FAIL] $Message" -ForegroundColor Red }

# --- Same-terminal service logging -------------------------------------------
# Services are started with UseShellExecute=$false, CreateNoWindow=$true and
# redirected stdout/stderr, so they never open a new window and never write
# straight to the console. Their lines are queued as PowerShell events and
# relayed into THIS terminal by Write-PendingServiceLogs on the main thread,
# with a fixed prefix so backend and frontend output stay distinguishable.
$ServiceLogSources = @{
    'stockpilot.backend.out'  = @{ Prefix = '[backend]  '; Color = 'Cyan' }
    'stockpilot.backend.err'  = @{ Prefix = '[backend]  '; Color = 'Cyan' }
    'stockpilot.frontend.out' = @{ Prefix = '[frontend] '; Color = 'Magenta' }
    'stockpilot.frontend.err' = @{ Prefix = '[frontend] '; Color = 'Magenta' }
}

function Start-ServiceProcess([string]$FilePath, [string]$ArgumentList, [string]$WorkingDirectory, [string]$Label) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = $ArgumentList
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false     # pipe stdio back into this terminal; no shell window
    $psi.CreateNoWindow = $true       # never open an extra console window
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    # Closed right after start: gives cmd.exe EOF on the "Terminate batch job"
    # prompt instead of letting it read from the shared console stdin.
    $psi.RedirectStandardInput = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    if ($FilePath -like '*python.exe') {
        # The child sees a pipe, not a TTY: force UTF-8 stdio so non-ASCII
        # log lines decode correctly with the UTF-8 readers set above.
        $psi.Environment['PYTHONIOENCODING'] = 'utf-8'
    }

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived `
        -SourceIdentifier "stockpilot.$Label.out"
    $null = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived `
        -SourceIdentifier "stockpilot.$Label.err"
    $null = $proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    $proc.StandardInput.Close()
    return $proc
}

# Relays every service log line queued since the last call into this terminal.
# Called from the readiness poll and the main loop so output keeps flowing.
# Only events with our SourceIdentifiers are consumed; anything else queued in
# the session is left untouched.
function Write-PendingServiceLogs {
    foreach ($evt in @(Get-Event -ErrorAction SilentlyContinue)) {
        $meta = $ServiceLogSources[$evt.SourceIdentifier]
        if (-not $meta) { continue }  # not ours - leave it in the queue
        Remove-Event -EventIdentifier $evt.EventIdentifier -ErrorAction SilentlyContinue
        $line = $evt.SourceEventArgs.Data
        if ($null -eq $line) { continue }  # end-of-stream marker, not a log line
        if ($line -eq '') { Write-Host ''; continue }
        Write-Host ($meta.Prefix + $line) -ForegroundColor $meta.Color
    }
}

# --- Port probe: $true when nothing accepts connections on either loopback ---
# Vite may bind ::1 only, so both IPv4 and IPv6 loopbacks are checked.
# A completed connect means something accepted us => port in use; a refused
# connection (EndConnect throws) means nothing listens on this address.
function Test-PortFree([int]$Port) {
    foreach ($addr in @('127.0.0.1', '::1')) {
        $client = $null
        try {
            $ip = [System.Net.IPAddress]::Parse($addr)
            $client = New-Object System.Net.Sockets.TcpClient($ip.AddressFamily)
            # NOTE: TcpClient.BeginConnect takes (IPAddress, int port, callback,
            # state) - there is no IPEndPoint overload. The old IPEndPoint call
            # threw on every probe and was swallowed, so conflicts were missed.
            $pending = $client.BeginConnect($ip, $Port, $null, $null)
            if ($pending.AsyncWaitHandle.WaitOne(500, $false)) {
                try {
                    $client.EndConnect($pending)
                    return $false  # something accepts => in use
                } catch {
                    # connection refused on this address => free here
                }
            }
            # connect timed out on loopback: treat as free (same as before)
        } catch {
            # address unparsable / family unsupported => free here
        } finally {
            if ($client) { $client.Close() }
        }
    }
    return $true
}

function Get-PortOwner([int]$Port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
        if ($conn) {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
            return "$($proc.ProcessName) (PID $($conn.OwningProcess))"
        }
    } catch { }
    return 'an unknown process'
}

function Test-HttpOk([string]$Url) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
    } catch {
        return $false
    }
}

# Polls any of the given URLs until one answers, the process exits, or the
# timeout passes. Multiple URLs cover both loopback families (a service may
# bind 127.0.0.1 or ::1). Returns 'ready' | 'exited' | 'timeout'.
# Service log lines queued in the meantime are relayed so startup output
# (including errors) stays visible in this terminal while we wait.
function Wait-ForHttp([string[]]$Urls, [int]$TimeoutSec, [System.Diagnostics.Process]$Proc) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        Write-PendingServiceLogs
        if ($Proc.HasExited) { return 'exited' }
        foreach ($url in $Urls) {
            if (Test-HttpOk $url) { return 'ready' }
        }
        Start-Sleep -Milliseconds 500
    }
    Write-PendingServiceLogs
    if ($Proc.HasExited) { return 'exited' }
    foreach ($url in $Urls) {
        if (Test-HttpOk $url) { return 'ready' }
    }
    return 'timeout'
}

# Collects the full descendant tree of $RootPid via CIM parent links (one
# snapshot, taken while the tree is still alive). taskkill /T alone can miss
# parts of an npm/node tree once an intermediate process has exited, so this
# snapshot is used as a follow-up sweep list after the tree kill.
function Get-DescendantPids([int]$RootPid) {
    $snapshot = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Select-Object ProcessId, ParentProcessId, CreationDate)
    $childrenOf = @{}
    foreach ($p in $snapshot) {
        $ppid = [int]$p.ParentProcessId
        if (-not $childrenOf.ContainsKey($ppid)) { $childrenOf[$ppid] = @() }
        $childrenOf[$ppid] += $p
    }
    $result = @()
    $seen = @{ $RootPid = $true }
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($RootPid)
    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        foreach ($child in $childrenOf[$current]) {
            $childPid = [int]$child.ProcessId
            if ($seen.ContainsKey($childPid)) { continue }
            $seen[$childPid] = $true
            # CreationDate rides along so a survivor can be re-verified after
            # the kill: a recycled PID owned by an unrelated process must not
            # be touched.
            $result += [pscustomobject]@{ Pid = $childPid; CreationDate = $child.CreationDate }
            $queue.Enqueue($childPid)
        }
    }
    return $result
}

# Stops one process started by this script, including its descendants
# (npm -> cmd -> node/vite). The tree kill is rooted at the given PID, so
# unrelated processes are never touched. Because taskkill /T is not trusted
# to catch every npm/node descendant, any survivor of the snapshot taken
# before the kill is re-verified (same creation time => same process) and
# then killed individually.
function Stop-TrackedProcess([System.Diagnostics.Process]$Proc, [string]$Label) {
    if ($null -eq $Proc) { return }
    try {
        if (-not $Proc.HasExited) {
            $descendants = @(Get-DescendantPids -RootPid $Proc.Id)
            $null = & taskkill.exe /PID $Proc.Id /T /F 2>&1
            $null = $Proc.WaitForExit(10000)
            if ($Proc.HasExited) {
                Ok "Stopped $Label (PID $($Proc.Id))."
            } else {
                Fail "Could not stop $Label (PID $($Proc.Id)); please end that process manually."
            }
            foreach ($entry in $descendants) {
                $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.Pid)" -ErrorAction SilentlyContinue
                if ($null -eq $current) { continue }  # gone = success
                if ($current.CreationDate -eq $entry.CreationDate) {
                    $null = & taskkill.exe /PID $entry.Pid /F 2>&1
                    Warn "Stopped a leftover $Label descendant (PID $($entry.Pid))."
                }
            }
        }
    } catch {
        Fail "Could not stop ${Label}: $($_.Exception.Message)"
    }
}

# A process-tree kill can miss grandchildren (npm re-parents some children),
# so afterwards ensure the ports this script claimed are actually released.
# Both ports were verified free before startup, therefore any listener now
# on them was started by this script - unless the owner process predates
# this script's launch, in which case it is left untouched and reported.
function Release-ScriptPorts([int[]]$Ports, [datetime]$StartedAt) {
    foreach ($port in $Ports) {
        try {
            $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
                Select-Object -First 1
            if (-not $conn) { continue }
            $owner = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
            if ($owner.StartTime -ge $StartedAt) {
                $null = & taskkill.exe /PID $owner.Id /T /F 2>&1
                Warn "Stopped a leftover service process on port $port (PID $($owner.Id))."
            } else {
                Warn "Port $port is held by PID $($owner.Id), which was not started by this script; leaving it untouched."
            }
        } catch { }
    }
    # Verify the ports are really released; report honestly if not.
    $busy = @()
    for ($i = 0; $i -lt 10; $i++) {
        $busy = @()
        foreach ($port in $Ports) {
            try {
                $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
                    Select-Object -First 1
                if ($conn) { $busy += "$port (PID $($conn.OwningProcess))" }
            } catch { }
        }
        if ($busy.Count -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    if ($busy.Count -gt 0) {
        Fail "These ports are still occupied after cleanup: $($busy -join ', '). Please end those processes manually."
    }
}

# ======================= 1. Prerequisites =======================
Say ''
Say '=============================================='
Say ' StockPilot AI - startup checks'
Say " Project : $Root"
Say '=============================================='

$problems = @()

# Python: prefer the existing virtual environment, fall back to PATH.
$python = $null
if (Test-Path $VenvPython) {
    $python = $VenvPython
    Ok "Python (venv): $VenvPython"
} else {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) {
        $python = $sysPython.Source
        Warn "venv not found at venv\Scripts\python.exe - falling back to system python: $python"
        Warn 'If the backend then fails to import modules, create the venv first (this script never installs anything).'
    } else {
        $problems += 'Python not found: no venv\Scripts\python.exe and no "python" on PATH. Create the environment first: python -m venv venv; venv\Scripts\pip install -r requirements.txt'
    }
}

if ($python) {
    & $python -c 'import uvicorn, fastapi, dotenv' 2>$null
    if ($LASTEXITCODE -ne 0) {
        $problems += "Backend dependencies are missing for '$python' (uvicorn/fastapi/python-dotenv not importable). Install them first: pip install -r requirements.txt (this script does not install packages)."
    }
}

# Node and npm: the existing local installation only.
$npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
if (-not $npm) { $npm = Get-Command 'npm' -ErrorAction SilentlyContinue }
if (-not $npm -or $npm.Source -like '*.ps1') {
    $problems += 'npm not found on PATH (or only a PowerShell shim exists). Install Node.js / fix PATH; this script does not install tools.'
} else {
    Ok "npm: $($npm.Source)"
}

# Frontend dependencies must already be installed.
if (-not (Test-Path (Join-Path $FrontendDir 'node_modules\vite'))) {
    $problems += "frontend\node_modules is missing or incomplete. Run ""npm install"" in ""$FrontendDir"" once first (this script does not install packages)."
} else {
    Ok "frontend dependencies: $FrontendDir\node_modules"
}

if ($problems.Count -gt 0) {
    Fail 'Missing prerequisites - nothing was started:'
    foreach ($p in $problems) { Fail "  - $p" }
    Say ''
    exit 1
}

# ======================= 2. Port conflicts =======================
$conflicts = @()
if (-not (Test-PortFree $BackendPort)) {
    $conflicts += "port $BackendPort (backend) is already in use by $(Get-PortOwner $BackendPort)"
}
if (-not (Test-PortFree $FrontendPort)) {
    $conflicts += "port $FrontendPort (frontend) is already in use by $(Get-PortOwner $FrontendPort)"
}
if ($conflicts.Count -gt 0) {
    Fail 'Port conflict - refusing to launch duplicate servers:'
    foreach ($c in $conflicts) { Fail "  - $c" }
    Fail 'Stop the process(es) above and run this script again.'
    Say ''
    exit 1
}
Ok "Ports are free: backend $BackendPort, frontend $FrontendPort"

# ======================= 3. Start both services =======================
Say ''
Say 'Starting services in this terminal (backend and frontend logs are prefixed below)...'

$backendProc = $null
$frontendProc = $null
$hadFailure = $false

try {
    # Backend: uvicorn from the resolved interpreter, project root as cwd.
    $backendProc = Start-ServiceProcess -FilePath $python `
        -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' `
        -WorkingDirectory $Root -Label 'backend'
    Say "  backend  PID $($backendProc.Id)"

    # Frontend: local npm from PATH, frontend directory as cwd.
    $frontendProc = Start-ServiceProcess -FilePath $npm.Source `
        -ArgumentList 'run dev' `
        -WorkingDirectory $FrontendDir -Label 'frontend'
    Say "  frontend PID $($frontendProc.Id)"

    # --- Readiness: only claim "ready" after a real HTTP 2xx/3xx answer.
    # The frontend is probed on both loopback families because Vite binds
    # whichever "localhost" resolves to on this machine. ---
    $backendUrls = @("http://127.0.0.1:$BackendPort/api/v1/ai/status")
    $frontendUrls = @("http://[::1]:$FrontendPort/", "http://127.0.0.1:$FrontendPort/")
    $backendState = Wait-ForHttp $backendUrls $ReadyTimeoutSec $backendProc
    $frontendState = Wait-ForHttp $frontendUrls $ReadyTimeoutSec $frontendProc

    if ($backendState -eq 'ready') {
        Ok "Backend ready  : http://127.0.0.1:$BackendPort  (API docs: http://127.0.0.1:$BackendPort/docs)"
    } elseif ($backendState -eq 'exited') {
        Fail "Backend exited during startup (exit code $($backendProc.ExitCode)). Check the [backend] log output above for the error."
        $hadFailure = $true
    } else {
        Warn "Backend did NOT answer HTTP within ${ReadyTimeoutSec}s - not reporting it ready. Check the [backend] log output above."
    }

    if ($frontendState -eq 'ready') {
        Ok "Frontend ready : http://localhost:$FrontendPort"
    } elseif ($frontendState -eq 'exited') {
        Fail "Frontend exited during startup (exit code $($frontendProc.ExitCode)). Check the [frontend] log output above for the error."
        $hadFailure = $true
    } else {
        Warn "Frontend did NOT answer HTTP within ${ReadyTimeoutSec}s - not reporting it ready. Check the [frontend] log output above."
    }

    $unconfirmed = @()
    if ($backendState -ne 'ready') { $unconfirmed += 'backend' }
    if ($frontendState -ne 'ready') { $unconfirmed += 'frontend' }

    if (-not $hadFailure) {
        Say ''
        if ($unconfirmed.Count -eq 0) {
            Say '----------------------------------------------'
            Say ' StockPilot AI is running:'
            Say "   Frontend : http://localhost:$FrontendPort"
            Say "   Backend  : http://127.0.0.1:$BackendPort"
            Say '   Data     : this script never modifies stockpilot.db, .env or source files.'
            Say ' Both services log into this terminal. Press Ctrl+C to stop both.'
            Say '----------------------------------------------'
        } else {
            Warn "Startup NOT fully confirmed: $($unconfirmed -join ' and ') did not answer HTTP within ${ReadyTimeoutSec}s (see warnings above)."
            Warn 'The processes stay alive - check their log output above, then verify the URLs yourself. Press Ctrl+C to stop.'
        }

        # --- Keep both running; relay logs; report (do not hide) unexpected exits. ---
        while ($true) {
            Write-PendingServiceLogs
            if ($backendProc.HasExited) {
                Fail "Backend exited unexpectedly (exit code $($backendProc.ExitCode))."
                $hadFailure = $true
                break
            }
            if ($frontendProc.HasExited) {
                Fail "Frontend exited unexpectedly (exit code $($frontendProc.ExitCode))."
                $hadFailure = $true
                break
            }
            Start-Sleep -Milliseconds 250
        }
    } else {
        Say ''
        Fail 'Startup failed - see messages above.'
    }
} catch {
    $hadFailure = $true
    Fail "Startup error: $($_.Exception.Message)"
} finally {
    # Runs on Ctrl+C, on errors, and on normal exit: stop ONLY what we started.
    Stop-TrackedProcess $frontendProc 'frontend'
    Stop-TrackedProcess $backendProc 'backend'
    # Relay whatever the services printed last, then detach from their events.
    Write-PendingServiceLogs
    foreach ($id in @($ServiceLogSources.Keys)) {
        Unregister-Event -SourceIdentifier $id -ErrorAction SilentlyContinue
    }
    Release-ScriptPorts -Ports @($BackendPort, $FrontendPort) -StartedAt $StartedAt
    Say 'Stopped the processes started by this script. No data or files were changed.'
}

Say ''
if ($hadFailure) { exit 1 } else { exit 0 }


