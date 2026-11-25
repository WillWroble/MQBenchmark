# MQBenchmark

A no-code spatial planning benchmark for LLMs, built on the puzzle game [Mirror Quest](https://github.com/WillWroble/MirrorQuestWindows).

You move every clone at once, and each move sends them all one square in the same direction. Walls hold some clones back while the rest keep moving, so the job is to break the formation and rebuild it until every clone stands on a goal. Models get the rules and a text board, and they must plan the moves in their heads. They have no tools and no code execution. Any agent that can run code solves these levels by search in seconds, so the benchmark measures planning, not programming.

**Play it and see the leaderboard:** [huggingface.co/spaces/inkling616/mirror-quest](https://huggingface.co/spaces/inkling616/mirror-quest)

## Example

Level 7 of the original game (minimum 20 moves):

```
_______
_______
_______
G.~~~T_
__~~~~_
__~~~~_
_GTSS~_
__.AB__
_______
_______
```

| Symbol | Meaning |
|---|---|
| `A` `B` `C` `D` | clones |
| `.` | floor |
| `#` | wall |
| `_` | void |
| `G` | goal |
| `~` | smooth floor |
| `S` | slider |
| `T` / `t` | teleporter / exit-only teleporter |
| `O` | drain |

The full rules the models see are in [`mqbench/rules.txt`](mqbench/rules.txt), and the prompts are in [`mqbench/prompts`](mqbench/prompts).

## Levels

- **Dev set** ([`levels/dev`](levels/dev)): the 12 hand-designed levels of the original game, ported exactly from its source.
- **Scored set** ([`levels/stock`](levels/stock)): procedurally generated levels on 10×7 boards, each solved by BFS so its minimum is exact. A kind of level is named `<tier>-<clones>-<sliders>`: for example, `hard-3-0` is a hard level with 3 clones and no sliders, and `medium-2-1` is a medium level with 2 clones and sliders.

| Tier | Minimum moves |
|---|---|
| easy | 6–12 |
| medium | 13–24 |
| hard | 25–40 |
| expert | 50–80, 3 clones on 12×9 boards |

The headline set has 90 levels: 10 of each tier for 2 clones, 3 clones, and 2 clones with sliders. The stock also has 4-clone, 3-clone-with-sliders and expert levels.

## Scoring

- **One-shot** (headline): the model commits its full list of moves with no feedback. A level counts as solved if the moves reach the goal within 2× the minimum.
- **One-shot minimum**: the model is told the minimum, and only a solution of exactly that length counts.
- **Interactive**: the model sends one action per turn and sees the board after each, with undo and reset as in the game. Undone moves don't count, but the model is capped at 5× the minimum in total actions.

Every model gets the same output limit, 65,536 tokens per call with reasoning included, and a reply cut off at the limit counts as unsolved. Every call logs input, output and reasoning tokens, time and cost, so reasoning efficiency can be reported alongside accuracy. Human baselines come from games played on the web version.

## Results

One-shot, 90-level headline set:

| Model | Solved | Moves / minimum | Output tokens / level | Cost / level |
|---|---|---|---|---|
| GPT-6.2 Astra (high) | 97% | 1.19 | 2,859 | $0.12 |
| Claude Opus 5.5 | 89% | 1.16 | 18,749 | $0.38 |
| Kimi K3.1 Pro (high) | 51% | 1.26 | 28,339 | $0.28 |
| Gemini 3.1 Pro (high) | 50% | 1.14 | 29,468 | $0.36 |
| Gemini 3.8 Flash (high) | 44% | 1.12 | 49,144 | $0.19 |
| GPT-5.6 Sol (high) | 43% | 1.26 | 14,277 | $0.29 |
| GPT-5.6 Sol | 30% | 1.18 | 7,738 | $0.16 |
| DeepSeek V4 Pro (high) | 26% | 1.17 | 51,177 | $0.20 |

Moves / minimum is averaged over solved levels. The live leaderboard, including human results, is on the [Space](https://huggingface.co/spaces/inkling616/mirror-quest).

## Usage

Run a model through [OpenRouter](https://openrouter.ai) (needs `OPENROUTER_API_KEY`):

```bash
python -m mqbench.harness anthropic/claude-opus-5.5 --kinds 2-0 3-0 2-1
```

The harness samples 10 levels of each kind from the stock with a fixed seed (`--seed`), writes one JSON line per level to `results/`, and resumes where it left off when rerun. Use `--mode` for the other modes, `--effort` for a reasoning effort, and `--set dev` for the original levels.

Summarize results:

```bash
python -m mqbench.report results/*.jsonl
```

Generate more levels:

```bash
python -m scripts.grow_stock 100 3-0 2-1 --tiers easy medium hard
```

Run the tests:

```bash
python -m pytest
```

The harness, engine, solver and generator use only the Python standard library. The web version in [`web`](web) and [`space`](space) runs on FastAPI.

## License

The code is MIT licensed (see [`LICENSE`](LICENSE)). The levels and the dataset are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); please attribute the original Mirror Quest game by Will Wroble.
