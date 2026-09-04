(() => {
'use strict';
window.__PIXELVAULT_STARTED__=true;

const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const uid=(p='id')=>`${p}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,8)}`;
const iso=d=>{const x=new Date(d);x.setMinutes(x.getMinutes()-x.getTimezoneOffset());return x.toISOString().slice(0,10)};
const today=()=>iso(new Date());
const fmtDate=(d,opt={month:'short',day:'numeric',year:'numeric'})=>d?new Intl.DateTimeFormat(undefined,opt).format(new Date(`${d}T12:00:00`)):'';
// Date/time helpers used by Planner, reports, project due dates and home scheduling.
// Keep date-only math at local noon so DST changes cannot shift the calendar day.
function validDateOnly(value){return /^\d{4}-\d{2}-\d{2}$/.test(String(value||''))}
function dateAtNoon(value){
  const d=validDateOnly(value)?new Date(`${value}T12:00:00`):new Date(value||Date.now());
  return Number.isNaN(d.getTime())?new Date():d;
}
function dateShift(value,days=0){const d=dateAtNoon(value);d.setDate(d.getDate()+(Number(days)||0));return iso(d)}
function monthStart(value){const d=dateAtNoon(value);return iso(new Date(d.getFullYear(),d.getMonth(),1,12,0,0))}
function monthEnd(value){const d=dateAtNoon(value);return iso(new Date(d.getFullYear(),d.getMonth()+1,0,12,0,0))}
function weekStartOf(value){
  const d=dateAtNoon(value),sundayFirst=state?.settings?.weekStart==='sunday',offset=sundayFirst?d.getDay():(d.getDay()+6)%7;
  d.setDate(d.getDate()-offset);return iso(d);
}
function rangeDates(start,end){
  if(!validDateOnly(start)||!validDateOnly(end)||start>end)return[];
  const out=[];let cursor=start,guard=0;
  while(cursor<=end&&guard<4000){out.push(cursor);cursor=dateShift(cursor,1);guard++}
  return out;
}
function parseTime(value){
  const m=String(value||'').match(/^(\d{1,2}):(\d{2})/);if(!m)return 24*60;
  const h=Number(m[1]),min=Number(m[2]);if(!Number.isFinite(h)||!Number.isFinite(min)||h<0||h>23||min<0||min>59)return 24*60;
  return h*60+min;
}
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const tags=s=>Array.isArray(s)?s:String(s||'').split(',').map(x=>x.trim()).filter(Boolean);
const CFG=window.PIXELVAULT_CONFIG||{};
const ASSET_BASE=CFG.assetBase||'/static/pixelvault/assets/';
const UI_ICONS={home:'nav-home.webp',idea:'nav-ideas.webp',project:'nav-projects.webp',task:'nav-tasks.webp',planner:'nav-planner.webp',skill:'nav-skills.webp',report:'nav-reports.webp',annotation:'nav-notes.webp',settings:'nav-settings.webp'};
const iconAsset=key=>`${ASSET_BASE}${UI_ICONS[key]||key||''}`;
const iconImg=(key,cls='ui-icon',alt='')=>`<img class="${cls}" src="${iconAsset(key)}" alt="${esc(alt)}">`;
const sidebarMedia=()=>window.matchMedia('(max-width:850px)').matches;
let serverOnline=true;
let syncTimer=null,syncInFlight=false,syncQueued=false;

function getCookie(name){const row=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith(name+'='));return row?decodeURIComponent(row.split('=').slice(1).join('=')):''}
async function apiFetch(url,options={}){
  const headers=new Headers(options.headers||{});
  if(options.body&&!(options.body instanceof FormData)&&!headers.has('Content-Type'))headers.set('Content-Type','application/json');
  if(!/^(GET|HEAD)$/i.test(options.method||'GET'))headers.set('X-CSRFToken',getCookie('csrftoken'));
  return fetch(url,{credentials:'same-origin',...options,headers});
}
function defaultState(){return {version:4,settings:{signature:'',plannerView:'weekly',plannerAnchor:today(),skillSelected:null,theme:'pixel-night',accent:'pink',density:'comfortable',textSize:'large',reduceMotion:false,showGrid:true,showMascots:true,highContrast:false,largeTargets:false,sidebarCollapsed:false,displayName:'Local Builder',role:'Maker / Builder',workspaceName:'PixelVault',socialHandle:'',bio:'',avatar:'mascot-cat.webp',landingPage:'home',plannerDefaultView:'weekly',weekStart:'monday',workdayStart:7,workdayEnd:22,defaultTaskDuration:45,defaultHighlight:'yellow',showHighlights:true,confirmDeletes:true,workspaceRoot:'',plannerSnapMinutes:15,plannerHourPx:96},ideas:[],projects:[],tasks:[],skills:[],annotations:[]}}
let state=defaultState();
let toastTimer=null;
function toast(message,kind='success',detail=''){
  const el=$('#toast');if(!el)return;
  clearTimeout(toastTimer);
  const icon=kind==='error'?'!':kind==='warning'?'△':'✓';
  el.dataset.kind=kind;
  el.innerHTML=`<span class="toast-icon" aria-hidden="true">${icon}</span><span class="toast-copy"><b>${esc(message)}</b>${detail?`<small>${esc(detail)}</small>`:''}</span>`;
  el.classList.add('show');
  toastTimer=setTimeout(()=>el.classList.remove('show'),detail?4200:2800);
}
function mergeState(raw){const base=defaultState(),data=raw&&typeof raw==='object'?raw:{};return {...base,...data,version:4,settings:{...base.settings,...(data.settings||{})},ideas:Array.isArray(data.ideas)?data.ideas:[],projects:Array.isArray(data.projects)?data.projects:[],tasks:Array.isArray(data.tasks)?data.tasks:[],skills:Array.isArray(data.skills)?data.skills:[],annotations:Array.isArray(data.annotations)?data.annotations:[]}}
function setSyncState(kind,text){let el=$('#pv-sync-state');if(!el){el=document.createElement('span');el.id='pv-sync-state';el.className='sync-state';const actions=$('.top-actions');if(actions)actions.prepend(el)}if(!el)return;el.className='sync-state '+kind;el.textContent=text}
async function loadServerState(){const res=await apiFetch(CFG.stateUrl||'/api/state/');if(!res.ok)throw new Error(`Django state request failed (${res.status})`);state=mergeState(await res.json());serverOnline=true;return state}
function save(){renderCounts();clearTimeout(syncTimer);syncTimer=setTimeout(syncState,180)}
async function syncState(){
  if(syncInFlight){syncQueued=true;return false}
  syncInFlight=true;syncQueued=false;setSyncState('busy','SAVING…');
  try{
    const snapshot=JSON.stringify(state);
    const res=await apiFetch(CFG.stateUrl||'/api/state/',{method:'PUT',body:snapshot});
    if(!res.ok){const body=await res.json().catch(()=>({}));throw new Error(body.error||`Save failed (${res.status})`)}
    await res.json().catch(()=>null);serverOnline=true;setSyncState('ok','SAVED');
    setTimeout(()=>{const el=$('#pv-sync-state');if(el&&el.textContent==='SAVED')el.textContent='DJANGO ONLINE'},900);
    return true;
  }catch(e){
    serverOnline=false;setSyncState('error','SAVE ERROR');console.error('[PixelVault] Django sync failed',e);
    toast('SAVE FAILED','error','Your changes were not confirmed by Django. Check the server and try again.');
    return false;
  }finally{syncInFlight=false;if(syncQueued)syncState()}
}
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function flushSave(){
  clearTimeout(syncTimer);
  while(syncInFlight)await wait(35);
  return await syncState();
}
function exportBackup(){window.location.href=CFG.backupUrl||'/api/backup/export/'}
const THEMES=[
  {id:'pixel-night',name:'Pixel Night',mode:'Dark',desc:'Original purple arcade workspace.',swatches:['#0d0a1b','#ff4aa2','#23d9ff','#8cff3f']},
  {id:'neon-cyan',name:'Neon Circuit',mode:'Dark',desc:'Deep navy with cyan and electric violet.',swatches:['#06111b','#11e7ff','#8e6bff','#54ffb0']},
  {id:'synthwave',name:'Synth Sunset',mode:'Dark',desc:'Plum night with pink, orange and gold.',swatches:['#16081f','#ff3f9b','#ff8b35','#ffe052']},
  {id:'terminal',name:'Terminal Green',mode:'Dark',desc:'Near-black hacker terminal with phosphor green.',swatches:['#06100a','#5cff72','#20e0a0','#d8ff4d']},
  {id:'amber-crt',name:'Amber CRT',mode:'Dark',desc:'Warm retro monitor palette with amber highlights.',swatches:['#151008','#ffb52e','#ffd56a','#5de0d0']},
  {id:'paper-light',name:'Pixel Paper',mode:'Light',desc:'Clean warm paper with bold arcade accents.',swatches:['#f7f1df','#d62978','#087ea4','#4b8f16']},
  {id:'candy-light',name:'Candy Desktop',mode:'Light',desc:'Soft lilac desktop with playful neon details.',swatches:['#f6f0ff','#c52b83','#067f9f','#5c8f1f']}
];
const ACCENTS={pink:'#ff4aa2',cyan:'#23d9ff',lime:'#8cff3f',yellow:'#ffd447',violet:'#9b6bff',orange:'#ff8b2e'};

function applySettings(){
  const s=state.settings||{};const b=document.body;
  b.dataset.theme=s.theme||'pixel-night';b.dataset.density=s.density||'comfortable';b.dataset.textSize=s.textSize||'large';b.dataset.reducedMotion=s.reduceMotion?'true':'false';b.dataset.pixelGrid=s.showGrid===false?'false':'true';b.dataset.hideMascots=s.showMascots===false?'true':'false';b.dataset.highContrast=s.highContrast?'true':'false';b.dataset.largeTargets=s.largeTargets?'true':'false';b.dataset.sidebar=s.sidebarCollapsed?'collapsed':'expanded';
  document.documentElement.style.setProperty('--accent',ACCENTS[s.accent]||ACCENTS.pink);
  const meta=$('meta[name="theme-color"]');if(meta){requestAnimationFrame(()=>meta.setAttribute('content',getComputedStyle(document.documentElement).getPropertyValue('--bg2').trim()||'#17122f'))}
}
function renderProfileUI(){
  const s=state.settings,name=s.displayName||'Local Builder',workspace=s.workspaceName||'PixelVault',avatar=`${ASSET_BASE}${s.avatar||'mascot-cat.webp'}`;
  [['#topbar-profile-name',name],['#sidebar-profile-name',name.toUpperCase()],['#settings-mini-name',name.toUpperCase()],['#profile-preview-name',name],['#topbar-workspace-name',workspace],['#sidebar-workspace-name',workspace.toUpperCase()],['#settings-mini-workspace',workspace.toUpperCase()],['#profile-preview-workspace',workspace.toUpperCase()],['#profile-preview-role',s.role||'Maker / Builder'],['#profile-preview-handle',s.socialHandle||'']].forEach(([sel,val])=>{const el=$(sel);if(el)el.textContent=val});
  ['#topbar-avatar','#sidebar-mascot','#settings-mini-avatar','#profile-preview-avatar','#settings-page-mascot'].forEach(sel=>{const el=$(sel);if(el)el.src=avatar});
}
function renderThemeGrid(){
  const grid=$('#theme-grid');if(!grid)return;grid.innerHTML=THEMES.map(t=>`<button class="theme-card ${state.settings.theme===t.id?'active':''}" data-theme-choice="${t.id}"><span class="theme-card-top"><b>${esc(t.name)}</b><em>${t.mode}</em></span><span class="theme-swatches">${t.swatches.map(c=>`<i style="background:${c}"></i>`).join('')}</span><small>${esc(t.desc)}</small>${state.settings.theme===t.id?'<strong>✓ ACTIVE</strong>':''}</button>`).join('');
}
function renderSettingsData(){
  const raw=JSON.stringify(state),bytes=new Blob([raw]).size,kb=Math.max(0,bytes/1024),estimatedLimit=10*1024;
  const size=$('#settings-storage-size'),meter=$('#settings-storage-meter'),items=$('#settings-item-count'),anns=$('#settings-annotation-count');
  if(size)size.textContent=kb<1024?`${kb.toFixed(1)} KB`:`${(kb/1024).toFixed(2)} MB`;if(meter)meter.style.width=`${Math.min(100,kb/estimatedLimit*100)}%`;if(items)items.textContent=state.ideas.length+state.projects.length+state.tasks.length+state.skills.length;if(anns)anns.textContent=state.annotations.length;
}
function renderSettings(){
  const s=state.settings;
  const values={
    'setting-display-name':s.displayName,'setting-role':s.role,'setting-workspace-name':s.workspaceName,'setting-social-handle':s.socialHandle,'setting-avatar':s.avatar,'setting-bio':s.bio,'setting-accent':s.accent,'setting-density':s.density,'setting-text-size':s.textSize,'setting-landing-page':s.landingPage,'setting-planner-default':s.plannerDefaultView,'setting-week-start':s.weekStart,'setting-workday-start':s.workdayStart,'setting-workday-end':s.workdayEnd,'setting-task-duration':s.defaultTaskDuration,'setting-highlight-color':s.defaultHighlight,'setting-workspace-root':s.workspaceRoot||''
  };
  Object.entries(values).forEach(([id,v])=>{const el=$('#'+id);if(el&&document.activeElement!==el)el.value=v??''});
  [['setting-show-highlights',s.showHighlights!==false],['setting-reduce-motion',!!s.reduceMotion],['setting-show-grid',s.showGrid!==false],['setting-show-mascots',s.showMascots!==false],['setting-confirm-delete',s.confirmDeletes!==false],['setting-high-contrast',!!s.highContrast],['setting-large-targets',!!s.largeTargets]].forEach(([id,v])=>{const el=$('#'+id);if(el)el.checked=v});
  renderThemeGrid();renderProfileUI();renderSettingsData();updateHighlightToolbar();
}
function collectSettings(){
  const s=state.settings,get=id=>$('#'+id);s.displayName=get('setting-display-name')?.value.trim()||'Local Builder';s.role=get('setting-role')?.value.trim()||'Maker / Builder';s.workspaceName=get('setting-workspace-name')?.value.trim()||'PixelVault';s.socialHandle=get('setting-social-handle')?.value.trim()||'';s.avatar=get('setting-avatar')?.value||'mascot-cat.webp';s.bio=get('setting-bio')?.value.trim()||'';s.accent=get('setting-accent')?.value||'pink';s.density=get('setting-density')?.value||'comfortable';s.textSize=get('setting-text-size')?.value||'large';s.landingPage=get('setting-landing-page')?.value||'home';s.plannerDefaultView=get('setting-planner-default')?.value||'weekly';s.weekStart=get('setting-week-start')?.value||'monday';s.workdayStart=clamp(+get('setting-workday-start')?.value||7,0,23);s.workdayEnd=clamp(+get('setting-workday-end')?.value||22,s.workdayStart+1,24);s.defaultTaskDuration=clamp(+get('setting-task-duration')?.value||45,5,1440);s.defaultHighlight=get('setting-highlight-color')?.value||'yellow';s.showHighlights=get('setting-show-highlights')?.checked!==false;s.reduceMotion=!!get('setting-reduce-motion')?.checked;s.showGrid=get('setting-show-grid')?.checked!==false;s.showMascots=get('setting-show-mascots')?.checked!==false;s.confirmDeletes=get('setting-confirm-delete')?.checked!==false;s.highContrast=!!get('setting-high-contrast')?.checked;s.largeTargets=!!get('setting-large-targets')?.checked;s.workspaceRoot=get('setting-workspace-root')?.value.trim()||'';if(!s.signature&&s.socialHandle)s.signature=s.socialHandle;
  save();applySettings();renderProfileUI();renderSettingsData();updateHighlightToolbar();rehydrateAnnotations();
}
function resetAppearance(){Object.assign(state.settings,{theme:'pixel-night',accent:'pink',density:'comfortable',textSize:'large',reduceMotion:false,showGrid:true,showMascots:true,highContrast:false,largeTargets:false});save();applySettings();renderSettings();toast('APPEARANCE RESET')}
function updateHighlightToolbar(){const c=state.settings.defaultHighlight||'yellow';$$('#selection-toolbar [data-highlight]').forEach(b=>b.classList.toggle('default-highlight',b.dataset.highlight===c))}
async function testBackend(){try{const r=await apiFetch(CFG.healthUrl||'/api/health/');const d=await r.json();if(!r.ok)throw new Error(d.error||'Backend unavailable');toast(`DJANGO ${d.version||''} · SQLITE ONLINE`);setSyncState('ok','DJANGO ONLINE')}catch(e){toast('Django backend is unavailable');setSyncState('error','BACKEND OFFLINE')}}
function clearWorkspaceData(){if(state.settings.confirmDeletes!==false&&!confirm('Clear ALL ideas, projects, tasks, skills, highlights and comments? Export a backup first if needed.'))return;state.ideas=[];state.projects=[];state.tasks=[];state.skills=[];state.annotations=[];state.settings.skillSelected=null;save();renderAll();renderSettings();rehydrateAnnotations();toast('WORKSPACE CLEARED')}

let currentPage='home', ideaStatus='all', projectStatus='all', taskStatus='all', ideaView='grid', taskView='board', plannerView=state.settings.plannerDefaultView||state.settings.plannerView||'weekly', plannerAnchor=state.settings.plannerAnchor||today();
let pendingSelection=null, commandFilter='all', commandIndex=0, entityFormDirty=false;

function getProject(id){return state.projects.find(x=>x.id===id)}
function taskProjectName(t){return getProject(t.projectId)?.title||'Independent'}
function isOverdue(t){return t.status!=='done'&&t.dueDate&&t.dueDate<today()}
function completedOn(t,d){return t.status==='done'&&(t.completedAt||t.updated)===d}
function isPinned(x){return !!x.pinned}
function allPinned(){return [
  ...state.ideas.filter(isPinned).map(x=>({...x,_type:'Idea'})),
  ...state.projects.filter(isPinned).map(x=>({...x,_type:'Project'})),
  ...state.tasks.filter(isPinned).map(x=>({...x,_type:'Task'})),
  ...state.skills.filter(isPinned).map(x=>({...x,title:x.name,_type:'Skill'}))
]}

function safeRender(name,fn){try{fn();return true}catch(e){console.error(`[PixelVault] ${name} render failed`,e);return false}}
function renderAll(){
  const jobs=[['Home',renderHome],['Ideas',renderIdeas],['Projects',renderProjects],['Tasks',renderTasks],['Planner',renderPlanner],['Skills',renderSkills],['Reports',renderReports],['Annotations',renderAnnotations],['Counts',renderCounts],['Profile',renderProfileUI]];
  const failed=jobs.filter(([name,fn])=>!safeRender(name,fn)).map(([name])=>name);
  setTimeout(()=>safeRender('Highlights',rehydrateAnnotations),20);
  if(failed.length)showStartupNotice(`Some modules recovered from an error: ${failed.join(', ')}. Your workspace is still available.`,'warning');
  return failed.length===0;
}
function showStartupNotice(message,type='info'){
  let el=$('#startup-notice');
  if(!el){el=document.createElement('div');el.id='startup-notice';el.className='startup-notice';el.innerHTML='<strong></strong><span></span><button type="button" aria-label="Dismiss">×</button>';document.body.append(el);el.querySelector('button').onclick=()=>el.remove()}
  el.dataset.type=type;el.querySelector('strong').textContent=type==='warning'?'RECOVERY MODE':'PIXELVAULT';el.querySelector('span').textContent=message;
}
function dismissBoot(){const b=$('#boot');if(!b)return;b.classList.add('hide');clearTimeout(window.__pvBootWatchdog);setTimeout(()=>{if(b&&b.parentNode)b.remove()},650)}
function renderCounts(){
  const pinned=allPinned().length,todayOpen=state.tasks.filter(t=>t.scheduledDate===today()&&t.status!=='done').length,overdue=state.tasks.filter(isOverdue).length;
  const values={'#pin-count':pinned,'#today-count':todayOpen,'#overdue-count':overdue,'#nav-ideas-count':state.ideas.length,'#nav-projects-count':state.projects.length,'#nav-tasks-count':state.tasks.filter(t=>t.status!=='done').length,'#nav-skills-count':state.skills.length,'#nav-notes-count':state.annotations.length};
  Object.entries(values).forEach(([sel,val])=>{const el=$(sel);if(el)el.textContent=val});
}
function syncSidebarControls(){
  const sb=$('#sidebar')||$('.sidebar'),menu=$('#menu-toggle'),collapse=$('#sidebar-collapse'),mobile=sidebarMedia();if(!sb)return;
  const drawerOpen=mobile&&sb.classList.contains('open'),collapsed=!mobile&&!!state.settings.sidebarCollapsed;
  if(menu){menu.setAttribute('aria-expanded',mobile?String(drawerOpen):String(!collapsed));menu.classList.toggle('active',drawerOpen||collapsed);menu.title=mobile?(drawerOpen?'Close navigation':'Open navigation'):(collapsed?'Expand sidebar (Ctrl+B)':'Collapse sidebar (Ctrl+B)')}
  if(collapse){collapse.setAttribute('aria-expanded',String(!collapsed));collapse.title=collapsed?'Expand sidebar':'Collapse sidebar';const s=collapse.querySelector('span');if(s)s.textContent=collapsed?'»':'«'}
  sb.setAttribute('aria-hidden',mobile&&!drawerOpen?'true':'false');
}
function setSidebarOpen(open){
  const sb=$('#sidebar')||$('.sidebar'),backdrop=$('#sidebar-backdrop');if(!sb)return;
  if(!sidebarMedia()){sb.classList.remove('open');document.body.classList.remove('sidebar-drawer-open');if(backdrop)backdrop.hidden=true;syncSidebarControls();return}
  const opening=!!open&&!sb.classList.contains('open');
  sb.classList.toggle('open',!!open);document.body.classList.toggle('sidebar-drawer-open',!!open);
  if(opening){const scroller=$('.sidebar-scroll',sb);if(scroller)scroller.scrollTop=0}
  if(backdrop){backdrop.hidden=!open;backdrop.setAttribute('aria-hidden',open?'false':'true')}
  syncSidebarControls();
}
function setSidebarCollapsed(collapsed){state.settings.sidebarCollapsed=!!collapsed;applySettings();save();syncSidebarControls()}
function toggleSidebar(){const sb=$('#sidebar')||$('.sidebar');if(!sb)return;if(sidebarMedia())setSidebarOpen(!sb.classList.contains('open'));else setSidebarCollapsed(!state.settings.sidebarCollapsed)}
function pageTo(p){
  hideSelectionToolbar(true);currentPage=p; $$('.page').forEach(x=>x.classList.toggle('active',x.dataset.page===p)); $$('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.page===p));
  $$('.mobile-dock [data-page-jump]').forEach(x=>x.classList.toggle('active',x.dataset.pageJump===p));
  const title=$('#topbar-page-title');if(title)title.textContent=({home:'HOME',ideas:'IDEA LAB',projects:'PROJECTS',tasks:'TASKS',planner:'PLANNER',skills:'SKILLS.MD',reports:'REPORT STUDIO',annotations:'NOTES',settings:'SETTINGS'}[p]||p).toUpperCase();
  document.title=`${p.toUpperCase()} — PIXELVAULT`; window.scrollTo({top:0,behavior:state.settings.reduceMotion?'auto':'smooth'}); if(innerWidth<850)setSidebarOpen(false);
  if(p==='planner')renderPlanner(); if(p==='reports')renderReports(); if(p==='annotations')renderAnnotations(); if(p==='settings')renderSettings(); setTimeout(rehydrateAnnotations,30);
}

function openWorkspaceReference(type,id){
  const normalizedType=String(type||'').toLowerCase(),normalizedId=String(id||'');
  const pageMap={idea:'ideas',project:'projects',task:'tasks',skill:'skills'};
  const collectionMap={idea:'ideas',project:'projects',task:'tasks',skill:'skills'};
  if(!pageMap[normalizedType]||!/^[A-Za-z0-9_-]{1,128}$/.test(normalizedId))return false;
  const item=state[collectionMap[normalizedType]]?.find(entry=>String(entry.id)===normalizedId);
  if(!item){toast('LINKED ITEM NOT FOUND','warning','It may have been deleted or belong to another workspace.');return false}
  pageTo(pageMap[normalizedType]);
  setTimeout(()=>{
    if(normalizedType==='project')openProjectDetail(normalizedId);
    else if(normalizedType==='skill'){
      state.settings.skillSelected=normalizedId;renderSkills();
      $('#skill-editor')?.scrollIntoView({behavior:state.settings.reduceMotion?'auto':'smooth',block:'start'});
    }else openEntityDetail(normalizedType,normalizedId);
  },80);
  return true;
}

function consumeWorkspaceReference(){
  const params=new URLSearchParams(window.location.search),raw=params.get('open');
  if(!raw)return false;
  const match=raw.match(/^(project|idea|task|skill):([A-Za-z0-9_-]{1,128})$/i);
  const opened=!!match&&openWorkspaceReference(match[1],match[2]);
  params.delete('open');
  const query=params.toString();
  history.replaceState(history.state,'',`${location.pathname}${query?`?${query}`:''}${location.hash}`);
  return opened;
}

function statCard(label,value,sub,img,target=''){return `<div class="stat-card ${target?'clickable':''}" ${target?`data-page-jump="${target}" tabindex="0" role="button"`:''}><span class="stat-label">${esc(label)}</span><b>${esc(value)}</b><span class="stat-sub">${esc(sub)}</span>${img?`<img src="${ASSET_BASE}${img}" alt="">`:''}<i class="stat-glow"></i></div>`}
function renderHome(){
  const doneMonth=state.tasks.filter(t=>t.status==='done'&&(t.completedAt||t.updated||'').slice(0,7)===today().slice(0,7)).length;
  const todays=state.tasks.filter(t=>t.scheduledDate===today()).sort((a,b)=>parseTime(a.time)-parseTime(b.time));
  const todayOpen=todays.filter(t=>t.status!=='done'),todayDone=todays.filter(t=>t.status==='done'),mins=todayOpen.reduce((n,t)=>n+(+t.duration||0),0),overdue=state.tasks.filter(isOverdue).length;
  const next=todayOpen.find(t=>t.time&&parseTime(t.time)>=new Date().getHours()*60+new Date().getMinutes())||todayOpen[0];
  const briefTitle=$('#brief-title'),briefCopy=$('#brief-copy'),briefMetrics=$('#brief-metrics');
  if(briefTitle)briefTitle.textContent=next?`NEXT: ${next.title}`:todayDone.length?'TODAY IS CLEAR. NICE WORK.':'BUILD YOUR DAY.';
  if(briefCopy)briefCopy.textContent=next?`${next.time||'Anytime'} · ${taskProjectName(next)} · ${next.duration||state.settings.defaultTaskDuration||45} min estimated`:(overdue?`${overdue} overdue task${overdue===1?'':'s'} need review.`:'Nothing urgent is scheduled. Capture or plan the next useful step.');
  if(briefMetrics)briefMetrics.innerHTML=`<div><b>${todayDone.length}/${todays.length}</b><span>done today</span></div><div><b>${(mins/60).toFixed(mins%60?1:0)}h</b><span>remaining plan</span></div><div class="${overdue?'hot':''}"><b>${overdue}</b><span>overdue</span></div>`;
  $('#home-stats').innerHTML=[
    statCard('IDEAS',state.ideas.length,`${state.ideas.filter(x=>x.status==='ready').length} ready`,'mascot-fox.webp','ideas'),
    statCard('PROJECTS',state.projects.length,`${state.projects.filter(x=>x.status==='active').length} active`,'mascot-robot.webp','projects'),
    statCard('OPEN TASKS',state.tasks.filter(x=>x.status!=='done').length,`${overdue} overdue`,'mascot-ghost.webp','tasks'),
    statCard('SKILLS',state.skills.length,`${state.skills.filter(isPinned).length} pinned`,'mascot-owl.webp','skills'),
    statCard('DONE / MONTH',doneMonth,'completed tasks','mascot-raccoon.webp','reports')
  ].join('');
  const pinned=allPinned().slice(0,6); $('#home-pinned').innerHTML=pinned.length?pinned.map(x=>`<button class="mini-row home-open-item" data-home-type="${x._type}" data-id="${x.id}"><div><strong>${esc(x.title||x.name)}</strong><small>${esc(x._type)}${x.description?' · '+esc(x.description.slice(0,65)):''}</small></div><span class="chip yellow">${esc(x._type)}</span></button>`).join(''):'<div class="empty-state compact"><span>★</span><b>NOTHING PINNED YET</b><p>Pin the work you want within one click.</p></div>';
  $('#today-date').textContent=fmtDate(today(),{weekday:'short',month:'short',day:'numeric'});
  $('#home-today').innerHTML=todays.length?todays.map(t=>`<button class="timeline-item edit-task" data-id="${t.id}"><time>${esc(t.time||'ANYTIME')}</time><div><b>${esc(t.title)}</b><small>${esc(taskProjectName(t))}</small></div><span class="timeline-status ${t.status}">${t.status==='done'?'✓':'›'}</span></button>`).join(''):'<div class="empty-state compact"><span>▦</span><b>OPEN SPACE TODAY</b><p>Drag tasks into your day from the Planner.</p></div>';
  const active=state.projects.filter(x=>x.status==='active').sort((a,b)=>(b.pinned-a.pinned)||String(b.updated||'').localeCompare(String(a.updated||''))).slice(0,3); $('#home-projects').innerHTML=active.length?active.map(p=>`<div class="project-mini"><div class="card-top"><div><span class="status active">ACTIVE</span><h3>${esc(p.title)}</h3></div><button class="pin-btn ${p.pinned?'on':''}" data-pin="project" data-id="${p.id}">★</button></div><p>${esc(p.description||'No description yet.')}</p><div class="progress"><i style="width:${clamp(+p.progress||0,0,100)}%"></i></div><div class="project-mini-foot"><small>${+p.progress||0}% complete</small><button class="text-btn open-project" data-id="${p.id}">OPEN →</button></div></div>`).join(''):'<div class="empty-state"><span>📁</span><b>NO ACTIVE PROJECTS</b><p>Create a project and connect your tasks, ideas and files.</p></div>';
  const monthTasks=state.tasks.filter(t=>(t.scheduledDate||t.dueDate||t.created||'').slice(0,7)===today().slice(0,7)); const pct=monthTasks.length?Math.round(monthTasks.filter(t=>t.status==='done').length/monthTasks.length*100):0;
  $('#momentum-title').textContent=pct>=70?'STRONG MONTH. KEEP SHIPPING.':pct>=35?'MOMENTUM IS BUILDING.':'START SMALL. SHIP DAILY.'; $('#momentum-copy').textContent=`${doneMonth} tasks completed this month · ${pct}% of tracked monthly tasks are done.`;
}

function renderIdeas(){
  let arr=state.ideas.filter(i=>ideaStatus==='all'||i.status===ideaStatus); const q=($('#idea-search')?.value||'').toLowerCase(); if(q)arr=arr.filter(i=>JSON.stringify(i).toLowerCase().includes(q));
  const sort=$('#idea-sort')?.value||'updated';arr.sort((a,b)=>(b.pinned-a.pinned)||(sort==='title'?String(a.title).localeCompare(String(b.title)):sort==='priority'?({high:3,medium:2,low:1}[b.priority]||0)-({high:3,medium:2,low:1}[a.priority]||0):String(b.updated||b.created||'').localeCompare(String(a.updated||a.created||''))));
  const grid=$('#ideas-grid');grid.classList.toggle('list-view',ideaView==='list');
  grid.innerHTML=arr.length?arr.map(i=>`<article class="idea-card">
    <div class="card-accent ${i.priority||'medium'}"></div><div class="card-top"><div><div class="card-kicker"><span class="status ${i.status}">${esc(i.status)}</span><span class="chip">${esc(i.contentType||'note')}</span>${i.liveSiteUrl?'<span class="chip cyan">● LIVE</span>':''}</div><h3>${esc(i.title)}</h3></div><div class="card-top-actions"><button class="pin-btn ${i.pinned?'on':''}" data-pin="idea" data-id="${i.id}" title="Pin">★</button><button class="icon-btn edit-idea" data-id="${i.id}" title="Open idea details">↗</button></div></div>
    <p>${esc(i.description||'No short description yet.')}</p>
    ${i.goal?`<div class="card-context"><b>WHY</b><span>${esc(truncate(i.goal,120))}</span></div>`:''}
    <div class="chip-row"><span class="chip ${i.priority==='high'?'pink':i.priority==='low'?'lime':'yellow'}">${esc(i.priority||'medium')} priority</span>${tags(i.tags).slice(0,4).map(t=>`<span class="chip pink">#${esc(t)}</span>`).join('')}</div>
    ${i.nextAction?`<div class="next-action"><span>NEXT MOVE</span><b>${esc(i.nextAction)}</b></div>`:''}
    <div class="card-footer"><small>${getProject(i.projectId)?'→ '+esc(getProject(i.projectId).title):'Unlinked idea'}</small><div class="idea-card-actions">${i.liveSiteUrl?`<button class="text-btn open-live-site" data-url="${esc(i.liveSiteUrl)}">🌐 LIVE</button>`:''}<button class="text-btn idea-to-project" data-id="${i.id}">PROJECT</button><button class="text-btn edit-idea" data-id="${i.id}">OPEN →</button></div></div></article>`).join(''):'<div class="empty-state panel"><span>💡</span><b>NO IDEAS IN THIS VIEW</b><p>Capture a thought now. You can organize it later.</p><button class="neo-btn pink small" data-create="idea">＋ CAPTURE IDEA</button></div>';
}

function renderProjects(){
  const overview=$('#project-overview');if(overview){const active=state.projects.filter(p=>p.status==='active'),done=state.projects.filter(p=>p.status==='done'),avg=active.length?Math.round(active.reduce((n,p)=>n+(+p.progress||0),0)/active.length):0,due=active.filter(p=>p.dueDate&&p.dueDate<=dateShift(today(),7)).length;overview.innerHTML=`<div><span>ACTIVE</span><b>${active.length}</b></div><div><span>AVG PROGRESS</span><b>${avg}%</b></div><div><span>DUE ≤ 7 DAYS</span><b>${due}</b></div><div><span>SHIPPED</span><b>${done.length}</b></div>`}
  let arr=state.projects.filter(p=>projectStatus==='all'||p.status===projectStatus); const q=($('#project-search')?.value||'').toLowerCase(); if(q)arr=arr.filter(p=>JSON.stringify(p).toLowerCase().includes(q));const sort=$('#project-sort')?.value||'updated';arr.sort((a,b)=>(b.pinned-a.pinned)||(sort==='title'?String(a.title).localeCompare(String(b.title)):sort==='progress'?(+b.progress||0)-(+a.progress||0):sort==='deadline'?String(a.dueDate||'9999').localeCompare(String(b.dueDate||'9999')):String(b.updated||b.created||'').localeCompare(String(a.updated||a.created||''))));
  $('#projects-grid').innerHTML=arr.length?arr.map(p=>{const projectTasks=state.tasks.filter(t=>t.projectId===p.id),open=projectTasks.filter(t=>t.status!=='done').length,done=projectTasks.length-open,dueSoon=p.dueDate&&p.dueDate<=dateShift(today(),7)&&p.status!=='done';return `<article class="project-card">
    <div class="project-card-rail ${p.status}"></div><div class="card-top"><div><div class="card-kicker"><span class="status ${p.status}">${esc(p.status)}</span>${p.isWeb?'<span class="chip lime">WEB APP</span>':''}${p.githubPagesUrl?'<span class="chip cyan">● LIVE</span>':''}</div><h3>${esc(p.title)}</h3></div><div class="card-top-actions"><button class="pin-btn ${p.pinned?'on':''}" data-pin="project" data-id="${p.id}">★</button><button class="icon-btn open-project" data-id="${p.id}" title="Open workspace">↗</button></div></div>
    <p>${esc(p.description||'No project summary yet.')}</p><div class="project-metrics"><div><b>${open}</b><span>open tasks</span></div><div><b>${done}</b><span>done</span></div><div><b>${+p.progress||0}%</b><span>progress</span></div></div>
    <div class="progress project-progress"><i style="width:${clamp(+p.progress||0,0,100)}%"></i><span>${+p.progress||0}%</span></div>
    ${p.milestone?`<div class="next-action"><span>NEXT MILESTONE</span><b>${esc(p.milestone)}</b></div>`:''}
    <div class="chip-row">${tags(p.tags).slice(0,4).map(t=>`<span class="chip cyan">#${esc(t)}</span>`).join('')}${dueSoon?`<span class="chip pink">DUE ${esc(fmtDate(p.dueDate,{month:'short',day:'numeric'}))}</span>`:p.dueDate?`<span class="chip yellow">target ${esc(fmtDate(p.dueDate,{month:'short',day:'numeric'}))}</span>`:''}</div>
    <div class="project-path"><span>⌁</span>${esc(p.pathHint||'No folder connected yet')}</div>
    <div class="project-actions"><button class="neo-btn small open-project" data-id="${p.id}">OPEN WORKSPACE</button>${p.githubPagesUrl?`<button class="neo-btn cyan small open-github-pages" data-url="${esc(p.githubPagesUrl)}">🌐 LIVE SITE</button>`:''}${p.isWeb&&(p.launchUrl||p.pathHint)?`<button class="neo-btn small launch-project" data-id="${p.id}">▶ DEV / PREVIEW</button>`:''}</div>
  </article>`}).join(''):`<div class="empty-state featured panel"><img class="empty-mascot" src="${ASSET_BASE}mascot-robot.webp" alt="Pixel robot project mascot"><span class="eyebrow">PROJECT LIBRARY</span><h2>BUILD YOUR FIRST WORKSPACE</h2><p>A project connects goals, tasks, milestones, local files, launch links and the skills your agents use.</p><div class="empty-onboarding"><div><b>01</b><span>NAME IT</span><small>Define the outcome.</small></div><div><b>02</b><span>CONNECT</span><small>Add a local folder.</small></div><div><b>03</b><span>SHIP</span><small>Plan tasks & milestones.</small></div></div><div class="empty-actions"><button class="neo-btn cyan" data-create="project">＋ CREATE PROJECT</button><button class="neo-btn" data-page-jump="ideas">VIEW IDEAS</button></div></div>`;
}

function taskIsBlocked(t){const dep=state.tasks.find(x=>x.id===t.dependsOn);return !!(dep&&dep.status!=='done')}
function taskCard(t,compact=false){const blocked=taskIsBlocked(t),subDone=Array.isArray(t.subtasks)?t.subtasks.filter(x=>typeof x==='object'&&x.done).length:0,subTotal=Array.isArray(t.subtasks)?t.subtasks.length:0;return `<article class="task-card ${compact?'compact-planner':''} ${t.status==='done'?'is-done':''}" draggable="true" data-task-id="${t.id}">
  <div class="task-card-line ${t.priority||'medium'}"></div><div class="card-top"><div class="task-title-wrap"><button class="task-check ${t.status==='done'?'done':''}" data-task-toggle="${t.id}" title="${t.status==='done'?'Reopen':'Mark complete'}">${t.status==='done'?'✓':''}</button><h3>${esc(t.title)}</h3></div><div class="card-top-actions"><button class="pin-btn ${t.pinned?'on':''}" data-pin="task" data-id="${t.id}" title="Pin">★</button><button class="text-btn edit-task" data-id="${t.id}">OPEN</button></div></div>
  ${compact?'':`<p>${esc(t.description||'')}</p>`}<div class="task-meta"><span><i class="priority-dot ${t.priority}"></i>${esc(t.priority||'medium')}${t.taskType?` · ${esc(t.taskType)}`:''}</span><span>${esc(t.time||'ANYTIME')}</span></div>
  <div class="chip-row"><span class="chip cyan">${esc(taskProjectName(t))}</span>${blocked?'<span class="chip pink">BLOCKED</span>':''}${t.dueDate?`<span class="chip ${isOverdue(t)?'pink':'yellow'}">due ${esc(fmtDate(t.dueDate,{month:'short',day:'numeric'}))}</span>`:''}${t.duration?`<span class="chip">${t.duration}m</span>`:''}${t.recurrence&&t.recurrence!=='none'?`<span class="chip lime">↻ ${esc(t.recurrence)}</span>`:''}${subTotal?`<span class="chip">${subDone}/${subTotal} subtasks</span>`:''}</div>
</article>`}
function renderTasks(){
  const counts={todo:0,doing:0,done:0,overdue:0};state.tasks.forEach(t=>{counts[t.status]=(counts[t.status]||0)+1;if(isOverdue(t))counts.overdue++});
  $('#task-summary').innerHTML=statCard('TO DO',counts.todo,'not started','', '')+statCard('DOING',counts.doing,'in progress','', '')+statCard('DONE',counts.done,'all time','', '')+statCard('OVERDUE',counts.overdue,'needs attention','', '');
  const pf=$('#task-project-filter'); if(pf){const old=pf.value;pf.innerHTML='<option value="all">All projects</option>'+state.projects.map(p=>`<option value="${p.id}">${esc(p.title)}</option>`).join('');pf.value=[...pf.options].some(o=>o.value===old)?old:'all'}
  const q=($('#task-search')?.value||'').toLowerCase(), project=$('#task-project-filter')?.value||'all', priority=$('#task-priority-filter')?.value||'all',smart=$('#task-smart-filter')?.value||'all';
  let arr=state.tasks.filter(t=>(taskStatus==='all'||t.status===taskStatus)&&(project==='all'||t.projectId===project)&&(priority==='all'||t.priority===priority));
  if(smart==='today')arr=arr.filter(t=>t.scheduledDate===today());if(smart==='overdue')arr=arr.filter(isOverdue);if(smart==='pinned')arr=arr.filter(t=>t.pinned);if(smart==='unscheduled')arr=arr.filter(t=>!t.scheduledDate&&t.status!=='done');
  if(q)arr=arr.filter(t=>JSON.stringify(t).toLowerCase().includes(q)||taskProjectName(t).toLowerCase().includes(q));arr.sort((a,b)=>(b.pinned-a.pinned)||({high:3,medium:2,low:1}[b.priority]||0)-({high:3,medium:2,low:1}[a.priority]||0)||String(a.dueDate||'9999').localeCompare(String(b.dueDate||'9999')));
  const board=$('#task-board');board.classList.toggle('task-list-view',taskView==='list');
  if(taskView==='list'){
    board.innerHTML=`<div class="task-table-head"><span>STATUS / TASK</span><span>PROJECT</span><span>DUE</span><span>TIME</span><span></span></div>`+(arr.map(t=>`<div class="task-list-row"><div class="task-list-main"><button class="task-check ${t.status==='done'?'done':''}" data-task-toggle="${t.id}">${t.status==='done'?'✓':''}</button><div><b>${esc(t.title)}</b><small><i class="priority-dot ${t.priority}"></i>${esc(t.status)} · ${esc(t.priority)}</small></div></div><span>${esc(taskProjectName(t))}</span><span class="${isOverdue(t)?'danger-text':''}">${esc(t.dueDate?fmtDate(t.dueDate,{month:'short',day:'numeric'}):'—')}</span><span>${esc(t.time||'—')}</span><button class="text-btn edit-task" data-id="${t.id}">OPEN →</button></div>`).join('')||`<div class="empty-state"><span>✓</span><b>NO TASKS MATCH</b><p>Try clearing a filter or create your next action.</p></div>`);
  }else{
    const cols=taskStatus==='all'?['todo','doing','done']:[taskStatus]; board.innerHTML=cols.map(st=>`<section class="task-column" data-task-status="${st}"><div class="task-column-head"><span>${st==='todo'?'TO DO':st==='doing'?'DOING':'DONE'}</span><b>${arr.filter(t=>t.status===st).length}</b><button class="planner-day-add" data-create-task-status="${st}" title="Add task here">＋</button></div><div class="task-column-body">${arr.filter(t=>t.status===st).map(t=>taskCard(t)).join('')||'<div class="column-empty">DROP OR ADD TASKS HERE</div>'}</div></section>`).join('');bindTaskDrag();
  }
}

function bindTaskDrag(){
  $$('.task-card[draggable=true],.planner-time-block[draggable=true],.planner-anytime-task[draggable=true]').forEach(el=>{el.addEventListener('dragstart',e=>{el.classList.add('dragging');e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/task-id',el.dataset.taskId)});el.addEventListener('dragend',()=>el.classList.remove('dragging'))});
  $$('.task-column').forEach(col=>{col.addEventListener('dragover',e=>e.preventDefault());col.addEventListener('drop',e=>{e.preventDefault();const id=e.dataTransfer.getData('text/task-id'),t=state.tasks.find(x=>x.id===id);if(t){const old=t.status;t.status=col.dataset.taskStatus;t.updated=today();if(t.status==='done'&&old!=='done'){t.completedAt=today();spawnRecurringTask(t)}else if(t.status!=='done')t.completedAt='';save();renderAll()}})});
}

function plannerRange(){
  if(plannerView==='daily')return{start:plannerAnchor,end:plannerAnchor};
  if(plannerView==='weekly'){const start=weekStartOf(plannerAnchor);return{start,end:dateShift(start,6)}}
  return{start:monthStart(plannerAnchor),end:monthEnd(plannerAnchor)};
}
function plannerVisibleTasks(){const project=$('#planner-project-filter')?.value||'all',hideDone=$('#planner-hide-done')?.checked===true;return state.tasks.filter(t=>(project==='all'||t.projectId===project)&&(!hideDone||t.status!=='done'))}
function plannerHourPx(){return clamp(+state.settings.plannerHourPx||96,64,144)}
function plannerSnapMinutes(){const n=+state.settings.plannerSnapMinutes||15;return [15,30,60].includes(n)?n:15}
function taskDurationMinutes(t){return clamp(+t.duration||+state.settings.defaultTaskDuration||45,5,1440)}
function clockFromMinutes(mins){mins=((Math.round(mins)%1440)+1440)%1440;return `${String(Math.floor(mins/60)).padStart(2,'0')}:${String(mins%60).padStart(2,'0')}`}
function durationLabel(mins){mins=+mins||0;if(mins<60)return `${mins}m`;const h=Math.floor(mins/60),m=mins%60;return m?`${h}h ${m}m`:`${h}h`}
function plannerTimelineBounds(tasks=[]){
  let startHour=clamp(+state.settings.workdayStart||7,0,23),endHour=clamp(+state.settings.workdayEnd||22,startHour+1,24);
  tasks.forEach(t=>{const start=parseTime(t.time);if(start>=1440)return;const end=Math.min(1440,start+taskDurationMinutes(t));startHour=Math.min(startHour,Math.floor(start/60));endHour=Math.max(endHour,Math.ceil(end/60))});
  startHour=clamp(startHour,0,23);endHour=clamp(endHour,startHour+1,24);const hourPx=plannerHourPx();return{startHour,endHour,hourPx,totalPx:(endHour-startHour)*hourPx};
}
function layoutPlannerTasks(tasks,bounds){
  const min=bounds.startHour*60,max=bounds.endHour*60;
  const items=tasks.filter(t=>t.time&&parseTime(t.time)<1440).map(t=>({t,start:parseTime(t.time),end:parseTime(t.time)+taskDurationMinutes(t)})).sort((a,b)=>a.start-b.start||b.end-a.end);
  const groups=[];let group=null;
  items.forEach(item=>{if(!group||item.start>=group.end){group={items:[],end:item.end};groups.push(group)}group.items.push(item);group.end=Math.max(group.end,item.end)});
  const out=[];
  groups.forEach(g=>{const colEnds=[];g.items.forEach(item=>{let col=colEnds.findIndex(end=>end<=item.start);if(col<0)col=colEnds.length;colEnds[col]=item.end;item.col=col});const cols=Math.max(1,colEnds.length);g.items.forEach(item=>{const clippedStart=Math.max(min,item.start),clippedEnd=Math.min(max,item.end);if(clippedEnd<=clippedStart)return;out.push({t:item.t,start:item.start,end:item.end,top:((clippedStart-min)/60)*bounds.hourPx,height:Math.max(44,((clippedEnd-clippedStart)/60)*bounds.hourPx-4),left:(item.col/cols)*100,width:100/cols})})});
  return out;
}
function plannerTaskBlock(t,layout,mode='daily'){
  const duration=taskDurationMinutes(t),start=parseTime(t.time),end=start+duration,showMeta=layout.height>=74,showMore=layout.height>=112,project=taskProjectName(t),done=t.status==='done';
  const style=`top:${Math.round(layout.top)+2}px;height:${Math.round(layout.height)}px;left:calc(${layout.left}% + 3px);width:calc(${layout.width}% - 6px)`;
  return `<article class="planner-time-block priority-${esc(t.priority||'medium')} ${done?'is-done':''} ${layout.height<70?'is-short':''}" style="${style}" draggable="true" data-task-id="${t.id}" aria-label="${esc(t.title)} · ${durationLabel(duration)}">
    <div class="planner-block-accent"></div><div class="planner-block-top"><button class="task-check ${done?'done':''}" data-task-toggle="${t.id}" title="${done?'Reopen':'Mark complete'}">${done?'✓':''}</button><button class="planner-block-title edit-task" data-id="${t.id}" title="Open task"><b>${esc(t.title)}</b>${showMeta?`<small>${esc(t.time)}–${clockFromMinutes(end)} · ${durationLabel(duration)}</small>`:''}</button><button class="planner-block-menu-btn" data-planner-menu="${t.id}" title="Task actions" aria-label="Task actions">•••</button></div>
    ${showMore?`<div class="planner-block-meta"><span>${esc(project)}</span><span>${esc(t.priority||'medium')}</span>${taskIsBlocked(t)?'<span>BLOCKED</span>':''}</div>`:''}
    <div class="planner-task-menu" role="menu"><button data-planner-action="open" data-id="${t.id}">↗ OPEN</button><button data-planner-action="duplicate" data-id="${t.id}">⧉ DUPLICATE</button><button data-planner-action="tomorrow" data-id="${t.id}">→ MOVE +1 DAY</button><button data-planner-action="today" data-id="${t.id}">⌂ MOVE TO TODAY</button><button data-planner-action="unschedule" data-id="${t.id}">↥ UNSCHEDULE</button><button data-planner-action="toggle" data-id="${t.id}">${done?'↺ REOPEN':'✓ COMPLETE'}</button></div>
  </article>`;
}
function plannerAnytimeTask(t){return `<button class="planner-anytime-task edit-task ${t.status==='done'?'is-done':''}" data-id="${t.id}" draggable="true" data-task-id="${t.id}" title="Open ${esc(t.title)}"><span class="priority-dot ${esc(t.priority||'medium')}"></span><b>${esc(t.title)}</b><em>${durationLabel(taskDurationMinutes(t))}</em></button>`}
function timelineSlots(date,bounds){
  return Array.from({length:bounds.endHour-bounds.startHour},(_,i)=>{const h=bounds.startHour+i;return `<div class="planner-hour-slot" style="top:${i*bounds.hourPx}px;height:${bounds.hourPx}px"><button class="hour-add planner-add-date" data-date="${date}" data-hour="${h}" title="Add task at ${String(h).padStart(2,'0')}:00">＋</button></div>`}).join('');
}
function timelineGutter(bounds){return `<div class="planner-time-gutter" style="height:${bounds.totalPx}px">${Array.from({length:bounds.endHour-bounds.startHour+1},(_,i)=>{const h=bounds.startHour+i;return `<span style="top:${i*bounds.hourPx}px">${String(h).padStart(2,'0')}:00</span>`}).join('')}</div>`}
function plannerNowLine(date,bounds){if(date!==today())return '';const d=new Date(),mins=d.getHours()*60+d.getMinutes(),start=bounds.startHour*60,end=bounds.endHour*60;if(mins<start||mins>end)return '';const top=((mins-start)/60)*bounds.hourPx;return `<i class="planner-now-line" style="top:${Math.round(top)}px"><span>NOW</span></i>`}
async function duplicateTask(id){
  const source=state.tasks.find(t=>t.id===id);if(!source)return null;const before=JSON.parse(JSON.stringify(state)),copy=JSON.parse(JSON.stringify(source));Object.assign(copy,{id:uid('task'),title:`${source.title} (copy)`,status:'todo',completedAt:'',recurrence:'none',recurrenceSpawned:false,recurrenceParentId:'',pinned:false,created:today(),updated:today()});state.tasks.push(copy);renderAll();const ok=await flushSave();if(!ok){state=mergeState(before);renderAll();return null}renderAll();toast('TASK DUPLICATED','success',`${copy.title} kept the same schedule and duration.`);return copy;
}
function movePlannerTask(id,action){
  const t=state.tasks.find(x=>x.id===id);if(!t)return;
  if(action==='tomorrow')t.scheduledDate=dateShift(t.scheduledDate||today(),1);
  if(action==='today')t.scheduledDate=today();
  if(action==='unschedule'){t.scheduledDate='';t.time=''}
  if(action==='toggle'){const was=t.status;t.status=t.status==='done'?'todo':'done';t.completedAt=t.status==='done'?today():'';if(t.status==='done'&&was!=='done')spawnRecurringTask(t)}
  t.updated=today();save();renderAll();toast(action==='unschedule'?'TASK UNSCHEDULED':action==='toggle'?(t.status==='done'?'TASK COMPLETE':'TASK REOPENED'):'TASK RESCHEDULED');
}
function renderPlanner(){
  state.settings.plannerView=plannerView;state.settings.plannerAnchor=plannerAnchor;save();
  $$('#planner-view button').forEach(b=>b.classList.toggle('active',b.dataset.value===plannerView));
  const dateJump=$('#planner-date-jump');if(dateJump&&document.activeElement!==dateJump)dateJump.value=plannerAnchor;
  const snap=$('#planner-snap');if(snap)snap.value=String(plannerSnapMinutes());const zoom=$('#planner-zoom-label');if(zoom)zoom.textContent=`${Math.round(plannerHourPx()/96*100)}%`;
  const pf=$('#planner-project-filter');if(pf){const old=pf.value||'all';pf.innerHTML='<option value="all">All projects</option>'+state.projects.map(p=>`<option value="${p.id}">${esc(p.title)}</option>`).join('');pf.value=[...pf.options].some(o=>o.value===old)?old:'all'}
  const visible=plannerVisibleTasks(),q=($('#planner-inbox-search')?.value||'').trim().toLowerCase();
  const inbox=visible.filter(t=>t.status!=='done'&&!t.scheduledDate&&(!q||JSON.stringify(t).toLowerCase().includes(q)||taskProjectName(t).toLowerCase().includes(q))).sort((a,b)=>(b.pinned-a.pinned)||(a.priority==='high'?-1:1));
  $('#planning-inbox').innerHTML=inbox.length?inbox.map(t=>taskCard(t,true)).join(''):'<div class="planner-empty">No matching unscheduled tasks.</div>';
  const range=plannerRange(),scheduled=visible.filter(t=>t.scheduledDate&&t.scheduledDate>=range.start&&t.scheduledDate<=range.end),open=scheduled.filter(t=>t.status!=='done'),mins=scheduled.reduce((n,t)=>n+(+t.duration||0),0),overdue=visible.filter(isOverdue).length,unplanned=visible.filter(t=>t.status!=='done'&&!t.scheduledDate).length;
  $('#planner-summary').innerHTML=`<div class="planner-summary-card"><span>SCHEDULED</span><b>${scheduled.length}</b><em>${open.length} still open</em></div><div class="planner-summary-card"><span>PLANNED TIME</span><b>${(mins/60).toFixed(mins%60?1:0)}h</b><em>${mins} minutes</em></div><div class="planner-summary-card"><span>UNPLANNED</span><b>${unplanned}</b><em>in planning inbox</em></div><div class="planner-summary-card"><span>OVERDUE</span><b>${overdue}</b><em>${overdue?'needs review':'all clear'}</em></div>`;
  let html='';
  if(plannerView==='daily'){
    $('#planner-range').textContent=fmtDate(plannerAnchor,{weekday:'long',month:'long',day:'numeric',year:'numeric'});
    const list=visible.filter(t=>t.scheduledDate===plannerAnchor).sort((a,b)=>parseTime(a.time)-parseTime(b.time)),allDay=list.filter(t=>!t.time),timed=list.filter(t=>t.time),bounds=plannerTimelineBounds(timed),laid=layoutPlannerTasks(timed,bounds);
    html=`<div class="planner-all-day planner-drop" data-date="${plannerAnchor}" data-clear-time="true"><div class="planner-all-day-head"><b>ANYTIME / UNSLOTTED TODAY</b><button class="planner-day-add planner-add-date" data-date="${plannerAnchor}" title="Add task today">＋</button></div><div class="planner-anytime-list">${allDay.map(plannerAnytimeTask).join('')||'<span class="muted">Drop a task here to schedule it without a start time.</span>'}</div></div><div class="planner-timeline daily-timeline">${timelineGutter(bounds)}<div class="planner-time-lane planner-drop" data-timeline="true" data-date="${plannerAnchor}" data-start-hour="${bounds.startHour}" data-end-hour="${bounds.endHour}" data-hour-px="${bounds.hourPx}" style="height:${bounds.totalPx}px">${timelineSlots(plannerAnchor,bounds)}${plannerNowLine(plannerAnchor,bounds)}${laid.map(x=>plannerTaskBlock(x.t,x,'daily')).join('')}</div></div>`;
  } else if(plannerView==='weekly'){
    const start=weekStartOf(plannerAnchor),dates=rangeDates(start,dateShift(start,6));$('#planner-range').textContent=`${fmtDate(start,{month:'short',day:'numeric'})} — ${fmtDate(dates[6],{month:'short',day:'numeric',year:'numeric'})}`;
    const weekTasks=visible.filter(t=>t.scheduledDate>=start&&t.scheduledDate<=dates[6]),timed=weekTasks.filter(t=>t.time),bounds=plannerTimelineBounds(timed);
    const heads=dates.map(d=>{const list=weekTasks.filter(t=>t.scheduledDate===d),dayMins=list.reduce((n,t)=>n+taskDurationMinutes(t),0),overloaded=dayMins>8*60;return `<div class="week-day-head ${d===today()?'today':''}"><div><b>${fmtDate(d,{weekday:'short'}).toUpperCase()}</b><span>${fmtDate(d,{month:'short',day:'numeric'})}</span></div><button class="planner-day-add planner-add-date" data-date="${d}" title="Add task">＋</button><small class="${overloaded?'overloaded':''}">${list.length} task${list.length===1?'':'s'} · ${(dayMins/60).toFixed(dayMins%60?1:0)}h${overloaded?' · HEAVY':''}</small></div>`}).join('');
    const anytime=dates.map(d=>{const list=weekTasks.filter(t=>t.scheduledDate===d&&!t.time);return `<div class="week-anytime-cell planner-drop" data-date="${d}" data-clear-time="true">${list.map(plannerAnytimeTask).join('')||'<span>Drop anytime</span>'}</div>`}).join('');
    const lanes=dates.map(d=>{const list=weekTasks.filter(t=>t.scheduledDate===d&&t.time),laid=layoutPlannerTasks(list,bounds);return `<div class="week-day-lane planner-drop ${d===today()?'today':''}" data-timeline="true" data-date="${d}" data-start-hour="${bounds.startHour}" data-end-hour="${bounds.endHour}" data-hour-px="${bounds.hourPx}" style="height:${bounds.totalPx}px">${timelineSlots(d,bounds)}${plannerNowLine(d,bounds)}${laid.map(x=>plannerTaskBlock(x.t,x,'weekly')).join('')}</div>`}).join('');
    html=`<div class="week-timeline-shell"><div class="week-timeline-head"><div class="week-corner">WEEK</div>${heads}</div><div class="week-anytime-row"><div class="week-anytime-label">ANYTIME</div>${anytime}</div><div class="week-timeline-body">${timelineGutter(bounds)}<div class="week-timeline-days">${lanes}</div></div></div>`;
  } else {
    const first=monthStart(plannerAnchor),d0=new Date(`${first}T12:00:00`),sundayFirst=state.settings.weekStart==='sunday',lead=sundayFirst?d0.getDay():(d0.getDay()+6)%7,start=dateShift(first,-lead),dates=rangeDates(start,dateShift(start,41)),weekdays=sundayFirst?['SUN','MON','TUE','WED','THU','FRI','SAT']:['MON','TUE','WED','THU','FRI','SAT','SUN'];$('#planner-range').textContent=fmtDate(first,{month:'long',year:'numeric'});
    html=`<div class="calendar-grid">${weekdays.map(x=>`<div class="calendar-weekday">${x}</div>`).join('')}${dates.map(d=>{const inMonth=d.slice(0,7)===first.slice(0,7),list=visible.filter(t=>t.scheduledDate===d).sort((a,b)=>parseTime(a.time)-parseTime(b.time));return `<div class="calendar-cell planner-drop ${inMonth?'':'muted'} ${d===today()?'today':''}" data-date="${d}"><div class="calendar-cell-head"><div class="calendar-date">${+d.slice(8)}</div><button class="calendar-add planner-add-date" data-date="${d}" title="Add task">＋</button></div>${list.slice(0,6).map(t=>`<button class="calendar-task edit-task" data-id="${t.id}" title="${esc(t.title)}">${esc(t.time?`${t.time} `:'')}${esc(t.title)} <em>${durationLabel(taskDurationMinutes(t))}</em></button>`).join('')}${list.length>6?`<small class="calendar-more">+${list.length-6} more</small>`:''}</div>`}).join('')}</div>`;
  }
  $('#planner-canvas').innerHTML=html;bindTaskDrag();bindPlannerDrop();
}
function bindPlannerDrop(){
  $$('.planner-drop').forEach(el=>{el.addEventListener('dragover',e=>{e.preventDefault();el.classList.add('drag-over')});el.addEventListener('dragleave',e=>{if(!el.contains(e.relatedTarget))el.classList.remove('drag-over')});el.addEventListener('drop',e=>{e.preventDefault();el.classList.remove('drag-over');const t=state.tasks.find(x=>x.id===e.dataTransfer.getData('text/task-id'));if(!t)return;t.scheduledDate=el.dataset.date||t.scheduledDate;
      if(el.dataset.timeline==='true'){
        const rect=el.getBoundingClientRect(),start=+el.dataset.startHour||0,end=+el.dataset.endHour||24,snap=plannerSnapMinutes(),raw=start*60+((e.clientY-rect.top)/Math.max(1,rect.height))*((end-start)*60),snapped=clamp(Math.round(raw/snap)*snap,start*60,Math.max(start*60,(end*60)-snap));t.time=clockFromMinutes(snapped);
      }else if(el.dataset.clearTime==='true')t.time='';
      t.updated=today();save();renderPlanner();renderHome();renderTasks();toast('TASK SCHEDULED','success',t.time?`${fmtDate(t.scheduledDate,{month:'short',day:'numeric'})} · ${t.time} · ${durationLabel(taskDurationMinutes(t))}`:fmtDate(t.scheduledDate,{month:'short',day:'numeric'}))})});
  const inbox=$('#planning-inbox-panel');if(inbox){inbox.ondragover=e=>{e.preventDefault();inbox.classList.add('drag-over')};inbox.ondragleave=()=>inbox.classList.remove('drag-over');inbox.ondrop=e=>{e.preventDefault();inbox.classList.remove('drag-over');const t=state.tasks.find(x=>x.id===e.dataTransfer.getData('text/task-id'));if(!t)return;t.scheduledDate='';t.time='';t.updated=today();save();renderPlanner();renderHome();renderTasks();toast('TASK RETURNED TO PLANNING INBOX')}}
}
function markdownLite(md=''){
  let out=esc(md);out=out.replace(/^### (.*)$/gm,'<h4>$1</h4>').replace(/^## (.*)$/gm,'<h3>$1</h3>').replace(/^# (.*)$/gm,'<h2>$1</h2>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/^[-*] (.*)$/gm,'<li>$1</li>').replace(/((?:<li>.*<\/li>\n?)+)/g,'<ul>$1</ul>').replace(/^> (.*)$/gm,'<blockquote>$1</blockquote>').replace(/\n{2,}/g,'</p><p>').replace(/\n/g,'<br>');return `<p>${out}</p>`
}
let skillEditorTab='edit';
function renderSkills(){
  const q=($('#skill-search')?.value||'').toLowerCase(),pinnedOnly=$('#skill-pinned-only')?.checked===true,cat=$('#skill-category-filter')?.value||'all';
  const cf=$('#skill-category-filter');if(cf){const old=cf.value||'all',cats=[...new Set(state.skills.map(s=>s.category||'General'))].sort();cf.innerHTML='<option value="all">All categories</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');cf.value=[...cf.options].some(o=>o.value===old)?old:'all'}
  const activeCat=$('#skill-category-filter')?.value||'all';const arr=state.skills.filter(s=>(!q||JSON.stringify(s).toLowerCase().includes(q))&&(!pinnedOnly||s.pinned)&&(activeCat==='all'||(s.category||'General')===activeCat)).sort((a,b)=>(b.pinned-a.pinned)||a.name.localeCompare(b.name));
  const count=$('#skill-list-count');if(count)count.textContent=`${arr.length} of ${state.skills.length} skills`;
  $('#skills-list').innerHTML=arr.length?arr.map(s=>`<button class="skill-list-item ${state.settings.skillSelected===s.id?'active':''}" data-skill-open="${s.id}"><div class="card-top"><div><span class="skill-icon">◇</span><h3>${esc(s.name)}</h3></div><span class="pin-btn ${s.pinned?'on':''}" data-pin="skill" data-id="${s.id}">★</span></div><p>${esc(s.description)}</p><div class="skill-meta-line"><span>${esc(s.category||'General')}</span><span>v${esc(s.version||'1.0.0')}</span><span>${tags(s.agents).length} agent${tags(s.agents).length===1?'':'s'}</span></div><div class="chip-row">${tags(s.tags).slice(0,3).map(t=>`<span class="chip">#${esc(t)}</span>`).join('')}</div></button>`).join(''):'<div class="empty-state compact"><span>🧠</span><b>NO SKILLS FOUND</b><p>Adjust filters or create a reusable agent skill.</p></div>';
  const sk=state.skills.find(x=>x.id===state.settings.skillSelected),ed=$('#skill-editor');if(!sk){ed.innerHTML=`<div class="skill-editor-empty"><div><img src="${ASSET_BASE}mascot-owl.webp" alt=""><span class="eyebrow">AGENT KNOWLEDGE</span><h2>SELECT A SKILL</h2><p>Edit metadata, inspect usage and work directly on the attached Markdown source.</p><button class="neo-btn violet small" data-create="skill">＋ NEW SKILL</button></div></div>`;return}
  const lines=String(sk.content||'').split('\n').length,words=String(sk.content||'').trim().split(/\s+/).filter(Boolean).length;
  ed.innerHTML=`<div class="skill-editor-head"><div><span class="eyebrow">${esc(sk.category||'GENERAL')} · v${esc(sk.version||'1.0.0')}</span><h2>${esc(sk.name)}</h2><p class="muted">${esc(sk.description)}</p></div><button class="pin-btn ${sk.pinned?'on':''}" data-pin="skill" data-id="${sk.id}">★</button></div>
  <div class="skill-editor-tabs"><button class="${skillEditorTab==='edit'?'active':''}" data-skill-tab="edit">EDIT</button><button class="${skillEditorTab==='preview'?'active':''}" data-skill-tab="preview">PREVIEW</button><button class="${skillEditorTab==='metadata'?'active':''}" data-skill-tab="metadata">METADATA</button></div>
  <div class="skill-tab-panel ${skillEditorTab==='metadata'?'active':''}" data-skill-panel="metadata"><div class="field-grid"><label>Skill name<input id="skill-name-edit" class="retro-input" value="${esc(sk.name)}"></label><label>Category<input id="skill-category-edit" class="retro-input" value="${esc(sk.category||'')}"></label><label class="full">Short description<input id="skill-description-edit" class="retro-input" value="${esc(sk.description)}"></label><label>Version<input id="skill-version-edit" class="retro-input" value="${esc(sk.version||'1.0.0')}" placeholder="1.0.0"></label><label>Source / reference<input id="skill-source-edit" class="retro-input" value="${esc(sk.sourceUrl||'')}" placeholder="https://... or local reference"></label><label>Tags<input id="skill-tags-edit" class="retro-input" value="${esc(tags(sk.tags).join(', '))}"></label><label>Agents<input id="skill-agents-edit" class="retro-input" value="${esc(tags(sk.agents).join(', '))}"></label><label class="full">Best used for<textarea id="skill-use-cases-edit" class="retro-textarea" rows="4">${esc(Array.isArray(sk.useCases)?sk.useCases.join('\n'):(sk.useCases||''))}</textarea></label></div></div>
  <div class="skill-tab-panel ${skillEditorTab==='edit'?'active':''}" data-skill-panel="edit"><div class="markdown-toolbar"><div><b>📄 ${esc(sk.filename||'skill.md')}</b><small>${lines} lines · ${words} words</small></div><span class="chip ${sk.attachedFile?'lime':'yellow'}">${sk.attachedFile?'ATTACHED FILE':'DATABASE SOURCE'}</span></div><textarea id="skill-content-edit" class="retro-textarea markdown-editor" spellcheck="false">${esc(sk.content||'')}</textarea></div>
  <div class="skill-tab-panel ${skillEditorTab==='preview'?'active':''}" data-skill-panel="preview"><article class="markdown-preview">${markdownLite(sk.content||'# Empty skill')}</article></div>
  <div class="skill-actionbar"><div><button class="neo-btn danger small" data-delete-skill="${sk.id}">DELETE</button><button class="neo-btn small" data-attach-skill="${sk.id}">ATTACH .MD</button><button class="neo-btn small" data-download-skill="${sk.id}">DOWNLOAD</button></div><div><button class="neo-btn cyan small" data-save-skill-file="${sk.id}">SAVE FILE</button><button class="neo-btn lime small" data-save-skill="${sk.id}">SAVE CHANGES</button></div></div>`;
}

function getReportRange(period,date){
  if(period==='daily')return{start:date,end:date,label:fmtDate(date,{weekday:'long',month:'long',day:'numeric',year:'numeric'})};
  if(period==='weekly'){const start=weekStartOf(date),end=dateShift(start,6);return{start,end,label:`${fmtDate(start,{month:'short',day:'numeric'})} — ${fmtDate(end,{month:'short',day:'numeric',year:'numeric'})}`}}
  const start=monthStart(date),end=monthEnd(date);return{start,end,label:fmtDate(start,{month:'long',year:'numeric'})};
}
function reportSummary(){
  const period=$('#report-period')?.value||'daily', date=$('#report-date')?.value||today(), range=getReportRange(period,date), all=state.tasks.filter(t=>{const d=t.completedAt||t.updated||t.scheduledDate||t.dueDate||t.created;return d>=range.start&&d<=range.end}), done=all.filter(t=>t.status==='done'&&(t.completedAt||t.updated)>=range.start&&(t.completedAt||t.updated)<=range.end), planned=state.tasks.filter(t=>t.scheduledDate>=range.start&&t.scheduledDate<=range.end), mins=done.reduce((a,t)=>a+(+t.duration||0),0);
  const projects={};done.forEach(t=>{const n=taskProjectName(t);projects[n]=(projects[n]||0)+1}); const topProject=Object.entries(projects).sort((a,b)=>b[1]-a[1])[0]?.[0]||'—';
  return {period,date,range,all,done,planned,mins,hours:(mins/60).toFixed(1),topProject,projects,completion:planned.length?Math.round(done.length/planned.length*100):0,overdue:state.tasks.filter(t=>t.dueDate>=range.start&&t.dueDate<=range.end&&isOverdue(t)).length};
}
function publicTaskTitle(t,mode){if(mode==='full')return t.title;if(mode==='showcase')return t.title.replace(/\b(fix|debug|error|bug)\b/ig,'Improve');return t.title.replace(/\b(api|password|client|payment|private|secret|bug|error)\b/ig,'workflow')}
function renderReports(){
  if(!$('#report-date').value)$('#report-date').value=today(); if(!$('#report-signature').value)$('#report-signature').value=state.settings.signature||state.settings.socialHandle||state.settings.workspaceName||'';
  const s=reportSummary(), mode=$('#report-privacy').value||'full'; $('#report-range-label').textContent=s.range.label;$$('[data-report-period]').forEach(b=>b.classList.toggle('active',b.dataset.reportPeriod===s.period));
  const projectEntries=Object.entries(s.projects).sort((a,b)=>b[1]-a[1]).slice(0,5),projectMax=Math.max(1,...projectEntries.map(x=>x[1]));
  const plannedOpen=s.planned.filter(t=>t.status!=='done').length;
  $('#report-preview').innerHTML=`<div class="report-preview-top"><div><span class="eyebrow">PIXELVAULT · ${s.period.toUpperCase()} REPORT</span><h2 class="report-title">${esc(s.range.label)}</h2><p class="muted">A local snapshot of execution, focus and project momentum.</p></div><span class="report-preview-seal">${esc(mode==='full'?'PRIVATE':mode==='public'?'PUBLIC SAFE':'SHOWCASE')}</span></div><div class="report-stat-grid"><div class="report-stat"><b>${s.done.length}</b><span>COMPLETED</span></div><div class="report-stat"><b>${s.hours}h</b><span>FOCUS TIME</span></div><div class="report-stat"><b>${s.completion}%</b><span>COMPLETION</span></div><div class="report-stat"><b>${s.overdue}</b><span>OVERDUE</span></div></div><div class="report-insight-grid"><section><div class="report-section-title"><h3>TOP COMPLETIONS</h3><span>${s.done.length} done</span></div><div class="report-list">${s.done.slice(0,7).map(t=>`<div><span>✓</span><b>${esc(publicTaskTitle(t,mode))}</b><small>${esc(taskProjectName(t))}</small></div>`).join('')||'<div class="empty-report-row">No completed tasks in this period yet.</div>'}</div></section><section><div class="report-section-title"><h3>PROJECT MOMENTUM</h3><span>${Object.keys(s.projects).length} projects</span></div><div class="report-project-bars">${projectEntries.map(([name,count])=>`<div><div><b>${esc(name)}</b><span>${count}</span></div><i><em style="width:${Math.round(count/projectMax*100)}%"></em></i></div>`).join('')||'<div class="empty-report-row">No completed project work in this period.</div>'}</div><div class="report-callout"><span>MOST ACTIVE</span><b>${esc(s.topProject)}</b><small>${plannedOpen} scheduled task${plannedOpen===1?'':'s'} still open</small></div></section></div>`;
}

function renderAnnotations(){
  const filter=$('#annotation-page-filter'); if(filter&&filter.options.length===1){['home','ideas','projects','tasks','planner','skills','reports','annotations','settings'].forEach(p=>filter.insertAdjacentHTML('beforeend',`<option value="${p}">${p.toUpperCase()}</option>`))}
  const f=filter?.value||'all',color=$('#annotation-color-filter')?.value||'all',q=($('#annotation-search')?.value||'').trim().toLowerCase();let arr=state.annotations.filter(a=>(f==='all'||a.page===f)&&(color==='all'||a.color===color)&&(!q||`${a.quote} ${a.comment||''} ${a.page}`.toLowerCase().includes(q))).sort((a,b)=>b.created.localeCompare(a.created));
  const summary=$('#annotation-summary');if(summary){const comments=state.annotations.filter(a=>a.comment).length,pages=new Set(state.annotations.map(a=>a.page)).size;summary.innerHTML=`<div><span>HIGHLIGHTS</span><b>${state.annotations.length}</b></div><div><span>WITH COMMENTS</span><b>${comments}</b></div><div><span>PAGES COVERED</span><b>${pages}</b></div><div><span>VISIBLE NOW</span><b>${arr.length}</b></div>`}
  $('#annotations-list').innerHTML=arr.length?arr.map(a=>`<article class="annotation-card"><div class="annotation-color ${a.color}"></div><div class="annotation-content"><div class="annotation-meta"><span class="chip ${a.color==='yellow'?'yellow':a.color}">${esc(a.page.toUpperCase())}</span><time>${esc(new Date(a.created).toLocaleString())}</time></div><blockquote>“${esc(a.quote)}”</blockquote>${a.comment?`<p>${esc(a.comment)}</p>`:'<p class="muted">Highlight only · no comment attached.</p>'}<div class="annotation-actions"><button class="text-btn annotation-open-page" data-page-jump="${a.page}">OPEN SOURCE PAGE →</button></div></div><button class="icon-btn delete-annotation" data-id="${a.id}" title="Delete">×</button></article>`).join(''):'<div class="empty-state panel"><span>✎</span><b>NO NOTES MATCH</b><p>Select text anywhere in PixelVault to highlight it or attach a comment.</p></div>';
}

function renderEntityForm(type,obj={}){
  let sectionIndex=0;const isEdit=!!obj.id;
  const head=(iconKey,title,copy)=>`<div class="form-dialog-head"><div class="form-dialog-title"><span class="eyebrow eyebrow-icon">${iconImg(iconKey,'dialog-entity-icon',title)} <span>${isEdit?'EDIT EXISTING':'CREATE NEW'}</span></span><h2>${title}</h2><p>${copy}</p></div><div class="form-dialog-head-actions"><span class="settings-badge safe">DJANGO</span><button type="button" class="form-close-btn" data-form-close aria-label="Close form">×</button></div></div><div class="form-dialog-context"><span><i class="online-dot"></i> SAVE CONFIRMED BY DJANGO</span><span><b>*</b> REQUIRED FIELD</span>${isEdit?`<span>UPDATED ${esc(obj.updated||'—')}</span>`:'<span>NEW WORKSPACE ITEM</span>'}</div>`;
  const section=(title,help,body)=>{sectionIndex+=1;return `<section class="form-section"><div class="form-section-title"><span class="form-section-number">${String(sectionIndex).padStart(2,'0')}</span><div><h3>${title}</h3><small>${help}</small></div></div><div class="dialog-form-grid">${body}</div></section>`};
  const pin=(checked)=>`<label class="form-pin-field"><span><b>★ PIN THIS ITEM</b><small>Keep it in Quick Access and dashboard highlights.</small></span><span class="switch"><input name="pinned" type="checkbox" ${checked?'checked':''}><span></span></span></label>`;
  const actions=(type,color,extra='')=>`<div class="dialog-actions"><div class="form-save-note"><span>✓</span><div><b>SAFE SAVE</b><small>The form closes only after Django confirms the save.</small></div></div>${extra}<button type="button" class="neo-btn small" data-form-close>CANCEL</button><button type="button" class="neo-btn ${color} entity-save" data-type="${type}" data-id="${obj.id||''}">${isEdit?'SAVE CHANGES':`CREATE ${type.toUpperCase()}`}</button></div>`;
  const shell=(header,sections,footer)=>`${header}<div class="form-dialog-scroll">${sections}</div>${footer}`;

  if(type==='idea'){
    const sections=section('CORE IDEA','Give the idea a clear identity so it is easy to scan later.',`<label>Title <span class="form-required">*</span><input name="title" class="retro-input" required value="${esc(obj.title||'')}" placeholder="A short, memorable idea name"><small class="field-help">Use a name you will recognize in search and reports.</small></label><label>Status<select name="status" class="retro-select">${['inbox','exploring','ready','building'].map(x=>`<option ${obj.status===x?'selected':''}>${x}</option>`).join('')}</select><small class="field-help">Move ideas through your discovery pipeline.</small></label><label>Priority<select name="priority" class="retro-select">${['low','medium','high'].map(x=>`<option ${(obj.priority||'medium')===x?'selected':''}>${x}</option>`).join('')}</select></label><label>Content type<select name="contentType" class="retro-select">${['note','prompt','webpage','reference'].map(x=>`<option ${obj.contentType===x?'selected':''}>${x}</option>`).join('')}</select></label><label class="full">Short description<input name="description" class="retro-input" value="${esc(obj.description||'')}" placeholder="One-sentence summary"><small class="field-help">This appears on cards, search results and reports.</small></label><div class="full">${pin(!!obj.pinned)}</div>`)
      +section('CONTEXT','Capture why it matters before the original thought gets lost.',`<label class="full">Goal / problem to solve<textarea name="goal" rows="3" class="retro-textarea" placeholder="What outcome should this idea create?">${esc(obj.goal||'')}</textarea></label><label>Audience / user<input name="audience" class="retro-input" value="${esc(obj.audience||'')}" placeholder="Who is this for?"></label><label>Source / reference URL<input name="sourceUrl" type="url" class="retro-input" value="${esc(obj.sourceUrl||'')}" placeholder="https://..."><small class="field-help">Original inspiration, article, repository or reference.</small></label><label>Live site URL<input name="liveSiteUrl" type="url" class="retro-input" value="${esc(obj.liveSiteUrl||'')}" placeholder="https://your-site.example/"><small class="field-help">Optional deployed prototype, GitHub Pages URL, demo or published webpage.</small></label><label>Related project<select name="projectId" class="retro-select"><option value="">None yet</option>${state.projects.map(p=>`<option value="${p.id}" ${obj.projectId===p.id?'selected':''}>${esc(p.title)}</option>`).join('')}</select></label><label>Tags<input name="tags" class="retro-input" value="${esc(tags(obj.tags).join(', '))}" placeholder="ai, web, research"></label><label class="full">Next action<input name="nextAction" class="retro-input" value="${esc(obj.nextAction||'')}" placeholder="The smallest useful next step"></label>`)
      +section('WORKING CONTENT','Store prompts, references, constraints and rough thinking without forcing structure.',`<label class="full">Idea / prompt / webpage notes<textarea name="content" rows="12" class="retro-textarea form-long-text" placeholder="Write the idea, prompt versions, references, constraints, examples...">${esc(obj.content||'')}</textarea></label>`);
    const extra=isEdit?`<button type="button" class="neo-btn cyan idea-to-project" data-id="${obj.id}">→ CONVERT TO PROJECT</button><button type="button" class="neo-btn danger entity-delete" data-type="idea" data-id="${obj.id}">DELETE</button>`:'';
    return shell(head('idea',isEdit?'EDIT IDEA':'NEW IDEA','Capture enough context so an idea can become a task or project without losing the original thought.'),sections,actions('idea','pink',extra));
  }
  if(type==='project'){
    const sections=section('PROJECT IDENTITY','Define the outcome before connecting files and tools.',`<label>Project name <span class="form-required">*</span><input name="title" class="retro-input" required value="${esc(obj.title||'')}" placeholder="Project name"><small class="field-help">Keep it short enough to scan in the sidebar and planner.</small></label><label>Status<select name="status" class="retro-select">${['active','paused','done'].map(x=>`<option ${obj.status===x?'selected':''}>${x}</option>`).join('')}</select></label><label class="full">Short description<input name="description" class="retro-input" value="${esc(obj.description||'')}" placeholder="What this project delivers"></label><label>Tags<input name="tags" class="retro-input" value="${esc(tags(obj.tags).join(', '))}" placeholder="web, client, research"></label><label>Progress %<input name="progress" type="number" min="0" max="100" class="retro-input" value="${esc(obj.progress??0)}"></label><label>Target / due date<input name="dueDate" type="date" class="retro-input" value="${esc(obj.dueDate||'')}"></label><label>Project type<select name="isWeb" class="retro-select"><option value="true" ${obj.isWeb?'selected':''}>Web app</option><option value="false" ${!obj.isWeb?'selected':''}>Other project</option></select></label><div class="full">${pin(!!obj.pinned)}</div>`)
      +section('TECH & LOCATION','Connect local development, source control and the public website.',`<label class="full">Local folder path on Django server<input name="pathHint" class="retro-input" value="${esc(obj.pathHint||'')}" placeholder="/home/me/projects/app or C:\\Projects\\app"><small class="field-help">PixelVault reads this path from the Django server, not from the browser.</small></label><label>Local / dev launch URL<input name="launchUrl" type="url" class="retro-input" value="${esc(obj.launchUrl||'')}" placeholder="http://localhost:3000"><small class="field-help">Optional development server or another launch URL.</small></label><label>GitHub Pages URL<input name="githubPagesUrl" type="url" class="retro-input" value="${esc(obj.githubPagesUrl||'')}" placeholder="https://username.github.io/project/"><small class="field-help">Public live site for projects deployed with GitHub Pages.</small></label><label>Repository URL<input name="repositoryUrl" type="url" class="retro-input" value="${esc(obj.repositoryUrl||'')}" placeholder="https://github.com/username/project"></label><label class="full">Tech stack<input name="techStack" class="retro-input" value="${esc(tags(obj.techStack).join(', '))}" placeholder="Django, HTML, CSS, JavaScript"></label>`)
      +section('DIRECTION','Keep the next milestone visible so the project always has a next move.',`<label class="full">Project goal<textarea name="goal" rows="3" class="retro-textarea" placeholder="Primary outcome or definition of success">${esc(obj.goal||'')}</textarea></label><label class="full">Next milestone<input name="milestone" class="retro-input" value="${esc(obj.milestone||'')}" placeholder="MVP ready, client review, launch..."></label><label class="full">Project notes<textarea name="notes" class="retro-textarea form-long-text" rows="7" placeholder="Constraints, decisions, links, reminders...">${esc(obj.notes||'')}</textarea></label>`);
    const extra=isEdit?`<button type="button" class="neo-btn danger entity-delete" data-type="project" data-id="${obj.id}">DELETE</button>`:'';
    return shell(head('project',isEdit?'EDIT PROJECT':'NEW PROJECT','Define the project, connect a server-accessible folder path, and keep launch, milestone and delivery context together.'),sections,actions('project','cyan',extra));
  }
  if(type==='task'){
    const sections=section('TASK BASICS','Write the next concrete action and connect it to the right project.',`<label>Task title <span class="form-required">*</span><input name="title" class="retro-input" required value="${esc(obj.title||'')}" placeholder="Action-oriented task title"><small class="field-help">Start with a verb when possible: Build, Review, Fix, Send…</small></label><label>Status<select name="status" class="retro-select">${['todo','doing','done'].map(x=>`<option ${obj.status===x?'selected':''}>${x}</option>`).join('')}</select></label><label class="full">Description<textarea name="description" rows="3" class="retro-textarea" placeholder="Context, expected result, acceptance criteria...">${esc(obj.description||'')}</textarea></label><label>Project<select name="projectId" class="retro-select"><option value="">Independent</option>${state.projects.map(p=>`<option value="${p.id}" ${obj.projectId===p.id?'selected':''}>${esc(p.title)}</option>`).join('')}</select></label><label>Priority<select name="priority" class="retro-select">${['high','medium','low'].map(x=>`<option ${(obj.priority||'medium')===x?'selected':''}>${x}</option>`).join('')}</select></label><label>Task type<select name="taskType" class="retro-select">${['development','design','research','deep-work','admin','meeting','learning','personal'].map(x=>`<option ${obj.taskType===x?'selected':''}>${x}</option>`).join('')}</select></label><label>Energy<select name="energy" class="retro-select">${['low','medium','high'].map(x=>`<option ${(obj.energy||'medium')===x?'selected':''}>${x}</option>`).join('')}</select></label><div class="full">${pin(!!obj.pinned)}</div>`)
      +section('SCHEDULE','Give the planner enough information to place the task realistically.',`<label>Scheduled date<input name="scheduledDate" type="date" class="retro-input" value="${esc(obj.scheduledDate||'')}"></label><label>Due date<input name="dueDate" type="date" class="retro-input" value="${esc(obj.dueDate||'')}"></label><label>Start time<input name="time" type="time" class="retro-input" value="${esc(obj.time||'')}"></label><label>Estimated minutes<input name="duration" type="number" min="0" step="5" class="retro-input" value="${esc(obj.duration??state.settings.defaultTaskDuration??45)}"></label><label>Repeat<select name="recurrence" class="retro-select">${['none','daily','weekly','monthly'].map(x=>`<option ${String(obj.recurrence||'none')===x?'selected':''}>${x}</option>`).join('')}</select></label><label>Blocked by<select name="dependsOn" class="retro-select"><option value="">Nothing</option>${state.tasks.filter(t=>t.id!==obj.id).map(t=>`<option value="${t.id}" ${obj.dependsOn===t.id?'selected':''}>${esc(t.title)}</option>`).join('')}</select></label>`)
      +section('EXECUTION DETAILS','Store the practical information you need when it is time to do the work.',`<label class="full">Tags<input name="tags" class="retro-input" value="${esc(tags(obj.tags).join(', '))}" placeholder="focus, client, ui"></label><label class="full">Subtasks — one per line<textarea name="subtasks" rows="5" class="retro-textarea">${esc((obj.subtasks||[]).join('\n'))}</textarea></label><label class="full">Task notes<textarea name="notes" rows="5" class="retro-textarea form-long-text" placeholder="Links, decisions, handoff notes, result...">${esc(obj.notes||'')}</textarea></label>`);
    const extra=isEdit?`<button type="button" class="neo-btn danger entity-delete" data-type="task" data-id="${obj.id}">DELETE</button>`:'';
    return shell(head('task',isEdit?'EDIT TASK':'NEW TASK','Plan the task with enough detail to schedule it realistically and report on it later.'),sections,actions('task','lime',extra));
  }
  if(type==='skill'){
    const sections=section('SKILL IDENTITY','Make the skill easy to discover and understand before an agent opens the file.',`<label>Skill name <span class="form-required">*</span><input name="name" class="retro-input" required value="${esc(obj.name||'')}" placeholder="Frontend UX Reviewer"></label><label>Category<input name="category" class="retro-input" value="${esc(obj.category||'')}" placeholder="Development"></label><label class="full">Short description <span class="form-required">*</span><input name="description" class="retro-input" required value="${esc(obj.description||'')}" placeholder="What this skill helps an agent do"></label><label>Version<input name="version" class="retro-input" value="${esc(obj.version||'1.0.0')}" placeholder="1.0.0"></label><label>Source / reference<input name="sourceUrl" class="retro-input" value="${esc(obj.sourceUrl||'')}" placeholder="https://... or source note"></label><label>Tags<input name="tags" class="retro-input" value="${esc(tags(obj.tags).join(', '))}" placeholder="web, testing, ux"></label><label>Agents<input name="agents" class="retro-input" value="${esc(tags(obj.agents).join(', '))}" placeholder="Codex, Claude"></label><label class="full">Best used for<textarea name="useCases" rows="3" class="retro-textarea" placeholder="One use case per line">${esc((obj.useCases||[]).join('\n'))}</textarea></label><label class="full">Filename<input name="filename" class="retro-input" value="${esc(obj.filename||'')}" placeholder="my-skill.skill.md"><span class="field-help">You can attach an existing .md after creating the skill.</span></label><div class="full">${pin(!!obj.pinned)}</div>`)
      +section('MARKDOWN SOURCE','This is the reusable instruction file your agents will actually use.',`<label class="full">Initial Markdown<textarea name="content" rows="14" class="retro-textarea form-long-text">${esc(obj.content||'# Skill Name\n\n## Purpose\n\n## When to use\n- \n\n## Workflow\n1. \n\n## Rules\n- \n\n## Output\n- ')}</textarea></label>`);
    return shell(head('skill',isEdit?'EDIT SKILL':'NEW SKILL','Create reusable agent knowledge with metadata, usage guidance and a real editable Markdown source file.'),sections,actions('skill','violet'));
  }
  return '';
}
function openEntity(type,id='',prefill={}){
  const d=$('#entity-dialog'),body=$('#entity-dialog-body');$('#detail-dialog')?.close();if(d.open)d.close();let obj={...prefill};if(id)obj=state[`${type}s`]?.find(x=>x.id===id)||{};body.innerHTML=renderEntityForm(type,obj);entityFormDirty=false;d.showModal();setTimeout(()=>body.querySelector('[required],input,textarea,select')?.focus(),30);
}


function nextRecurringDate(date,recurrence){if(!date||!recurrence||recurrence==='none')return date||'';const d=new Date(`${date}T12:00:00`);if(recurrence==='daily')d.setDate(d.getDate()+1);if(recurrence==='weekly')d.setDate(d.getDate()+7);if(recurrence==='monthly')d.setMonth(d.getMonth()+1);return iso(d)}
function spawnRecurringTask(t){if(!t.recurrence||t.recurrence==='none'||t.recurrenceSpawned)return;t.recurrenceSpawned=true;const base=t.scheduledDate||t.dueDate||today(),next={...t,id:uid('task'),status:'todo',pinned:false,completedAt:'',created:today(),updated:today(),recurrenceSpawned:false,recurrenceParentId:t.id,scheduledDate:t.scheduledDate?nextRecurringDate(t.scheduledDate,t.recurrence):'',dueDate:t.dueDate?nextRecurringDate(t.dueDate,t.recurrence):''};state.tasks.push(next);toast(`NEXT ${t.recurrence.toUpperCase()} TASK CREATED`)}
async function saveEntity(type,id,form){
  const before=JSON.parse(JSON.stringify(state)),fd=new FormData(form),now=today(),isNew=!id;let savedItem=null;
  try{
    if(type==='idea'){
      const x=id?state.ideas.find(x=>x.id===id):{id:uid('idea'),pinned:false,created:now};if(!x)throw new Error('Idea no longer exists.');
      Object.assign(x,{title:String(fd.get('title')||'').trim(),description:String(fd.get('description')||'').trim(),priority:fd.get('priority')||'medium',contentType:fd.get('contentType')||'note',content:fd.get('content')||'',status:fd.get('status')||'inbox',tags:tags(fd.get('tags')),projectId:fd.get('projectId')||'',goal:fd.get('goal')||'',audience:fd.get('audience')||'',sourceUrl:fd.get('sourceUrl')||'',liveSiteUrl:fd.get('liveSiteUrl')||'',nextAction:fd.get('nextAction')||'',pinned:fd.get('pinned')==='on',updated:now});if(!id)state.ideas.push(x);savedItem=x;
    }
    if(type==='project'){
      const x=id?state.projects.find(x=>x.id===id):{id:uid('project'),pinned:false,created:now};if(!x)throw new Error('Project no longer exists.');
      Object.assign(x,{title:String(fd.get('title')||'').trim(),description:String(fd.get('description')||'').trim(),status:fd.get('status')||'active',tags:tags(fd.get('tags')),progress:clamp(+fd.get('progress')||0,0,100),pathHint:String(fd.get('pathHint')||'').trim(),launchUrl:String(fd.get('launchUrl')||'').trim(),repositoryUrl:String(fd.get('repositoryUrl')||'').trim(),githubPagesUrl:String(fd.get('githubPagesUrl')||'').trim(),techStack:tags(fd.get('techStack')),goal:fd.get('goal')||'',milestone:fd.get('milestone')||'',dueDate:fd.get('dueDate')||'',isWeb:fd.get('isWeb')==='true',notes:fd.get('notes')||'',pinned:fd.get('pinned')==='on',updated:now});if(!id)state.projects.push(x);savedItem=x;
    }
    if(type==='task'){
      const x=id?state.tasks.find(x=>x.id===id):{id:uid('task'),pinned:false,created:now,completedAt:'',recurrenceSpawned:false};if(!x)throw new Error('Task no longer exists.');const old=x.status;
      Object.assign(x,{title:String(fd.get('title')||'').trim(),description:String(fd.get('description')||'').trim(),projectId:fd.get('projectId')||'',status:fd.get('status')||'todo',priority:fd.get('priority')||'medium',taskType:fd.get('taskType')||'development',energy:fd.get('energy')||'medium',scheduledDate:fd.get('scheduledDate')||'',dueDate:fd.get('dueDate')||'',time:fd.get('time')||'',duration:+fd.get('duration')||0,recurrence:fd.get('recurrence')||'none',dependsOn:fd.get('dependsOn')||'',tags:tags(fd.get('tags')),subtasks:String(fd.get('subtasks')||'').split('\n').map(s=>s.trim()).filter(Boolean),notes:fd.get('notes')||'',pinned:fd.get('pinned')==='on',updated:now});if(x.status==='done'&&old!=='done'){x.completedAt=now;spawnRecurringTask(x)}if(x.status!=='done')x.completedAt='';if(!id)state.tasks.push(x);savedItem=x;
    }
    if(type==='skill'){
      const name=String(fd.get('name')||'').trim(),x=id?state.skills.find(x=>x.id===id):{id:uid('skill'),pinned:false,created:now};if(!x)throw new Error('Skill no longer exists.');
      Object.assign(x,{name,description:String(fd.get('description')||'').trim(),category:String(fd.get('category')||'').trim()||'General',version:String(fd.get('version')||'1.0.0').trim(),sourceUrl:String(fd.get('sourceUrl')||'').trim(),useCases:String(fd.get('useCases')||'').split('\n').map(x=>x.trim()).filter(Boolean),tags:tags(fd.get('tags')),agents:tags(fd.get('agents')),filename:String(fd.get('filename')||'').trim()||`${slug(name)}.skill.md`,content:fd.get('content')||'',pinned:fd.get('pinned')==='on',updated:now});if(!id)state.skills.push(x);state.settings.skillSelected=x.id;savedItem=x;
    }
    if(!savedItem)throw new Error('Unsupported workspace item.');
    renderCounts();const ok=await flushSave();if(!ok)throw new Error('Django did not confirm the save.');
    renderAll();entityFormDirty=false;
    return {item:savedItem,isNew};
  }catch(e){
    state=mergeState(before);renderAll();console.error('[PixelVault] entity save reverted',e);
    toast('CHANGES NOT SAVED','error',e.message||'Django could not confirm this save.');
    return null;
  }
}

function detailValue(label,value,wide=false){return `<div class="detail-kv ${wide?'wide':''}"><span>${esc(label)}</span><b>${value||'<em>Not set</em>'}</b></div>`}
function openEntityDetail(type,id,notice=''){
  const d=$('#detail-dialog'),body=$('#detail-dialog-body');if(!d||!body)return;const item=state[`${type}s`]?.find(x=>x.id===id);if(!item)return;if(d.open)d.close();
  const close=`<button type="button" class="icon-btn detail-close" aria-label="Close details">×</button>`;
  const noticeHtml=notice?`<div class="save-confirmation-strip"><span>✓</span><div><b>${esc(notice)}</b><small>Confirmed by Django and stored in your workspace.</small></div></div>`:'';
  if(type==='idea'){
    const project=getProject(item.projectId);body.innerHTML=`<article class="entity-detail">${noticeHtml}<header class="entity-detail-head"><div><div class="card-kicker"><span class="status ${esc(item.status||'inbox')}">${esc(item.status||'inbox')}</span><span class="chip ${item.priority==='high'?'pink':item.priority==='low'?'lime':'yellow'}">${esc((item.priority||'medium').toUpperCase())}</span>${item.pinned?'<span class="chip yellow">★ PINNED</span>':''}</div><span class="eyebrow">💡 IDEA</span><h1>${esc(item.title)}</h1><p>${esc(item.description||'No short description yet.')}</p></div><div class="entity-detail-head-actions">${close}</div></header><div class="entity-detail-grid">${detailValue('CONTENT TYPE',esc(item.contentType||'note'))}${detailValue('RELATED PROJECT',project?esc(project.title):'<em>Unlinked</em>')}${detailValue('AUDIENCE',esc(item.audience||''))}${item.liveSiteUrl?detailValue('LIVE SITE',`<a class="detail-live-link open-live-site" href="${esc(item.liveSiteUrl)}" data-url="${esc(item.liveSiteUrl)}">${esc(item.liveSiteUrl)}</a>`,true):''}${detailValue('UPDATED',esc(item.updated||'—'))}</div>${item.goal?`<section class="detail-section"><span class="detail-section-label">GOAL / PROBLEM</span><p>${esc(item.goal)}</p></section>`:''}${item.nextAction?`<section class="detail-callout"><span>NEXT ACTION</span><b>${esc(item.nextAction)}</b></section>`:''}<section class="detail-section"><div class="detail-section-head"><span class="detail-section-label">WORKING CONTENT</span><span>${item.content?item.content.length:0} chars</span></div><div class="detail-prose">${esc(item.content||'No working content yet.').replace(/\n/g,'<br>')}</div></section>${tags(item.tags).length?`<div class="chip-row detail-tags">${tags(item.tags).map(t=>`<span class="chip">#${esc(t)}</span>`).join('')}</div>`:''}<footer class="entity-detail-actions">${item.liveSiteUrl?`<button type="button" class="neo-btn cyan open-live-site" data-url="${esc(item.liveSiteUrl)}">🌐 OPEN LIVE SITE</button>`:''}<button type="button" class="neo-btn cyan idea-to-project" data-id="${item.id}">→ CONVERT TO PROJECT</button><button type="button" class="neo-btn" data-pin="idea" data-id="${item.id}">${item.pinned?'★ UNPIN':'☆ PIN'}</button><button type="button" class="neo-btn pink" data-detail-edit="idea" data-id="${item.id}">✎ EDIT IDEA</button></footer></article>`;
  }else if(type==='task'){
    const project=getProject(item.projectId),dependency=state.tasks.find(t=>t.id===item.dependsOn);body.innerHTML=`<article class="entity-detail">${noticeHtml}<header class="entity-detail-head"><div><div class="card-kicker"><span class="status ${esc(item.status||'todo')}">${esc(item.status||'todo')}</span><span class="chip ${item.priority==='high'?'pink':item.priority==='low'?'lime':'yellow'}">${esc((item.priority||'medium').toUpperCase())}</span>${item.pinned?'<span class="chip yellow">★ PINNED</span>':''}</div><span class="eyebrow">✓ TASK</span><h1>${esc(item.title)}</h1><p>${esc(item.description||'No task description yet.')}</p></div><div class="entity-detail-head-actions">${close}</div></header><div class="entity-detail-grid">${detailValue('PROJECT',project?esc(project.title):'Independent')}${detailValue('SCHEDULED',item.scheduledDate?esc(fmtDate(item.scheduledDate)):'<em>Unscheduled</em>')}${detailValue('DUE',item.dueDate?esc(fmtDate(item.dueDate)):'<em>No deadline</em>')}${detailValue('START',esc(item.time||'Anytime'))}${detailValue('ESTIMATE',`${+item.duration||0} min`)}${detailValue('ENERGY',esc(item.energy||'medium'))}${detailValue('TYPE',esc(item.taskType||'development'))}${detailValue('BLOCKED BY',dependency?esc(dependency.title):'<em>Nothing</em>')}</div>${item.subtasks?.length?`<section class="detail-section"><span class="detail-section-label">SUBTASKS</span><div class="detail-checklist">${item.subtasks.map(x=>`<div><span>□</span><b>${esc(x)}</b></div>`).join('')}</div></section>`:''}${item.notes?`<section class="detail-section"><span class="detail-section-label">NOTES</span><div class="detail-prose">${esc(item.notes).replace(/\n/g,'<br>')}</div></section>`:''}${tags(item.tags).length?`<div class="chip-row detail-tags">${tags(item.tags).map(t=>`<span class="chip">#${esc(t)}</span>`).join('')}</div>`:''}<footer class="entity-detail-actions"><button type="button" class="neo-btn ${item.status==='done'?'':'lime'}" data-task-toggle="${item.id}">${item.status==='done'?'↺ REOPEN TASK':'✓ MARK COMPLETE'}</button><button type="button" class="neo-btn" data-duplicate-task="${item.id}">⧉ DUPLICATE</button><button type="button" class="neo-btn" data-pin="task" data-id="${item.id}">${item.pinned?'★ UNPIN':'☆ PIN'}</button><button type="button" class="neo-btn pink" data-detail-edit="task" data-id="${item.id}">✎ EDIT TASK</button></footer></article>`;
  }else return;
  d.showModal();
}
function showSaveBanner(message){
  $('.save-page-banner')?.remove();const page=$('.page.active');if(!page)return;const el=document.createElement('div');el.className='save-page-banner';el.innerHTML=`<span>✓</span><div><b>${esc(message)}</b><small>Saved successfully to your Django workspace.</small></div><button type="button" aria-label="Dismiss">×</button>`;el.querySelector('button').onclick=()=>el.remove();page.prepend(el);setTimeout(()=>el.remove(),5200);
}
function revealSavedEntity(type,item,isNew){
  const action=isNew?'CREATED':'UPDATED',pageMap={idea:'ideas',project:'projects',task:'tasks',skill:'skills'};pageTo(pageMap[type]||'home');
  toast(`${type.toUpperCase()} ${action}`,'success',`${item.title||item.name} was saved successfully.`);showSaveBanner(`${item.title||item.name} · ${action}`);
  const note=`${type.toUpperCase()} ${action} · SAVED`;
  setTimeout(()=>{if(type==='project')openProjectDetail(item.id,note);else if(type==='skill'){state.settings.skillSelected=item.id;renderSkills();$('#skill-editor')?.scrollIntoView({behavior:state.settings.reduceMotion?'auto':'smooth',block:'start'})}else openEntityDetail(type,item.id,note)},80);
}
function deleteEntity(type,id){if(state.settings.confirmDeletes!==false&&!confirm(`Delete this ${type}?`))return;const key=`${type}s`;state[key]=state[key].filter(x=>x.id!==id);if(type==='project'){state.tasks.forEach(t=>{if(t.projectId===id)t.projectId=''});state.ideas.forEach(i=>{if(i.projectId===id)i.projectId=''})}if(type==='skill'&&state.settings.skillSelected===id)state.settings.skillSelected=null;save();renderAll();toast(`${type.toUpperCase()} DELETED`)}

async function connectProject(id){
  const p=getProject(id);if(!p)return;
  if(!p.pathHint){toast('Add the local folder path first.');openEntity('project',id);return}
  openProjectDetail(id)
}
async function fetchProjectTree(id,path=''){
  const url=`/api/projects/${encodeURIComponent(id)}/tree/?path=${encodeURIComponent(path)}`;
  const r=await apiFetch(url);const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||`Folder scan failed (${r.status})`);return d
}
async function fetchProjectFile(id,path=''){
  const url=`/api/projects/${encodeURIComponent(id)}/file/?path=${encodeURIComponent(path)}`;
  const r=await apiFetch(url);const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||`File preview failed (${r.status})`);return d
}
function formatBytes(n){if(n==null)return'';if(n<1024)return`${n} B`;if(n<1024*1024)return`${Math.max(1,Math.round(n/1024))} KB`;return`${(n/1024/1024).toFixed(1)} MB`}
async function openProjectDetail(id,notice=''){
  const p=getProject(id);if(!p)return;const d=$('#project-dialog'),b=$('#project-dialog-body');if(d.open)d.close();
  const tasks=state.tasks.filter(t=>t.projectId===p.id),openTasks=tasks.filter(t=>t.status!=='done'),doneTasks=tasks.filter(t=>t.status==='done'),due=tasks.filter(isOverdue).length;
  const savedNotice=notice?`<div class="save-confirmation-strip"><span>✓</span><div><b>${esc(notice)}</b><small>Confirmed by Django and stored in your workspace.</small></div></div>`:'';
  b.innerHTML=`${savedNotice}<div class="project-workspace-head"><div class="project-workspace-title"><div class="card-kicker"><span class="status ${p.status}">${esc(p.status||'active')}</span>${p.isWeb?'<span class="chip lime">WEB APP</span>':''}${p.githubPagesUrl?'<span class="chip cyan">● LIVE</span>':''}${p.dueDate?`<span class="chip yellow">TARGET ${esc(fmtDate(p.dueDate,{month:'short',day:'numeric',year:'numeric'}))}</span>`:''}</div><h1>${esc(p.title)}</h1><p>${esc(p.description||'No project description yet.')}</p><div class="chip-row">${tags(p.techStack).slice(0,7).map(x=>`<span class="chip">${esc(x)}</span>`).join('')}</div></div><div class="project-workspace-actions"><button class="pin-btn ${p.pinned?'on':''}" data-pin="project" data-id="${p.id}" title="Pin project">★</button><button class="icon-btn" type="button" onclick="this.closest('dialog').close()" title="Close">×</button></div></div>
  <div class="project-workspace-stats"><div><span>PROGRESS</span><b>${+p.progress||0}%</b></div><div><span>OPEN TASKS</span><b>${openTasks.length}</b></div><div><span>COMPLETED</span><b>${doneTasks.length}</b></div><div class="${due?'warn':''}"><span>OVERDUE</span><b>${due}</b></div></div>
  <div class="progress project-workspace-progress"><i style="width:${clamp(+p.progress||0,0,100)}%"></i></div>
  <div class="project-workspace-toolbar"><button class="neo-btn small connect-project" data-id="${p.id}">↻ REFRESH FILES</button>${p.githubPagesUrl?`<button class="neo-btn cyan small open-github-pages" data-url="${esc(p.githubPagesUrl)}">🌐 GITHUB PAGES</button>`:''}${p.isWeb&&(p.launchUrl||p.pathHint)?`<button class="neo-btn small launch-project" data-id="${p.id}">▶ DEV / PREVIEW</button>`:''}${p.repositoryUrl?`<button class="neo-btn violet small open-repository" data-url="${esc(p.repositoryUrl)}">↗ REPOSITORY</button>`:''}<button class="neo-btn small edit-project" data-id="${p.id}">✎ EDIT PROJECT</button></div>
  <div class="project-workspace-grid">
    <section class="project-workspace-main">
      <div class="project-info-strip"><div><span>SERVER FOLDER</span><code>${esc(p.pathHint||'No local path configured')}</code></div>${p.githubPagesUrl?`<div><span>LIVE SITE</span><a class="project-live-link open-github-pages" href="${esc(p.githubPagesUrl)}" data-url="${esc(p.githubPagesUrl)}">${esc(p.githubPagesUrl)}</a></div>`:''}${p.milestone?`<div><span>NEXT MILESTONE</span><b>${esc(p.milestone)}</b></div>`:''}</div>
      <div class="project-files-shell"><div class="panel-head"><div><h2>FILES & FOLDERS</h2><small class="muted">Folders load on demand from the Django server</small></div><span class="chip cyan">READ ONLY PREVIEW</span></div><div class="project-file-split"><div id="project-file-tree" class="file-tree"><span class="muted">Scanning project folder…</span></div><pre id="project-file-preview" class="project-file-preview"><span class="muted">Select a text/code file to preview it here.</span></pre></div></div>
    </section>
    <aside class="project-workspace-side"><section><div class="panel-head"><h2>NEXT ACTIONS</h2><button class="text-btn" data-project-task-create="${p.id}">＋ TASK</button></div>${openTasks.slice(0,6).map(t=>`<button class="project-task-row edit-task" data-id="${t.id}"><span class="priority-dot ${t.priority}"></span><div><b>${esc(t.title)}</b><small>${t.dueDate?'due '+esc(fmtDate(t.dueDate,{month:'short',day:'numeric'})):'no due date'}</small></div><span>›</span></button>`).join('')||'<div class="empty-state compact"><span>✓</span><b>NO OPEN TASKS</b><p>This project has a clean queue.</p></div>'}</section><section><div class="panel-head"><h2>PROJECT NOTES</h2></div><div class="project-notes">${esc(p.notes||'No project notes yet.').replace(/\n/g,'<br>')}</div></section></aside>
  </div>`;
  d.showModal();const tree=$('#project-file-tree');
  if(!p.pathHint){tree.innerHTML='<div class="empty-state compact"><span>📁</span><b>NO SERVER FOLDER</b><p>Edit project metadata and enter an absolute folder path visible to this Django server.</p></div>';return}
  try{tree.innerHTML='';const data=await fetchProjectTree(id,'');const root=document.createElement('div');root.className='folder project-root-folder';root.textContent=`📁 ${data.rootName}`;tree.append(root);const branch=document.createElement('div');tree.append(branch);await mountServerDirectory(id,'',branch,0,data)}catch(e){tree.innerHTML=`<div class="empty-state compact"><span>!</span><b>COULD NOT READ FOLDER</b><p>${esc(e.message)}</p></div>`}
}
async function mountServerDirectory(id,path,container,depth,data=null){
  try{
    data=data||await fetchProjectTree(id,path);container.innerHTML='';
    for(const entry of data.entries||[]){
      if(entry.kind==='directory'){
        const details=document.createElement('details');details.style.marginLeft=`${Math.min(depth,8)*14}px`;const summary=document.createElement('summary');summary.className='folder';summary.textContent=`📁 ${entry.name}`;details.append(summary);const child=document.createElement('div');details.append(child);let loaded=false;details.addEventListener('toggle',async()=>{if(details.open&&!loaded){loaded=true;child.innerHTML='<span class="muted">loading…</span>';await mountServerDirectory(id,entry.path,child,depth+1)}});container.append(details)
      }else{
        const row=document.createElement('div');row.className='file';row.style.marginLeft=`${Math.min(depth,8)*14}px`;const btn=document.createElement('button');btn.className='file-preview-btn';btn.type='button';btn.textContent=`📄 ${entry.name}`;btn.addEventListener('click',()=>previewProjectFile(id,entry.path));row.append(btn);const meta=document.createElement('small');meta.className='muted';meta.textContent=formatBytes(entry.size);row.append(meta);container.append(row)
      }
    }
    if(data.truncated){const note=document.createElement('div');note.className='muted';note.textContent='Directory truncated after 500 entries.';container.append(note)}
  }catch(e){container.innerHTML=`<span class="muted">${esc(e.message)}</span>`}
}
async function previewProjectFile(id,path){const pre=$('#project-file-preview');if(!pre)return;pre.hidden=false;pre.textContent='Loading preview…';try{const d=await fetchProjectFile(id,path);pre.textContent=`// ${d.path}\n\n${d.content}`}catch(e){pre.textContent=e.message}}
async function launchProject(id){const p=getProject(id);if(!p)return;if(p.launchUrl){window.open(p.launchUrl,'_blank','noopener');return}if(p.githubPagesUrl){window.open(p.githubPagesUrl,'_blank','noopener');return}if(p.isWeb&&p.pathHint){window.open(`/preview/${encodeURIComponent(id)}/`,'_blank','noopener');toast('OPENED DJANGO STATIC PREVIEW');return}toast('Add a dev Launch URL, GitHub Pages URL, or a local project folder containing index.html.');openEntity('project',id)}

async function attachSkill(id){
  const s=state.skills.find(x=>x.id===id);if(!s)return;const input=document.createElement('input');input.type='file';input.accept='.md,.markdown,.txt,text/markdown,text/plain';
  input.onchange=async()=>{const f=input.files?.[0];if(!f)return;const fd=new FormData();fd.append('file',f);try{setSyncState('busy','UPLOADING…');const r=await apiFetch(`/api/skills/${encodeURIComponent(id)}/upload/`,{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw new Error(d.error||'Upload failed');s.content=d.content||'';s.filename=d.filename||f.name;s.attachedFile=d.url||'';s.updated=today();renderSkills();setSyncState('ok','SAVED');toast('MARKDOWN ATTACHED')}catch(e){setSyncState('error','UPLOAD ERROR');toast(e.message)}};input.click()
}
async function saveSkillToFile(id){const s=state.skills.find(x=>x.id===id);if(!s)return;try{const r=await apiFetch(`/api/skills/${encodeURIComponent(id)}/write/`,{method:'POST',body:JSON.stringify({content:s.content||'',filename:s.filename||`${slug(s.name)}.skill.md`})});const d=await r.json();if(!r.ok)throw new Error(d.error||'Could not write skill');s.attachedFile=d.url||s.attachedFile||'';s.updated=today();toast(s.attachedFile?'ATTACHED MARKDOWN UPDATED':'SKILL CONTENT SAVED IN DJANGO')}catch(e){toast(e.message)}}
async function saveSkillEditor(id){const s=state.skills.find(x=>x.id===id);if(!s)return false;const before=JSON.parse(JSON.stringify(state));s.name=$('#skill-name-edit').value.trim();s.category=$('#skill-category-edit').value.trim()||'General';s.description=$('#skill-description-edit').value.trim();s.version=$('#skill-version-edit').value.trim()||'1.0.0';s.sourceUrl=$('#skill-source-edit').value.trim();s.tags=tags($('#skill-tags-edit').value);s.agents=tags($('#skill-agents-edit').value);s.useCases=$('#skill-use-cases-edit').value.split('\n').map(x=>x.trim()).filter(Boolean);s.content=$('#skill-content-edit').value;s.filename=s.filename||`${slug(s.name)}.skill.md`;s.updated=today();renderCounts();const ok=await flushSave();if(!ok){state=mergeState(before);renderAll();return false}renderSkills();toast('SKILL UPDATED','success',`${s.name} was saved successfully.`);showSaveBanner(`${s.name} · UPDATED`);return true}
function downloadSkill(id){window.location.href=`/api/skills/${encodeURIComponent(id)}/download/`}

function textOffset(root,node,offset){let total=0;const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n;while((n=w.nextNode())){if(n===node)return total+offset;total+=n.data.length}return total}
function captureSelection(){
  const sel=getSelection();if(!sel||sel.isCollapsed||!sel.rangeCount)return null;const r=sel.getRangeAt(0);const page=r.commonAncestorContainer.nodeType===1?r.commonAncestorContainer.closest?.('.page'):r.commonAncestorContainer.parentElement?.closest('.page');if(!page||!page.classList.contains('active'))return null;if(r.commonAncestorContainer.parentElement?.closest('input,textarea,select'))return null;const quote=sel.toString().trim();if(quote.length<2)return null;const start=textOffset(page,r.startContainer,r.startOffset),end=textOffset(page,r.endContainer,r.endOffset),txt=page.textContent||'';return{quote,page:page.dataset.page,prefix:txt.slice(Math.max(0,start-36),start),suffix:txt.slice(end,end+36),created:new Date().toISOString()}
}
function hideSelectionToolbar(clear=false){const tb=$('#selection-toolbar');if(tb)tb.hidden=true;if(clear){pendingSelection=null;const sel=getSelection();if(sel&&!sel.isCollapsed)sel.removeAllRanges()}}
function showSelectionToolbar(ev){const p=captureSelection();if(!p){hideSelectionToolbar(false);return}pendingSelection=p;updateHighlightToolbar();const tb=$('#selection-toolbar');tb.hidden=false;const width=Math.max(255,tb.offsetWidth||255),height=Math.max(42,tb.offsetHeight||42),x=ev?.clientX??innerWidth/2,y=ev?.clientY??innerHeight/2;tb.style.left=`${clamp(x,10,innerWidth-width-10)}px`;tb.style.top=`${clamp(y-height-12,10,innerHeight-height-10)}px`}
function addAnnotation(color,comment=''){if(!pendingSelection)return;state.annotations.push({...pendingSelection,id:uid('ann'),color:color||state.settings.defaultHighlight||'yellow',comment});save();hideSelectionToolbar(true);renderAnnotations();rehydrateAnnotations();toast(comment?'COMMENT SAVED':'HIGHLIGHT SAVED')}
function locateRange(root,a){
  const nodes=[],w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n,total='';while((n=w.nextNode())){nodes.push({node:n,start:total.length,end:total.length+n.data.length});total+=n.data}
  let candidates=[],i=total.indexOf(a.quote);while(i>=0){candidates.push(i);i=total.indexOf(a.quote,i+1)}if(!candidates.length)return null;let start=candidates.find(i=>{const pre=total.slice(Math.max(0,i-a.prefix.length),i),suf=total.slice(i+a.quote.length,i+a.quote.length+a.suffix.length);return(!a.prefix||pre.endsWith(a.prefix.slice(-Math.min(18,a.prefix.length))))&&(!a.suffix||suf.startsWith(a.suffix.slice(0,Math.min(18,a.suffix.length))))});if(start==null)start=candidates[0];const end=start+a.quote.length, sn=nodes.find(x=>start>=x.start&&start<=x.end),en=nodes.find(x=>end>=x.start&&end<=x.end);if(!sn||!en)return null;const r=document.createRange();r.setStart(sn.node,start-sn.start);r.setEnd(en.node,end-en.start);return r
}
function rehydrateAnnotations(){
  if(!window.CSS?.highlights)return;['yellow','pink','cyan','lime'].forEach(c=>CSS.highlights.delete(`pv-${c}`));if(state.settings.showHighlights===false)return;const groups={yellow:[],pink:[],cyan:[],lime:[]};state.annotations.forEach(a=>{const root=$(`#page-${a.page}`);if(root){const r=locateRange(root,a);if(r)groups[a.color]?.push(r)}});Object.entries(groups).forEach(([c,rs])=>{if(rs.length)CSS.highlights.set(`pv-${c}`,new Highlight(...rs))})
}

function downloadServerReport(kind){const base=kind==='png'?(CFG.reportPngUrl||'/reports/social.png'):(CFG.reportPdfUrl||'/reports/report.pdf');const q=new URLSearchParams({period:$('#report-period').value,date:$('#report-date').value||today(),privacy:$('#report-privacy').value,signature:$('#report-signature').value.trim()||state.settings.signature||state.settings.workspaceName||'PIXELVAULT'});window.location.href=`${base}?${q.toString()}`}
async function socialReport(){
  const s=reportSummary(), mode=$('#report-privacy').value, sig=$('#report-signature').value.trim()||'PIXELVAULT', canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1350;const c=canvas.getContext('2d');
  c.fillStyle='#0d0a1b';c.fillRect(0,0,1080,1350);c.fillStyle='#171438';c.fillRect(42,42,996,1266);c.strokeStyle='#9b6bff';c.lineWidth=6;c.strokeRect(42,42,996,1266);
  for(let y=70;y<1280;y+=24){c.strokeStyle='rgba(255,255,255,.025)';c.lineWidth=1;c.beginPath();c.moveTo(60,y);c.lineTo(1020,y);c.stroke()}
  c.fillStyle='#ff4aa2';c.font='bold 42px monospace';c.fillText('PIXELVAULT',82,115);c.fillStyle='#23d9ff';c.font='bold 22px monospace';c.fillText(`${s.period.toUpperCase()} REPORT`,82,152);c.fillStyle='#f8f5ff';c.font='bold 34px monospace';wrapCanvas(c,s.range.label,82,215,860,42);
  const stats=[['DONE',s.done.length],['FOCUS',`${s.hours}h`],['RATE',`${s.completion}%`],['OVERDUE',s.overdue]];stats.forEach(([l,v],i)=>{const x=82+(i%2)*460,y=310+Math.floor(i/2)*155;c.fillStyle='#100f25';c.fillRect(x,y,420,120);c.strokeStyle=i%2?'#8cff3f':'#ffd447';c.lineWidth=3;c.strokeRect(x,y,420,120);c.fillStyle='#aaa4c8';c.font='bold 18px monospace';c.fillText(l,x+22,y+32);c.fillStyle='#fff';c.font='bold 43px monospace';c.fillText(String(v),x+22,y+88)});
  c.fillStyle='#8cff3f';c.font='bold 22px monospace';c.fillText('TOP COMPLETIONS',82,650);let y=700;c.font='20px monospace';c.fillStyle='#f8f5ff';s.done.slice(0,7).forEach((t,i)=>{c.fillStyle=i%2?'#13102b':'#100f25';c.fillRect(82,y-28,880,58);c.fillStyle='#8cff3f';c.fillText('✓',100,y);c.fillStyle='#f8f5ff';c.fillText(truncate(publicTaskTitle(t,mode),55),138,y);y+=70});if(!s.done.length){c.fillStyle='#aaa4c8';c.fillText('No completed tasks in this period yet.',100,y)}
  c.fillStyle='#23d9ff';c.font='bold 22px monospace';c.fillText('MOST ACTIVE PROJECT',82,1160);c.fillStyle='#fff';c.font='bold 26px monospace';c.fillText(truncate(s.topProject,48),82,1205);c.fillStyle='#aaa4c8';c.font='18px monospace';c.fillText(`${sig}  ·  generated locally`,82,1260);
  try{const img=await loadImage(`${ASSET_BASE}mascot-raccoon.webp`);c.globalAlpha=.88;c.drawImage(img,760,25,260,260);c.globalAlpha=1}catch{}
  canvas.toBlob(b=>downloadBlob(b,`${slug(s.period+'-'+s.date)}-pixelvault.png`),'image/png')
}
function truncate(s,n){s=String(s);return s.length>n?s.slice(0,n-1)+'…':s}
function wrapCanvas(c,text,x,y,max,lh){const words=String(text).split(' ');let line='';for(const w of words){const t=line?line+' '+w:w;if(c.measureText(t).width>max&&line){c.fillText(line,x,y);line=w;y+=lh}else line=t}if(line)c.fillText(line,x,y);return y}
function loadImage(src){return new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=src})}

function pdfEsc(s){return String(s).replace(/\\/g,'\\\\').replace(/\(/g,'\\(').replace(/\)/g,'\\)').replace(/[^\x20-\x7E]/g,'?')}
function makePdf(){
  const s=reportSummary(), mode=$('#report-privacy').value, sig=$('#report-signature').value.trim()||'PIXELVAULT';
  const pages=[];let page=makePdfPage(`PIXELVAULT ${s.period.toUpperCase()} REPORT`,s.range.label,sig);pages.push(page);
  page.section('EXECUTIVE SUMMARY');page.stat('Completed tasks',String(s.done.length));page.stat('Estimated focus time',`${s.hours} hours`);page.stat('Completion rate',`${s.completion}%`);page.stat('Overdue in period',String(s.overdue));page.text(`Most active project: ${s.topProject}`);page.text('This report was generated locally from the task and planner data stored in PixelVault.');
  page=makePdfPage('COMPLETED WORK',s.range.label,sig);pages.push(page); if(!s.done.length)page.text('No completed tasks were recorded in this period.');s.done.forEach((t,i)=>{if(!page.canFit(72)){page=makePdfPage('COMPLETED WORK — CONTINUED',s.range.label,sig);pages.push(page)}page.item(`${i+1}. ${publicTaskTitle(t,mode)}`,`${taskProjectName(t)} | ${t.priority} priority | ${t.duration||0} min | ${t.completedAt||t.updated}`)});
  page=makePdfPage('PROJECT BREAKDOWN',s.range.label,sig);pages.push(page);const entries=Object.entries(s.projects).sort((a,b)=>b[1]-a[1]);if(!entries.length)page.text('No project completion data for this period.');entries.forEach(([name,count])=>page.bar(name,count,Math.max(...entries.map(x=>x[1]),1)));
  page=makePdfPage('PLANNER & OPEN LOOP REVIEW',s.range.label,sig);pages.push(page);const scheduled=state.tasks.filter(t=>t.scheduledDate>=s.range.start&&t.scheduledDate<=s.range.end).sort((a,b)=>a.scheduledDate.localeCompare(b.scheduledDate)||parseTime(a.time)-parseTime(b.time));scheduled.forEach(t=>{if(!page.canFit(58)){page=makePdfPage('PLANNER REVIEW — CONTINUED',s.range.label,sig);pages.push(page)}page.item(`${t.scheduledDate}${t.time?' '+t.time:''} — ${publicTaskTitle(t,mode)}`,`${taskProjectName(t)} | status: ${t.status} | due: ${t.dueDate||'—'}`)}); if(!scheduled.length)page.text('No scheduled tasks for this period.');
  page=makePdfPage('NEXT ACTIONS',s.range.label,sig);pages.push(page);const next=state.tasks.filter(t=>t.status!=='done').sort((a,b)=>(a.dueDate||'9999').localeCompare(b.dueDate||'9999')).slice(0,25);next.forEach((t,i)=>{if(!page.canFit(58)){page=makePdfPage('NEXT ACTIONS — CONTINUED',s.range.label,sig);pages.push(page)}page.item(`${i+1}. ${publicTaskTitle(t,mode)}`,`${taskProjectName(t)} | ${t.priority} | due ${t.dueDate||'unscheduled'}`)});
  const blob=buildPdf(pages);downloadBlob(blob,`${slug(s.period+'-'+s.date)}-pixelvault-report.pdf`)
}
function makePdfPage(title,subtitle,sig){
  const ops=[];let y=760; const add=t=>ops.push(t); add('0.05 0.04 0.11 rg 0 0 595 842 re f');add('0.10 0.08 0.22 rg 28 28 539 786 re f');add('0.61 0.42 1 rg 28 808 539 6 re f');add(`BT /F2 18 Tf 1 0.29 0.64 rg 48 774 Td (${pdfEsc(title)}) Tj ET`);add(`BT /F1 10 Tf 0.14 0.85 1 rg 48 752 Td (${pdfEsc(subtitle)}) Tj ET`); y=710;
  function text(t,size=10,color='0.86 0.84 0.94'){for(const line of wrapTextPdf(t,86)){add(`BT /F1 ${size} Tf ${color} rg 48 ${y} Td (${pdfEsc(line)}) Tj ET`);y-=size+6}y-=4}
  return {ops,get y(){return y},canFit:h=>y-h>65,text,section(t){y-=8;add(`0.14 0.85 1 rg 48 ${y-2} 5 18 re f`);add(`BT /F2 13 Tf 0.55 1 0.25 rg 62 ${y} Td (${pdfEsc(t)}) Tj ET`);y-=32},stat(l,v){add(`0.08 0.07 0.16 rg 48 ${y-30} 499 42 re f`);add(`BT /F1 9 Tf 0.65 0.63 0.78 rg 62 ${y-9} Td (${pdfEsc(l.toUpperCase())}) Tj ET`);add(`BT /F2 15 Tf 1 1 1 rg 420 ${y-10} Td (${pdfEsc(v)}) Tj ET`);y-=52},item(a,b){add(`0.10 0.09 0.20 rg 48 ${y-42} 499 52 re f`);add(`0.55 1 0.25 rg 48 ${y-42} 4 52 re f`);add(`BT /F2 10 Tf 1 1 1 rg 62 ${y-15} Td (${pdfEsc(truncate(a,80))}) Tj ET`);add(`BT /F1 8 Tf 0.67 0.64 0.79 rg 62 ${y-31} Td (${pdfEsc(truncate(b,96))}) Tj ET`);y-=62},bar(name,val,max){if(y<100)return;add(`BT /F1 9 Tf 1 1 1 rg 48 ${y} Td (${pdfEsc(truncate(name,55))}) Tj ET`);add(`0.08 0.07 0.16 rg 48 ${y-17} 430 10 re f`);add(`0.14 0.85 1 rg 48 ${y-17} ${Math.max(4,430*val/max)} 10 re f`);add(`BT /F2 9 Tf 0.55 1 0.25 rg 500 ${y-15} Td (${val}) Tj ET`);y-=40},finish(i,n){add(`BT /F1 8 Tf 0.45 0.42 0.58 rg 48 44 Td (${pdfEsc(sig)} | PIXELVAULT | PAGE ${i}/${n}) Tj ET`);return ops.join('\n')}}
}
function wrapTextPdf(text,max=84){const words=String(text).split(/\s+/),lines=[];let l='';for(const w of words){if((l+' '+w).trim().length>max&&l){lines.push(l);l=w}else l=(l+' '+w).trim()}if(l)lines.push(l);return lines}
function buildPdf(pages){
  const objs=[];const add=o=>{objs.push(o);return objs.length};const catalog=add('');const pagesId=add('');const f1=add('<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>');const f2=add('<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold >>');const pageIds=[];
  pages.forEach((p,i)=>{const content=p.finish(i+1,pages.length),cid=add(`<< /Length ${content.length} >>\nstream\n${content}\nendstream`),pid=add(`<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 ${f1} 0 R /F2 ${f2} 0 R >> >> /Contents ${cid} 0 R >>`);pageIds.push(pid)});
  objs[catalog-1]=`<< /Type /Catalog /Pages ${pagesId} 0 R >>`;objs[pagesId-1]=`<< /Type /Pages /Kids [${pageIds.map(id=>`${id} 0 R`).join(' ')}] /Count ${pageIds.length} >>`;
  let pdf='%PDF-1.4\n%PVLT\n',offs=[0];objs.forEach((o,i)=>{offs.push(pdf.length);pdf+=`${i+1} 0 obj\n${o}\nendobj\n`});const x=pdf.length;pdf+=`xref\n0 ${objs.length+1}\n0000000000 65535 f \n`;for(let i=1;i<offs.length;i++)pdf+=String(offs[i]).padStart(10,'0')+' 00000 n \n';pdf+=`trailer\n<< /Size ${objs.length+1} /Root ${catalog} 0 R >>\nstartxref\n${x}\n%%EOF`;return new Blob([new TextEncoder().encode(pdf)],{type:'application/pdf'})
}

function commandSearch(q){
  q=String(q||'').toLowerCase().trim();const terms=q.split(/\s+/).filter(Boolean),items=[...state.ideas.map(x=>({...x,_type:'idea',_name:x.title})),...state.projects.map(x=>({...x,_type:'project',_name:x.title})),...state.tasks.map(x=>({...x,_type:'task',_name:x.title})),...state.skills.map(x=>({...x,_type:'skill',_name:x.name}))];
  return items.filter(x=>commandFilter==='all'||x._type===commandFilter).map(x=>{const hay=JSON.stringify(x).toLowerCase(),name=String(x._name||'').toLowerCase();if(terms.length&&!terms.every(t=>hay.includes(t)))return null;let score=x.pinned?20:0;if(q&&name===q)score+=120;else if(q&&name.startsWith(q))score+=80;else if(q&&name.includes(q))score+=45;score+=Math.max(0,20-(name.length||0)/8);return{...x,_score:score}}).filter(Boolean).sort((a,b)=>b._score-a._score||String(a._name).localeCompare(String(b._name))).slice(0,40);
}
function commandMeta(x){if(x._type==='task')return `${taskProjectName(x)}${x.dueDate?' · due '+fmtDate(x.dueDate,{month:'short',day:'numeric'}):''}`;if(x._type==='project')return `${x.status||'project'}${x.isWeb?' · web app':''}`;if(x._type==='skill')return `${x.category||'General'} · ${x.filename||'skill.md'}`;return `${x.status||'idea'} · ${x.contentType||'note'}`}
function renderCommand(){const input=$('#command-input');if(!input)return;const q=input.value,arr=commandSearch(q);commandIndex=clamp(commandIndex,0,Math.max(0,arr.length-1));const count=$('#command-count');if(count)count.textContent=`${arr.length} result${arr.length===1?'':'s'}`;$('#command-results').innerHTML=arr.length?arr.map((x,i)=>`<div class="command-result ${i===commandIndex?'active':''}" role="option" aria-selected="${i===commandIndex?'true':'false'}" data-command-type="${x._type}" data-id="${x.id}" data-command-index="${i}"><div><b>${esc(x._name)}</b><small>${esc(x.description||commandMeta(x))}</small><small>${esc(commandMeta(x))}</small></div><div class="command-result-meta">${x.pinned?'<span class="chip yellow">★</span>':''}<span class="chip">${x._type}</span></div></div>`).join(''):`<div class="command-empty">${q?'No matching items. Try fewer words or another filter.':'Start typing, choose a filter, or use one of the quick actions above.'}</div>`;const active=$('.command-result.active',$('#command-results'));active?.scrollIntoView({block:'nearest'})}
function setCommandFilter(filter){commandFilter=filter||'all';commandIndex=0;$$('#command-filters [data-command-filter]').forEach(b=>b.classList.toggle('active',b.dataset.commandFilter===commandFilter));renderCommand()}
function openCommand(initial=''){const d=$('#command-dialog'),input=$('#command-input');if(!d.open)d.showModal();if(initial!==undefined&&input&&input.value!==String(initial))input.value=String(initial);commandIndex=0;renderCommand();setTimeout(()=>{input?.focus();input?.setSelectionRange(input.value.length,input.value.length)},20)}
function closeCommand(clear=true){const d=$('#command-dialog');if(d.open)d.close();if(clear){const a=$('#command-input'),g=$('#global-search');if(a)a.value='';if(g)g.value='';$('#global-search-reset')?.setAttribute('hidden','');}$('#global-search')?.blur()}
function activateCommandResult(el){if(!el)return;const type=el.dataset.commandType,id=el.dataset.id;closeCommand();if(type==='idea'){pageTo('ideas');openEntity('idea',id)}if(type==='project'){pageTo('projects');openProjectDetail(id)}if(type==='task'){pageTo('tasks');openEntity('task',id)}if(type==='skill'){pageTo('skills');state.settings.skillSelected=id;save();renderSkills()}}
async function importBackup(file){try{const obj=JSON.parse(await file.text()),data=obj.data||obj;if(!data.ideas||!data.projects||!data.tasks||!data.skills)throw new Error('Not a PixelVault backup');if(!confirm('Replace the current Django workspace with this backup?'))return;state=mergeState(data);plannerView=state.settings.plannerDefaultView||state.settings.plannerView||'weekly';plannerAnchor=state.settings.plannerAnchor||today();await syncState();applySettings();renderAll();renderSettings();toast('BACKUP IMPORTED INTO DJANGO')}catch(e){toast(`Import failed: ${e.message}`)}}

// Settings and shell UX
let settingsSaveTimer;
$('#page-settings')?.addEventListener('input',e=>{if(!e.target.matches('input,textarea,select'))return;clearTimeout(settingsSaveTimer);settingsSaveTimer=setTimeout(collectSettings,220)});
$('#page-settings')?.addEventListener('change',e=>{if(e.target.matches('input,textarea,select')){clearTimeout(settingsSaveTimer);collectSettings();renderThemeGrid()}});
$('#theme-grid')?.addEventListener('click',e=>{const b=e.target.closest('[data-theme-choice]');if(!b)return;state.settings.theme=b.dataset.themeChoice;save();applySettings();renderThemeGrid();toast(`${THEMES.find(t=>t.id===state.settings.theme)?.name||'THEME'} ACTIVE`)});
$$('[data-settings-target]').forEach(b=>b.addEventListener('click',()=>$('#'+b.dataset.settingsTarget)?.scrollIntoView({behavior:state.settings.reduceMotion?'auto':'smooth',block:'start'})));
$('#reset-appearance').onclick=resetAppearance;$('#settings-export-backup').onclick=exportBackup;$('#settings-import-backup').onchange=e=>e.target.files[0]&&importBackup(e.target.files[0]);$('#test-backend').onclick=testBackend;$('#clear-workspace').onclick=clearWorkspaceData;

// Event delegation
$('.sidebar').addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(b)pageTo(b.dataset.page)});
document.addEventListener('click',async e=>{
  const jump=e.target.closest('[data-page-jump]');if(jump)pageTo(jump.dataset.pageJump);
  const create=e.target.closest('[data-create]');if(create&&!e.target.closest('#entity-dialog'))openEntity(create.dataset.create);
  const pin=e.target.closest('[data-pin]');if(pin){e.preventDefault();e.stopPropagation();const key=pin.dataset.pin==='skill'?'skills':`${pin.dataset.pin}s`,x=state[key].find(x=>x.id===pin.dataset.id);if(x){x.pinned=!x.pinned;save();renderAll();toast(x.pinned?'PINNED':'UNPINNED')}return}
  const editIdea=e.target.closest('.edit-idea');if(editIdea)openEntityDetail('idea',editIdea.dataset.id);
  const convert=e.target.closest('.idea-to-project');if(convert){e.preventDefault();const i=state.ideas.find(x=>x.id===convert.dataset.id);if(i){const before=JSON.parse(JSON.stringify(state)),p={id:uid('project'),title:i.title,description:i.description,tags:[...tags(i.tags)],status:'active',pathHint:'',launchUrl:'',repositoryUrl:'',githubPagesUrl:i.liveSiteUrl||'',techStack:[],goal:i.goal||'',milestone:i.nextAction||'',dueDate:'',isWeb:i.contentType==='webpage',pinned:i.pinned,progress:0,notes:`Created from idea.\n\n${i.content||''}`,created:today(),updated:today()};state.projects.push(p);i.projectId=p.id;i.status='building';i.updated=today();renderCounts();const ok=await flushSave();if(!ok){state=mergeState(before);renderAll();return}renderAll();if($('#entity-dialog')?.open)$('#entity-dialog').close();if($('#detail-dialog')?.open)$('#detail-dialog').close();pageTo('projects');toast('PROJECT CREATED','success',`${p.title} was created from your idea.`);showSaveBanner(`${p.title} · CREATED FROM IDEA`);setTimeout(()=>openProjectDetail(p.id,'PROJECT CREATED · SAVED'),80)}return}
  const plannerMenu=e.target.closest('[data-planner-menu]');if(plannerMenu){e.preventDefault();e.stopPropagation();const block=plannerMenu.closest('.planner-time-block');const already=block?.classList.contains('menu-open');$$('.planner-time-block.menu-open').forEach(x=>x.classList.remove('menu-open'));if(block&&!already)block.classList.add('menu-open');return}
  const plannerAction=e.target.closest('[data-planner-action]');if(plannerAction){e.preventDefault();e.stopPropagation();const id=plannerAction.dataset.id,action=plannerAction.dataset.plannerAction;$$('.planner-time-block.menu-open').forEach(x=>x.classList.remove('menu-open'));if(action==='open'){openEntityDetail('task',id);return}if(action==='duplicate'){await duplicateTask(id);return}movePlannerTask(id,action);return}
  if(!e.target.closest('.planner-task-menu'))$$('.planner-time-block.menu-open').forEach(x=>x.classList.remove('menu-open'));
  const duplicate=e.target.closest('[data-duplicate-task]');if(duplicate){e.preventDefault();e.stopPropagation();const copy=await duplicateTask(duplicate.dataset.duplicateTask);if(copy){$('#detail-dialog')?.close();setTimeout(()=>openEntityDetail('task',copy.id,'TASK DUPLICATED · SAVED'),60)}return}
  const editTask=e.target.closest('.edit-task');if(editTask)openEntityDetail('task',editTask.dataset.id);
  const editProject=e.target.closest('.edit-project');if(editProject){$('#project-dialog').close();openEntity('project',editProject.dataset.id)}
  const openP=e.target.closest('.open-project');if(openP)openProjectDetail(openP.dataset.id);
  const connect=e.target.closest('.connect-project');if(connect)connectProject(connect.dataset.id);
  const launch=e.target.closest('.launch-project');if(launch)launchProject(launch.dataset.id);
  const ideaLive=e.target.closest('.open-live-site');if(ideaLive){e.preventDefault();const url=ideaLive.dataset.url||ideaLive.getAttribute('href');if(!url)return;try{window.open(url,'_blank','noopener,noreferrer')}catch{toast('Could not open live site URL')}}
  const live=e.target.closest('.open-github-pages');if(live){e.preventDefault();try{window.open(live.dataset.url||live.getAttribute('href'),'_blank','noopener,noreferrer')}catch{toast('Could not open GitHub Pages URL')}}
  const repo=e.target.closest('.open-repository');if(repo){try{window.open(repo.dataset.url,'_blank','noopener')}catch{toast('Could not open repository URL')}}
  const skill=e.target.closest('[data-skill-open]');if(skill&&!e.target.closest('[data-pin]')){state.settings.skillSelected=skill.dataset.skillOpen;save();renderSkills()}
  const ss=e.target.closest('[data-save-skill]');if(ss){ss.disabled=true;ss.classList.add('is-saving');saveSkillEditor(ss.dataset.saveSkill).finally(()=>{ss.disabled=false;ss.classList.remove('is-saving')})}
  const ds=e.target.closest('[data-download-skill]');if(ds)downloadSkill(ds.dataset.downloadSkill);
  const as=e.target.closest('[data-attach-skill]');if(as)attachSkill(as.dataset.attachSkill);
  const sf=e.target.closest('[data-save-skill-file]');if(sf)saveSkillToFile(sf.dataset.saveSkillFile);
  const delS=e.target.closest('[data-delete-skill]');if(delS)deleteEntity('skill',delS.dataset.deleteSkill);
  const delA=e.target.closest('.delete-annotation');if(delA){state.annotations=state.annotations.filter(a=>a.id!==delA.dataset.id);save();renderAnnotations();rehydrateAnnotations()}
  const homeItem=e.target.closest('.home-open-item');if(homeItem){const type=homeItem.dataset.homeType,id=homeItem.dataset.id;if(type==='idea'){pageTo('ideas');openEntityDetail('idea',id)}else if(type==='project'){pageTo('projects');openProjectDetail(id)}else if(type==='task'){pageTo('tasks');openEntityDetail('task',id)}else if(type==='skill'){pageTo('skills');state.settings.skillSelected=id;save();renderSkills()}return}
  const taskToggle=e.target.closest('[data-task-toggle]');if(taskToggle){e.preventDefault();e.stopPropagation();const t=state.tasks.find(x=>x.id===taskToggle.dataset.taskToggle);if(t){const was=t.status;t.status=t.status==='done'?'todo':'done';t.completedAt=t.status==='done'?today():'';t.updated=today();if(t.status==='done'&&was!=='done')spawnRecurringTask(t);save();renderAll();toast(t.status==='done'?'TASK COMPLETE':'TASK REOPENED')}return}
  const addStatus=e.target.closest('[data-create-task-status]');if(addStatus){e.preventDefault();openEntity('task','',{status:addStatus.dataset.createTaskStatus});return}
  const projectTask=e.target.closest('[data-project-task-create]');if(projectTask){e.preventDefault();e.stopPropagation();const projectId=projectTask.dataset.projectTaskCreate;$('#project-dialog')?.close();openEntity('task','',{projectId,scheduledDate:plannerView==='daily'&&currentPage==='planner'?plannerAnchor:''});return}
  const skillTab=e.target.closest('[data-skill-tab]');if(skillTab){skillEditorTab=skillTab.dataset.skillTab;renderSkills();return}
  const plannerAdd=e.target.closest('.planner-add-date');if(plannerAdd){e.preventDefault();e.stopPropagation();openEntity('task','',{scheduledDate:plannerAdd.dataset.date||plannerAnchor,time:plannerAdd.dataset.hour?`${String(plannerAdd.dataset.hour).padStart(2,'0')}:00`:''});return}
  const detailClose=e.target.closest('.detail-close');if(detailClose){$('#detail-dialog')?.close();return}
  const detailEdit=e.target.closest('[data-detail-edit]');if(detailEdit){const type=detailEdit.dataset.detailEdit,id=detailEdit.dataset.id;$('#detail-dialog')?.close();openEntity(type,id);return}
  const commandAction=e.target.closest('[data-command-action]');if(commandAction){const action=commandAction.dataset.commandAction;closeCommand();if(action==='new-task')openEntity('task');if(action==='new-idea')openEntity('idea');if(action==='planner')pageTo('planner');return}
  const cmd=e.target.closest('.command-result');if(cmd){activateCommandResult(cmd);return}
});

