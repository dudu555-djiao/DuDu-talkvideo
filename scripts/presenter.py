"""Per-episode presenter choice, confirmed before semantic planning."""
import json
from pathlib import Path


def require_presenter(project, board):
    path = Path(project) / 'presenter-request.json'
    if not path.exists():
        # Older approved episodes retain their existing plans and approval hashes.
        if 'presenterMode' in board:
            raise ValueError('新期缺少 presenter-request.json；先记录用户本期出镜选择。')
        return None
    choice = json.loads(path.read_text(encoding='utf-8'))
    if (choice.get('mode') not in {'ip', 'real'} or choice.get('status') != 'confirmed'
            or not str(choice.get('userStatement', '')).strip()
            or not str(choice.get('evidence', '')).strip()):
        raise ValueError('先向用户确认本期使用 IP 小人物还是真人出镜，再用 presenter 记录原话及出处；不能按素材自动选择。')
    if board.get('presenterMode') != choice['mode']:
        raise ValueError('分镜 presenterMode 与本期出镜选择不一致。')
    for shot in board.get('shots', []):
        camera = shot.get('cameraPlan')
        if not isinstance(camera, dict) or any(not str(camera.get(key, '')).strip() for key in ('subject', 'framing', 'movement', 'reason')):
            raise ValueError(shot.get('id', '?') + ' 须填写 cameraPlan：主体、景别/构图、运动和依据；静止镜头也应明确。')
        ip = shot.get('ip') or {}
        if choice['mode'] == 'real':
            if ip.get('mode') != 'hidden' or ip.get('visible', False) or ip.get('emphasis'):
                raise ValueError(shot['id'] + ' 真人模式须隐藏 IP，不能沿用 IP 出框/口型安排。')
            if shot.get('render', {}).get('type', shot.get('visual', {}).get('type')) == 'ip-scene':
                raise ValueError(shot['id'] + ' 真人模式不能使用 ip-scene；按本人原片与 B-roll 编排。')
    return choice
