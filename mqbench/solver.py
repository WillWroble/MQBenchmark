from collections import deque

from .engine import DIRECTIONS


def search(level, stop=lambda state: False):
    """Breadth-first search from the start. Returns {state: (previous state, move)}, ending early at a stop state."""
    parents = {level.start: None}
    queue = deque([level.start])
    while queue:
        state = queue.popleft()
        if stop(state):
            break
        for move in DIRECTIONS:
            nxt = level.step(state, move)
            if nxt not in parents:
                parents[nxt] = state, move
                queue.append(nxt)
    return parents


def path(parents, state):
    moves = []
    while parents[state]:
        state, move = parents[state]
        moves.append(move)
    return ''.join(reversed(moves))


def solve(level):
    """Returns a shortest solution as a move string, or None if the level is unsolvable."""
    parents = search(level, level.solved)
    return next((path(parents, s) for s in parents if level.solved(s)), None)
