/* Gennemført: valid-as-tested engine, browser port of src/gennemfoert/engine.py (parity-tested). */
(function (root) {
  const COVERS = { 'U/U': ['U/U', 'C/U', 'U/C', 'C/C'], 'C/U': ['C/U', 'C/C'], 'U/C': ['U/C', 'C/C'], 'C/C': ['C/C'] };
  const PLASTIC = ['pvc-u', 'pe', 'pp', 'composite'];
  const CHANGEABLE = ['isoleringstype', 'isoleringstykkelse', 'isoleringsfabrikat', 'hulstørrelse', 'kantafstand', 'fyldningsgrad'];
  const HOST_DA = { rigid_wall: 'massiv væg', flexible_wall: 'let væg', rigid_floor: 'massivt dæk' };
  const BRANDS = ['kaiflex', 'multitherm'];
  const INS_DA = { none: 'ingen', stone_wool: 'stenuld', elastomeric: 'elastomer', multitherm: 'Multitherm', other: 'anden' };
  const MAT = { 'pvc-u': 'pvc-u', 'pvc': 'pvc-u', 'upvc': 'pvc-u', 'pp': 'pp', 'pe': 'pe', 'pe-hd': 'pe', 'kobber': 'copper', 'copper': 'copper',
    'cu': 'copper', 'stål': 'steel', 'steel': 'steel', 'rustfrit stål': 'steel', 'stainless steel': 'steel', 'alupex': 'composite',
    'pex-al-pex': 'composite', 'composite': 'composite' };
  let RECORDS = [], NEXT = {};

  function normMaterial(name) {
    if (!name) return null;
    const n = name.toLowerCase();
    const keys = Object.keys(MAT).sort((a, b) => b.length - a.length);
    for (const k of keys) if (n.includes(k)) return MAT[k];
    return null;
  }
  function load(records) {
    RECORDS = records; NEXT = {};
    const groups = {};
    for (const r of records) {
      const s = r.service;
      if (r.graph_page && s.material === 'steel' && s.od_min === s.od_max) {
        const k = r.section + '|' + r.classification.text + '|' + r.insulation.text;
        (groups[k] = groups[k] || []).push(r);
      }
    }
    for (const rows of Object.values(groups)) {
      const u = {}; for (const r of rows) u[r.service.od_max] = r;                       // last row per Ø, as in engine.py
      const sorted = Object.values(u).sort((a, b) => a.service.od_max - b.service.od_max);
      for (let i = 0; i + 1 < sorted.length; i++) NEXT[sorted[i].id] = sorted[i + 1];
    }
  }
  const fmt = v => (v === null || v === undefined) ? '–' : (typeof v === 'number' ? String(+v.toFixed(6)) : String(v));
  function requiredConfig(material, open) {
    if (open === null || open === undefined || !material) return null;
    if (PLASTIC.includes(material)) return open ? 'U/C' : 'C/C';
    return open ? 'U/U' : 'C/U';
  }
  function check(rec, q) {
    const s = rec.service, c = rec.classification, ins = rec.insulation, out = [];
    const add = (name, ok, actual, tested, note) => out.push({ check: name, ok: !!ok, actual, tested, note: note || null });
    add('konstruktion', rec.hosts.includes(q.host_kind), HOST_DA[q.host_kind] || q.host_kind, rec.hosts.map(h => HOST_DA[h]).join(' / '));
    add('tykkelse', (q.thickness_mm || 0) >= rec.min_thickness, fmt(q.thickness_mm) + ' mm', '≥ ' + rec.min_thickness + ' mm');
    const kind = q.service_kind;
    if (kind === 'pipe' || kind === 'conduit') {
      const od = q.od_mm, lo = s.od_min, hi = s.od_max;
      let note = null, wallMin = s.wall_min;
      let ok = od != null && lo != null && lo - 0.05 <= od && od <= hi + 0.05;
      const nb = NEXT[rec.id];
      if (!ok && od != null && nb && hi < od && od < nb.service.od_max) {
        const f = (od - hi) / (nb.service.od_max - hi);
        wallMin = Math.round((s.wall_min + f * (nb.service.wall_min - s.wall_min)) * 100) / 100;
        ok = true; note = `mellemstørrelse via grafen s. ${rec.graph_page} (min. godstykkelse ${fmt(wallMin)} mm)`;
      }
      const tested = lo === hi ? 'Ø ' + fmt(hi) : (!lo ? 'Ø ≤ ' + fmt(hi) : 'Ø ' + fmt(lo) + '-' + fmt(hi));
      add('diameter', ok, 'Ø ' + fmt(od) + ' mm', tested + ' mm', note);
      if (s.wall_min !== null && s.wall_min !== undefined) {
        const w = q.wall_mm, wmax = s.wall_max;
        add('godstykkelse', w != null && wallMin - 0.05 <= w && w <= wmax + 0.05, fmt(w) + ' mm',
          fmt(wallMin) + (wmax !== wallMin ? '-' + fmt(wmax) : '') + ' mm');
      }
    } else if (kind === 'cable' || kind === 'cable_bundle' || kind === 'wires') {
      const od = q.od_mm;
      add('diameter', od != null && s.od_max != null && od <= s.od_max, 'Ø ' + fmt(od) + ' mm', '≤ ' + fmt(s.od_max) + ' mm');
      if (kind === 'cable_bundle' && s.bundle_max) {
        const b = q.bundle_mm;
        add('bundtdiameter', b != null && b <= s.bundle_max, 'Ø ' + fmt(b) + ' mm', '≤ ' + fmt(s.bundle_max) + ' mm');
      }
    }
    const qi = q.insulation || { type: 'none' };
    if (kind === 'pipe' || kind === 'conduit') {
      add('isoleringstype', qi.type === ins.type, INS_DA[qi.type] || qi.type, INS_DA[ins.type] || ins.type);
      if (ins.type !== 'none') {
        const t = qi.thickness_mm;
        add('isoleringstykkelse', t != null && (ins.t_min || 0) - 0.5 <= t && t <= (ins.t_max || 0) + 0.5, fmt(t) + ' mm',
          fmt(ins.t_min) + (ins.t_max !== ins.t_min ? '-' + fmt(ins.t_max) : '') + ' mm');
        const brand = BRANDS.find(b => ins.text.toLowerCase().includes(b));
        if (brand) {
          const prod = qi.product || '';
          add('isoleringsfabrikat', prod.toLowerCase().includes(brand), prod || 'ukendt', ins.text);
        }
      }
    }
    const ei = c.EI;
    add('klassifikation', ei != null && ei >= (q.ei_required || 0), 'EI ' + fmt(q.ei_required) + ' krævet', c.text);
    if (c.config && (kind === 'pipe' || kind === 'conduit')) {
      const need = requiredConfig(q.material, q.open_system);
      add('rørende', need !== null && COVERS[c.config].includes(need), need || 'ukendt (åbent/lukket system?)', c.config,
        q.open_system ? 'åbent system (afløb/ventilation)' : (q.open_system === false ? 'lukket system (brugsvand/varme)' : null));
    }
    const ap = q.aperture_mm, seal = rec.seal_max || {};
    if (ap && seal.h) {
      const big = Math.max(...ap), small = Math.min(...ap), sw = seal.w || 1e9, sh = seal.h;
      add('hulstørrelse', big <= Math.max(sw, sh) + 1 && small <= Math.min(sw, sh) + 1, ap[0] + ' x ' + ap[1] + ' mm', seal.text);
    }
    if (q.edge_mm != null && rec.edge_min) add('kantafstand', q.edge_mm >= rec.edge_min, fmt(q.edge_mm) + ' mm', '≥ ' + fmt(rec.edge_min) + ' mm');
    if (q.separation_mm != null) {
      const need = rec.between_min || 200;
      add('afstand mellem tætninger', q.separation_mm >= need, fmt(q.separation_mm) + ' mm', '≥ ' + fmt(need) + ' mm (ETA afsnit 2, pkt. 5)');
    }
    if (q.fill != null) add('fyldningsgrad', q.fill <= 0.6, Math.round(q.fill * 100) + ' %', '≤ 60 % (ETA afsnit 2, pkt. 4)');
    return out;
  }
  function candidates(q) {
    const kind = q.service_kind, kinds = [kind];
    if (kind === 'cable_bundle') kinds.push('cable');
    return RECORDS.filter(r => {
      const s = r.service;
      if (!kinds.includes(s.kind)) return false;
      if (kind === 'cable_bundle' && s.kind === 'cable' && !s.text.toLowerCase().includes('bundled')) return false;
      if (kind === 'pipe' || kind === 'conduit') {
        if (normMaterial(s.material || '') !== q.material && s.material !== q.material) return false;
      }
      return true;
    });
  }
  function missing(q) {
    const m = [];
    if (q.service_kind === 'pipe' || q.service_kind === 'conduit') {
      if (!q.material) m.push('Hvilket rørmateriale (fx PVC-U, PP, PE, kobber, stål, Alupex)?');
      if (!q.od_mm) m.push('Rørets udvendige diameter (mm)?');
      if (q.wall_mm === null || q.wall_mm === undefined) m.push('Rørets godstykkelse (mm)?');
      if (q.open_system === null || q.open_system === undefined) m.push('Er systemet åbent (afløb) eller lukket (brugsvand/varme)?');
    }
    if (!q.ei_required) m.push('Hvilken brandmodstand kræves for væggen/dækket (fx EI 60)?');
    if (!q.thickness_mm) m.push('Væggens/dækkets tykkelse og opbygning?');
    return m;
  }
  function brief(r, checks, fails) {
    const b = r.board;
    return { id: r.id, eta: r.eta, section: r.section, page: r.page, heading: r.heading, service: r.service, classification: r.classification,
      insulation: r.insulation, board: b ? `${b.type} ${b.layers}x${b.thickness} mm` : null, wrap: r.wrap !== 'Not required' ? r.wrap : null,
      seal: (r.seal_max || {}).text, row_bbox: r.row_bbox, source: r.source, deviates: fails || [],
      checks: checks.map(c => ({ c: c.check, ok: c.ok, a: c.actual, t: c.tested, n: c.note })) };
  }
  function evaluate(q) {
    const res = { status: null, matches: [], nearest: [], alternatives: [], conditions: [], questions: [] };
    if (q.service_kind === 'duct') {
      res.status = 'ANDET_SYSTEM';
      res.conditions.push('Ventilationskanal: brandspjæld eller brandisolering af kanalen (fx ROCKWOOL Conlit) efter dennes dokumentation. Ikke omfattet af en gennemføringstætning efter ETA-21/0110.');
      return res;
    }
    const miss = missing(q);
    if (miss.length) { res.status = 'MANGLER_DATA'; res.questions = miss; return res; }
    const scored = candidates(q).map(r => { const ch = check(r, q); return [r, ch, ch.filter(c => !c.ok).map(c => c.check)]; });
    const gap = r => {
      const od = q.od_mm, s = r.service;
      if (od == null || s.od_max == null) return 0;
      const lo = s.od_min || 0;
      return (lo <= od && od <= s.od_max) ? 0 : Math.min(Math.abs(od - lo), Math.abs(od - s.od_max)) / od;
    };
    const key = x => [x[2].length, Math.round(gap(x[0]) * 1000) / 1000, (x[0].board || {}).layers ?? 9, -(x[0].classification.EI || 0), x[0].page];
    const cmp = (a, b) => { const ka = key(a), kb = key(b); for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i]; return 0; };
    const stable = arr => arr.map((x, i) => [x, i]).sort((a, b) => cmp(a[0], b[0]) || a[1] - b[1]).map(x => x[0]);
    const full = scored.filter(x => !x[2].length);
    if (full.length) {
      res.status = 'TESTET';
      res.matches = stable(full).map(x => brief(x[0], x[1]));
    } else {
      const close = scored.filter(x => !x[2].includes('konstruktion') && !x[2].includes('tykkelse') && x[2].length <= 2);
      if (close.length) {
        res.status = 'AFVIGELSE';
        res.nearest = stable(close).slice(0, 3).map(x => brief(x[0], x[1], x[2]));
      } else {
        res.status = 'IKKE_DAEKKET';
        const sameHost = scored.filter(x => !x[2].includes('konstruktion') && !x[2].includes('tykkelse'));
        res.nearest = stable(sameHost).slice(0, 2).map(x => brief(x[0], x[1], x[2]));
      }
      const alt = scored.filter(x => x[2].length && x[2].every(f => CHANGEABLE.includes(f)) && !x[2].includes('konstruktion'));
      res.alternatives = stable(alt).slice(0, 2).map(x => brief(x[0], x[1], x[2]));
    }
    const best = res.matches[0];
    if (best && best.insulation.length) res.conditions.push(`Testet med lokal isolering: min. ${fmt(best.insulation.length)} mm længde (${best.section}).`);
    if (best && best.wrap) res.conditions.push(`Mulcol Multiwrap: ${best.wrap} (${best.section}).`);
    if (best && best.board) res.conditions.push(`Tætning: Multimastic ${best.board}, Multimastic C (≤ 1 mm) og Multimastic SP i kanten (${best.section}, s. ${best.page}).`);
    if (q.hollow_core) res.conditions.push("Huldæk: ETA'en forudsætter dæk af beton/letbeton ≥ 150 mm og ≥ 650 kg/m³. Kontrollér placering i forhold til huldækkets kanaler og ribber.");
    if (q.host_kind === 'rigid_floor') res.conditions.push('Installationer i dæk understøttes 250 mm og 400 mm fra dækkets overside (ETA afsnit 2, pkt. 6).');
    else if (['pipe', 'conduit', 'cable', 'cable_bundle'].includes(q.service_kind)) res.conditions.push('Installationer i væg understøttes 270 mm og 470 mm fra begge sider af væggen (ETA afsnit 2, pkt. 6).');
    return res;
  }
  root.GEngine = { load, evaluate, check, normMaterial };
})(typeof window !== 'undefined' ? window : globalThis);
