import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
} from "antd";
import type { TableColumnsType, TabsProps } from "antd";
import { useTranslation } from "react-i18next";
import api from "../../../api";
import type {
  MCPClientInfo,
  SkillSpec,
  SubagentRoleConfig,
  SubagentTask,
  SubagentTaskStatus,
  SubagentsConfig,
} from "../../../api/types";
import styles from "./index.module.less";

type PaginationState = {
  page: number;
  pageSize: number;
};

const DEFAULT_TASK_POLL_INTERVAL_SECONDS = 3;
const MIN_TASK_POLL_INTERVAL_SECONDS = 1;
const MAX_TASK_POLL_INTERVAL_SECONDS = 60;
const TASK_POLL_INTERVAL_STORAGE_KEY = "copaw:subagents:taskPollIntervalSec";

function normalizePollInterval(value: number): number {
  return Math.max(
    MIN_TASK_POLL_INTERVAL_SECONDS,
    Math.min(MAX_TASK_POLL_INTERVAL_SECONDS, Math.floor(value)),
  );
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatDuration(ms?: number | null): string {
  if (ms === null || ms === undefined) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

type RoleTemplate = Pick<
  SubagentRoleConfig,
  "key" | "name" | "description" | "identity_prompt" | "tool_guidelines" | "routing_keywords"
>;

const ROLE_TEMPLATES: Record<"en" | "zh", RoleTemplate[]> = {
  en: [
    {
      key: "research_agent",
      name: "Research Agent",
      description:
        "Collects and summarizes trustworthy information, then returns concise evidence-based findings.",
      identity_prompt:
        "You are a research specialist. Prioritize source quality, cite key evidence, and separate facts from assumptions.",
      tool_guidelines:
        "Prefer web_search/web_fetch and read-only tools first. Keep write actions minimal and only when explicitly required.",
      routing_keywords: ["research", "analyze", "collect", "summary", "report"],
    },
    {
      key: "coding_agent",
      name: "Coding Agent",
      description:
        "Implements code changes with clear scope, small diffs, and verification-first workflow.",
      identity_prompt:
        "You are a software engineer focused on correctness and maintainability. Make minimal, testable changes.",
      tool_guidelines:
        "Use read_file/edit_file/write_file and execute_shell_command for tests/build. Run verification before completion.",
      routing_keywords: ["code", "implement", "bugfix", "refactor", "test"],
    },
    {
      key: "ops_agent",
      name: "Ops Agent",
      description:
        "Handles environment checks, deployment/runtime diagnostics, and operational safety controls.",
      identity_prompt:
        "You are an operations specialist. Prefer safe, reversible actions and explain risk before impactful changes.",
      tool_guidelines:
        "Use execute_shell_command for diagnostics and scripts. Avoid destructive commands unless explicitly approved.",
      routing_keywords: ["deploy", "runtime", "ops", "monitor", "incident"],
    },
  ],
  zh: [
    {
      key: "research_agent",
      name: "资讯 Agent",
      description: "负责信息采集与可信来源归纳，输出简明且可追溯的结论。",
      identity_prompt:
        "你是资讯研究专家。优先引用高可信来源，区分事实与推断，给出结构化结论。",
      tool_guidelines:
        "优先使用 web_search/web_fetch 与只读工具；非必要不写文件，不做与目标无关的操作。",
      routing_keywords: ["资讯", "调研", "采集", "分析", "总结"],
    },
    {
      key: "coding_agent",
      name: "开发 Agent",
      description: "负责代码实现与修复，追求小步提交、可验证、可维护。",
      identity_prompt:
        "你是开发专家。先理解上下文，再做最小改动，优先保证正确性与可测试性。",
      tool_guidelines:
        "主要使用 read_file/edit_file/write_file 与 execute_shell_command；先验证再宣称完成。",
      routing_keywords: ["开发", "编码", "修复", "重构", "测试"],
    },
    {
      key: "ops_agent",
      name: "运维 Agent",
      description: "负责运行诊断、部署与稳定性保障，强调风险控制。",
      identity_prompt:
        "你是运维专家。优先安全与可回滚，关键变更前说明影响范围与风险。",
      tool_guidelines:
        "优先做诊断与可逆操作；涉及破坏性命令必须获得明确授权后再执行。",
      routing_keywords: ["运维", "部署", "监控", "故障", "告警"],
    },
  ],
};

function buildUniqueRoleKey(base: string, existing: Set<string>): string {
  let candidate = base;
  let idx = 2;
  while (existing.has(candidate.toLowerCase())) {
    candidate = `${base}_${idx}`;
    idx += 1;
  }
  return candidate;
}

function makeRoleDefaults(
  lang: string,
  existingRoles: Array<Partial<SubagentRoleConfig>>,
): SubagentRoleConfig {
  const locale = lang.toLowerCase().startsWith("zh") ? "zh" : "en";
  const templates = ROLE_TEMPLATES[locale];
  const template = templates[existingRoles.length % templates.length];
  const existingKeys = new Set(
    existingRoles
      .map((role) => (role.key || "").trim().toLowerCase())
      .filter(Boolean),
  );
  const roleKey = buildUniqueRoleKey(template.key, existingKeys);
  const roleName =
    roleKey === template.key ? template.name : `${template.name} ${existingRoles.length + 1}`;

  return {
    key: roleKey,
    name: roleName,
    description: template.description,
    identity_prompt: template.identity_prompt,
    tool_guidelines: template.tool_guidelines,
    enabled: true,
    routing_keywords: [...template.routing_keywords],
    tool_allowlist: [],
    mcp_policy: "inherit",
    mcp_selected: [],
    skills_policy: "inherit",
    skills_selected: [],
  };
}

function SubagentsPage() {
  const { t, i18n } = useTranslation();
  const [form] = Form.useForm<SubagentsConfig>();
  const roleValues =
    (Form.useWatch("roles", form) as Array<Partial<SubagentRoleConfig>> | undefined) || [];

  const [activeTab, setActiveTab] = useState("config");
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [savingConfig, setSavingConfig] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);

  const [mcpOptions, setMcpOptions] = useState<string[]>([]);
  const [skillOptions, setSkillOptions] = useState<string[]>([]);

  const [tasksLoading, setTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [tasks, setTasks] = useState<SubagentTask[]>([]);
  const [tasksTotal, setTasksTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [taskPollIntervalSec, setTaskPollIntervalSec] = useState(() => {
    if (typeof window === "undefined") {
      return DEFAULT_TASK_POLL_INTERVAL_SECONDS;
    }
    const rawValue = window.localStorage.getItem(TASK_POLL_INTERVAL_STORAGE_KEY);
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) {
      return DEFAULT_TASK_POLL_INTERVAL_SECONDS;
    }
    return normalizePollInterval(parsed);
  });
  const [pagination, setPagination] = useState<PaginationState>({
    page: 1,
    pageSize: 10,
  });

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailTask, setDetailTask] = useState<SubagentTask | null>(null);

  const fetchReferenceOptions = useCallback(async () => {
    const [mcpResult, skillsResult] = await Promise.allSettled([
      api.listMCPClients(),
      api.listSkills(),
    ]);

    if (mcpResult.status === "fulfilled") {
      const mcpValues = mcpResult.value.map((item: MCPClientInfo) => item.key);
      setMcpOptions(mcpValues);
    }
    if (skillsResult.status === "fulfilled") {
      const skillValues = skillsResult.value.map((item: SkillSpec) => item.name);
      setSkillOptions(skillValues);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    setLoadingConfig(true);
    setConfigError(null);
    try {
      const config = await api.getSubagentsConfig();
      form.setFieldsValue(config);
    } catch (error) {
      setConfigError(
        error instanceof Error ? error.message : t("subagents.loadFailed"),
      );
    } finally {
      setLoadingConfig(false);
    }
  }, [form, t]);

  useEffect(() => {
    void fetchReferenceOptions();
    void fetchConfig();
  }, [fetchConfig, fetchReferenceOptions]);

  const fetchTasks = useCallback(
    async (silent = false) => {
      if (!silent) {
        setTasksLoading(true);
      }
      try {
        const limit = pagination.pageSize;
        const offset = (pagination.page - 1) * pagination.pageSize;
        const result = await api.listSubagentTasks({
          status: statusFilter || undefined,
          limit,
          offset,
        });
        setTasks(result.items);
        setTasksTotal(result.total);
        setTasksError(null);
      } catch (error) {
        setTasksError(
          error instanceof Error ? error.message : t("subagents.tasksLoadFailed"),
        );
      } finally {
        if (!silent) {
          setTasksLoading(false);
        }
      }
    },
    [pagination.page, pagination.pageSize, statusFilter, t],
  );

  useEffect(() => {
    if (activeTab !== "tasks") return;
    void fetchTasks();
    const timer = window.setInterval(() => {
      void fetchTasks(true);
    }, taskPollIntervalSec * 1000);
    return () => window.clearInterval(timer);
  }, [activeTab, fetchTasks, taskPollIntervalSec]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      TASK_POLL_INTERVAL_STORAGE_KEY,
      String(taskPollIntervalSec),
    );
  }, [taskPollIntervalSec]);

  const handleSaveConfig = async () => {
    try {
      const values = await form.validateFields();
      setSavingConfig(true);
      await api.updateSubagentsConfig(values);
      message.success(t("subagents.saveSuccess"));
      await fetchConfig();
    } catch (error) {
      if (error instanceof Error && "errorFields" in error) return;
      message.error(
        error instanceof Error ? error.message : t("subagents.saveFailed"),
      );
    } finally {
      setSavingConfig(false);
    }
  };

  const handleViewTask = useCallback(
    async (taskId: string) => {
      setDetailOpen(true);
      setDetailLoading(true);
      try {
        const detail = await api.getSubagentTask(taskId);
        setDetailTask(detail);
      } catch (error) {
        message.error(
          error instanceof Error ? error.message : t("subagents.detailLoadFailed"),
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [t],
  );

  const taskColumns: TableColumnsType<SubagentTask> = useMemo(
    () => [
      { title: t("subagents.taskId"), dataIndex: "task_id", width: 220 },
      { title: t("subagents.label"), dataIndex: "label", width: 120 },
      {
        title: t("subagents.role"),
        dataIndex: "role_key",
        width: 120,
        render: (value: string) => value || "-",
      },
      {
        title: t("subagents.statusLabel"),
        dataIndex: "status",
        width: 120,
        render: (status: SubagentTaskStatus) => (
          <span className={`${styles.statusTag} ${styles[`status-${status}`] ?? ""}`}>
            {t(`subagents.status.${status}`)}
          </span>
        ),
      },
      {
        title: t("subagents.dispatchReason"),
        dataIndex: "dispatch_reason",
        width: 220,
        render: (value: string) => value || "-",
      },
      {
        title: t("subagents.duration"),
        dataIndex: "duration_ms",
        width: 100,
        render: (value: number | null | undefined) => formatDuration(value),
      },
      {
        title: t("subagents.actions"),
        key: "actions",
        width: 100,
        render: (_, record) => (
          <Button type="link" onClick={() => void handleViewTask(record.task_id)}>
            {t("subagents.viewDetail")}
          </Button>
        ),
      },
    ],
    [handleViewTask, t],
  );

  const roleOptions = useMemo(
    () =>
      roleValues
        .map((role: { key?: string; name?: string }) => ({
          value: role.key || "",
          label: role.name || role.key || "",
        }))
        .filter((item) => item.value),
    [roleValues],
  );

  const defaultRoleDraft = useMemo(
    () => makeRoleDefaults(i18n.resolvedLanguage || i18n.language || "en", roleValues),
    [i18n.language, i18n.resolvedLanguage, roleValues],
  );

  const tabItems: TabsProps["items"] = [
    {
      key: "config",
      label: t("subagents.tabs.config"),
      children: (
        <Card className={styles.card}>
          <Form form={form} layout="vertical">
            <div className={styles.grid2}>
              <Form.Item label={t("subagents.enabled")} name="enabled" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item label={t("subagents.allowNestedSpawn")} name="allow_nested_spawn" valuePropName="checked">
                <Switch />
              </Form.Item>
            </div>

            <div className={styles.grid2}>
              <Form.Item label={t("subagents.maxConcurrency")} name="max_concurrency">
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label={t("subagents.defaultTimeoutSeconds")} name="default_timeout_seconds">
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
            </div>

            <div className={styles.grid2}>
              <Form.Item label={t("subagents.hardTimeoutSeconds")} name="hard_timeout_seconds">
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label={t("subagents.writeMode")} name="write_mode">
                <Select
                  options={[
                    { value: "worktree", label: t("subagents.writeModeWorktree") },
                    { value: "direct", label: t("subagents.writeModeDirect") },
                  ]}
                />
              </Form.Item>
            </div>

            <div className={styles.grid2}>
              <Form.Item label={t("subagents.executionMode")} name="execution_mode">
                <Select
                  options={[
                    { value: "sync", label: t("subagents.executionModeSync") },
                    { value: "async", label: t("subagents.executionModeAsync") },
                  ]}
                />
              </Form.Item>
              <Form.Item label={t("subagents.retryMaxAttempts")} name="retry_max_attempts">
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
            </div>

            <Form.Item label={t("subagents.retryBackoffSeconds")} name="retry_backoff_seconds">
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>

            <div className={styles.grid2}>
              <Form.Item label={t("subagents.dispatchMode")} name="dispatch_mode">
                <Select
                  options={[
                    { value: "advisory", label: t("subagents.dispatchModeAdvisory") },
                    { value: "force_when_matched", label: t("subagents.dispatchModeMatched") },
                    { value: "force_by_default", label: t("subagents.dispatchModeDefault") },
                  ]}
                />
              </Form.Item>
              <Form.Item label={t("subagents.autoDispatchMinPromptChars")} name="auto_dispatch_min_prompt_chars">
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
            </div>

            <Form.Item label={t("subagents.autoDispatchKeywords")} name="auto_dispatch_keywords">
              <Select mode="tags" tokenSeparators={[","]} />
            </Form.Item>

            <div className={styles.grid2}>
              <Form.Item label={t("subagents.roleSelectionMode")} name="role_selection_mode">
                <Select
                  options={[
                    { value: "auto", label: t("subagents.roleSelectionModeAuto") },
                    { value: "default", label: t("subagents.roleSelectionModeDefault") },
                  ]}
                />
              </Form.Item>
              <Form.Item label={t("subagents.defaultRole")} name="default_role">
                <Select allowClear options={roleOptions} />
              </Form.Item>
            </div>

            <Form.Item label={t("subagents.allowedPaths")} name="allowed_paths">
              <Select mode="tags" tokenSeparators={[","]} />
            </Form.Item>
            <Form.Item label={t("subagents.defaultTools")} name={["tools", "default_enabled"]}>
              <Select mode="tags" tokenSeparators={[","]} />
            </Form.Item>

            <div className={styles.actions}>
              <Button onClick={() => void fetchConfig()} disabled={savingConfig}>
                {t("common.reset")}
              </Button>
              <Button type="primary" loading={savingConfig} onClick={() => void handleSaveConfig()}>
                {t("common.save")}
              </Button>
            </div>
          </Form>
        </Card>
      ),
    },
    {
      key: "roles",
      label: t("subagents.tabs.roles"),
      children: (
        <Card className={styles.card}>
          <Form form={form} layout="vertical">
            <Form.List name="roles">
              {(fields, { add, remove }) => (
                <>
                  <Alert
                    style={{ marginBottom: 12 }}
                    type="info"
                    showIcon
                    message={t("subagents.rolesHint")}
                  />
                  <div className={styles.actions}>
                    <Button
                      type="dashed"
                      onClick={() => add(defaultRoleDraft)}
                    >
                      {t("subagents.addRole")}
                    </Button>
                  </div>
                  {fields.map((field, idx) => (
                    <Card
                      key={field.key}
                      size="small"
                      style={{ marginBottom: 12 }}
                      title={`${t("subagents.roleCardTitle")} #${idx + 1}`}
                      extra={
                        <Button danger type="link" onClick={() => remove(field.name)}>
                          {t("common.delete")}
                        </Button>
                      }
                    >
                      <div className={styles.grid2}>
                        <Form.Item label={t("subagents.roleKey")} name={[field.name, "key"]}>
                          <Input placeholder="research_agent" />
                        </Form.Item>
                        <Form.Item label={t("subagents.roleName")} name={[field.name, "name"]}>
                          <Input placeholder={t("subagents.roleNamePlaceholder")} />
                        </Form.Item>
                      </div>
                      <Form.Item label={t("subagents.roleEnabled")} name={[field.name, "enabled"]} valuePropName="checked">
                        <Switch />
                      </Form.Item>
                      <Form.Item label={t("subagents.roleDescription")} name={[field.name, "description"]}>
                        <Input.TextArea rows={2} />
                      </Form.Item>
                      <Form.Item label={t("subagents.roleIdentityPrompt")} name={[field.name, "identity_prompt"]}>
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      <Form.Item label={t("subagents.roleToolGuidelines")} name={[field.name, "tool_guidelines"]}>
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      <Form.Item label={t("subagents.roleRoutingKeywords")} name={[field.name, "routing_keywords"]}>
                        <Select mode="tags" tokenSeparators={[","]} />
                      </Form.Item>
                      <Form.Item label={t("subagents.roleToolAllowlist")} name={[field.name, "tool_allowlist"]}>
                        <Select mode="tags" tokenSeparators={[","]} />
                      </Form.Item>
                      <div className={styles.grid2}>
                        <Form.Item label={t("subagents.roleMcpPolicy")} name={[field.name, "mcp_policy"]}>
                          <Select
                            options={[
                              { value: "inherit", label: t("subagents.policy.inherit") },
                              { value: "none", label: t("subagents.policy.none") },
                              { value: "selected", label: t("subagents.policy.selected") },
                              { value: "all", label: t("subagents.policy.all") },
                            ]}
                          />
                        </Form.Item>
                        <Form.Item label={t("subagents.roleSkillsPolicy")} name={[field.name, "skills_policy"]}>
                          <Select
                            options={[
                              { value: "inherit", label: t("subagents.policy.inherit") },
                              { value: "none", label: t("subagents.policy.none") },
                              { value: "selected", label: t("subagents.policy.selected") },
                              { value: "all", label: t("subagents.policy.all") },
                            ]}
                          />
                        </Form.Item>
                      </div>
                      <Form.Item label={t("subagents.mcpSelected")} name={[field.name, "mcp_selected"]}>
                        <Select mode="tags" options={mcpOptions.map((v) => ({ value: v, label: v }))} />
                      </Form.Item>
                      <Form.Item label={t("subagents.skillsSelected")} name={[field.name, "skills_selected"]}>
                        <Select mode="tags" options={skillOptions.map((v) => ({ value: v, label: v }))} />
                      </Form.Item>
                    </Card>
                  ))}
                </>
              )}
            </Form.List>
            <div className={styles.actions}>
              <Button onClick={() => void fetchConfig()} disabled={savingConfig}>
                {t("common.reset")}
              </Button>
              <Button type="primary" loading={savingConfig} onClick={() => void handleSaveConfig()}>
                {t("common.save")}
              </Button>
            </div>
          </Form>
        </Card>
      ),
    },
    {
      key: "tasks",
      label: t("subagents.tabs.tasks"),
      children: (
        <Card className={styles.card}>
          <div className={styles.tasksToolbar}>
            <Space size={12}>
              <Select
                value={statusFilter}
                style={{ width: 180 }}
                onChange={(value) => {
                  setStatusFilter(value);
                  setPagination((prev) => ({ ...prev, page: 1 }));
                }}
                options={[
                  { value: "", label: t("subagents.status.all") },
                  { value: "queued", label: t("subagents.status.queued") },
                  { value: "running", label: t("subagents.status.running") },
                  { value: "success", label: t("subagents.status.success") },
                  { value: "error", label: t("subagents.status.error") },
                  { value: "timeout", label: t("subagents.status.timeout") },
                  { value: "cancelled", label: t("subagents.status.cancelled") },
                ]}
              />
              <Button onClick={() => void fetchTasks()}>{t("common.refresh")}</Button>
            </Space>
            <Space size={8}>
              <span className={styles.toolbarLabel}>
                {t("subagents.taskPollInterval")}
              </span>
              <InputNumber
                min={MIN_TASK_POLL_INTERVAL_SECONDS}
                max={MAX_TASK_POLL_INTERVAL_SECONDS}
                value={taskPollIntervalSec}
                style={{ width: 100 }}
                onChange={(value) => {
                  if (typeof value !== "number" || Number.isNaN(value)) return;
                  setTaskPollIntervalSec(normalizePollInterval(value));
                }}
              />
              <span className={styles.toolbarLabel}>{t("subagents.secondsShort")}</span>
            </Space>
          </div>

          {tasksError && (
            <Alert style={{ marginBottom: 12 }} type="error" showIcon message={tasksError} />
          )}

          <Table<SubagentTask>
            rowKey="task_id"
            columns={taskColumns}
            dataSource={tasks}
            loading={tasksLoading}
            pagination={{
              current: pagination.page,
              pageSize: pagination.pageSize,
              total: tasksTotal,
              showSizeChanger: true,
              onChange: (page, pageSize) => setPagination({ page, pageSize }),
            }}
          />
        </Card>
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>{t("subagents.title")}</h1>
        <p className={styles.description}>{t("subagents.description")}</p>
      </div>

      {loadingConfig ? (
        <div className={styles.centerState}>{t("common.loading")}</div>
      ) : configError ? (
        <div className={styles.centerState}>
          <Alert
            type="error"
            showIcon
            message={configError}
            action={
              <Button size="small" onClick={() => void fetchConfig()}>
                {t("environments.retry")}
              </Button>
            }
          />
        </div>
      ) : (
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      )}

      <Drawer
        title={t("subagents.detailTitle")}
        open={detailOpen}
        width={720}
        onClose={() => setDetailOpen(false)}
      >
        {detailLoading ? (
          <div>{t("common.loading")}</div>
        ) : detailTask ? (
          <div className={styles.detailContent}>
            <div>
              <strong>{t("subagents.taskId")}:</strong> {detailTask.task_id}
            </div>
            <div>
              <strong>{t("subagents.statusLabel")}:</strong>{" "}
              {t(`subagents.status.${detailTask.status}`)}
            </div>
            <div>
              <strong>{t("subagents.role")}:</strong> {detailTask.role_key || "-"}
            </div>
            <div>
              <strong>{t("subagents.dispatchReason")}:</strong>{" "}
              {detailTask.dispatch_reason || "-"}
            </div>
            <div>
              <strong>{t("subagents.startedAt")}:</strong>{" "}
              {formatDateTime(detailTask.started_at)}
            </div>
            <div>
              <strong>{t("subagents.endedAt")}:</strong>{" "}
              {formatDateTime(detailTask.ended_at)}
            </div>
            <div>
              <strong>{t("subagents.duration")}:</strong>{" "}
              {formatDuration(detailTask.duration_ms)}
            </div>
            <div>
              <strong>{t("subagents.summary")}:</strong>{" "}
              {detailTask.result_summary || "-"}
            </div>
            <div>
              <strong>{t("subagents.errorMessage")}:</strong>{" "}
              {detailTask.error_message || "-"}
            </div>
            <div>
              <strong>{t("subagents.taskPrompt")}:</strong>
              <pre className={styles.pre}>{detailTask.task_prompt || "-"}</pre>
            </div>
            <div>
              <strong>{t("subagents.artifacts")}:</strong>
              <pre className={styles.pre}>
                {JSON.stringify(detailTask.artifacts, null, 2)}
              </pre>
            </div>
          </div>
        ) : (
          <div>{t("subagents.emptyDetail")}</div>
        )}
      </Drawer>
    </div>
  );
}

export default SubagentsPage;
