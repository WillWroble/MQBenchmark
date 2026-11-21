"""The Mirror Quest Space: serves the game, records human games and computes the leaderboard."""
import json
import os
import random
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from huggingface_hub import CommitScheduler, snapshot_download
from pydantic import BaseModel

from mqbench.engine import Level
from mqbench.generator import TIERS
from mqbench.session import Session
from mqbench.solver import solve

ROOT = Path(__file__).parent.parent
PLAYS_REPO = 'inkling616/mqbench-human-plays'
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

# Level ids are 'dev-<number>' for the original levels, and '<tier>-<clones>-<sliders 0/1>-<seed>'
# for generated levels, which come from the stock made by scripts/grow_stock.py.
LEVELS = {}  # level id -> (text, minimum)
STOCK = {}  # kind of level -> ids
for p in (ROOT / 'levels' / 'dev').glob('*.txt'):
    LEVELS[f'dev-{int(p.stem)}'] = p.read_text(), len(solve(Level(p.read_text())))
for p in (ROOT / 'levels' / 'stock').glob('*.jsonl'):
    for level in map(json.loads, p.read_text().splitlines()):
        LEVELS[f'{p.stem}-{level["seed"]}'] = level['text'], level['minimum']
        STOCK.setdefault(p.stem, []).append(f'{p.stem}-{level["seed"]}')

app = FastAPI()


def load(id_):
    if id_ not in LEVELS:
        raise HTTPException(404, f'No level {id_}')
    return LEVELS[id_]


@app.get('/api/rules', response_class=PlainTextResponse)
def rules():
    return (ROOT / 'mqbench' / 'rules.txt').read_text()


@app.get('/api/levels/new')
def new_level(tier: str, clones: int, sliders: bool):
    ids = STOCK.get(f'{tier}-{clones}-{int(sliders)}')
    if not ids:
        raise HTTPException(404, 'No levels of this kind yet')
    id_ = random.choice(ids)
    return {'id': id_, 'text': LEVELS[id_][0]}


@app.get('/api/levels/{id_}')
def get_level(id_: str):
    return {'id': id_, 'text': load(id_)[0]}


class Action(BaseModel):
    a: str
    t: int  # milliseconds since the level appeared


class Play(BaseModel):
    level: str
    player: str
    attempt: int = 1  # retries of a solved level count up from 1
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
    """Human baseline for each kind of benchmark level: solve rate, and moves over the minimum when solved.

    Only first attempts count, since a retry comes after seeing the minimum.
    """
    groups = {}
    for p in plays:
        if not p['level'].startswith('dev-') and p.get('attempt', 1) == 1:
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
