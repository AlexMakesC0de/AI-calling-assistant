param(
    [switch]$DryRun,
    [int]$MinGpuVramGb = 8,
    [string]$Profile = "dev",
    [string[]]$ComposeExtraArgs
)

$ErrorActionPreference = "Stop"

# Auto-select CPU or GPU compose mode based on host capability.
# GPU mode is enabled only when:
# 1) nvidia-smi is available
# 2) at least one NVIDIA GPU has VRAM >= MinGpuVramGb
# 3) Docker can run a GPU-enabled container

$rootDir = Split-Path -Parent $PSScriptRoot
Set-Location $rootDir

$composeCpu = @("compose", "--profile", $Profile, "up", "-d", "--build")
$composeGpu = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml", "--profile", $Profile, "up", "-d", "--build")

if ($ComposeExtraArgs) {
    $composeCpu += $ComposeExtraArgs
    $composeGpu += $ComposeExtraArgs
}


$gpuMode = $false
$gpuReason = ""

$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $nvidiaSmi) {
    $gpuReason = "nvidia-smi is not available on host"
} else {
    $memoryLines = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
    $maxMib = 0

    foreach ($line in $memoryLines) {
        $trimmed = $line.Trim()
        $value = 0
        if ([int]::TryParse($trimmed, [ref]$value)) {
            if ($value -gt $maxMib) { $maxMib = $value }
        }
    }

    # Use decimal GB conversion so common 8 GB cards (~8000-8190 MiB reported)
    # are not incorrectly rejected.
    $minMib = $MinGpuVramGb * 1000
    if ($maxMib -lt $minMib) {
        $gpuReason = "largest GPU has $maxMib MiB, below required $minMib MiB"
    } else {
        try {
            & docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi *> $null
            if ($LASTEXITCODE -eq 0) {
                $gpuMode = $true
                $gpuReason = "NVIDIA GPU available ($maxMib MiB) and Docker GPU runtime works"
            } else {
                $gpuReason = "Docker GPU runtime is unavailable"
            }
        } catch {
            $gpuReason = "Docker GPU runtime is unavailable"
        }
    }
}

Write-Host "Host GPU check: $gpuReason"

if ($gpuMode) {
    $selected = $composeGpu
    Write-Host "Selected mode: GPU"
} else {
    $selected = $composeCpu
    Write-Host "Selected mode: CPU"
}

Write-Host ("Command: docker " + ($selected -join " "))

if ($DryRun) {
    Write-Host "Dry run enabled; command was not executed."
    exit 0
}

& docker @selected
