# InferGuard DataOps

**A context-aware, reversible multi-agent incident response system powered by DataHub.**

InferGuard DataOps correlates noisy DataOps alerts, retrieves trusted metadata and lineage through the DataHub MCP Server, ranks evidence-backed root causes, proposes a reversible remediation, verifies recovery against explicit SLOs, and writes an auditable postmortem.

This branch is the DataHub Agent Hackathon implementation. DataHub is part of the reasoning path: the Data Context Analyst calls `search`, `get_entities`, and `get_lineage` to identify the failing asset, its owner, the changed upstream producer, and the downstream blast radius.

## DataHub demo

Run the reproducible scenario without credentials:

```powershell
python -m unittest discover -s tests -v
python -m inferguard.cli demo `
  --scenario scenarios/datahub_customer_features_schema_break.json `
  --datahub-mode fixture `
  --output artifacts/datahub-latest
```

The scenario replays a breaking `raw_orders` schema rename that causes a customer feature pipeline to fail. DataHub context connects the producer change to the failed dataset and exposes the churn model and retention dashboard in the downstream blast radius.

For a real DataHub Core or DataHub Cloud instance, install the optional MCP client and run the same scenario in live mode:

```powershell
pip install -e ".[datahub]"
$env:DATAHUB_GMS_URL = "http://localhost:18080"
$env:DATAHUB_GMS_TOKEN = "<personal-access-token>"
python -m inferguard.cli demo `
  --scenario scenarios/datahub_customer_features_schema_break.json `
  --datahub-mode mcp `
  --output artifacts/datahub-live
```

Live mode starts the official `mcp-server-datahub` process and records every MCP tool name, argument, result, and resulting decision in `incident.json`. Secrets are passed only through environment variables and are never written to incident artifacts.

See [DataHub integration](docs/datahub-integration.md) for the architecture, safety boundary, and live setup.

## 原始 InferGuard 能力

**面向 AI 推理服务的可验证、可回滚零人工运维多 Agent 系统。**

InferGuard 将网关、推理引擎、GPU、Kubernetes、Trace 和质量探针的信号归并为一个事故，由不同职能 Agent 完成证据收集、根因排序、策略授权、安全修复、独立恢复验证和事故复盘。系统不会把“命令执行成功”等同于“服务恢复成功”；只有性能、可用性和回答质量 SLO 同时通过，事故才会关闭。

当前版本是可验证 PoC：零外部依赖、零云密钥，使用确定性仿真工具跑通完整链路。工具边界与未来 MCP Server 保持一致，后续可替换为 Higress、vLLM、Prometheus、Kubernetes 和 AgentLoop。

## 原始推理服务 Demo

场景：`qwen-serving-v2` 灰度版本把 `max_model_len` 从 8192 提升到 32768，KV Cache 达到 99%，导致请求抢占、TTFT 和 5xx 激增。系统确认 GPU 硬件正常、质量没有退化，并将失败 Trace 与 v2 路由对齐后，按策略回切灰度流量至 v1；最后验证错误率、TTFT 和质量分数。

```powershell
python -m unittest discover -s tests -v
python -m inferguard.cli demo --output artifacts/latest
```

运行后生成：

- `artifacts/latest/incident.json`：结构化事故状态、证据、决策与完整 Trace。
- `artifacts/latest/postmortem.md`：事故复盘和可复用 Runbook 草稿。

## AgentTeams 映射

| InferGuard | AgentTeams | 协作职责 |
|---|---|---|
| Incident Commander | Manager | 拆解事故任务、分派 Worker、维护状态并决定闭环或升级 |
| Signal Analyst | Worker | 多源告警归并和影响面识别 |
| RCA Investigator | Worker | 查询证据、生成并排序根因假设 |
| Safety Governor | Worker | 风险分级、白名单、审批与回滚条件校验 |
| Remediation Executor | Worker | 执行参数化、幂等、可回滚动作 |
| Recovery & Learning | Worker | 独立验证恢复、生成复盘并沉淀 Runbook |

正式 AgentTeams 运行时中，结构化 Incident State 作为共享文件/状态在 Manager 与 Workers 间传递；协作消息进入 Matrix 房间，工具凭据通过 Higress AI Gateway 隔离，任务和证据可由人实时观察与介入。当前本地 `IncidentCommander` 是同一编排契约的确定性适配器，不冒充正式 AgentTeams 运行时。

## 安全模型

- L0：只读采集与诊断，自动执行。
- L1：低风险、白名单、可逆动作，允许自动执行。
- L2：灰度配置或扩大影响面的动作，必须人工批准。
- L3：删除数据、不可逆变更等，只生成建议，禁止执行。

执行前必须具备白名单动作、幂等键、参数边界和回滚动作。恢复验证由不同 Agent 完成；验证失败触发自动回滚。

## 项目结构

```text
inferguard/                  核心领域模型、Agents、Skills 与编排
scenarios/                   可回放事故数据集
tests/                       闭环和安全边界测试
docs/                        参赛方案、Identity、Skill 与接口契约
artifacts/                   可复现运行证据（默认不提交生成物）
```

## 开放计划

计划以 Apache-2.0 开放 Agent Identity、Skill 契约、MCP 工具 Schema、仿真事故数据集、评测脚本和部署说明。仿真数据为团队原创，不含真实用户数据、企业日志或个人信息。
