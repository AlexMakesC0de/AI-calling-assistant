#!/usr/bin/env bash
set -euo pipefail

# Auto-select CPU or GPU compose mode based on host capability.
# GPU mode is enabled only when:
# 1) nvidia-smi is available
# 2) at least one NVIDIA GPU has VRAM >= MIN_GPU_VRAM_GB
# 3) Docker can run a GPU-enabled container

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MIN_GPU_VRAM_GB="${MIN_GPU_VRAM_GB:-8}"
PROFILE="${COMPOSE_PROFILE:-dev}"
DRY_RUN="${DRY_RUN:-0}"
EXTRA_ARGS=()

usage() {
    cat <<'EOF'
Usage:
  ./scripts/start-stack-auto.sh [--dry-run] [--min-gpu-vram-gb N] [--profile NAME] [-- <extra docker compose args>]

Examples:
  ./scripts/start-stack-auto.sh
  ./scripts/start-stack-auto.sh --min-gpu-vram-gb 10
  ./scripts/start-stack-auto.sh --dry-run
  ./scripts/start-stack-auto.sh -- --remove-orphans
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --min-gpu-vram-gb)
            shift
            MIN_GPU_VRAM_GB="${1:-}"
            if ! printf '%s' "$MIN_GPU_VRAM_GB" | grep -Eq '^[0-9]+$'; then
                echo "Invalid value for --min-gpu-vram-gb: $MIN_GPU_VRAM_GB" >&2
                exit 1
            fi
            ;;
        --profile)
            shift
            PROFILE="${1:-}"
            if [ -z "$PROFILE" ]; then
                echo "--profile requires a value" >&2
                exit 1
            fi
            ;;
        --)
            shift
            while [ "$#" -gt 0 ]; do
                EXTRA_ARGS+=("$1")
                shift
            done
            break
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
done

compose_cpu=(docker compose --profile "$PROFILE" up -d --build)
compose_gpu=(docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile "$PROFILE" up -d --build)

if [ "${#EXTRA_ARGS[@]}" -gt 0 ]; then
    compose_cpu+=("${EXTRA_ARGS[@]}")
    compose_gpu+=("${EXTRA_ARGS[@]}")
fi

gpu_mode=0
gpu_reason=""

if ! command -v nvidia-smi >/dev/null 2>&1; then
    gpu_reason="nvidia-smi is not available on host"
else
    # Use decimal GB conversion so common 8 GB cards (~8000-8190 MiB reported)
    # are not incorrectly rejected.
    min_mib=$((MIN_GPU_VRAM_GB * 1000))
    max_mib=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | awk 'BEGIN{m=0} {if ($1>m) m=$1} END{print m}')

    if [ -z "$max_mib" ] || ! printf '%s' "$max_mib" | grep -Eq '^[0-9]+$'; then
        gpu_reason="unable to read GPU memory from nvidia-smi"
    elif [ "$max_mib" -lt "$min_mib" ]; then
        gpu_reason="largest GPU has ${max_mib} MiB, below required ${min_mib} MiB"
    else
        if docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
            gpu_mode=1
            gpu_reason="NVIDIA GPU available (${max_mib} MiB) and Docker GPU runtime works"
        else
            gpu_reason="Docker GPU runtime is unavailable"
        fi
    fi
fi

echo "Host GPU check: $gpu_reason"

if [ "$gpu_mode" -eq 1 ]; then
    selected=("${compose_gpu[@]}")
    echo "Selected mode: GPU"
else
    selected=("${compose_cpu[@]}")
    echo "Selected mode: CPU"
fi

echo "Command: ${selected[*]}"

if [ "$DRY_RUN" = "1" ]; then
    echo "Dry run enabled; command was not executed."
    exit 0
fi

"${selected[@]}"
