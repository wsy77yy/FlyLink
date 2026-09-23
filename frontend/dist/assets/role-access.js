const currentUser=()=>{try{return JSON.parse(localStorage.getItem("fl_user")||"null")}catch{return null}};
const role=()=>currentUser()?.role||"";
const allowed=(path,userRole=role())=>{
  if(!userRole)return path==="/"||path==="/jobs"||path==="/rental"||path==="/login"||path==="/register";
  if(userRole==="admin")return path==="/"||path==="/profile";
  if(userRole==="enterprise")return path==="/"||path==="/orders/publish"||path.startsWith("/orders/")&&!path.startsWith("/orders/hall")||path==="/jobs"||path==="/jobs/publish"||path.startsWith("/jobs/chat")||path==="/rental"||path.startsWith("/rental/order/")||path==="/rental/my"||path==="/profile";
  if(userRole==="pilot")return path==="/"||path==="/orders/hall"||/^\/orders\/\d+/.test(path)||path==="/jobs"||path==="/jobs/resume"||path.startsWith("/jobs/chat")||path==="/rental"||path.startsWith("/rental/order/")||path==="/rental/my"||path==="/profile";
  return false;
};

const labels={user_count:"已注册用户",enterprise_count:"已注册企业",pilot_count:"已注册飞手",order_count:"订单总数",open_order_count:"进行中订单",job_count:"招募信息",open_job_count:"招聘中岗位",application_count:"面试申请",device_total:"设备总数",available_device_count:"可租设备",rental_order_count:"租赁订单",renting_device_count:"在租设备"};

async function renderAdminDashboard(){
  if(role()!=="admin"||location.pathname!=="/")return;
  const main=document.querySelector("main.main");
  if(!main||main.dataset.adminDashboard==="ready")return;
  main.dataset.adminDashboard="loading";
  main.innerHTML='<div class="admin-dashboard"><section class="admin-hero glass-panel"><p class="eyebrow">PLATFORM ADMINISTRATION</p><h1>平台管理数据</h1><p class="muted">管理员仅查看平台运营与设备基本数据，不参与发布订单、发布岗位或抢单。</p></section><p class="admin-loading">数据加载中……</p></div>';
  try{
    const response=await fetch("/api/common/admin-stats/",{headers:{Authorization:`Bearer ${localStorage.getItem("fl_token")||""}`}});
    if(!response.ok)throw new Error("管理员数据加载失败");
    const stats=await response.json();
    const dashboard=main.querySelector(".admin-dashboard");
    dashboard.querySelector(".admin-loading")?.remove();
    const section=document.createElement("section");section.className="admin-stats";
    for(const [key,label] of Object.entries(labels)){const card=document.createElement("article");card.className="admin-card glass-panel";const name=document.createElement("p");name.className="admin-label";name.textContent=label;const value=document.createElement("strong");value.className="admin-value";value.textContent=String(stats[key]??0);card.append(name,value);section.append(card)}
    dashboard.append(section);main.dataset.adminDashboard="ready";
  }catch(error){main.querySelector(".admin-loading").textContent=error.message;main.dataset.adminDashboard="error"}
}

function applyRoleVisibility(){
  const userRole=role();
  if(userRole&&!allowed(location.pathname,userRole)){location.replace("/");return}
  document.querySelectorAll('a[href^="/"]').forEach(link=>{const path=new URL(link.href,location.origin).pathname;link.hidden=!allowed(path,userRole)});
  document.querySelectorAll("button").forEach(button=>{
    const text=button.textContent.trim();
    if(text==="发布作业需求")button.hidden=userRole!=="enterprise";
    if(text==="飞手抢单大厅"||text==="抢单大厅")button.hidden=userRole!=="pilot";
  });
  renderAdminDashboard();
}

document.addEventListener("click",event=>{const link=event.target.closest('a[href^="/"]');if(link&&!allowed(new URL(link.href,location.origin).pathname)){event.preventDefault();event.stopImmediatePropagation()}},true);
window.addEventListener("popstate",applyRoleVisibility);
new MutationObserver(applyRoleVisibility).observe(document.documentElement,{subtree:true,childList:true});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",applyRoleVisibility);else applyRoleVisibility();
