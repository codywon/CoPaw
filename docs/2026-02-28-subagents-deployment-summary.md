# Subagents 功能部署总结（2026-02-28）

## 1. 本次目标
- 在 Web 控制台 `Agent` 菜单下新增 `Subagents` 页面。
- 页面支持两大能力：
  - 子代理编排配置（Config）
  - 子代理任务监控（Tasks）
- 与现有 UI/UX 风格保持一致，并支持中英文切换。
- 打通“主代理自动调度子代理”执行链路（通过工具调用）。

## 2. 变更范围

### 2.1 后端
- 新增 `agents.subagents` 配置模型（默认并发、超时、写入模式、策略等）。
- 新增子代理任务内存存储与任务模型。
- 新增 `SubagentManager`（并发/超时/状态流转控制）。
- 主代理新增 `spawn_worker` 工具注册与执行逻辑：
  - 仅主代理可用
  - 子代理禁用嵌套 spawn
  - 按 `agents.subagents` 策略构建子代理执行上下文
- 新增 API：
  - `GET /api/agent/subagents/config`
  - `PUT /api/agent/subagents/config`
  - `GET /api/agent/subagents/tasks`
  - `GET /api/agent/subagents/tasks/{task_id}`
  - `POST /api/agent/subagents/tasks/{task_id}/cancel`

### 2.2 前端
- 新增 `Agent > Subagents` 菜单与路由 `/subagents`。
- 新增 `Subagents` 页面：
  - `Config` Tab：配置读取、校验、保存、重置。
  - `Tasks` Tab：任务列表、状态筛选、轮询刷新、详情查看、任务取消。
- 新增前端 API 类型与请求模块（subagents）。

### 2.3 国际化
- 新增 `nav.subagents` 与 `subagents.*` 文案键。
- 已在 `en.json`、`zh.json` 同步添加，页面无硬编码文案。

## 3. 验证结果
- 后端定向测试：`8 passed`
  - 配置 schema 测试
  - 任务 store 测试
  - subagents 路由测试
- 前端构建：`npm run build` 通过。
- 前端定向 lint：本次新增页面与相关文件通过。
- 运行链路自检：
  - `subagents.enabled=true` 时主代理工具集中可见 `spawn_worker`
  - 子代理工具集中不可见 `spawn_worker`
- 说明：全量 `npm run lint` 仍存在仓库历史问题（非本次新增引入）。

## 4. 交付状态
- 功能代码已落地并可构建。
- 文档已补齐：
  - 设计文档
  - 实施计划
  - 本部署总结

## 5. 已知限制
- 当前任务存储为内存实现（PoC 形态），进程重启后任务记录不保留。
- 自动调度触发基于模型的工具选择（主代理会“可调用”子代理，但不保证每次都调用）。
- 任务监控已可用，但尚未与完整生产级持久化调度体系完全打通。

## 6. 风险与回滚建议
- 风险点：
  - `write_mode=direct` 配置不当可能带来路径写入风险。
  - 全量启用 MCP/Skills（`all`）会增加能力与安全面。
- 回滚建议：
  - 快速隐藏入口：移除前端 `Subagents` 菜单与路由。
  - 后端保留接口但将 `enabled=false` 作为默认降级。
  - 按提交顺序逆向回滚（先前端后后端）。

## 7. 建议后续
- 接入持久化任务存储（DB/文件）与历史查询。
- 对接真实子代理调度器状态流，完善任务详情与审计字段。
- 增加端到端回归用例与权限边界测试（路径白名单、策略校验）。
