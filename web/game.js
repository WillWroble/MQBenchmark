const $ = id => document.getElementById(id);
const TILE_SPRITES = { '.': 'floor', '#': 'wall', 'G': 'goal', 'T': 'teleporter', 't': 'exit', '~': 'smooth', 'O': 'drain' };
const SPRITES = [...Object.values(TILE_SPRITES), 'slider', 'clone', 'clone-disabled'];
const KEYS = { arrowup: 'U', arrowdown: 'D', arrowleft: 'L', arrowright: 'R', w: 'U', s: 'D', a: 'L', d: 'R',
               z: 'undo', b: 'undo', backspace: 'undo', r: 'reset' };
const ORIGINAL = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0];
// Movement matches the game's CloneManager2: speed 3.5 squares/s, growing by a factor of
// (1 + 4 × distance covered), so a step accelerates and takes about 115 ms.
const SPEED = 3.5, ACCELERATION = 4;
const STEP_MS = 1000 * Math.log(1 + ACCELERATION) / (SPEED * ACCELERATION);
const ART = 20;  // the sprites are drawn on a 20-pixel grid, so cells are multiples of it
// As in the game, sprites are 1.05 cells wide and overlap their neighbours, layered back to front:
// smooth floor, then teleporters and drains, then floor, walls and goals, then sliders and clones.
const SIZE = 1.05, OVERLAP = (SIZE - 1) / 2;
const TILE_LAYERS = ['~', 'TtO', '.#G'];

const storage = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const settings = { set: 'benchmark', clones: '2', sliders: 'false', tier: 'easy', original: '1', ...storage.get('settings') };
const player = storage.get('player') ?? crypto.randomUUID();
storage.set('player', player);

const images = {};
let game = null, anim = null, prefetched = null, pending = null, cell = 2 * ART;
let linked = new URLSearchParams(location.search).get('level');  // ?level=<id> opens that level first

// Levels

const kind = () => `tier=${settings.tier}&clones=${settings.clones}&sliders=${settings.sliders}`;
const fetchJson = url => fetch(url).then(r => r.ok ? r.json() : Promise.reject(r));

function nextBenchmark() {
  const current = prefetched?.kind === kind() ? prefetched.level : fetchJson(`/api/levels/new?${kind()}`);
  prefetched = { kind: kind(), level: fetchJson(`/api/levels/new?${kind()}`) };
  prefetched.level.catch(() => { prefetched = null; });
  return current;
}

async function newGame() {
  record();
  game = anim = null;
  $('result').hidden = true;
  $('loading').textContent = 'Building a level…';
  $('loading').hidden = false;
  render();
  const request = pending = {};
  let data;
  try {
    const id = linked ?? (settings.set === 'original' ? `dev-${settings.original}` : null);
    linked = null;
    data = await (id ? fetchJson(`/api/levels/${encodeURIComponent(id)}`) : nextBenchmark());
  } catch (error) {
    if (request === pending) {
      $('loading').textContent = error.status === 404 ? 'No levels of this kind yet. Pick another kind.'
        : 'Could not load a level. Check your connection and pick a level again.';
    }
    return;
  }
  if (request !== pending) return;
  $('loading').hidden = true;
  game = attempt(data.id, new Level(data.text), 1);
  resize();
  render();
}

// Playing

const state = () => game.history.at(-1);
const solved = () => game && game.level.solved(state());
const attempt = (id, level, number) =>
  ({ id, level, number, history: [level.start], actions: [], started: performance.now(), sent: false });

function act(action) {
  if (!game) return;
  if (solved()) {
    // After a solve, reset starts a new attempt at the same level.
    if (action === 'reset') {
      game = attempt(game.id, game.level, game.number + 1);
      $('result').hidden = true;
      render();
    }
    return;
  }
  anim = null;
  game.actions.push({ a: action, t: Math.round(performance.now() - game.started) });
  if (action === 'undo') {
    if (game.history.length > 1) {
      // Undo plays the move backwards, as in the game.
      const before = game.history.pop();
      const back = new Map([...before.moves].map(([from, [to]]) => [to, from]));
      animate(before, [...before.sliders].map(p => [p, back.get(p) ?? p]));
    }
  } else if (action === 'reset') {
    game.history = [game.level.start];
  } else {
    const before = state(), after = game.level.step(before, action);
    if (after !== before) {
      game.history.push(after);
      animate(before, [...before.sliders].map(p => [p, after.moves.get(p)?.[0] ?? p]));
    }
  }
  render();
  if (solved()) finish();
}

