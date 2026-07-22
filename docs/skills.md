# 核心 Skill 清单

本清单采用参赛手册附录 B 字段。所有 Skill 计划使用语义化版本并附带 Golden/Badcase 测试；当前 PoC 为 `0.1.0`。

## correlate-alerts

- **Skill 类型**：自定义 Skill。
- **使用场景**：多源告警聚合、去重和事故创建。
- **输入参数**：`Alert[]`，包含 source、service、signal、timestamp、fingerprint、value、threshold。
- **输出结果**：`Incident`、唯一信号数和告警压缩率。
- **调用条件**：接收到一个或多个有效告警。
- **依赖工具 / 系统**：告警 MCP/Adapter；PoC 使用 JSON 回放。
- **失败处理**：空输入拒绝；无法识别服务时转人工分诊。
- **权限与安全**：只读；不接触生产凭据。
- **复用价值**：适用于 Kubernetes、数据库、网关和其他 SRE 场景。

## collect-incident-evidence

- **Skill 类型**：外部工具封装。
- **使用场景**：按事故窗口采集日志、指标、Trace、变更和质量结果。
- **输入参数**：incident_id、service、time_range、evidence_types。
- **输出结果**：带来源、时间戳和不可变 ID 的 `Evidence[]`。
- **调用条件**：Incident 进入 investigating。
- **依赖工具 / 系统**：Higress、Prometheus、vLLM、OpenTelemetry、Kubernetes、模型注册中心。
- **失败处理**：部分失败保留已有证据并显式输出证据缺口；超时最多重试两次。
- **权限与安全**：只读、最小范围 Token、敏感日志脱敏。
- **复用价值**：所有根因分析 Agent 共用同一证据格式。

## rank-root-causes

- **Skill 类型**：自定义 Skill。
- **使用场景**：生成不少于两个根因假设，并对支持证据和反证对齐。
- **输入参数**：Incident、Evidence[]、服务拓扑、历史案例。
- **输出结果**：按置信度排序的 `Hypothesis[]`。
- **调用条件**：核心证据采集完成或超时。
- **依赖工具 / 系统**：Runbook RAG、事故记忆；PoC 使用确定性评分。
- **失败处理**：置信度低于 0.70 时禁止自动修复并请求补证。
- **权限与安全**：不允许无证据的确定性结论。
- **复用价值**：评分器与推理模型可替换，不改变下游契约。

## authorize-action

- **Skill 类型**：自定义治理 Skill。
- **使用场景**：执行前检查风险、白名单、可逆性、审批和幂等性。
- **输入参数**：ActionPlan、策略版本、Agent Identity、环境。
- **输出结果**：authorized/rejected/approval_required 及原因。
- **调用条件**：修复计划生成后、任何写操作之前。
- **依赖工具 / 系统**：策略库、RBAC、AgentTeams 人工协作房间。
- **失败处理**：策略不可用时 fail closed，禁止执行。
- **权限与安全**：L2 人工审批，L3 永不执行；Governor 无执行权限。
- **复用价值**：作为所有有副作用 Skill 的统一前置门禁。

## execute-safe-action

- **Skill 类型**：MCP/企业系统执行封装。
- **使用场景**：模型流量回切、灰度比例调整或受限重启。
- **输入参数**：授权令牌、ActionPlan、idempotency_key、rollback_ref。
- **输出结果**：结构化执行结果、差异和审计引用。
- **调用条件**：Safety Governor 已授权且动作在白名单。
- **依赖工具 / 系统**：Higress/Kubernetes MCP；PoC 使用模拟后端。
- **失败处理**：超时查询幂等状态；部分失败自动回滚并升级。
- **权限与安全**：短期凭据、参数范围、最小权限、禁止任意 Shell。
- **复用价值**：可支持多集群和不同流量网关适配器。

## verify-and-postmortem

- **Skill 类型**：自定义验证与知识 Skill。
- **使用场景**：修复后验证可用性、性能、质量并生成复盘。
- **输入参数**：Incident、修复前后 SLI、质量 Golden Probe、Trace。
- **输出结果**：Verification、Postmortem、Runbook Candidate。
- **调用条件**：执行完成或进入观察窗口。
- **依赖工具 / 系统**：Prometheus、质量评测、知识库。
- **失败处理**：任一硬 SLO 失败即触发回滚；知识写入失败不影响回滚。
- **权限与安全**：验证 Agent 与执行 Agent 身份隔离；知识入库前审核脱敏。
- **复用价值**：验证契约可配置，可迁移到不同 AI 服务 SLO。