$('#entity-form').addEventListener('click',async e=>{
  const close=e.target.closest('[data-form-close]');if(close){e.preventDefault();if(entityFormDirty&&!confirm('Discard unsaved changes?'))return;entityFormDirty=false;$('#entity-dialog').close();return}
  const s=e.target.closest('.entity-save');if(s){
    e.preventDefault();const form=$('#entity-form');if(!form.reportValidity()){toast('CHECK REQUIRED FIELDS','warning','Complete the highlighted fields before saving.');return}
    const original=s.textContent;s.disabled=true;s.classList.add('is-saving');s.textContent='SAVING TO DJANGO…';
    const result=await saveEntity(s.dataset.type,s.dataset.id,form);s.disabled=false;s.classList.remove('is-saving');s.textContent=original;
    if(result){entityFormDirty=false;$('#entity-dialog').close();revealSavedEntity(s.dataset.type,result.item,result.isNew)}return;
  }
  const d=e.target.closest('.entity-delete');if(d){e.preventDefault();entityFormDirty=false;$('#entity-dialog').close();deleteEntity(d.dataset.type,d.dataset.id);return}
});
$('#entity-form').addEventListener('input',()=>{entityFormDirty=true});
$('#entity-form').addEventListener('change',()=>{entityFormDirty=true});
$('#entity-form').addEventListener('submit',e=>{e.preventDefault();$('#entity-form .entity-save')?.click()});
$('#entity-dialog').addEventListener('cancel',e=>{if(entityFormDirty&&!confirm('Discard unsaved changes?'))e.preventDefault();else entityFormDirty=false});

