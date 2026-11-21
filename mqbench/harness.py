"""Runs models on Mirror Quest levels through OpenRouter, logging every call.

Usage: python -m mqbench.harness MODEL [--mode one-shot|interactive] [--set scored|dev]
       [--seed N] [--per-kind N] [--kinds 2-0 3-0 ...] [--workers N] [--out FILE]

Each level becomes one JSON line in the output file, with the full conversation, every
call's tokens, time and cost, and the result. A rerun skips levels already in the file.
"""
import argparse
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .engine import CLONES, DRAIN, EXIT, GOAL, SMOOTH, TELEPORTER, Level
from .session import Session
from .solver import solve

ROOT = Path(__file__).parent
LEVELS = ROOT.parent / 'levels'
TEXT = {p.stem: p.read_text().strip() for p in [ROOT / 'rules.txt', *(ROOT / 'prompts').glob('*.txt')]}
BUDGET = 2  # a level counts as solved within BUDGET × its minimum moves
CAP = 5  # interactive mode stops after CAP × the minimum actions, undos and resets included
TILE_NAMES = {GOAL: 'a goal', SMOOTH: 'smooth floor', TELEPORTER: 'a teleporter', EXIT: 'an exit-only teleporter', DRAIN: 'a drain'}


def board_text(level, state):
    """The board as a character grid, plus a line for each hidden square that matters."""
    notes = [f'{k} is on {TILE_NAMES[level.tile(p)]}.' for k, p in zip(CLONES, state[0]) if level.tile(p) in TILE_NAMES]
    notes += [f'The slider in row {r + 1}, column {c + 1} is on {TILE_NAMES[level.tile((r, c))]}.'
              for r, c in sorted(state[1]) if level.tile((r, c)) != SMOOTH]
    return '\n'.join([level.render(state), *notes])


def prompt(mode, level):
    return TEXT[mode.replace('-', '_')].format(rules=TEXT['rules'], legend=TEXT['legend'], board=board_text(level, level.start))


def last_match(pattern, text):
    matches = re.findall(pattern, text or '', re.IGNORECASE | re.MULTILINE)
    return matches[-1] if matches else None


def openrouter(model):
    """A client that sends a conversation to a model and returns its reply and the call's log entry."""
    def complete(messages):
        body = json.dumps({'model': model, 'messages': messages, 'usage': {'include': True}}).encode()
        request = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', body, {
            'Content-Type': 'application/json', 'Authorization': f'Bearer {os.environ.get("OPENROUTER_API_KEY", "proxy")}'})
        for wait in [5, 15, 60, 120, None]:
            start = time.time()
            try:
                with urllib.request.urlopen(request, timeout=1800) as response:
                    data = json.load(response)
                break
            except (urllib.error.URLError, TimeoutError) as error:
                if wait is None or getattr(error, 'code', 500) not in (408, 429, 500, 502, 503, 504):
                    raise
                time.sleep(wait)
        if 'choices' not in data:
            raise RuntimeError(data.get('error', data))
        message = data['choices'][0]['message']
        usage = data.get('usage', {})
        return message.get('content') or '', {
            'seconds': round(time.time() - start, 2),
            'input_tokens': usage.get('prompt_tokens'),
            'output_tokens': usage.get('completion_tokens'),
            'reasoning_tokens': (usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),
            'cost': usage.get('cost'),
            'provider': data.get('provider'),
            'reasoning': message.get('reasoning'),
            'finish_reason': data['choices'][0].get('finish_reason'),
        }
    return complete


def play(complete, mode, level, minimum):
    """Plays one level. Returns the conversation, the log of every call, the finished session and the submitted moves."""
    session = Session(level)
    messages = [{'role': 'user', 'content': prompt(mode, level)}]
    calls = []
    while True:
        reply, call = complete(messages)
        calls.append(call)
        messages.append({'role': 'assistant', 'content': reply})
        if mode == 'one-shot':
            moves = re.sub(r'[^UDLR]', '', (last_match(r'^\W*MOVES:(.*)$', reply) or '').upper())
            for move in moves:
                session.act(move)
            return messages, calls, session, moves
        action = last_match(r'^\W*ACTION:\W*(UNDO|RESET|U|D|L|R)\b', reply)
        if action:
            moves = session.moves
            session.act(action.upper() if len(action) == 1 else action.lower())
            if session.solved:
                return messages, calls, session, None
            feedback = board_text(level, session.state) + f'\nMoves: {session.moves}'
            if action.upper() in 'UDLR' and session.moves == moves:
                feedback = 'Nothing moved.\n' + feedback
        else:
            session.actions += 1  # an unreadable reply uses up an action, so a confused model still stops
            feedback = 'Your reply didn\'t end with an action. End it with a line like ACTION: U'
        if session.actions >= CAP * minimum:
            return messages, calls, session, None
        messages.append({'role': 'user', 'content': feedback})


