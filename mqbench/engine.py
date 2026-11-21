"""Mirror Quest rules, ported from CloneManager2.cs and extended to N clones.

Every move pushes all clones one step in the same direction. A clone that hits a wall stays
put. Sliders are pushed in chains, but only onto smooth floor, teleporters or drains. If
anything would fall into the void, or two objects would end on the same square, the whole
move is cancelled. A clone on a drain is disabled: it can't move, but can be pushed. Anything
entering a teleporter comes out of its partner. The level is solved when every clone is on
a goal.
"""

VOID, FLOOR, WALL, GOAL, SMOOTH, TELEPORTER, EXIT, DRAIN, SLIDER = '_.#G~TtDS'
CLONES = 'ABC'
SLIDES = {VOID, SMOOTH, TELEPORTER, EXIT, DRAIN}
DIRECTIONS = {'U': (-1, 0), 'D': (1, 0), 'L': (0, -1), 'R': (0, 1)}
BLOCKED, FALLS = 'blocked', 'falls'


def add(p, d):
    return p[0] + d[0], p[1] + d[1]


class Level:
    def __init__(self, text):
        rows = text.split()
        self.tiles, clones, sliders = {}, {}, set()
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch in CLONES:
                    clones[ch], ch = (r, c), FLOOR
                elif ch == SLIDER:
                    sliders.add((r, c))
                    ch = SMOOTH
                self.tiles[r, c] = ch
        self.shape = len(rows), len(rows[0])
        self.teleporters = [p for p, t in self.tiles.items() if t in (TELEPORTER, EXIT)]
        self.start = tuple(clones[k] for k in sorted(clones)), frozenset(sliders)

    def tile(self, p):
        return self.tiles.get(p, VOID)

    def render(self, state):
        clones, sliders = state
        grid = [[self.tiles[r, c] for c in range(self.shape[1])] for r in range(self.shape[0])]
        for r, c in sliders:
            grid[r][c] = SLIDER
        for k, (r, c) in zip(CLONES, clones):
            grid[r][c] = k
        return '\n'.join(''.join(row) for row in grid)

    def solved(self, state):
        return all(self.tile(p) == GOAL for p in state[0])

    def step(self, state, move):
        """Returns the state after a move, or the same state if nothing moved."""
        d = DIRECTIONS[move]
        clones, sliders = state
        disabled = {i for i, p in enumerate(clones) if self.tile(p) == DRAIN}
        banned, pushed = set(), set()
        while True:
            free = set(sliders)
            moves = {}  # start square -> (end square, teleporter it depends on)
            for i in [i for i in range(len(clones)) if i not in disabled] + sorted(pushed):
                chain = self.enter(free, add(clones[i], d), d, banned)
                if chain == FALLS:
                    return state
                if chain != BLOCKED:
                    end, tag, rest = chain
                    moves[clones[i]] = end, tag
                    moves.update(rest)
            ends = {}
            for p in [*clones, *sliders]:
                ends.setdefault(moves.get(p, (p,))[0], []).append(p)
            colliding = {p for ps in ends.values() if len(ps) > 1 for p in ps}
            if not colliding:
                break
            tags = {moves[p][1] for p in colliding if p in moves and moves[p][1]}
            hit = {i for i in disabled - pushed if clones[i] in colliding}
            if tags:
                banned |= tags
            elif hit:
                pushed |= hit
            else:
                return state
        end = lambda p: moves.get(p, (p,))[0]
        return tuple(map(end, clones)), frozenset(map(end, sliders))

    def enter(self, free, p, d, banned, tag=None):
        """An object enters square p moving along d, pushing any sliders ahead of it.

        Returns BLOCKED, FALLS, or (where it ends, the teleporter that move depends on,
        {start: (end, tag)} for the sliders it pushes).
        """
        tile = self.tile(p)
        if tile == WALL:
            return BLOCKED
        if tile == VOID:
            return BLOCKED if tag else FALLS
        pushed = {}
        if p in free:
            if self.tile(add(p, d)) not in SLIDES:
                return BLOCKED
            free.remove(p)
            chain = self.enter(free, add(p, d), d, banned, tag)
            if chain in (BLOCKED, FALLS):
                free.add(p)
                return chain
            end, slider_tag, pushed = chain
            pushed[p] = end, slider_tag
        if tile == TELEPORTER and not tag and p not in banned:
            exit_ = next(q for q in self.teleporters if q != p)
            chain = self.enter(free, exit_, d, banned, p)
            if chain != BLOCKED:
                return chain[0], chain[1], {**pushed, **chain[2]}
        return p, tag, pushed