$$('#idea-status-filter button').forEach(b=>b.onclick=()=>{ideaStatus=b.dataset.value;$$('#idea-status-filter button').forEach(x=>x.classList.toggle('active',x===b));renderIdeas()});
$$('#project-status-filter button').forEach(b=>b.onclick=()=>{projectStatus=b.dataset.value;$$('#project-status-filter button').forEach(x=>x.classList.toggle('active',x===b));renderProjects()});
$$('#task-status-filter button').forEach(b=>b.onclick=()=>{taskStatus=b.dataset.value;$$('#task-status-filter button').forEach(x=>x.classList.toggle('active',x===b));renderTasks()});
$$('#idea-view button').forEach(b=>b.onclick=()=>{ideaView=b.dataset.view;$$('#idea-view button').forEach(x=>x.classList.toggle('active',x===b));renderIdeas()});
$$('#task-view button').forEach(b=>b.onclick=()=>{taskView=b.dataset.view;$$('#task-view button').forEach(x=>x.classList.toggle('active',x===b));renderTasks()});
$('#idea-search').addEventListener('input',renderIdeas);$('#idea-sort')?.addEventListener('change',renderIdeas);$('#project-search').addEventListener('input',renderProjects);$('#project-sort')?.addEventListener('change',renderProjects);$('#task-search').addEventListener('input',renderTasks);$('#task-project-filter').addEventListener('change',renderTasks);$('#task-priority-filter').addEventListener('change',renderTasks);$('#task-smart-filter')?.addEventListener('change',renderTasks);$('#skill-search').addEventListener('input',renderSkills);$('#skill-category-filter')?.addEventListener('change',renderSkills);$('#skill-pinned-only')?.addEventListener('change',renderSkills);
$$('#planner-view button').forEach(b=>b.onclick=()=>{plannerView=b.dataset.value;renderPlanner()});
$('#planner-snap')?.addEventListener('change',e=>{state.settings.plannerSnapMinutes=+e.target.value||15;save();renderPlanner();toast(`SNAP SET TO ${plannerSnapMinutes()} MIN`)});$('#planner-zoom-out')?.addEventListener('click',()=>{state.settings.plannerHourPx=clamp(plannerHourPx()-16,64,144);save();renderPlanner()});$('#planner-zoom-in')?.addEventListener('click',()=>{state.settings.plannerHourPx=clamp(plannerHourPx()+16,64,144);save();renderPlanner()});
$('#planner-today').onclick=()=>{plannerAnchor=today();renderPlanner()};$('#planner-prev').onclick=()=>{plannerAnchor=plannerView==='daily'?dateShift(plannerAnchor,-1):plannerView==='weekly'?dateShift(plannerAnchor,-7):iso(new Date(new Date(`${plannerAnchor}T12:00:00`).setMonth(new Date(`${plannerAnchor}T12:00:00`).getMonth()-1)));renderPlanner()};$('#planner-next').onclick=()=>{plannerAnchor=plannerView==='daily'?dateShift(plannerAnchor,1):plannerView==='weekly'?dateShift(plannerAnchor,7):iso(new Date(new Date(`${plannerAnchor}T12:00:00`).setMonth(new Date(`${plannerAnchor}T12:00:00`).getMonth()+1)));renderPlanner()};
$('#planner-add-task').onclick=()=>openEntity('task','',{scheduledDate:plannerView==='daily'?plannerAnchor:''});$('#planner-add-inbox').onclick=()=>openEntity('task');$('#planner-date-jump').onchange=e=>{if(e.target.value){plannerAnchor=e.target.value;renderPlanner()}};$('#planner-project-filter').onchange=renderPlanner;$('#planner-hide-done').onchange=renderPlanner;$('#planner-inbox-search').oninput=renderPlanner;$('#planner-clear-filters').onclick=()=>{$('#planner-project-filter').value='all';$('#planner-hide-done').checked=false;$('#planner-inbox-search').value='';renderPlanner()};$('#planner-reschedule-overdue').onclick=()=>{const overdue=plannerVisibleTasks().filter(isOverdue);if(!overdue.length){toast('NO OVERDUE TASKS TO MOVE');return}overdue.forEach(t=>{t.scheduledDate=today();t.updated=today()});plannerAnchor=today();save();renderPlanner();renderTasks();renderHome();toast(`${overdue.length} OVERDUE TASK${overdue.length===1?'':'S'} MOVED TO TODAY`)};
['report-period','report-date','report-privacy','report-signature'].forEach(id=>$('#'+id).addEventListener('input',()=>{if(id==='report-signature'){state.settings.signature=$('#report-signature').value;save()}renderReports()}));
$$('[data-report-period]').forEach(b=>b.onclick=()=>{$('#report-period').value=b.dataset.reportPeriod;$$('[data-report-period]').forEach(x=>x.classList.toggle('active',x===b));renderReports()});
$('#download-social').onclick=()=>downloadServerReport('png');$('#download-pdf').onclick=()=>downloadServerReport('pdf');$('#annotation-page-filter').onchange=renderAnnotations;$('#annotation-color-filter')?.addEventListener('change',renderAnnotations);$('#annotation-search')?.addEventListener('input',renderAnnotations);$('#clear-annotations').onclick=()=>{if(confirm('Delete every highlight and comment?')){state.annotations=[];save();renderAnnotations();rehydrateAnnotations()}};
$('#menu-toggle')?.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();toggleSidebar()});
$('#sidebar-backdrop')?.addEventListener('click',()=>setSidebarOpen(false));
$('#sidebar-collapse')?.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();setSidebarCollapsed(!state.settings.sidebarCollapsed)});
$('#sidebar-create')?.addEventListener('click',()=>{$('#new-any')?.click();if(sidebarMedia())setSidebarOpen(false)});
$('#annotation-open').onclick=()=>pageTo('annotations');$('#settings-open').onclick=()=>pageTo('settings');$('#export-backup').onclick=exportBackup;$('#import-backup').onchange=e=>e.target.files[0]&&importBackup(e.target.files[0]);$('#mobile-create')?.addEventListener('click',()=>$('#new-any').click());
$('#new-any').onclick=()=>{const d=$('#entity-dialog');$('#entity-dialog-body').innerHTML=`<div class="create-dialog-head"><span class="eyebrow">QUICK CAPTURE</span><h2>WHAT ARE YOU MAKING?</h2><p>Start with the right object. You can link everything together later.</p></div><div class="create-grid"><button type="button" class="create-card idea" data-create="idea">${iconImg('idea','create-card-icon','Idea')}<div><b>IDEA</b><small>Capture a thought, prompt, webpage concept or reference.</small></div><i>01</i></button><button type="button" class="create-card project" data-create="project">${iconImg('project','create-card-icon','Project')}<div><b>PROJECT</b><small>Track goals, files, milestones, tasks and launch details.</small></div><i>02</i></button><button type="button" class="create-card task" data-create="task">${iconImg('task','create-card-icon','Task')}<div><b>TASK</b><small>Add the next concrete action to your execution system.</small></div><i>03</i></button><button type="button" class="create-card skill" data-create="skill">${iconImg('skill','create-card-icon','Skill')}<div><b>SKILL.MD</b><small>Create reusable Markdown knowledge for your agents.</small></div><i>04</i></button></div><div class="dialog-actions"><span class="muted create-tip">Tip: press Ctrl+K from anywhere for universal search.</span><button value="cancel" class="neo-btn small">CLOSE</button></div>`;d.showModal();d.addEventListener('click',function once(e){const c=e.target.closest('[data-create]');if(c){d.close();openEntity(c.dataset.create);d.removeEventListener('click',once)}})};

