let DATA = null;
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = value => { try { const u = new URL(value); return ['https:','http:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
const day = value => value ? new Date(value).toLocaleDateString('zh-CN',{year:'numeric',month:'short',day:'numeric'}) : '日期未知';
const time = value => value ? new Date(value).toLocaleString('zh-CN',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '尚无成功采集';
const company = id => DATA.companies.find(c => c.id === id) || {name:id};
const empty = message => `<div class="empty">${esc(message)}</div>`;

function setView(name) {
  $$('.view').forEach(node => node.classList.toggle('active', node.id === name));
  $$('.nav-link').forEach(node => node.classList.toggle('active', node.dataset.view === name));
  $('#crumb').textContent = ({overview:'总览',jobs:'招聘信号',changes:'每日变化',papers:'论文候选',coverage:'数据覆盖'})[name];
  history.replaceState(null,'','#'+name);
  window.scrollTo({top:0,behavior:'smooth'});
}

function renderOverview() {
  const ok = DATA.companies.filter(c => c.sources.jobs.status === 'ok');
  const weekAgo = Date.now() - 7*86400000;
  $('#stat-jobs').textContent = DATA.jobs.length.toLocaleString();
  $('#stat-sources').textContent = `${ok.length} / ${DATA.companies.length}`;
  $('#stat-sources').parentElement.querySelector('.stat-foot').textContent = 'NVIDIA 为定向搜索 · 其余为完整公开板';
  $('#stat-changes').textContent = DATA.events.filter(e => new Date(e.occurred_at).getTime() >= weekAgo).length;
  $('#stat-papers').textContent = DATA.papers.length;
  $('#company-grid').innerHTML = DATA.companies.map(c => {
    const status = c.sources.jobs.status;
    const partial = c.jobs && c.jobs.type === 'workday';
    const label = status === 'ok' ? (partial ? '定向搜索' : '招聘已接入') : status === 'error' ? '采集异常' : '待接入';
    return `<button class="company-card" data-company="${esc(c.id)}"><div class="company-top"><div class="company-icon">${esc(c.name[0])}</div><span class="company-status ${status === 'ok' ? '' : status === 'error' ? 'error' : 'pending'}">${label}</span></div><div class="company-name">${esc(c.name)}</div><div class="company-meta">${status === 'ok' ? `${c.relevant_jobs} 个相关职位${partial ? '（部分）' : ''} · ${esc(c.group)}` : `招聘数据待接入 · ${esc(c.group)}`}</div></button>`;
  }).join('');
  const recent = DATA.events.slice(0,4);
  $('#recent-changes').innerHTML = recent.length ? recent.map(e => `<div class="mini-row"><strong>${esc(company(e.company_id).name)} · ${esc(e.title)}</strong><span>${day(e.occurred_at)}</span></div>`).join('') : empty('目前只有首次基线，下一次成功采集后会显示真实变化。');
  $$('.company-card').forEach(node => node.addEventListener('click', () => { $('#job-company').value = node.dataset.company; renderJobs(); setView('jobs'); }));
}

function renderJobs() {
  const cid = $('#job-company').value;
  const topic = $('#job-topic').value;
  const query = $('#job-search').value.trim().toLowerCase();
  const jobs = DATA.jobs.filter(j => (!cid || j.company_id === cid) && (!topic || j.topics.includes(topic)) && (!query || `${j.title} ${j.location} ${company(j.company_id).name}`.toLowerCase().includes(query)));
  $('#job-count').textContent = `${jobs.length} 个职位 · 点击标题查看原始招聘页`;
  $('#job-list').innerHTML = jobs.length ? jobs.slice(0,150).map(j => `<article class="item"><div class="item-main"><a class="item-title" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener noreferrer">${esc(j.title)} ↗</a><div class="item-meta"><span>${esc(company(j.company_id).name)}</span><span>${esc(j.location || '地点未提供')}</span><span>${j.published_at ? `招聘页日期 ${day(j.published_at)}` : `首次观察 ${day(j.first_seen)}`}</span></div></div><div class="item-side">${j.topics.slice(0,3).map(t => `<span class="pill">${esc(t)}</span>`).join('')}</div></article>`).join('') : empty('没有符合筛选条件的职位。未接入公司不会显示职位数。');
  if (jobs.length > 150) $('#job-count').textContent += ' · 当前显示前 150 条';
}

function renderChanges() {
  const names = {new:'新出现',changed:'信息变化',reopened:'重新上架',removed:'已下架'};
  $('#change-list').innerHTML = DATA.events.length ? DATA.events.map(e => `<article class="item"><div class="item-main"><div class="item-title">${esc(e.title)}</div><div class="item-meta"><span>${esc(company(e.company_id).name)}</span><span>${time(e.occurred_at)}</span></div></div><div class="item-side"><span class="pill neutral event-${esc(e.kind)}">${names[e.kind] || esc(e.kind)}</span></div></article>`).join('') : empty('首次运行只建立基线。明天再次采集后，这里才会记录变化。');
}

function renderPapers() {
  $('#paper-list').innerHTML = DATA.papers.length ? DATA.papers.slice(0,100).map(p => `<article class="item"><div class="item-main"><a class="item-title" href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener noreferrer">${esc(p.title)} ↗</a><div class="item-meta"><span>${esc(company(p.company_id).name)} · 索引关联</span><span>${day(p.publication_date)}</span><span>OpenAlex 引用 ${p.citations}</span></div></div><div class="item-side"><span class="pill neutral">候选</span></div></article>`).join('') : empty('暂无符合筛选条件的论文候选。');
}

function searchLink(platform,name) {
  if (platform === 'linkedin') return 'https://www.linkedin.com/jobs/search/?keywords=' + encodeURIComponent(name + ' research');
  return 'https://x.com/search?q=' + encodeURIComponent(name + ' research') + '&src=typed_query&f=live';
}
function renderCoverage() {
  $('#coverage-list').innerHTML = DATA.companies.map(c => {
    const jobs = c.sources.jobs, papers = c.sources.papers;
    const status = s => s.status === 'ok' ? `<span class="ok">已更新 · ${time(s.last_success)}</span>` : s.status === 'error' ? `<span class="error">采集失败 · 上次成功 ${time(s.last_success)}</span>` : `<span class="pending">未接入</span>`;
    const jobStatus = c.jobs && c.jobs.type === 'workday' && jobs.status === 'ok' ? `<span class="ok">定向搜索 · ${time(jobs.last_success)}</span>` : status(jobs);
    return `<article class="coverage-row"><div><strong>${esc(c.name)}</strong><span class="label">${esc(c.group)}</span></div><div><span class="label">公开职位</span>${jobStatus}</div><div><span class="label">论文候选</span>${status(papers)}</div><div><span class="label">手动发现</span><a href="${esc(searchLink('linkedin',c.name))}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a> · <a href="${esc(searchLink('x',c.name))}" target="_blank" rel="noopener noreferrer">X ↗</a></div></article>`;
  }).join('');
}

async function load() {
  try {
    const response = await fetch('./data.json?ts='+Date.now(),{cache:'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    DATA = await response.json();
    $('#generated').textContent = '快照生成 ' + time(DATA.generated_at);
    const topics = [...new Set(DATA.jobs.flatMap(j => j.topics))].sort();
    $('#job-company').innerHTML = '<option value="">所有公司</option>' + DATA.companies.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');
    $('#job-topic').innerHTML = '<option value="">所有方向</option>' + topics.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join('');
    renderOverview(); renderJobs(); renderChanges(); renderPapers(); renderCoverage();
    const failures = DATA.companies.filter(c => c.sources.jobs.status === 'error');
    $('#notice').hidden = failures.length === 0;
    if (failures.length) $('#notice').textContent = `${failures.map(c => c.name).join('、')} 的招聘采集失败；页面保留上次成功快照，请查看数据覆盖。`;
    setView(['overview','jobs','changes','papers','coverage'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview');
  } catch (err) {
    $('#generated').textContent = '暂无数据';
    $('#notice').hidden = false;
    $('#notice').textContent = '尚未找到数据快照。请先运行一次采集：python3 -m radar collect。';
  }
}
$$('.nav-link').forEach(node => node.addEventListener('click', () => setView(node.dataset.view)));
$$('[data-go]').forEach(node => node.addEventListener('click', () => setView(node.dataset.go)));
['#job-company','#job-topic'].forEach(selector => $(selector).addEventListener('change',renderJobs));
$('#job-search').addEventListener('input',renderJobs);
$('#refresh').addEventListener('click',load);
load();
