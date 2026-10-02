(function () {
  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const token = () => localStorage.getItem('fl_token') || localStorage.getItem('access_token') || localStorage.getItem('access') || localStorage.getItem('token') || sessionStorage.getItem('access_token') || '';
  const api = async (url, options = {}) => {
    const headers = Object.assign({'Content-Type':'application/json'}, options.headers || {});
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(url, Object.assign({}, options, {headers}));
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || '请求失败');
    return data;
  };

  function simplifyOverview() {
    const cards = [...document.querySelectorAll('main div, body > div div')].filter(el => {
      const text = el.textContent.trim();
      return /^(已注册用户|已注册企业|已注册飞手|订单总数|进行中订单|招聘信息|招聘中岗位|面试申请|设备总数|可租设备|租赁订单|在租设备)\s*\d+$/.test(text.replace(/\s+/g, ''));
    });
    if (cards.length < 6 || document.querySelector('.admin-summary-table')) return;
    const values = {};
    cards.forEach(card => {
      const match = card.textContent.trim().match(/^([^\d]+)\s*(\d+)$/s);
      if (match) values[match[1].trim()] = match[2];
    });
    const container = cards[0].parentElement;
    if (!container) return;
    container.innerHTML = `<div class="admin-summary-table">
      <div class="summary-row summary-head"><span>业务板块</span><span>总量</span><span>当前活跃</span><span>补充信息</span></div>
      <div class="summary-row"><strong>用户与资质</strong><span>${esc(values['已注册用户'] || 0)}</span><span>企业 ${esc(values['已注册企业'] || 0)} / 飞手 ${esc(values['已注册飞手'] || 0)}</span><span>进入“用户与资质审核”处理</span></div>
      <div class="summary-row"><strong>作业订单</strong><span>${esc(values['订单总数'] || 0)}</span><span>进行中 ${esc(values['进行中订单'] || 0)}</span><span>进入“订单监管”查看进度</span></div>
      <div class="summary-row"><strong>招聘业务</strong><span>${esc(values['招聘信息'] || 0)}</span><span>招聘中 ${esc(values['招聘中岗位'] || 0)}</span><span>面试申请 ${esc(values['面试申请'] || 0)}</span></div>
      <div class="summary-row"><strong>设备租赁</strong><span>${esc(values['设备总数'] || 0)}</span><span>可租 ${esc(values['可租设备'] || 0)}</span><span>租赁单 ${esc(values['租赁订单'] || 0)} / 在租 ${esc(values['在租设备'] || 0)}</span></div>
    </div>`;
  }

  function detailMarkup(order) {
    const id = order.id;
    const code = order.order_no || order.order_number || `订单 #${id}`;
    const status = order.status_display || order.status || '—';
    const company = order.enterprise_name || order.company_name || (order.enterprise && (order.enterprise.company_name || order.enterprise.username)) || '—';
    const pilot = order.pilot_name || (order.pilot && (order.pilot.real_name || order.pilot.username)) || '尚未匹配';
    const fields = [
      ['订单编号', code], ['当前状态', status], ['需求企业', company], ['执行飞手', pilot],
      ['作业地点', order.location || order.address || '—'], ['执行时间', order.scheduled_at || order.execution_time || '—'],
      ['作业规模', order.duration ? `${order.duration} 小时` : (order.scale || '—')], ['资质要求', order.qualification_requirement || order.qualification || '—']
    ];
    return `<div class="admin-order-modal" role="dialog" aria-modal="true">
      <div class="admin-order-dialog">
        <div class="dialog-head"><div><small>ORDER SUPERVISION</small><h2>${esc(code)}</h2></div><button type="button" data-close-detail>关闭</button></div>
        <div class="admin-detail-grid">${fields.map(([k,v]) => `<div><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`).join('')}</div>
        <section><h3>合规闸门</h3><div id="admin-detail-gates"><p class="muted">正在读取合规状态…</p></div></section>
        <section><h3>监管说明</h3><p class="muted">管理员可在此核对订单、人员和合规条件。空域及天气状态请前往“空域与合规”页调整。</p></section>
      </div></div>`;
  }

  async function openOrderDetail(id) {
    let order;
    try { order = await api(`/api/orders/${id}/`); }
    catch (error) {
      try {
        const workspace = await api('/api/common/admin-workspace/');
        const orders = workspace.orders || (workspace.data && workspace.data.orders) || [];
        order = orders.find(item => String(item.id) === String(id));
      } catch (_) {}
      if (!order) { alert(`无法读取订单详情：${error.message}`); return; }
    }
    document.body.insertAdjacentHTML('beforeend', detailMarkup(order));
    document.querySelector('[data-close-detail]').onclick = () => document.querySelector('.admin-order-modal').remove();
    try {
      const result = await api(`/api/orders/${id}/compliance/`);
      const gates = result.gates || result.items || [];
      document.getElementById('admin-detail-gates').innerHTML = gates.length ? `<div class="gate-table">${gates.map(g => `<div><span class="gate-dot ${g.passed ? 'pass' : 'block'}"></span><strong>${esc(g.label || g.name)}</strong><span>${g.passed ? '已通过' : esc(g.reason || '尚未通过')}</span></div>`).join('')}</div>` : '<p class="muted">该订单尚无合规检查数据。</p>';
    } catch (error) { document.getElementById('admin-detail-gates').innerHTML = `<p class="muted">${esc(error.message)}</p>`; }
  }

  document.addEventListener('click', (event) => {
    const control = event.target.closest('a,button');
    if (!control || control.textContent.trim() !== '查看') return;
    const href = control.getAttribute('href') || '';
    const match = href.match(/\/orders\/(\d+)/);
    const row = control.closest('[data-order-id]');
    const id = (row && row.dataset.orderId) || (match && match[1]);
    if (!id) return;
    event.preventDefault(); event.stopImmediatePropagation();
    openOrderDetail(id);
  }, true);

  window.openAdminOrderDetail = openOrderDetail;
  const observer = new MutationObserver(simplifyOverview);
  document.addEventListener('DOMContentLoaded', () => { observer.observe(document.body, {childList:true, subtree:true}); simplifyOverview(); });
})();

