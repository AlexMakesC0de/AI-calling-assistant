# Scripts

Utility scripts for the IT-2C project.

## Available Scripts

### start-stack-auto.sh
Auto-start script for Linux/macOS that detects GPU readiness and starts:
- GPU mode when NVIDIA + Docker GPU runtime are available and VRAM threshold is met.
- CPU mode otherwise.

Usage:

```bash
chmod +x scripts/start-stack-auto.sh
./scripts/start-stack-auto.sh
./scripts/start-stack-auto.sh --dry-run
./scripts/start-stack-auto.sh --min-gpu-vram-gb 10
```

Notes:
- Default minimum GPU VRAM is 8 GB (`--min-gpu-vram-gb 8`).
- VRAM threshold uses decimal conversion (`1 GB = 1000 MiB`) to avoid false
	negatives on cards that report slightly below powers-of-two values.

### start-stack-auto.ps1
Auto-start script for Windows PowerShell with the same GPU/CPU selection logic.

Usage:

```powershell
./scripts/start-stack-auto.ps1
./scripts/start-stack-auto.ps1 -DryRun
./scripts/start-stack-auto.ps1 -MinGpuVramGb 10
```

### mix_audio/
Mix main audio with background noise for testing transcription with noise.

See [mix_audio/README.md](mix_audio/README.md) for usage instructions.