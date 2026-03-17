/* RaceBox — app.js
   All dashboard logic: tab switching, API calls, chart rendering.
*/

const API = '';  // same origin

// ── Team colours ──────────────────────────────────────────────────────────────
const TEAM_COLORS = {
  'Red Bull Racing':   '#3671C6',
  'Red Bull':          '#3671C6',
  'Ferrari':           '#E8002D',
  'Mercedes':          '#27F4D2',
  'McLaren':           '#FF8000',
  'Aston Martin':      '#229971',
  'Alpine':            '#FF87BC',
  'Williams':          '#64C4FF',
  'AlphaTauri':        '#5E8FAA',
  'RB':                '#6692FF',
  'Haas':              '#B6BABD',
  'Haas F1 Team':      '#B6BABD',
  'Alfa Romeo':        '#C92D4B',
  'Kick Sauber':       '#52E252',
  'Sauber':            '#52E252',
};

const COMPOUND_COLORS = {
  SOFT: '#e8192c', MEDIUM: '#f5a623', HARD: '#8888a0',
  INTER: '#4fa8f5', WET: '#93c5fd',
};

// State
let state = {
  year: 2024,
  gp: null,
  gpName: '',
  schedule: [],
  charts: {},
};

// ── Utils ──────────────────────────────────────────────────────────────────────
function fmt(s) {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(3).padStart(6, '0');
  return m > 0 ? `${m}:${sec}` : `${sec}s`;
}

function fmtDelta(s) {
  return (s > 0 ? '+' : '') + s.toFixed(3) + 's';
}

const log = (msg, type = '') => {
  const feed = document.getElementById('liveFeed');
  const now = new Date();
  const t = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const div = document.createElement('div');
  div.className = `feed-item ${type}`;
  div.innerHTML = `<span class="feed-time">${t}</span><span class="feed-msg">${msg}</span>`;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
};

function destroyChart(id) {
  if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; }
}

// ── Tab navigation ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    const view = document.getElementById('view-' + btn.dataset.view);
    if (view) view.classList.add('active');
  });
});

// ── Year / GP selectors ────────────────────────────────────────────────────────
document.getElementById('yearSelect').addEventListener('change', e => {
  state.year = parseInt(e.target.value);
  loadSchedule();
  loadStandings();
  loadConstructors();
});

document.getElementById('gpSelect').addEventListener('change', e => {
  const opt = e.target.selectedOptions[0];
  state.gp = parseInt(e.target.value);
  state.gpName = opt.text;
  document.getElementById('infoYear').textContent = state.year;
  document.getElementById('infoGP').textContent = state.gpName;
  document.getElementById('infoRound').textContent = state.gp;
  const date = opt.dataset.date || '—';
  document.getElementById('infoDate').textContent = date.slice(0, 10);
  log(`Selected: ${state.year} ${state.gpName}`);
  loadRaceResults();
});

// ── Schedule ───────────────────────────────────────────────────────────────────
async function loadSchedule() {
  const sel = document.getElementById('gpSelect');
  sel.innerHTML = '<option>Loading…</option>';
  try {
    const res = await fetch(`${API}/api/schedule/${state.year}`);
    const data = await res.json();
    state.schedule = data;
    sel.innerHTML = data.map(r =>
      `<option value="${r.RoundNumber}" data-date="${r.EventDate}">${r.EventName}</option>`
    ).join('');
    state.gp = data[0]?.RoundNumber || 1;
    state.gpName = data[0]?.EventName || '';
    sel.dispatchEvent(new Event('change'));
  } catch (e) {
    sel.innerHTML = '<option>Error loading schedule</option>';
    log('Failed to load schedule: ' + e.message, 'alert');
  }
}

// ── Driver standings (sidebar) ─────────────────────────────────────────────────
async function loadStandings() {
  const list = document.getElementById('standingsList');
  list.innerHTML = '<div class="loading-overlay"><span class="spinner"></span> Loading…</div>';
  try {
    const res = await fetch(`${API}/api/standings/drivers/${state.year}`);
    const data = await res.json();
    list.innerHTML = data.map(entry => {
      const drv = entry.Driver;
      const team = entry.Constructors?.[0]?.name || '';
      const color = TEAM_COLORS[team] || '#888';
      return `
        <div class="standing-row" title="${drv.givenName} ${drv.familyName} — ${team}">
          <span class="pos-num">${entry.position}</span>
          <span class="driver-code" style="color:${color}">${drv.code}</span>
          <span class="driver-name">${drv.familyName}</span>
          <span class="driver-pts">${entry.points}</span>
        </div>`;
    }).join('');
  } catch (e) {
    list.innerHTML = '<div style="padding:12px;color:var(--text3);font-size:11px">Could not load standings.<br>Check API server.</div>';
  }
}

