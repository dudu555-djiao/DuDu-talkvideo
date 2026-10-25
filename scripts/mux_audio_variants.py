#!/usr/bin/env python3
"""Copy one picture master into versions with existing, aligned AAC soundtracks.

Manifest: [{"id":"voice", "audio":"voice.m4a", "output":"out/voice.mp4"}].
Manifest paths are relative to its directory. Audio can also come from an MP4.
Only AAC stream copy is supported: prepare any WAV/mixes as AAC separately.
No rendering, audio mixing, normalization, shortening or overwrite is performed.
Inputs with soft subtitles are rejected; use a subtitle-preserving workflow instead.
Requires Python 3.10+, ffmpeg and ffprobe; standard library only.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from fractions import Fraction


def run(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode or proc.stderr.strip():
        raise ValueError(proc.stderr.strip()[-3000:])
    return proc.stdout


def probe(path, ffprobe, count=False):
    return json.loads(run([ffprobe, '-v', 'error'] + (['-count_frames'] if count else []) +
                          ['-show_streams', '-of', 'json', str(path)]))['streams']


def stream_hash(path, selector, ffmpeg):
    return run([ffmpeg, '-v', 'error', '-i', str(path), '-map', selector,
                '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-']).strip()


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def finite(stream, key):
    value = float(stream.get(key, 'nan'))
    if not math.isfinite(value):
        raise ValueError(f'Stream {key} must be available and finite')
    return value


def single_stream(streams, kind):
    selected = [stream for stream in streams if stream['codec_type'] == kind]
    if len(selected) != 1:
        raise ValueError(f'Input must contain exactly one {kind} stream')
    return selected[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('picture', type=Path, help='One zero-start picture master (its audio is ignored)')
    parser.add_argument('manifest', type=Path, help='JSON variant list; see --help example')
    parser.add_argument('--report', type=Path, help='New JSON report file; default prints to stdout')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args()
    staged = []
    published = []
    try:
        ffmpeg, ffprobe = shutil.which(args.ffmpeg), shutil.which(args.ffprobe)
        if not ffmpeg or not ffprobe:
            raise ValueError('ffmpeg/ffprobe not found; install FFmpeg or pass their paths')
        if args.report and args.report.exists():
            raise ValueError('Report exists; choose a new path')
        picture = args.picture.resolve(strict=True)
        manifest = args.manifest.resolve(strict=True)
        rows = json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(rows, list) or not rows:
            raise ValueError('Manifest must be a nonempty list')
        picture_streams = probe(picture, ffprobe, count=True)
        if any(stream['codec_type'] == 'subtitle' for stream in picture_streams):
            raise ValueError('Picture contains soft subtitles. This tool supports video + AAC only; use a subtitle-preserving workflow instead.')
        video = single_stream(picture_streams, 'video')
        duration = finite(video, 'duration')
        start = finite(video, 'start_time')
        if duration <= 0 or abs(start) > max(1e-6, float(Fraction(video['time_base']))):
            raise ValueError('Picture must have a positive duration and start at zero')
        frames = int(video.get('nb_read_frames', -1))
        if frames <= 0:
            raise ValueError('Picture decoded frame count is unavailable')
        if video.get('nb_frames') not in (None, 'N/A') and int(video['nb_frames']) != frames:
            raise ValueError('Picture container and decoded frame counts differ')
        video_hash = stream_hash(picture, '0:v:0', ffmpeg)
        picture_sha = sha256(picture)
        prepared = []
        ids, outputs = set(), set()
        inputs = {picture, manifest}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise ValueError('Each variant needs a nonempty string id')
            if row['id'] in ids:
                raise ValueError('Variant ids must be unique')
            ids.add(row['id'])
            audio = (manifest.parent / row['audio']).resolve(strict=True)
            target = (manifest.parent / row['output']).resolve()
            if target.suffix.lower() != '.mp4' or target in outputs or target.exists():
                raise ValueError('Outputs must be distinct, nonexistent .mp4 paths')
            outputs.add(target)
            inputs.add(audio)
            audio_streams = probe(audio, ffprobe)
            if any(stream['codec_type'] == 'subtitle' for stream in audio_streams):
                raise ValueError(f"{row['id']}: audio source contains soft subtitles. This tool supports video + AAC only; use a subtitle-preserving workflow instead.")
            sound = single_stream(audio_streams, 'audio')
            if sound.get('codec_name') != 'aac' or not sound.get('extradata_size'):
                raise ValueError('Use AAC in M4A/MP4 with codec configuration; raw ADTS/WAV are not supported')
            sample_rate = int(sound['sample_rate'])
            if sample_rate <= 0:
                raise ValueError('AAC sample rate must be positive')
            tolerance = 2048 / sample_rate  # At most two AAC packets of codec/container rounding.
            if abs(finite(sound, 'start_time')) > max(1e-6, 1 / sample_rate):
                raise ValueError(f"{row['id']}: audio must start at zero; align it separately")
            if abs(finite(sound, 'duration') - duration) > tolerance:
                raise ValueError(f"{row['id']}: audio/video duration mismatch; no automatic trim or pad")
            prepared.append({'id': row['id'], 'audio': audio, 'output': target,
                             'audioSha256': sha256(audio), 'audioStreamHash': stream_hash(audio, '0:a:0', ffmpeg),
                             'durationToleranceSeconds': tolerance})
        if outputs & inputs or (args.report and args.report.resolve() in outputs | inputs):
            raise ValueError('Outputs/report cannot replace an input or each other')
        for item in prepared:
            target = item['output']
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix='.mux-', suffix='.mp4', dir=target.parent)
            os.close(descriptor)
            temporary = Path(temporary_name)
            staged.append(temporary)
            run([ffmpeg, '-v', 'error', '-y', '-i', str(picture), '-i', str(item['audio']),
                 '-map', '0:v:0', '-map', '1:a:0', '-map_metadata', '-1',
                 '-c:v', 'copy', '-c:a', 'copy', '-movflags', '+faststart', str(temporary)])
            streams = probe(temporary, ffprobe, count=True)
            out_video, out_audio = single_stream(streams, 'video'), single_stream(streams, 'audio')
            checks = {
                'onlyVideoAndAudio': len(streams) == 2,
                'sameVideoPackets': stream_hash(temporary, '0:v:0', ffmpeg) == video_hash,
                'sameAudioPackets': stream_hash(temporary, '0:a:0', ffmpeg) == item['audioStreamHash'],
                'sameDecodedFrameCount': int(out_video.get('nb_read_frames', -1)) == frames,
                'videoDurationPreserved': abs(finite(out_video, 'duration') - duration) < 1e-5,
                'videoStartPreserved': abs(finite(out_video, 'start_time') - start) < 1e-5,
                'audioAligned': abs(finite(out_audio, 'start_time')) <= 1e-5 and
                    abs(finite(out_audio, 'duration') - duration) <= item['durationToleranceSeconds'],
            }
            if not all(checks.values()):
                raise ValueError(f"{item['id']}: output validation failed: {checks}")
            item.update(temporary=temporary, checks=checks, sha256=sha256(temporary))
        if sha256(picture) != picture_sha or any(sha256(item['audio']) != item['audioSha256'] for item in prepared):
            raise ValueError('An input changed during export')
        # Hard-link within the same directory: publish atomically without replacing a concurrent file.
        for item in prepared:
            os.link(item['temporary'], item['output'])
            published.append(item['output'])
        report = {'schemaVersion': 1, 'passed': True, 'picture': str(picture),
                  'pictureSha256': picture_sha, 'videoStreamHash': video_hash,
                  'frames': frames, 'durationSeconds': duration, 'audioMode': 'AAC stream copy',
                  'variants': [{key: str(value) if isinstance(value, Path) else value
                                for key, value in item.items() if key != 'temporary'} for item in prepared]}
        payload = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.report:
            with args.report.open('x', encoding='utf-8') as output:
                output.write(payload)
        else:
            print(payload, end='')
    except (ValueError, OSError, KeyError, TypeError, ZeroDivisionError) as error:
        # These paths were created by this invocation only; original media is never removed.
        for target in published:
            target.unlink(missing_ok=True)
        parser.error(str(error))
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
