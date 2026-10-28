/* Gennemført 2.0 — shared page code: navigation, theme, data, verdict cards, audit chain (same hash as cases.py). */
(function (root) {
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const num = (v, d) => (v === null || v === undefined || v === '') ? '–' : Number(v).toLocaleString('da-DK', { maximumFractionDigits: d ?? 1 });

  const NAV = [['index.html', 'Overblik'], ['forespoergsel.html', 'Forespørgsel'], ['sager.html', 'Sager'], ['projekt.html', 'Projekt (BIM)'],
    ['tilbud.html', 'Tilbud'], ['udfoerelse.html', 'Udførelse'], ['overblik.html', 'Ledelse'], ['viden.html', 'Viden'], ['verify.html', 'Verificér']];
  const STATUS = { TESTET: 'Testet løsning', AFVIGELSE: 'Afvigelse: brandteknisk vurdering', IKKE_DAEKKET: "Ingen testet løsning i ETA'erne",
    ANDET_SYSTEM: 'Andet system (spjæld / kanalisolering)', MANGLER_DATA: 'Mangler data' };
  const SHORT = { TESTET: 'Testet', AFVIGELSE: 'Afvigelse', IKKE_DAEKKET: 'Ikke dækket', ANDET_SYSTEM: 'Andet system', MANGLER_DATA: 'Mangler data' };
  const ACTION = { TESTET: 'Udfør som testet. Følg betingelserne og dokumentér med foto.',
    AFVIGELSE: 'Brandteknisk vurdering af afvigelsen, eller ændr til den testede/alternative løsning.',
    IKKE_DAEKKET: 'Vælg et andet testet system eller få en brandteknisk vurdering.',
    ANDET_SYSTEM: 'Brandspjæld eller brandisolering af kanalen efter producentens dokumentation.',
    MANGLER_DATA: 'Indhent de manglende oplysninger hos projekterende/installatør.' };
  const COL = { TESTET: '--ok', AFVIGELSE: '--dev', IKKE_DAEKKET: '--bad', ANDET_SYSTEM: '--other', MANGLER_DATA: '--miss' };
  const ORDER = ['TESTET', 'AFVIGELSE', 'IKKE_DAEKKET', 'ANDET_SYSTEM', 'MANGLER_DATA'];
  const TRIAGE = { BESVARET_TESTET: ['Besvaret: testet', '--ok'], TIL_VURDERING: ['Til vurdering', '--dev'], MANGLER_INFO: ['Mangler info', '--miss'],
    ANDET_SYSTEM: ['Andet system', '--other'] };
  const CASE = { MODTAGET: 'Modtaget', MANGLER_INFO: 'Mangler oplysninger', TIL_VURDERING: 'Til vurdering', UDKAST: 'Udkast',
    TIL_KONTROL: 'Til kontrol (4 øjne)', UDSENDT: 'Udsendt', BESVARET: 'Besvaret (testet løsning)', ARKIVERET: 'Arkiveret', AFVIST: 'Afvist' };
  const CASE_FLOW = ['MODTAGET', 'TIL_VURDERING', 'UDKAST', 'TIL_KONTROL', 'UDSENDT', 'ARKIVERET'];
  const HOST = { rigid_wall: 'Massiv væg', flexible_wall: 'Let væg', rigid_floor: 'Massivt dæk' };
  const DISCLAIMER = 'Beslutningsstøtte, ikke godkendelse. Hver løsning kontrolleres mod kildedokumentet (ETA-21/0110, ETA-20/1322) og producentens monteringsvejledning. En brandteknisk vurdering udarbejdes og underskrives af en person.';

  /* ---------- storage (per-viewer conveniences and local demo state only) ---------- */
  const store = {
    get(k, d) { try { const v = localStorage.getItem('gf2-' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('gf2-' + k, JSON.stringify(v)); return true; } catch (e) { return false; } },
    del(k) { try { localStorage.removeItem('gf2-' + k); } catch (e) { } }
  };

  /* ---------- theme + navigation ---------- */
  const t0 = store.get('theme', null); if (t0) document.documentElement.dataset.theme = t0;
  function isDark() { return css('--bg') === '#0c0e12'; }
  function nav() {
    const page = (location.pathname.split('/').pop() || 'index.html');
    const el = document.createElement('header'); el.className = 'top';
    el.innerHTML = `<a class="brand" href="index.html"><i></i><span>Gennemført<sup>2.0</sup></span></a>
      <nav class="nav">${NAV.map(([h, l]) => `<a href="${h}" class="${h === page ? 'on' : ''}">${l}</a>`).join('')}</nav>
      <button class="iconbtn" id="themebtn" title="Lys / mørk" aria-label="Skift lys/mørk">◐</button>`;
    document.body.prepend(el);
    $('#themebtn').onclick = () => { const r = document.documentElement; r.dataset.theme = isDark() ? 'light' : 'dark'; store.set('theme', r.dataset.theme);
      document.dispatchEvent(new Event('themechange')); };
    const on = $('.nav a.on'); if (on) on.scrollIntoView({ block: 'nearest', inline: 'center' });
  }

  /* ---------- data ---------- */
  const cache = {};
  const load = (...names) => Promise.all(names.map(n => cache[n] || (cache[n] = fetch('data/' + n + '.json').then(r => { if (!r.ok) throw new Error(n); return r.json(); }))));
  let SUMMARY = null;
  async function engineReady() {
    const [s, recs] = await load('summary', 'records');
    SUMMARY = s; GEngine.load(recs); return s;
  }

  /* ---------- verdict rendering (engine brief format) ---------- */
  const badge = st => `<span class="badge" style="background:var(${COL[st]})">${esc(SHORT[st] || st)}</span>`;
  const triageBadge = t => { const [l, c] = TRIAGE[t] || [t, '--miss']; return `<span class="pill"><i style="background:var(${c})"></i>${esc(l)}</span>`; };
  const caseBadge = s => `<span class="pill"><i style="background:var(${s === 'UDSENDT' || s === 'BESVARET' || s === 'ARKIVERET' ? '--ok' : s === 'MANGLER_INFO' ? '--miss' : s === 'AFVIST' ? '--bad' : '--dev'})"></i>${esc(CASE[s] || s)}</span>`;
  function etaImg(ref) {
    const pages = SUMMARY && SUMMARY.eta.pages[ref.eta]; const m = pages && pages[ref.page]; if (!m) return '';
    let hl = '';
    if (ref.row_bbox) {
      const top = (ref.row_bbox[1] - m.y0) / m.h * 100, h = (ref.row_bbox[3] - ref.row_bbox[1]) / m.h * 100;
      hl = `<div class="hl" style="top:${top}%;height:${h}%"></div>`;
    }
    return `<div class="etaimg"><img loading="lazy" src="data/eta/${m.dir}/p${ref.page}.jpg" alt="${esc(ref.eta)} side ${ref.page}">${hl}<span class="cap">${esc(ref.eta)} · ${esc(ref.section)} · side ${ref.page}</span></div>`;
  }
  function checksHTML(ref) {
    return `<table class="chk"><tr><th>Parameter</th><th>Projekteret</th><th>Testet</th><th></th></tr>` + ref.checks.map(c =>
      `<tr class="${c.ok ? '' : 'bad'}"><td>${esc(c.check)}</td><td>${esc(c.actual)}</td><td>${esc(c.tested)}${c.note ? `<div class="note">${esc(c.note)}</div>` : ''}</td><td class="${c.ok ? 'ok' : 'no'}">${c.ok ? '✓' : '✗'}</td></tr>`).join('') + '</table>';
  }
  function solLine(ref) {
    const what = ref.board ? 'Multimastic ' + ref.board : ref.system === 'Multicollar Slim' ? `Multicollar Slim, ${ref.collars_per_face || 1} pr. side` : ref.system;
    const conf = ref.configuration && ref.configuration !== 'perpendicular' ? ' · ' + (GEngine.CONF_DA[ref.configuration] || ref.configuration) : '';
    return `${esc(ref.classification)} · ${esc(what)}${conf}${ref.insulation && ref.insulation !== 'None' ? ' · ' + esc(ref.insulation) : ''}${ref.wrap ? ' · Multiwrap ' + esc(ref.wrap) : ''}`;
  }
  function refHTML(ref, title, opts) {
    opts = opts || {};
    const sys = SUMMARY && SUMMARY.kb.systems.find(s => s.eta === ref.eta);
    const src = sys ? ` · <a href="${esc(sys.url)}#page=${ref.page}" target="_blank" rel="noopener" title="Kildedokumentet på den citerede side">åbn kilden ↗</a>` : '';
    return `<div class="sec"><h3>${title}</h3><div class="sol"><div class="ref">${esc(ref.eta)} ${esc(ref.section)} · side ${ref.page}${ref.source === 'override' ? ' · række indtastet og kontrolleret' : ''}${src}</div>
      <div style="margin-top:4px"><b>${esc(ref.service)}</b></div><div class="sub">${solLine(ref)}</div>
      ${opts.noimg ? '' : etaImg(ref)}${opts.nochecks ? '' : checksHTML(ref)}</div></div>`;
  }
  function verdictHTML(v, o) {
    o = o || {};
    let h = `<div>${badge(v.status)} <span class="sub" style="margin-left:6px">${esc(STATUS[v.status])}</span></div>`;
    if (o.title) h = `<h2 style="margin:8px 0 2px">${esc(o.title)}</h2>${o.sub ? `<div class="sub">${o.sub}</div>` : ''}` + h;
    h += `<div class="sec"><h3>Handling</h3><div>${esc(ACTION[v.status])}</div></div>`;
    if (v.matches && v.matches.length) {
      const sys = [...new Set(v.matches.map(m => m.system))];
      h += refHTML(v.matches[0], `Testet løsning${v.matches.length > 1 ? ` (1 af ${v.matches.length} der passer${sys.length > 1 ? ', i ' + sys.join(' og ') : ''})` : ''}`, o);
    }
    if (v.nearest && v.nearest.length) h += refHTML(v.nearest[0], v.status === 'AFVIGELSE' ? 'Nærmeste testede opbygning: afviger på ' + esc(v.nearest[0].deviates.join(', ')) : 'Nærmeste i samme konstruktion', o);
    if (v.alternatives && v.alternatives.length && !o.noalt) {
      h += `<div class="sec"><h3>Testede alternativer</h3>` + v.alternatives.map(a => `<div class="sol" style="margin-bottom:6px"><div class="ref">${esc(a.eta)} ${esc(a.section)} · side ${a.page}</div>
        <div class="sub">${solLine(a)}</div><div class="note">Kræver ændring af: ${esc(a.deviates.join(', '))}</div></div>`).join('') + '</div>';
    }
    if (v.questions && v.questions.length) h += `<div class="sec"><h3>Spørgsmål</h3><ul class="cond">${v.questions.map(q => `<li>${esc(q)}</li>`).join('')}</ul></div>`;
    if (v.conditions && v.conditions.length) h += `<div class="sec"><h3>Betingelser og noter</h3><ul class="cond">${v.conditions.map(q => `<li>${esc(q)}</li>`).join('')}</ul></div>`;
    if (!o.nodisc) h += `<div class="disc">${esc(DISCLAIMER)}</div>`;
    return h;
  }

  /* ---------- audit chain: identical to cases._hash (json.dumps sort_keys, ensure_ascii=False) ---------- */
  function pyDumps(x) {
    if (x === null || x === undefined) return 'null';
    if (typeof x === 'boolean') return x ? 'true' : 'false';
    if (typeof x === 'number') return Number.isInteger(x) ? String(x) : String(x);
    if (typeof x === 'string') return JSON.stringify(x);
    if (Array.isArray(x)) return '[' + x.map(pyDumps).join(', ') + ']';
    const keys = Object.keys(x).sort((a, b) => a < b ? -1 : a > b ? 1 : 0);   // code-point order, as Python
    return '{' + keys.map(k => JSON.stringify(k) + ': ' + pyDumps(x[k])).join(', ') + '}';
  }
  async function sha256(s) {
    const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
    return Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join('');
  }
  async function eventHash(prev, ev) { const { hash, ...body } = ev; return sha256(prev + pyDumps(body)); }
  async function verifyChain(events) {
    let prev = '0'.repeat(64); const res = [];
    for (const ev of events) { const h = await eventHash(prev, ev); res.push(h === ev.hash); prev = ev.hash; }
    return { ok: res.every(Boolean), each: res };
  }
  async function appendEvent(c, actor, action, detail, kb) {
    const prev = c.events.length ? c.events[c.events.length - 1].hash : '0'.repeat(64);
    const now = new Date(); now.setMilliseconds(0);
    const pad = n => String(n).padStart(2, '0');
    const at = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    const ev = { at, actor, action, detail: detail || {}, kb: kb || null, state: c.status };
    ev.hash = await eventHash(prev, ev); c.events.push(ev); return ev;
  }

  /* ---------- tooltip ---------- */
  let tipEl = null;
  function tip(html, e) {
    if (!tipEl) { tipEl = document.createElement('div'); tipEl.className = 'tip'; document.body.appendChild(tipEl); }
    if (!html) { tipEl.style.display = 'none'; return; }
    tipEl.innerHTML = html; tipEl.style.display = 'block';
    const x = Math.min(e.clientX + 14, innerWidth - tipEl.offsetWidth - 8), y = Math.min(e.clientY + 14, innerHeight - tipEl.offsetHeight - 8);
    tipEl.style.left = x + 'px'; tipEl.style.top = y + 'px';
  }
  function download(name, text, type) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/plain' })); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  root.GF = { $, $$, esc, css, num, nav, load, engineReady, store, isDark, badge, triageBadge, caseBadge, etaImg, checksHTML, refHTML, verdictHTML, solLine,
    pyDumps, sha256, verifyChain, appendEvent, tip, download, STATUS, SHORT, ACTION, COL, ORDER, TRIAGE, CASE, CASE_FLOW, HOST, DISCLAIMER,
    summary: () => SUMMARY };
  document.addEventListener('DOMContentLoaded', nav);
})(window);