// ── Constructors (right panel) ─────────────────────────────────────────────────
async function loadConstructors() {
  const el = document.getElementById('constructorList');
  try {
    const res = await fetch(`${API}/api/standings/constructors/${state.year}`);
    const data = await res.json();
    el.innerHTML = data.slice(0, 8).map(entry => {
      const team = entry.Constructor.name;
      const color = TEAM_COLORS[team] || '#666';
      const pts = parseFloat(entry.points);
      const maxPts = parseFloat(data[0].points) || 1;
      const pct = (pts / maxPts * 100).toFixed(0);
      return `
        <div style="display:grid;grid-template-columns:8px 1fr 40px;align-items:center;gap:6px;padding:2px 0">
          <div style="width:8px;height:8px;background:${color};border-radius:1px"></div>
          <div>
            <div style="font-size:10px;color:var(--text)">${team.replace('F1 Team','').trim()}</div>
            <div style="background:var(--bg3);height:3px;border-radius:2px;margin-top:2px;overflow:hidden">
              <div style="background:${color};height:100%;width:${pct}%"></div>
            </div>
          </div>
          <div style="font-size:10px;color:var(--amber);text-align:right">${pts}</div>
        </div>`;
    }).join('');
  } catch (e) {
    el.innerHTML = '<div style="color:var(--text3);font-size:10px;padding:4px">—</div>';
  }
}

// ── Race results ───────────────────────────────────────────────────────────────
async function loadRaceResults() {
  if (!state.gp) return;
  document.getElementById('resultsBody').innerHTML =
    '<tr><td colspan="5"><div class="loading-overlay"><span class="spinner"></span> Loading race data…</div></td></tr>';

  try {
    const res = await fetch(`${API}/api/race/${state.year}/${state.gp}/results`);
    const data = await res.json();

    const winner = data.find(r => r.Position == 1);
    const fastest = data.find(r => r.FastestLap);
    const dnfs = data.filter(r => r.Status && r.Status !== 'Finished' && !r.Status.match(/Lap/));

    document.getElementById('stat-winner').textContent = winner?.Abbreviation || '—';
    document.getElementById('stat-winner-team').textContent = winner?.TeamName || '—';
    document.getElementById('stat-fastest').textContent = fastest?.Abbreviation || '—';
    document.getElementById('stat-fastest-time').textContent = 'Fastest lap holder';
    document.getElementById('stat-laps').textContent = '—';
    document.getElementById('stat-circuit').textContent = state.gpName;
    document.getElementById('stat-dnf').textContent = dnfs.length;

    document.getElementById('resultsBody').innerHTML = data.map(r => {
      const color = TEAM_COLORS[r.TeamName] || '#666';
      const pos = parseInt(r.Position);
      const medal = pos === 1 ? '🥇' : pos === 2 ? '🥈' : pos === 3 ? '🥉' : pos;
      return `<tr>
        <td style="color:var(--amber)">${medal}</td>
        <td>
          <span style="color:${color};font-weight:600">${r.Abbreviation || r.DriverNumber}</span>
          <span style="color:var(--text2);margin-left:6px;font-size:10px">${r.FullName || ''}</span>
        </td>
        <td style="color:var(--text2)">${r.TeamName || '—'}</td>
        <td style="color:${r.Status === 'Finished' || r.Status?.match(/Lap/) ? 'var(--green)' : 'var(--red)'}">${r.Status || '—'}</td>
        <td style="color:var(--amber)">${r.Points || 0}</td>
      </tr>`;
    }).join('');

    log(`Race results loaded: ${state.gpName} ${state.year}`, 'pit');
    await loadLapChart();
  } catch (e) {
    document.getElementById('resultsBody').innerHTML =
      `<tr><td colspan="5" style="color:var(--red);padding:12px">${e.message}</td></tr>`;
    log('Failed to load results: ' + e.message, 'alert');
  }
}

