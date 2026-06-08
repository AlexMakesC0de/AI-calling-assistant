# Demo: personal Outlook -> email-monitor -> voice-app form -> Mailpit
# Prereqs: device login done (see docker logs support-email-monitor)
# Usage: .\scripts\demo-outlook-ingest.ps1

$ErrorActionPreference = "Stop"

Write-Host "1. Trigger inbox sync (POST /sync)..."
try {
    $sync = Invoke-RestMethod -Method Post -Uri "http://localhost:5003/sync" -TimeoutSec 600
    Write-Host ($sync | ConvertTo-Json -Compress)
} catch {
    Write-Host "Sync failed: $_"
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    Write-Host "`nTip: docker logs -f support-email-monitor (device login code?)"
    exit 1
}

Write-Host "`n2. Recent notifications..."
$notes = Invoke-RestMethod -Uri "http://localhost:5003/notifications" -TimeoutSec 30
Write-Host ($notes | ConvertTo-Json -Depth 6)

Write-Host "`n3. Check Mailpit for incident form: http://localhost:8025"
Write-Host "Done."
