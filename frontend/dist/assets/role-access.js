const currentUser=()=>{try{return JSON.parse(localStorage.getItem("fl_user")||"null")}catch{return null}};
const role=()=>currentUser()?.role||"";
const allowed=(path,userRole=role())=>{
  if(!userRole)return path==="/"||path==="/jobs"||path==="/rental"||path==="/login"||path==="/register";
  if(userRole==="admin")return path==="/"||path==="/admin-dashboard.html"||path==="/profile";
  if(userRole==="enterprise")return path==="/"||path==="/orders/publish"||path.startsWith("/orders/")&&!path.startsWith("/orders/hall")||path==="/jobs"||path==="/jobs/publish"||path.startsWith("/jobs/chat")||path==="/rental"||path.startsWith("/rental/order/")||path==="/rental/my"||path==="/profile";
  if(userRole==="pilot")return path==="/"||path==="/orders/hall"||/^\/orders\/\d+/.test(path)||path==="/jobs"||path==="/jobs/resume"||path.startsWith("/jobs/chat")||path==="/rental"||path.startsWith("/rental/order/")||path==="/rental/my"||path==="/profile";
  return false;
};

function applyRoleVisibility(){
  const userRole=role();
  document.body.classList.toggle("fl-role-pilot",userRole==="pilot");
  document.body.classList.toggle("fl-role-enterprise",userRole==="enterprise");
  if(userRole==="admin"&&location.pathname==="/"){location.replace("/admin-dashboard.html");return}
  if(userRole&&!allowed(location.pathname,userRole)){location.replace("/");return}
  document.querySelectorAll('a[href^="/"]').forEach(link=>{const path=new URL(link.href,location.origin).pathname;link.hidden=!allowed(path,userRole)});
  document.querySelectorAll("button").forEach(button=>{
    const text=button.textContent.trim();
    if(text==="发布作业需求")button.hidden=userRole!=="enterprise";
    if(text==="飞手抢单大厅"||text==="抢单大厅")button.hidden=true;
  });
  if(userRole==="pilot"){
    const menu=document.querySelector("nav.menu");
    if(menu&&!menu.querySelector('[data-role-link="pilot-orders"]')){
      const orderLink=document.createElement("a");
      orderLink.href="/orders/hall";
      orderLink.textContent="抢单大厅";
      orderLink.dataset.roleLink="pilot-orders";
      orderLink.setAttribute("data-v-13da54f5","");
      if(location.pathname==="/orders/hall")orderLink.classList.add("router-link-active");
      menu.prepend(orderLink);
    }
    document.querySelectorAll('a[href="/jobs"]').forEach(link=>{if(link.textContent!=="招募大厅")link.textContent="招募大厅"});
  }
}

document.addEventListener("click",event=>{const link=event.target.closest('a[href^="/"]');if(link&&!allowed(new URL(link.href,location.origin).pathname)){event.preventDefault();event.stopImmediatePropagation()}},true);
window.addEventListener("popstate",applyRoleVisibility);
new MutationObserver(applyRoleVisibility).observe(document.documentElement,{subtree:true,childList:true});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",applyRoleVisibility);else applyRoleVisibility();
