"""A recorded user semantic-storyboard approval is bound to the exact reviewed bytes."""
from pathlib import Path
import hashlib,json

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require_semantic(project):
    p=Path(project); source=p/'storyboard.json'; file=p/'approvals/semantic.json'
    if not source.is_file() or not file.is_file():raise ValueError('先提供语义分镜 HTML 并等待用户同意；尚无对应批准记录。')
    a=json.loads(file.read_text())
    if a.get('status')!='approved' or a.get('approvedBy')!='user' or not str(a.get('userStatement','')).strip():raise ValueError('缺少用户明确批准语义分镜的原话；助手自检或网页意见不等于批准。')
    if a.get('storyboardSha256')!=digest(source):raise ValueError('语义分镜已变更，现有批准失效；请展示新版 HTML 并等待用户同意。')
    from presenter import require_presenter
    require_presenter(p,json.loads(source.read_text()))
    return a
