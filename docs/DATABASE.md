# FlyLink 飞链 — 数据库表设计

> 本地开发默认 SQLite；生产推荐 MySQL 8.x，字符集 `utf8mb4`。

## 角色枚举

- `enterprise` 需求企业方
- `pilot` 个人飞手
- `admin` 平台管理员

---

## 1. 用户与信用（users）

### user_account（用户账号）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | |
| username | VARCHAR(64) UNIQUE | 登录名 |
| password | VARCHAR(128) | 哈希密码 |
| role | VARCHAR(20) | enterprise/pilot/admin |
| phone | VARCHAR(20) | |
| email | VARCHAR(128) | |
| avatar | VARCHAR(255) | |
| is_active | BOOL | |
| credit_score | INT | 信用分 300-1000（数据库约束） |
| created_at / updated_at | DATETIME | |

### enterprise_profile（企业资料）

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | FK → user | |
| company_name | VARCHAR(128) | |
| license_no | VARCHAR(64) | 营业执照号 |
| contact_name | VARCHAR(64) | |
| address | VARCHAR(255) | |
| verified | BOOL | 认证状态 |

### pilot_profile（飞手资料）

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | FK → user | |
| real_name | VARCHAR(64) | |
| license_level | VARCHAR(32) | 执照等级 CAAC 等 |
| years_exp | INT | 实操年限 |
| offline_status | VARCHAR(20) | idle/busy/offline |
| lat / lng | DECIMAL | 当前位置 |
| skills | JSON | 擅长标签 |
| verified | BOOL | |

### pilot_resume（飞手电子简历）

| 字段 | 类型 | 说明 |
|------|------|------|
| pilot_id | FK | |
| summary | TEXT | |
| projects | JSON | 过往项目案例 |
| portfolio | JSON | 作品集 URL 列表 |
| education | TEXT | |

### credit_review（双向评价）

| 字段 | 类型 | 说明 |
|------|------|------|
| from_user_id / to_user_id | FK | |
| biz_type | VARCHAR(20) | order/job |
| biz_id | BIGINT | |
| score | INT 1-5 | |
| tags | JSON | |
| content | TEXT | |

---

## 2. 模块一：次结商单（orders）

### work_order（作业订单）

| 字段 | 类型 | 说明 |
|------|------|------|
| order_no | VARCHAR(32) UNIQUE | |
| enterprise_id | FK | 发单企业 |
| pilot_id | FK NULL | 接单飞手 |
| work_type | VARCHAR(20) | plant/inspect/aerial/survey |
| location / lat / lng | | 作业地点 |
| execute_time | DATETIME | |
| area_or_duration | VARCHAR(64) | 面积/时长 |
| budget | DECIMAL(12,2) | 100.00-9,999,999,999.99 |
| license_req | VARCHAR(64) | 资质硬性要求 |
| urgent | BOOL | 紧急标识 |
| status | VARCHAR(20) | pending/matched/accepted/declared/working/submitted/accepted_done/settled/cancelled |
| match_radius_km | FLOAT | |
| assigned_by_admin | BOOL | 是否平台指派 |
| platform_fee_rate | DECIMAL | 抽成比例 |
| escrow_amount | DECIMAL | 托管金额 |
| actual_area | DECIMAL | 实测面积 |
| created_at | DATETIME | |

### order_match_log（匹配推送日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | FK | |
| pilot_id | FK | |
| distance_km | FLOAT | |
| score | FLOAT | 综合匹配分 |
| pushed_at | DATETIME | |

### flight_plan（飞行计划申报）

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | FK ONE | |
| plan_content | JSON/TEXT | 自动填充材料 |
| declare_status | VARCHAR(20) | draft/submitted/approved |
| external_ref | VARCHAR(64) | 空域接口回执 |

### work_track（GPS 轨迹）

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | FK | |
| lat / lng / altitude | DECIMAL | |
| recorded_at | DATETIME | |

### work_media（作业素材）

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | FK | |
| media_type | VARCHAR(10) | image/video |
| url | VARCHAR(255) | |
| uploaded_at | DATETIME | |

