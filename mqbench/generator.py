"""Seeded level generator.

A random island of floor is explored exhaustively, and the goals go on squares the clones
can reach together in a number of moves within the tier, so every level is solvable and
its minimum is exact.
"""
import random

from .engine import CLONES, DIRECTIONS, FLOOR, GOAL, SLIDER, SMOOTH, VOID, WALL, Level, add
from .solver import path, search

TIERS = {'easy': (6, 12), 'medium': (13, 24), 'hard': (25, 40)}


def generate(seed, tier, clones=2, sliders=0, rows=10, cols=7, land=0.55, wall=0.15):
    """Returns (level text, shortest solution)."""
    lo, hi = TIERS[tier]
    rng = random.Random(f'{seed}-{tier}-{clones}-{sliders}')
    while True:
        board = random_board(rng, clones, sliders, rows, cols, land, wall)
        if board is None:
            continue
        level = Level(board)
        parents = search(level)
        depth, candidates = {}, {}  # candidates: set of clone squares -> first state reaching it
        for state, parent in parents.items():
            depth[state] = depth[parent[0]] + 1 if parent else 0
            squares = frozenset(state[0])
            if all(level.tile(p) == FLOOR for p in squares) and not squares & set(level.start[0]):
                candidates.setdefault(squares, state)
        in_tier = [s for s in candidates.values() if lo <= depth[s] <= hi]
        if in_tier:
            state = rng.choice(in_tier)
            return place_goals(board, state[0]), path(parents, state)


def random_board(rng, clones, sliders, rows, cols, land, wall):
    """Grows one connected island of floor out of the void, then scatters walls on it."""
    grid = [[VOID] * cols for _ in range(rows)]
    island = [(rng.randrange(rows), rng.randrange(cols))]
    while len(island) < land * rows * cols:
        r, c = add(rng.choice(island), rng.choice(list(DIRECTIONS.values())))
        if 0 <= r < rows and 0 <= c < cols and (r, c) not in island:
            island.append((r, c))
    for r, c in island:
        grid[r][c] = WALL if rng.random() < wall else FLOOR
    if sliders:
        r0, c0 = rng.choice(island)
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
