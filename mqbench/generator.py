"""Seeded level generator.

A random board is explored exhaustively, and the goals go on the squares the clones take
longest to reach together, so every level is solvable and its minimum is exact.
"""
import random

from .engine import CLONES, FLOOR, GOAL, SLIDER, SMOOTH, VOID, WALL, Level
from .solver import path, search


def generate(seed, clones=2, sliders=0, rows=10, cols=7, void=0.25, wall=0.15):
    """Returns (level text, shortest solution)."""
    rng = random.Random(seed)
    while True:
        board = random_board(rng, clones, sliders, rows, cols, void, wall)
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
        if candidates:
            state = max(candidates.values(), key=depth.get)
            return place_goals(board, state[0]), path(parents, state)


def random_board(rng, clones, sliders, rows, cols, void, wall):
    grid = [[rng.choices([VOID, WALL, FLOOR], [void, wall, 1 - void - wall])[0] for _ in range(cols)]
            for _ in range(rows)]
    if sliders:
        h, w = rng.randint(2, 4), rng.randint(2, 4)
        r0, c0 = rng.randrange(rows - h + 1), rng.randrange(cols - w + 1)
        patch = [(r, c) for r in range(r0, r0 + h) for c in range(c0, c0 + w)]
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