### settlement（担保结算）

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | FK ONE | |
| total_amount | DECIMAL | |
| platform_fee | DECIMAL | |
| pilot_income | DECIMAL | |
| status | VARCHAR(20) | holding/paid/refunded |
| paid_at | DATETIME | |

---

## 3. 模块二：长期招聘（jobs）

### job_post（岗位）

| 字段 | 类型 | 说明 |
|------|------|------|
| enterprise_id | FK | |
| title | VARCHAR(128) | |
| job_type | VARCHAR(20) | fulltime/parttime |
| location | VARCHAR(255) | |
| salary_min / salary_max | INT | 各 3,000-1,000,000，且最高薪资不得低于最低薪资 |
| license_req | VARCHAR(64) | |
| benefits | TEXT | |
| responsibilities | TEXT | |
| tags | JSON | |
| status | VARCHAR(20) | open/closed |

### job_application（投递/推荐）

| 字段 | 类型 | 说明 |
|------|------|------|
| job_id / pilot_id | FK | |
| match_score | FLOAT | AI 匹配分 |
| status | VARCHAR(20) | recommended/applied/interview/offered/hired/rejected |
| source | VARCHAR(20) | self/ai |

### chat_message（IM 私聊）

| 字段 | 类型 | 说明 |
|------|------|------|
| application_id | FK | |
| sender_id | FK | |
| content | TEXT | |
| msg_type | VARCHAR(20) | text/interview_invite |
| created_at | DATETIME | |

### labor_contract（电子合同）

| 字段 | 类型 | 说明 |
|------|------|------|
| application_id | FK | |
| contract_url | VARCHAR(255) | |
| signed_enterprise | BOOL | |
| signed_pilot | BOOL | |
| onboarded_at | DATETIME | |

### agency_fee（中介费）

| 字段 | 类型 | 说明 |
|------|------|------|
| application_id | FK | |
| fee_rate | DECIMAL | |
| amount | DECIMAL | |
| status | VARCHAR(20) | pending/paid |

---

## 4. 模块三：设备租赁（rental）

### drone_device（设备台账）

| 字段 | 类型 | 说明 |
|------|------|------|
| model_name | VARCHAR(128) | |
| specs | JSON | 参数 |
| daily_price / monthly_price | DECIMAL | |
| deposit | DECIMAL | |
| stock | INT | |
| status | VARCHAR(20) | available/rented/maintaining |
| depreciation | DECIMAL | 折旧 |
| cover_image | VARCHAR(255) | |

### maintenance_record（维保记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| device_id | FK | |
| content | TEXT | |
| cost | DECIMAL | |
| maintained_at | DATETIME | |

### rental_order（租赁订单）

| 字段 | 类型 | 说明 |
|------|------|------|
| order_no | VARCHAR(32) | |
| user_id / device_id | FK | |
| start_date / end_date | DATE | 合法自然日，结束日期不得早于开始日期；接口自动返回对应星期 |
| delivery_type | VARCHAR(20) | pickup/express |
| deposit_paid | DECIMAL | |
| deposit_waived | BOOL | 信用免押 |
| insurance_fee | DECIMAL | 强制保险 |
| rent_amount | DECIMAL | |
| status | VARCHAR(20) | pending_pay/renting/returning/settled/cancelled |
| damage_fee | DECIMAL | 损坏扣款 |
| credit_score_snapshot | INT | |

### rental_history（租借历史）— 可与 rental_order 复用查询，或独立日志表。

---

## 5. ER 关系简图

```
user ─┬─ enterprise_profile
      ├─ pilot_profile ─ pilot_resume
      └─ credit_review

enterprise ─ work_order ─┬─ flight_plan
                         ├─ work_track / work_media
                         ├─ settlement
                         └─ order_match_log ─ pilot

enterprise ─ job_post ─ job_application ─┬─ chat_message
                                         ├─ labor_contract
                                         └─ agency_fee

drone_device ─┬─ maintenance_record
              └─ rental_order ─ user
```
