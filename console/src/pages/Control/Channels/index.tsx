import { useEffect, useMemo, useState } from "react";
import { Form, Switch, message } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";

import api from "../../../api";
import type { SingleChannelConfig } from "../../../api/types";
import {
  ChannelCard,
  ChannelDrawer,
  useChannels,
  CHANNEL_LABELS,
  type ChannelKey,
} from "./components";
import { publishShowToolDetails } from "../../../utils/showToolDetailsSync";
import styles from "./index.module.less";

function ChannelsPage() {
  const { t } = useTranslation();
  const { channels, loading, fetchChannels } = useChannels();
  const [saving, setSaving] = useState(false);
  const [showToolDetails, setShowToolDetails] = useState(true);
  const [loadingShowToolDetails, setLoadingShowToolDetails] = useState(true);
  const [savingShowToolDetails, setSavingShowToolDetails] = useState(false);
  const [hoverKey, setHoverKey] = useState<ChannelKey | null>(null);
  const [activeKey, setActiveKey] = useState<ChannelKey | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [form] = Form.useForm<SingleChannelConfig>();

  useEffect(() => {
    let mounted = true;

    const fetchShowToolDetails = async () => {
      setLoadingShowToolDetails(true);
      try {
        const result = await api.getShowToolDetails();
        if (mounted) {
          setShowToolDetails(result.show_tool_details);
        }
      } catch (error) {
        console.error("Failed to load show_tool_details:", error);
        if (mounted) {
          message.error(t("channels.showToolDetailsLoadFailed"));
        }
      } finally {
        if (mounted) {
          setLoadingShowToolDetails(false);
        }
      }
    };

    void fetchShowToolDetails();

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
      console.error("❌ Failed to update channel config:", error);
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
    </div>
  );
}

export default ChannelsPage;
