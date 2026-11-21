"""Summarizes harness results: accuracy alongside the tokens, time and cost it took.

Usage: python -m mqbench.report RESULTS.jsonl ...
"""
import json
import sys
from collections import defaultdict


def summarize(records):
    """Per (model, mode, kind of level), plus an 'all' row per model and mode."""
    groups = defaultdict(list)
    for r in records:
        kind = 'dev' if r['level'].startswith('dev-') else r['level'].rsplit('-', 1)[0]
        groups[r['model'], r['mode'], kind].append(r)
        groups[r['model'], r['mode'], 'all'].append(r)
    rows = []
    for (model, mode, kind), rs in sorted(groups.items()):
        solved = [r for r in rs if r['solved']]
        mean = lambda key, of=rs: sum(r[key] or 0 for r in of) / len(of) if of else None
        rows.append({
            'model': model, 'mode': mode, 'kind': kind, 'levels': len(rs),
            'solve_rate': len(solved) / len(rs),
            'moves_over_minimum': sum(r['moves'] / r['minimum'] for r in solved) / len(solved) if solved else None,
            'output_tokens': mean('output_tokens'), 'reasoning_tokens': mean('reasoning_tokens'),
            'output_tokens_per_solve': sum(r['output_tokens'] or 0 for r in rs) / len(solved) if solved else None,
            'seconds': mean('seconds'), 'cost': mean('cost'),
        })
    return rows


def main():
    records = [json.loads(line) for path in sys.argv[1:] for line in open(path)]
    columns = ['model', 'mode', 'kind', 'levels', 'solve_rate', 'moves_over_minimum', 'output_tokens',
               'reasoning_tokens', 'output_tokens_per_solve', 'seconds', 'cost']
    fmt = lambda v: '-' if v is None else f'{v:.3g}' if isinstance(v, float) else str(v)
    table = [columns] + [[fmt(row[c]) for c in columns] for row in summarize(records)]
    widths = [max(len(line[i]) for line in table) for i in range(len(columns))]
    for line in table:
        print('  '.join(cell.ljust(w) for cell, w in zip(line, widths)))


if __name__ == '__main__':
    main()
