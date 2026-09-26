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
    return '<details class="class-group"' + (pinned?' open':'') + '><summary class="class-head' + (pinned?' pinned':'') + '"><h3>Class of ' + year + '</h3><span class="count">' + ppl.length + (ppl.length===1?' person':' people') + '</span><span class="caret" aria-hidden="true"></span></summary><ul class="names">' + ppl.map(nameHTML).join('') + '</ul></details>';
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
      ? '<details class="class-group" open><summary class="class-head"><h3>' + hits.length + ' match' + (hits.length===1?'':'es') + '</h3><span class="caret" aria-hidden="true"></span></summary><ul class="names">' + hits.map(p => nameHTML(p).replace('</span>', ' <span class="alt">\'' + String(p.y).slice(2) + '</span></span>')).join('') + '</ul></details>'
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

  // committees: descriptions, members from the roster, hover/tap reveal, volunteer form
  const COMMITTEES = [
    ['EB','Endowment Board','Sets direction for the whole effort, keeps the committees moving, and is the alumni group\'s point of contact with Vassar Athletics and Advancement.'],
    ['SV','Strategic Vision','The long-range plan: what the program should look like in ten years and what it takes to get there.'],
    ['EF','Endowment Fundraising','Builds the permanent Rowing Endowment through anchor gifts and multi-year pledges, working through Advancement.'],
    ['BD','Brewer Day Challenge','Runs the annual day-of-giving push: cohort captains for each decade, the challenge structure, and the participation race.'],
    ['RE','Real Estate Ownership & Utilization','How the boathouse site on the Hudson is used, cared for, and improved over time.'],
    ['EQ','Equipment & Facilities Funding','Shells, oars, ergs, launches, and the boathouse itself: what the team needs and how it gets funded.'],
    ['AR','Annual Alum Rowing Event','Plans the fall alumni regatta weekend, from boatings and ergs to dinner.'],
    ['CB','Communications & Booster Activities','This website, the roster, newsletters, photos, and the outreach that keeps everyone connected.']
  ];
  const cWrap = document.getElementById('committees'), checks = document.getElementById('v-checks');
  if (cWrap) {
    COMMITTEES.forEach(([code, name, blurb]) => {
      const members = R.filter(p => Array.isArray(p.c) && p.c.includes(code)).sort((a,b)=> a.l.localeCompare(b.l) || a.f.localeCompare(b.f));
      const div = document.createElement('div'); div.className = 'cmte'; div.tabIndex = 0;
      div.innerHTML = '<div class="cmte-name"><span>' + esc(name) + '</span><span class="n">' + (members.length ? members.length + (members.length===1?' member':' members') : 'forming') + '</span></div>'
        + '<div class="cmte-body"><div>' + esc(blurb) + '</div><div class="members"><span class="lbl">Members</span>'
        + (members.length ? members.map(p => esc(p.f + ' ' + p.l) + ' \'' + String(p.y).slice(2)).join(', ') : 'Not yet announced. Raise your hand below.') + '</div></div>';
      div.addEventListener('click', () => div.classList.toggle('open'));
      cWrap.appendChild(div);
      if (checks && code !== 'EB') { const lab = document.createElement('label'); lab.innerHTML = '<input type="checkbox" value="' + esc(name) + '"> <span>' + esc(name) + '</span>'; checks.appendChild(lab); }
    });
    if (checks) { const lab = document.createElement('label'); lab.innerHTML = '<input type="checkbox" value="Cohort captain for my decade (Brewer Day)"> <span>Cohort captain for my decade (Brewer Day)</span>'; checks.appendChild(lab); }
  }
  const vf = document.getElementById('vf');
  if (vf) {
    const vout = document.getElementById('v-out'), vbody = document.getElementById('v-body');
    const vv = id => document.getElementById(id).value.trim();
    vf.addEventListener('submit', e => {
      e.preventDefault();
      const picked = [...vf.querySelectorAll('input[type=checkbox]:checked')].map(c => c.value);
      const txt = ['Vassar Rowing volunteer', '', 'Name: ' + vv('v-name'), 'Class year: ' + vv('v-year'), 'Email: ' + vv('v-email'), '',
        'Committees: ' + (picked.length ? picked.join('; ') : '(none picked)'), '', vv('v-note')].join('\n');
      vbody.textContent = txt;
      document.getElementById('v-mailto').href = 'mailto:' + document.getElementById('v-addr').textContent + '?subject=' + encodeURIComponent('Volunteer – Vassar Rowing committees') + '&body=' + encodeURIComponent(txt);
      vout.classList.add('show'); vout.scrollIntoView({behavior:'smooth', block:'nearest'});
    });
    document.getElementById('v-copy').addEventListener('click', function(){
      const btn = this;
      navigator.clipboard.writeText(vbody.textContent).then(()=>{ btn.textContent='Copied'; setTimeout(()=>btn.textContent='Copy text',1500); })
        .catch(()=>{ const r=document.createRange(); r.selectNodeContents(vbody); const s=getSelection(); s.removeAllRanges(); s.addRange(r); });
    });
  }

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
