const user=()=>{try{return JSON.parse(localStorage.getItem('fl_user')||'null')}catch{return null}};
const token=()=>localStorage.getItem('fl_token')||'';
const api=async(path,options={})=>{const response=await fetch(`/api${path}`,{...options,headers:{'Content-Type':'application/json',Authorization:`Bearer ${token()}`,...options.headers}});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||'请求失败');return data};
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const date=value=>value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—';
const statusClass=value=>['settled','accepted_done','reviewed'].includes(value)?'ok':['cancelled'].includes(value)?'bad':'wait';

function shell(title,subtitle,content){
  const current=user();
  const scope='data-v-13da54f5';
  const menu=current?.role==='enterprise'?'<a href="/orders/publish">需求发单</a><a href="/jobs">招聘中心</a><a href="/rental">设备租赁</a><a href="/profile">个人中心</a><a href="/orders/my">我的订单</a><a href="/finance">资金中心</a><a href="/notifications">消息中心</a>':'<a href="/orders/hall">抢单大厅</a><a href="/jobs">招募大厅</a><a href="/rental">设备租赁</a><a href="/profile">个人中心</a><a href="/finance">收益中心</a><a href="/notifications">消息中心</a>';
  const role=current?.role==='enterprise'?'需求企业':'持证飞手';
  return `<div class="layout" ${scope}><header class="nav glass-panel" ${scope}><div class="nav-inner" ${scope}><a class="brand" href="/" ${scope}><span class="logo-mark" ${scope}><span class="rotor" ${scope}></span></span><span class="brand-text" ${scope}><strong class="brand-name" ${scope}>FlyLink</strong><span class="brand-cn" ${scope}>飞链</span></span></a><nav class="menu" ${scope}>${menu}</nav><div class="actions" ${scope}><span class="fb-role">${role}</span><span class="uname" ${scope}>${esc(current?.username||'')}</span><button class="fb-logout" type="button" onclick="localStorage.removeItem('fl_token');localStorage.removeItem('fl_user');location.href='/login'">退出</button></div></div></header><main class="main fb-main" ${scope}><div class="fb-heading"><div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div></div>${content}</main><footer class="footer" ${scope}><div>FlyLink 飞链 · 无人机飞手供需匹配综合服务平台</div><div class="muted" ${scope}>次结商单 · 长期招聘 · 设备租赁</div></footer></div>`;
}

async function renderMyOrders(){
  document.title='我的订单 · FlyLink';
  document.querySelector('#app').innerHTML=shell('我的订单','集中查看进行中与历史作业订单','<section class="fb-panel"><div class="fb-filters"><input id="fb-search" placeholder="搜索订单号或地点"><select id="fb-status"><option value="">全部状态</option><option value="pending_review">待平台审核</option><option value="pending">待匹配</option><option value="matched">已推送</option><option value="accepted">已接单</option><option value="working">作业中</option><option value="submitted">待审核</option><option value="rectifying">整改中</option><option value="disputed">争议处理中</option><option value="aborted">异常中止</option><option value="refunded">已退款</option><option value="settled">已结算</option></select></div><div id="fb-orders" class="fb-list"><p class="fb-muted">订单加载中……</p></div></section>');
  const payload=await api('/orders/');const orders=payload.results||payload;const host=document.querySelector('#fb-orders');
  const paint=()=>{const q=document.querySelector('#fb-search').value.trim().toLowerCase(),s=document.querySelector('#fb-status').value;const rows=orders.filter(o=>(!s||o.status===s)&&(!q||`${o.order_no} ${o.location}`.toLowerCase().includes(q)));host.innerHTML=rows.length?rows.map(o=>`<article class="fb-order"><div><div class="fb-row"><strong>${esc(o.order_no)}</strong><span class="fb-chip ${statusClass(o.status)}">${esc(o.status_display)}</span></div><h3>${esc(o.location)}</h3><p>${esc(o.work_type_display)} · ${esc(o.area_or_duration)} · ${date(o.execute_time)}</p></div><div class="fb-order-side"><b>¥${Number(o.budget).toFixed(2)}</b><div><a class="fb-btn ghost" href="/orders/${o.id}/candidates">候选飞手</a><a class="fb-btn" href="/orders/${o.id}">订单详情</a></div></div></article>`).join(''):'<div class="fb-empty"><strong>没有匹配的订单</strong><p>试试调整搜索或状态筛选。</p></div>'};
  document.querySelector('#fb-search').addEventListener('input',paint);document.querySelector('#fb-status').addEventListener('change',paint);paint();
}

