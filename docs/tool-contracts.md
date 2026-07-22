# MCP 等价工具契约

初赛 PoC 尚未部署 MCP Server，因此按参赛手册 9.2 提供等价契约。迁移时只增加协议适配层。

| 工具 | 入口 | 权限 | 幂等/重试 | 审计与降级 |
|---|---|---|---|---|
| `query_inference_metrics` | `GET /metrics/query` | 指定服务和时间窗只读 | 超时退避重试 2 次 | 记录 query hash；失败标记证据缺口 |
| `query_genai_traces` | `POST /traces/search` | 脱敏 Trace 只读 | cursor 保证分页一致 | 保存 trace_id；失败使用指标降级 |
| `get_model_deployments` | `GET /models/{service}/revisions` | 模型元数据只读 | ETag 缓存 | 保存 revision；失败禁止自动修复 |
| `shift_canary_traffic` | `POST /routes/canary` | 单服务路由写权限 | 必须 idempotency_key | 写前后比例；失败恢复旧比例 |
| `rollback_model_revision` | `POST /models/rollback` | 白名单 revision 写权限 | 必须 idempotency_key | 保存 rollback_ref；失败升级人工 |
| `run_quality_probe` | `POST /eval/golden` | 脱敏数据集执行权限 | dataset/version 固定 | 保存评测版本；失败不得关闭事故 |

鉴权计划：AgentTeams Worker 只持有 Higress consumer token，不接触真实 API Key；路由按 Identity 和 Tool 细分权限。所有写调用必须携带 incident_id、action_id、policy_version 和 idempotency_key。

