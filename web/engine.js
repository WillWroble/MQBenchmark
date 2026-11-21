// Port of mqbench/engine.py. Keep the two in step: tests/test_web.py replays random moves through both.

const [VOID, FLOOR, WALL, GOAL, SMOOTH, TELEPORTER, EXIT, DRAIN, SLIDER] = '_.#G~TtDS';
const CLONES = 'ABC';
const SLIDES = new Set([VOID, SMOOTH, TELEPORTER, EXIT, DRAIN]);
const DIRECTIONS = { U: [-1, 0], D: [1, 0], L: [0, -1], R: [0, 1] };
const BLOCKED = 'blocked', FALLS = 'falls';

const key = (r, c) => `${r},${c}`;
const add = (p, [dr, dc]) => { const [r, c] = p.split(',').map(Number); return key(r + dr, c + dc); };

class Level {
  constructor(text) {
    const rows = text.trim().split(/\s+/);
    const clones = {};
    const sliders = new Set();
    this.tiles = new Map();
    rows.forEach((row, r) => [...row].forEach((ch, c) => {
      if (CLONES.includes(ch)) { clones[ch] = key(r, c); ch = FLOOR; }
      else if (ch === SLIDER) { sliders.add(key(r, c)); ch = SMOOTH; }
      this.tiles.set(key(r, c), ch);
    }));
    this.shape = [rows.length, rows[0].length];
    this.teleporters = [...this.tiles].filter(([, t]) => t === TELEPORTER || t === EXIT).map(([p]) => p);
    this.start = { clones: Object.keys(clones).sort().map(k => clones[k]), sliders };
  }

  tile(p) { return this.tiles.get(p) ?? VOID; }

  solved(state) { return state.clones.every(p => this.tile(p) === GOAL); }

  // Returns the state after a move, or the same state if nothing moved.
  step(state, move) {
    const d = DIRECTIONS[move];
    const { clones, sliders } = state;
    const disabled = clones.map((p, i) => i).filter(i => this.tile(clones[i]) === DRAIN);
    const banned = new Set(), pushed = new Set();
    for (;;) {
      const free = new Set(sliders);
      const moves = new Map();  // start square -> [end square, teleporter it depends on]
      const order = clones.map((p, i) => i).filter(i => !disabled.includes(i))
        .concat([...pushed].sort((a, b) => a - b));
      for (const i of order) {
        const chain = this.enter(free, add(clones[i], d), d, banned, null);
        if (chain === FALLS) return state;
        if (chain !== BLOCKED) {
          const [end, tag, rest] = chain;
          moves.set(clones[i], [end, tag]);
          rest.forEach((v, k) => moves.set(k, v));
        }
      }
      const end = p => moves.has(p) ? moves.get(p)[0] : p;
      const ends = new Map();
      for (const p of [...clones, ...sliders]) ends.set(end(p), [...(ends.get(end(p)) ?? []), p]);
      const colliding = new Set([...ends.values()].filter(ps => ps.length > 1).flat());
      if (!colliding.size && !moves.size) return state;
      if (!colliding.size) return { clones: clones.map(end), sliders: new Set([...sliders].map(end)), moves };
      const tags = [...colliding].map(p => moves.get(p)?.[1]).filter(Boolean);
      const hit = disabled.filter(i => !pushed.has(i) && colliding.has(clones[i]));
      if (tags.length) tags.forEach(t => banned.add(t));
      else if (hit.length) hit.forEach(i => pushed.add(i));
      else return state;
    }
  }

  // An object enters square p moving along d, pushing any sliders ahead of it.
  // Returns BLOCKED, FALLS, or [where it ends, the teleporter that move depends on, Map of pushed sliders].
  enter(free, p, d, banned, tag) {
    const tile = this.tile(p);
    if (tile === WALL) return BLOCKED;
    if (tile === VOID) return tag ? BLOCKED : FALLS;
    let pushed = new Map();
    if (free.has(p)) {
      if (!SLIDES.has(this.tile(add(p, d)))) return BLOCKED;
      free.delete(p);
      const chain = this.enter(free, add(p, d), d, banned, tag);
      if (chain === BLOCKED || chain === FALLS) { free.add(p); return chain; }
      const [end, sliderTag, rest] = chain;
      pushed = rest.set(p, [end, sliderTag]);
    }
    if (tile === TELEPORTER && !tag && !banned.has(p)) {
      const exit = this.teleporters.find(q => q !== p);
      const chain = this.enter(free, exit, d, banned, p);
      if (chain !== BLOCKED) return [chain[0], chain[1], new Map([...pushed, ...chain[2]])];
    }
    return [p, tag, pushed];
  }
}

if (typeof module !== 'undefined') module.exports = { Level, CLONES };
