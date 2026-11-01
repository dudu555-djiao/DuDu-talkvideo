#!/usr/bin/env python3
"""Check the public asset boundary and theme resources without external requests."""
from pathlib import Path
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def main():
    themes=json.loads((ROOT/'brand/themes.json').read_text())
    runtime=(ROOT/'runtime/themes.js').read_text()
    assert json.loads(runtime.removeprefix('window.PUBLIC_THEMES=').strip().removesuffix(';'))==themes
    default=json.loads((ROOT/'brand/style-lock.json').read_text())
    assert default['theme']=='mint' and default['mascot']=='block'
    assert default['version']=='1.4.0'
    expected={f'{kind}-{theme}-{state}.svg' for kind in ['block','bird','orbit'] for theme in themes for state in ['closed','small','wide']}
    actual={p.name for p in (ROOT/'assets/mascots').glob('*.svg')}
    assert actual==expected,(actual-expected,expected-actual)
    for p in (ROOT/'assets').rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT/'assets')
        assert rel.parts[0] in {'fonts','mascots'},rel
        if p.suffix=='.svg':
            tree=ET.parse(p)
            assert not tree.findall('.//{http://www.w3.org/2000/svg}image'),rel
            assert 'data:image' not in p.read_text(),rel
    tracked=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    forbidden=[]
    for name in tracked:
        if name=='.env' or (name.startswith('.env.') and name!='.env.example'):forbidden.append(name)
        if name.endswith(('.png','.jpg','.jpeg','.webp','.mp4','.zip')):
            if not (name=='docs/public-templates.png' or name.startswith('examples/public-templates/')):forbidden.append(name)
    assert not forbidden,forbidden
    print(json.dumps({'passed':True,'themes':len(themes),'mascotSvgCount':len(actual),'default':'mint/block','embeddedRasterAssets':0},ensure_ascii=False))


if __name__=='__main__':main()
