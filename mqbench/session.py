class Session:
    """A game in progress, with a human player's controls: moves, undo and reset.

    As in the game, moves that change nothing aren't counted, undo takes a move back off
    the count, and reset starts the count over. Every action counts toward `actions`.
    """

    def __init__(self, level):
        self.level = level
        self.history = [level.start]
        self.actions = 0

    @property
    def state(self):
        return self.history[-1]

    @property
    def moves(self):
        return len(self.history) - 1

    @property
    def solved(self):
        return self.level.solved(self.state)

    def act(self, action):
        self.actions += 1
        if action == 'undo':
            if self.moves:
                self.history.pop()
        elif action == 'reset':
            self.history = [self.level.start]
        elif not self.solved:
            state = self.level.step(self.state, action)
            if state != self.state:
                self.history.append(state)
