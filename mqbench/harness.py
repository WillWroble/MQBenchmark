"""Runs models on Mirror Quest levels through OpenRouter, logging every call.

Usage: python -m mqbench.harness MODEL [--mode one-shot|one-shot-minimum|interactive] [--set scored|dev]
       [--seed N] [--per-kind N] [--kinds 2-0 3-0 ...] [--effort LEVEL] [--workers N] [--out FILE]

Each level becomes one JSON line in the output file, with the full conversation, every
call's tokens, time and cost, and the result. A rerun skips levels already in the file.
In one-shot-minimum mode the model is told the minimum and must solve the level in exactly that many moves.
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
MAX_TOKENS = 65536  # output limit per call, reasoning included, the same for every model
# Some providers ignore MAX_TOKENS, so a call is also cut off after TIME_LIMIT seconds: enough for
# MAX_TOKENS at 36 tokens a second, slower than any model run so far.
TIME_LIMIT = 1800
CUT_OFF = {'length', 'timeout'}
API = 'https://openrouter.ai/api/v1'
TILE_NAMES = {GOAL: 'a goal', SMOOTH: 'smooth floor', TELEPORTER: 'a teleporter', EXIT: 'an exit-only teleporter', DRAIN: 'a drain'}


def board_text(level, state):
    """The board as a character grid, plus a line for each hidden square that matters."""
    notes = [f'{k} is on {TILE_NAMES[level.tile(p)]}.' for k, p in zip(CLONES, state[0]) if level.tile(p) in TILE_NAMES]
    notes += [f'The slider in row {r + 1}, column {c + 1} is on {TILE_NAMES[level.tile((r, c))]}.'
              for r, c in sorted(state[1]) if level.tile((r, c)) != SMOOTH]
    return '\n'.join([level.render(state), *notes])


def prompt(mode, level, minimum):
    return TEXT[mode.replace('-', '_')].format(rules=TEXT['rules'], legend=TEXT['legend'], board=board_text(level, level.start),
                                               minimum=minimum)


def last_match(pattern, text):
    matches = re.findall(pattern, text or '', re.IGNORECASE | re.MULTILINE)
    return matches[-1] if matches else None


def merge(details):
    """Joins streamed reasoning fragments that continue the same part."""
    merged = []
    for d in details:
        last = merged[-1] if merged else {}
        if d.get('type') != 'reasoning.encrypted' and (last.get('type'), last.get('index')) == (d.get('type'), d.get('index')):
            for key in ['summary', 'text']:
                if d.get(key):
                    last[key] = (last.get(key) or '') + d[key]
        else:
            merged.append(dict(d))
    return merged


def stream(request, headers):
    """Reads a streamed reply in the shape of an unstreamed one, hanging up after TIME_LIMIT seconds.

    A reply that is hung up on gets finish_reason 'timeout', and its usage from OpenRouter's record of it.
    """
    start, content, reasoning, details, data, finish = time.time(), [], [], [], {}, None
    with urllib.request.urlopen(request, timeout=TIME_LIMIT) as response:
        for line in response:
            if not line.startswith(b'data: {'):
                continue
            chunk = json.loads(line[6:])
            data |= {k: v for k, v in chunk.items() if k != 'choices'}
            choice = (chunk.get('choices') or [{}])[0]
            delta = choice.get('delta') or {}
            content.append(delta.get('content') or '')
            reasoning.append(delta.get('reasoning') or '')
            details += delta.get('reasoning_details') or []
            finish = choice.get('finish_reason') or finish
            if time.time() - start > TIME_LIMIT and not finish:
                finish = 'timeout'
                break
    if not finish:
        raise ConnectionError('the stream ended before the reply did')
    if finish == 'timeout':
        for wait in [5, 15, 30, 60, 120]:  # the record appears shortly after the call ends
            time.sleep(wait)
            try:
                with urllib.request.urlopen(urllib.request.Request(f"{API}/generation?id={data['id']}", headers=headers)) as response:
                    record = json.load(response)['data']
                break
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
        else:
            raise RuntimeError(f"no record of {data['id']}")
        data['usage'] = {'prompt_tokens': record['native_tokens_prompt'], 'completion_tokens': record['native_tokens_completion'],
                         'completion_tokens_details': {'reasoning_tokens': record['native_tokens_reasoning']}, 'cost': record['usage']}
    message = {'content': ''.join(content), 'reasoning': ''.join(reasoning) or None, 'reasoning_details': merge(details) or None}
    return data | {'choices': [{'message': message, 'finish_reason': finish}]}


def openrouter(model, effort=None):
    """A client that sends a conversation to a model and returns its reply and the call's log entry."""
    def complete(messages):
        # exclude: false asks for the reasoning text (a summary, for some providers) without changing its effort
        body = json.dumps({'model': model, 'messages': messages, 'usage': {'include': True},
                           'max_tokens': MAX_TOKENS, 'stream': True,
                           'reasoning': {'exclude': False, **({'effort': effort} if effort else {})}}).encode()
        headers = {'Authorization': f'Bearer {os.environ.get("OPENROUTER_API_KEY", "proxy")}'}
        request = urllib.request.Request(f'{API}/chat/completions', body, headers | {'Content-Type': 'application/json'})
        for wait in [5, 15, 60, 120, None]:
            start = time.time()
            try:
                data = stream(request, headers)
                if 'choices' in data and data['choices'][0].get('finish_reason') != 'error':
                    break
                error = RuntimeError(data.get('error') or 'the provider stopped with an error')
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:  # long calls can be dropped
                if getattr(e, 'code', 500) not in (408, 429, 500, 502, 503, 504):
                    raise
                error = e
            if wait is None:
                raise error
            time.sleep(wait)
        message = data['choices'][0]['message']
        usage = data.get('usage', {})
        # some providers ignore max_tokens, so a reply over the limit is treated as cut off there
        over = (usage.get('completion_tokens') or 0) > MAX_TOKENS
        finish = 'length' if over else data['choices'][0].get('finish_reason')
        return '' if finish in CUT_OFF else message.get('content') or '', {
            'seconds': round(time.time() - start, 2),
            'input_tokens': usage.get('prompt_tokens'),
            'output_tokens': usage.get('completion_tokens'),
            'reasoning_tokens': (usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),
            'cost': usage.get('cost'),
            'provider': data.get('provider'),
            'reasoning': message.get('reasoning'),
            'reasoning_details': message.get('reasoning_details'),
            'finish_reason': finish,
        }
    return complete


