const $ = id => document.getElementById(id);
const TILE_SPRITES = { '.': 'floor', '#': 'wall', 'G': 'goal', 'T': 'teleporter', 't': 'exit', '~': 'smooth', 'D': 'drain' };
const SPRITES = [...Object.values(TILE_SPRITES), 'slider', 'clone', 'clone-disabled'];
const KEYS = { arrowup: 'U', arrowdown: 'D', arrowleft: 'L', arrowright: 'R', w: 'U', s: 'D', a: 'L', d: 'R',
               z: 'undo', b: 'undo', backspace: 'undo', r: 'reset' };
const ORIGINAL = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0];
// Movement matches the game's CloneManager2: speed 3.5 squares/s, growing by a factor of
// (1 + 4 × distance covered), so a step accelerates and takes about 115 ms.
const SPEED = 3.5, ACCELERATION = 4;
const STEP_MS = 1000 * Math.log(1 + ACCELERATION) / (SPEED * ACCELERATION);
const ART = 20;  // the sprites are drawn on a 20-pixel grid, so cells are multiples of it

const storage = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const settings = { set: 'benchmark', clones: '2', sliders: 'false', tier: 'easy', original: '1', ...storage.get('settings') };
const player = storage.get('player') ?? crypto.randomUUID();
storage.set('player', player);

const images = {};
let game = null, anim = null, prefetched = null, pending = null, cell = 2 * ART;

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
    data = await (settings.set === 'original' ? fetchJson(`/api/levels/dev-${settings.original}`) : nextBenchmark());
  } catch {
    if (request === pending) $('loading').textContent = 'Could not load a level. Check your connection and pick a level again.';
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
  return fetch('/api/plays', {
    method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level: game.id, player, attempt: game.number, actions: game.actions }),
  });
}

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
  $('undo').disabled = !game || solved();
  $('reset').disabled = !game;
  const canvas = $('board'), ctx = canvas.getContext('2d');
  ctx.setTransform(canvas.width / (canvas.clientWidth || 1), 0, 0, canvas.width / (canvas.clientWidth || 1), 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!game) return;
  const [rows, cols] = game.level.shape;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const sprite = TILE_SPRITES[game.level.tile(`${r},${c}`)];
      if (sprite) ctx.drawImage(images[sprite], c * cell, r * cell, cell, cell);
    }
  }
  const seconds = anim ? (performance.now() - anim.start) / 1000 : Infinity;
  const k = Math.min(1, (Math.exp(SPEED * ACCELERATION * seconds) - 1) / ACCELERATION);
  const draw = (sprite, from, to) => {
    const [r0, c0] = from.split(',').map(Number), [r1, c1] = to.split(',').map(Number);
    const t = Math.abs(r1 - r0) + Math.abs(c1 - c0) > 1 ? 1 : k;  // teleports jump
    ctx.drawImage(images[sprite], (c0 + (c1 - c0) * t) * cell, (r0 + (r1 - r0) * t) * cell, cell, cell);
  };
  if (anim) {
    anim.sliders.forEach(([from, to]) => draw('slider', from, to));
  } else {
    state().sliders.forEach(p => draw('slider', p, p));
  }
  state().clones.forEach((p, i) => {
    const stuck = !anim && game.level.tile(p) === 'D';
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

async function showLeaderboard() {
  const { humans } = await fetchJson('/api/leaderboard');
  if (!humans.length) {
    $('humans').innerHTML = '<p class="lede">No games yet. Play a benchmark level to start the baseline.</p>';
    return;
  }
  const pct = x => `${Math.round(x * 100)}%`;
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
