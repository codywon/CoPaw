import {
  AgentScopeRuntimeWebUI,
  IAgentScopeRuntimeWebUIOptions,
} from "@agentscope-ai/chat";
import { useEffect, useMemo, useRef, useState } from "react";
import { Modal, Button, Result } from "antd";
import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import sessionApi from "./sessionApi";
import { useLocalStorageState } from "ahooks";
import defaultConfig, { DefaultConfig } from "./OptionsPanel/defaultConfig";
import Weather from "./Weather";
import api from "../../api";
import { getApiUrl, getApiToken } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import { subscribeShowToolDetails } from "../../utils/showToolDetailsSync";
import "./index.module.less";

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

type OptionsConfig = DefaultConfig;

const TOOL_PROCESS_MESSAGE_TYPES = new Set([
  "plugin_call",
  "plugin_call_output",
  "function_call",
  "function_call_output",
  "component_call",
  "component_call_output",
  "mcp_call",
  "mcp_call_output",
]);

function isObjectLike(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null;
}

function toHeartbeatEvent(event: Record<string, any>): Record<string, any> {
  return {
    object: "message",
    type: "heartbeat",
    id:
      typeof event.id === "string" && event.id
        ? event.id
        : `heartbeat-${Date.now()}`,
    role: "assistant",
    status:
      typeof event.status === "string" ? event.status : "in_progress",
    content: [],
  };
}

function filterToolProcessEvent(
  event: unknown,
  showToolDetails: boolean,
  hiddenToolMessageIds: Set<string>,
): unknown {
  if (!isObjectLike(event)) return event;

  if (showToolDetails) {
    hiddenToolMessageIds.clear();
    return event;
  }

  if (event.object === "message") {
    const eventType = typeof event.type === "string" ? event.type : "";
    if (TOOL_PROCESS_MESSAGE_TYPES.has(eventType)) {
      if (typeof event.id === "string" && event.id) {
        hiddenToolMessageIds.add(event.id);
      }
      return toHeartbeatEvent(event);
    }
    return event;
  }

  if (event.object === "content") {
    const msgId = typeof event.msg_id === "string" ? event.msg_id : "";
    if (msgId && hiddenToolMessageIds.has(msgId)) {
      return toHeartbeatEvent({ id: msgId, status: event.status });
    }
    return event;
  }

  if (event.object === "response" && Array.isArray(event.output)) {
    const filtered = {
      ...event,
      output: event.output.filter(
        (item: any) => !TOOL_PROCESS_MESSAGE_TYPES.has(item?.type),
      ),
    };
    if (
      event.status === "completed" ||
      event.status === "failed" ||
      event.status === "canceled"
    ) {
      hiddenToolMessageIds.clear();
    }
    return filtered;
  }

  return event;
}

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const showToolDetailsRef = useRef(true);
  const hiddenToolMessageIdsRef = useRef<Set<string>>(new Set());
  const [optionsConfig] = useLocalStorageState<OptionsConfig>(
    "agent-scope-runtime-webui-options",
    {
      defaultValue: defaultConfig,
      listenStorageChange: true,
    },
  );

  const handleConfigureModel = () => {
    setShowModelPrompt(false);
    navigate("/models");
  };

  const handleSkipConfiguration = () => {
    setShowModelPrompt(false);
  };

  useEffect(() => {
    const applyShowToolDetails = (value: boolean) => {
      if (showToolDetailsRef.current !== value) {
        hiddenToolMessageIdsRef.current.clear();
      }
      showToolDetailsRef.current = value;
    };

    const syncShowToolDetails = async () => {
      try {
        const result = await api.getShowToolDetails();
        applyShowToolDetails(result.show_tool_details);
      } catch (error) {
        console.error("Failed to sync show_tool_details in chat:", error);
      }
    };

    const onVisibilityChange = () => {
      if (!document.hidden) {
        void syncShowToolDetails();
      }
    };

    const unsubscribe = subscribeShowToolDetails(applyShowToolDetails);
    void syncShowToolDetails();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      unsubscribe();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  const options = useMemo(() => {
    const handleModelError = () => {
      setShowModelPrompt(true);
      return new Response(
        JSON.stringify({
          error: "Model not configured",
          message: "Please configure a model first",
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      );
    };

    const customFetch = async (data: {
      input: any[];
      biz_params?: any;
      signal?: AbortSignal;
    }): Promise<Response> => {
      try {
        const activeModels = await providerApi.getActiveModels();

        if (
          !activeModels?.active_llm?.provider_id ||
          !activeModels?.active_llm?.model
        ) {
          return handleModelError();
        }
      } catch (error) {
        console.error("Failed to check model configuration:", error);
        return handleModelError();
      }

      hiddenToolMessageIdsRef.current.clear();

      const { input, biz_params } = data;

      const lastMessage = input[input.length - 1];
      const session = lastMessage?.session || {};

      const session_id = window.currentSessionId || session?.session_id || "";
      const user_id = window.currentUserId || session?.user_id || "default";
      const channel = window.currentChannel || session?.channel || "console";

      const requestBody = {
        input: input.slice(-1),
        session_id,
        user_id,
        channel,
        stream: true,
        ...biz_params,
      };

      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };

      const token = getApiToken();
      if (token) {
        (headers as Record<string, string>).Authorization = `Bearer ${token}`;
      }

      const url = optionsConfig?.api?.baseURL || getApiUrl("/agent/process");
      return fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
        signal: data.signal,
      });
    };

    return {
      ...optionsConfig,
      session: {
        multiple: true,
        api: sessionApi,
      },
      theme: {
        ...optionsConfig.theme,
      },
      api: {
        ...optionsConfig.api,
        fetch: customFetch,
        responseParser: (chunk: string) => {
          const parsed = JSON.parse(chunk);
          return filterToolProcessEvent(
            parsed,
            showToolDetailsRef.current,
            hiddenToolMessageIdsRef.current,
          );
        },
        cancel(data: { session_id: string }) {
          console.log(data);
        },
      },
      customToolRenderConfig: {
        "weather search mock": Weather,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [optionsConfig]);

  return (
    <div style={{ height: "100%", width: "100%" }}>
      <AgentScopeRuntimeWebUI options={options} />

      <Modal open={showModelPrompt} closable={false} footer={null} width={480}>
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#faad14" }} />}
          title={t("modelConfig.promptTitle")}
          subTitle={t("modelConfig.promptMessage")}
          extra={[
            <Button key="skip" onClick={handleSkipConfiguration}>
              {t("modelConfig.skipButton")}
            </Button>,
            <Button
              key="configure"
              type="primary"
              icon={<SettingOutlined />}
              onClick={handleConfigureModel}
            >
              {t("modelConfig.configureButton")}
            </Button>,
          ]}
        />
      </Modal>
    </div>
  );
}