const globalSearch=$('#global-search'),searchShell=$('#global-search-shell'),searchDisplay=$('#global-search-display'),commandDialog=$('#command-dialog'),commandInput=$('#command-input');
searchShell?.addEventListener('click',()=>openCommand(globalSearch?.value||''));
commandInput.addEventListener('input',()=>{commandIndex=0;if(globalSearch)globalSearch.value=commandInput.value;if(searchDisplay)searchDisplay.textContent=commandInput.value||'Search everything or run a command…';renderCommand()});
$('#command-close').onclick=()=>closeCommand();$('#command-clear').onclick=()=>{commandInput.value='';if(globalSearch)globalSearch.value='';if(searchDisplay)searchDisplay.textContent='Search everything or run a command…';commandIndex=0;renderCommand();commandInput.focus()};
$('#command-filters').addEventListener('click',e=>{const b=e.target.closest('[data-command-filter]');if(b)setCommandFilter(b.dataset.commandFilter)});
commandInput.addEventListener('keydown',e=>{const rows=$$('.command-result',$('#command-results'));if(e.key==='ArrowDown'){e.preventDefault();commandIndex=rows.length?(commandIndex+1)%rows.length:0;renderCommand()}if(e.key==='ArrowUp'){e.preventDefault();commandIndex=rows.length?(commandIndex-1+rows.length)%rows.length:0;renderCommand()}if(e.key==='Enter'&&rows.length){e.preventDefault();activateCommandResult(rows[commandIndex]||rows[0])}if(e.key==='Escape'){e.preventDefault();closeCommand()}});
commandDialog.addEventListener('cancel',e=>{e.preventDefault();closeCommand()});commandDialog.addEventListener('pointerdown',e=>{if(e.target===commandDialog)closeCommand()});commandDialog.addEventListener('close',()=>{if(globalSearch)globalSearch.value='';if(searchDisplay)searchDisplay.textContent='Search everything or run a command…'});
document.addEventListener('keydown',e=>{const actionTarget=e.target.closest?.('[data-page-jump][role="button"]');if(actionTarget&&(e.key==='Enter'||e.key===' ')){e.preventDefault();pageTo(actionTarget.dataset.pageJump);return}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openCommand('')}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='b'){e.preventDefault();toggleSidebar()}if((e.ctrlKey||e.metaKey)&&e.key===','){e.preventDefault();pageTo('settings')}if(e.key.toLowerCase()==='n'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName||'')){e.preventDefault();$('#new-any')?.click()}if(e.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName||'')){e.preventDefault();openCommand('')}if(e.key==='Escape'){if(commandDialog.open){e.preventDefault();closeCommand()}hideSelectionToolbar(true);if(sidebarMedia())setSidebarOpen(false)}});

