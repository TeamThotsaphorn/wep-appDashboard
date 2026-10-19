/* EEC Seafood Operations — static web app over JSON exported by src/11_export_web_data.py */
(() => {
  'use strict';

  // ---------------------------------------------------------------- helpers
  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === 'class') n.className = v; else if (k === 'text') n.textContent = v; else n.setAttribute(k, v);
    }
    kids.flat().forEach((k) => k != null && n.append(k));
    return n;
  };
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const f0 = d3.format(',.0f'), f1 = d3.format(',.1f'), f2 = d3.format(',.2f'), pct = d3.format('.1%');
  const fmtNum = (v, f = f0) => (v == null || Number.isNaN(v) ? '–' : f(v));
  const parseMonth = d3.utcParse('%Y-%m');
  const parseDay = d3.utcParse('%Y-%m-%d');
  const thDate = (d, opt = { day: 'numeric', month: 'short', year: 'numeric' }) => d.toLocaleDateString('th-TH', { timeZone: 'UTC', ...opt });
  const thDateTime = (iso) => new Date(iso).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' });
  const thMonth = (d) => d.toLocaleDateString('th-TH', { timeZone: 'UTC', month: 'short', year: 'numeric' });
  const sum = (a, f) => a.reduce((s, x) => s + (f(x) || 0), 0);
  const zip = (cols, rows) => rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  // ---------------------------------------------------------------- tooltip
  function tooltip(box) {
    let t = box.querySelector(':scope > .tip');
    if (!t) { t = el('div', { class: 'tip', role: 'status' }); box.append(t); }
    return {
      show(ev, head, lines) {
        t.replaceChildren(el('div', { class: 't-head', text: head }), ...lines.map((l) => el('div', { class: 't-val', text: l })));
        const r = box.getBoundingClientRect();
        t.style.opacity = 1;
        let x = ev.clientX - r.left + 14, y = ev.clientY - r.top - t.offsetHeight - 8;
        if (x + t.offsetWidth > r.width) x = ev.clientX - r.left - t.offsetWidth - 14;
        t.style.left = Math.max(0, x) + 'px';
        t.style.top = (y < 0 ? ev.clientY - r.top + 16 : y) + 'px';
      },
      hide() { t.style.opacity = 0; },
    };
  }

  function svgIn(box, h) {
    const w = Math.max(280, box.clientWidth);
    d3.select(box).selectAll('svg').remove();
    const svg = d3.select(box).insert('svg', ':first-child').attr('viewBox', `0 0 ${w} ${h}`).attr('height', h);
    return { svg, w, h };
  }
  function textWidth(svg, labels, size = 11) {
    const p = svg.append('text').attr('class', 'axis-label').style('font-size', size + 'px');
    let w = 0;
    labels.forEach((s) => { p.text(s); w = Math.max(w, p.node().getComputedTextLength()); });
    p.remove();
    return Math.ceil(w);
  }
  function yGrid(svg, y, x0, x1, fmt, ticks = 4) {
    const g = svg.append('g');
    y.ticks(ticks).forEach((v) => {
      g.append('line').attr('class', 'gridline').attr('x1', x0).attr('x2', x1).attr('y1', y(v)).attr('y2', y(v));
      g.append('text').attr('class', 'axis-label').attr('x', x0 - 8).attr('y', y(v)).attr('dy', '0.32em').attr('text-anchor', 'end').text(fmt(v));
    });
  }

  // Monthly bars: data [{d: Date, v: number}]
  function barTime(box, data, { fmt = f0, unit = '', h = 240, extra } = {}) {
    if (!data.length) { box.replaceChildren(el('div', { class: 'loading', text: 'ไม่มีข้อมูลตามตัวกรอง' })); return; }
    const { svg, w } = svgIn(box, h);
    const lo = Math.min(0, d3.min(data, (d) => d.v)), hi = Math.max(0, d3.max(data, (d) => d.v));
    const y = d3.scaleLinear([lo, hi || 1], [h - 26, 10]).nice();
    const ml = textWidth(svg, y.ticks(4).map(fmt)) + 14;
    const x = d3.scaleBand(data.map((d) => +d.d), [ml, w - 4]).paddingInner(data.length > 30 ? 0.18 : 0.3);
    yGrid(svg, y, ml, w - 4, fmt);
    svg.append('line').attr('class', 'baseline').attr('x1', ml).attr('x2', w - 4).attr('y1', y(0)).attr('y2', y(0));
    const accent = css('--accent'), bad = css('--bad');
    const bars = svg.append('g').selectAll('rect').data(data).join('rect')
      .attr('x', (d) => x(+d.d)).attr('width', x.bandwidth())
      .attr('y', (d) => y(Math.max(0, d.v))).attr('height', (d) => Math.max(1, Math.abs(y(d.v) - y(0))))
      .attr('rx', Math.min(3, x.bandwidth() / 2)).attr('fill', (d) => (d.v < 0 ? bad : accent));
    // year (or month) labels
    const span = data.length;
    const lab = data.filter((d, i) => (span > 18 ? d.d.getUTCMonth() === 0 || i === 0 : i % Math.ceil(span / 8) === 0));
    svg.append('g').selectAll('text').data(lab).join('text').attr('class', 'axis-label')
      .attr('x', (d) => x(+d.d)).attr('y', h - 8)
      .text((d) => (span > 18 ? d.d.getUTCFullYear() + 543 : thMonth(d.d)));
    const tip = tooltip(box);
    svg.append('g').selectAll('rect').data(data).join('rect')
      .attr('x', (d) => x(+d.d) - x.step() * x.paddingInner() / 2).attr('width', x.step()).attr('y', 0).attr('height', h - 20)
      .attr('fill', 'transparent')
      .on('mousemove', (ev, d) => {
        bars.attr('opacity', (b) => (b === d ? 1 : 0.55));
        tip.show(ev, thMonth(d.d), [`${fmt(d.v)} ${unit}`.trim(), ...(extra ? extra(d) : [])]);
      })
      .on('mouseleave', () => { bars.attr('opacity', 1); tip.hide(); });
  }

  // Horizontal bars: rows [{label, v, tip?}]
  function hbar(box, rows, { fmt = f0, unit = '' } = {}) {
    const row = 26, h = rows.length * row + 8;
    const { svg, w } = svgIn(box, h);
    const lw = Math.min(textWidth(svg, rows.map((r) => r.label), 12) + 12, w * 0.42);
    const vw = textWidth(svg, rows.map((r) => fmt(r.v))) + 10;
    const x = d3.scaleLinear([0, d3.max(rows, (r) => r.v) || 1], [lw, w - vw]);
    const accent = css('--accent');
    const tip = tooltip(box);
    const g = svg.selectAll('g.r').data(rows).join('g').attr('class', 'r').attr('transform', (d, i) => `translate(0,${i * row + 4})`);
    g.append('text').attr('class', 'axis-label').style('font-size', '12px').style('fill', css('--ink'))
      .attr('x', lw - 10).attr('y', row / 2 - 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((d) => d.label);
    g.append('rect').attr('x', lw).attr('y', 4).attr('height', row - 12).attr('rx', 3)
      .attr('width', (d) => Math.max(1, x(d.v) - lw)).attr('fill', accent);
    g.append('text').attr('class', 'axis-label').attr('x', (d) => x(d.v) + 6).attr('y', row / 2 - 2).attr('dy', '0.32em').text((d) => fmt(d.v));
    g.append('rect').attr('x', 0).attr('width', w).attr('height', row).attr('y', -2).attr('fill', 'transparent')
      .on('mousemove', (ev, d) => tip.show(ev, d.label, d.tip || [`${fmt(d.v)} ${unit}`.trim()]))
      .on('mouseleave', () => tip.hide());
  }

  // Vertical category bars with value labels: rows [{label, v, tip}]
  function vbar(box, rows, { fmt = f0, h = 240 } = {}) {
    const { svg, w } = svgIn(box, h);
    const y = d3.scaleLinear([0, (d3.max(rows, (r) => r.v) || 1) * 1.15], [h - 28, 12]);
    const ml = textWidth(svg, y.ticks(4).map(fmt)) + 14;
    const x = d3.scaleBand(rows.map((r) => r.label), [ml, w - 4]).padding(0.3);
    yGrid(svg, y, ml, w - 4, fmt);
    const tip = tooltip(box);
    svg.append('g').selectAll('rect').data(rows).join('rect')
      .attr('x', (d) => x(d.label)).attr('width', x.bandwidth()).attr('y', (d) => y(d.v)).attr('height', (d) => y(0) - y(d.v))
      .attr('rx', 4).attr('fill', css('--accent'))
      .on('mousemove', (ev, d) => tip.show(ev, d.label, d.tip || [fmt(d.v)])).on('mouseleave', () => tip.hide());
    svg.append('g').selectAll('text').data(rows).join('text').attr('class', 'axis-label').style('fill', css('--ink'))
      .attr('x', (d) => x(d.label) + x.bandwidth() / 2).attr('y', (d) => y(d.v) - 6).attr('text-anchor', 'middle').text((d) => fmt(d.v));
    svg.append('g').selectAll('text').data(rows).join('text').attr('class', 'axis-label')
      .attr('x', (d) => x(d.label) + x.bandwidth() / 2).attr('y', h - 8).attr('text-anchor', 'middle').text((d) => d.label);
  }

  // Lines: series [{key, label, values:[{d, v}], accent}]; tooltip follows the accent series
  function lines(box, series, { fmt = f1, unit = '', h = 230, zero = true } = {}) {
    const { svg, w } = svgIn(box, h);
    const all = series.flatMap((s) => s.values).filter((p) => p.v != null);
    if (!all.length) { box.replaceChildren(el('div', { class: 'loading', text: 'ไม่มีข้อมูล' })); return; }
    const lo = zero ? 0 : d3.min(all, (p) => p.v), hi = d3.max(all, (p) => p.v);
    const y = d3.scaleLinear([lo, hi], [h - 26, 10]).nice();
    const ml = textWidth(svg, y.ticks(4).map(fmt)) + 14;
    const x = d3.scaleUtc(d3.extent(all, (p) => p.d), [ml, w - 8]);
    yGrid(svg, y, ml, w - 8, fmt);
    svg.append('g').selectAll('text').data(x.ticks(d3.utcYear.every(1))).join('text').attr('class', 'axis-label')
      .attr('x', (d) => x(d)).attr('y', h - 8).attr('text-anchor', 'middle').text((d) => d.getUTCFullYear() + 543);
    const line = d3.line().defined((p) => p.v != null).x((p) => x(p.d)).y((p) => y(p.v));
    const order = [...series].sort((a, b) => (a.accent === b.accent ? 0 : a.accent ? 1 : -1));
    svg.append('g').selectAll('path').data(order).join('path')
      .attr('d', (s) => line(s.values)).attr('fill', 'none')
      .attr('stroke', (s) => (s.accent ? css('--accent') : css('--mute-series')))
      .attr('stroke-width', (s) => (s.accent ? 2 : 1.2)).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
    const acc = series.find((s) => s.accent) || series[0];
    const pts = acc.values.filter((p) => p.v != null);
    const rule = svg.append('line').attr('y1', 10).attr('y2', h - 26).attr('stroke', css('--faint')).attr('stroke-dasharray', '3 3').attr('opacity', 0);
    const dot = svg.append('circle').attr('r', 4.5).attr('fill', css('--accent')).attr('stroke', css('--panel')).attr('stroke-width', 2).attr('opacity', 0);
    const tip = tooltip(box);
    const bis = d3.bisector((p) => p.d).center;
    svg.append('rect').attr('x', ml).attr('width', w - ml - 8).attr('y', 0).attr('height', h - 20).attr('fill', 'transparent')
      .on('mousemove', (ev) => {
        const [mx] = d3.pointer(ev);
        const p = pts[bis(pts, x.invert(mx))];
        if (!p) return;
        rule.attr('x1', x(p.d)).attr('x2', x(p.d)).attr('opacity', 1);
        dot.attr('cx', x(p.d)).attr('cy', y(p.v)).attr('opacity', 1);
        tip.show(ev, thMonth(p.d), [`${acc.label}: ${fmt(p.v)} ${unit}`.trim()]);
      })
      .on('mouseleave', () => { rule.attr('opacity', 0); dot.attr('opacity', 0); tip.hide(); });
  }

  // Lon/lat dot map: points [{lon, lat, r, fill, head, lines}]
  function dotMap(box, points, { h = 380 } = {}) {
    const { svg, w } = svgIn(box, h);
    const pad = 0.6;
    let [x0, x1] = d3.extent(points, (p) => p.lon), [y0, y1] = d3.extent(points, (p) => p.lat);
    x0 -= pad; x1 += pad; y0 -= pad; y1 += pad;
    const k = Math.cos(((y0 + y1) / 2) * Math.PI / 180);
    const sx = (w - 50) / ((x1 - x0) * k), sy = (h - 30) / (y1 - y0), s = Math.min(sx, sy);
    const ox = 40 + ((w - 50) - (x1 - x0) * k * s) / 2, oy = 6 + ((h - 30) - (y1 - y0) * s) / 2;
    const X = (lon) => ox + (lon - x0) * k * s, Y = (lat) => oy + (y1 - lat) * s;
    const g = svg.append('g');
    d3.range(Math.ceil(x0), Math.floor(x1) + 1).forEach((lon) => {
      g.append('line').attr('class', 'gridline').attr('x1', X(lon)).attr('x2', X(lon)).attr('y1', Y(y1)).attr('y2', Y(y0));
      g.append('text').attr('class', 'axis-label').attr('x', X(lon)).attr('y', Y(y0) + 14).attr('text-anchor', 'middle').text(lon + '°E');
    });
    d3.range(Math.ceil(y0), Math.floor(y1) + 1).forEach((lat) => {
      g.append('line').attr('class', 'gridline').attr('x1', X(x0)).attr('x2', X(x1)).attr('y1', Y(lat)).attr('y2', Y(lat));
      g.append('text').attr('class', 'axis-label').attr('x', X(x0) - 6).attr('y', Y(lat)).attr('dy', '0.32em').attr('text-anchor', 'end').text(lat + '°N');
    });
    const tip = tooltip(box);
    svg.append('g').selectAll('circle').data([...points].sort((a, b) => b.r - a.r)).join('circle')
      .attr('cx', (p) => X(p.lon)).attr('cy', (p) => Y(p.lat)).attr('r', (p) => p.r)
      .attr('fill', (p) => p.fill).attr('stroke', css('--panel')).attr('stroke-width', 2).style('cursor', 'default')
      .on('mousemove', (ev, p) => tip.show(ev, p.head, p.lines)).on('mouseleave', () => tip.hide());
  }

  const seqColor = () => d3.interpolateRgb(css('--seq-lo'), css('--seq-hi'));
  const inkOn = (bg) => (d3.hsl(bg).l > 0.58 ? '#13263b' : '#ffffff');

  // Sortable (optionally paged) table. cols: [{key, label, num, fmt, get}]
  function table(tbl, cols, { sort, pageSize, pager } = {}) {
    const st = { rows: [], sort: sort || null, page: 0 };
    const get = (c, r) => (c.get ? c.get(r) : r[c.key]);
    function render() {
      let rows = st.rows.slice();
      if (st.sort) {
        const c = cols.find((x) => x.key === st.sort.key);
        rows.sort((a, b) => {
          const va = get(c, a), vb = get(c, b);
          if (va == null) return 1; if (vb == null) return -1;
          const r = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb), 'th');
          return st.sort.dir === 'asc' ? r : -r;
        });
      }
      const pages = pageSize ? Math.max(1, Math.ceil(rows.length / pageSize)) : 1;
      st.page = Math.min(st.page, pages - 1);
      if (pageSize) rows = rows.slice(st.page * pageSize, (st.page + 1) * pageSize);
      const head = el('tr', {}, cols.map((c) => {
        const th = el('th', { class: c.num ? 'n' : null, scope: 'col' });
        if (st.sort && st.sort.key === c.key) th.setAttribute('aria-sort', st.sort.dir === 'asc' ? 'ascending' : 'descending');
        const b = el('button', { type: 'button', text: c.label });
        b.addEventListener('click', () => {
          st.sort = { key: c.key, dir: st.sort && st.sort.key === c.key && st.sort.dir === 'desc' ? 'asc' : 'desc' };
          st.page = 0; render();
        });
        th.append(b);
        return th;
      }));
      const body = rows.map((r) => el('tr', {}, cols.map((c) => {
        const v = get(c, r);
        const td = el('td', { class: [c.num ? 'n' : '', c.neg && v < 0 ? 'neg' : ''].join(' ').trim() || null });
        td.textContent = v == null ? '–' : c.fmt ? c.fmt(v, r) : v;
        return td;
      })));
      if (!body.length) body.push(el('tr', {}, el('td', { colspan: cols.length, class: 'sub', text: 'ไม่มีรายการตามตัวกรอง' })));
      tbl.replaceChildren(el('thead', {}, head), el('tbody', {}, body));
      if (pager) {
        pager.info.textContent = `หน้า ${st.page + 1} / ${pages} · ${f0(st.rows.length)} รายการ`;
        pager.prev.disabled = st.page === 0; pager.next.disabled = st.page >= pages - 1;
      }
    }
    if (pager) {
      pager.prev.addEventListener('click', () => { st.page--; render(); });
      pager.next.addEventListener('click', () => { st.page++; render(); });
    }
    return { set(rows) { st.rows = rows; st.page = 0; render(); }, render };
  }

  // ---------------------------------------------------------------- state & data
  const D = {};
  const S = {
    ovMetric: 'catch', fcVar: 'wave', fcDate: null, envRegion: null, spPick: null,
    tf: { zone: '', gear: '', from: '', to: '' },
  };

  async function load() {
    const names = ['meta', 'trips', 'zones', 'forecast', 'environment', 'exports', 'species', 'model'];
    const res = await Promise.all(names.map((n) => fetch(`data/${n}.json`, { cache: 'no-cache' }).then((r) => {
      if (!r.ok) throw new Error(`โหลด data/${n}.json ไม่ได้ (HTTP ${r.status})`);
      return r.json();
    })));
    names.forEach((n, i) => { D[n] = res[i]; });

    D.zoneById = Object.fromEntries(D.zones.zones.map((z) => [z.id, z]));
    D.regionName = D.zones.regions;
    D.trips = zip(D.trips.columns, D.trips.rows).map((t) => ({ ...t, d: parseDay(t.departure), m: t.departure.slice(0, 7) }));
    D.gears = [...new Set(D.trips.map((t) => t.gear))].sort((a, b) => a.localeCompare(b, 'th'));
    D.fc = zip(D.forecast.columns, D.forecast.rows);
    D.fcDates = [...new Set(D.fc.map((r) => r.date))].sort();
    D.env = { sea: zip(D.environment.sea_columns, D.environment.sea), wx: zip(D.environment.weather_columns, D.environment.weather) };
    D.sp = zip(D.species.columns, D.species.monthly);

    // per-zone trip aggregates
    const zAgg = d3.rollup(D.trips, (v) => ({
      trips: v.length, catch: sum(v, (t) => t.catch_kg), profit: sum(v, (t) => t.profit_thb),
    }), (t) => t.zone);
    D.zones.zones.forEach((z) => {
      const a = zAgg.get(z.id) || { trips: 0, catch: 0, profit: 0 };
      Object.assign(z, a, { avg_catch: a.trips ? a.catch / a.trips : null, avg_profit: a.trips ? a.profit / a.trips : null });
    });
  }

  const monthlyOf = (trips) => d3.rollups(trips, (v) => ({
    trips: v.length, catch: sum(v, (t) => t.catch_kg), revenue: sum(v, (t) => t.revenue_thb), profit: sum(v, (t) => t.profit_thb),
  }), (t) => t.m).sort((a, b) => d3.ascending(a[0], b[0])).map(([m, a]) => ({ d: parseMonth(m), ...a }));

  // ---------------------------------------------------------------- pages
  const PAGES = {
    overview: ['Operations overview', 'ภาพรวมการดำเนินงาน', 'เที่ยวเรือ ผลจับ และพยากรณ์ทะเลล่าสุด'],
    forecast: ['Marine forecast', 'พยากรณ์ทะเล 7 วัน', 'คลื่น ลม และฝน รายโซนประมง จากรอบพยากรณ์ล่าสุด'],
    trips: ['Fishing trips', 'เที่ยวเรือ', 'กรองตามพื้นที่ เครื่องมือ และช่วงวันที่'],
    zones: ['Fishing zones', 'พื้นที่ประมง', '23 โซนในอ่าวไทย พร้อมผลจับและกำไรเฉลี่ย'],
    species: ['Species', 'ชนิดสัตว์น้ำ', 'ผลจับและมูลค่าจากรายการจับในแต่ละเที่ยว'],
    environment: ['Observed conditions', 'อากาศและทะเลย้อนหลัง', 'ค่าเฉลี่ยรายเดือนจากข้อมูลตรวจวัด แยกภูมิภาค'],
    exports: ['Export orders', 'การส่งออก', 'คำสั่งซื้อส่งออก ตามเดือน ประเทศ และชนิดสัตว์น้ำ'],
    model: ['Analysis', 'ผลโมเดลและ CRISP-DM', 'สิ่งที่ข้อมูลบอก และสิ่งที่ยังบอกไม่ได้'],
    data: ['Data sources', 'แหล่งข้อมูล', 'ที่มาของตัวเลขทุกตัวในหน้านี้'],
  };
  const RENDER = {};
  let current = null;

  RENDER.overview = () => {
    const T = D.trips;
    const catchT = sum(T, (t) => t.catch_kg) / 1000, rev = sum(T, (t) => t.revenue_thb), profit = sum(T, (t) => t.profit_thb);
    $('#ovTrips').textContent = f0(T.length);
    $('#ovRange').textContent = `${thDate(parseDay(D.meta.trip_range[0]))} – ${thDate(parseDay(D.meta.trip_range[1]))}`;
    $('#ovCatch').textContent = f0(catchT);
    $('#ovRev').textContent = f1(rev / 1e6);
    $('#ovProfit').textContent = f1(profit / 1e6);
    $('#ovMargin').textContent = `อัตรากำไร ${pct(profit / rev)} ของรายได้`;
    const M = monthlyOf(T);
    const spec = {
      catch: { v: (m) => m.catch / 1000, fmt: f0, unit: 'ตัน', note: 'ผลจับ ตันต่อเดือน' },
      trips: { v: (m) => m.trips, fmt: f0, unit: 'เที่ยว', note: 'จำนวนเที่ยวเรือต่อเดือน' },
      revenue: { v: (m) => m.revenue / 1e6, fmt: f1, unit: 'ล้านบาท', note: 'รายได้ ล้านบาทต่อเดือน' },
      profit: { v: (m) => m.profit / 1e6, fmt: f1, unit: 'ล้านบาท', note: 'กำไร ล้านบาทต่อเดือน' },
    }[S.ovMetric];
    $('#ovTrendNote').textContent = spec.note + ' ตามวันออกเรือ';
    barTime($('#ovTrend'), M.map((m) => ({ d: m.d, v: spec.v(m), trips: m.trips })), {
      fmt: spec.fmt, unit: spec.unit, extra: S.ovMetric === 'trips' ? null : (d) => [`${f0(d.trips)} เที่ยว`],
    });

    // forecast: tomorrow (or the 2nd forecast day)
    const day = D.fcDates[1] || D.fcDates[0];
    if (day) {
      const rows = D.fc.filter((r) => r.date === day && r.wave_m != null).sort((a, b) => b.wave_m - a.wave_m).slice(0, 8);
      $('#ovFcNote').textContent = `${thDate(parseDay(day), { weekday: 'long', day: 'numeric', month: 'short' })} · 8 โซนที่คลื่นสูงสุด (เมตร)`;
      hbar($('#ovFc'), rows.map((r) => ({
        label: D.zoneById[r.zone]?.name || r.zone, v: r.wave_m,
        tip: [`คลื่น ${f2(r.wave_m)} ม.`, `ลม ${fmtNum(r.wind_kn, f1)} นอต`, `ฝน ${fmtNum(r.rain_mm, f1)} มม.`],
      })), { fmt: f2 });
    } else {
      $('#ovFc').replaceChildren(el('div', { class: 'sub', text: 'ยังไม่มีข้อมูลพยากรณ์' }));
    }

    const G = d3.rollups(T, (v) => ({ n: v.length, avg: sum(v, (t) => t.catch_kg) / v.length, p: sum(v, (t) => t.profit_thb) / v.length }), (t) => t.gear)
      .sort((a, b) => b[1].avg - a[1].avg);
    hbar($('#ovGear'), G.map(([g, a]) => ({ label: g, v: a.avg, tip: [`จับเฉลี่ย ${f0(a.avg)} กก./เที่ยว`, `กำไรเฉลี่ย ${f0(a.p)} บาท/เที่ยว`, `${f0(a.n)} เที่ยว`] })), { fmt: f0 });

    const top = [...D.zones.zones].sort((a, b) => b.avg_catch - a.avg_catch)[0];
    const wa = D.model.wave_activity;
    $('#ovFindings').replaceChildren(
      el('b', { text: 'จำนวนลูกเรือ' }), ' อธิบายผลจับต่อเที่ยวได้มากที่สุด โมเดลลดความคลาดเคลื่อนจาก ',
      el('span', { class: 'num', text: f0(D.model.single_split.baseline_mae) }), ' เหลือ ', el('span', { class: 'num', text: f0(D.model.single_split.model_mae) }), ' กก. ต่อเที่ยว',
      el('br'), el('br'),
      el('b', { text: 'อากาศและทะเลรายวัน' }), ' ไม่ช่วยให้พยากรณ์ผลจับแม่นขึ้น แต่จำนวนเที่ยวต่อวันลดลงจาก ',
      el('span', { class: 'num', text: f2(wa[0].trips_per_zone_day) }), ' เป็น ', el('span', { class: 'num', text: f2(wa[wa.length - 1].trips_per_zone_day) }), ' เมื่อคลื่นวันก่อนสูงกว่า 1 เมตร',
      el('br'), el('br'),
      el('b', { text: top.name }), ` มีผลจับเฉลี่ยสูงสุด ${f0(top.avg_catch)} กก. ต่อเที่ยว`,
    );
  };

  RENDER.forecast = () => {
    const F = D.fc;
    if (!F.length) { $('#fcHeat').replaceChildren(el('tr', {}, el('td', { text: 'ยังไม่มีข้อมูลพยากรณ์' }))); return; }
    if (!S.fcDate || !D.fcDates.includes(S.fcDate)) S.fcDate = D.fcDates[0];
    const V = {
      wave: { k: 'wave_m', fmt: f2, unit: 'ม.', name: 'คลื่นสูงสุด' },
      wind: { k: 'wind_kn', fmt: f1, unit: 'นอต', name: 'ลมสูงสุด' },
      rain: { k: 'rain_mm', fmt: f1, unit: 'มม.', name: 'ฝนรวม' },
      period: { k: 'period_s', fmt: f1, unit: 'วินาที', name: 'คาบคลื่นสูงสุด' },
    }[S.fcVar];

    const maxBy = (k) => F.filter((r) => r[k] != null).reduce((a, b) => (b[k] > a[k] ? b : a));
    const mw = maxBy('wave_m'), mk = maxBy('wind_kn');
    const kpi = (label, value, foot) => el('div', { class: 'card kpi' }, el('div', { class: 'label', text: label }), el('div', { class: 'value', text: value }), el('div', { class: 'foot', text: foot }));
    $('#fcKpis').replaceChildren(
      kpi('รอบพยากรณ์ล่าสุด', new Date(D.forecast.fetched_at).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }) + ' น.',
        `${new Date(D.forecast.fetched_at).toLocaleDateString('th-TH', { dateStyle: 'medium' })} · ${D.forecast.source}`),
      kpi('คลื่นสูงสุดใน 7 วัน (ม.)', f2(mw.wave_m), `${D.zoneById[mw.zone]?.name} · ${thDate(parseDay(mw.date), { day: 'numeric', month: 'short' })}`),
      kpi('ลมแรงสุดใน 7 วัน (นอต)', f1(mk.wind_kn), `${D.zoneById[mk.zone]?.name} · ${thDate(parseDay(mk.date), { day: 'numeric', month: 'short' })}`),
      kpi('รอบที่เก็บไว้', f0(D.forecast.runs_stored), `${D.zones.zones.length} โซน × ${D.fcDates.length} วัน ต่อรอบ`),
    );

    const vals = F.map((r) => r[V.k]).filter((v) => v != null);
    const c = d3.scaleSequential([0, d3.max(vals) || 1], seqColor());
    $('#rampLo').textContent = '0'; $('#rampHi').textContent = `${V.fmt(d3.max(vals))} ${V.unit}`;
    const byZone = d3.group(F, (r) => r.zone);
    const head = el('tr', {}, el('th', { text: 'โซน' }), D.fcDates.map((d) => el('th', {
      class: d === S.fcDate ? 'sel' : null, text: thDate(parseDay(d), { weekday: 'short', day: 'numeric' }),
    })));
    const body = D.zones.zones.map((z) => el('tr', {}, el('td', { class: 'zn', text: z.name }), D.fcDates.map((d) => {
      const r = (byZone.get(z.id) || []).find((x) => x.date === d);
      const v = r ? r[V.k] : null;
      const td = el('td', { class: 'cell' + (d === S.fcDate ? ' sel' : ''), text: v == null ? '–' : V.fmt(v), title: `${z.name} · ${d}` });
      if (v != null) { const bg = c(v); td.style.background = bg; td.style.color = inkOn(bg); } else td.style.color = css('--faint');
      td.addEventListener('click', () => { S.fcDate = d; RENDER.forecast(); });
      return td;
    })));
    $('#fcHeat').replaceChildren(el('thead', {}, head), el('tbody', {}, body));

    const dayRows = F.filter((r) => r.date === S.fcDate);
    const dLabel = thDate(parseDay(S.fcDate), { weekday: 'long', day: 'numeric', month: 'long' });
    $('#fcMapTitle').textContent = `${V.name} · ${dLabel}`;
    $('#fcDayTitle').textContent = dLabel;
    dotMap($('#fcMap'), dayRows.map((r) => {
      const z = D.zoneById[r.zone], v = r[V.k];
      return {
        lon: z.lon, lat: z.lat, r: 9, fill: v == null ? css('--mute-series') : c(v), head: `${z.name} (${z.province || '–'})`,
        lines: [`คลื่น ${fmtNum(r.wave_m, f2)} ม. · คาบ ${fmtNum(r.period_s, f1)} วิ`, `ลม ${fmtNum(r.wind_kn, f1)} นอต · ฝน ${fmtNum(r.rain_mm, f1)} มม.`],
      };
    }), { h: 360 });
    fcDayTable.set(dayRows.map((r) => ({ ...r, name: D.zoneById[r.zone]?.name, province: D.zoneById[r.zone]?.province })));
  };
  let fcDayTable;

  // trips
  let tripTable;
  function filteredTrips() {
    const { zone, gear, from, to } = S.tf;
    return D.trips.filter((t) => (!zone || t.zone === zone) && (!gear || t.gear === gear) && (!from || t.departure >= from) && (!to || t.departure <= to));
  }
  RENDER.trips = () => {
    const T = filteredTrips();
    $('#tfCount').textContent = `${f0(T.length)} จาก ${f0(D.trips.length)} เที่ยว`;
    const kpi = (label, value, foot) => el('div', { class: 'card kpi' }, el('div', { class: 'label', text: label }), el('div', { class: 'value', text: value }), el('div', { class: 'foot', text: foot }));
    const c = sum(T, (t) => t.catch_kg), p = sum(T, (t) => t.profit_thb), loss = T.filter((t) => t.profit_thb < 0).length;
    $('#tKpis').replaceChildren(
      kpi('เที่ยวเรือ', f0(T.length), 'ตามตัวกรอง'),
      kpi('ผลจับรวม (ตัน)', f1(c / 1000), T.length ? `เฉลี่ย ${f0(c / T.length)} กก./เที่ยว` : '–'),
      kpi('กำไรรวม (ล้านบาท)', f2(p / 1e6), T.length ? `เฉลี่ย ${f0(p / T.length)} บาท/เที่ยว` : '–'),
      kpi('เที่ยวที่ขาดทุน', f0(loss), T.length ? `${pct(loss / T.length)} ของเที่ยวที่กรอง` : '–'),
    );
    barTime($('#tTrend'), monthlyOf(T).map((m) => ({ d: m.d, v: m.catch / 1000, trips: m.trips })), {
      fmt: f1, unit: 'ตัน', h: 220, extra: (d) => [`${f0(d.trips)} เที่ยว`],
    });
    tripTable.set(T);
  };

  RENDER.zones = () => {
    const Z = D.zones.zones;
    const c = d3.scaleSequential(d3.extent(Z, (z) => z.avg_catch), seqColor());
    const r = d3.scaleSqrt([0, d3.max(Z, (z) => z.trips)], [3, 18]);
    dotMap($('#zMap'), Z.map((z) => ({
      lon: z.lon, lat: z.lat, r: r(z.trips), fill: c(z.avg_catch), head: `${z.name} (${z.id})`,
      lines: [`${z.province || 'ไม่ระบุจังหวัด'} · ลึก ${z.depth_m} ม.`, `${f0(z.trips)} เที่ยว · จับเฉลี่ย ${f0(z.avg_catch)} กก.`, `กำไรเฉลี่ย ${f0(z.avg_profit)} บาท/เที่ยว`],
    })), { h: 400 });
    const R = d3.rollups(Z, (v) => {
      const trips = sum(v, (z) => z.trips);
      return { zones: v.length, trips, avg_catch: sum(v, (z) => z.catch) / trips, avg_profit: sum(v, (z) => z.profit) / trips };
    }, (z) => z.region).map(([id, a]) => ({ id, name: D.regionName[id] || id, ...a }));
    regionTable.set(R);
    zoneTable.set(Z);
    const miss = Z.filter((z) => !z.station).map((z) => z.name);
    $('#zMissing').textContent = miss.length ? `ไม่มีสถานีอากาศในข้อมูล ${miss.length} โซน: ${miss.join(', ')}` : '';
  };
  let regionTable, zoneTable;

  RENDER.species = () => {
    const tot = d3.rollups(D.sp, (v) => ({ kg: sum(v, (r) => r.catch_kg), thb: sum(v, (r) => r.value_thb) }), (r) => r.species);
    const name = (id) => D.species.species[id]?.name || id;
    const cat = (id) => D.species.species[id]?.category || '';
    hbar($('#spKg'), tot.sort((a, b) => b[1].kg - a[1].kg).map(([id, a]) => ({
      label: name(id), v: a.kg / 1000, tip: [`${f1(a.kg / 1000)} ตัน`, cat(id), `ราคาเฉลี่ย ${f0(a.thb / a.kg)} บาท/กก.`],
    })), { fmt: f0 });
    hbar($('#spThb'), tot.sort((a, b) => b[1].thb - a[1].thb).map(([id, a]) => ({
      label: name(id), v: a.thb / 1e6, tip: [`${f1(a.thb / 1e6)} ล้านบาท`, cat(id)],
    })), { fmt: f1 });
    const sel = $('#spPick');
    if (!sel.options.length) {
      tot.sort((a, b) => b[1].kg - a[1].kg).forEach(([id]) => sel.append(new Option(name(id), id)));
      sel.addEventListener('change', () => { S.spPick = sel.value; RENDER.species(); });
    }
    S.spPick = S.spPick || sel.value;
    sel.value = S.spPick;
    $('#spTrendTitle').textContent = `แนวโน้มรายเดือน · ${name(S.spPick)}`;
    barTime($('#spTrend'), D.sp.filter((r) => r.species === S.spPick).map((r) => ({ d: parseMonth(r.month), v: r.catch_kg / 1000, thb: r.value_thb })), {
      fmt: f1, unit: 'ตัน', h: 220, extra: (d) => [`${f1(d.thb / 1e6)} ล้านบาท`],
    });
  };

  RENDER.environment = () => {
    const sel = $('#envRegion');
    const ids = Object.keys(D.regionName).sort();
    if (!sel.options.length) {
      ids.forEach((id) => sel.append(new Option(`${D.regionName[id]} (${id})`, id)));
      sel.addEventListener('change', () => { S.envRegion = sel.value; RENDER.environment(); });
    }
    S.envRegion = S.envRegion || ids[0];
    sel.value = S.envRegion;
    const mk = (rows, k) => ids.map((id) => ({
      key: id, label: D.regionName[id], accent: id === S.envRegion,
      values: rows.filter((r) => r.region === id).map((r) => ({ d: parseMonth(r.month), v: r[k] })),
    })).filter((s) => s.values.length);
    lines($('#envWave'), mk(D.env.sea, 'wave_avg_m'), { fmt: f2, unit: 'ม.' });
    lines($('#envWind'), mk(D.env.wx, 'wind_avg_kn'), { fmt: f1, unit: 'นอต' });
    lines($('#envRain'), mk(D.env.wx, 'rain_avg_mm'), { fmt: f1, unit: 'มม./วัน' });
    lines($('#envSst'), mk(D.env.sea, 'sst_avg_c'), { fmt: f1, unit: '°C', zero: false });
  };

  RENDER.exports = () => {
    const E = D.exports;
    const M = zip(E.monthly_columns, E.monthly), C = zip(E.country_columns, E.countries), P = zip(E.species_columns, E.species);
    const kpi = (label, value, foot) => el('div', { class: 'card kpi' }, el('div', { class: 'label', text: label }), el('div', { class: 'value', text: value }), el('div', { class: 'foot', text: foot }));
    const thb = sum(M, (m) => m.value_thb), kg = sum(M, (m) => m.weight_kg), n = sum(M, (m) => m.orders);
    $('#exKpis').replaceChildren(
      kpi('คำสั่งซื้อ', f0(n), `${thMonth(parseMonth(M[0].month))} – ${thMonth(parseMonth(M[M.length - 1].month))}`),
      kpi('น้ำหนักรวม (ตัน)', f1(kg / 1000), 'eo_total_weight_kg'),
      kpi('มูลค่ารวม (ล้านบาท)', f1(thb / 1e6), 'eo_total_value_thb'),
      kpi('ประเทศปลายทาง', f0(C.length), `มากสุด: ${C[0].country}`),
    );
    barTime($('#exTrend'), M.map((m) => ({ d: parseMonth(m.month), v: m.value_thb / 1e6, n: m.orders, kg: m.weight_kg })), {
      fmt: f1, unit: 'ล้านบาท', h: 220, extra: (d) => [`${f0(d.n)} คำสั่งซื้อ`, `${f1(d.kg / 1000)} ตัน`],
    });
    hbar($('#exCountry'), C.map((c) => ({ label: c.country, v: c.value_thb / 1e6, tip: [`${f1(c.value_thb / 1e6)} ล้านบาท`, `${f0(c.orders)} คำสั่งซื้อ`, `${f1(c.weight_kg / 1000)} ตัน`] })), { fmt: f1 });
    hbar($('#exSpecies'), P.map((p) => ({ label: p.species, v: p.value_thb / 1e6, tip: [`${f1(p.value_thb / 1e6)} ล้านบาท`, `${f1(p.weight_kg / 1000)} ตัน`] })), { fmt: f1 });
  };

  RENDER.model = () => {
    const s = D.model.single_split;
    const kpi = (label, value, foot) => el('div', { class: 'card kpi' }, el('div', { class: 'label', text: label }), el('div', { class: 'value', text: value }), el('div', { class: 'foot', text: foot }));
    $('#mKpis').replaceChildren(
      kpi('MAE ค่าเฉลี่ยอย่างเดียว (กก.)', f1(s.baseline_mae), 'เดาทุกเที่ยวด้วยค่าเฉลี่ยชุดฝึก'),
      kpi('MAE โมเดล (กก.)', f1(s.model_mae), `ดีขึ้น ${pct(1 - s.model_mae / s.baseline_mae)} · HistGradientBoosting`),
      kpi('R² ชุดทดสอบ', s.r2.toFixed(3), `ทดสอบ ${s.test}`),
      kpi('ตัวแปรสำคัญที่สุด', 'ลูกเรือ', 'ft_crew_count · permutation importance'),
    );
    mTests.set(D.model.tests.map((t) => ({ ...t, change: (t.without_env - t.with_env) / t.without_env })));
    vbar($('#mWave'), D.model.wave_activity.map((w) => ({
      label: w.band, v: w.trips_per_zone_day, tip: [`${f2(w.trips_per_zone_day)} เที่ยวต่อโซน-วัน`, `จาก ${f0(w.zone_days)} โซน-วัน`],
    })), { fmt: (v) => v.toFixed(3) });
    const steps = [
      ['1. Business Understanding', 'part', 'เป้าหมาย: ช่วยประเมินพื้นที่และช่วงเวลาออกเรือ แต่ยังไม่มีเกณฑ์ตัดสินใจที่ยืนยันกับผู้ใช้'],
      ['2. Data Understanding', 'done', 'ตรวจ schema คีย์เชื่อม ค่าว่าง และช่วงเวลาของ 7 collections แล้ว'],
      ['3. Data Preparation', 'done', 'รวมทริปกับโซน ทะเล อากาศ ใช้เฉพาะข้อมูลวัน D-1 และเฉลี่ย 3 วัน'],
      ['4. Modeling', 'done', 'โมเดลผลจับต่อเที่ยว และเทียบแบบมี/ไม่มีอากาศ-ทะเล แบ่งตามเวลา'],
      ['5. Evaluation', 'part', 'วัด MAE และ deviance แล้ว ยังไม่ได้ปรับพารามิเตอร์หรือเทียบกับเป้าหมายธุรกิจ'],
      ['6. Deployment', 'part', 'มี API ในเครื่อง หน้าเว็บนี้ และดึงพยากรณ์อัตโนมัติ ยังไม่มีโมเดลทำนายบนเว็บ'],
    ];
    const lab = { done: 'ทำแล้ว', part: 'บางส่วน', todo: 'ยังไม่ทำ' };
    $('#mSteps').replaceChildren(...steps.map(([h, st, p]) => el('div', { class: 'step' },
      el('h3', {}, h, el('span', { class: `pill ${st}`, text: lab[st] })), el('p', { text: p }))));
  };
  let mTests;

  RENDER.data = () => {
    const desc = {
      fishing_trips: 'เที่ยวเรือ ผลจับ ต้นทุน กำไร', fishing_zones: 'โซนประมง พิกัด ความลึก สถานีอากาศ',
      weather_reports: 'อากาศตรวจวัดรายวันต่อสถานี', sea_conditions: 'สภาพทะเลรายวันต่อโซน',
      export_orders: 'คำสั่งซื้อส่งออก', catch_images: 'เมทาดาทาภาพสัตว์น้ำ (ไม่เผยแพร่บนเว็บ)',
      weather_forcasting: 'พยากรณ์ Open-Meteo เก็บทุกรอบ',
    };
    dbTable.set(Object.entries(D.meta.counts).map(([k, n]) => ({ k, n, desc: desc[k] || '' })));
    $('#dbNote').textContent = `ฐานข้อมูล ${D.meta.database} · นับเมื่อ ${thDateTime(D.meta.generated_at)}`;
  };
  let dbTable;

  // ---------------------------------------------------------------- wiring
  function setupTables() {
    const zoneName = (r) => D.zoneById[r.zone]?.name || r.zone;
    tripTable = table($('#tTable'), [
      { key: 'id', label: 'Trip ID' },
      { key: 'departure', label: 'ออกเรือ' },
      { key: 'return', label: 'กลับ' },
      { key: 'zone', label: 'พื้นที่', get: zoneName },
      { key: 'gear', label: 'เครื่องมือ' },
      { key: 'size_gt', label: 'ขนาด (GT)', num: true, fmt: f0 },
      { key: 'crew', label: 'ลูกเรือ', num: true, fmt: f0 },
      { key: 'catch_kg', label: 'ผลจับ (กก.)', num: true, fmt: f1 },
      { key: 'revenue_thb', label: 'รายได้ (บาท)', num: true, fmt: f0 },
      { key: 'profit_thb', label: 'กำไร (บาท)', num: true, fmt: f0, neg: true },
    ], { sort: { key: 'departure', dir: 'desc' }, pageSize: 25, pager: { prev: $('#tPrev'), next: $('#tNext'), info: $('#tPage') } });

    fcDayTable = table($('#fcDayTable'), [
      { key: 'name', label: 'โซน' },
      { key: 'wave_m', label: 'คลื่น (ม.)', num: true, fmt: f2 },
      { key: 'period_s', label: 'คาบ (วิ)', num: true, fmt: f1 },
      { key: 'wind_kn', label: 'ลม (นอต)', num: true, fmt: f1 },
      { key: 'rain_mm', label: 'ฝน (มม.)', num: true, fmt: f1 },
    ], { sort: { key: 'wave_m', dir: 'desc' } });

    regionTable = table($('#zRegion'), [
      { key: 'name', label: 'ภูมิภาค' },
      { key: 'zones', label: 'โซน', num: true, fmt: f0 },
      { key: 'trips', label: 'เที่ยว', num: true, fmt: f0 },
      { key: 'avg_catch', label: 'จับ/เที่ยว (กก.)', num: true, fmt: f0 },
      { key: 'avg_profit', label: 'กำไร/เที่ยว (บาท)', num: true, fmt: f0, neg: true },
    ], { sort: { key: 'trips', dir: 'desc' } });

    zoneTable = table($('#zTable'), [
      { key: 'id', label: 'รหัส' },
      { key: 'name', label: 'โซน' },
      { key: 'province', label: 'จังหวัด' },
      { key: 'region', label: 'ภูมิภาค', get: (z) => D.regionName[z.region] },
      { key: 'depth_m', label: 'ลึก (ม.)', num: true, fmt: f0 },
      { key: 'port', label: 'ท่าเรือใกล้สุด' },
      { key: 'station', label: 'สถานีอากาศ' },
      { key: 'trips', label: 'เที่ยว', num: true, fmt: f0 },
      { key: 'avg_catch', label: 'จับ/เที่ยว (กก.)', num: true, fmt: f1 },
      { key: 'avg_profit', label: 'กำไร/เที่ยว (บาท)', num: true, fmt: f0, neg: true },
    ], { sort: { key: 'trips', dir: 'desc' } });

    mTests = table($('#mTests'), [
      { key: 'test', label: 'การทดสอบ' },
      { key: 'metric', label: 'ตัวชี้วัด' },
      { key: 'without_env', label: 'ไม่มีอากาศ/ทะเล', num: true, fmt: (v) => String(v) },
      { key: 'with_env', label: 'มีอากาศ/ทะเล', num: true, fmt: (v) => String(v) },
      { key: 'change', label: 'ดีขึ้น', num: true, fmt: (v) => (v > 0 ? '+' : '') + pct(v) },
      { key: 'folds_better', label: 'รอบที่ดีขึ้น', num: true, fmt: (v) => `${v}/5` },
    ]);

    dbTable = table($('#dbTable'), [
      { key: 'k', label: 'Collection' },
      { key: 'n', label: 'เอกสาร', num: true, fmt: f0 },
      { key: 'desc', label: 'เนื้อหา' },
    ], { sort: { key: 'n', dir: 'desc' } });
  }

  function setupControls() {
    const seg = (root, key) => root.addEventListener('click', (ev) => {
      const b = ev.target.closest('button'); if (!b) return;
      root.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      S[key] = b.dataset.m || b.dataset.v;
      RENDER[current]();
    });
    seg($('#ovMetric'), 'ovMetric');
    seg($('#fcVar'), 'fcVar');

    const zSel = $('#tfZone'), gSel = $('#tfGear'), from = $('#tfFrom'), to = $('#tfTo');
    zSel.append(new Option('ทุกพื้นที่', ''), ...D.zones.zones.map((z) => new Option(`${z.name} (${z.province || '–'})`, z.id)));
    gSel.append(new Option('ทุกเครื่องมือ', ''), ...D.gears.map((g) => new Option(g, g)));
    [from, to].forEach((i) => { i.min = D.meta.trip_range[0]; i.max = D.meta.trip_range[1]; });
    const apply = () => {
      S.tf = { zone: zSel.value, gear: gSel.value, from: from.validity.valid ? from.value : '', to: to.validity.valid ? to.value : '' };
      if (S.tf.from && S.tf.to && S.tf.from > S.tf.to) { $('#tfCount').textContent = 'วันที่เริ่มต้องไม่อยู่หลังวันที่สิ้นสุด'; return; }
      RENDER.trips();
    };
    [zSel, gSel, from, to].forEach((i) => i.addEventListener('change', apply));
    $('#tfReset').addEventListener('click', () => { zSel.value = ''; gSel.value = ''; from.value = ''; to.value = ''; apply(); });
    $('#tfCsv').addEventListener('click', () => {
      const cols = ['id', 'departure', 'return', 'zone', 'gear', 'size_gt', 'crew', 'catch_kg', 'revenue_thb', 'profit_thb', 'cost_thb'];
      const q = (v) => (v == null ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
      const csv = '﻿' + [cols.join(','), ...filteredTrips().map((t) => cols.map((c) => q(t[c])).join(','))].join('\r\n');
      const a = el('a', { href: URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })), download: 'eec_trips_filtered.csv' });
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });

    $('#menuBtn').addEventListener('click', () => $('#rail').classList.toggle('open'));
    $('#themeBtn').addEventListener('click', () => {
      const dark = document.documentElement.dataset.theme
        ? document.documentElement.dataset.theme === 'dark'
        : matchMedia('(prefers-color-scheme: dark)').matches;
      const next = dark ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem('eec-theme', next); } catch (e) { /* storage blocked */ }
      RENDER[current]();
    });
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => current && RENDER[current]());
    window.addEventListener('resize', debounce(() => current && RENDER[current](), 150));
  }

  function route() {
    const id = PAGES[location.hash.slice(1)] ? location.hash.slice(1) : 'overview';
    current = id;
    document.querySelectorAll('main section').forEach((s) => { s.hidden = s.id !== id; });
    document.querySelectorAll('.nav a').forEach((a) => (a.dataset.page === id ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
    const [eb, title, sub] = PAGES[id];
    $('#eyebrow').textContent = eb; $('#pageTitle').textContent = title; $('#pageSub').textContent = sub;
    document.title = `${title} · EEC Seafood`;
    $('#rail').classList.remove('open');
    RENDER[id]();
    window.scrollTo(0, 0);
  }

  function header() {
    const gen = new Date(D.meta.generated_at);
    const ageH = (Date.now() - gen) / 36e5;
    $('#freshChip').replaceChildren(el('span', { class: 'dot' + (ageH > 48 ? ' warn' : '') }), `ข้อมูล ณ ${thDateTime(D.meta.generated_at)}`);
    $('#railFoot').replaceChildren(
      el('b', { text: 'Snapshot จาก MongoDB' }), el('br'),
      `ส่งออกเมื่อ ${thDateTime(D.meta.generated_at)}`, el('br'),
      D.forecast.fetched_at ? `พยากรณ์รอบ ${thDateTime(D.forecast.fetched_at)}` : 'ยังไม่มีพยากรณ์', el('br'),
      'หน้าเว็บนี้ไม่ได้เชื่อมฐานข้อมูลสด',
    );
    $('#ftDb').textContent = D.meta.database;
    $('#ftGen').textContent = `สร้างจาก src/11_export_web_data.py · ${thDateTime(D.meta.generated_at)}`;
  }

  // ---------------------------------------------------------------- boot
  try { const t = localStorage.getItem('eec-theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* storage blocked */ }
  load().then(() => {
    $('#loading').remove();
    setupTables();
    setupControls();
    header();
    window.addEventListener('hashchange', route);
    route();
  }).catch((e) => {
    $('#loading').replaceChildren(el('div', { class: 'error', text: e.message }),
      el('div', { class: 'sub', text: 'ถ้าเปิดไฟล์ตรงจากเครื่อง (file://) ให้เปิดผ่าน HTTP server เช่น python -m http.server ในโฟลเดอร์ docs' }));
  });
})();