def play(complete, mode, level, minimum):
    """Plays one level. Returns the conversation, the log of every call, the finished session and the submitted moves."""
    session = Session(level)
    messages = [{'role': 'user', 'content': prompt(mode, level, minimum)}]
    calls = []
    while True:
        reply, call = complete(messages)
        calls.append(call)
        messages.append({'role': 'assistant', 'content': reply})
        if mode != 'interactive':
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
        'solved': session.solved and session.moves <= (1 if mode == 'one-shot-minimum' else BUDGET) * minimum,
        'reached_goal': session.solved, 'moves': session.moves, 'total_actions': session.actions,
        'submitted': moves, 'calls': len(calls),
        'truncated': any(c['finish_reason'] in CUT_OFF for c in calls),  # ran out of output tokens or time
        **{key: total(key) for key in ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cost', 'seconds']},
        'messages': messages, 'call_log': calls,
    }


def scored_set(seed, per_kind, kinds=None):
    """A seeded sample of per_kind levels from the stock for each kind of level: {id: (text, minimum)}.

    Each kind is sampled on its own, so one kind's stock growing doesn't change another's sample.
    Kinds are '<clones>-<sliders 0/1>', optionally with a tier in front ('hard-3-0'); all by default.
    """
    levels = {}
    for path in sorted((LEVELS / 'stock').glob('*.jsonl')):
        if kinds and path.stem.split('-', 1)[1] not in kinds and path.stem not in kinds:
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
    parser.add_argument('--mode', choices=['one-shot', 'one-shot-minimum', 'interactive'], default='one-shot')
    parser.add_argument('--set', choices=['scored', 'dev'], default='scored')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--per-kind', type=int, default=10)
    parser.add_argument('--kinds', nargs='*', help="kinds of level to run, as <clones>-<sliders 0/1>, optionally with a tier ('hard-3-0'); all by default")
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--effort', choices=['low', 'medium', 'high', 'xhigh', 'max'],
                        help='reasoning effort; the provider default if omitted')
    parser.add_argument('--out')
    args = parser.parse_args()
    levels = dev_set() if args.set == 'dev' else scored_set(args.seed, args.per_kind, args.kinds)
    name = (f'{args.model.replace("/", "_")}-{args.mode}-{args.set}' + (f'-seed{args.seed}' if args.set == 'scored' else '')
            + (f'-effort-{args.effort}' if args.effort else ''))
    out = Path(args.out or ROOT.parent / 'results' / f'{name}.jsonl')
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)['level'] for line in out.read_text().splitlines()} if out.exists() else set()
    todo = {k: v for k, v in levels.items() if k not in done}
    complete = openrouter(args.model, args.effort)

    def work(item):
        level_id, (text, minimum) = item
        try:
            record = {**run_level(complete, args.model, args.mode, level_id, text, minimum), 'effort': args.effort or 'default'}
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