function animate(before, sliders) {
  anim = { before, sliders, start: performance.now() };
  requestAnimationFrame(frame);
}

function finish() {
  const g = game, moves = g.history.length - 1;
  $('result-text').textContent = `Solved in ${moves} moves`;
  $('result').hidden = false;
  $('next').focus();
  record()?.then(r => r.json()).then(({ minimum }) => {
    if (game === g) $('result-text').textContent = `Solved in ${moves} moves · minimum ${minimum}`;
  }).catch(() => {});
}

// Sends the game to the server once, when it is solved or left unfinished.
function record() {
  if (!game || game.sent || !game.actions.length) return null;
  game.sent = true;
  return send(JSON.stringify({ id: crypto.randomUUID(), level: game.id, player, attempt: game.number, actions: game.actions }));
}

// Each game is kept in the browser until the server confirms it, so one that fails to send, even as
// the page closes, is sent again on the next visit; its id stops the server counting it twice.
// Browsers refuse keepalive requests over 64 KB, which long games exceed.
function send(body) {
  const unsent = (without = body) => (storage.get('unsent') ?? []).filter(b => b !== without);
  storage.set('unsent', [...unsent(), body]);
  const request = fetch('/api/plays', {
    method: 'POST', keepalive: body.length < 60000, headers: { 'Content-Type': 'application/json' }, body,
  }).then(r => {
    if (r.status >= 500) throw r;
    storage.set('unsent', unsent());
    return r;
  });
  request.catch(() => {});
  return request;
}

const resend = () => (storage.get('unsent') ?? []).forEach(send);

function next() {
  if (settings.set === 'original') {
    settings.original = String(ORIGINAL[(ORIGINAL.indexOf(Number(settings.original)) + 1) % ORIGINAL.length]);
    storage.set('settings', settings);
    showSettings();
  }
  newGame();
}

// Drawing

function resize() {
  if (!game) return;
  const [rows, cols] = game.level.shape;
  const width = Math.min(document.querySelector('.stage').clientWidth, 720);
  const height = Math.max(window.innerHeight * 0.6, 240);
  cell = ART * Math.max(1, Math.min(3, Math.floor(Math.min(width / cols, height / rows) / ART)));
  const canvas = $('board'), dpr = window.devicePixelRatio || 1;
  canvas.style.width = `${cols * cell}px`;
  canvas.style.height = `${rows * cell}px`;
  canvas.width = Math.round(cols * cell * dpr);
  canvas.height = Math.round(rows * cell * dpr);
  document.documentElement.style.setProperty('--board-width', `${cols * cell}px`);
}

function frame() {
  render();
  if (anim && performance.now() - anim.start < STEP_MS) requestAnimationFrame(frame);
  else if (anim) { anim = null; render(); }
}

function render() {
  $('moves').textContent = game ? game.history.length - 1 : 0;
  $('level-id').textContent = game?.id ?? '';
  $('undo').disabled = !game || solved();
  $('reset').disabled = !game;
  const canvas = $('board'), ctx = canvas.getContext('2d');
  ctx.setTransform(canvas.width / (canvas.clientWidth || 1), 0, 0, canvas.width / (canvas.clientWidth || 1), 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!game) return;
  const [rows, cols] = game.level.shape;
  const put = (sprite, r, c) => ctx.drawImage(images[sprite], (c - OVERLAP) * cell, (r - OVERLAP) * cell, SIZE * cell, SIZE * cell);
  for (const layer of TILE_LAYERS) {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const tile = game.level.tile(`${r},${c}`);
        if (layer.includes(tile)) put(TILE_SPRITES[tile], r, c);
      }
    }
  }
  const seconds = anim ? (performance.now() - anim.start) / 1000 : Infinity;
  const k = Math.min(1, (Math.exp(SPEED * ACCELERATION * seconds) - 1) / ACCELERATION);
  const draw = (sprite, from, to) => {
    const [r0, c0] = from.split(',').map(Number), [r1, c1] = to.split(',').map(Number);
    const t = Math.abs(r1 - r0) + Math.abs(c1 - c0) > 1 ? 1 : k;  // teleports jump
    put(sprite, r0 + (r1 - r0) * t, c0 + (c1 - c0) * t);
  };
  if (anim) {
    anim.sliders.forEach(([from, to]) => draw('slider', from, to));
  } else {
    state().sliders.forEach(p => draw('slider', p, p));
  }
  state().clones.forEach((p, i) => {
    const stuck = !anim && game.level.tile(p) === 'O';
    draw(stuck ? 'clone-disabled' : 'clone', anim ? anim.before.clones[i] : p, p);
  });
}

