/* Material list from tested solutions: browser port of src/gennemfoert/quote.py (parity-tested). */
(function (root) {
  const ITEMS = {
    FB1: { no: '6476478013', name: 'Mulcol Multimastic FB1 50 mm, 1-sidet brandplade', unit: 'stk', size_m2: 0.625 },
    FB2: { no: '6476478014', name: 'Mulcol Multimastic FB2 60 mm, 2-sidet brandplade', unit: 'stk', size_m2: 0.625 },
    SP: { no: '6476478010', name: 'Mulcol Multimastic SP akryl 310 ml brandfuge', unit: 'stk', ml: 310 },
    C6: { no: '6476477922', name: 'Mulcol Multimastic C coating 6 kg brandmaling', unit: 'stk' },
    COLLAR: { no: '6476477918', name: 'Mulcol Multicollar Slim 2600x30 mm brandmanchet (174 segmenter)', unit: 'rl', segments: 174 },
  };
  const FACTORS = { board_waste: 1.15, joint_mm2: 100.0, segment_mm: 2610 / 174, inlay_mm: 12.0, coat_kg_m2: 1.5 };
  const g = v => String(+v.toPrecision(6));
  const segmentsFor = (od, f) => Math.ceil(Math.PI * (od + 2 * f.inlay_mm) / f.segment_mm);
  function linesFor(item, best, faces, f) {
    const q = {}, ap = item.aperture_mm || [200, 200], add = (k, v) => { q[k] = (q[k] || 0) + v; };
    if (best.board) {
      const typ = best.board.split(' ')[0], layers = parseInt(best.board.split(' ')[1].split('x')[0]);
      add(typ, ap[0] * ap[1] / 1e6 * layers * f.board_waste);
      const joint = 2 * (ap[0] + ap[1]) / 1000 * 2;
      add('SP_ml', joint * f.joint_mm2);
      add('C_m2', ap[0] * ap[1] / 1e6 * (typ === 'FB2' || layers > 1 ? 2 : 1));
    }
    if (best.system === 'Multicollar Slim') {
      const n = (best.collars_per_face || 1) * faces;
      add('COLLAR_seg', n * segmentsFor(item.outer_d, f));
      add('clips', n * (item.clips || 2));
      const gap = (Math.min(...ap) - item.outer_d) / 2;
      if (gap <= 20) add('SP_ml', Math.PI * (item.outer_d + gap) * gap * 10 / 1000 * faces);
      else add('mortar_l', (ap[0] * ap[1] - Math.PI * item.outer_d ** 2 / 4) * item.thickness_mm / 1e6);
    }
    return q;
  }
  function materialList(solved, f) {
    f = f || FACTORS;
    const tot = {};
    for (const it of solved) for (const [k, v] of Object.entries(linesFor(it, it.best, it.faces, f))) tot[k] = (tot[k] || 0) + v;
    const out = [];
    for (const typ of ['FB1', 'FB2']) if (tot[typ]) {
      out.push({ ...ITEMS[typ], qty: Math.ceil(tot[typ] / ITEMS[typ].size_m2), basis: `${tot[typ].toFixed(2)} m² plade inkl. ${GEngine.pyRound((f.board_waste - 1) * 100)} % spild, plader á ${ITEMS[typ].size_m2} m²` });
    }
    if (tot.COLLAR_seg) out.push({ ...ITEMS.COLLAR, qty: Math.ceil(tot.COLLAR_seg / ITEMS.COLLAR.segments),
      basis: `${tot.COLLAR_seg.toFixed(0)} segmenter á ${f.segment_mm.toFixed(1)} mm (omkreds af rør inkl. isolering + 2x${f.inlay_mm.toFixed(0)} mm indlæg), ${tot.clips.toFixed(0)} Multiclips (følger med)` });
    if (tot.SP_ml) out.push({ ...ITEMS.SP, qty: Math.ceil(tot.SP_ml / ITEMS.SP.ml), basis: `${tot.SP_ml.toFixed(0)} ml fuge (kant/ringspalte, ${f.joint_mm2.toFixed(0)} mm² tværsnit)` });
    if (tot.C_m2) out.push({ ...ITEMS.C6, qty: Math.max(1, Math.ceil(tot.C_m2 * f.coat_kg_m2 / 6)),
      basis: `${tot.C_m2.toFixed(2)} m² pladeflade med ≤ 1 mm coating (mængde efter producentens anvisning; overslag ${g(f.coat_kg_m2)} kg/m²)` });
    if (tot.mortar_l) out.push({ no: '-', name: 'Mulcol Multimortar (brandmørtel)', unit: 'l', qty: GEngine.pyRound(tot.mortar_l, 1),
      basis: 'ringspalte i dæk udfyldes helt (ETA-20/1322 afsnit 1, pkt. 4); mængden følger modellens hul, et kernebor tæt på manchetten sparer mørtel; varenummer efter sortiment' });
    return out;
  }
  function solvedFromRegister(reg) {
    return reg.filter(p => p.status === 'TESTET').map(p => {
      const q = GEngine.queryFromPenetration(p), od = GEngine.outerDiameter(q);
      return { id: p.id, outer_d: od, thickness_mm: p.host.thickness_mm, aperture_mm: p.aperture || [200, 200],
        faces: p.host.kind === 'rigid_floor' ? 1 : 2, clips: GEngine.collarClips(od), best: p.matches[0], p };
    });
  }
  root.GQuote = { ITEMS, FACTORS, segmentsFor, linesFor, materialList, solvedFromRegister };
})(window);
