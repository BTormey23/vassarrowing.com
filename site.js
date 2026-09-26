(function(){
  const R = window.ROSTER || [];
  const results = document.getElementById('results');
  const yearEl = document.getElementById('year');
  const qEl = document.getElementById('q');
  const decades = document.getElementById('decades');
  const SIDE = {P:'Port',S:'Starboard',C:'Cox',B:'Port/Starboard'};
  const SQ = {M:"Men's",W:"Women's"};
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function nameHTML(p){
    let n = esc(p.f) + ' ' + esc(p.l);
    const alt = [];
    if (p.p) alt.push('goes by ' + esc(p.p));
    if (p.x) alt.push('née ' + esc(p.x));
    let tags = '';
    if (p.q) tags += '<span class="tag">' + SQ[p.q] + '</span>';
    if (p.s) tags += '<span class="tag side">' + SIDE[p.s] + '</span>';
    if (p.t === 'S') tags += '<span class="tag stu">Current team</span>';
    return '<li><span class="nm">' + n + (alt.length ? ' <span class="alt">(' + alt.join(', ') + ')</span>' : '') + '</span>' + tags + '</li>';
  }
  function group(year, pinned){
    const ppl = R.filter(p => p.y === year).sort((a,b)=> a.l.localeCompare(b.l) || a.f.localeCompare(b.f));
    if (!ppl.length) return '';
    return '<div class="class-group"><div class="class-head' + (pinned?' pinned':'') + '"><h3>Class of ' + year + '</h3><span class="count">' + ppl.length + (ppl.length===1?' person':' people') + '</span></div><ul class="names">' + ppl.map(nameHTML).join('') + '</ul></div>';
  }
  function showYear(y){
    if (!y || y < 1900 || y > 2035) { results.innerHTML = ''; return; }
    let html = group(y, true) || '<div class="class-group"><div class="class-head pinned"><h3>Class of ' + y + '</h3></div><p class="empty">We don\'t have anyone listed for ' + y + ' yet. If that\'s your class, you can be the first.</p></div>';
    const near = [];
    for (let d = 1; d <= 3; d++) { near.push(y - d); near.push(y + d); }
    const nearHTML = near.sort((a,b)=>a-b).map(yy => group(yy, false)).join('');
    if (nearHTML) html += '<div class="class-group"><span class="eyebrow">Nearby classes · ' + (y-3) + ' to ' + (y+3) + '</span></div>' + nearHTML;
    results.innerHTML = html;
    document.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', String(Math.floor(y/10)*10 === +c.dataset.d)));
  }
  function showSearch(q){
    q = q.trim().toLowerCase();
    if (q.length < 2) { results.innerHTML = ''; return; }
    const hits = R.filter(p => (p.f + ' ' + p.l + ' ' + (p.p||'') + ' ' + (p.x||'')).toLowerCase().includes(q)).sort((a,b)=> a.l.localeCompare(b.l) || a.y - b.y);
    results.innerHTML = hits.length
      ? '<div class="class-group"><div class="class-head"><h3>' + hits.length + ' match' + (hits.length===1?'':'es') + '</h3></div><ul class="names">' + hits.map(p => nameHTML(p).replace('</span>', ' <span class="alt">\'' + String(p.y).slice(2) + '</span></span>')).join('') + '</ul></div>'
      : '<p class="empty">No one by that name yet. Add them below.</p>';
  }
  const years = R.map(p=>p.y);
  const minD = Math.floor(Math.min.apply(null, years)/10)*10, maxD = Math.floor(Math.max.apply(null, years)/10)*10;
  for (let d = minD; d <= maxD; d += 10) {
    const b = document.createElement('button'); b.type='button'; b.className='chip'; b.dataset.d = d; b.setAttribute('aria-pressed','false');
    const n = R.filter(p => p.y >= d && p.y < d+10).length;
    b.textContent = d + 's · ' + n;
    b.addEventListener('click', () => { qEl.value=''; yearEl.value = d; showYear(d); });
    decades.appendChild(b);
  }
  yearEl.addEventListener('input', () => { qEl.value=''; if (yearEl.value.length === 4) showYear(+yearEl.value); });
  qEl.addEventListener('input', () => { yearEl.value=''; showSearch(qEl.value); });
  showYear(2002);

  // live schedule + news, written to data/feeds.json by the daily GitHub Action
  (async function(){
    const ev = document.getElementById('feed-events'), nw = document.getElementById('feed-news'), st = document.getElementById('feed-stamp');
    try {
      const r = await fetch('data/feeds.json', {cache:'no-store'}); if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      const today = new Date(); today.setHours(0,0,0,0);
      const fmt = iso => { const x = new Date(iso + (iso.length === 10 ? 'T12:00:00' : '')); return x.toLocaleDateString('en-US',{month:'short',day:'numeric'}); };
      const events = (d.events||[]).filter(e => e.date && new Date(e.date + 'T23:59:59') >= today).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,8);
      ev.innerHTML = events.length ? events.map(e => '<li><span class="d">' + fmt(e.date) + '</span><span class="t">' + esc(e.name) + (e.squad ? ' <span class="tag">' + esc(e.squad) + '</span>' : '') + '<span class="m">' + esc([e.time, e.location].filter(Boolean).join(' · ')) + '</span></span></li>').join('')
        : '<li class="feed-empty">No upcoming races posted yet. Check the Vassar Athletics schedules above.</li>';
      const news = (d.news||[]).slice(0,6);
      nw.innerHTML = news.length ? news.map(n => '<li><span class="d">' + fmt(n.date) + '</span><span class="t"><a href="' + esc(n.url) + '" target="_blank" rel="noopener">' + esc(n.title) + '</a>' + (n.squad ? '<span class="m">' + esc(n.squad) + '</span>' : '') + '</span></li>').join('')
        : '<li class="feed-empty">No stories yet.</li>';
      if (d.updated) st.textContent = 'Schedule and news pulled automatically from vassarathletics.com · updated ' + new Date(d.updated).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}) + '.';
    } catch (err) {
      ev.innerHTML = '<li class="feed-empty">Schedule feed unavailable right now. See the Vassar Athletics links above.</li>';
      nw.innerHTML = '<li class="feed-empty">News feed unavailable right now.</li>';
    }
  })();

  // update form → prepared email text (the live site will post to a form service instead)
  const f = document.getElementById('f'), out = document.getElementById('out'), body = document.getElementById('body');
  const v = id => document.getElementById(id).value.trim();
  f.addEventListener('submit', e => {
    e.preventDefault();
    const lines = ['Vassar Rowing roster update', '',
      'Name: ' + v('f-name'), 'Class year: ' + v('f-year'), 'Squad: ' + v('f-squad'), 'Side: ' + v('f-side'),
      'Seasons rowed: ' + v('f-seasons'), 'Email: ' + v('f-email'), 'Phone: ' + v('f-phone'), '', v('f-note')];
    const txt = lines.join('\n');
    body.textContent = txt;
    document.getElementById('mailto').href = 'mailto:' + document.getElementById('addr').textContent + '?subject=' + encodeURIComponent('Roster update – Class of ' + v('f-year')) + '&body=' + encodeURIComponent(txt);
    out.classList.add('show'); out.scrollIntoView({behavior:'smooth', block:'nearest'});
  });
  document.getElementById('copy').addEventListener('click', function(){
    const btn = this;
    navigator.clipboard.writeText(body.textContent).then(()=>{ btn.textContent='Copied'; setTimeout(()=>btn.textContent='Copy text',1500); })
      .catch(()=>{ const r=document.createRange(); r.selectNodeContents(body); const s=getSelection(); s.removeAllRanges(); s.addRange(r); });
  });
})();
