from pathlib import Path

import pytest

from mqbench.engine import Level
from mqbench.generator import generate
from mqbench.solver import solve

DEV = Path(__file__).parent.parent / 'levels' / 'dev'


def play(board, moves):
    level = Level(board)
    state = level.start
    for move in moves:
        state = level.step(state, move)
    return level.render(state)


@pytest.mark.parametrize('board, moves, expected', [
    # A wall stops one clone while the other moves.
    ('#..\nA.B', 'U', '#.B\nA..'),
    # Anything falling into the void cancels the whole move.
    ('...\nA.B\n__.', 'D', '...\nA.B\n__.'),
    # Moving into a clone that is blocked cancels the move.
    ('AB#', 'R', 'AB#'),
    # Clones in a line move together.
    ('AB.', 'R', '.AB'),
    # Sliders are pushed in chains along smooth floor.
    ('ASS~', 'R', '.ASS'),
    # Sliders don't move onto plain floor, so the pusher is blocked.
    ('AS.', 'R', 'AS.'),
    # Pushing a slider into the void cancels the move.
    ('AS_\n.B.', 'R', 'AS_\n.B.'),
    # A clone on a drain can't move...
    ('AD.\nB#.', 'RR', '.A.\nB#.'),
    # ...but is pushed by another clone.
    ('ABD..', 'RR', '..AB.'),
    # Entering a teleporter comes out of its partner.
    ('AT..T.\n.B....', 'R', '.T..A.\n..B...'),
    # If coming out would collide, the clone stops on the entry teleporter instead.
    ('AT.\n.Bt', 'R', '.A.\n..B'),
])
def test_rules(board, moves, expected):
    assert play(board, moves) == expected


def test_level_7_minimum():
    assert len(solve(Level((DEV / '07.txt').read_text()))) == 20


@pytest.mark.parametrize('path', sorted(DEV.glob('*.txt')), ids=lambda p: p.stem)
def test_dev_solutions_replay(path):
    level = Level(path.read_text())
    state = level.start
    for move in solve(level):
        state = level.step(state, move)
    assert level.solved(state)


@pytest.mark.parametrize('clones, sliders', [(2, 0), (3, 0), (2, 2)])
def test_generated_minimum_is_exact(clones, sliders):
    for seed in range(5):
        text, solution = generate(seed, clones, sliders)
        assert len(solve(Level(text))) == len(solution)