async function renderCandidates(id){
  document.querySelector('#app').innerHTML=shell('候选飞手','根据资质、距离、技能和当前状态综合排序','<section class="fb-panel"><div id="fb-candidates" class="fb-card-grid"><p class="fb-muted">正在计算匹配结果……</p></div></section>');
  const rows=await api(`/orders/${id}/candidates/`);const host=document.querySelector('#fb-candidates');host.innerHTML=rows.length?rows.map(p=>`<article class="fb-pilot"><div class="fb-avatar">${esc((p.real_name||p.username).slice(0,1))}</div><div class="fb-score">${p.score}%<small>匹配度</small></div><h3>${esc(p.real_name||p.username)} ${p.verified?'<span class="fb-verified">已认证</span>':''}</h3><p>${esc(p.license_level||'未填写执照')} · ${p.years_exp}年经验 · ${p.distance_km}km</p><div class="fb-tags">${(p.skills||[]).map(x=>`<span>${esc(x)}</span>`).join('')}</div><p class="fb-hint">候选人由系统推送，飞手接单前将再次执行五项硬闸门。</p></article>`).join(''):'<div class="fb-empty"><strong>暂无符合条件的飞手</strong><p>可返回订单详情后重新匹配。</p></div>';
}

async function renderNotifications(){
  document.querySelector('#app').innerHTML=shell('消息中心','订单、合规、资金与系统通知统一汇总','<section class="fb-panel"><div class="fb-filter-tabs"><button class="active">全部消息</button><button>订单</button><button>合规</button><button>资金</button></div><div id="fb-notifications" class="fb-notifications"><p class="fb-muted">消息加载中……</p></div></section>');
  const rows=await api('/common/notifications/');document.querySelector('#fb-notifications').innerHTML=(rows.some(n=>n.unread)?'<div class="fb-toolbar"><button id="fb-read-all" class="fb-btn ghost">全部标为已读</button></div>':'')+(rows.length?rows.map(n=>`<a class="fb-note ${n.unread?'unread':''}" data-note-id="${n.id}" href="${esc(n.link)}"><span class="fb-note-icon">${n.type==='compliance'?'⛨':n.type==='finance'?'¥':'◎'}</span><div><div class="fb-row"><strong>${esc(n.title)}</strong>${n.unread?'<i>未读</i>':''}</div><p>${esc(n.content)}</p><small>${date(n.created_at)}</small></div><b>›</b></a>`).join(''):'<div class="fb-empty"><strong>暂无新消息</strong><p>订单和审批状态变化后会在这里提醒。</p></div>');document.querySelector('#fb-read-all')?.addEventListener('click',async()=>{await api('/common/notifications/',{method:'POST',body:'{}'});renderNotifications()});document.querySelectorAll('[data-note-id]').forEach(a=>a.addEventListener('click',()=>api('/common/notifications/',{method:'POST',body:JSON.stringify({ids:[Number(a.dataset.noteId)]})}).catch(()=>{})));
}