// ── Lap time chart ─────────────────────────────────────────────────────────────
async function loadLapChart() {
  try {
    // Use top 5 from results
    const res = await fetch(`${API}/api/race/${state.year}/${state.gp}/results`);
    const results = await res.json();
    const top5 = results.filter(r => parseInt(r.Position) <= 5).map(r => r.Abbreviation);

    const paceRes = await fetch(`${API}/api/telemetry/${state.year}/${state.gp}/pace?drivers=${top5.join(',')}`);
    const paceData = await paceRes.json();

    destroyChart('lapChart');
    const ctx = document.getElementById('lapChart').getContext('2d');
    const colors = ['#e8192c', '#f5a623', '#00e5a0', '#4fa8f5', '#9d7df5'];

    const datasets = Object.entries(paceData).map(([drv, data], i) => ({
      label: drv,
      data: data.laps.map((l, j) => ({ x: l, y: data.times[j] })),
      borderColor: colors[i % colors.length],
      backgroundColor: 'transparent',
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
    }));

    state.charts.lapChart = new Chart(ctx, {
      type: 'scatter',
      data: { datasets },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: 'Lap', color: '#50505f', font: { size: 10 } }, ticks: { color: '#50505f', font: { size: 10 } }, grid: { color: '#2a2a35' } },
          y: { title: { display: true, text: 'Lap time (s)', color: '#50505f', font: { size: 10 } }, ticks: { color: '#50505f', font: { size: 10 }, callback: v => fmt(v) }, grid: { color: '#2a2a35' } },
        },
        plugins: {
          legend: { labels: { color: '#8888a0', font: { size: 10, family: "'IBM Plex Mono'" }, boxWidth: 12 } },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.dataset.label}: ${fmt(ctx.parsed.y)}`,
            },
          },
        },
      },
    });
    document.getElementById('lapChartDrivers').textContent = top5.join(' · ');
  } catch (e) {
    log('Lap chart: ' + e.message, 'alert');
  }
}

// ── Strategy comparison ────────────────────────────────────────────────────────
async function runStrategyComparison() {
  const laps = parseInt(document.getElementById('stratLaps').value);
  const base = parseFloat(document.getElementById('stratBase').value);
  log(`Running strategy comparison: ${laps} laps, ${base}s base`);

  document.getElementById('stratBody').innerHTML =
    '<tr><td colspan="5"><div class="loading-overlay"><span class="spinner"></span> Analysing strategies…</div></td></tr>';

  try {
    const res = await fetch(`${API}/api/strategy/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ race_laps: laps, base_lap_time: base }),
    });
    const strategies = await res.json();

    const best = strategies[0]?.total_race_time || 0;
    document.getElementById('stratCount').textContent = `${strategies.length} strategies evaluated`;

    document.getElementById('stratBody').innerHTML = strategies.slice(0, 15).map((s, i) => {
      const delta = s.total_race_time - best;
      const stintHtml = s.stints.map(st =>
        `<span class="compound-badge C-${st.compound}">${st.compound[0]}${st.length}</span>`
      ).join(' ');
      return `<tr class="${i === 0 ? 'best' : ''}">
        <td style="color:var(--text3)">${i + 1}</td>
        <td>${stintHtml}</td>
        <td>${s.pit_stops}</td>
        <td style="color:var(--green)">${fmt(s.total_race_time)}</td>
        <td style="color:${delta === 0 ? 'var(--green)' : 'var(--text2)'}">${delta === 0 ? '— optimal' : '+' + delta.toFixed(1) + 's'}</td>
      </tr>`;
    }).join('');

    renderDegChart(laps);
    renderStintChart(strategies.slice(0, 5), best);
    log(`Strategy analysis complete: optimal is ${strategies[0]?.label}`, 'pit');
  } catch (e) {
    document.getElementById('stratBody').innerHTML =
      `<tr><td colspan="5" style="color:var(--red);padding:12px">${e.message}</td></tr>`;
    log('Strategy error: ' + e.message, 'alert');
  }
}

function renderDegChart(laps) {
  destroyChart('degChart');
  const ctx = document.getElementById('degChart').getContext('2d');
  const compounds = { SOFT: 0.085, MEDIUM: 0.045, HARD: 0.022 };
  const base = parseFloat(document.getElementById('stratBase').value);
  const ages = Array.from({ length: Math.min(laps, 40) }, (_, i) => i);

  state.charts.degChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ages,
      datasets: Object.entries(compounds).map(([c, deg]) => ({
        label: c,
        data: ages.map(a => base + (c === 'SOFT' ? 0 : c === 'MEDIUM' ? 0.4 : 0.9) + deg * Math.pow(a, 1.12)),
        borderColor: COMPOUND_COLORS[c],
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.2,
      })),
    },
    options: chartDefaults({ x: 'Tyre age (laps)', y: 'Lap time (s)' }),
  });
}

