---
license: cc-by-4.0
pretty_name: MQBenchmark human plays
tags:
- puzzles
- planning
- human-baseline
configs:
- config_name: default
  data_files: plays/*.jsonl
---

# MQBenchmark human plays

Games of Mirror Quest played by people on the [Mirror Quest Space](https://huggingface.co/spaces/inkling616/mirror-quest). They are the human baseline for [MQBenchmark](https://github.com/WillWroble/MQBenchmark), a no-code spatial planning benchmark for LLMs. Players are anonymous.

Each row is one attempt at one level, recorded when the level was solved or left unfinished. The server replays every game on the benchmark's engine, so `solved`, `moves` and `total_actions` are computed, not reported by the browser.

| Field | Meaning |
|---|---|
| `level` | `dev-<n>` for an original level, or `<tier>-<clones>-<sliders 0/1>-<seed>` for a generated benchmark level |
| `player` | Random id kept in the player's browser |
| `attempt` | 1 for a first attempt; a player who resets after solving retries the level as attempt 2, 3 and so on. The leaderboard counts first attempts only |
| `actions` | Every action in order: `a` is `U`, `D`, `L`, `R`, `undo` or `reset`, and `t` is milliseconds since the level appeared |
| `solved` | Whether every clone ended on a goal |
| `moves` | Moves on the final count, as the game counts them: undone moves come off, and a reset starts over |
| `minimum` | The level's minimum number of moves |
| `total_actions` | All actions, including undos and resets |
| `time_ms` | Milliseconds from the level appearing to the last action |
| `recorded_at` | Unix time the server stored the game |

Levels are adapted from the original [Mirror Quest](https://github.com/WillWroble/MirrorQuestWindows) game. Licensed CC BY 4.0.
