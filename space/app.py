"""The Mirror Quest Space: serves the game, records human games and computes the leaderboard."""
import json
import os
import random
import time
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from huggingface_hub import CommitScheduler, snapshot_download
from pydantic import BaseModel

from mqbench.engine import Level
from mqbench.generator import TIERS, generate
from mqbench.session import Session
from mqbench.solver import solve

ROOT = Path(__file__).parent.parent
DEV = {int(p.stem): p.read_text() for p in (ROOT / 'levels' / 'dev').glob('*.txt')}
PLAYS_REPO = 'inkling616/mqbench-human-plays'
SLIDERS = 2  # sliders in a level of the sliders tier
ACTIONS = {'U', 'D', 'L', 'R', 'undo', 'reset'}

DATA = ROOT / 'data'
OUTBOX = DATA / 'plays'
OUTBOX.mkdir(parents=True, exist_ok=True)
outbox = OUTBOX / f'{uuid.uuid4()}.jsonl'
token = os.environ.get('HF_TOKEN')
scheduler = None
if token:
    snapshot_download(PLAYS_REPO, repo_type='dataset', local_dir=DATA / 'saved', token=token)
    scheduler = CommitScheduler(repo_id=PLAYS_REPO, repo_type='dataset', folder_path=OUTBOX,
                                path_in_repo='plays', every=5, token=token)
plays = [json.loads(line) for f in DATA.glob('*/plays/*.jsonl') for line in f.read_text().splitlines()]

app = FastAPI()


@lru_cache(maxsize=1024)
def load(id_):
    """Level ids are 'dev-<number>' or '<tier>-<clones>-<sliders 0/1>-<seed>'."""
    try:
        if id_.startswith('dev-'):
            text = DEV[int(id_[4:])]
            return text, len(solve(Level(text)))
        tier, clones, sliders, seed = id_.split('-')
        if tier not in TIERS or clones not in ('2', '3') or sliders not in ('0', '1'):
            raise ValueError
        text, solution = generate(int(seed), tier, int(clones), SLIDERS * int(sliders))
        return text, len(solution)
    except (KeyError, ValueError):
        raise HTTPException(404, f'No level {id_}')


@app.get('/api/rules', response_class=PlainTextResponse)
def rules():
    return (ROOT / 'mqbench' / 'rules.txt').read_text()


@app.get('/api/levels/new')
def new_level(tier: str, clones: int, sliders: bool):
    id_ = f'{tier}-{clones}-{int(sliders)}-{random.randrange(2 ** 31)}'
    return {'id': id_, 'text': load(id_)[0]}


@app.get('/api/levels/{id_}')
def get_level(id_: str):
    return {'id': id_, 'text': load(id_)[0]}


class Action(BaseModel):
    a: str
    t: int  # milliseconds since the level appeared


class Play(BaseModel):
    level: str
    player: str
    actions: list[Action]


@app.post('/api/plays')
def record(play: Play):
    """Replays a finished or abandoned game on the server, stores it and returns the result."""
    if not play.actions or any(x.a not in ACTIONS for x in play.actions):
        raise HTTPException(400, 'Invalid actions')
    text, minimum = load(play.level)
    session = Session(Level(text))
    for x in play.actions:
        session.act(x.a)
    result = {'solved': session.solved, 'moves': session.moves, 'minimum': minimum}
    row = {**play.model_dump(), **result, 'total_actions': session.actions,
           'time_ms': play.actions[-1].t, 'recorded_at': int(time.time())}
    plays.append(row)
    if scheduler:
        with scheduler.lock, outbox.open('a') as f:
            f.write(json.dumps(row) + '\n')
    return result


@app.get('/api/leaderboard')
def leaderboard():
    """Human baseline for each kind of benchmark level: solve rate, and moves over the minimum when solved."""
    groups = {}
    for p in plays:
        if not p['level'].startswith('dev-'):
            tier, clones, sliders, _ = p['level'].split('-')
            groups.setdefault((tier, clones, sliders), []).append(p)
    humans = []
    for (tier, clones, sliders), ps in sorted(groups.items(), key=lambda g: (g[0][1], g[0][2], list(TIERS).index(g[0][0]))):
        solved = [p for p in ps if p['solved']]
        humans.append({'tier': tier, 'clones': int(clones), 'sliders': sliders == '1', 'games': len(ps),
                       'solve_rate': len(solved) / len(ps),
                       'moves_over_minimum': sum(p['moves'] / p['minimum'] for p in solved) / len(solved) if solved else None})
    return {'humans': humans, 'models': []}


app.mount('/', StaticFiles(directory=ROOT / 'web', html=True))