document.addEventListener('pointerdown',e=>{const more=$('.more-menu[open]');if(more&&!e.target.closest('.more-menu'))more.removeAttribute('open');const tb=$('#selection-toolbar');if(tb&&!tb.hidden&&!e.target.closest('#selection-toolbar')&&!e.target.closest('#comment-dialog'))hideSelectionToolbar(true);if(innerWidth<850&&$('.sidebar')?.classList.contains('open')&&!e.target.closest('.sidebar')&&!e.target.closest('#menu-toggle'))setSidebarOpen(false)},true);
document.addEventListener('mouseup',e=>{if(e.target.closest('.selection-toolbar,.pixel-dialog,input,textarea,select,button'))return;setTimeout(()=>showSelectionToolbar(e),10)});
document.addEventListener('selectionchange',()=>{const sel=getSelection();if(sel?.isCollapsed&&!$('#comment-dialog')?.open)hideSelectionToolbar(false)});
window.addEventListener('scroll',()=>hideSelectionToolbar(false),{passive:true});window.addEventListener('resize',()=>{hideSelectionToolbar(false);if(!sidebarMedia())setSidebarOpen(false);syncSidebarControls()});
$('#selection-toolbar').addEventListener('mousedown',e=>e.preventDefault());$('#selection-toolbar').addEventListener('click',e=>{const h=e.target.closest('[data-highlight]');if(h)addAnnotation(h.dataset.highlight,'')});$('#selection-close').onclick=()=>hideSelectionToolbar(true);
$('#selection-comment').onclick=()=>{if(!pendingSelection)return;$('#comment-quote').textContent=pendingSelection.quote;$('#comment-text').value='';hideSelectionToolbar(false);$('#comment-dialog').showModal();setTimeout(()=>$('#comment-text').focus(),20)};$('#save-comment').onclick=e=>{e.preventDefault();const txt=$('#comment-text').value.trim();addAnnotation(state.settings.defaultHighlight||'yellow',txt);$('#comment-dialog').close()};