function drawStars() {
  const canvas = $('stars'), dpr = window.devicePixelRatio || 1;
  canvas.width = innerWidth * dpr;
  canvas.height = innerHeight * dpr;
  const ctx = canvas.getContext('2d');
  let seed = 7;
  const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let n = innerWidth * innerHeight / 2500; n > 0; n--) {
    ctx.fillStyle = `rgba(220, 230, 227, ${0.15 + rand() * 0.6})`;
    const size = (rand() < 0.1 ? 2 : 1) * dpr;
    ctx.fillRect(Math.floor(rand() * canvas.width), Math.floor(rand() * canvas.height), size, size);
  }
}

// Controls

function showSettings() {
  document.body.dataset.set = settings.set;
  for (const group of document.querySelectorAll('.segmented')) {
    for (const b of group.querySelectorAll('button')) b.setAttribute('aria-pressed', b.dataset.value === settings[group.id]);
  }
  $('original').value = settings.original;
}

for (const group of document.querySelectorAll('.segmented')) {
  group.addEventListener('click', e => {
    const value = e.target.closest('button')?.dataset.value;
    if (!value || value === settings[group.id]) return;
    settings[group.id] = value;
    storage.set('settings', settings);
    showSettings();
    newGame();
  });
}
$('original').append(...ORIGINAL.map(n => new Option(`Level ${n}`, n)));
$('original').addEventListener('change', e => {
  settings.original = e.target.value;
  storage.set('settings', settings);
  newGame();
});
$('undo').addEventListener('click', () => act('undo'));
$('reset').addEventListener('click', () => act('reset'));
$('next').addEventListener('click', next);
document.querySelectorAll('[data-move]').forEach(b => b.addEventListener('click', () => act(b.dataset.move)));

document.addEventListener('keydown', e => {
  if ($('play').hidden || e.metaKey || e.ctrlKey || e.altKey || e.target.tagName === 'SELECT') return;
  const key = e.key.toLowerCase();
  if (key === 'enter' && solved()) { e.preventDefault(); next(); }
  else if (KEYS[key]) { e.preventDefault(); act(KEYS[key]); }
});

let swipe = null;
const board = document.querySelector('.board');
board.addEventListener('pointerdown', e => { swipe = [e.clientX, e.clientY]; });
board.addEventListener('pointerup', e => {
  if (!swipe) return;
  const [dx, dy] = [e.clientX - swipe[0], e.clientY - swipe[1]];
  swipe = null;
  if (Math.max(Math.abs(dx), Math.abs(dy)) >= 24) act(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'R' : 'L') : (dy > 0 ? 'D' : 'U'));
});

addEventListener('pagehide', record);
addEventListener('resize', () => { drawStars(); resize(); render(); });

// Pages

const KIND_NAMES = { '2-0': '2 clones', '2-1': '2 clones, sliders', '3-0': '3 clones', '3-1': '3 clones, sliders', '4-0': '4 clones' };
const TIERS = ['easy', 'medium', 'hard', 'expert'];
const pct = x => `${Math.round(x * 100)}%`;
const thousands = x => x == null ? '–' : `${(x / 1000).toFixed(1)}k`;

// Charts

const shortName = model => model.split('/').pop().replace(' (high effort)', ' (high)');
const OUTCOMES = [['solved', 'Solved', m => m.solve_rate], ['wrong', 'Wrong', m => m.wrong], ['cut', 'Cut off', m => m.truncated]];
const legend = items => `<p class="legend">${items.map(([c, label]) => `<span style="--c: var(--${c})">${label}</span>`).join('')}</p>`;

function showBars(overall) {
  $('model-bars').innerHTML = `<h3>Outcome per level</h3>${legend(OUTCOMES)}<div class="bars">${overall.map(m => `
    <span class="name">${shortName(m.model)}</span>
    <div class="track">${OUTCOMES.filter(([, , f]) => f(m) > 0).map(([c, label, f]) =>
      `<i class="${c}" style="flex: ${f(m)}" data-tip="${shortName(m.model)}\n${label}: ${pct(f(m))} of ${m.levels} levels"></i>`).join('')}</div>
    <span class="value">${pct(m.solve_rate)}</span>`).join('')}</div>`;
}

