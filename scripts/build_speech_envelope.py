#!/usr/bin/env python3
"""Build deterministic talking-ray strength from the unchanged narration WAV.

Only the narration drives the avatar; music and sound effects are excluded.
Run with the bundled Python (numpy installed), or any Python with numpy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path

from runtime_support import ensure_dependencies
ensure_dependencies(('numpy',))
import numpy as np


def spans(mask: np.ndarray):
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def build(project: Path, fps: int = 30, frames: int = 1561, narration: str = 'audio/narration.wav') -> dict:
    source = project / narration
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with wave.open(str(source), 'rb') as wav:
        if wav.getsampwidth() != 2:
            raise ValueError('Expected signed 16-bit PCM narration WAV')
        rate, channels, samples = wav.getframerate(), wav.getnchannels(), wav.getnframes()
        pcm = np.frombuffer(wav.readframes(samples), dtype='<i2').reshape(-1, channels)
        # Channel-wise energy avoids accidental cancellation in other stereo files.
        energy = np.mean((pcm.astype(np.float64) / 32768.0) ** 2, axis=1)

    hop_s = 0.005
    hop = round(rate * hop_s)
    half_window = round(rate * 0.010)
    centers = np.arange(0, samples + 1, hop)
    integral = np.r_[0.0, np.cumsum(energy)]
    left = np.maximum(0, centers - half_window)
    right = np.minimum(samples, centers + half_window)
    rms = np.sqrt((integral[right] - integral[left]) / np.maximum(1, right - left))

    # Hysteresis protects soft syllables; 80 ms hangover bridges tiny phoneme gaps.
    open_level = 10 ** (-39.0 / 20)
    close_level = 10 ** (-43.0 / 20)
    hangover_s = 0.080
    attack_s, release_s = 0.015, 0.080
    active_rms = rms[rms >= open_level]
    reference = max(float(np.percentile(active_rms, 95)) if len(active_rms) else open_level, close_level + 1e-6)
    target = np.clip((rms - close_level) / (reference - close_level), 0, 1) ** 0.65
    attack_coef = math.exp(-hop_s / attack_s)
    release_coef = math.exp(-hop_s / release_s)
    opened, quiet_steps, previous = False, 0, 0.0
    gate, envelope = [], []
    hold_steps = round(hangover_s / hop_s)
    for level, strength in zip(rms, target):
        if level >= open_level:
            opened, quiet_steps = True, 0
        elif opened and level < close_level:
            quiet_steps += 1
            if quiet_steps >= hold_steps:
                opened = False
        elif level >= close_level:
            quiet_steps = 0
        if opened:
            coef = attack_coef if strength > previous else release_coef
            previous = coef * previous + (1 - coef) * float(strength)
        else:
            # Prevent release tails or floating noise from animating genuine pauses.
            previous = 0.0
        gate.append(opened)
        envelope.append(previous)
    gate = np.asarray(gate, dtype=bool)
    envelope = np.asarray(envelope)
    frame_times = np.arange(frames) / fps
    high_times = centers / rate
    values = np.interp(frame_times, high_times, envelope, left=0, right=0)
    gate_index = np.clip(np.floor(frame_times / hop_s).astype(int), 0, len(gate) - 1)
    values[~gate[gate_index]] = 0
    values = np.round(np.clip(values, 0, 1), 5)

    # Interior samples of sustained low-energy pauses must have no animation.
    silent_ranges = []
    tested_indices = []
    for start, end in spans(rms < close_level):
        start_s, end_s = start * hop_s, min(end * hop_s, samples / rate)
        if end_s - start_s >= 0.12:
            interior = np.flatnonzero((frame_times >= start_s + hangover_s + hop_s)
                                      & (frame_times < end_s - hop_s))
            tested_indices.extend(interior.tolist())
            silent_ranges.append({'from': round(start_s, 3), 'to': round(end_s, 3),
                                  'zeroInteriorFrames': int(len(interior))})
    if tested_indices and np.any(values[tested_indices] != 0):
        raise AssertionError('Talking rays remain active inside a sustained pause')
    if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
        raise AssertionError('Source narration changed')

    assets = project / 'assets'
    assets.mkdir(exist_ok=True)
    data = values.tolist()
    (assets / 'speech-envelope.json').write_text(json.dumps(data, separators=(',', ':')) + '\n')
    (assets / 'speech-envelope.js').write_text(
        '// 30 fps narration-driven talking strength. 0 means silent: close mouth and hold ray pose.\n'
        'window.SPEECH_ENVELOPE=' + json.dumps(data, separators=(',', ':')) + ';\n')
    report = {
        'source': narration, 'sourceSha256': original_hash,
        'sourceUnchanged': True, 'fps': fps, 'frames': frames,
        'durationSeconds': samples / rate,
        'rmsWindowMs': 20, 'analysisHopMs': 5,
        'attackMs': 15, 'releaseMs': 80, 'silenceHangoverMs': 80,
        'gateOpenDbfs': -39, 'gateCloseDbfs': -43,
        'normalization': '95th percentile voiced RMS; power 0.65',
        'normalizationRms': reference,
        'nonzeroFrames': int(np.count_nonzero(values)),
        'zeroFrames': int(np.count_nonzero(values == 0)),
        'min': float(values.min()), 'max': float(values.max()),
        'sustainedPauseChecks': len(tested_indices),
        'sustainedPausesAllZero': True, 'silenceRanges': silent_ranges,
        'zeroEnvelopeRanges': [
            {'from': round(s / fps, 3), 'to': round(e / fps, 3)}
            for s, e in spans(values == 0) if e - s >= 2
        ],
        'usage': 'Load assets/speech-envelope.js before renderer. Sample at floor(t * fps), clamped to the frame array. Close mouth and hold the previous ray pose at zero strength. Never animate speech during a sustained pause.'
    }
    (assets / 'speech-envelope-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('project',type=Path)
    args=parser.parse_args(); project=args.project.resolve()
    e=json.loads((project/'episode.json').read_text())
    report=build(project,e['fps'],round(e['duration']*e['fps']),e.get('narration','audio/narration.wav'))
    print(json.dumps({k:report[k] for k in ('frames','zeroFrames','sustainedPauseChecks','sourceUnchanged')}))
