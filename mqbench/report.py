"""Summarizes harness results: accuracy alongside the tokens, time and cost it took.

Usage: python -m mqbench.report RESULTS.jsonl ... [--json FILE]

With --json, the summary is written to FILE for the leaderboard instead of printed.
"""
import argparse
import json
from collections import defaultdict


def summarize(records):
    """Per (model, mode, kind of level), plus an 'all' row per model and mode."""
    groups = defaultdict(list)
    for r in records:
        kind = 'dev' if r['level'].startswith('dev-') else r['level'].rsplit('-', 1)[0]
        model = r['model'] + (f" ({r['effort']} effort)" if r.get('effort', 'default') != 'default' else '')
        groups[model, r['mode'], kind].append(r)
        groups[model, r['mode'], 'all'].append(r)
    rows = []
    for (model, mode, kind), rs in sorted(groups.items()):
        solved = [r for r in rs if r['solved']]
        mean = lambda key, of=rs: sum(r[key] or 0 for r in of) / len(of) if of else None
        rows.append({
            'model': model, 'mode': mode, 'kind': kind, 'levels': len(rs),
            'solve_rate': len(solved) / len(rs),
            'truncated': sum(r.get('truncated', False) for r in rs) / len(rs),
            'wrong': sum(not r['solved'] and not r.get('truncated') for r in rs) / len(rs),  # answered, but failed
            'moves_over_minimum': sum(r['moves'] / r['minimum'] for r in solved) / len(solved) if solved else None,
            'output_tokens': mean('output_tokens'), 'reasoning_tokens': mean('reasoning_tokens'),
            'output_tokens_per_solve': sum(r['output_tokens'] or 0 for r in rs) / len(solved) if solved else None,
            'seconds': mean('seconds'), 'cost': mean('cost'),
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('results', nargs='+')
    parser.add_argument('--json')
    args = parser.parse_args()
    rows = summarize([json.loads(line) for path in args.results for line in open(path)])
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(rows, f, indent=1)
        return
    columns = ['model', 'mode', 'kind', 'levels', 'solve_rate', 'truncated', 'wrong', 'moves_over_minimum', 'output_tokens',
               'reasoning_tokens', 'output_tokens_per_solve', 'seconds', 'cost']
    fmt = lambda v: '-' if v is None else f'{v:.3g}' if isinstance(v, float) else str(v)
    table = [columns] + [[fmt(row[c]) for c in columns] for row in rows]
    widths = [max(len(line[i]) for line in table) for i in range(len(columns))]
    for line in table:
        print('  '.join(cell.ljust(w) for cell, w in zip(line, widths)))


if __name__ == '__main__':
    main()
