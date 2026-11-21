"""Renders harness results as one HTML page per file, to read how models approached each level.

Usage: python -m mqbench.transcripts RESULTS.jsonl ... [--out FILE]
"""
import argparse
import json
from html import escape

STYLE = """
body { font: 15px/1.55 system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 24px 16px; color: #1d2230; background: #fbfbfd; }
h1 { font-size: 22px; } h2 { font-size: 17px; margin: 0; }
section { border: 1px solid #dde1ea; background: #fff; border-radius: 8px; padding: 16px; margin: 16px 0; }
.meta { color: #5b6275; font-size: 13px; margin: 4px 0 10px; }
.solved { color: #11803b; } .failed { color: #b4232b; }
pre { white-space: pre-wrap; word-break: break-word; font: 13px/1.45 ui-monospace, Menlo, monospace; background: #f3f4f8; padding: 10px; border-radius: 6px; margin: 6px 0; }
pre.board { display: inline-block; letter-spacing: 0.25em; }
summary { cursor: pointer; font-weight: 600; margin-top: 8px; }
.turn { border-left: 3px solid #dde1ea; padding-left: 10px; margin: 8px 0; }
"""


def reasoning_text(call):
    if call.get('reasoning'):
        return call['reasoning']
    parts = [d.get('summary') or d.get('text') for d in call.get('reasoning_details') or []]
    return '\n\n'.join(p for p in parts if p) or None


def render(record):
    result = (f'<span class="solved">Solved in {record["moves"]}</span>' if record['solved']
              else f'<span class="failed">Not solved</span> ({record["moves"]} moves played)')
    meta = (f'{result} · minimum {record["minimum"]} · {record["output_tokens"]:,} output tokens '
            f'({record["reasoning_tokens"] or 0:,} reasoning) · {record["seconds"]:.0f}s · ${record["cost"] or 0:.3f}'
            + (' · <b>cut off at the output limit</b>' if record.get('truncated') else ''))
    board = record['messages'][0]['content'].split('Here is the level:\n\n', 1)[1].split('\n\n', 1)[0]
    turns = []
    for call, reply in zip(record['call_log'], record['messages'][1::2]):
        thinking = reasoning_text(call)
        turns.append('<div class="turn">'
                     + (f'<details><summary>Reasoning</summary><pre>{escape(thinking)}</pre></details>' if thinking else '')
                     + f'<pre>{escape(reply["content"])}</pre></div>')
    feedback = [f'<pre>{escape(m["content"])}</pre>' for m in record['messages'][2::2]]
    body = ''.join(t + (feedback[i] if i < len(feedback) else '') for i, t in enumerate(turns))
    return (f'<section><h2>{escape(record["level"])}</h2><p class="meta">{meta}</p>'
            f'<pre class="board">{escape(board)}</pre>{body}</section>')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('results', nargs='+')
    parser.add_argument('--out', default='transcripts.html')
    args = parser.parse_args()
    records = [json.loads(line) for path in args.results for line in open(path)]
    records.sort(key=lambda r: (r['model'], r['mode'], r['level']))
    title = ', '.join(sorted({f'{r["model"]} ({r["mode"]})' for r in records}))
    with open(args.out, 'w') as f:
        f.write(f'<!doctype html><meta charset="utf-8"><title>Mirror Quest transcripts</title><style>{STYLE}</style>'
                f'<h1>Mirror Quest transcripts</h1><p class="meta">{escape(title)}</p>'
                + ''.join(render(r) for r in records))


if __name__ == '__main__':
    main()
