# run_outreach.ps1 -- paced wrapper around the vendored linkedin-cli for manual outreach batches.
#
# YOU run this by hand -- never an unattended agent. A `session open --session work`
# owner must already be running in another terminal, and `login` done once. It loops
# handles, calls the vendored exe with --json, pretty-prints results, sleeps 30-60s
# (randomized) between calls, and HARD-STOPS on the first connection_limit or
# checkpoint_challenge error.
#
# Usage (from repo root):
#   .\working\scripts\outreach\run_outreach.ps1 -Handles alice-smith,bob-jones -Action status
#   .\working\scripts\outreach\run_outreach.ps1 -Handles alice-smith -Action connect
#   .\working\scripts\outreach\run_outreach.ps1 -Handles alice-smith -Action profile -Session work
#
# Windows PowerShell 5.1 compatible.

param(
    [Parameter(Mandatory = $true)]
    [string[]]$Handles,

    [Parameter(Mandatory = $true)]
    [ValidateSet("status", "connect", "profile")]
    [string]$Action,

    [string]$Session = "work"
)

$ErrorActionPreference = "Stop"

# Resolve the vendored exe relative to this script: working/scripts/outreach -> repo root
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$exe = Join-Path $repoRoot ".agents\vendor\linkedin-cli\.venv\Scripts\linkedin-cli.exe"

if (-not (Test-Path $exe)) {
    Write-Host "linkedin-cli.exe not found at:" -ForegroundColor Red
    Write-Host "  $exe"
    Write-Host "Run .\.agents\vendor\setup_linkedin_cli.ps1 from the repo root first."
    exit 1
}

# Safety reminder + confirm gate for connection requests
if ($Action -eq "connect") {
    Write-Host "You are about to send $($Handles.Count) connection request(s):" -ForegroundColor Yellow
    Write-Host "  $($Handles -join ', ')"
    Write-Host "Pacing caps: <=5 connects per org per day, <=10 per day total." -ForegroundColor Yellow
    $answer = Read-Host "Proceed? (y/N)"
    if ($answer -ne "y") {
        Write-Host "Aborted."
        exit 0
    }
}

$i = 0
$failures = 0

foreach ($handle in $Handles) {
    $i++
    Write-Host ""
    Write-Host ("[{0}/{1}] {2} {3}  ({4})" -f $i, $Handles.Count, $Action, $handle, (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Cyan

    # Capture stdout/stderr separately via temp files (clean in PS 5.1 --
    # avoids NativeCommandError wrapping from 2>&1 redirection).
    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process -FilePath $exe `
            -ArgumentList @("--session", $Session, $Action, $handle, "--json") `
            -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $outFile `
            -RedirectStandardError $errFile

        $stdout = ""
        $stderr = ""
        if (Test-Path $outFile) { $stdout = [System.IO.File]::ReadAllText($outFile) }
        if (Test-Path $errFile) { $stderr = [System.IO.File]::ReadAllText($errFile) }
    }
    finally {
        try { Remove-Item $outFile, $errFile -Force -ErrorAction Stop } catch {}
    }

    if ($proc.ExitCode -ne 0) {
        $failures++
        Write-Host ("  FAILED (exit {0})" -f $proc.ExitCode) -ForegroundColor Red
        if ($stderr.Trim().Length -gt 0) {
            Write-Host ("  " + $stderr.Trim()) -ForegroundColor Red
        }

        # HARD STOP on rate limit or security checkpoint -- do not continue, do not retry today.
        if ($stderr -match "connection_limit" -or $stderr -match "checkpoint_challenge") {
            Write-Host ""
            Write-Host "HARD STOP: LinkedIn rate limit or security checkpoint hit." -ForegroundColor Red
            Write-Host "Do NOT retry today. Remaining handles were skipped:" -ForegroundColor Red
            if ($i -lt $Handles.Count) {
                Write-Host ("  " + (($Handles | Select-Object -Skip $i) -join ", "))
            }
            if ($stderr -match "checkpoint_challenge") {
                Write-Host "Checkpoint: attach to the bound browser and clear it by hand before any further use."
            }
            Write-Host "Log this in the org's outreach_log.md action log."
            exit 2
        }

        # Other errors (profile_inaccessible, skip_profile, ...) -- log and continue.
        Write-Host "  Non-fatal error type -- skipping this handle and continuing." -ForegroundColor DarkYellow
    }
    else {
        if ($stdout.Trim().Length -gt 0) {
            $printed = $false
            try {
                $obj = $stdout | ConvertFrom-Json
                Write-Host ($obj | ConvertTo-Json -Depth 6)
                $printed = $true
            }
            catch {}
            if (-not $printed) { Write-Host $stdout }
        }
        else {
            Write-Host "  (no output)"
        }
    }

    # Randomized human-ish pacing between calls (skip after the last one).
    if ($i -lt $Handles.Count) {
        $delay = Get-Random -Minimum 30 -Maximum 61
        Write-Host ("  pausing {0}s before next call..." -f $delay) -ForegroundColor DarkGray
        Start-Sleep -Seconds $delay
    }
}

Write-Host ""
Write-Host ("Done: {0} handle(s), {1} failure(s). Update the outreach_log.md action log now." -f $Handles.Count, $failures) -ForegroundColor Green
if ($failures -gt 0) { exit 1 }
exit 0
