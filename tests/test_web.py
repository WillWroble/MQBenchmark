"""The web engine must match the Python engine move for move."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from mqbench.engine import DIRECTIONS, Level
from mqbench.generator import generate

ROOT = Path(__file__).parent.parent
REPLAY = """
const { Level } = require(process.argv[1]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
console.log(JSON.stringify(cases.map(({ text, moves }) => {
  const level = new Level(text);
  let state = level.start;
  return [...moves].map(m => {
    state = level.step(state, m);
    return [state.clones, [...state.sliders].sort()];
  });
})));
"""


def as_keys(state):
    key = lambda p: f'{p[0]},{p[1]}'
    return [list(map(key, state[0])), sorted(map(key, state[1]))]


@pytest.mark.skipif(not shutil.which('node'), reason='needs node')
def test_web_engine_matches_python():
    rng = random.Random(0)
    texts = [p.read_text() for p in sorted((ROOT / 'levels' / 'dev').glob('*.txt'))]
    texts += [generate(seed, 'medium', clones, sliders)[0] for seed in range(3) for clones, sliders in [(2, 0), (3, 0), (2, 2)]]
    cases, expected = [], []
    for text in texts:
        for _ in range(10):
            moves = ''.join(rng.choices(list(DIRECTIONS), k=60))
            level, states = Level(text), []
            state = level.start
            for move in moves:
                state = level.step(state, move)
                states.append(as_keys(state))
            cases.append({'text': text, 'moves': moves})
            expected.append(states)
    out = subprocess.run(['node', '-e', REPLAY, str(ROOT / 'web' / 'engine.js')],
                         input=json.dumps(cases), capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == expected
