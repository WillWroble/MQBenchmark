"""Writes web/levels.json: the dev set plus a few generated levels from each tier."""
import json
from pathlib import Path

from mqbench.engine import Level
from mqbench.generator import TIERS, generate
from mqbench.solver import solve

ROOT = Path(__file__).parent.parent
TYPES = {'2 clones': (2, 0), '3 clones': (3, 0), '2 clones, sliders': (2, 2)}

levels = [{'group': 'Original levels', 'name': f'Level {int(p.stem)}', 'text': p.read_text().strip(),
           'minimum': len(solve(Level(p.read_text())))}
          for p in sorted((ROOT / 'levels' / 'dev').glob('*.txt'), key=lambda p: (p.stem == '00', p.stem))]
for kind, (clones, sliders) in TYPES.items():
    for tier in TIERS:
        for seed in range(3):
            text, solution = generate(seed, tier, clones, sliders)
            levels.append({'group': f'Generated: {kind}', 'name': f'{tier.capitalize()} · seed {seed}',
                           'text': text, 'minimum': len(solution)})
(ROOT / 'web' / 'levels.json').write_text(json.dumps(levels, indent=1) + '\n')
