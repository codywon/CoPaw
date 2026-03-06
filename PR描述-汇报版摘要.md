# CoPaw 相对上游改动 PR 描述 / 汇报版摘要

## PR 标题建议

`feat: extend CoPaw for enterprise-ready multi-agent, multi-bot, multi-channel operations`

## 一句话摘要

本次改动在上游 CoPaw 基础上，补齐了部署稳健性、MCP/Provider 接入、多智能体编排、多 Bot Profile、多 Channel 实例、定时任务精确投递和输出可见性控制等能力，使其从通用 Agent 框架进一步演进为更适合真实业务场景的可运营平台。

## 背景

- 上游 CoPaw 更偏通用 Agent 容器与开发者工具形态。
- 当前分支围绕真实业务落地，重点解决“能长期稳定运行、能支持多角色协作、能承载多个 Bot/渠道、能控制对外输出”的问题。
- 当前分支相对 `origin/main` 超前 `27` 个提交。

## 本次改动概览

### 1. 基础设施与部署稳健性增强

- 修复工作目录、环境初始化与配置持久化问题。
- 增强 Docker 部署可用性，支持容器重启后保留配置。
- 统一端口配置来源，优化 CLI 默认监听地址，支持局域网访问。
- 调整依赖与启动行为，降低本地与 CI 环境的不稳定性。

**价值：** 让系统从“能跑”提升到“能稳定跑、能持续维护”。

### 2. MCP 与 Provider 生态增强

- 为 MCP 增加 `SSE` 和 `Streamable HTTP` 传输支持。
- 强化 `headers`、`env`、`base_url` 等配置项校验。
- 内建 `OpenAI` 与 `Azure OpenAI` Provider。
- 对 MCP 配置路由与前端交互进行了对齐和加固。

**价值：** 提高模型与外部工具接入的兼容性、稳定性与开箱即用程度。

### 3. 多智能体 `Subagents` 编排能力

- 新增 `subagents` 相关后端模块、路由、任务存储、策略与队列能力。
- 支持角色模型策略、任务事件与基础监控能力。
- 提供控制台页面用于配置和查看多智能体相关能力。
- 配套补充了设计文档、实施计划与测试用例。

**价值：** 将单 Agent 响应模式扩展为可分工、可编排、可监控的多角色工作流。

### 4. 多 Bot Profile 与会话隔离

- 新增 `BotProfilesConfig`、`BotProfileConfig` 与 `channel_bindings`。
- 支持为不同 Bot 配置独立身份、描述和 `identity_prompt`。
- 支持聊天页切换 Bot，并将 `bot_id` 透传到 session/meta。
- 为不同 Bot 提供会话命名空间隔离，降低上下文串线风险。

**价值：** 一套平台可承载多个业务身份，如销售 Bot、运营 Bot、客服 Bot 等。

### 5. 多 Channel 实例管理

- 突破“一个渠道类型只能有一个实例”的限制。
- 新增 channel instance 的列表、详情、创建/编辑、删除接口。
- 支持同一 `channel_type` 运行多个实例。
- 控制台新增 channel instance 管理能力。

**价值：** 支持同类渠道多账号、多业务线、多入口接入，是平台化运营的重要前提。

### 6. 输出可见性控制：`show_tool_details` + `show_reasoning`

- 在已有工具详情控制基础上，新增 `show_reasoning` 全局开关。
- Channel、Renderer、Watcher、Config Router 全链路支持该开关。
- 支持在不同渠道中隐藏内部推理内容，仅保留面向用户的最终结果。

**价值：** 兼顾调试可见性与对外输出控制，更适合真实用户场景与合规要求。

### 7. Cron 定时任务精确投递

- 增强定时任务保存时的目标绑定与严格投递逻辑。
- 补充 targeting、executor、API 和前端联动能力。

**价值：** 让定时任务不仅“按时执行”，还能“准确发送到正确目标”。

### 8. 技能系统治理与业务技能沉淀

- 修复技能列表去重逻辑：`customized` 技能覆盖同名 `builtin` 技能。
- 删除自定义技能后，可自动恢复同名内建技能到激活目录。
- 增加技能 frontmatter 校验测试。
- 新增 `wechat-content-ops` 业务技能，面向公众号内容运营流程。

**价值：** 把技能从零散 Prompt 片段提升为可治理、可复用、可沉淀的业务资产。

## 主要收益

- 提升部署稳定性与环境兼容性。
- 提升多模型、多工具、多渠道接入能力。
- 支持从单 Agent 升级为多角色协同系统。
- 支持一套平台同时管理多个 Bot 与多个渠道入口。
- 支持更细粒度的输出控制，降低对外暴露内部过程的风险。
- 为企业化、平台化、长期运营打下更扎实的基础。

## 风险与注意事项

- 当前工作区仍存在部分未提交文件与本地运行产物，如 `.home/`、`.xhs/`、`sync-conflict` 副本等，建议在正式 PR 前清理。
- 本轮改动跨度较大，建议按“基础设施 / MCP&Provider / Subagents / 多 Bot&多 Channel”四条主线拆分审阅。
- `Bot Profiles`、`Channel Instances`、`show_reasoning` 当前仍有一部分属于本地未提交工作，建议在最终合并前继续收口与补齐回归验证。

## 建议评审顺序

1. 基础设施与部署相关改动
2. MCP / Provider 相关改动
3. `Subagents` 核心编排能力
4. `Bot Profiles` 与 `Channel Instances`
5. 渲染控制、Cron、Skill 管理与测试补充

## 汇报版结论

如果用一句更偏汇报的话来概括：

**这轮改造的核心不是单点功能增强，而是把上游 CoPaw 从通用 Agent 框架，推进为一个更适合企业场景的多智能体、多 Bot、多渠道、可治理、可运营的平台底座。**
