from collections import deque

from .engine import DIRECTIONS


def solve(level):
    """Breadth-first search for a shortest solution. Returns a move string, or None if unsolvable."""
    parents = {level.start: None}
    queue = deque([level.start])
    while queue:
        state = queue.popleft()
        if level.solved(state):
            moves = []
            while parents[state]:
                state, move = parents[state]
                moves.append(move)
            return ''.join(reversed(moves))
        for move in DIRECTIONS:
            nxt = level.step(state, move)
            if nxt not in parents:
                parents[nxt] = state, move
                queue.append(nxt)
    return None
