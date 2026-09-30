# FlyLink API 文档

启动后端后可访问：

- Swagger UI：`http://127.0.0.1:8000/api/docs/`
- OpenAPI 3 Schema：`http://127.0.0.1:8000/api/schema/`

需要认证的接口使用 JWT Bearer Token：

```http
Authorization: Bearer <access-token>
```

登录接口为 `POST /api/auth/login/`，刷新接口为
`POST /api/auth/refresh/`。

## 设备租赁兼容说明

`GET /api/rental/devices/` 仍返回旧前端使用的 `stock`、`status` 和
`depreciation` 聚合字段，但数据库内部已拆分为：

- `DroneModel`：型号、规格、日租/月租价格和押金；
- `DroneUnit`：实体序列号、可租/锁定/出租/维修/退役状态及折旧。

创建租赁订单时，`device` 参数仍传型号 ID。服务会在事务中锁定并分配一台
可用实体，订单响应额外返回 `serial_number` 与 `unit_detail`。

管理员可通过 `POST /api/rental/devices/{model_id}/units/` 增加实体，录入维修时
调用 `POST /api/rental/devices/{model_id}/maintenance/` 并提供 `unit_id`。

## 请求追踪

每个响应都包含 `X-Request-ID`。服务日志使用 JSON 行格式记录请求方法、路径、
状态码、耗时与用户 ID；客户端也可以传入自己的 `X-Request-ID` 便于跨服务追踪。
