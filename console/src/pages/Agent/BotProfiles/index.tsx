import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Switch,
  message,
} from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import api from "../../../api";
import type { BotProfileConfig, BotProfilesConfig } from "../../../api/types";
import styles from "./index.module.less";

type ProfileFormValue = BotProfileConfig;

const EMPTY_PROFILE: ProfileFormValue = {
  key: "",
  name: "",
  enabled: true,
  description: "",
  identity_prompt: "",
};

function normalizeProfile(profile: ProfileFormValue): ProfileFormValue {
  return {
    key: profile.key.trim(),
    name: profile.name.trim(),
    enabled: Boolean(profile.enabled),
    description: profile.description.trim(),
    identity_prompt: profile.identity_prompt.trim(),
  };
}

export default function BotProfilesPage() {
  const { t } = useTranslation();
  const [form] = Form.useForm<BotProfilesConfig>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [channelTypes, setChannelTypes] = useState<string[]>([]);
  const [channelBindings, setChannelBindings] = useState<Record<string, string>>(
    {},
  );

  const profiles = Form.useWatch("profiles", form) || [];
  const enabledProfiles = useMemo(
    () => profiles.filter((item) => item?.enabled && item?.key?.trim()),
    [profiles],
  );

  useEffect(() => {
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const currentDefault = form.getFieldValue("default_bot");
    const exists = enabledProfiles.some((profile) => profile.key === currentDefault);
    if (!exists && enabledProfiles.length > 0) {
      form.setFieldsValue({ default_bot: enabledProfiles[0].key });
    }
  }, [enabledProfiles, form]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [config, channels] = await Promise.all([
        api.getBotProfilesConfig(),
        api.listChannelTypes(),
      ]);
      setChannelTypes(channels);
      setChannelBindings(config.channel_bindings || {});
      form.setFieldsValue(config);
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : t("botProfiles.loadFailed");
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    void fetchData();
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const normalizedProfiles = (values.profiles || [])
        .map(normalizeProfile)
        .filter((item) => item.key);

      if (normalizedProfiles.length === 0) {
        message.error(t("botProfiles.atLeastOneProfile"));
        return;
      }

      const normalizedBindings: Record<string, string> = {};
      for (const channel of channelTypes) {
        const botKey = (channelBindings[channel] || "").trim();
        if (!botKey) continue;
        normalizedBindings[channel] = botKey;
      }

      const payload: BotProfilesConfig = {
        enabled: Boolean(values.enabled),
        default_bot: (values.default_bot || "").trim(),
        profiles: normalizedProfiles,
        channel_bindings: normalizedBindings,
      };

      setSaving(true);
      const saved = await api.updateBotProfilesConfig(payload);
      form.setFieldsValue(saved);
      setChannelBindings(saved.channel_bindings || {});
      message.success(t("botProfiles.saveSuccess"));
    } catch (err) {
      if (err instanceof Error && "errorFields" in err) {
        return;
      }
      const errMsg =
        err instanceof Error ? err.message : t("botProfiles.saveFailed");
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      {loading && (
        <div className={styles.centerState}>
          <span className={styles.stateText}>{t("common.loading")}</span>
        </div>
      )}

      {error && !loading && (
        <div className={styles.centerState}>
          <span className={styles.stateTextError}>{error}</span>
          <Button size="small" onClick={fetchData} style={{ marginTop: 12 }}>
            {t("environments.retry")}
          </Button>
        </div>
      )}

      <div style={{ display: loading || error ? "none" : "block" }}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>{t("botProfiles.title")}</h1>
            <p className={styles.description}>{t("botProfiles.description")}</p>
          </div>
        </div>

        <Alert
          className={styles.notice}
          type="info"
          showIcon
          message={t("botProfiles.notice")}
        />

        <Form form={form} layout="vertical" className={styles.form}>
          <Card className={styles.card}>
            <div className={styles.inlineRow}>
              <Form.Item
                label={t("botProfiles.enabled")}
                name="enabled"
                valuePropName="checked"
                className={styles.compactItem}
              >
                <Switch />
              </Form.Item>

              <Form.Item
                label={t("botProfiles.defaultBot")}
                name="default_bot"
                rules={[
                  {
                    required: true,
                    message: t("botProfiles.defaultBotRequired"),
                  },
                ]}
                className={styles.compactItem}
              >
                <Select
                  options={enabledProfiles.map((profile) => ({
                    value: profile.key,
                    label: `${profile.name || profile.key} (${profile.key})`,
                  }))}
                  placeholder={t("botProfiles.defaultBotPlaceholder")}
                />
              </Form.Item>
            </div>
          </Card>

          <Card
            className={styles.card}
            title={t("botProfiles.profilesTitle")}
            extra={
              <Button
                icon={<PlusOutlined />}
                onClick={() => {
                  const existing = form.getFieldValue("profiles") || [];
                  form.setFieldsValue({
                    profiles: [...existing, { ...EMPTY_PROFILE }],
                  });
                }}
              >
                {t("botProfiles.addProfile")}
              </Button>
            }
          >
            <Form.List name="profiles">
              {(fields, { remove }) => (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  {fields.map((field) => (
                    <Card
                      key={field.key}
                      size="small"
                      className={styles.profileCard}
                      extra={
                        <Button
                          danger
                          type="text"
                          icon={<DeleteOutlined />}
                          onClick={() => remove(field.name)}
                        />
                      }
                    >
                      <div className={styles.profileGrid}>
                        <Form.Item
                          label={t("botProfiles.profileKey")}
                          name={[field.name, "key"]}
                          rules={[
                            {
                              required: true,
                              message: t("botProfiles.profileKeyRequired"),
                            },
                          ]}
                        >
                          <Input placeholder={t("botProfiles.profileKeyPlaceholder")} />
                        </Form.Item>

                        <Form.Item
                          label={t("botProfiles.profileName")}
                          name={[field.name, "name"]}
                          rules={[
                            {
                              required: true,
                              message: t("botProfiles.profileNameRequired"),
                            },
                          ]}
                        >
                          <Input
                            placeholder={t("botProfiles.profileNamePlaceholder")}
                          />
                        </Form.Item>

                        <Form.Item
                          label={t("botProfiles.profileEnabled")}
                          name={[field.name, "enabled"]}
                          valuePropName="checked"
                        >
                          <Switch />
                        </Form.Item>
                      </div>

                      <Form.Item
                        label={t("botProfiles.profileDescription")}
                        name={[field.name, "description"]}
                      >
                        <Input.TextArea rows={2} />
                      </Form.Item>

                      <Form.Item
                        label={t("botProfiles.identityPrompt")}
                        name={[field.name, "identity_prompt"]}
                      >
                        <Input.TextArea rows={4} />
                      </Form.Item>
                    </Card>
                  ))}
                </Space>
              )}
            </Form.List>
          </Card>

          <Card className={styles.card} title={t("botProfiles.channelBindingsTitle")}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              {channelTypes.map((channel) => (
                <div key={channel} className={styles.bindingRow}>
                  <span className={styles.channelLabel}>{channel}</span>
                  <Select
                    allowClear
                    value={channelBindings[channel]}
                    placeholder={t("botProfiles.unbound")}
                    options={(profiles || [])
                      .filter((profile) => profile?.key?.trim())
                      .map((profile) => ({
                        value: profile.key,
                        label: `${profile.name || profile.key} (${profile.key})`,
                      }))}
                    onChange={(value) => {
                      setChannelBindings((prev) => ({
                        ...prev,
                        [channel]: (value || "").trim(),
                      }));
                    }}
                    style={{ minWidth: 320 }}
                  />
                </div>
              ))}
            </Space>
          </Card>

          <div className={styles.footer}>
            <Button onClick={handleReset} disabled={saving}>
              {t("common.reset")}
            </Button>
            <Button type="primary" onClick={handleSave} loading={saving}>
              {t("common.save")}
            </Button>
          </div>
        </Form>
      </div>
    </div>
  );
}
