# CoPaw 多实例/多 Agent 协作编排设计报告（主代理统一调度）

## 1. 背景与目标

当前 CoPaw 运行模型为“单会话单 Agent 推理循环”。本设计目标是在保持现有主流程稳定的前提下，增加“主代理调度多个可写从代理（Subagents）”能力，用于并行处理复杂任务（如爬虫、批量改文件、长时间视频生成等）。

本报告是 PoC（Proof of Concept）级别设计：优先验证架构可行性、隔离性与可观测性，再逐步产品化。

## 2. 需求基线（已确认）

1. 主代理统一调度其他代理（非平级协商）。
2. 从代理支持可写执行（可写文件、可执行命令）。
3. `web_search/fetch` 默认开启。
4. `MCP`、`Skill` 可配置（none/selected/all）。
5. 并发上限默认 5，且可配置。
6. 超时可配置，10 分钟过短；需支持长任务。
7. 默认仅允许 workspace，支持额外目录白名单。

## 3. 参考实现与设计借鉴

参考 `D:\myscript\nanobot` 已验证模式：

- `SpawnTool`：主代理工具触发从代理任务。
- `SubagentManager`：负责并发、超时、生命周期。
- 异步结果回传：从代理完成后将结果注入主代理消息流，再由主代理统一回复。

借鉴点保留，框架适配 CoPaw 现有结构（`CoPawAgent` + `AgentRunner` + `ChannelManager`）：

- 不重写主推理框架，采用“工具扩展 + 管理器 + 事件注入”的最小侵入方式。
- 从代理仍复用 CoPaw 工具链与模型工厂，减少重复实现。

## 4. 非目标（PoC 阶段）

1. 不做跨机器分布式调度（先单实例内多从代理）。
2. 不做完整前端可视化调度面板（先提供 API/日志）。
3. 不做自动合并冲突 UI（先可回退、可审计）。

## 5. 总体架构

### 5.1 组件

- **Main Agent（已有）**：接收用户请求，决定是否调用 `spawn_worker`。
- **Spawn Worker Tool（新增）**：从主代理触发子任务。
- **SubagentManager（新增）**：维护任务队列、并发池、超时、回传。
- **Subagent Worker（新增）**：受限能力的从代理执行器（独立上下文）。
- **Subagent Event Store（新增）**：保存任务状态（queued/running/success/error/timeout）。
- **Runner 回传桥（改造）**：将从代理结果投递给主会话，最终由主代理统一表达。

### 5.2 执行模式

- `write_mode = worktree`（默认，推荐）
  - 每个从代理在独立 worktree 执行，避免主工作区直接污染。
  - 主代理汇总从代理结果并决定是否应用。
- `write_mode = direct`（可选）
  - 直接对目标目录写入。
  - 必须通过 `allowed_paths` 白名单校验。

## 6. 配置设计

在 `config.json` 中扩展 `agents.subagents`：

```json
{
  "agents": {
    "subagents": {
      "enabled": true,
      "max_concurrency": 5,
      "default_timeout_seconds": 3600,
      "hard_timeout_seconds": 10800,
      "write_mode": "worktree",
      "allow_nested_spawn": false,
      "allowed_paths": ["<workspace>"],
      "tools": {
        "default_enabled": [
          "read_file",
          "write_file",
          "edit_file",
          "execute_shell_command",
          "web_search",
          "web_fetch"
        ]
      },
      "mcp_policy": "selected",
      "mcp_selected": [],
      "skills_policy": "selected",
      "skills_selected": []
    }
  }
}
```

### 6.1 关键策略

1. `allow_nested_spawn=false`：防止从代理递归拉起更多代理。
2. `default_timeout_seconds` 与 `hard_timeout_seconds`：支持长任务但防止失控。
3. `allowed_paths`：路径白名单。默认仅 workspace，按需增加。

## 7. 数据结构与状态机

### 7.1 任务实体

`SubagentTask` 字段建议：

- `task_id`
- `parent_session_id`
- `origin_user_id`
- `origin_channel`
- `status` (`queued|running|success|error|timeout|cancelled`)
- `task_prompt`
- `worker_profile`
- `write_mode`
- `allowed_paths`
- `start_at/end_at`
- `result_summary`
- `artifacts`（文件/日志/可选 diff）
- `error_message`

### 7.2 状态流转

`queued -> running -> success|error|timeout|cancelled`

所有状态变化写入事件存储，便于 API 查询与后续 UI 对接。

## 8. 主从消息流

1. 用户请求进入主代理。
2. 主代理调用 `spawn_worker(task, label?, timeout?, profile?)`。
3. `SubagentManager` 校验并入队。
4. 并发池调度从代理执行任务。
5. 从代理执行结束，产出 `SubagentResult`。
6. 结果通过 Runner 回传到主会话（内部系统消息或事件）。
7. 主代理读取结果并向用户输出整合后回复。

## 9. 安全与权限模型

### 9.1 文件与命令权限

- 默认强隔离：`worktree` + workspace 限制。
- `direct` 模式启用时：
  - 必须校验路径在 `allowed_paths` 内。
  - 记录文件变更审计（task_id、路径、时间）。
  - 禁止越权路径（绝对路径逃逸、符号链接逃逸需防护）。

### 9.2 工具权限

- 主代理与从代理工具集拆分。
- 从代理默认不开放：发送用户消息、再次 spawn、敏感管理工具。
- `MCP/Skill` 按策略加载：
  - `none`：全部禁用
  - `selected`：白名单
  - `all`：全部启用（高风险，建议仅受信环境）

## 10. 可观测性与运维

### 10.1 日志与指标

- 任务日志：创建、启动、结束、超时、失败原因。
- 指标建议：
  - `subagent_tasks_total`
  - `subagent_running`
  - `subagent_queue_length`
  - `subagent_success_rate`
  - `subagent_timeout_rate`
  - `subagent_avg_duration_ms`

### 10.2 API（PoC 最小集）

- `GET /api/agent/subagents/tasks`（列表）
- `GET /api/agent/subagents/tasks/{id}`（详情）
- `POST /api/agent/subagents/tasks/{id}/cancel`（取消）

## 11. 风险与缓解

1. 长任务占满并发池  
  缓解：分级超时、队列监控、取消能力。

2. 多从代理写同一文件冲突  
  缓解：默认 worktree；direct 模式下文件锁与冲突检测。

3. 工具能力过强导致误操作  
  缓解：默认最小权限 + 路径白名单 + 禁止嵌套 spawn。

4. 主代理输出质量下降  
  缓解：结果回传模板标准化（摘要、证据、产物路径）。

## 12. 分阶段落地建议

### Phase 1（PoC）

- 单实例内多从代理。
- 工具可写 + web_search/fetch。
- 并发/超时/路径白名单可配置。
- API 查询任务状态。

### Phase 2（稳定化）

- worktree 生命周期管理增强。
- 冲突检测/自动重试策略。
- 更细粒度权限模型（按 profile）。

### Phase 3（产品化）

- 前端任务面板。
- 跨实例调度（可选，后续扩展）。

## 13. 结论

采用“主代理统一调度 + SubagentManager + 默认 worktree 隔离 + 配置化权限”的方案，能够在较小改动下把 CoPaw 从单 Agent 扩展到可控的多 Agent 协作编排，并与 nanobot 已验证模式保持一致的工程可行性。

