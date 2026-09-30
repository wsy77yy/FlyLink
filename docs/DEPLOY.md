# FlyLink 飞链 — 本地部署与启动教程

## 环境要求

- Windows 10/11（已验证）/ macOS / Linux
- Python **3.10+**
- Node.js **18+**（建议 20 LTS）
- 可选：MySQL 8.x（默认使用 SQLite，无需安装数据库即可启动）

---

## 一、获取项目

项目路径：`C:\Users\yvjia\Projects\FlyLink`

```
FlyLink/
├── backend/     # Django + DRF
├── frontend/    # Vue3 + Element Plus
├── docs/        # 架构与库表设计
└── README.md
```

---

## 二、启动后端

### 1. 创建虚拟环境并安装依赖

在 **PowerShell** 中执行：

```powershell
cd C:\Users\yvjia\Projects\FlyLink\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

若执行策略拦截，先运行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. 数据库迁移 + 演示数据

```powershell
python manage.py migrate
python manage.py seed_demo
```

演示账号：

| 账号 | 密码 | 角色 |
|------|------|------|
| `enterprise1` | `demo1234` | 需求企业方 |
| `pilot1` | `demo1234` | 个人飞手 |
| `admin` | `admin123` | 平台管理员 |

### 3. 启动 API 服务

```powershell
python manage.py runserver 8000
```

访问探活：`http://127.0.0.1:8000/api/common/stats/`

接口文档：`http://127.0.0.1:8000/api/docs/`

服务输出 JSON 结构化日志，每个响应携带 `X-Request-ID`；可以通过
`LOG_LEVEL=WARNING` 等环境变量调整日志级别。

### 4. 生产环境（MySQL）

1. 创建库：`CREATE DATABASE flylink DEFAULT CHARSET utf8mb4;`
2. 设置环境变量后重启：

```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.production"
$env:DJANGO_SECRET_KEY="请替换为足够长的随机密钥"
$env:DJANGO_ALLOWED_HOSTS="flylink.example.com"
$env:CSRF_TRUSTED_ORIGINS="https://flylink.example.com"
$env:CORS_ALLOWED_ORIGINS="https://flylink.example.com"
$env:DB_NAME="flylink"
$env:DB_USER="flylink"
$env:DB_PASSWORD="你的密码"
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
python manage.py migrate
python manage.py seed_demo
python manage.py migrate
# 使用生产级 WSGI 服务启动 config.wsgi:application
```

本地命令默认使用 `config.settings.local`（SQLite、调试模式）；部署入口使用
`config.settings.production`（MySQL、安全 Cookie、HTTPS/HSTS）。可复制仓库根目录
`.env.example` 准备生产环境变量，生产配置缺少密钥或域名时会直接拒绝启动。

---

## 三、启动前端

新开一个终端：

```powershell
cd C:\Users\yvjia\Projects\FlyLink\frontend
npm install
npm run dev
```

浏览器打开：`http://127.0.0.1:5173`

前端已通过 Vite 代理将 `/api` 转发到 `http://127.0.0.1:8000`。

生产构建：

```powershell
npm run build
```

产物在 `frontend/dist/`。

---

## 四、标准演示路径（模块一）

1. 用 `enterprise1` 登录 → **需求发单** 分步发布订单  
2. 退出后用 `pilot1` 登录 → **抢单大厅** → 一键接单  
3. 订单详情：申报飞行计划 → 开始作业 → 上传轨迹/素材 → 提交验收  
4. 切回企业账号 → 验收结算 → 双方互评  

模块二：企业发岗 → 飞手投递/简历 → IM 沟通 → 签约 → 入职中介费  
模块三：设备货架 → 步骤条下单 → 信用免押/保险 → 归还核验  

---

## 五、前端美化相关文件位置

| 文件 | 作用 |
|------|------|
| `frontend/src/styles/theme.css` | 深空蓝+淡青设计系统、滚动条、毛玻璃、过渡动画 |
| `frontend/src/layouts/MainLayout.vue` | 固定悬浮顶栏、Logo、响应式抽屉导航 |
| `frontend/src/views/home/HomeView.vue` | 可视化大屏首页与数据卡片动效 |
| `frontend/src/views/orders/*` | 分步发单、卡片抢单、订单管控页 |
| `frontend/src/views/jobs/*` | 岗位卡片、折叠简历、IM/签约 |
| `frontend/src/views/rental/*` | 设备网格商城、租赁步骤条 |
| `frontend/index.html` | Orbitron + Noto Sans SC 字体 |

业务 API 未改动，仅样式/布局/动效升级。

---

## 六、常见问题

**1. `npm` 不是内部命令**  
安装 Node.js LTS 并重新打开终端。

**2. 登录 401 / 跨域**  
确认后端 `runserver 8000` 已启动，前端走 `5173` 代理，不要直接打开 `dist` 的 file 协议。

**3. 注册密码复杂度报错**  
Django 默认校验：避免纯数字、过短，可用 `Demo1234`。

**4. PowerShell 无法激活 venv**  
使用 `cmd`：`backend\.venv\Scripts\activate.bat`
