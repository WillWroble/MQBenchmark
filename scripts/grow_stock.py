"""Adds generated levels to the stock in levels/stock, using every CPU core.

Each kind of level has its own file, <tier>-<clones>-<sliders 0/1>.jsonl, with one level per
line. New levels continue from the highest seed already in the file, and each is saved as
soon as it is made, so an interrupted run loses nothing.

Usage: python -m scripts.grow_stock COUNT [KIND ...], where a kind is <clones>-<sliders 0/1>
(all four by default) and COUNT is how many levels to add for each tier of each kind.
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from mqbench.generator import SLIDERS, TIERS, generate

STOCK = Path(__file__).parent.parent / 'levels' / 'stock'
KINDS = ['2-0', '3-0', '2-1', '3-1']


def make(tier, clones, sliders, seed):
    text, solution = generate(seed, tier, clones, SLIDERS * sliders)
    return {'seed': seed, 'text': text, 'minimum': len(solution), 'solution': solution}


def main(count, kinds=KINDS):
    STOCK.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor() as pool:
        jobs = {}
        for kind in kinds:
            clones, sliders = map(int, kind.split('-'))
            for tier in TIERS:
                path = STOCK / f'{tier}-{kind}.jsonl'
                seeds = [json.loads(line)['seed'] for line in path.read_text().splitlines()] if path.exists() else []
                first = max(seeds, default=-1) + 1
                for seed in range(first, first + count):
                    jobs[pool.submit(make, tier, clones, sliders, seed)] = path
        for done, job in enumerate(as_completed(jobs), 1):
            with jobs[job].open('a') as f:
                f.write(json.dumps(job.result()) + '\n')
            print(f'{done}/{len(jobs)} {jobs[job].stem}', flush=True)


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2:] or KINDS)
