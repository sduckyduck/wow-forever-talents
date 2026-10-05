// ===================== 任务百科（#/quests[/<任务ID>]）=====================
const QA_KIND = { 0:'普通任务',1:'精英任务',21:'职业任务',41:'PvP任务',62:'团队任务',81:'副本任务',82:'活动任务',83:'传奇任务',84:'护送任务' };
const QA_CHANGE = { new:'无限新增',updated:'无限改动',unchanged:'经典延续',unconfirmed:'资料待确认',unknown:'资料待补齐' };
const QA_SIDE = { 1:'联盟',2:'部落',3:'双方' };
const QA_CLASSES = [[1,'战士'],[2,'圣骑士'],[4,'猎人'],[8,'潜行者'],[16,'牧师'],[64,'萨满祭司'],[128,'法师'],[256,'术士'],[1024,'德鲁伊']];
const QA_REV='__QUEST_ASSET_REV__';
const qaSavedDone=store.get('forever-quest-completed-v1',[]);
const qa = { filters: { side:'',classMask:'',zone:'',dungeon:'',kind:'',change:'',search:'',min:'',max:'',hideDone:false,indexOnly:false }, page:0, id:null, load:null, entityLoad:null, detailLoad:new Map(), token:0, map:null, layers:null, tab:'all', error:null, done:new Set((Array.isArray(qaSavedDone)?qaSavedDone:[]).filter(id=>Number.isSafeInteger(id)&&id>0)), mapKinds:{start:true,end:true,npc:true,object:true,poi:true}, selectedPoint:null };
let QA = null, QAE = {}, QAI = {};
const qaEntityLoads=new Map();
window.FOREVER_QUEST_CHUNKS = {};
function questReadRoute(p) { qa.id = /^\d+$/.test(p[1] || '') ? +p[1] : null; }
function qaLoadScript(url) {
  return new Promise((resolve,reject) => { const s=document.createElement('script');s.src=url+'?v='+QA_REV;s.onload=resolve;s.onerror=()=>{s.remove();reject(new Error('任务数据加载失败，请重试。'));};document.head.appendChild(s); });
}
async function qaLoad() {
  if (!qa.load) qa.load = qaLoadScript('assets/quests/catalog.js').then(() => { QA=window.FOREVER_QUESTS;QAI=Object.fromEntries(QA.quests.map(q=>[q.id,q])); }).catch(e=>{qa.load=null;throw e;});
  return qa.load;
}
async function qaEntities(q) {
  if(!q)return;
  let keys=[...q.starts,...q.ends,...q.objectives.map(o=>o.entity),...(q.requiredSourceItems||[]),...(q.sourceItem?[q.sourceItem]:[]),...(q.spellObjectives||[]).map(o=>o.item).filter(Boolean),...(q.rewards?[...q.rewards.fixed,...q.rewards.choice].map(r=>r.entity):[])];
  for(let pass=0;pass<3;pass++){
    const chunks=[...new Set(keys.filter(k=>!QAE[k]).map(k=>{const [kind,id]=k.split(':');return `${kind}-${Math.floor(+id/2048)}`;}))];
    await Promise.all(chunks.map(chunk=>{if(!qaEntityLoads.has(chunk))qaEntityLoads.set(chunk,qaLoadScript(`assets/quests/entity-${chunk}.js`).then(()=>{QAE=window.FOREVER_QUEST_ENTITIES;}).catch(e=>{qaEntityLoads.delete(chunk);throw e;}));return qaEntityLoads.get(chunk);}));
    keys=keys.flatMap(k=>[...(QAE[k]?.drops||[]),...(QAE[k]?.vendors||[])]);
  }
}
async function qaGet(id) {
  if (!QAI[id]) return null;
  const chunk=Math.floor(id/256);
  if (!qa.detailLoad.has(chunk)) qa.detailLoad.set(chunk,qaLoadScript(`assets/quests/detail-${chunk}.js`).catch(e=>{qa.detailLoad.delete(chunk);throw e;}));
  await qa.detailLoad.get(chunk);
  return window.FOREVER_QUEST_CHUNKS[chunk]?.[id] || null;
}
const qaZone = z => QA?.zones[z]?.name || '地区待补齐';
const qaName = id => QAI[id]?.name || `任务 #${id}`;
function qaMoney(value){const c=Math.abs(Math.round(value));return (value<0?'−':'')+(c?tvMoney(c):'0铜');}
const qaKnown = q => q && (q.listed || q.observed);
function qaOption(value,label,selected) { return `<option value="${esc(String(value))}"${String(value)===String(selected)?' selected':''}>${esc(label)}</option>`; }
function qaSelect(key,label,options) { return `<label>${label}<select data-filter="${key}">${qaOption('','全部',qa.filters[key])}${options.map(([v,t])=>qaOption(v,t,qa.filters[key])).join('')}</select></label>`; }
function qaButton(id,label) { return `<button type="button" class="qa-link" data-quest="${id}">${esc(label || qaName(id))}</button>`; }
function qaSaveDone() { store.set('forever-quest-completed-v1',[...qa.done]); }
function qaDestroyMap() { if(qa.map){qa.map.remove();qa.map=null;} }
function qaBuildShell() {
  const el=document.getElementById('questsPage');
  const zoneIDs=[...new Set(QA.quests.filter(qaKnown).map(q=>q.zone).filter(z=>z!=null))];
  const zones=zoneIDs.sort((a,b)=>qaZone(a).localeCompare(qaZone(b),'zh-CN')).map(z=>[z,qaZone(z)]);
  const dungeons=Object.values(QA.zones).filter(z=>z.dungeon && QA.quests.some(q=>qaKnown(q)&&q.dungeons?.includes(z.id))).sort((a,b)=>a.name.localeCompare(b.name,'zh-CN')).map(z=>[z.id,z.name]);
  el.innerHTML=`<div class="qa-heading"><div><h2>任务百科</h2><p>先找到任务，再看前置、接取点、目标位置和奖励。</p></div><a href="#/travel" class="qa-link">打开旅行导航 →</a></div>
    <div class="qa-tabs" role="group" aria-label="任务浏览方式"><button type="button" data-qa-tab="all" aria-pressed="${qa.tab==='all'}">全部任务</button><button type="button" data-qa-tab="dungeon" aria-pressed="${qa.tab==='dungeon'}">副本出发准备</button><button type="button" data-qa-tab="progress" aria-pressed="${qa.tab==='progress'}">我的完成记录 <span id="qaDoneCount">${qa.done.size}</span></button></div>
    <div class="qa-filterbar"><label class="qa-search">搜索任务、NPC 或奖励<input id="qaSearch" data-filter="search" type="search" autocomplete="off" placeholder="中文名 / 英文名 / 任务ID / 装备" value="${esc(qa.filters.search)}"></label>
      ${qaSelect('side','阵营',[[1,'联盟'],[2,'部落'],[3,'双方任务']])}${qaSelect('classMask','职业',QA_CLASSES)}${qaSelect('zone','地区',zones)}
      <label class="qa-levels">任务等级<span><input data-filter="min" type="number" min="1" max="60" placeholder="1" aria-label="最低任务等级" value="${qa.filters.min}"><span>—</span><input data-filter="max" type="number" min="1" max="60" placeholder="60" aria-label="最高任务等级" value="${qa.filters.max}"></span></label>
      ${qaSelect('kind','类型', [['dungeon','副本任务'],['raid','团队任务'],['class','职业任务'],['elite','精英任务'],['chain','有任务链']])}
    </div>
    <div class="qa-advanced"><div>${qaSelect('change','版本',Object.entries(QA_CHANGE))}<label class="qa-check"><input type="checkbox" data-filter="hideDone"${qa.filters.hideDone?' checked':''}>隐藏已完成</label><label class="qa-check"><input type="checkbox" data-filter="indexOnly"${qa.filters.indexOnly?' checked':''}>显示ID、旧资料与占位条目</label><button type="button" class="qa-link" data-qa-action="reset">重置筛选</button></div><span>${QA.meta.foreverListed.toLocaleString()} 条有无限资料 · ${QA.meta.clientQuestIds.toLocaleString()} 个客户端ID</span></div>
    <div id="qaDungeonControls" class="qa-dungeon-controls"${qa.tab!=='dungeon'?' hidden':''}>${qaSelect('dungeon','准备前往的副本',dungeons)}<p>点开任务可展开副本外的全部已知前置；选择阵营后查看对应接取点。</p><button type="button" data-qa-action="prepare" class="qa-primary">展开这个副本的任务与前置</button><div id="qaPreparation" aria-live="polite"></div></div>
    <div id="qaProgressControls" class="qa-progress-controls"${qa.tab!=='progress'?' hidden':''}><p>手动完成记录保存在这台设备；可导出备份或在另一台设备导入。</p><button type="button" data-qa-action="export">导出记录</button><label class="qa-import">导入记录<input type="file" id="qaImport" accept=".json,application/json"></label><span id="qaImportStatus" role="status"></span></div>
    <div class="qa-workspace"><section class="qa-results" aria-label="任务搜索结果"><div class="qa-resulthead"><strong id="qaCount" role="status"></strong><span>等级 · 最低接取</span></div><div id="qaList"></div><div id="qaPager" class="qa-pager"></div></section><article id="qaDetail" class="qa-detail" aria-live="polite"><div class="qa-empty"><h3>选一个任务，展开完整资料</h3><p>可以先搜任务名，也可以选择副本查看出发前要接的任务。</p></div></article></div>
    <details class="qa-coverage"><summary>数据覆盖与版本说明</summary><p>当前客户端 ${esc(QA.meta.build)}；收录 ${QA.meta.foreverListed.toLocaleString()} 条公开无限任务，其中 ${QA.meta.changes.new} 条新增、${QA.meta.changes.updated} 条改动。${QA.meta.coverage.publicChinese.toLocaleString()} 条有中文名称，${QA.meta.coverage.publicRelations.toLocaleString()} 条有前后置关联，${QA.meta.coverage.publicStartCoordinates.toLocaleString()} 条有接取坐标（含继承数据）。</p><p>目录与奖励来自 Wowhead Forever；任务关系和目标位置合并 QuestieDB 的无限静态修正与社区采集。经典前置仍标作参考，坐标换算沿用原世界位置，尚未全部逐点实机验证。本机观察仅覆盖实际读到的字段。新增中文文本与部分服务器条件待补齐；经验显示数据库基础值。</p><p>客户端只有ID的任务不代表已开放；缺少资料会明确标出。</p><a href="assets/quests/manifest.json" target="_blank" rel="noopener">查看逐文件来源与覆盖记录</a><p>任务数据与中文词条来自 <a href="https://github.com/Questie/QuestieDB">QuestieDB</a> 和 <a href="https://github.com/Questie/Questie">Questie</a>（<a href="assets/quests/COPYING.txt">GPLv3</a>）。<a href="assets/quests/source/README.md">数据转换源码与固定版本来源</a>。</p></details>`;
  el.dataset.built='1';
  el.addEventListener('change',qaChange);
  el.addEventListener('input',qaInput);
  el.addEventListener('click',qaClick);
}
function qaRows() {
  const rows=QuestAtlasModel.filter(QA.quests,qa.filters,QA.zones,qa.done);
  return qa.tab==='progress'?rows.filter(q=>qa.done.has(q.id)):rows;
}
function qaRenderList() {
  const rows=qaRows(), size=50, pages=Math.max(1,Math.ceil(rows.length/size));
  qa.page=Math.min(qa.page,pages-1);
  document.getElementById('qaCount').textContent=`${rows.length.toLocaleString()} 个任务`;
  document.getElementById('qaDoneCount').textContent=qa.done.size;
  document.getElementById('qaList').innerHTML=rows.slice(qa.page*size,(qa.page+1)*size).map(q=>`<button type="button" class="qa-result${q.id===qa.id?' is-selected':''}" data-quest="${q.id}"${q.id===qa.id?' aria-current="true"':''}><span class="qa-resultname">${qa.done.has(q.id)?'<span class="qa-tick" aria-label="已完成">✓</span>':''}${esc(q.name)}${q.change==='new'?'<span class="qa-new">新</span>':''}</span><span class="qa-resultmeta">${esc(qaZone(q.zone))} · ${QA_SIDE[q.side]||'阵营待补齐'}${q.type===81?' · 副本':''}${q.classMask?' · 职业':''}</span><span class="qa-resultlevel">${q.level>0?q.level:'—'}<small>${q.minLevel>0?q.minLevel:'—'}级起</small></span></button>`).join('')||`<div class="qa-empty"><h3>${qa.tab==='progress'?'还没有完成记录':'当前筛选没有匹配任务'}</h3><p>${qa.tab==='progress'?'在任务详情里点“标记已完成”，就会出现在这里。':'可清空搜索或放宽地区、等级与版本筛选。'}</p></div>`;
  document.getElementById('qaPager').innerHTML=`<button type="button" data-qa-action="prev"${qa.page===0?' disabled':''}>上一页</button><span>${qa.page+1} / ${pages}</span><button type="button" data-qa-action="next"${qa.page+1===pages?' disabled':''}>下一页</button>`;
}
let qaSearchTimer;
function qaInput(e) { if(e.target.dataset.filter==='search'){clearTimeout(qaSearchTimer);qaSearchTimer=setTimeout(()=>{qa.filters.search=e.target.value;qa.page=0;qaRenderList();},140);} }
async function qaChange(e) {
  const key=e.target.dataset.filter;
  if(key && key!=='search'){qa.filters[key]=e.target.type==='checkbox'?e.target.checked:e.target.value;qa.page=0;qaRenderList();document.getElementById('qaPreparation').innerHTML='';}
  if(e.target.id==='qaImport'){
    const status=document.getElementById('qaImportStatus');
    try { const file=e.target.files[0];if(!file)return;if(file.size>1024*1024)throw new Error('进度文件过大，请选择本站导出的 JSON。');const ids=QuestAtlasModel.validateProgress(JSON.parse(await file.text()));qa.done=new Set([...qa.done,...ids]);qaSaveDone();status.textContent=`已合并 ${ids.length} 条记录。`;qaRenderList();if(qa.id)qaShowDetail(); }
    catch(error){status.textContent=error.message;}finally{e.target.value='';}
  }
}
function qaDownload(name,value) { const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
function qaClick(e) {
  const quest=e.target.closest('[data-quest]');
  if(quest){location.hash=`#/quests/${quest.dataset.quest}`;if(matchMedia('(max-width:900px)').matches)setTimeout(()=>document.getElementById('qaDetail').scrollIntoView({block:'start'}),50);return;}
  const tab=e.target.closest('[data-qa-tab]');
  if(tab){qa.tab=tab.dataset.qaTab;qa.page=0;qa.filters.kind=qa.tab==='dungeon'?'dungeon':'';if(qa.tab==='progress')qa.filters.hideDone=false;document.querySelectorAll('[data-qa-tab]').forEach(b=>b.setAttribute('aria-pressed',b===tab));document.getElementById('qaDungeonControls').hidden=qa.tab!=='dungeon';document.getElementById('qaProgressControls').hidden=qa.tab!=='progress';document.querySelector('[data-filter="kind"]').value=qa.filters.kind;document.querySelector('[data-filter="hideDone"]').checked=qa.filters.hideDone;qaRenderList();return;}
  const action=e.target.closest('[data-qa-action]')?.dataset.qaAction;
  if(action==='prev'||action==='next'){qa.page+=action==='next'?1:-1;qaRenderList();document.getElementById('qaCount').scrollIntoView({block:'nearest'});}
  if(action==='reset'){clearTimeout(qaSearchTimer);qa.filters={side:'',classMask:'',zone:'',dungeon:'',kind:qa.tab==='dungeon'?'dungeon':'',change:'',search:'',min:'',max:'',hideDone:false,indexOnly:false};document.querySelectorAll('[data-filter]').forEach(x=>{if(x.type==='checkbox')x.checked=false;else x.value=qa.filters[x.dataset.filter]||'';});qa.page=0;qaRenderList();}
  if(action==='done'&&qa.id){qa.done.has(qa.id)?qa.done.delete(qa.id):qa.done.add(qa.id);qaSaveDone();qaRenderList();qaShowDetail();}
  if(action==='downloadQuest'&&qa.current){const q=qa.current,keys=[...q.starts,...q.ends,...q.objectives.map(o=>o.entity),...(q.rewards?[...q.rewards.fixed,...q.rewards.choice].map(r=>r.entity):[])];for(const key of [...keys])keys.push(...(QAE[key]?.drops||[]));qaDownload(`forever-quest-${q.id}.json`,{schemaVersion:1,build:QA.meta.build,quest:q,entities:Object.fromEntries([...new Set(keys)].filter(k=>QAE[k]).map(k=>[k,QAE[k]]))});}
  if(action==='export')qaDownload('forever-quest-progress.json',{schemaVersion:1,product:'wow_classic_beta',completed:[...qa.done]});
  if(action==='prepare')qaPrepare();
  if(action==='retry')renderQuests();
  const point=e.target.closest('[data-point]');if(point){const p=qa._points?.[+point.dataset.point];if(p&&qa.map){qa.map.setView(qa.map.unproject(p.world,QA.worldmap.Z),Math.max(qa.map.getZoom(),QA.worldmap.Z-1));document.getElementById('qaMap').scrollIntoView({block:'nearest',behavior:'smooth'});}}
  const mapFilter=e.target.closest('[data-map-kind]');if(mapFilter){const key=mapFilter.dataset.mapKind;qa.mapKinds[key]=!qa.mapKinds[key];mapFilter.setAttribute('aria-pressed',qa.mapKinds[key]);qaPaintMap();}
}
async function renderQuests() {
  const el=document.getElementById('questsPage');
  if(!QA){el.innerHTML='<div class="qa-wait" role="status">正在载入任务目录…</div>';try{await qaLoad();}catch(e){el.innerHTML=`<div class="qa-empty"><p>${esc(e.message)}</p><button type="button" onclick="renderQuests()">重新加载</button></div>`;return;}}
  if(route.name!=='quests')return;
  if(!el.dataset.built)qaBuildShell();
  qaRenderList();
  if(qa.id)await qaShowDetail();
  else {qa.token++;qa.current=null;qaDestroyMap();document.getElementById('qaDetail').innerHTML='<div class="qa-empty"><h3>选一个任务，展开完整资料</h3><p>右侧会显示接取与交付、地图目标、奖励和全部已知前置。</p></div>';}
}
function qaEntityHtml(key,role='') {
  const e=QAE[key];if(!e)return '<li>对象资料待补齐</li>';
  const live=(qa.current?.currentPoints||[]).filter(p=>p.entity===key&&p.role===role);
  const positions=live.length?live:e.positions||[], grouped=new Map();
  for(const p of positions){if(!grouped.has(p.zone))grouped.set(p.zone,p);}
  return `<li><b>${esc(e.name)}</b>${e.kind==='item'?'<span class="qa-badge">物品触发</span>':''}${grouped.size?`<span>${[...grouped.values()].map(p=>`${esc(qaZone(p.zone))} (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`).join('；')}${positions.length>grouped.size?' 等多个位置':''}</span>`:e.instanceZones?.length?`<span>副本内：${e.instanceZones.map(qaZone).map(esc).join('、')} · 没有室内坐标</span>`:'<span>接取坐标待补齐</span>'}${e.kind==='item'&&e.drops?.length?`<span>来源：${e.drops.map(k=>esc(QAE[k]?.name||k)).join('、')}</span>`:''}</li>`;
}
function qaRewardHtml(reward) {
  const e=QAE[reward.entity];return `<li>${e?.icon?`<img src="https://wow.zamimg.com/images/wow/icons/medium/${encodeURIComponent(e.icon)}.jpg" alt="" loading="lazy" width="32" height="32">`:''}<div><a href="https://www.wowhead.com/forever/cn/item=${e?.id||0}" target="_blank" rel="noopener">${esc(e?.name||reward.entity)}</a>${reward.count>1?` × ${reward.count}`:''}${e?.itemLevel?`<small>物品等级 ${e.itemLevel}${e.requiredLevel?` · 使用等级 ${e.requiredLevel}`:''}</small>`:''}</div></li>`;
}
function qaConditions(q) {
  const rows=[];
  if(q.repeatable)rows.push('可重复任务');
  if(q.maxLevel>0)rows.push(`最高接取等级：${q.maxLevel}`);
  if(q.raceMask)rows.push(`种族：${(QA.races||[]).filter(r=>(BigInt(q.raceMask)&BigInt(r.bit))!==0n).map(r=>esc(r.name)).join('、')||'特殊种族条件，待核验'}`);
  if(q.requiredSkill)rows.push(`专业技能 #${esc(q.requiredSkill['1'])}，要求 ${esc(q.requiredSkill['2'])} 点`);
  for(const [key,label] of [['requiredMinRep','最低声望'],['requiredMaxRep','最高声望']])if(q[key])rows.push(`${label}：${esc(QA.factions[q[key]['1']]||`阵营 #${q[key]['1']}`)} ${esc(q[key]['2'])}`);
  if(q.requiredSpell)rows.push(`需要已学习法术 #${q.requiredSpell}`);
  if(q.requiredSpecialization)rows.push(`需要专业／专精 #${q.requiredSpecialization}`);
  if(q.requiredRanks)rows.push(`专业阶级任选一项：${Object.values(q.requiredRanks).map(r=>`专业 #${esc(r['1'])}，阶级 ${esc(r['2'])}`).join('；')}`);
  for(const [key,label]of [['availableStartingWith','需要正在进行或已完成'],['availableUntilCompleted','完成以下任务后无法再接'],['disabledByQuest','以下任务进行中时无法接取']])if(q[key])rows.push(`${label}：${qaButton(q[key])}`);
  if(q.supersededBy)rows.push(`以下任务已接取或已完成后，本条不再提供：${qaButton(q.supersededBy)}`);
  if(q.requiredSourceItems?.length)rows.push(`额外所需物品：${q.requiredSourceItems.map(k=>esc(QAE[k]?.name||k)).join('、')}`);
  return rows.map(x=>`<p>${x}</p>`).join('')||'<p>资料中暂未列出其他接取限制。</p>';
}
function qaTargetHtml(o) {
  const e=QAE[o.entity];if(!e)return `<li>${esc(o.entity)}</li>`;
  const targets=(e.drops||[]).map(k=>QAE[k]).filter(Boolean);
  return `<li>${esc(e.name)}${o.count?` × ${o.count}`:''}${targets.length?`<span>来源：${targets.map(t=>`${esc(t.name)}${t.instanceZones?.length?`（${t.instanceZones.map(qaZone).map(esc).join('、')}内）`:''}`).join('、')}</span>`:''}${e.instanceZones?.length?`<span>${e.instanceZones.map(qaZone).map(esc).join('、')}内 · 室内坐标待补齐</span>`:''}</li>`;
}
function qaObjectiveExtras(q) {
  const rows=[];
  if(q.sourceItem)rows.push(`接取时提供：${esc(QAE[q.sourceItem]?.name||q.sourceItem)}`);
  if(q.reputationObjective)rows.push(`目标声望：${esc(QA.factions[q.reputationObjective['1']]||`阵营 #${q.reputationObjective['1']}`)} ${esc(q.reputationObjective['2'])}`);
  for(const o of q.spellObjectives||[])rows.push(`${o.text?esc(o.text):`施放法术 #${o.spell}`}${o.item?`，使用 ${esc(QAE[o.item]?.name||o.item)}`:''}`);
  return rows.length?'<ul class="qa-targetnames">'+rows.map(t=>`<li>${t}</li>`).join('')+'</ul>':'';
}
async function qaLoadGraph(id) {
  const details=new Map(), pending=[id];let iterations=0;
  while(pending.length&&iterations++<100){const batch=[...new Set(pending.splice(0))].filter(x=>!details.has(x));if(!batch.length)break;const qs=await Promise.all(batch.map(qaGet));qs.forEach((q,i)=>{details.set(batch[i],q);if(q)pending.push(...QuestAtlasModel.prerequisites(q));});}
  return details;
}
function qaRelationList(ids) {return `<ul class="qa-chainlist">${ids.map(id=>{const q=QAI[Math.abs(id)],p=q?.startLocations?.[0];return `<li>${qa.done.has(Math.abs(id))?'<span class="qa-tick">✓</span>':''}${qaButton(Math.abs(id))}<span>${q?.minLevel>0?`${q.minLevel}级起 · `:''}${QA_SIDE[q?.side]||'阵营待补齐'} · ${esc(qaZone(q?.zone))}${id<0?' · 必须完成本条':''}</span>${p?`<span>接取：${esc(p.name)} · ${esc(qaZone(p.zone))} (${p.x.toFixed(1)}, ${p.y.toFixed(1)})</span>`:q?.starterNames?.length?`<span>接取：${q.starterNames.map(esc).join('、')} · 坐标待补齐</span>`:''}</li>`;}).join('')}</ul>`;}
async function qaShowDetail() {
  const token=++qa.token,id=qa.id,el=document.getElementById('qaDetail');
  qaDestroyMap();el.innerHTML='<div class="qa-wait" role="status">正在载入任务详情与前置链…</div>';
  try {
    const q=await qaGet(id);if(q)await qaEntities(q);
    if(token!==qa.token||route.name!=='quests')return;
    if(!q){el.innerHTML=`<div class="qa-empty"><h3>还没有任务 #${id} 的资料</h3><p>可以换一个任务ID或查看全部任务。</p></div>`;return;}
    const graph=await qaLoadGraph(id),anc=QuestAtlasModel.ancestors(id,x=>graph.get(x));
    if(token!==qa.token||route.name!=='quests')return;
    const r=q.rewards;
    qa.current=q;
    el.innerHTML=`<header class="qa-detailhead"><div><span class="qa-eyebrow">任务 #${q.id} · ${esc(qaZone(q.zone))}</span><h3>${esc(q.name)}</h3>${q.nameEn&&q.nameEn!==q.name?`<p>${esc(q.nameEn)}</p>`:''}</div><button type="button" data-qa-action="done" class="qa-primary" aria-pressed="${qa.done.has(id)}">${qa.done.has(id)?'✓ 已完成 · 撤销':'标记已完成'}</button></header>
      <div class="qa-facts"><span><b>${q.level>0?q.level:'—'}</b>任务等级</span><span><b>${q.minLevel>0?q.minLevel:'—'}</b>最低接取</span><span><b>${QA_SIDE[q.side]||'待补齐'}</b>阵营</span><span><b>${QA_KIND[q.type]||'类型待补齐'}</b>${QA_CHANGE[q.change]||'版本待补齐'}</span></div>
      ${q.classMask?`<p class="qa-restrictions">职业：${QA_CLASSES.filter(([bit])=>q.classMask&bit).map(([,cn])=>cn).join('、')}</p>`:''}
      ${!q.listed?'<p class="qa-notice">当前无限任务目录暂未列出本条。以下已有资料供查阅，开放状态待确认。</p>':''}
      <section class="qa-section"><h4>任务目标</h4>${q.change==='updated'&&!q.observedTexts?.length&&(q.textSource==='questiedb-forever-seed'||q.textSource==='questiedb-forever-seed-correction')?'<p class="qa-muted">经典目标参考，当前无限改动内容待核验。</p>':''}${(q.observedTexts?.length?q.observedTexts:q.texts).length?`<ul class="qa-objectivetext">${(q.observedTexts?.length?q.observedTexts:q.texts).map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:'<p class="qa-muted">目标文字待补齐；可先查看下方已有目标位置。</p>'}${q.objectives.length?`<ul class="qa-targetnames">${q.objectives.map(qaTargetHtml).join('')}</ul>`:''}${qaObjectiveExtras(q)}</section>
      <section class="qa-section"><div class="qa-sectiontitle"><h4>接取与交付</h4><span>${q.locationSource==='wowhead-forever'?'无限任务资料':q.locationSource==='questiedb-forever'?'无限任务库':'无限库继承资料'}</span></div><div class="qa-givers"><div><h5><span class="qa-pinicon start">!</span>在哪里接</h5><ul>${q.starts.map(k=>qaEntityHtml(k,'start')).join('')||'<li class="qa-muted">接取NPC／物品资料待补齐</li>'}</ul></div><div><h5><span class="qa-pinicon end">?</span>交给谁</h5><ul>${q.ends.map(k=>qaEntityHtml(k,'end')).join('')||'<li class="qa-muted">交付NPC资料待补齐</li>'}</ul></div></div></section>
      <section class="qa-section"><h4>地图位置</h4><div class="qa-mapkeys" role="group" aria-label="地图目标图层">${[['start','! 接取'],['end','? 交付'],['npc','⚔ 怪物／来源'],['object','◆ 物品／物体'],['poi','● 任务点']].map(([k,t])=>`<button type="button" data-map-kind="${k}" aria-pressed="${qa.mapKinds[k]}">${t}</button>`).join('')}</div><div id="qaMap" class="qa-map" aria-label="任务目标交互地图"><p class="qa-mapmessage">正在载入地图…</p></div><div id="qaMapPoints" class="qa-pointlist"></div><p class="qa-mapnote">图标表示接取、交付与目标分布；副本内目标会列出所属副本；未取得室内坐标时不放置室外怪物标记。</p></section>
      <section class="qa-section"><div class="qa-sectiontitle"><h4>前置与任务链</h4><span>${q.relationSource==='questiedb-forever'?'无限任务库':'经典链参考'}</span></div>${q.all.length?'<h5>以下前置都要完成</h5>'+qaRelationList(q.all):''}${q.any.length?'<h5>以下前置任选一个完成</h5>'+qaRelationList(q.any):''}${!q.all.length&&!q.any.length?`<p class="qa-muted">${q.relationSource?'资料中未列出必做前置。':'前置关系待补齐。'}</p>`:''}${q.parentActive?`<p>需要正在进行：${qaButton(q.parentActive)}</p>`:''}${q.breadcrumbs.length?'<details><summary>可选引导任务</summary>'+qaRelationList(q.breadcrumbs)+'</details>':''}${anc.ids.length?`<details open><summary>展开全部上游前置（${anc.ids.length} 条）</summary><p class="qa-muted">有“任选一个”的分支时，只需完成符合角色条件的一条。每条任务可继续查看它自己的接取点。</p>${qaRelationList(anc.ids)}</details>`:''}${anc.cycles.length?'<p class="qa-notice">此链包含循环或替代分支，循环边已停止展开。</p>':''}${q.next.length?'<h5>完成后关联的后续任务</h5>'+qaRelationList(q.next):''}${q.exclusive.length?'<h5>互斥或替代任务</h5>'+qaRelationList(q.exclusive):''}</section>
      <section class="qa-section"><h4>任务奖励</h4>${r?`<div class="qa-rewardnumbers">${r.xp!=null?`<span><b>${r.xp.toLocaleString()}</b> 基础经验</span>`:''}${r.money!=null?`<span><b>${qaMoney(r.money)}</b> ${r.money<0?'所需金钱':'奖励金钱'}</span>`:''}</div>${r.fixed.length?'<h5>固定获得</h5><ul class="qa-rewards">'+r.fixed.map(qaRewardHtml).join('')+'</ul>':''}${r.choice.length?'<h5>从以下奖励中选择</h5><ul class="qa-rewards">'+r.choice.map(qaRewardHtml).join('')+'</ul>':''}${r.reputation?.length?'<h5>声望</h5><ul>'+r.reputation.map(([f,n])=>`<li>${esc(QA.factions[f]||`阵营 #${f}`)} ${n>=0?'+':''}${n}</li>`).join('')+'</ul>':''}${!r.fixed.length&&!r.choice.length?'<p class="qa-muted">目录中未列出物品奖励。</p>':''}`:'<p class="qa-muted">奖励资料待补齐。</p>'}</section>
      <details class="qa-section qa-source"><summary>接取限制与资料来源</summary>${qaConditions(q)}<p>缺少条件记录时仍需以游戏中的接取要求为准；各字段保留来源，新任务中文文本未齐时显示原文。</p><a href="https://www.wowhead.com/forever/cn/quest=${q.id}" target="_blank" rel="noopener">查看此任务的无限资料页 ↗</a><button type="button" class="qa-link" id="qaCopyLink">复制任务链接</button><button type="button" class="qa-link" data-qa-action="downloadQuest">下载该任务资料</button><span id="qaCopyStatus" role="status"></span></details>`;
    document.getElementById('qaCopyLink').onclick=async()=>{try{await navigator.clipboard.writeText(location.href);document.getElementById('qaCopyStatus').textContent='链接已复制';}catch{document.getElementById('qaCopyStatus').textContent='可直接复制浏览器地址栏中的链接';}};
    qaCollectPoints(q);await qaDrawMap(token);
    if(token===qa.token&&route.name==='quests'){
      const rows=qa._points.map(p=>({name:p.name,zone:p.zone,x:p.x,y:p.y,source:p.source}));
      for(const p of q.currentPoints||[])if(!p.world)rows.push({...p,name:QAE[p.entity]?.name||p.entity});
      const section=document.getElementById('qaMapPoints');
      if(section&&rows.length)section.insertAdjacentHTML('afterend',`<details class="qa-coordinates"><summary>查看坐标表（${rows.length} 个位置）</summary><div class="qa-coordinate-table"><table><thead><tr><th>对象</th><th>地区</th><th>坐标</th></tr></thead><tbody>${rows.slice(0,150).map(p=>`<tr><td>${esc(p.name)}</td><td>${esc(qaZone(p.zone))}${p.floor>0?` · ${p.floor+1}层`:''}</td><td>${p.x!=null?`${p.x.toFixed(1)}, ${p.y.toFixed(1)}`:'世界坐标点'}</td></tr>`).join('')}</tbody></table></div>${rows.length>150?'<p class="qa-muted">此处显示前150个位置，下载该任务资料可查看全量坐标。</p>':''}</details>`);
    }
  }catch(e){if(token===qa.token)el.innerHTML=`<div class="qa-empty"><p>${esc(e.message)}</p><button type="button" onclick="qaShowDetail()">重新加载详情</button></div>`;}
}
function qaCollectPoints(q) {
  const result=[], seen=new Set();
  const add=(e,p,kind,source)=>{if(!p.world)return;const key=`${kind}/${e}/${p.world.join('/')}`;if(seen.has(key))return;seen.add(key);result.push({...p,entity:e,kind,source,name:e?QAE[e]?.name||e:p.label||'任务位置'});};
  const live=q.currentPoints||[];
  for(const [list,kind] of [[q.starts,'start'],[q.ends,'end']])for(const e of list){if(live.some(p=>p.entity===e&&p.role===kind))continue;for(const p of QAE[e]?.positions||[])add(e,p,kind,QAE[e].source);}
  if(!live.some(p=>p.role==='requirement'||p.role==='sourcerequirement'))for(const o of q.objectives){const e=QAE[o.entity];if(!e)continue;for(const p of e.positions||[])add(o.entity,p,e.kind,e.source);for(const key of e.drops||[])for(const p of QAE[key]?.positions||[])add(key,p,QAE[key].kind,QAE[key].source);}
  for(const p of live)add(p.entity,p,p.role==='start'?'start':p.role==='end'?'end':QAE[p.entity]?.kind||'poi',p.source);
  for(const p of q.positions||[])add(null,p,p.role==='start'?'start':p.role==='turnin'?'end':'poi',p.source||'local-game');
  qa._points=result;
}
async function qaDrawMap(token) {
  try {
    if(!window.L){if(!document.querySelector('link[data-qa-leaflet]')){const css=document.createElement('link');css.rel='stylesheet';css.href='assets/quests/vendor/leaflet.css';css.dataset.qaLeaflet='1';document.head.appendChild(css);}await qaLoadScript('assets/quests/vendor/leaflet.js');}
    if(token!==qa.token||route.name!=='quests')return;
    const el=document.getElementById('qaMap');el.innerHTML='';
    qa.map=L.map(el,{crs:L.CRS.Simple,minZoom:1,maxZoom:QA.worldmap.Z+1,attributionControl:false,preferCanvas:true});
    const [gw,gh]=QA.worldmap.grid,z=QA.worldmap.Z;
    const bounds=L.latLngBounds(qa.map.unproject([0,gh*256],z),qa.map.unproject([gw*256,0],z));
    const blank='data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==';
    const tiles=L.tileLayer('assets/travel/tiles/{z}/{x}/{y}.webp',{minZoom:0,maxNativeZoom:z,maxZoom:z+1,noWrap:true,bounds,errorTileUrl:blank});
    const tileIndex=Object.fromEntries(Object.entries(QA.worldmap.tiles).map(([level,rows])=>[level,new Set(rows)]));
    tiles.getTileUrl=function(c){return tileIndex[c.z]?.has(`${c.x}_${c.y}`)?`assets/travel/tiles/${c.z}/${c.x}/${c.y}.webp`:blank;};tiles.addTo(qa.map);
    qa.map.setMaxBounds(bounds.pad(.15));qa.layers=L.layerGroup().addTo(qa.map);
    qaPaintMap();
    const pts=qa._points.filter(p=>qa.mapKinds[p.kind]);
    if(pts.length)qa.map.fitBounds(L.latLngBounds(pts.map(p=>qa.map.unproject(p.world,z))),{padding:[32,32],maxZoom:z});else {qa.map.fitBounds(bounds);const note=document.createElement('div');note.className='qa-mapmessage';note.textContent='本条还没有可映射到世界地图的坐标。';el.appendChild(note);}
    qa.map.invalidateSize();
  }catch{if(token===qa.token){const el=document.getElementById('qaMap');if(el)el.innerHTML='<p class="qa-mapmessage">地图暂时无法加载，接取点和目标坐标仍可在资料表中查看。</p>';}}
}
function qaPaintMap() {
  if(!qa.map||!qa.layers)return;qa.layers.clearLayers();
  const colors={start:'#f5c842',end:'#79cbee',npc:'#df6b5e',object:'#a38ae2',poi:'#dce4ec'},icons={start:'!',end:'?',npc:'⚔',object:'◆',poi:'●'};
  const marked=new Set();
  for(const p of qa._points){if(!qa.mapKinds[p.kind])continue;const pos=qa.map.unproject(p.world,QA.worldmap.Z),key=`${p.entity}/${p.kind}/${p.zone}`;
    if(p.kind==='start'||p.kind==='end'||!marked.has(key)){marked.add(key);L.marker(pos,{title:p.name,icon:L.divIcon({className:`qa-marker ${p.kind}`,html:icons[p.kind],iconSize:[25,29],iconAnchor:p.kind==='end'?[29,27]:[3,27]})}).bindPopup(`${icons[p.kind]} ${esc(p.name)}<br>${esc(qaZone(p.zone))}${p.x!=null?` (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`:''}<br>${p.source==='wowhead-forever'?'无限任务资料':p.source==='client-db2'||p.source==='local-game'?'本机客户端':'Questie 无限任务库（含继承坐标）'}`).addTo(qa.layers);}
    else L.circleMarker(pos,{radius:5,color:colors[p.kind],fillColor:colors[p.kind],fillOpacity:.8,weight:1}).bindPopup(`${icons[p.kind]} ${esc(p.name)}<br>${esc(qaZone(p.zone))}${p.x!=null?` (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`:''}`).addTo(qa.layers);
  }
  const rows=[],names=new Set();for(let i=0;i<qa._points.length;i++){const p=qa._points[i];if(!qa.mapKinds[p.kind]||names.has(p.entity+'/'+p.kind+'/'+p.zone))continue;names.add(p.entity+'/'+p.kind+'/'+p.zone);rows.push(`<button type="button" data-point="${i}"><span>${icons[p.kind]}</span> ${esc(p.name)}<small>${esc(qaZone(p.zone))}${p.x!=null?` (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`:''}</small></button>`);}
  document.getElementById('qaMapPoints').innerHTML=rows.join('');
}
async function qaPrepare() {
  const el=document.getElementById('qaPreparation');
  if(!qa.filters.dungeon){el.innerHTML='<p>先选择准备前往的副本。</p>';return;}
  const key=JSON.stringify(qa.filters),rows=qaRows();el.innerHTML='<p role="status">正在展开所有已知前置…</p>';
  try {await qaEntities();const details=new Map();for(const row of rows){const g=await qaLoadGraph(row.id);for(const [id,q]of g)details.set(id,q);}if(key!==JSON.stringify(qa.filters))return;
    const ids=[...new Set([...details.keys()])],extra=ids.filter(id=>!rows.some(q=>q.id===id));
    const groups=QuestAtlasModel.preparationGroups(extra,id=>QAI[id],QA.zones);
    el.innerHTML=`<h4>${esc(qaZone(+qa.filters.dungeon))}：${rows.length} 条关联任务，${extra.length} 条上游前置</h4><p>建议出发前核对前置分支与职业限制；物品触发任务可在副本内取得后再接。</p><h5>副本关联任务</h5>${qaRelationList(rows.map(q=>q.id))}${groups.outside.length?'<h5>副本外的上游前置</h5>'+qaRelationList(groups.outside):''}${groups.instances.length?'<h5>涉及副本的上游前置</h5>'+qaRelationList(groups.instances):''}${groups.unknown.length?'<h5>地点资料待补齐的上游前置</h5>'+qaRelationList(groups.unknown):''}<button type="button" id="qaExportChecklist">导出任务清单</button>`;
    document.getElementById('qaExportChecklist').onclick=()=>qaDownload('forever-dungeon-checklist.json',{schemaVersion:1,dungeon:qaZone(+qa.filters.dungeon),side:qa.filters.side,tasks:ids.map(id=>({id,name:qaName(id),completed:qa.done.has(id),requiresAll:details.get(id)?.all||[],requiresAny:details.get(id)?.any||[]}))});
  }catch(e){el.innerHTML=`<p>${esc(e.message)}，可以点击按钮重试。</p>`;}
}