async function renderFinance(){
  const current=user(),pilot=current?.role==='pilot';document.querySelector('#app').innerHTML=shell(pilot?'收益中心':'资金与发票',pilot?'查看结算明细并提交模拟提现':'查看订单结算并提交模拟开票','<section class="fb-panel"><div class="fb-finance-summary" id="fb-finance-summary"></div><form id="fb-finance-form" class="fb-form"><h3>'+(pilot?'申请提现':'申请电子发票')+'</h3><label>金额<input name="amount" type="number" min="1" step="0.01" required></label>'+(pilot?'<label>模拟到账账户<input name="account_hint" placeholder="例如：尾号 8888"></label>':'<label>发票抬头<input name="title" required></label><label>纳税人识别号<input name="tax_no"></label>')+'<button class="fb-btn" type="submit">提交模拟申请</button><span aria-live="polite"></span></form><div id="fb-finance-list" class="fb-list"></div></section>');
  const paint=async()=>{const data=await api('/common/finance-center/');document.querySelector('#fb-finance-summary').innerHTML=`<article><span>平台服务费率</span><strong>${Number(data.fee_rate)*100}%</strong></article><article><span>已结算订单</span><strong>${data.settlements.length}</strong></article><article><span>${pilot?'提现申请':'开票申请'}</span><strong>${(pilot?data.withdrawals:data.invoices).length}</strong></article>`;const rows=pilot?data.withdrawals:data.invoices;document.querySelector('#fb-finance-list').innerHTML=rows.map(x=>`<article class="fb-order"><div><strong>申请 #${x.id}</strong><p>${date(x.created_at)} · ${esc(x.status)}</p></div><b>¥${Number(x.amount).toFixed(2)}</b></article>`).join('')||'<div class="fb-empty"><p>暂无申请记录</p></div>'};
  document.querySelector('#fb-finance-form').addEventListener('submit',async e=>{e.preventDefault();const form=e.currentTarget,status=form.querySelector('[aria-live]'),payload=Object.fromEntries(new FormData(form));try{await api('/common/finance-center/',{method:'POST',body:JSON.stringify(payload)});status.textContent='已提交模拟审核';form.reset();paint()}catch(error){status.textContent=error.message}});await paint();
}

async function renderAcceptance(id){
  document.querySelector('#app').innerHTML=shell('成果验收','按清单确认成果，也可发起整改或争议','<section class="fb-panel"><form id="fb-acceptance" class="fb-form"><h3>标准验收清单</h3><label><input type="checkbox" name="track"> 作业轨迹完整</label><label><input type="checkbox" name="media"> 影像与成果材料完整</label><label><input type="checkbox" name="scope"> 作业范围符合订单</label><label>验收意见<textarea name="note" rows="4" placeholder="整改或争议时请填写具体原因"></textarea></label><div><button class="fb-btn" data-result="accepted">验收通过并结算</button><button class="fb-btn ghost" data-result="rectify">要求整改</button><button class="fb-btn danger" data-result="dispute">发起争议</button></div><span aria-live="polite"></span></form></section>');
  document.querySelectorAll('[data-result]').forEach(button=>button.addEventListener('click',async e=>{e.preventDefault();const form=document.querySelector('#fb-acceptance'),result=button.dataset.result,checklist=[...form.querySelectorAll('input[type=checkbox]:checked')].map(x=>x.name);try{await api(`/orders/${id}/acceptance/`,{method:'POST',body:JSON.stringify({result,checklist,note:form.note.value})});form.querySelector('[aria-live]').textContent='验收结果已提交';setTimeout(()=>location.href=`/orders/${id}`,700)}catch(error){form.querySelector('[aria-live]').textContent=error.message}}));
}