def run_level(complete, model, mode, level_id, text, minimum):
    messages, calls, session, moves = play(complete, mode, Level(text), minimum)
    total = lambda key: sum(c[key] or 0 for c in calls)
    return {
        'model': model, 'mode': mode, 'level': level_id, 'minimum': minimum,
        'solved': session.solved and session.moves <= BUDGET * minimum,
        'reached_goal': session.solved, 'moves': session.moves, 'total_actions': session.actions,
        'submitted': moves, 'calls': len(calls),
        'truncated': any(c['finish_reason'] == 'length' for c in calls),  # ran out of output tokens
        **{key: total(key) for key in ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cost', 'seconds']},
        'messages': messages, 'call_log': calls,
    }


def scored_set(seed, per_kind, kinds=None):
    """A seeded sample of per_kind levels from the stock for each kind of level: {id: (text, minimum)}.

    Each kind is sampled on its own, so one kind's stock growing doesn't change another's sample.
    Kinds are '<clones>-<sliders 0/1>', all by default.
    """
    levels = {}
    for path in sorted((LEVELS / 'stock').glob('*.jsonl')):
        if kinds and path.stem.split('-', 1)[1] not in kinds:
            continue
        stock = sorted((json.loads(line) for line in path.read_text().splitlines()), key=lambda lv: lv['seed'])
        rng = random.Random(f'{seed}-{path.stem}')
        for level in sorted(rng.sample(stock, min(per_kind, len(stock))), key=lambda lv: lv['seed']):
            levels[f'{path.stem}-{level["seed"]}'] = level['text'], level['minimum']
    return levels


def dev_set():
    return {f'dev-{int(p.stem)}': (p.read_text(), len(solve(Level(p.read_text())))) for p in sorted((LEVELS / 'dev').glob('*.txt'))}


def main():
    parser = argparse.ArgumentParser(description='Run a model on Mirror Quest levels.')
    parser.add_argument('model', help='OpenRouter model id, for example anthropic/claude-sonnet-4.5')
    parser.add_argument('--mode', choices=['one-shot', 'interactive'], default='one-shot')
    parser.add_argument('--set', choices=['scored', 'dev'], default='scored')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--per-kind', type=int, default=10)
    parser.add_argument('--kinds', nargs='*', help='kinds of level to run, as <clones>-<sliders 0/1>; all by default')
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--out')
    args = parser.parse_args()
    levels = dev_set() if args.set == 'dev' else scored_set(args.seed, args.per_kind, args.kinds)
    name = f'{args.model.replace("/", "_")}-{args.mode}-{args.set}' + (f'-seed{args.seed}' if args.set == 'scored' else '')
    out = Path(args.out or ROOT.parent / 'results' / f'{name}.jsonl')
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)['level'] for line in out.read_text().splitlines()} if out.exists() else set()
    todo = {k: v for k, v in levels.items() if k not in done}
    complete = openrouter(args.model)

    def work(item):
        level_id, (text, minimum) = item
        try:
            record = run_level(complete, args.model, args.mode, level_id, text, minimum)
        except Exception as error:  # left out of the file, so a rerun tries the level again
            print(f'{level_id}: failed: {error}', flush=True)
            return
        with out.open('a') as f:
            f.write(json.dumps(record) + '\n')
        print(f"{record['level']}: {'solved' if record['solved'] else 'not solved'} in {record['moves']} "
              f"(minimum {record['minimum']}), {record['output_tokens']} output tokens", flush=True)

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(work, todo.items()))
    print(f'Results in {out}')


if __name__ == '__main__':
    main()
