/* Gennemført 2.0: valid-as-tested engine across the product range (ETA-21/0110 board seals, ETA-20/1322 fire collars),
   browser port of src/gennemfoert/engine.py + intake.py + precedents.py (parity-tested against Python). */
(function (root) {
  const COVERS = { 'U/U': ['U/U', 'C/U', 'U/C', 'C/C'], 'C/U': ['C/U', 'C/C'], 'U/C': ['U/C', 'C/C'], 'C/C': ['C/C'] };
  const PLASTIC = ['pvc-u', 'pvc-c', 'pe', 'pp', 'pp-r', 'abs', 'san+pvc', 'composite'];
  const CHANGEABLE = ['isoleringstype', 'isoleringstykkelse', 'isoleringsfabrikat', 'hulstørrelse', 'kantafstand', 'fyldningsgrad', 'ringspalte'];
  const SEPARATION_MIN = 200, FILL_MAX = 0.6;
  const BRANDS = ['kaiflex', 'multitherm'];
  const COLLAR_ELASTOMERS = ['armaflex', 'kaiflex', 'k-flex'];
  const HOST_DA = { rigid_wall: 'massiv væg', flexible_wall: 'let væg', rigid_floor: 'massivt dæk' };
  const INS_DA = { none: 'ingen', stone_wool: 'stenuld', elastomeric: 'elastomer', multitherm: 'Multitherm', other: 'anden',
    pe_foam: 'PE-skum', pir: 'PIR/PUR', pe_conduit: 'PE-rør (kappe)', unknown: 'ukendt' };
  const CONF_DA = { perpendicular: 'vinkelret, almindelig', angled: 'skrå (45-90°)', elbow: 'bøjning', socket: 'muffe/kobling',
    zero_distance: 'nul afstand til dæk/væg', corner: 'i hjørne', conduit: 'i kabelrør/kappe', half_shell: 'med rørbærer-halvskal',
    multiple: 'flere rør samlet', flue: 'røgrør', in_board: 'i Multimastic FB1-plade', cast_in: 'støbt ind' };
  const COLLAR_CLIPS = [[90, 2], [160, 3], [200, 4], [285, 5], [315, 6]];
  const MAT = { 'pvc-u': 'pvc-u', 'pvc-c': 'pvc-c', 'pvc': 'pvc-u', 'upvc': 'pvc-u', 'pp-r': 'pp-r', 'pp-rct': 'pp-r', 'pp': 'pp', 'pe': 'pe',
    'pe-hd': 'pe', 'abs': 'abs', 'kobber': 'copper', 'copper': 'copper', 'cu': 'copper', 'stål': 'steel', 'steel': 'steel',
    'rustfrit stål': 'steel', 'stainless steel': 'steel', 'støbejern': 'steel', 'alupex': 'composite', 'pex-al-pex': 'composite',
    'composite': 'composite' };
  const MAT_KEYS = Object.keys(MAT).sort((a, b) => b.length - a.length);
  const COLLAR = 'Multicollar Slim';
  let RECORDS = [], NEXT = {}, BY_ID = {};

  // Python's round(): half to even (used for gaps and edges so both engines print the same numbers)
  function pyRound(x, nd) {
    const m = Math.pow(10, nd || 0), v = x * m, f = Math.floor(v), d = v - f;
    let r = d > 0.5 + 1e-9 ? f + 1 : d < 0.5 - 1e-9 ? f : (f % 2 === 0 ? f : f + 1);
    return r / m;
  }
  const fmt = v => (v === null || v === undefined) ? '–' : (typeof v === 'number' ? String(+v.toPrecision(6)) : String(v));
  const isNum = v => v !== null && v !== undefined;

  function normMaterial(name) {
    if (!name) return null;
    const n = name.toLowerCase();
    for (const k of MAT_KEYS) if (n.includes(k)) return MAT[k];
    return null;
  }
  function normInsulation(ins) {
    if (!ins) return { type: 'none' };
    const cat = (ins.category || ins.type || ins.product || '').toLowerCase();
    let t;
    if (cat.includes('sten') || cat.includes('stone') || cat.includes('mineral')) t = 'stone_wool';
    else if (['elast', 'kaiflex', 'armaflex', 'gummi', 'k-flex'].some(k => cat.includes(k))) t = 'elastomeric';
    else if (cat.includes('multitherm')) t = 'multitherm';
    else if (cat.includes('pir') || cat.includes('pur')) t = 'pir';
    else if (cat.includes('pe') && (cat.includes('skum') || cat.includes('foam'))) t = 'pe_foam';
    else if (cat === 'none' || cat === 'ingen') t = 'none';
    else t = 'other';
    return { type: t, thickness_mm: ins.thickness_mm ?? null, product: ins.product ?? null, extent: ins.extent || 'continuous' };
  }
  function load(records) {
    RECORDS = records; NEXT = {}; BY_ID = {};
    const groups = {};
    for (const r of records) {
      BY_ID[r.id] = r;
      const s = r.service;
      if (r.graph_page && s.material === 'steel' && s.od_min === s.od_max) {
        const k = r.section + '|' + r.classification.text + '|' + r.insulation.text;
        (groups[k] = groups[k] || []).push(r);
      }
    }
    for (const rows of Object.values(groups)) {
      const byOd = {};                                       // last row per Ø, as in engine.py
      for (const r of rows) byOd[r.service.od_max] = r;
      const sorted = Object.values(byOd).sort((a, b) => a.service.od_max - b.service.od_max);
      for (let i = 0; i + 1 < sorted.length; i++) NEXT[sorted[i].id] = sorted[i + 1];
    }
    return records.length;
  }
  function requiredConfig(material, open) {
    if (open === null || open === undefined || !material) return null;
    if (PLASTIC.includes(material)) return open ? 'U/C' : 'C/C';
    return open ? 'U/U' : 'C/U';
  }
  function outerDiameter(q) {
    const ins = q.insulation || {};
    return (q.bundle_mm || q.od_mm || 0) + 2 * (ins.thickness_mm || 0);
  }
  const collarClips = outer => { for (const [d, n] of COLLAR_CLIPS) if (outer <= d) return n; return 6; };

  function check(rec, q) {
    const s = rec.service, c = rec.classification, ins = rec.insulation, out = [];
    const add = (name, ok, actual, tested, note) => out.push({ check: name, ok: !!ok, actual, tested, note: note ?? null });
    const collar = rec.system === COLLAR;
    add('konstruktion', rec.hosts.includes(q.host_kind), HOST_DA[q.host_kind] || q.host_kind, rec.hosts.map(h => HOST_DA[h]).join(' / '));
    add('tykkelse', (q.thickness_mm || 0) >= rec.min_thickness, fmt(q.thickness_mm) + ' mm', '≥ ' + fmt(rec.min_thickness) + ' mm');
    const qconf = q.configuration || 'perpendicular';
    if (collar || qconf !== 'perpendicular') {
      const rc = rec.configuration || 'perpendicular';
      add('monteringssituation', qconf === rc, CONF_DA[qconf] || qconf, CONF_DA[rec.configuration] || rec.configuration);
    }
    const kind = q.service_kind;
    if (kind === 'pipe' || kind === 'conduit') {
      const od = q.od_mm, lo = s.od_min, hi = s.od_max;
      let note = null, wallMin = s.wall_min;
      let ok = isNum(od) && isNum(lo) && isNum(hi) && lo - 0.05 <= od && od <= hi + 0.05;
      const nb = NEXT[rec.id];
      if (!ok && isNum(od) && nb && hi < od && od < nb.service.od_max) {
        const f = (od - hi) / (nb.service.od_max - hi);
        wallMin = pyRound(s.wall_min + f * (nb.service.wall_min - s.wall_min), 2);
        ok = true; note = `mellemstørrelse via grafen s. ${rec.graph_page} (min. godstykkelse ${fmt(wallMin)} mm)`;
      }
      const tested = lo === hi ? 'Ø ' + fmt(hi) : (!lo ? 'Ø ≤ ' + fmt(hi) : 'Ø ' + fmt(lo) + '-' + fmt(hi));
      add('diameter', ok, 'Ø ' + fmt(od) + ' mm', tested + ' mm', note);
      if (isNum(s.wall_min)) {
        const w = q.wall_mm, wmax = s.wall_max;
        add('godstykkelse', isNum(w) && wallMin - 0.05 <= w && w <= wmax + 0.05, fmt(w) + ' mm',
          fmt(wallMin) + (wmax !== wallMin ? '-' + fmt(wmax) : '') + ' mm');
      }
    } else if (kind === 'cable' || kind === 'cable_bundle' || kind === 'wires') {
      const od = q.od_mm;
      add('diameter', isNum(od) && isNum(s.od_max) && od <= s.od_max, 'Ø ' + fmt(od) + ' mm', '≤ ' + fmt(s.od_max) + ' mm');
      if (kind === 'cable_bundle' && s.bundle_max) {
        const b = q.bundle_mm;
        add('bundtdiameter', isNum(b) && b <= s.bundle_max, 'Ø ' + fmt(b) + ' mm', '≤ ' + fmt(s.bundle_max) + ' mm');
      }
    }
    const qi = q.insulation || { type: 'none' };
    if (kind === 'pipe' || kind === 'conduit') {
      add('isoleringstype', qi.type === ins.type, INS_DA[qi.type] || qi.type, INS_DA[ins.type] || ins.type);
      if (ins.type !== 'none' && isNum(ins.t_min)) {
        const t = qi.thickness_mm;
        add('isoleringstykkelse', isNum(t) && (ins.t_min || 0) - 0.5 <= t && t <= (ins.t_max || 0) + 0.5, fmt(t) + ' mm',
          fmt(ins.t_min) + (ins.t_max !== ins.t_min ? '-' + fmt(ins.t_max) : '') + ' mm');
      }
      if (ins.type === 'elastomeric' && collar) {
        const prod = qi.product || '';
        add('isoleringsfabrikat', COLLAR_ELASTOMERS.some(b => prod.toLowerCase().includes(b)), prod || 'ukendt',
          'AF/SH Armaflex, Kaiflex ST/KKplus s2 eller K-Flex (ETA-20/1322 afsnit 2, pkt. 9)');
      } else {
        const brand = BRANDS.find(b => (ins.text || '').toLowerCase().includes(b));
        if (brand) {
          const prod = qi.product || '';
          add('isoleringsfabrikat', prod.toLowerCase().includes(brand), prod || 'ukendt', ins.text);
        }
      }
    }
    const ei = c.EI;
    add('klassifikation', isNum(ei) && ei >= (q.ei_required || 0), 'EI ' + fmt(q.ei_required) + ' krævet', c.text);
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
    if (ap && collar && rec.configuration !== 'in_board') {
      const gap = pyRound((Math.min(...ap) - outerDiameter(q)) / 2);
      if (q.host_kind === 'rigid_floor')
        add('ringspalte', true, gap + ' mm', '≤ 20 mm med fuge, større udfyldes helt med Multimortar (dæk)',
          gap > 20 ? 'Multimortar, fuldt udfyldt' : 'Multisealant A / Multimastic SP, dybde ≥ 10 mm');
      else add('ringspalte', gap <= 20, gap + ' mm', '≤ 20 mm, Multisealant A / Multimastic SP (ETA-20/1322 afsnit 1, pkt. 4)');
    }
    if (isNum(q.edge_mm) && rec.edge_min) add('kantafstand', q.edge_mm >= rec.edge_min, fmt(q.edge_mm) + ' mm', '≥ ' + fmt(rec.edge_min) + ' mm');
    if (isNum(q.separation_mm)) {
      const need = rec.between_min || (collar ? 100 : SEPARATION_MIN);
      add('afstand mellem tætninger', q.separation_mm >= need, fmt(q.separation_mm) + ' mm',
        '≥ ' + fmt(need) + ' mm (' + (collar ? 'ETA-20/1322 afsnit 1, pkt. 4' : 'ETA afsnit 2, pkt. 5') + ')');
    }
    if (isNum(q.fill) && !collar) add('fyldningsgrad', q.fill <= FILL_MAX, pyRound(q.fill * 100) + ' %', '≤ 60 % (ETA afsnit 2, pkt. 4)');
    return out;
  }
  function candidates(q) {
    const kind = q.service_kind, kinds = [kind];
    if (kind === 'cable_bundle') kinds.push('cable');
    return RECORDS.filter(r => {
      const s = r.service;
      if (!kinds.includes(s.kind)) return false;
      if (kind === 'cable_bundle' && s.kind === 'cable' && !s.text.toLowerCase().includes('bundled') && r.system !== COLLAR) return false;
      if (kind === 'pipe' || kind === 'conduit') {
        const mats = (s.materials || []).map(m => normMaterial(m) || m);
        if (!mats.includes(q.material)) return false;
      }
      return true;
    });
  }
  function missing(q) {
    const m = [];
    if (q.service_kind === 'pipe' || q.service_kind === 'conduit') {
      if (!q.material) m.push('Hvilket rørmateriale (fx PVC-U, PP, PE, kobber, stål, Alupex)?');
      if (!q.od_mm) m.push('Rørets udvendige diameter (mm)?');
      if (!isNum(q.wall_mm)) m.push('Rørets godstykkelse (mm)?');
      if (!isNum(q.open_system)) m.push('Er systemet åbent (afløb) eller lukket (brugsvand/varme)?');
      if (q.insulation_unknown) m.push('Er røret isoleret? Type, fabrikat og tykkelse?');
    }
    if (!q.ei_required) m.push('Hvilken brandmodstand kræves for væggen/dækket (fx EI 60)?');
    if (!q.thickness_mm) m.push('Væggens/dækkets tykkelse og opbygning?');
    return m;
  }
  function brief(r, checks, fails) {
    const b = r.board, ins = r.insulation || {};
    return { id: r.id, eta: r.eta, system: r.system, section: r.section, page: r.page, heading: r.heading, service: r.service.text,
      classification: r.classification.text, insulation: ins.text || '', insulation_length: ins.length ?? null,
      wrap: r.wrap !== undefined && r.wrap !== 'Not required' ? r.wrap : null,
      board: b ? `${b.type} ${b.layers}x${b.thickness} mm` : null, seal: (r.seal_max || {}).text ?? null,
      configuration: r.configuration, collars_per_face: r.collars_per_face ?? null, row_bbox: r.row_bbox ?? null, source: r.source,
      checks, deviates: fails || [] };
  }
  function cmpKey(a, b) {
    for (let i = 0; i < a.length; i++) {
      if (a[i] === b[i]) continue;
      if (typeof a[i] === 'string') return a[i] < b[i] ? -1 : 1;
      return a[i] - b[i];
    }
    return 0;
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
    const sizeGap = r => {
      const od = q.od_mm, s = r.service;
      if (!isNum(od) || !isNum(s.od_max)) return 0;
      const lo = s.od_min || 0;
      return (lo <= od && od <= s.od_max) ? 0 : Math.min(Math.abs(od - lo), Math.abs(od - s.od_max)) / od;
    };
    const wallGap = r => {
      const w = q.wall_mm, s = r.service;
      if (!isNum(w) || !isNum(s.wall_min) || r.system !== COLLAR) return 0;
      return (s.wall_min <= w && w <= s.wall_max) ? 0 : Math.min(Math.abs(w - s.wall_min), Math.abs(w - s.wall_max)) / Math.max(w, 0.1);
    };
    const key = x => {
      const r = x[0];
      const effort = r.board ? (r.board.layers ?? 0) : (r.collars_per_face || 1) * 0.5;
      return [x[2].length, pyRound(sizeGap(r), 3), pyRound(wallGap(r), 3), effort, -(r.classification.EI || 0), r.eta, r.page];
    };
    const sorted = arr => arr.map((x, i) => [x, key(x), i]).sort((a, b) => cmpKey(a[1], b[1]) || a[2] - b[2]).map(x => x[0]);
    const full = scored.filter(x => !x[2].length);
    if (full.length) {
      res.status = 'TESTET';
      res.matches = sorted(full).map(x => brief(x[0], x[1]));
    } else {
      const close = scored.filter(x => !['konstruktion', 'tykkelse', 'monteringssituation'].some(f => x[2].includes(f)) && x[2].length <= 2);
      if (close.length) {
        res.status = 'AFVIGELSE';
        res.nearest = sorted(close).slice(0, 3).map(x => brief(x[0], x[1], x[2]));
      } else {
        res.status = 'IKKE_DAEKKET';
        const sameHost = scored.filter(x => !x[2].includes('konstruktion') && !x[2].includes('tykkelse'));
        res.nearest = sorted(sameHost).slice(0, 2).map(x => brief(x[0], x[1], x[2]));
      }
      const alt = scored.filter(x => x[2].length && x[2].every(f => CHANGEABLE.includes(f)) && !x[2].includes('konstruktion'));
      res.alternatives = sorted(alt).slice(0, 3).map(x => brief(x[0], x[1], x[2]));
    }
    const best = res.matches[0] || null;
    const ref = best || res.nearest[0] || null;
    const C = res.conditions;
    if (ref && ref.system === COLLAR && q.material === 'composite')
      C.push('Komposit-rør: testet med navngivne fabrikater (fx Henco, Uponor, Geberit Mepla, REHAU, Wavin Tigris, Alpex DUO). Kontrollér rørfabrikatet mod ETA-20/1322 afsnit 2, pkt. 10.');
    if (best && best.insulation_length) C.push(`Testet med isolering: min. ${fmt(best.insulation_length)} mm længde (${best.eta} ${best.section}).`);
    if (best && best.wrap) C.push(`Mulcol Multiwrap: ${best.wrap} (${best.section}).`);
    if (best && best.board) C.push(`Tætning: Multimastic ${best.board}, Multimastic C (≤ 1 mm) og Multimastic SP i kanten (${best.section}, s. ${best.page}).`);
    if (best && best.system === COLLAR) {
      const n = best.collars_per_face || 1;
      const faces = q.host_kind === 'rigid_floor' ? 'på undersiden af dækket' : 'på begge sider af væggen';
      const clips = collarClips(outerDiameter(q));
      C.push(`Multicollar Slim: ${n} manchet${n > 1 ? 'ter' : ''} pr. side ${faces}, ${clips} Multiclips pr. manchet (${best.eta} ${best.section}, s. ${best.page}; afsnit 1, pkt. 5).`);
      C.push('Installationer understøttes højst 450 mm fra væggens begge sider / dækkets overside; min. 10 mm fra manchettens stålbånd til tilstødende konstruktion (ETA-20/1322 afsnit 1, pkt. 3 og afsnit 2, pkt. 3).');
    }
    if (q.hollow_core) C.push("Huldæk: ETA'erne forudsætter dæk af beton/letbeton ≥ 150 mm (densitet efter ETA'en). Kontrollér placering i forhold til huldækkets kanaler og ribber.");
    if (!best && ref && ref.system === COLLAR) C.push('Installationer understøttes højst 450 mm fra væggens begge sider / dækkets overside (ETA-20/1322 afsnit 1, pkt. 3).');
    else if (ref === null || ref.system !== COLLAR) {
      if (q.host_kind === 'rigid_floor') C.push('Installationer i dæk understøttes 250 mm og 400 mm fra dækkets overside (ETA-21/0110 afsnit 2, pkt. 6).');
      else if (['pipe', 'conduit', 'cable', 'cable_bundle'].includes(q.service_kind)) C.push('Installationer i væg understøttes 270 mm og 470 mm fra begge sider af væggen (ETA-21/0110 afsnit 2, pkt. 6).');
    }
    return res;
  }

  /* ---------- intake (intake.py) ---------- */
  const PHOTOS = { hul: 'Hullet/udsparingen med mål', installation: 'Røret/kablet med isolering og mærkning', konstruktion: 'Væg/dæk-opbygning (kant, lag)',
    oversigt: 'Oversigtsbillede af placeringen' };
  const REQUIRED = [['construction.kind', 3, 'Hvilken konstruktion (massivt dæk, massiv væg, let væg)?'], ['construction.thickness_mm', 2, 'Konstruktionens tykkelse (mm)?'],
    ['construction.ei_required', 3, 'Krævet brandmodstand (fx EI 60)?'], ['service.kind', 3, 'Hvilken installation (rør, kabel, kabelbakke, kanal)?'],
    ['service.material', 2, 'Rørmateriale?'], ['service.od_mm', 2, 'Udvendig diameter (mm)?'], ['service.wall_mm', 1, 'Godstykkelse (mm)?'],
    ['service.system', 1, 'Åbent (afløb) eller lukket (brugsvand/varme) system?'], ['service.insulation', 1, 'Isolering: type, fabrikat og tykkelse (eller ingen)?'],
    ['aperture_mm', 1, 'Hullets størrelse (mm)?']];
  const PIPE_ONLY = ['service.material', 'service.wall_mm', 'service.system', 'service.insulation'];
  const get = (d, path) => { for (const k of path.split('.')) { if (!d || typeof d !== 'object') return null; d = d[k]; } return d ?? null; };
  function itemQuery(item) {
    const c = item.construction || {}, s = item.service || {}, ins = s.insulation;
    const q = { host_kind: c.kind ?? null, thickness_mm: c.thickness_mm ?? null, ei_required: c.ei_required ?? null, hollow_core: !!c.hollow_core,
      service_kind: s.kind ?? null, material: normMaterial(s.material), od_mm: s.od_mm ?? null, wall_mm: s.wall_mm ?? null, bundle_mm: s.bundle_mm ?? null,
      open_system: isNum(s.system) ? s.system === 'open' : null, insulation: normInsulation(!ins || ins === 'none' ? null : ins),
      configuration: s.configuration || 'perpendicular' };
    if (item.aperture_mm) {
      const ap = item.aperture_mm; q.aperture_mm = ap;
      const tot = outerDiameter(q);
      q.edge_mm = pyRound((Math.min(...ap) - tot) / 2);
      q.fill = tot ? pyRound(3.14159 * tot * tot / 4 / (ap[0] * ap[1]), 3) : null;
    }
    if (isNum(item.separation_mm)) q.separation_mm = item.separation_mm;
    return q;
  }
  function completeness(item) {
    const s = item.service || {};
    let total = 0, have = 0; const miss = [];
    for (const [path, w, question] of REQUIRED) {
      if (path.startsWith('service.') && !['pipe', null, undefined].includes(s.kind) && PIPE_ONLY.includes(path)) continue;
      total += w;
      const v = get(item, path);
      if (v !== null && v !== '' && !(Array.isArray(v) && !v.length)) have += w; else miss.push(question);
    }
    const ph = item.photos || {};
    for (const [k, label] of Object.entries(PHOTOS)) { total += 1; if (ph[k]) have += 1; else miss.push('Foto: ' + label); }
    return [pyRound(100 * have / total), miss];
  }
  function precheck(item) {
    const q = itemQuery(item);
    if (!q.host_kind || !q.service_kind)
      return { status: 'MANGLER_DATA', questions: ['Konstruktion og installation skal angives.'], matches: [], nearest: [], alternatives: [], conditions: [] };
    return evaluate(q);
  }
  const regionFor = address => { const m = /\b(\d{4})\b/.exec(address || ''); return m && +m[1] >= 5000 ? 'VEST' : 'ØST'; };
  function triage(item) {
    const [score, miss] = completeness(item), v = precheck(item);
    let t = { TESTET: 'BESVARET_TESTET', MANGLER_DATA: 'MANGLER_INFO', ANDET_SYSTEM: 'ANDET_SYSTEM' }[v.status] || 'TIL_VURDERING';
    if ((v.status === 'AFVIGELSE' || v.status === 'IKKE_DAEKKET') && score < 70) t = 'MANGLER_INFO';
    return { completeness: score, missing: miss, verdict: v, triage: t };
  }

  /* ---------- precedents (precedents.py) ---------- */
  const FAMILY = { 'pvc-u': 'plast', 'pvc-c': 'plast', pe: 'plast', pp: 'plast', abs: 'plast', 'pp-r': 'plast', composite: 'komposit', copper: 'metal', steel: 'metal' };
  function signature(q, nearest) {
    const rec = nearest ? BY_ID[nearest.id] : null, out = [];
    for (const p of (nearest || {}).deviates || []) {
      let d = 'anden', m = null;
      if (rec) {
        const s = rec.service, ins = rec.insulation;
        if (p === 'diameter' && q.od_mm && s.od_max) {
          d = q.od_mm > s.od_max ? 'større' : 'mindre';
          m = q.od_mm > s.od_max ? pyRound(100 * (q.od_mm - s.od_max) / s.od_max) : pyRound(100 * (q.od_mm - (s.od_min || 0)) / Math.max(q.od_mm, 1));
        } else if (p === 'godstykkelse' && isNum(q.wall_mm) && isNum(s.wall_min)) {
          d = q.wall_mm < s.wall_min ? 'tyndere' : 'tykkere';
          const ref = d === 'tyndere' ? s.wall_min : s.wall_max; m = pyRound(100 * (q.wall_mm - ref) / ref);
        } else if (p === 'isoleringstykkelse' && isNum(ins.t_min)) {
          const t = (q.insulation || {}).thickness_mm || 0;
          d = t > ins.t_max ? 'tykkere' : 'tyndere';
          const ref = d === 'tykkere' ? ins.t_max : ins.t_min; m = pyRound(100 * (t - ref) / Math.max(ref, 1));
        } else if (p === 'klassifikation') { d = 'lavere'; m = (rec.classification.EI || 0) - (q.ei_required || 0); }
        else if (p === 'isoleringsfabrikat') d = 'andet fabrikat';
        else if (p === 'isoleringstype') d = `${(q.insulation || {}).type} i stedet for ${ins.type}`;
        else if (['afstand mellem tætninger', 'ringspalte', 'hulstørrelse', 'kantafstand'].includes(p)) d = 'geometri';
      }
      out.push({ param: p, direction: d, magnitude: m });
    }
    return out;
  }
  function precedentKey(q, sig) {
    return { host: q.host_kind, family: FAMILY[q.material] || q.service_kind, params: sig.map(s => s.param + ':' + s.direction).sort() };
  }
  function findPrecedents(q, nearest, library, limit) {
    const sig = signature(q, nearest), k = precedentKey(q, sig), hits = [];
    for (const p of library || []) {
      const pk = p.key;
      if (JSON.stringify(pk.params) !== JSON.stringify(k.params) || pk.host !== k.host) continue;
      let score = 3 + (pk.family === k.family ? 2 : 0);
      if (nearest && p.section === nearest.section) score += 2;
      const mags = sig.map(s => s.magnitude).filter(isNum), pm = p.signature.map(s => s.magnitude).filter(isNum);
      if (mags.length && pm.length) score -= Math.min(2, Math.abs(mags[0] - pm[0]) / 10);
      hits.push({ ...p, score: pyRound(score, 2) });
    }
    return { hits: hits.map((h, i) => [h, i]).sort((a, b) => b[0].score - a[0].score || a[1] - b[1]).map(x => x[0]).slice(0, limit || 3), signature: sig, key: k };
  }

  /* ---------- project register -> query (engine.query_from_penetration) ---------- */
  function queryFromPenetration(p) {
    const s = p.service, h = p.host, od = s.od_mm ?? null, ins = s.insulation;
    const q = { host_kind: h.kind, thickness_mm: h.thickness_mm, ei_required: h.ei_required, hollow_core: h.hollow_core ?? null, service_kind: s.kind,
      material: normMaterial(s.material), od_mm: od, wall_mm: s.wall_mm ?? null, bundle_mm: s.bundle_mm ?? null, open_system: s.open_system ?? null,
      insulation: normInsulation(ins), aperture_mm: p.aperture ?? p.aperture_mm ?? null, separation_mm: p.separation ?? p.separation_mm ?? null,
      configuration: p.configuration || 'perpendicular' };
    let dia, area, tw = 0, th = 0;
    if (s.kind === 'cable_tray') { tw = s.width_mm || 0; th = s.height_mm || 0; area = tw * th; dia = Math.max(tw, th); }
    else { const t = (ins || {}).thickness_mm || 0; dia = (s.bundle_mm || od || 0) + 2 * t; area = Math.PI * dia * dia / 4; }
    if (q.aperture_mm) {
      const [w, h2] = q.aperture_mm;
      q.edge_mm = pyRound((Math.min(w, h2) - (s.kind === 'cable_tray' ? Math.min(tw, th) : dia)) / 2);
      q.fill = w * h2 ? pyRound(area / (w * h2), 3) : null;
    }
    return q;
  }

  root.GEngine = { load, evaluate, check, normMaterial, normInsulation, outerDiameter, collarClips, queryFromPenetration, itemQuery, completeness,
    precheck, regionFor, triage, signature, precedentKey, findPrecedents, pyRound, fmt, records: () => RECORDS, record: id => BY_ID[id], next: id => NEXT[id],
    HOST_DA, INS_DA, CONF_DA, PHOTOS };
})(typeof window !== 'undefined' ? window : globalThis);