async function renderRentalOrder(id){
  const current=user();document.querySelector('#app').innerHTML=shell('租赁下单','选择租期与取件方式，确认费用后生成模拟租赁订单','<section class="fb-panel"><div id="fb-rental-order"><p class="fb-muted">正在加载设备信息……</p></div></section>');
  const model=await api(`/rental/devices/${id}/`),host=document.querySelector('#fb-rental-order');let block='';
  if(model.status!=='available'||Number(model.stock||0)<1)block='该型号目前没有可租设备，请返回设备租赁页选择其他型号。';
  if(current?.role==='pilot'){try{const compliance=await api('/common/pilot-compliance/');if(!compliance.verified)block=compliance.review_reason||`飞手实名认证与飞行资质尚未通过；请先到个人中心补齐：${(compliance.missing||[]).join('、')}`;}catch{block='暂时无法读取飞手认证状态，请稍后重试。'}}
  const today=new Date().toISOString().slice(0,10);host.innerHTML=`<div class="fb-rental-layout"><article class="fb-rental-model"><span class="fb-chip ${block?'bad':'ok'}">${block?'暂不可租':'现货可租 '+model.stock+' 台'}</span><h2>${esc(model.model_name)}</h2><p>${esc(model.description||model.specs||'')}</p><div class="fb-price-line"><strong>日租 ¥${Number(model.daily_price).toFixed(2)}</strong><span>月租 ¥${Number(model.monthly_price).toFixed(2)}</span><span>押金 ¥${Number(model.deposit).toFixed(2)}</span></div></article><aside class="fb-rental-rules"><h3>租赁条件</h3><ul><li>企业用户登录后可直接申请。</li><li>飞手须完成实名认证及飞行资质审核。</li><li>型号须有可租库存，开始日期不能早于今天。</li><li>单次租期不超过 366 天。</li><li>信用分达到 650 分免押，否则收取页面所示押金。</li><li>保险按 ¥38/天模拟计算。</li></ul></aside></div>${block?`<div class="pilot-compliance-banner"><div><strong>当前不能租赁</strong><p>${esc(block)}</p></div><a href="${current?.role==='pilot'?'/profile#pilot-compliance-editor':'/rental'}">${current?.role==='pilot'?'去完善资料':'返回设备列表'}</a></div>`:`<form id="fb-rental-form" class="fb-form"><h3>填写租赁信息</h3><div class="fb-form-grid"><label>开始日期<input name="start_date" type="date" min="${today}" value="${today}" required></label><label>结束日期<input name="end_date" type="date" min="${today}" value="${today}" required></label><label>取件方式<select name="delivery_type"><option value="pickup">线下自提</option><option value="express">物流配送</option></select></label><label data-address hidden>配送地址<input name="delivery_address" placeholder="请输入模拟配送地址"></label></div><label>备注<textarea name="remark" rows="3" placeholder="可填写设备配件或时间要求"></textarea></label><div id="fb-rental-estimate" class="fb-cost-preview"></div><div class="pilot-profile-actions"><button type="submit">确认租赁并生成订单</button><span aria-live="polite"></span></div></form>`}`;
  const form=document.querySelector('#fb-rental-form');if(!form)return;const delivery=form.delivery_type,address=form.querySelector('[data-address]'),preview=form.querySelector('#fb-rental-estimate');const estimate=()=>{const start=new Date(form.start_date.value),end=new Date(form.end_date.value);if(Number.isNaN(start.valueOf())||Number.isNaN(end.valueOf())||end<start){preview.textContent='请选择有效租期';return}const days=Math.round((end-start)/86400000)+1,rent=days>=28?Number(model.monthly_price)*Math.max(Math.floor(days/30),1):Number(model.daily_price)*days,insurance=38*days;preview.innerHTML=`租期 <strong>${days}</strong> 天 · 租金 <strong>¥${rent.toFixed(2)}</strong> · 保险 <strong>¥${insurance.toFixed(2)}</strong> · 押金按信用分结算`;};delivery.addEventListener('change',()=>{address.hidden=delivery.value!=='express';form.delivery_address.required=delivery.value==='express'});form.start_date.addEventListener('change',estimate);form.end_date.addEventListener('change',estimate);estimate();
  form.addEventListener('submit',async e=>{e.preventDefault();const state=form.querySelector('[aria-live]'),payload=Object.fromEntries(new FormData(form));payload.device=Number(id);state.textContent='正在生成订单……';try{const order=await api('/rental/orders/',{method:'POST',body:JSON.stringify(payload)});state.textContent='订单已生成，正在前往支付确认';setTimeout(()=>location.href=`/rental/my`,700)}catch(error){state.textContent=error.message}});
}

