# MQBenchmark

A no-code spatial planning benchmark for LLMs, built on the puzzle game Mirror Quest. Models are given the rules and the board and must plan moves without tools or code execution: given the rules, any code-running agent can solve these levels by search in seconds.

## References

- Repository: https://github.com/WillWroble/MQBenchmark
- Original game (source of truth for rules and levels): https://github.com/WillWroble/MirrorQuestWindows. Derive mechanics from this code.
- Rotation code in the original project never shipped. Ignore it.
- Validation datum confirmed against the shipped game: level 7, numbered as the game shows it, has a minimum of 20 moves.

## Design

- **Level sets**
  - *Dev set:* the original hand-designed levels, published openly.
  - *Scored set:* procedurally generated levels with exact minimums computed by BFS, generated fresh per evaluation from seeds.
- **Generated level scope at launch:** walls only, with 2, 3 and 4 clones, plus a sliders tier with 2 and 3 clones. Teleporters and drains are deferred. Boards are 10×7. Clones are A–D and drains are O in the text format.
- **Rules:** generated levels use the original game's rules, extended to N clones.
- **Model interface:** text only, with the board given as a text matrix (ARC-style). Otherwise the model's experience should match a human player's: the same rules text and the same controls, including undo and reset in interactive mode.
- **Human interface:** a web version using the original game's art (`Assets/Resources/Textures`; the sprites used in levels are assigned in the `InGame` scene).
- **Third-party assets:** the original project includes Unity Asset Store packs (backgrounds, UI kits, music, fonts) that generally can't be redistributed. Confirm the provenance of any asset before committing it.
- **Modes:** one-shot (the full move list committed with no feedback) is the headline metric. Interactive mode is reported as a secondary metric.
- **Scoring:** solve rate within a move budget (default 2× the minimum), plus moves relative to the minimum. In interactive mode, undone moves don't count, as in the game, but the model is capped at 5× the minimum in total actions, undos and resets included; total actions are logged. Human baselines are collected through the web version.
- **Harness:** API-only, with no tool use, fixed prompts and full logging. Models are reached through OpenRouter and run with provider-default reasoning settings, under the same output limit of 65,536 tokens per call, reasoning included; a reply cut off at the limit counts as unsolved. Every call logs input, output and reasoning tokens, time and cost, so reasoning efficiency can be reported alongside accuracy. In interactive mode the model sends one action per turn and sees the board after each, as a human does. A scored evaluation samples 10 levels of each kind (clones × sliders × tier) from the stock.
- **Level stock:** generated levels are built ahead of time by `scripts/grow_stock.py` into `levels/stock`, and scored sets are fresh seeded samples from it.
- **Hosting:** GitHub (engine, generator, solver, harness, seeds), Hugging Face (dataset and leaderboard), and a public web version for human baselines.

## Licensing

- Code: MIT.
- Levels and dataset: CC BY 4.0, attributing the original Mirror Quest game.
- Include `LICENSE`, `CITATION.cff`, `README.md`, and a Hugging Face dataset card.

## Conventions

- Keep code clean and minimal, reuse existing code where reasonable, and follow established conventions.
- Confirm design decisions with the maintainer before implementing non-trivial changes; don't choose defaults unilaterally.
- Use the game's terminology: clones, formations, walls, sliders, teleporters, drains.

## Open questions

- The symbol for each tile type in the text matrix.
- Prompt wording, and whether dev-set levels are shown as examples.
- Move budget and difficulty-tier boundaries for the scored set.