// V2: rebuild the two affected panels from their data instead of depending on
// the original card markup. This also makes the result stable after tab switches.
(function () {
  const exactText = text => [...document.querySelectorAll('h1,h2,h3,h4,p,span,div')].find(el => el.children.length === 0 && el.textContent.trim() === text);
  const closestPanel = node => node && (node.closest('section,[data-panel],.workspace-panel,.admin-panel,.panel') || node.parentElement);
  const getToken = () => localStorage.getItem('fl_token') || localStorage.getItem('access_token') || localStorage.getItem('access') || localStorage.getItem('token') || sessionStorage.getItem('access_token') || '';
  const getWorkspace = async () => {
    const headers = getToken() ? {Authorization:`Bearer ${getToken()}`} : {};
    const response = await fetch('/api/common/admin-workspace/', {headers});
    if (!response.ok) throw new Error('管理员数据读取失败');
    return response.json();
  };
  const escapeHtml = value => String(value == null ? '' : value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const numberFor = label => {
    const labelNode = exactText(label);
    if (!labelNode) return '0';
    let card = labelNode.parentElement;
    while (card && card !== document.body) {
      const values = [...card.querySelectorAll('*')].filter(el => el.children.length === 0).map(el => el.textContent.trim()).filter(value => /^\d+$/.test(value));
      if (values.length) return values[0];
      card = card.parentElement;
    }
    return '0';
  };
  function rebuildOverview() {
    const heading = exactText('平台管理数据');
    const overviewTab = exactText('运营总览');
    if (!heading || !overviewTab || document.querySelector('.overview-business-table')) return;
    const firstLabel = exactText('已注册用户');
    if (!firstLabel) return;
    let grid = firstLabel.parentElement;
    while (grid && grid !== document.body && !/已注册企业/.test(grid.textContent)) grid = grid.parentElement;
    if (!grid || grid === document.body) return;
    const table = document.createElement('div');
    table.className = 'admin-summary-table overview-business-table';
    table.innerHTML = `<div class="summary-row summary-head"><span>业务板块</span><span>总量</span><span>当前状态</span><span>管理入口</span></div>
      <div class="summary-row"><strong>用户与资质</strong><span>${numberFor('已注册用户')} 人</span><span>企业 ${numberFor('已注册企业')} · 飞手 ${numberFor('已注册飞手')}</span><span>用户与资质审核</span></div>
      <div class="summary-row"><strong>作业订单</strong><span>${numberFor('订单总数')} 单</span><span>进行中 ${numberFor('进行中订单')}</span><span>订单监管</span></div>
      <div class="summary-row"><strong>招聘业务</strong><span>${numberFor('招聘信息')} 条</span><span>招聘中 ${numberFor('招聘中岗位')} · 面试 ${numberFor('面试申请')}</span><span>业务数据汇总</span></div>
      <div class="summary-row"><strong>设备租赁</strong><span>${numberFor('设备总数')} 台</span><span>可租 ${numberFor('可租设备')} · 在租 ${numberFor('在租设备')}</span><span>资金管理</span></div>`;
    grid.insertAdjacentElement('beforebegin', table);
    grid.style.setProperty('display', 'none', 'important');
  }
  async function rebuildOrders() {
    const heading = exactText('订单全流程监管');
    if (!heading) return;
    const panel = closestPanel(heading);
    if (!panel || panel.dataset.v2Orders === 'true') return;
    let workspace;
    try { workspace = await getWorkspace(); } catch (_) { return; }
    const orders = workspace.orders || (workspace.data && workspace.data.orders) || [];
    const oldRows = [...panel.querySelectorAll('a,button')].filter(el => el.textContent.trim() === '查看');
    if (!oldRows.length) return;
    const listContainer = panel.querySelector('#admin-orders') || oldRows[0].parentElement.parentElement;
    if (!listContainer) return;
    listContainer.innerHTML = orders.map(order => `<div class="admin-v2-order-row" data-order-id="${escapeHtml(order.id)}">
      <div><strong>${escapeHtml(order.order_no || order.order_number || `订单 #${order.id}`)}</strong><small>${escapeHtml(order.location || order.address || '未填写作业地点')}</small></div>
      <span>${escapeHtml(order.enterprise_name || order.company_name || '需求企业')}</span>
      <span>${escapeHtml(order.status_display || order.status || '—')}</span>
      <button type="button" class="admin-v2-view" data-order-id="${escapeHtml(order.id)}">监管详情</button>
    </div>`).join('') || '<p class="muted">暂无订单。</p>';
    panel.dataset.v2Orders = 'true';
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('.admin-v2-view');
    if (!button) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (typeof window.openAdminOrderDetail === 'function') window.openAdminOrderDetail(button.dataset.orderId);
    else {
      const fallback = [...document.querySelectorAll('[data-order-id]')].find(el => el.dataset.orderId === button.dataset.orderId && el !== button);
      const legacy = fallback && fallback.querySelector('a[href*="/orders/"]');
      if (legacy) legacy.click();
    }
  }, true);
  const refresh = () => { rebuildOverview(); rebuildOrders(); };
  const observer = new MutationObserver(() => setTimeout(refresh, 20));
  document.addEventListener('DOMContentLoaded', () => { observer.observe(document.body, {subtree:true,childList:true}); setTimeout(refresh, 300); setTimeout(refresh, 1000); });
})();