let complianceLoading=false;
async function injectCompliance(){
  const match=location.pathname.match(/^\/orders\/(\d+)$/);if(!match||document.querySelector('[data-compliance-panel]'))return;
  const detail=document.querySelector('.detail');if(!detail)return;
  if(complianceLoading)return;complianceLoading=true;
  try{const data=await api(`/orders/${match[1]}/compliance/`);if(document.querySelector('[data-compliance-panel]'))return;const panel=document.createElement('section');panel.className='fb-compliance glass-panel';panel.dataset.compliancePanel='1';panel.innerHTML=`<div class="fb-compliance-title"><div><small>SAFETY GATE</small><h3>五项作业硬闸门</h3></div><span class="fb-chip ${data.passed?'ok':'bad'}">${data.passed?'全部通过':'禁止作业'}</span></div><div class="fb-gates">${data.gates?.length?data.gates.map(g=>`<div class="${g.passed?'pass':'fail'}"><b>${g.passed?'✓':'!'}</b><span><strong>${esc(g.label)}</strong><small>${esc(g.detail)}</small></span></div>`).join(''):'<p class="fb-muted">订单尚未匹配飞手，暂时无法执行个人资质校验。</p>'}</div>`;detail.querySelector('.head')?.after(panel)}catch(error){console.warn(error)}finally{complianceLoading=false}
}

function injectNavigation(){
  if(['/orders/my','/notifications','/finance'].includes(location.pathname)||/^\/orders\/\d+\/(candidates|acceptance)$/.test(location.pathname)||/^\/rental\/order\/\d+$/.test(location.pathname))return;
  const current=user(),menu=document.querySelector('nav.menu');if(!current||!menu)return;
  [...menu.querySelectorAll('a')].filter(a=>!a.textContent.trim()&&!a.getAttribute('aria-label')).forEach(a=>a.remove());
  const add=(href,label,key)=>{if(menu.querySelector(`[data-first-batch="${key}"]`))return;const a=document.createElement('a');a.href=href;a.textContent=label;a.dataset.firstBatch=key;a.setAttribute('data-v-13da54f5','');menu.append(a)};
  if(current.role==='enterprise')add('/orders/my','我的订单','orders');add('/finance',current.role==='pilot'?'收益中心':'资金中心','finance');add('/notifications','消息中心','notifications');
}

function injectRegistrationConsent(){
  if(location.pathname!='/register'||document.querySelector('[data-register-consent]'))return;const form=document.querySelector('.auth form,.auth .el-form');if(!form)return;const submit=[...form.querySelectorAll('button')].find(b=>b.textContent.includes('注册并登录'));if(!submit)return;const wrap=document.createElement('label');wrap.className='fb-consent';wrap.dataset.registerConsent='1';wrap.innerHTML='<input id="fb-consent" type="checkbox"><span>我已阅读并同意《用户服务协议》《隐私与数据保护政策》和《飞行安全与合规承诺书》</span>';submit.before(wrap);submit.disabled=true;wrap.querySelector('input').addEventListener('change',e=>submit.disabled=!e.target.checked);
}

const originalOpen=XMLHttpRequest.prototype.open,originalSend=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open=function(method,url,...rest){this.__flylinkRegister=String(url).includes('/api/users/register/');return originalOpen.call(this,method,url,...rest)};
XMLHttpRequest.prototype.send=function(body){if(this.__flylinkRegister&&typeof body==='string'){const consent=document.querySelector('#fb-consent');if(!consent?.checked)throw new Error('请先确认并同意相关协议');try{const payload=JSON.parse(body);payload.agreements_accepted=true;body=JSON.stringify(payload)}catch{}}return originalSend.call(this,body)};