let scatterData = null;

// Solve rate against output tokens on a log scale. Labels go beside their dot where they fit,
// and are left to the tooltip where they don't.
function showScatter(overall = scatterData) {
  scatterData = overall;
  const box = $('model-scatter');
  const w = box.parentElement.clientWidth - 36, h = 300, left = 40, right = 12, top = 10, bottom = 34;
  if (!overall || $('leaderboard').hidden || w <= 0) return;
  const ticks = [1e3, 2e3, 5e3, 1e4, 2e4, 5e4, 1e5];
  const lo = Math.log10(ticks[0]), hi = Math.log10(ticks.at(-1));
  const x = t => left + (Math.log10(t) - lo) / (hi - lo) * (w - left - right);
  const y = r => top + (1 - r) * (h - top - bottom);
  const measure = document.createElement('canvas').getContext('2d');
  measure.font = '12px Inter, system-ui, sans-serif';
  const taken = overall.map(m => ({ x0: x(m.output_tokens) - 6, x1: x(m.output_tokens) + 6, y0: y(m.solve_rate) - 6, y1: y(m.solve_rate) + 6 }));
  const overlaps = b => b.x0 < left || b.x1 > w - right || b.y0 < 0 || b.y1 > h - bottom ||
    taken.some(t => b.x0 < t.x1 && t.x0 < b.x1 && b.y0 < t.y1 && t.y0 < b.y1);
  const labels = overall.map(m => {
    const name = shortName(m.model), tw = measure.measureText(name).width, px = x(m.output_tokens), py = y(m.solve_rate);
    const spots = [[px + 9, py + 4, 'start'], [px - 9, py + 4, 'end'], [px, py - 10, 'middle'], [px, py + 18, 'middle']];
    for (const [lx, ly, anchor] of spots) {
      const x0 = anchor === 'start' ? lx : anchor === 'end' ? lx - tw : lx - tw / 2;
      const b = { x0, x1: x0 + tw, y0: ly - 11, y1: ly + 3 };
      if (!overlaps(b)) { taken.push(b); return `<text class="label" x="${lx}" y="${ly}" text-anchor="${anchor}">${name}</text>`; }
    }
    return '';
  });
  const compact = t => `${t / 1e3}K`;
  box.innerHTML = `<h3>Solve rate against output tokens per level</h3>
    <svg class="scatter" width="${w}" height="${h}" role="img" aria-label="Solve rate against output tokens per level for each model">
      ${[0, 0.25, 0.5, 0.75, 1].map(r => `<line class="grid" x1="${left}" x2="${w - right}" y1="${y(r)}" y2="${y(r)}"/>
        <text class="axis" x="${left - 8}" y="${y(r) + 4}" text-anchor="end">${r * 100}%</text>`).join('')}
      ${ticks.map(t => `<text class="axis" x="${x(t)}" y="${h - bottom + 18}" text-anchor="middle">${compact(t)}</text>`).join('')}
      <text class="axis" x="${(left + w - right) / 2}" y="${h - 2}" text-anchor="middle">Output tokens per level (log scale)</text>
      ${overall.map(m => `<circle class="hit" cx="${x(m.output_tokens)}" cy="${y(m.solve_rate)}" r="12"
          data-tip="${shortName(m.model)}\nSolved: ${pct(m.solve_rate)}\nTokens per level: ${thousands(m.output_tokens)}\nCost per level: $${(m.cost ?? 0).toFixed(2)}"/>
        <circle class="dot" cx="${x(m.output_tokens)}" cy="${y(m.solve_rate)}" r="5" pointer-events="none"/>`).join('')}
      ${labels.join('')}
    </svg>`;
}
addEventListener('resize', () => showScatter());

// Cells of the by-kind table are shaded by solve rate, one hue from clear to full.
const heatCell = rate => rate === undefined ? '<td class="num">–</td>'
  : `<td class="num heat" style="background: rgb(17 159 204 / ${0.08 + 0.72 * rate})">${pct(rate)}</td>`;

// One tooltip for every chart: marks carry their text in data-tip.
document.addEventListener('pointermove', e => {
  const target = e.target.closest?.('[data-tip]'), tip = $('tip');
  tip.hidden = !target;
  if (!target) return;
  tip.textContent = target.dataset.tip;
  tip.style.left = `${Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8)}px`;
  tip.style.top = `${e.clientY + 14}px`;
});

