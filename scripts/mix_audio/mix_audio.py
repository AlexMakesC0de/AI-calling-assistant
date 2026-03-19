#!/usr/bin/env python3
"""
mix_audio.py – Mix main audio with background noise for transcription testing.

Usage:
    python mix_audio.py <main_audio> <noise> <output.wav> [--noise-volume <dB>]

Supported formats: WAV, MP3, FLAC, OGG, M4A, etc.

Options:
    --noise-volume <dB>    Volume reduction for noise in dB (default: 20)
                          Lower values = louder noise, higher = quieter

Example:
    python mix_audio.py test_call.wav factory_noise.mp3 test_call_with_noise.wav --noise-volume 15
"""

import sys
import numpy as np
from scipy.io import wavfile
import librosa
import argparse

def load_audio(file_path):
    """Load audio file in any format (WAV, MP3, FLAC, etc.)."""
    audio, sr = librosa.load(file_path, sr=None, mono=True)
    # Librosa returns float32 in range [-1, 1]
    return sr, audio

def mix_audio(main_file, noise_file, output_file, noise_db=20):
    # Load audio files
    sr_main, main_audio = load_audio(main_file)
    sr_noise, noise_audio = load_audio(noise_file)
    
    # Resample noise to match main audio sample rate if needed
    if sr_main != sr_noise:
        noise_audio = librosa.resample(noise_audio, orig_sr=sr_noise, target_sr=sr_main)
    
    # Ensure both are float for processing (librosa already returns float)
    main_audio = np.array(main_audio, dtype=float)
    noise_audio = np.array(noise_audio, dtype=float)
    
    # Reduce noise volume (make it background) - convert dB to linear scale
    noise_reduction = 10 ** (noise_db / 20)  # dB to linear
    noise_audio = noise_audio / noise_reduction
    
    # If noise is shorter, loop it to match main audio length
    if len(noise_audio) < len(main_audio):
        loops = (len(main_audio) // len(noise_audio)) + 1
        noise_audio = np.tile(noise_audio, loops)
    
    # Trim noise to match main audio length
    noise_audio = noise_audio[:len(main_audio)]
    
    # Overlay noise onto main audio
    mixed = main_audio + noise_audio
    
    # Normalize to prevent clipping (keep in [-1, 1] range)
    max_val = np.max(np.abs(mixed))
    if max_val > 1.0:
        mixed = mixed / max_val
    
    # Convert to int16 for WAV export
    mixed_int16 = np.int16(mixed * 32767)
    
    # Export the mixed audio
    wavfile.write(output_file, sr_main, mixed_int16)
    
    print(f"✅ Mixed audio saved to {output_file}")
    print(f"   Main audio: {main_file} ({len(main_audio)/sr_main:.1f}s)")
    print(f"   Noise: {noise_file} ({len(noise_audio)/sr_main:.1f}s, {noise_db}dB reduction)")
    print(f"   Output: {output_file} ({len(mixed)/sr_main:.1f}s)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mix main audio with background noise for transcription testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mix_audio.py test_call.wav factory_noise.mp3 output.wav
  python mix_audio.py test_call.wav factory_noise.mp3 output.wav --noise-volume 15
  python mix_audio.py test_call.wav factory_noise.mp3 output.wav -nv 10
        """
    )
    parser.add_argument("main_audio", help="Path to main audio file")
    parser.add_argument("noise", help="Path to noise audio file")
    parser.add_argument("output", help="Path to output WAV file")
    parser.add_argument(
        "--noise-volume", "-nv",
        type=float,
        default=20,
        help="Volume reduction for noise in dB (default: 20). Lower = louder noise"
    )
    
    args = parser.parse_args()
    
    try:
        mix_audio(args.main_audio, args.noise, args.output, args.noise_volume)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)