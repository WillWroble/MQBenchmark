"""Seeded level generator.

Random boards are explored exhaustively, and the goals go on squares the clones can reach
together in a number of moves within the tier, so every level is solvable and its minimum
is exact. Of several such boards, the one with the most reachable states is kept, since a
bigger search space makes the route less obvious.
"""
import random

from .engine import CLONES, FLOOR, GOAL, SLIDER, SMOOTH, VOID, WALL, Level
from .solver import path, search

TIERS = {'easy': (6, 12), 'medium': (13, 24), 'hard': (25, 40)}
SLIDERS = 2  # sliders in a level of the sliders tier


def generate(seed, tier, clones=2, sliders=0, rows=10, cols=7, candidates=10):
    """Returns (level text, shortest solution) for the best of `candidates` boards."""
    lo, hi = TIERS[tier]
    rng = random.Random(f'{seed}-{tier}-{clones}-{sliders}')
    best, found = None, 0
    while found < candidates:
        board = random_board(rng, clones, sliders, rows, cols)
        if board is None:
            continue
        level = Level(board)
        parents = search(level)
        depth, goals = {}, {}  # goals: set of clone squares -> first state reaching it
        for state, parent in parents.items():
            depth[state] = depth[parent[0]] + 1 if parent else 0
            squares = frozenset(state[0])
            if all(level.tile(p) == FLOOR for p in squares) and not squares & set(level.start[0]):
                goals.setdefault(squares, state)
        in_tier = [s for s in goals.values() if lo <= depth[s] <= hi]
        if in_tier:
            found += 1
            if best is None or len(parents) > best[0]:
                state = rng.choice(in_tier)
                best = len(parents), place_goals(board, state[0]), path(parents, state)
    return best[1:]


def random_board(rng, clones, sliders, rows, cols):
    """A full board with ragged void edges, like the original levels, and a few random walls and holes."""
    grid = [[FLOOR] * cols for _ in range(rows)]
    for row in grid:
        for c in (0, cols - 1):
            if rng.random() < 0.7:
                row[c] = VOID
    for _ in range(rng.randint(5, 9)):
        grid[rng.randrange(rows)][rng.randrange(cols)] = rng.choice([WALL, WALL, VOID])
    if sliders:
        r0, c0 = rng.randrange(rows), rng.randrange(cols)
        patch = [(r, c) for r in range(r0, min(r0 + rng.randint(2, 4), rows))
                 for c in range(c0, min(c0 + rng.randint(2, 4), cols))]
        if len(patch) <= sliders:
            return None
        for r, c in patch:
            grid[r][c] = SMOOTH
        for r, c in rng.sample(patch, sliders):
            grid[r][c] = SLIDER
    floor = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == FLOOR]
    if len(floor) < 2 * clones:
        return None
    for k, (r, c) in zip(CLONES, rng.sample(floor, clones)):
        grid[r][c] = k
    return trim(grid)


def place_goals(board, squares):
    grid = [list(row) for row in board.split()]
    for r, c in squares:
        grid[r][c] = GOAL
    return '\n'.join(''.join(row) for row in grid)


def trim(grid):
    """Drops rows and columns of void from the edges."""
    keep = lambda line: any(ch != VOID for ch in line)
    rows = [r for r, row in enumerate(grid) if keep(row)]
    cols = [c for c in range(len(grid[0])) if keep([row[c] for row in grid])]
    return '\n'.join(''.join(grid[r][cols[0]:cols[-1] + 1]) for r in range(rows[0], rows[-1] + 1))
