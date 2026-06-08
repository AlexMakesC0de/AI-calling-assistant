# Quick smoke test after full stack is up (ISR-242/243/311).
# Usage: .\scripts\test-email-ingest.ps1

$ErrorActionPreference = "Stop"
$base = "http://localhost:5000"

Write-Host "1. voice-app health..."
$health = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 10
Write-Host ($health | ConvertTo-Json -Compress)

Write-Host "`n2. POST /ingest/email (synthetic support email)..."
$body = @{
    subject = "Machine 3 stopped - conveyor belt"
    sender  = "plant.operator@example.com"
    body    = "Line 3 emergency stop. Motor overheating. Need technician today."
    message_id = "test-smoke-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    received_at = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json

try {
    $resp = Invoke-RestMethod -Method Post -Uri "$base/ingest/email" `
        -ContentType "application/json" -Body $body -TimeoutSec 600
    Write-Host ($resp | ConvertTo-Json -Depth 8)
    $formStatus = $resp.pipeline.incident_form.status
    if ($formStatus -eq "completed") {
        Write-Host "`nOK: incident form completed - check Mailpit http://localhost:8025"
        exit 0
    }
    Write-Host "`nPartial/stopped: form status=$formStatus"
    exit 1
} catch {
    Write-Host "FAILED: $_"
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    exit 1
}
