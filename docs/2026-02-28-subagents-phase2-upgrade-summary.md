# CoPaw 子代理二阶段升级总结（2026-02-28）

## 1. 本次升级目标

本次在既有 `Subagents` 基础上，完成以下能力闭环：

1. 主代理强制调度策略（可配置）。
2. 子代理角色化（身份/工具指南/路由关键词）。
3. 全局并发控制（跨实例生效）。
4. 任务执行模式可选：`sync` / `async`。
5. 异步队列执行、失败重试、级联取消。
6. 前端配置页与任务监控页同步增强（中英文文案支持）。

## 2. 核心后端改动

### 2.1 配置模型扩展

`SubagentsConfig` 新增关键字段：

1. `dispatch_mode`: `advisory | force_when_matched | force_by_default`
2. `auto_dispatch_keywords`
3. `auto_dispatch_min_prompt_chars`
4. `execution_mode`: `sync | async`
5. `retry_max_attempts`
6. `retry_backoff_seconds`
7. `role_selection_mode`: `auto | default`
8. `default_role`
9. `roles[]`（角色配置列表）

角色模型 `SubagentRoleConfig` 支持：

1. 身份与行为：`identity_prompt`, `tool_guidelines`
2. 路由：`routing_keywords`
3. 工具白名单：`tool_allowlist`
4. 角色级策略：`mcp_policy/skills_policy` 及 `selected` 列表
5. 角色级超时：`timeout_seconds`

### 2.2 调度策略与角色路由

新增策略模块：

1. `should_force_dispatch(...)`：判定是否强制分流。
2. `select_role_for_task(...)`：按 `profile`、关键词、默认角色选路由角色。

### 2.3 子代理执行器升级（Manager）

`SubagentManager` 新增与强化：

1. `submit_task(...)`：异步入队，立即返回 `queued` 任务快照。
2. `run_task(...)`：同步执行并等待完成。
3. 重试逻辑：`retry_max_attempts + retry_backoff_seconds`。
4. 运行任务表：可取消运行中的后台任务。
5. 级联取消：`cancel_task_tree(...)` / `cancel_task_tree_for_store(...)`。
6. 全局并发：共享 semaphore，跨主代理实例生效。

### 2.4 任务存储与模型增强

任务模型新增：

1. `role_key`
2. `dispatch_reason`
3. `parent_task_id`
4. `attempts`
5. `max_attempts`

任务存储新增：

1. 父子任务关系索引（children map）
2. `set_attempt(...)`
3. `get_descendant_task_ids(...)`

### 2.5 主代理链路接入

`CoPawAgent` 的 `spawn_worker` 与 `reply` 已接入：

1. `dispatch_mode` 强制分流判定。
2. 角色解析与角色策略继承/覆盖。
3. `execution_mode=async` 时入队返回 `task_id`。
4. `execution_mode=sync` 时保留“等待结果”语义。
5. 任务摘要中返回 `role` 与 `dispatch_reason` 便于审计。

### 2.6 API 行为变化

1. `PUT /api/agent/subagents/config`：
   - 增加角色与自动调度字段校验。
   - `default_role` 必须属于 `roles`。
   - `role.key` 必须唯一。
2. `POST /api/agent/subagents/tasks/{task_id}/cancel`：
   - 改为级联取消父任务及其后代任务。

## 3. 前端改动（Subagents 页面）

页面结构：

1. `Config`：全局调度、执行模式、重试与策略配置。
2. `Roles`：角色新增/编辑/删除，包含身份与工具指南配置。
3. `Tasks`：任务监控新增 `role`、`dispatch_reason` 展示。

新增配置项展示：

1. `execution_mode`
2. `retry_max_attempts`
3. `retry_backoff_seconds`

i18n：

1. `en.json` / `zh.json` 已补齐对应文案键。
2. 保持与现有 UI 样式一致，不引入新视觉体系。

## 4. 测试与验证结果

后端测试：

1. 新增/更新了配置、策略、store、manager、router 相关测试。
2. 覆盖点包括：
   - 强制调度判定
   - 角色路由
   - 异步入队执行
   - 重试成功
   - 父子级联取消
   - 路由层级联取消接口行为
3. 结果：`20 passed`（存在既有 pytest 配置 warning，不影响通过）。

前端验证：

1. `npm run build` 通过。

## 5. 默认值与建议

当前默认：

1. `execution_mode = sync`
2. `max_concurrency = 5`
3. `retry_max_attempts = 1`
4. `retry_backoff_seconds = 0`

说明：

1. 默认 `sync` 是兼容优先，避免当前链路行为突变。
2. 若追求 OpenClaw/Cowork 风格生产实践，建议将默认切换为 `async`。

## 6. 后续建议（下一阶段）

1. 将异步任务状态持久化到磁盘/数据库（当前为内存态）。
2. 增加任务重启恢复机制（进程重启后恢复队列）。
3. 支持任务事件流（SSE/WebSocket）代替轮询。
4. 增加角色级并发配额（全局并发之上再做角色限流）。
5. 增加失败告警与自动熔断策略。