$$('.quick-filter').forEach(b=>b.onclick=()=>{const f=b.dataset.filter;if(f==='today'){pageTo('planner');plannerView='daily';plannerAnchor=today();renderPlanner()}if(f==='overdue'){pageTo('tasks');taskStatus='all';$('#task-search').value='';$('#task-priority-filter').value='all';if($('#task-smart-filter'))$('#task-smart-filter').value='overdue';renderTasks();toast(`${state.tasks.filter(isOverdue).length} OVERDUE TASKS`)}if(f==='pinned'){pageTo('home');setTimeout(()=>$('#home-pinned').scrollIntoView({behavior:'smooth'}),100)}});

window.addEventListener('load',async()=>{
  try{
    setSyncState('busy','CONNECTING…');
    await loadServerState();
    plannerView=state.settings.plannerDefaultView||state.settings.plannerView||'weekly';
    plannerAnchor=state.settings.plannerAnchor||today();
    setSyncState('ok','DJANGO ONLINE');
    safeRender('Settings application',applySettings);syncSidebarControls();
    renderAll();
    safeRender('Settings',renderSettings);
    const reportDate=$('#report-date');if(reportDate)reportDate.value=today();
    safeRender('Report preview',renderReports);
    let linkedItemOpened=false;safeRender('Linked workspace item',()=>{linkedItemOpened=consumeWorkspaceReference()});
    const landing=state.settings?.landingPage||'home';if(!linkedItemOpened&&landing!=='home')safeRender('Landing page',()=>pageTo(landing));
  }catch(e){
    console.error('[PixelVault] Django startup failed',e);
    setSyncState('error','BACKEND OFFLINE');
    showStartupNotice('Could not load the Django workspace. Make sure migrations were applied and the Django server is still running.','warning');
    renderAll();
  }finally{setTimeout(dismissBoot,180)}
});
})();