const route=async()=>{const path=location.pathname.replace(/\/$/,'')||'/',app=document.querySelector('#app');if(app?.dataset.fbRoute===path)return;let renderer=null;if(path==='/orders/my'&&user()?.role==='enterprise')renderer=()=>renderMyOrders();const candidate=path.match(/^\/orders\/(\d+)\/candidates$/);if(candidate&&user()?.role==='enterprise')renderer=()=>renderCandidates(candidate[1]);const acceptance=path.match(/^\/orders\/(\d+)\/acceptance$/);if(acceptance&&user()?.role==='enterprise')renderer=()=>renderAcceptance(acceptance[1]);const rental=path.match(/^\/rental\/order\/(\d+)$/);if(rental&&user())renderer=()=>renderRentalOrder(rental[1]);if(path==='/notifications'&&user())renderer=()=>renderNotifications();if(path==='/finance'&&user())renderer=()=>renderFinance();if(renderer){app.dataset.fbRoute=path;return renderer()}else if(app)delete app.dataset.fbRoute};
route().catch(error=>{document.querySelector('#app').innerHTML=shell('页面加载失败',error.message,'<a class="fb-btn" href="/">返回首页</a>')});
let scheduled=false;new MutationObserver(()=>{if(scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;route().catch(console.warn);injectNavigation();injectCompliance();injectRegistrationConsent()})}).observe(document.documentElement,{subtree:true,childList:true});
const originalPushState=history.pushState.bind(history),originalReplaceState=history.replaceState.bind(history);history.pushState=(...args)=>{originalPushState(...args);queueMicrotask(()=>route().catch(console.warn))};history.replaceState=(...args)=>{originalReplaceState(...args);queueMicrotask(()=>route().catch(console.warn))};addEventListener('popstate',()=>route().catch(console.warn));
injectNavigation();injectCompliance();injectRegistrationConsent();
// Pilot compliance guidance and a concrete place to complete required data.
(function () {
  const authHeaders = () => {
    const token = localStorage.getItem('fl_token') || localStorage.getItem('access_token') || localStorage.getItem('access') || localStorage.getItem('token') || sessionStorage.getItem('access_token');
    return token ? {Authorization:`Bearer ${token}`} : {};
  };
  const api = async (url, options = {}) => {
    const response = await fetch(url, {...options, headers:{'Content-Type':'application/json', ...authHeaders(), ...(options.headers || {})}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '请求失败');
    return data;
  };
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let currentCompliance = null;
  const isPilot = () => {
    try { const user = JSON.parse(localStorage.getItem('fl_user') || localStorage.getItem('user') || sessionStorage.getItem('user') || '{}'); return user.role === 'pilot'; } catch (_) { return false; }
  };

  async function loadCompliance() {
    if (!isPilot()) return null;
    try { currentCompliance = await api('/api/common/pilot-compliance/'); return currentCompliance; } catch (_) { return null; }
  }
  async function addBlockingGuidance() {
    const path = location.pathname;
    if (!(/jobs|recruit|rental|mall|profile/.test(path))) return;
    const data = await loadCompliance();
    if (!data || data.verified) return;
    const target = document.querySelector('main') || document.querySelector('#app') || document.body;
    if (!target || document.querySelector('.pilot-compliance-banner')) return;
    const reason = data.missing && data.missing.length ? `尚缺：${data.missing.join('、')}。` : '资料已提交，但管理员尚未审核通过。';
    const action = /profile/.test(path) ? '#pilot-compliance-editor' : '/profile#pilot-compliance-editor';
    target.insertAdjacentHTML('afterbegin', `<div class="pilot-compliance-banner"><div><strong>当前不能投递简历或租赁设备</strong><p>${esc(reason)}请补充资料并等待管理员审核；审核通过后相关功能会自动开放。</p></div><a href="${action}">去补充资料</a></div>`);
  }
  async function addProfileEditor() {
    if (!/profile/.test(location.pathname) || document.getElementById('pilot-compliance-editor')) return;
    const data = await loadCompliance();
    if (!data) return;
    const target = document.querySelector('main') || document.querySelector('#app');
    if (!target) return;
    target.insertAdjacentHTML('beforeend', `<section id="pilot-compliance-editor" class="pilot-profile-editor">
      <h2>实名认证与飞行合规资料</h2><p class="editor-note">这些资料用于岗位投递、设备租赁和作业闸门审核。保存修改后，需要管理员重新审核。</p>
      <div class="pilot-review-state">审核状态：${esc(data.review_status_display || (data.verified ? '已通过' : '待审核'))}${data.review_reason ? ` · 驳回原因：${esc(data.review_reason)}` : ''}${data.missing && data.missing.length ? ` · 待补充 ${esc(data.missing.join('、'))}` : ''}</div>
      <form class="pilot-profile-form">
        <label>真实姓名<input name="real_name" value="${esc(data.real_name)}" required></label>
        <label>身份证号<input name="id_card" value="${esc(data.id_card)}" required></label>
        <label>联系电话<input name="phone" value="${esc(data.phone)}" required></label>
        <label>飞手执照编号<input name="license_no" value="${esc(data.license_no)}" required></label>
        <label>保险有效期<input name="insurance_expiry" type="date" value="${esc(data.insurance_expiry)}" required></label>
        <label>航空器实名登记编号<input name="aircraft_registration_no" value="${esc(data.aircraft_registration_no)}" required></label>
        <label>身份证正面材料<input name="id_card_front" type="file" accept="image/*,.pdf"><small>${data.id_card_front_url?'已提交，可重新上传替换':'未提交'}</small></label>
        <label>身份证反面材料<input name="id_card_back" type="file" accept="image/*,.pdf"><small>${data.id_card_back_url?'已提交，可重新上传替换':'未提交'}</small></label>
        <label>飞手执照材料<input name="license_document" type="file" accept="image/*,.pdf"><small>${data.license_document_url?'已提交，可重新上传替换':'未提交'}</small></label>
        <label>保险凭证<input name="insurance_document" type="file" accept="image/*,.pdf"><small>${data.insurance_document_url?'已提交，可重新上传替换':'未提交'}</small></label>
        <label>航空器登记证明<input name="aircraft_document" type="file" accept="image/*,.pdf"><small>${data.aircraft_document_url?'已提交，可重新上传替换':'未提交'}</small></label>
        <div class="pilot-profile-actions"><button type="submit">保存并提交审核</button><span aria-live="polite"></span></div>
      </form></section>`);
    const form = target.querySelector('.pilot-profile-form');
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const status = form.querySelector('[aria-live]'); status.textContent = '正在保存…';
      const formData = new FormData(form); const payload = {};
      for (const [key,value] of formData.entries()) if (!(value instanceof File)) payload[key]=value;
      try {
        const uploads = new FormData(); let hasUpload=false;
        for (const [key,value] of formData.entries()) if (value instanceof File && value.size) { uploads.append(key,value); hasUpload=true; }
        if (hasUpload) { const uploadResponse=await fetch('/api/common/pilot-document-upload/',{method:'POST',headers:authHeaders(),body:uploads}); const uploadData=await uploadResponse.json().catch(()=>({})); if(!uploadResponse.ok)throw new Error(uploadData.detail||'材料上传失败'); }
        await api('/api/common/pilot-compliance/', {method:'PATCH', body:JSON.stringify(payload)}); status.textContent = '已保存并提交，等待管理员审核';
      }
      catch (error) { status.textContent = error.message; }
    });
    if (location.hash === '#pilot-compliance-editor') target.querySelector('#pilot-compliance-editor').scrollIntoView({behavior:'smooth'});
  }
  document.addEventListener('click', event => {
    const action = event.target.closest('button,a');
    if (!action || !isPilot() || !currentCompliance || currentCompliance.verified) return;
    if (!/(投递|申请职位|立即租赁|确认租赁|提交租赁)/.test(action.textContent.trim())) return;
    event.preventDefault(); event.stopImmediatePropagation();
    const missing = currentCompliance.missing && currentCompliance.missing.length ? `尚缺：${currentCompliance.missing.join('、')}。` : '资料尚未通过管理员审核。';
    if (confirm(`${missing}\n请先补充资料并等待审核通过。现在前往个人中心吗？`)) location.href = '/profile#pilot-compliance-editor';
  }, true);
  const run = () => { loadCompliance(); setTimeout(addBlockingGuidance, 350); setTimeout(addProfileEditor, 500); };
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', run) : run();
})();

