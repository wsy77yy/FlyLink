const labels={user_count:"已注册用户",enterprise_count:"已注册企业",pilot_count:"已注册飞手",order_count:"订单总数",open_order_count:"进行中订单",job_count:"招募信息",open_job_count:"招聘中岗位",application_count:"面试申请",device_total:"设备总数",available_device_count:"可租设备",rental_order_count:"租赁订单",renting_device_count:"在租设备"};

function getUser(){try{return JSON.parse(localStorage.getItem("fl_user")||"null")}catch{return null}}
function logout(){localStorage.removeItem("fl_token");localStorage.removeItem("fl_user");location.replace("/login")}

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
  }catch(error){const status=document.querySelector("#admin-status");status.className="admin-error";status.textContent=error.message}
}

document.querySelector("#logout").addEventListener("click",logout);
loadDashboard();
