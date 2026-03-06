import { Input, Select } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

interface FilterBarProps {
  filterUserId: string;
  filterChannel: string;
  filterBotId: string;
  uniqueChannels: string[];
  uniqueBots: string[];
  onUserIdChange: (value: string) => void;
  onChannelChange: (value: string) => void;
  onBotChange: (value: string) => void;
}

export function FilterBar({
  filterUserId,
  filterChannel,
  filterBotId,
  uniqueChannels,
  uniqueBots,
  onUserIdChange,
  onChannelChange,
  onBotChange,
}: FilterBarProps) {
  const { t } = useTranslation();

  return (
    <div className={styles.filterBar}>
      <Input
        placeholder={t("sessions.filterUserId")}
        value={filterUserId}
        onChange={(e) => onUserIdChange(e.target.value)}
        allowClear
        className="sessions-filter-input"
        style={{ width: 200 }}
      />
      <Select
        placeholder={t("sessions.filterChannel")}
        value={filterChannel || undefined}
        onChange={(value) => onChannelChange(value || "")}
        allowClear
        className="sessions-filter-select"
        style={{ width: 180 }}
      >
        {uniqueChannels.map((channel) => (
          <Select.Option key={channel} value={channel}>
            {channel}
          </Select.Option>
        ))}
      </Select>
      <Select
        placeholder={t("sessions.filterBot", { defaultValue: "Bot" })}
        value={filterBotId || undefined}
        onChange={(value) => onBotChange(value || "")}
        allowClear
        className="sessions-filter-select"
        style={{ width: 180 }}
      >
        {uniqueBots.map((bot) => (
          <Select.Option key={bot} value={bot}>
            {bot}
          </Select.Option>
        ))}
      </Select>
    </div>
  );
}