function renderStintChart(strategies, best) {
  destroyChart('stintChart');
  const ctx = document.getElementById('stintChart').getContext('2d');
  const colors = ['#e8192c', '#f5a623', '#00e5a0', '#4fa8f5', '#9d7df5'];

  state.charts.stintChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: strategies.map(s => s.label),
      datasets: [{
        label: 'Race time delta (s)',
        data: strategies.map(s => +(s.total_race_time - best).toFixed(1)),
        backgroundColor: colors,
        borderRadius: 2,
      }],
    },
    options: {
      ...chartDefaults({ x: 'Strategy', y: 'Delta (s)' }),
      indexAxis: 'y',
    },
  });
}

// ── Simulation ─────────────────────────────────────────────────────────────────
async function runSimulation() {
  const n = parseInt(document.getElementById('simN').value);
  const laps = parseInt(document.getElementById('simLaps').value);
  log(`Running ${n} Monte Carlo simulations (${laps} laps)…`);
  document.getElementById('simMeta').textContent = 'Running…';

  document.getElementById('winProbList').innerHTML = '<div class="loading-overlay"><span class="spinner"></span> Simulating…</div>';
  document.getElementById('podiumProbList').innerHTML = '<div class="loading-overlay"><span class="spinner"></span></div>';

  try {
    const res = await fetch(`${API}/api/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        year: state.year,
        race_laps: laps,
        n_simulations: n,
      }),
    });
    const data = await res.json();
    const drivers = data.drivers.sort((a, b) => b.win_probability - a.win_probability);

    document.getElementById('simMeta').textContent =
      `${n} simulations · SC probability: ${(data.safety_car_probability * 100).toFixed(0)}%`;

    function renderBars(elId, drivers, key, color) {
      const max = Math.max(...drivers.map(d => d[key]));
      document.getElementById(elId).innerHTML = drivers.slice(0, 10).map(d => `
        <div class="prob-bar-row">
          <span style="color:var(--text);font-weight:600;font-size:11px">${d.driver}</span>
          <div class="prob-bar-bg">
            <div class="prob-bar-fill" style="width:${(d[key]/max*100).toFixed(1)}%;background:${color}"></div>
          </div>
          <span class="prob-bar-label">${(d[key]*100).toFixed(1)}%</span>
        </div>`).join('');
    }

    renderBars('winProbList', drivers, 'win_probability', 'var(--red)');
    renderBars('podiumProbList', drivers, 'podium_probability', 'var(--green)');
    renderSimHeatmap(data, drivers.slice(0, 10));
    log(`Simulation complete: ${drivers[0]?.driver} most likely to win (${(drivers[0]?.win_probability*100).toFixed(0)}%)`, 'pit');
  } catch (e) {
    document.getElementById('winProbList').innerHTML = `<div style="color:var(--red);padding:12px">${e.message}</div>`;
    log('Simulation error: ' + e.message, 'alert');
  }
}

function renderSimHeatmap(data, topDrivers) {
  destroyChart('simHeatmap');
  const ctx = document.getElementById('simHeatmap').getContext('2d');
  const positions = Array.from({ length: 10 }, (_, i) => `P${i + 1}`);
  const colors = [
    '#e8192c','#f5a623','#00e5a0','#4fa8f5','#9d7df5',
    '#f87171','#fbbf24','#34d399','#60a5fa','#a78bfa'
  ];

  state.charts.simHeatmap = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: positions,
      datasets: topDrivers.map((d, i) => ({
        label: d.driver,
        data: d.position_distribution.slice(0, 10).map(p => (p * 100).toFixed(1)),
        backgroundColor: colors[i % colors.length] + '99',
        borderColor: colors[i % colors.length],
        borderWidth: 1,
        borderRadius: 2,
      })),
    },
    options: {
      ...chartDefaults({ x: 'Finishing position', y: 'Probability (%)' }),
      scales: {
        x: { stacked: false, ticks: { color: '#50505f', font: { size: 10 } }, grid: { color: '#2a2a35' } },
        y: { ticks: { color: '#50505f', font: { size: 10 } }, grid: { color: '#2a2a35' } },
      },
    },
  });
}

// ── Telemetry ──────────────────────────────────────────────────────────────────
async function loadTelemetry() {
  const dA = document.getElementById('telDriverA').value.toUpperCase() || 'VER';
  const dB = document.getElementById('telDriverB').value.toUpperCase() || 'NOR';
  if (!state.gp) { log('Select a GP first', 'alert'); return; }

  log(`Loading telemetry: ${dA} vs ${dB} — ${state.gpName}`);
  try {
    const res = await fetch(`${API}/api/telemetry/${state.year}/${state.gp}/compare?driver_a=${dA}&driver_b=${dB}`);
    const data = await res.json();

    document.getElementById('telLapA').textContent = fmt(data.lap_time_a);
    document.getElementById('telLapB').textContent = fmt(data.lap_time_b);

    // Downsample for rendering
    const step = Math.max(1, Math.floor(data.distance.length / 300));
    const dist = data.distance.filter((_, i) => i % step === 0);
    const sA = data.speed_a.filter((_, i) => i % step === 0);
    const sB = data.speed_b.filter((_, i) => i % step === 0);
    const delta = data.delta_speed.filter((_, i) => i % step === 0);

    destroyChart('speedChart');
    const ctx1 = document.getElementById('speedChart').getContext('2d');
    state.charts.speedChart = new Chart(ctx1, {
      type: 'line',
      data: {
        labels: dist.map(d => d.toFixed(0)),
        datasets: [
          { label: dA, data: sA, borderColor: '#e8192c', backgroundColor: 'transparent', borderWidth: 1.5, pointRadius: 0, tension: 0.2 },
          { label: dB, data: sB, borderColor: '#4fa8f5', backgroundColor: 'transparent', borderWidth: 1.5, pointRadius: 0, tension: 0.2 },
        ],
      },
      options: chartDefaults({ x: 'Distance (m)', y: 'Speed (km/h)' }),
    });

    destroyChart('deltaChart');
    const ctx2 = document.getElementById('deltaChart').getContext('2d');
    state.charts.deltaChart = new Chart(ctx2, {
      type: 'line',
      data: {
        labels: dist.map(d => d.toFixed(0)),
        datasets: [{
          label: `${dA} − ${dB} speed delta`,
          data: delta,
          borderColor: '#9d7df5',
          backgroundColor: delta.map(v => v > 0 ? 'rgba(232,25,44,.15)' : 'rgba(79,168,245,.15)'),
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.2,
          fill: 'origin',
        }],
      },
      options: chartDefaults({ x: 'Distance (m)', y: 'Δ Speed (km/h)' }),
    });

    log(`Telemetry loaded: ${dA} ${fmt(data.lap_time_a)} | ${dB} ${fmt(data.lap_time_b)} | gap: ${fmtDelta(data.gap)}`, 'pit');
  } catch (e) {
    log('Telemetry error: ' + e.message, 'alert');
  }
}

// ── Championship ───────────────────────────────────────────────────────────────
async function loadChampionship() {
  const completedRounds = state.schedule.length > 0 ?
    Math.max(0, state.schedule.findIndex(r => r.RoundNumber === state.gp)) : 0;

  log(`Loading ${state.year} championship (${completedRounds} rounds completed)…`);
  document.getElementById('champBody').innerHTML =
    '<tr><td colspan="8"><div class="loading-overlay"><span class="spinner"></span></div></td></tr>';
  document.getElementById('titleProbList').innerHTML =
    '<div class="loading-overlay"><span class="spinner"></span></div>';

  try {
    const res = await fetch(`${API}/api/championship/${state.year}?completed_rounds=${completedRounds}&n_simulations=500`);
    const data = await res.json();

    const leader = data.standings[0];
    document.getElementById('champLeader').querySelector('.stat-value').textContent = leader?.code || '—';
    document.getElementById('champLeader').querySelector('.stat-sub').textContent =
      `${leader?.points} pts · ${leader?.wins} wins`;
    document.getElementById('champRounds').querySelector('.stat-value').textContent = data.rounds_remaining;
    document.getElementById('champRounds').querySelector('.stat-sub').textContent =
      `Rounds completed: ${completedRounds}`;
    document.getElementById('champPts').querySelector('.stat-value').textContent = data.max_points_available;
    document.getElementById('champPts').querySelector('.stat-sub').textContent = 'Including fastest lap bonuses';

    // Title prob bars
    const topDrivers = data.standings.slice(0, 8);
    const maxProb = Math.max(...topDrivers.map(d => d.title_probability)) || 1;
    document.getElementById('titleProbList').innerHTML = topDrivers.map(d => `
      <div class="prob-bar-row">
        <span style="color:var(--text);font-weight:600;font-size:11px">${d.code}</span>
        <div class="prob-bar-bg">
          <div class="prob-bar-fill" style="width:${(d.title_probability/maxProb*100).toFixed(1)}%;background:${d.eliminated ? 'var(--text3)' : 'var(--amber)'}"></div>
        </div>
        <span class="prob-bar-label">${(d.title_probability*100).toFixed(1)}%</span>
      </div>`).join('');

    // Table
    document.getElementById('champBody').innerHTML = data.standings.map(d => {
      const prob = (d.title_probability * 100).toFixed(1);
      return `<tr>
        <td style="color:var(--amber)">${d.position}</td>
        <td style="font-weight:600">${d.code}</td>
        <td style="color:var(--text2);font-size:10px">${d.team}</td>
        <td style="color:var(--amber)">${d.points}</td>
        <td>${d.wins}</td>
        <td style="color:${d.points_gap === 0 ? 'var(--green)' : 'var(--text3)'}">${d.points_gap === 0 ? 'Leader' : d.points_gap + 'pts'}</td>
        <td style="color:${parseFloat(prob) > 20 ? 'var(--green)' : parseFloat(prob) > 5 ? 'var(--amber)' : 'var(--text3)'}">${prob}%</td>
        <td style="font-size:10px;color:${d.eliminated ? 'var(--red)' : 'var(--green)'}">${d.eliminated ? 'Eliminated' : 'In contention'}</td>
      </tr>`;
    }).join('');

    renderChampChart(data.standings.slice(0, 6));
    log(`Championship loaded: ${leader?.name} leads with ${leader?.points} pts`, 'pit');
  } catch (e) {
    document.getElementById('champBody').innerHTML =
      `<tr><td colspan="8" style="color:var(--red);padding:12px">${e.message}</td></tr>`;
    log('Championship error: ' + e.message, 'alert');
  }
}

function renderChampChart(standings) {
  destroyChart('champChart');
  const ctx = document.getElementById('champChart').getContext('2d');
  const colors = ['#e8192c','#f5a623','#00e5a0','#4fa8f5','#9d7df5','#f87171'];

  state.charts.champChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: standings.map(d => d.code),
      datasets: [
        {
          label: 'Points',
          data: standings.map(d => d.points),
          backgroundColor: standings.map((_, i) => colors[i % colors.length] + 'cc'),
          borderColor: standings.map((_, i) => colors[i % colors.length]),
          borderWidth: 1,
          borderRadius: 3,
        },
        {
          label: 'Title %',
          data: standings.map(d => (d.title_probability * 100).toFixed(1)),
          backgroundColor: 'transparent',
          borderColor: '#9d7df5',
          borderWidth: 1.5,
          type: 'line',
          yAxisID: 'y2',
          pointRadius: 4,
          pointBackgroundColor: '#9d7df5',
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: { ticks: { color: '#50505f', font: { size: 10 } }, grid: { color: '#2a2a35' } },
        y: { ticks: { color: '#50505f', font: { size: 10 } }, grid: { color: '#2a2a35' }, title: { display: true, text: 'Points', color: '#50505f', font: { size: 10 } } },
        y2: { position: 'right', ticks: { color: '#9d7df5', font: { size: 10 }, callback: v => v + '%' }, grid: { display: false }, title: { display: true, text: 'Title %', color: '#9d7df5', font: { size: 10 } } },
      },
      plugins: {
        legend: { labels: { color: '#8888a0', font: { size: 10, family: "'IBM Plex Mono'" }, boxWidth: 12 } },
      },
    },
  });
}

// ── Chart defaults ─────────────────────────────────────────────────────────────
function chartDefaults({ x, y }) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: { title: { display: true, text: x, color: '#50505f', font: { size: 10 } }, ticks: { color: '#50505f', font: { size: 10 } }, grid: { color: '#2a2a35' } },
      y: { title: { display: true, text: y, color: '#50505f', font: { size: 10 } }, ticks: { color: '#50505f', font: { size: 10 } }, grid: { color: '#2a2a35' } },
    },
    plugins: {
      legend: { labels: { color: '#8888a0', font: { size: 10, family: "'IBM Plex Mono'" }, boxWidth: 12 } },
    },
  };
}

// ── Auto-load championship when that tab is clicked ────────────────────────────
document.querySelector('[data-view="championship"]').addEventListener('click', loadChampionship);

// ── Init ───────────────────────────────────────────────────────────────────────
(async () => {
  log('RaceBox initialising…');
  await loadSchedule();
  await loadStandings();
  await loadConstructors();
  log('Ready. Select a GP to begin.', 'pit');
})();
