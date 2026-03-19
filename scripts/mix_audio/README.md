# Mix Audio

Mix main audio with background noise for testing transcription with noise.

## Prerequisites

- Python 3.8+
- Dependencies: `pip install -r requirements.txt`

## Usage

```bash
python mix_audio.py <main_audio> <noise> <output.wav> [--noise-volume <dB>]
```

### Options

- `--noise-volume <dB>`, `-nv <dB>`: Volume reduction for noise in dB (default: 20)
  - Lower values = louder noise (e.g., 10 dB = moderate noise)
  - Higher values = quieter noise (e.g., 30 dB = very quiet noise)

### Examples

```bash
# Default 20dB noise reduction
python mix_audio.py ../../test_call.wav factory_noise.mp3 ../../test_call_with_noise.wav

# Louder noise (15dB reduction)
python mix_audio.py ../../test_call.wav factory_noise.mp3 ../../test_call_with_noise.wav --noise-volume 15

# Very quiet noise (30dB reduction)
python mix_audio.py ../../test_call.wav factory_noise.mp3 ../../test_call_with_noise.wav -nv 30
```

This will:
- Load main audio and noise files (supports WAV, MP3, FLAC, OGG, M4A, etc.)
- Reduce noise volume by specified dB
- Loop noise if shorter than main audio
- Overlay noise onto main audio
- Save the mixed result as WAV