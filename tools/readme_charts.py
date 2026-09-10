#!/usr/bin/env python3
"""Render repository charts from published verified records, with no extrapolation."""
import argparse
import html
import json
from pathlib import Path
from readme_snapshot import CONTEXTS, validated_state

ROOT = Path(__file__).resolve().parents[1]

def render(data):
    report = json.loads((data / 'cluster.json').read_text(encoding='utf-8'))
    policy = json.loads((data / 'strategy.json').read_text(encoding='utf-8'))
    total, epoch, _, _, exploration, current, history, stamp = validated_state(report, policy)
    points = [(0, 0)] + [(int(h['epoch']), int(h['through_verified_tasks'])) for h in history]
    max_x = max([p[0] for p in points] + [1])
    max_y = max([p[1] for p in points] + [1])
    weights = [float(current[context]) for context in CONTEXTS]
    max_weight = max(max(weights), 1/81) * 1.08
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="460" viewBox="0 0 1000 460" role="img" aria-labelledby="title desc">',
        '<title id="title">Verified work and the current cost allocation</title>',
        '<desc id="desc">Recorded calibration boundaries and published lane weights. These charts measure work and scheduling, not discovery probability.</desc>',
        '<rect width="1000" height="460" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111}.tick{font-size:12px;fill:#555}.grid{stroke:#ddd;stroke-width:1}</style>',
        '<text x="38" y="38" font-size="23">Math Gambling: verified work, visible decisions</text>',
        f'<text x="38" y="65" font-size="14">{total:,} unique tasks verified · policy epoch {epoch} · {html.escape(stamp)}</text>',
        '<text x="38" y="105" font-size="17">Verified task count at each frozen model epoch</text>',
        '<text x="540" y="105" font-size="17">Current allocation across 81 lanes</text>']
    for j in range(5):
        y = 340-j*50
        out += [f'<line class="grid" x1="74" y1="{y}" x2="465" y2="{y}"/>',
                f'<text class="tick" x="65" y="{y+4}" text-anchor="end">{max_y*j/4:g}</text>',
                f'<line class="grid" x1="580" y1="{y}" x2="963" y2="{y}"/>',
                f'<text class="tick" x="571" y="{y+4}" text-anchor="end">{100*max_weight*j/4:.1f}%</text>']
    coords = [(74+x/max_x*391, 340-y/max_y*200) for x,y in points]
    if len(coords)>1:
        out.append('<polyline fill="none" stroke="#111" stroke-width="2" points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in coords)+'"/>')
    for (x,y),(epoch,count) in zip(coords,points):
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#111"><title>Epoch {epoch}: {count} verified tasks</title></circle>')
    for j in range(min(max_x,4)+1):
        epoch = round(max_x*j/min(max_x,4))
        out.append(f'<text class="tick" x="{74+epoch/max_x*391:.2f}" y="362" text-anchor="middle">{epoch}</text>')
    for i,weight in enumerate(weights):
        height=weight/max_weight*200
        out.append(f'<rect x="{580+i*383/81:.2f}" y="{340-height:.2f}" width="3.5" height="{height:.2f}" fill="#111"><title>c{i:02}: {100*weight:.4f}%</title></rect>')
    uniform_y=340-(1/81)/max_weight*200
    out += [f'<line x1="580" x2="963" y1="{uniform_y:.2f}" y2="{uniform_y:.2f}" stroke="#b5222c" stroke-dasharray="4 3"/>',
        '<text class="tick" x="580" y="362">c00</text><text class="tick" x="943" y="362">c80</text>',
        '<text class="tick" x="225" y="385">Calibration epoch</text>',
        '<text class="tick" x="580" y="385">Dashed line: uniform allocation</text>',
        '<text x="38" y="428" font-size="14">40% uniform task exploration. Exploitation follows the current declared objective; no discovery advantage established.</text>', '</svg>']
    (data / 'readme-progress.svg').write_text('\n'.join(out)+'\n',encoding='utf-8')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=ROOT/'data')
    render(p.parse_args().data)
