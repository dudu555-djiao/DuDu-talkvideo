#!/usr/bin/env python3
"""Plan (never execute) partial renders around edits in a zero-start CFR video.

Keyframe flags provide candidate splice boundaries, not proof of closed GOPs.
The renderer must separately verify codec headers, timing, decoding and seams.
Requires Python 3.10+ and ffprobe; uses only the Python standard library.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess


def run_json(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode or proc.stderr.strip():
        raise ValueError(proc.stderr.strip()[-3000:])
    return json.loads(proc.stdout)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{name} must be a finite number')
    return number


def inspect_video(base, ffprobe):
    info = run_json([ffprobe, '-v', 'error', '-count_frames', '-show_streams',
                     '-of', 'json', str(base)])
    videos = [stream for stream in info['streams'] if stream['codec_type'] == 'video']
    if len(videos) != 1:
        raise ValueError('Baseline must have exactly one video stream')
    video = videos[0]
    fps = Fraction(video.get('avg_frame_rate', '0/1'))
    if fps <= 0:
        raise ValueError('A positive CFR frame rate is required')
    tick = float(Fraction(video['time_base']))
    tolerance = max(1e-6, tick * 1.5)
    if abs(finite_number(video.get('start_time', 'nan'), 'video start')) > tolerance:
        raise ValueError('Baseline video must start at zero')
    frames = run_json([ffprobe, '-v', 'error', '-select_streams', 'v:0',
                       '-show_frames', '-show_entries',
                       'frame=best_effort_timestamp_time', '-of', 'json', str(base)])['frames']
    count = len(frames)
    if count < 1 or int(video.get('nb_read_frames', -1)) != count:
        raise ValueError('Decoded frame count is unavailable or inconsistent')
    if video.get('nb_frames') not in (None, 'N/A') and int(video['nb_frames']) != count:
        raise ValueError('Container and decoded frame counts differ')
    for i, frame in enumerate(frames):
        timestamp = finite_number(frame.get('best_effort_timestamp_time', 'nan'), 'frame PTS')
        if abs(timestamp - float(i / fps)) > tolerance:
            raise ValueError(f'Non-CFR or discontinuous timestamps at frame {i}; normalize separately')
    duration = float(count / fps)
    if abs(finite_number(video.get('duration', 'nan'), 'video duration') - duration) > tolerance:
        raise ValueError('Video duration does not match the decoded CFR frame count')
    packets = run_json([ffprobe, '-v', 'error', '-select_streams', 'v:0',
                        '-show_packets', '-show_entries', 'packet=pts_time,flags',
                        '-of', 'json', str(base)])['packets']
    boundaries = set()
    for packet in packets:
        if 'K' not in packet.get('flags', ''):
            continue
        timestamp = finite_number(packet.get('pts_time', 'nan'), 'keyframe PTS')
        frame = round(timestamp * float(fps))
        if not 0 <= frame < count or abs(timestamp - float(frame / fps)) > tolerance:
            raise ValueError('A keyframe timestamp is outside the CFR frame grid')
        boundaries.add(frame)
    if 0 not in boundaries:
        raise ValueError('First frame must be a marked keyframe')
    return video, fps, count, sorted(boundaries | {count})


def make_plan(base, requested, handle, ffprobe):
    handle = finite_number(handle, 'handle')
    if handle < 0:
        raise ValueError('handle cannot be negative')
    if not isinstance(requested, list) or not requested:
        raise ValueError('Provide at least one edit range')
    normalized = []
    for row in requested:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError('Each range must be [start_seconds, end_seconds]')
        start, end = [finite_number(value, 'range time') for value in row]
        if start < 0 or end <= start:
            raise ValueError('Each range must satisfy 0 <= start < end')
        normalized.append((start, end))
    base_hash = sha256(base)
    video, fps, total, boundaries = inspect_video(base, ffprobe)
    if sha256(base) != base_hash:
        raise ValueError('Baseline changed during inspection; use an immutable finished render')
    duration = float(total / fps)
    padded = []
    expanded = []
    for start, end in sorted(normalized):
        if end > duration + 1e-6:
            raise ValueError(f'Edit ends after video duration {duration:.9f}')
        first = max(0, math.floor((start - handle) * float(fps) + 1e-7))
        last = min(total, math.ceil((end + handle) * float(fps) - 1e-7))
        lower = max(frame for frame in boundaries if frame <= first)
        upper = min(frame for frame in boundaries if frame >= last)
        padded.append({'seconds': [start, end], 'withHandlesFrames': [first, last],
                       'candidateBoundaryFrames': [lower, upper]})
        if expanded and lower <= expanded[-1][1]:
            expanded[-1][1] = max(upper, expanded[-1][1])
        else:
            expanded.append([lower, upper])
    pieces = []
    position = 0
    for first, last in expanded:
        if first > position:
            pieces.append({'kind': 'copy-candidate', 'startFrame': position, 'endFrame': first})
        pieces.append({'kind': 'render', 'startFrame': first, 'endFrame': last})
        position = last
    if position < total:
        pieces.append({'kind': 'copy-candidate', 'startFrame': position, 'endFrame': total})
    for piece in pieces:
        piece.update(frames=piece['endFrame'] - piece['startFrame'],
                     startSeconds=float(piece['startFrame'] / fps),
                     endSeconds=float(piece['endFrame'] / fps))
    rendered = sum(piece['frames'] for piece in pieces if piece['kind'] == 'render')
    return {'schemaVersion': 1, 'planOnly': True, 'spliceSafetyVerified': False,
            'base': str(base.resolve()), 'baseSha256': base_hash,
            'fps': str(fps), 'totalFrames': total, 'durationSeconds': duration,
            'handleSeconds': handle, 'frameRangeConvention': '[startFrame, endFrame)',
            'baselineVideo': {key: video.get(key) for key in
                              ('codec_name', 'width', 'height', 'pix_fmt', 'time_base',
                               'color_range', 'color_space', 'color_transfer', 'color_primaries')},
            'edits': padded, 'candidateRenderRanges': expanded, 'pieces': pieces,
            'renderFrames': rendered, 'copyCandidateFrames': total - rendered,
            'requiredBeforeSplicing': [
                'Verify marked boundaries are independent closed GOPs; keyframe flags alone do not prove this.',
                'Match codec configuration (including SPS/PPS where applicable), pixel format, color and time base.',
                'Render with absolute episode times and preserve the full narration timeline.',
                'Check decoded total frame count, A/V start and duration, every seam, and copied-frame hashes.',
                'If any check fails, expand the render range or use a verified full render.'],
            'audioPolicy': 'This planner never changes, copies or encodes audio.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', type=Path, help='Existing zero-start CFR video')
    parser.add_argument('--range', dest='ranges', action='append', default=[], metavar='START:END',
                        help='Changed time interval in seconds; repeat as needed')
    parser.add_argument('--ranges-json', type=Path, help='JSON list of [start,end] pairs, or {"ranges": [...]}')
    parser.add_argument('--handle', default='2', help='Context seconds on each side (default: 2)')
    parser.add_argument('--ffprobe', default='ffprobe', help='Executable name or path')
    parser.add_argument('--output', type=Path, help='New plan JSON file; default prints to stdout')
    args = parser.parse_args()
    try:
        binary = shutil.which(args.ffprobe)
        if not binary:
            raise ValueError('ffprobe was not found; install FFmpeg or pass --ffprobe')
        if not args.base.is_file():
            raise ValueError('Baseline file does not exist')
        if args.output and args.output.exists():
            raise ValueError('Output already exists; choose a new plan path')
        ranges = [value.split(':') for value in args.ranges]
        if args.ranges_json:
            data = json.loads(args.ranges_json.read_text(encoding='utf-8'))
            data = data.get('ranges') if isinstance(data, dict) else data
            if not isinstance(data, list):
                raise ValueError('ranges JSON must contain a list')
            ranges.extend(data)
        plan = make_plan(args.base, ranges, args.handle, binary)
        payload = json.dumps(plan, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as output:
                output.write(payload)
        else:
            print(payload, end='')
    except (ValueError, OSError, KeyError, TypeError, ZeroDivisionError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