// Document-aligned simulated enterprise certification and order exception controls.
(function(){
  const current=user();
  async function enterpriseEditor(){
    if(location.pathname!=='/profile'||current?.role!=='enterprise'||document.querySelector('#enterprise-certification'))return;
    const host=document.querySelector('main')||document.querySelector('#app');if(!host)return;
    const me=await api('/users/me/');const p=me.profile||{};
    host.insertAdjacentHTML('beforeend',`<section id="enterprise-certification" class="pilot-profile-editor"><h2>企业实名认证</h2><p class="editor-note">本演示仅保存模拟证件链接，不接入真实工商或身份核验服务。</p><div class="pilot-review-state">审核状态：${esc(p.review_status||'待完善')}${p.review_reason?' · 原因：'+esc(p.review_reason):''}</div><form class="pilot-profile-form"><label>企业名称<input name="company_name" value="${esc(p.company_name)}" required></label><label>统一社会信用代码<input name="license_no" value="${esc(p.license_no)}" required></label><label>法定代表人<input name="legal_representative" value="${esc(p.legal_representative)}" required></label><label>联系人<input name="contact_name" value="${esc(p.contact_name)}"></label><label>模拟营业执照链接<input name="business_license_url" value="${esc(p.business_license_url)}" placeholder="https://mock.local/license.jpg" required></label><label>模拟法人证件链接<input name="legal_id_url" value="${esc(p.legal_id_url)}" placeholder="https://mock.local/legal-id.jpg" required></label><label>企业地址<input name="address" value="${esc(p.address)}"></label><div class="pilot-profile-actions"><button>保存并提交审核</button><span aria-live="polite"></span></div></form></section>`);
    const form=host.querySelector('#enterprise-certification form');form.addEventListener('submit',async e=>{e.preventDefault();const state=form.querySelector('[aria-live]');try{const result=await api('/common/enterprise-certification/',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});state.textContent=result.detail}catch(error){state.textContent=error.message}});
  }
  function orderControls(){
    const match=location.pathname.match(/^\/orders\/(\d+)$/);if(!match||document.querySelector('[data-doc-controls]'))return;const detail=document.querySelector('.detail');if(!detail)return;
    const panel=document.createElement('section');panel.className='fb-compliance glass-panel';panel.dataset.docControls='1';panel.innerHTML=`<div class="fb-compliance-title"><div><small>ORDER CONTROL</small><h3>验收与异常处理</h3></div></div><p class="fb-muted">企业可进入标准验收清单；订单参与方可在发生异常时中止并留存模拟证据。</p><div style="margin-top:14px"><a class="fb-btn" href="/orders/${match[1]}/acceptance">进入成果验收</a><button class="fb-btn danger" data-abort>异常中止</button></div>`;detail.append(panel);
    panel.querySelector('[data-abort]').addEventListener('click',async()=>{const reason=prompt('请填写异常中止原因：');if(!reason?.trim())return;try{await api(`/orders/${match[1]}/abnormal-abort/`,{method:'POST',body:JSON.stringify({reason:reason.trim(),evidence_url:'https://mock.flylink.local/evidence/demo'})});location.reload()}catch(error){alert(error.message)}});
  }
  const run=()=>{enterpriseEditor().catch(console.warn);setTimeout(orderControls,500)};document.readyState==='loading'?document.addEventListener('DOMContentLoaded',run):run();new MutationObserver(orderControls).observe(document.documentElement,{subtree:true,childList:true});
})();
