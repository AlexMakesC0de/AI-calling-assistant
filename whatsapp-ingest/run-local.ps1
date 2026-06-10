# Load environment from .env file in this directory
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*"?(.+?)"?\s*$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
} else {
    Write-Error "Missing .env file — copy .env.example to .env and fill in your credentials."
    exit 1
}

$env:WHATSAPP_EVENTS_DIR = "$PSScriptRoot\local-data\events"
$env:WHATSAPP_MEDIA_DIR = "$PSScriptRoot\local-data\media"
$env:WHATSAPP_TMP_DIR = "$PSScriptRoot\local-data\tmp"

Write-Host "Starting whatsapp-ingest on http://localhost:5011"
Write-Host "Twilio signature validation: $($env:TWILIO_VALIDATE_SIGNATURE)"
Write-Host ""

python "$PSScriptRoot\app.py"
