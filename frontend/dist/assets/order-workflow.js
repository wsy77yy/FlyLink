const api=async(path,options={})=>{
  const response=await fetch(`/api${path}`,{...options,headers:{"Content-Type":"application/json",Authorization:`Bearer ${localStorage.getItem("fl_token")||""}`,...options.headers}});
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.detail||"操作失败");
  return data;
};
const getUser=()=>{try{return JSON.parse(localStorage.getItem("fl_user")||"null")}catch{return null}};
const orderId=()=>location.pathname.match(/^\/orders\/(\d+)$/)?.[1];
const money=value=>Number(value||0).toFixed(2);
const dateText=value=>value?new Date(value).toLocaleString("zh-CN",{hour12:false}):"—";
const statusLabels={pending:"待匹配",matched:"已推送",accepted:"已接单",declared:"已申报",arrived:"飞手已到达",working:"作业中",finished:"作业已完成",submitted:"等待管理员审核",reviewed:"管理员已审核",accepted_done:"企业已验收",settled:"已结算",cancelled:"已取消"};

async function action(id,name,data={}){
  try{await api(`/orders/${id}/${name}/`,{method:"POST",body:JSON.stringify(data)});await renderWorkflow(true)}catch(error){alert(error.message)}
}

function button(label,handler,type="primary"){
  const el=document.createElement("button");el.type="button";el.className=`workflow-btn ${type}`;el.textContent=label;el.addEventListener("click",handler);return el;
}

async function confirmArrival(id){
  if(!navigator.geolocation){alert("当前浏览器不支持定位");return}
  navigator.geolocation.getCurrentPosition(
    position=>action(id,"arrive",{lat:position.coords.latitude,lng:position.coords.longitude}),
    ()=>alert("无法获取当前位置，请允许浏览器使用定位后重试。"),
    {enableHighAccuracy:true,timeout:12000},
  );
}

let workflowLoading=false;
async function renderWorkflow(force=false){
  const id=orderId(),user=getUser(),detail=document.querySelector(".detail");
  if(!id||!user||!detail||workflowLoading)return;
  let panel=detail.querySelector("[data-order-workflow]");
  if(panel&&!force)return;
  if(panel)panel.remove();
  workflowLoading=true;
  try{
    const progress=await api(`/orders/${id}/progress/`),order=progress.order;
    detail.querySelector("[data-order-workflow]")?.remove();
    panel=document.createElement("section");panel.className="workflow-panel glass-panel";panel.dataset.orderWorkflow="true";
    const title=document.createElement("div");title.className="workflow-title";title.innerHTML=`<div><p class="eyebrow">ORDER CONTROL</p><h3>企业作业流程</h3></div><span class="workflow-status">${statusLabels[order.status]||order.status}</span>`;panel.append(title);
    const financial=document.createElement("div");financial.className="workflow-grid";
    financial.innerHTML=`<div><span>20%预付款</span><strong>¥${money(order.deposit_amount||Number(order.budget)*.2)}</strong><small>${order.deposit_paid_at?`已支付 ${dateText(order.deposit_paid_at)}`:"待支付"}</small></div><div><span>80%尾款</span><strong>¥${money(order.balance_amount||Number(order.budget)*.8)}</strong><small>${order.balance_paid_at?`已支付 ${dateText(order.balance_paid_at)}`:"管理员审核后支付"}</small></div><div><span>到达任务点</span><strong>${order.arrived_at?"已到达":"待确认"}</strong><small>${order.arrival_distance_km==null?"500米范围内定位确认":`距任务点 ${Number(order.arrival_distance_km).toFixed(3)} km`}</small></div><div><span>成果提交期限</span><strong>${order.submission_deadline?dateText(order.submission_deadline):"尚未开始"}</strong><small>${order.finished_at?"完成作业后24小时内":"飞手点击完成后开始计时"}</small></div>`;
    panel.append(financial);
    const latest=(progress.tracks||[]).at(-1),location=document.createElement("div");location.className="workflow-location";
    location.innerHTML=`<span>飞手实时位置</span><strong>${latest?`${latest.lat}, ${latest.lng}`:"暂无轨迹位置"}</strong><small>${latest?`更新时间 ${dateText(latest.recorded_at)}`:"飞手上传轨迹后企业可查看"}</small>`;panel.append(location);
    const actions=document.createElement("div");actions.className="workflow-actions";
    if(user.role==="enterprise"){
      if(order.pilot&&!order.deposit_paid_at&&["accepted","declared","arrived"].includes(order.status))actions.append(button(`支付20%预付款 ¥${money(order.deposit_amount||Number(order.budget)*.2)}`,()=>confirm("确认模拟支付20%预付款？")&&action(id,"pay_deposit")));
      if(order.status==="reviewed")actions.append(button(`支付80%尾款 ¥${money(order.balance_amount||Number(order.budget)*.8)}`,()=>confirm("管理员已审核通过，确认模拟支付80%尾款？")&&action(id,"pay_balance"),"success"));
      if(!["submitted","reviewed","accepted_done","settled","cancelled"].includes(order.status))actions.append(button("取消订单",()=>{const reason=prompt("请输入取消原因（发布1小时后且飞手已接单，将收取任务金额5%的违约款）：","");if(reason!==null&&confirm("确认取消此订单？"))action(id,"cancel_order",{reason})},"danger"));
      actions.append(button("刷新飞手位置",()=>renderWorkflow(true),"plain"));
    }
    if(user.role==="pilot"){
      if(order.status==="declared")actions.append(button("已到达 · 定位确认",()=>confirmArrival(id)));
      if(order.status==="arrived")actions.append(button("开始作业",()=>action(id,"start_work")));
      if(order.status==="working")actions.append(button("已完成作业",()=>confirm("确认现场作业已完成？确认后须在24小时内提交成果。")&&action(id,"finish_work"),"success"));
      if(order.status==="finished")actions.append(button("提交作业任务",()=>action(id,"submit_work"),"success"));
    }
    panel.append(actions);
    detail.querySelector(".head")?.after(panel);
    detail.querySelectorAll(".ops button").forEach(el=>{if(["开始作业","提交待验收","甲方验收并结算"].includes(el.textContent.trim()))el.style.display="none"});
  }catch(error){console.warn("订单流程面板加载失败",error)}finally{workflowLoading=false}
}

let scheduled=false;
new MutationObserver(()=>{if(scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;renderWorkflow()})}).observe(document.documentElement,{subtree:true,childList:true});
window.addEventListener("popstate",()=>renderWorkflow(true));
renderWorkflow();
