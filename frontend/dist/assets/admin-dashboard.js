const labels={user_count:"已注册用户",enterprise_count:"已注册企业",pilot_count:"已注册飞手",order_count:"订单总数",open_order_count:"进行中订单",job_count:"招募信息",open_job_count:"招聘中岗位",application_count:"面试申请",device_total:"设备总数",available_device_count:"可租设备",rental_order_count:"租赁订单",renting_device_count:"在租设备"};

function getUser(){try{return JSON.parse(localStorage.getItem("fl_user")||"null")}catch{return null}}
function logout(){localStorage.removeItem("fl_token");localStorage.removeItem("fl_user");location.replace("/login")}
const authHeaders=()=>({Authorization:`Bearer ${localStorage.getItem("fl_token")||""}`,"Content-Type":"application/json"});

async function loadReviews(){
  const host=document.querySelector("#review-orders");host.innerHTML='<p class="admin-loading">正在加载待审核订单……</p>';
  try{
    const response=await fetch("/api/orders/?status=submitted",{headers:authHeaders()});
    if(!response.ok)throw new Error("待审核订单加载失败");
    const payload=await response.json(),orders=payload.results||payload;
    host.innerHTML="";
    if(!orders.length){host.innerHTML='<p class="admin-empty">当前没有待审核作业。</p>';return}
    for(const order of orders){
      const row=document.createElement("article");row.className="review-order";
      row.innerHTML=`<div><strong>${order.order_no}</strong><p>${order.location} · ${order.pilot_name||"未知飞手"}</p><small>预算 ¥${Number(order.budget).toFixed(2)} · 提交于 ${order.submitted_at?new Date(order.submitted_at).toLocaleString("zh-CN",{hour12:false}):"—"}</small></div>`;
      const approve=document.createElement("button");approve.type="button";approve.textContent="审核通过";approve.addEventListener("click",async()=>{if(!confirm("确认该作业成果审核通过？"))return;const result=await fetch(`/api/orders/${order.id}/admin_review/`,{method:"POST",headers:authHeaders(),body:"{}"});if(!result.ok){const data=await result.json().catch(()=>({}));alert(data.detail||"审核失败");return}loadReviews()});
      row.append(approve);host.append(row);
    }
  }catch(error){host.innerHTML=`<p class="admin-error">${error.message}</p>`}
}

async function loadDashboard(){
  const user=getUser();
  const token=localStorage.getItem("fl_token")||"";
  if(!token||user?.role!=="admin"){logout();return}
  document.querySelector("#admin-name").textContent=`${user.username||"管理员"} · 平台管理员`;
  try{
    const response=await fetch("/api/common/admin-stats/",{headers:{Authorization:`Bearer ${token}`}});
    if(response.status===401||response.status===403){logout();return}
    if(!response.ok)throw new Error("管理员数据加载失败，请稍后重试。");
    const stats=await response.json();
    const container=document.querySelector("#admin-stats");
    for(const [key,label] of Object.entries(labels)){
      const card=document.createElement("article");card.className="admin-card glass-panel";
      const name=document.createElement("p");name.className="admin-label";name.textContent=label;
      const value=document.createElement("strong");value.className="admin-value";value.textContent=String(stats[key]??0);
      card.append(name,value);container.append(card);
    }
    document.querySelector("#admin-status").hidden=true;container.hidden=false;
    loadReviews();
  }catch(error){const status=document.querySelector("#admin-status");status.className="admin-error";status.textContent=error.message}
}

document.querySelector("#logout").addEventListener("click",logout);
document.querySelector("#refresh-review").addEventListener("click",loadReviews);
loadDashboard();
