# 可验证材料

本目录用于初赛评审快速检查，不包含真实企业数据或个人信息。

- `incident.json`：一次成功自愈运行的标准化事故、证据、根因、动作、验证结果和 9 个 Trace 事件。
- `postmortem.md`：由 Recovery & Learning Agent 生成的事故复盘及 Runbook 候选。
- `test-results.txt`：自动化测试结果摘要。
- `screenshots/`：13 页已完成视觉检查的方案与 Demo 证据截图（发布 ZIP 中提供）。

复现命令：

```powershell
python -m unittest discover -s tests -v
python -m inferguard.cli demo --output artifacts/latest
```

当前版本为初赛本地 PoC。`IncidentCommander` 是 AgentTeams Manager 编排契约的确定性适配器，尚未声称运行在正式 AgentTeams 环境中。