function showModels(models) {
  const overall = models.filter(m => m.kind === 'all').sort((a, b) => b.solve_rate - a.solve_rate);
  if (!overall.length) return;
  showBars(overall);
  showScatter(overall);
  $('models').innerHTML = `<table>
    <thead><tr><th>Model</th><th class="num">Levels</th><th class="num">Solved</th><th class="num">Cut off</th><th class="num">Wrong</th>
      <th class="num">Moves vs minimum</th><th class="num">Tokens per level</th><th class="num">Tokens per solve</th><th class="num">Cost per level</th></tr></thead>
    <tbody>${overall.map(m => `<tr><td>${m.model}</td><td class="num">${m.levels}</td><td class="num"><b>${pct(m.solve_rate)}</b></td>
      <td class="num">${pct(m.truncated)}</td><td class="num">${pct(m.wrong)}</td>
      <td class="num">${m.moves_over_minimum ? m.moves_over_minimum.toFixed(2) + '×' : '–'}</td>
      <td class="num">${thousands(m.output_tokens)}</td><td class="num">${thousands(m.output_tokens_per_solve)}</td>
      <td class="num">$${(m.cost ?? 0).toFixed(2)}</td></tr>`).join('')}</tbody></table>`;
  // kinds look like 'easy-2-0': sort by clones and sliders, then tier
  const split = k => [k.slice(k.indexOf('-') + 1), TIERS.indexOf(k.split('-')[0])];
  const kinds = [...new Set(models.map(m => m.kind).filter(k => k !== 'all' && k !== 'dev'))]
    .sort((a, b) => split(a)[0].localeCompare(split(b)[0]) || split(a)[1] - split(b)[1]);
  const cell = (model, kind) => models.find(m => m.model === model && m.kind === kind);
  $('model-kinds').innerHTML = `<table>
    <thead><tr><th>Solved, by kind of level</th>${overall.map(m => `<th class="num">${shortName(m.model)}</th>`).join('')}</tr></thead>
    <tbody>${kinds.map(k => `<tr><td>${KIND_NAMES[split(k)[0]]} · ${k.split('-')[0]}</td>
      ${overall.map(m => heatCell(cell(m.model, k)?.solve_rate)).join('')}</tr>`).join('')}</tbody></table>`;
}

async function showLeaderboard() {
  const { humans, models } = await fetchJson('/api/leaderboard');
  showModels(models);
  if (!humans.length) {
    $('humans').innerHTML = '<p class="lede">No games yet. Play a benchmark level to start the baseline.</p>';
    return;
  }
  $('humans').innerHTML = `<table>
    <thead><tr><th>Clones</th><th>Sliders</th><th>Difficulty</th><th class="num">Games</th><th class="num">Solved</th><th class="num">Moves vs minimum</th></tr></thead>
    <tbody>${humans.map(h => `<tr><td>${h.clones}</td><td>${h.sliders ? 'Yes' : 'No'}</td><td>${h.tier[0].toUpperCase() + h.tier.slice(1)}</td>
      <td class="num">${h.games}</td><td class="num">${pct(h.solve_rate)}</td>
      <td class="num">${h.moves_over_minimum ? h.moves_over_minimum.toFixed(2) + '×' : '–'}</td></tr>`).join('')}</tbody></table>`;
}

function route() {
  const page = location.hash === '#leaderboard' ? 'leaderboard' : 'play';
  $('play').hidden = page !== 'play';
  $('leaderboard').hidden = page !== 'leaderboard';
  $('tab-play').toggleAttribute('aria-current', page === 'play');
  $('tab-leaderboard').toggleAttribute('aria-current', page === 'leaderboard');
  document.querySelectorAll('nav a[aria-current]').forEach(a => a.setAttribute('aria-current', 'page'));
  if (page === 'leaderboard') showLeaderboard().catch(() => { $('humans').textContent = 'Could not load the leaderboard.'; });
  else { resize(); render(); }
}
addEventListener('hashchange', route);

async function start() {
  resend();
  drawStars();
  showSettings();
  route();
  fetch('/api/rules').then(r => r.text()).then(text => {
    $('rules').replaceChildren(...text.trim().split('\n').map(line => Object.assign(document.createElement('li'), { textContent: line })));
  });
  await Promise.all(SPRITES.map(name => new Promise(resolve => {
    images[name] = Object.assign(new Image(), { src: `sprites/${name}.png`, onload: resolve });
  })));
  newGame();
}
start();
