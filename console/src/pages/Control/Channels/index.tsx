import { useEffect, useMemo, useState } from "react";
import {
  Form,
  Switch,
  message,
  Button,
  Card,
  Table,
  Modal,
  Input,
  Select,
  Tag,
} from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";

import api from "../../../api";
import type {
  SingleChannelConfig,
  ChannelInstanceSummary,
} from "../../../api/types";
import {
  ChannelCard,
  ChannelDrawer,
  useChannels,
  CHANNEL_LABELS,
  type ChannelKey,
} from "./components";
import { publishShowToolDetails } from "../../../utils/showToolDetailsSync";
import styles from "./index.module.less";

interface InstanceFormValues {
  instanceKey: string;
  channelType: string;
  enabled: boolean;
  botPrefix: string;
  overridesJson: string;
}

function ChannelsPage() {
  const { t } = useTranslation();
  const { channels, loading, fetchChannels } = useChannels();
  const [saving, setSaving] = useState(false);
  const [showToolDetails, setShowToolDetails] = useState(true);
  const [loadingShowToolDetails, setLoadingShowToolDetails] = useState(true);
  const [savingShowToolDetails, setSavingShowToolDetails] = useState(false);
  const [showReasoning, setShowReasoning] = useState(true);
  const [loadingShowReasoning, setLoadingShowReasoning] = useState(true);
  const [savingShowReasoning, setSavingShowReasoning] = useState(false);
  const [hoverKey, setHoverKey] = useState<ChannelKey | null>(null);
  const [activeKey, setActiveKey] = useState<ChannelKey | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [form] = Form.useForm<SingleChannelConfig>();

  const [instances, setInstances] = useState<ChannelInstanceSummary[]>([]);
  const [channelTypes, setChannelTypes] = useState<string[]>([]);
  const [loadingInstances, setLoadingInstances] = useState(false);
  const [instanceModalOpen, setInstanceModalOpen] = useState(false);
  const [instanceSaving, setInstanceSaving] = useState(false);
  const [editingInstanceKey, setEditingInstanceKey] = useState<string | null>(
    null,
  );
  const [instanceForm] = Form.useForm<InstanceFormValues>();

  const refreshInstanceData = async () => {
    setLoadingInstances(true);
    try {
      const [instanceData, types] = await Promise.all([
        api.listChannelInstances(),
        api.listChannelTypes(),
      ]);
      setInstances(instanceData || []);
      setChannelTypes(types || []);
    } catch (error) {
      console.error("Failed to load channel instances:", error);
      message.error(
        t("channels.instanceLoadFailed", {
          defaultValue: "Failed to load channel instances",
        }),
      );
    } finally {
      setLoadingInstances(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const fetchRenderVisibility = async () => {
      setLoadingShowToolDetails(true);
      setLoadingShowReasoning(true);
      try {
        const [toolDetailsResult, reasoningResult] = await Promise.all([
          api.getShowToolDetails(),
          api.getShowReasoning(),
        ]);
        if (mounted) {
          setShowToolDetails(toolDetailsResult.show_tool_details);
          setShowReasoning(reasoningResult.show_reasoning);
        }
      } catch (error) {
        console.error("Failed to load render visibility settings:", error);
        if (mounted) {
          message.error(t("channels.renderVisibilityLoadFailed"));
        }
      } finally {
        if (mounted) {
          setLoadingShowToolDetails(false);
          setLoadingShowReasoning(false);
        }
      }
    };

    void fetchRenderVisibility();
    void refreshInstanceData();

    return () => {
      mounted = false;
    };
  }, [t]);

  const cards = useMemo(() => {
    const entries: { key: ChannelKey; config: SingleChannelConfig }[] = [];

    const channelOrder: ChannelKey[] = [
      "console",
      "dingtalk",
      "feishu",
      "imessage",
      "discord",
      "qq",
    ];

    channelOrder.forEach((key) => {
      if (channels[key] && channels[key].enabled) {
        entries.push({ key, config: channels[key] });
      }
    });

    channelOrder.forEach((key) => {
      if (channels[key] && !channels[key].enabled) {
        entries.push({ key, config: channels[key] });
      }
    });

    return entries;
  }, [channels]);

  const customInstances = useMemo(() => {
    const typeSet = new Set(channelTypes);
    return instances
      .filter((item) => !typeSet.has(item.key))
      .sort((a, b) => a.key.localeCompare(b.key));
  }, [instances, channelTypes]);

  const handleCardClick = (key: ChannelKey) => {
    setActiveKey(key);
    setDrawerOpen(true);
    form.setFieldsValue(channels[key]);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setActiveKey(null);
  };

  const handleSubmit = async (values: SingleChannelConfig) => {
    if (!activeKey) return;

    const updatedChannel: SingleChannelConfig = {
      ...channels[activeKey],
      ...values,
    };

    setSaving(true);
    try {
      await api.updateChannelConfig(activeKey, updatedChannel);
      await fetchChannels();

      setDrawerOpen(false);
      message.success(t("channels.configSaved"));
    } catch (error) {
      console.error("Failed to update channel config:", error);
      message.error(t("channels.configFailed"));
    } finally {
      setSaving(false);
    }
  };

  const activeLabel = activeKey ? CHANNEL_LABELS[activeKey] : "";

  const handleToggleShowToolDetails = async (checked: boolean) => {
    setShowToolDetails(checked);
    setSavingShowToolDetails(true);
    try {
      const result = await api.updateShowToolDetails(checked);
      setShowToolDetails(result.show_tool_details);
      publishShowToolDetails(result.show_tool_details);
      message.success(t("channels.showToolDetailsSaved"));
    } catch (error) {
      console.error("Failed to update show_tool_details:", error);
      setShowToolDetails((prev) => !prev);
      message.error(t("channels.showToolDetailsSaveFailed"));
    } finally {
      setSavingShowToolDetails(false);
    }
  };

  const handleToggleShowReasoning = async (checked: boolean) => {
    setShowReasoning(checked);
    setSavingShowReasoning(true);
    try {
      const result = await api.updateShowReasoning(checked);
      setShowReasoning(result.show_reasoning);
      message.success(t("channels.showReasoningSaved"));
    } catch (error) {
      console.error("Failed to update show_reasoning:", error);
      setShowReasoning((prev) => !prev);
      message.error(t("channels.showReasoningSaveFailed"));
    } finally {
      setSavingShowReasoning(false);
    }
  };

  const openCreateInstanceModal = () => {
    setEditingInstanceKey(null);
    instanceForm.setFieldsValue({
      instanceKey: "",
      channelType: channelTypes[0] || "console",
      enabled: true,
      botPrefix: "",
      overridesJson: "{}",
    });
    setInstanceModalOpen(true);
  };

  const openEditInstanceModal = async (instanceKey: string) => {
    try {
      const detail = await api.getChannelInstance(instanceKey);
      const config =
        (detail.config as Record<string, unknown> | undefined) || {};
      const overrides: Record<string, unknown> = { ...config };
      delete overrides.enabled;
      delete overrides.bot_prefix;
      delete overrides.channel_type;

      setEditingInstanceKey(instanceKey);
      instanceForm.setFieldsValue({
        instanceKey,
        channelType: detail.channel_type,
        enabled: Boolean(config.enabled),
        botPrefix: String(config.bot_prefix || ""),
        overridesJson: JSON.stringify(overrides, null, 2),
      });
      setInstanceModalOpen(true);
    } catch (error) {
      console.error("Failed to load channel instance:", error);
      message.error(
        t("channels.instanceLoadFailed", {
          defaultValue: "Failed to load channel instance",
        }),
      );
    }
  };

  const handleDeleteInstance = (instanceKey: string) => {
    Modal.confirm({
      title: t("channels.instanceDeleteTitle", {
        defaultValue: "Delete Instance",
      }),
      content: t("channels.instanceDeleteConfirm", {
        defaultValue: "Delete channel instance {{key}}?",
        key: instanceKey,
      }),
      okText: t("common.delete"),
      okType: "danger",
      cancelText: t("common.cancel"),
      onOk: async () => {
        try {
          await api.deleteChannelInstance(instanceKey);
          await refreshInstanceData();
          message.success(
            t("channels.instanceDeleteSuccess", {
              defaultValue: "Channel instance deleted",
            }),
          );
        } catch (error) {
          console.error("Failed to delete channel instance:", error);
          message.error(
            t("channels.instanceDeleteFailed", {
              defaultValue: "Failed to delete channel instance",
            }),
          );
        }
      },
    });
  };

  const handleSaveInstance = async () => {
    try {
      const values = await instanceForm.validateFields();
      const targetKey = (editingInstanceKey || values.instanceKey || "").trim();
      if (!targetKey) {
        message.error(
          t("channels.instanceKeyRequired", {
            defaultValue: "Instance key is required",
          }),
        );
        return;
      }

      let overrides: Record<string, unknown> = {};
      const rawJson = (values.overridesJson || "").trim();
      if (rawJson) {
        const parsed = JSON.parse(rawJson) as unknown;
        if (
          typeof parsed !== "object" ||
          parsed === null ||
          Array.isArray(parsed)
        ) {
          throw new Error("overrides_json_must_be_object");
        }
        overrides = parsed as Record<string, unknown>;
      }

      const configPayload: Record<string, unknown> = {
        ...overrides,
        enabled: values.enabled,
        bot_prefix: values.botPrefix || "",
      };

      setInstanceSaving(true);
      await api.upsertChannelInstance(targetKey, {
        channel_type: values.channelType,
        config: configPayload,
      });
      await Promise.all([refreshInstanceData(), fetchChannels()]);
      setInstanceModalOpen(false);
      message.success(
        t("channels.instanceSaveSuccess", {
          defaultValue: "Channel instance saved",
        }),
      );
    } catch (error) {
      if (error instanceof SyntaxError) {
        message.error(
          t("channels.instanceOverridesJsonInvalid", {
            defaultValue: "Overrides JSON must be valid object JSON",
          }),
        );
        return;
      }
      if (
        typeof error === "object" &&
        error !== null &&
        "errorFields" in error
      ) {
        return;
      }
      console.error("Failed to save channel instance:", error);
      message.error(
        t("channels.instanceSaveFailed", {
          defaultValue: "Failed to save channel instance",
        }),
      );
    } finally {
      setInstanceSaving(false);
    }
  };

  const instanceColumns = [
    {
      title: t("channels.instanceKey", { defaultValue: "Instance" }),
      dataIndex: "key",
      key: "key",
      width: 220,
    },
    {
      title: t("channels.instanceType", { defaultValue: "Type" }),
      dataIndex: "channel_type",
      key: "channel_type",
      width: 140,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: t("channels.status", { defaultValue: "Status" }),
      key: "enabled",
      width: 120,
      render: (_: unknown, record: ChannelInstanceSummary) => (
        <Tag color={record.enabled ? "green" : "default"}>
          {record.enabled ? "Enabled" : "Disabled"}
        </Tag>
      ),
    },
    {
      title: t("channels.botPrefix", { defaultValue: "Bot Prefix" }),
      dataIndex: "bot_prefix",
      key: "bot_prefix",
      ellipsis: true,
      render: (value: string) => value || "-",
    },
    {
      title: t("cronJobs.action", { defaultValue: "Action" }),
      key: "action",
      width: 180,
      render: (_: unknown, record: ChannelInstanceSummary) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="link"
            size="small"
            onClick={() => {
              void openEditInstanceModal(record.key);
            }}
          >
            {t("common.edit")}
          </Button>
          <Button
            type="link"
            size="small"
            danger
            onClick={() => handleDeleteInstance(record.key)}
          >
            {t("common.delete")}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className={styles.channelsPage}>
      <h1 className={styles.title}>{t("channels.title")}</h1>
      <p className={styles.description}>{t("channels.description")}</p>
      <div className={styles.settingRow}>
        <div className={styles.settingText}>
          <div className={styles.settingTitle}>
            {t("channels.showToolDetails")}
          </div>
          <div className={styles.settingDescription}>
            {t("channels.showToolDetailsDesc")}
          </div>
        </div>
        <Switch
          checked={showToolDetails}
          loading={savingShowToolDetails}
          disabled={loadingShowToolDetails}
          onChange={(checked) => {
            void handleToggleShowToolDetails(checked);
          }}
        />
      </div>
      <div className={styles.settingRow}>
        <div className={styles.settingText}>
          <div className={styles.settingTitle}>
            {t("channels.showReasoning")}
          </div>
          <div className={styles.settingDescription}>
            {t("channels.showReasoningDesc")}
          </div>
        </div>
        <Switch
          checked={showReasoning}
          loading={savingShowReasoning}
          disabled={loadingShowReasoning}
          onChange={(checked) => {
            void handleToggleShowReasoning(checked);
          }}
        />
      </div>

      {loading ? (
        <div className={styles.loading}>
          <span className={styles.loadingText}>{t("channels.loading")}</span>
        </div>
      ) : (
        <div className={styles.channelsGrid}>
          {cards.map(({ key, config }) => (
            <ChannelCard
              key={key}
              channelKey={key}
              config={config}
              isHover={hoverKey === key}
              onClick={() => handleCardClick(key)}
              onMouseEnter={() => setHoverKey(key)}
              onMouseLeave={() => setHoverKey(null)}
            />
          ))}
        </div>
      )}

      <div className={styles.instanceSection}>
        <div className={styles.instanceHeader}>
          <div>
            <h2 className={styles.instanceTitle}>
              {t("channels.instanceTitle", {
                defaultValue: "Channel Instances",
              })}
            </h2>
            <p className={styles.description}>
              {t("channels.instanceDescription", {
                defaultValue:
                  "Create multiple bot instances under the same channel type.",
              })}
            </p>
          </div>
          <Button type="primary" onClick={openCreateInstanceModal}>
            {t("channels.instanceCreate", { defaultValue: "Add Instance" })}
          </Button>
        </div>

        <Card className={styles.instanceTableCard} bodyStyle={{ padding: 0 }}>
          <Table
            rowKey="key"
            columns={instanceColumns}
            dataSource={customInstances}
            loading={loadingInstances}
            pagination={{
              pageSize: 8,
              showTotal: (total) =>
                t("channels.totalItems", {
                  count: total,
                  defaultValue: "Total {{count}} items",
                }),
            }}
          />
        </Card>
      </div>

      <ChannelDrawer
        open={drawerOpen}
        activeKey={activeKey}
        activeLabel={activeLabel}
        form={form}
        saving={saving}
        initialValues={activeKey ? channels[activeKey] : undefined}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />

      <Modal
        title={
          editingInstanceKey
            ? t("channels.instanceEditTitle", {
                defaultValue: "Edit Channel Instance",
              })
            : t("channels.instanceCreateTitle", {
                defaultValue: "Create Channel Instance",
              })
        }
        open={instanceModalOpen}
        onCancel={() => setInstanceModalOpen(false)}
        onOk={() => {
          void handleSaveInstance();
        }}
        confirmLoading={instanceSaving}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        width={680}
      >
        <Form form={instanceForm} layout="vertical">
          <Form.Item
            name="instanceKey"
            label={t("channels.instanceKey", { defaultValue: "Instance Key" })}
            rules={[
              {
                required: true,
                message: t("channels.instanceKeyRequired", {
                  defaultValue: "Instance key is required",
                }),
              },
            ]}
          >
            <Input
              placeholder={t("channels.instanceKeyPlaceholder", {
                defaultValue: "e.g. telegram_sales",
              })}
              disabled={Boolean(editingInstanceKey)}
            />
          </Form.Item>

          <Form.Item
            name="channelType"
            label={t("channels.instanceType", { defaultValue: "Channel Type" })}
            rules={[
              {
                required: true,
                message: t("channels.instanceTypeRequired", {
                  defaultValue: "Channel type is required",
                }),
              },
            ]}
          >
            <Select
              options={channelTypes.map((value) => ({
                label: value,
                value,
              }))}
            />
          </Form.Item>

          <Form.Item
            name="enabled"
            label={t("channels.status", { defaultValue: "Enabled" })}
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="botPrefix"
            label={t("channels.botPrefix", { defaultValue: "Bot Prefix" })}
          >
            <Input placeholder="@bot" />
          </Form.Item>

          <Form.Item
            name="overridesJson"
            label={t("channels.instanceOverrides", {
              defaultValue: "Overrides (JSON)",
            })}
            extra={t("channels.instanceOverridesHint", {
              defaultValue:
                "Provide per-instance fields (token, app_id, secret, etc.) in JSON object format.",
            })}
          >
            <Input.TextArea
              autoSize={{ minRows: 8, maxRows: 16 }}
              placeholder='{"bot_token": "xxx", "http_proxy": "http://127.0.0.1:7890"}'
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default ChannelsPage;
