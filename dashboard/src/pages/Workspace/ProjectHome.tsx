import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button, Dropdown, Result, Segmented, Spin } from "antd";
import type { MenuProps } from "antd";
import {
  BarChart3,
  Bug,
  Clock,
  Code2,
  Coffee,
  Eye,
  FileText,
  FileSearch,
  FolderOpen,
  Lightbulb,
  Play,
  Plus,
  Presentation,
  Shield,
  ShieldCheck,
  Telescope,
  TestTube2,
  Wallet,
  Wrench,
} from "lucide-react";
import { message } from "@/utils/antdMessage";

import ChatInput, { type ChatInputHandle } from "../Chat/components/ChatInput";
import { useChatComposerResources } from "../Chat/hooks/useChatComposerResources";
import * as chatStore from "../Chat/hooks/chatStore";
import type { ChatAttachment } from "../Chat/hooks/sseHelpers";
import {
  buildComposerContext,
  resolveTurnModelRef,
} from "../Chat/utils/chatMessages";
import { parseSkillSlugsInText } from "../Chat/utils/skillSlash";
import { useSkills } from "../Agent/Skills/useSkills";
import WorkspaceDrawer from "../Agent/Workspace/components/WorkspaceDrawer";
import { useAgent } from "../../context/AgentContext";
import { octopAgentsApi } from "../../api/modules/octopAgents";
import type { WorkspaceProject } from "../../api/modules/projects";
import { useWorkspaceProjects } from "../../hooks/useWorkspaceProjects";
import { isAgentChatReady } from "../../utils/agentError";
import { apiErrorMessage } from "../../utils/apiError";
import styles from "./index.module.less";

type HomeMode = "work" | "code";

const MODE_STORAGE_KEY = "octop:workspace-home-mode";

function loadMode(): HomeMode {
  try {
    return localStorage.getItem(MODE_STORAGE_KEY) === "code" ? "code" : "work";
  } catch {
    return "work";
  }
}

const MODE_CHIPS: Record<HomeMode, { key: string; icon: typeof FileText }[]> = {
  work: [
    { key: "documents", icon: FileText },
    { key: "finance", icon: Wallet },
    { key: "data", icon: BarChart3 },
    { key: "slides", icon: Presentation },
    { key: "research", icon: Telescope },
    { key: "proposals", icon: Lightbulb },
    { key: "scheduled", icon: Clock },
  ],
  code: [
    { key: "explain", icon: FileSearch },
    { key: "fix", icon: Bug },
    { key: "tests", icon: TestTube2 },
    { key: "refactor", icon: Wrench },
    { key: "review", icon: Eye },
    { key: "run", icon: Play },
  ],
};

export default function ProjectHomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const { projects, loading } = useWorkspaceProjects();
  const project =
    projects.find((item) => item.project_id === projectId) ?? null;

  if (loading && !project) {
    return (
      <div className={styles.loading}>
        <Spin />
      </div>
    );
  }

  if (!project) {
    return (
      <Result
        status="404"
        title={t("workspace.notFound")}
        extra={
          <Button type="primary" onClick={() => navigate("/workspace")}>
            {t("workspace.backToProjects")}
          </Button>
        }
      />
    );
  }

  return <ProjectHome project={project} projects={projects} />;
}

function ProjectHome({
  project,
  projects,
}: {
  project: WorkspaceProject;
  projects: WorkspaceProject[];
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const composerRef = useRef<ChatInputHandle | null>(null);
  const [mode, setMode] = useState<HomeMode>(loadMode);
  const [filesOpen, setFilesOpen] = useState(false);
  const { agents, refresh: refreshAgents } = useAgent();
  const agent =
    agents.find((item) => item.agent_id === project.agent_id) ?? null;
  const ready = isAgentChatReady(agent?.state, agent);
  const startAttemptedRef = useRef(false);

  const {
    selectedModel,
    setSelectedModel,
    selectedConnectors,
    selectedKnowledgeBaseIds,
    chatConnectors,
    chatKnowledgeBases,
    availableModels,
    reasoningMode,
    reasoningEffort,
    handleReasoningChange,
    conversationMode,
    handleConversationModeChange,
    hitlPolicy,
    handleHitlPolicyChange,
    handleConnectorsChange,
    handleKnowledgeBaseIdsChange,
  } = useChatComposerResources(project.agent_id);
  const { skills } = useSkills(project.agent_id, { enabled: ready });

  const changeMode = useCallback((next: HomeMode) => {
    setMode(next);
    try {
      localStorage.setItem(MODE_STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!agent || ready || startAttemptedRef.current) return;
    startAttemptedRef.current = true;
    void octopAgentsApi
      .start(project.agent_id)
      .then(() => refreshAgents({ silent: true }))
      .catch(() => {
        /* The chat page surfaces a not-ready agent on send. */
      });
  }, [agent, ready, project.agent_id, refreshAgents]);

  const prefill = useCallback((prompt: string) => {
    composerRef.current?.setPrefillComposer(prompt);
    composerRef.current?.focusComposer();
  }, []);

  const handleSend = useCallback(
    (text: string, attachments?: ChatAttachment[]) => {
      const trimmed = text.trim();
      if (!trimmed && !(attachments && attachments.length > 0)) return;
      if (!ready) {
        void octopAgentsApi
          .start(project.agent_id)
          .then(() => refreshAgents({ silent: true }))
          .catch((err: unknown) => {
            message.error(apiErrorMessage(err, t("workspace.startFailed"), t));
          });
      }
      const composerContext = buildComposerContext({
        skills: parseSkillSlugsInText(trimmed),
        connectors: selectedConnectors,
        knowledgeBaseIds: selectedKnowledgeBaseIds,
        selectedModel,
        reasoningMode,
        reasoningEffort,
      });
      chatStore.setPendingAutoSend({
        agentId: project.agent_id,
        text: trimmed,
        attachments,
        overrides: {
          selectedConnectors,
          selectedKnowledgeBaseIds,
          composerContext,
          modelRef: resolveTurnModelRef(
            selectedModel,
            agent?.default_model ?? null,
          ),
          conversationMode,
          hitlPolicy,
        },
      });
      navigate(`/chat/${project.agent_id}`, { state: { newChat: true } });
    },
    [
      agent?.default_model,
      conversationMode,
      hitlPolicy,
      navigate,
      project.agent_id,
      ready,
      reasoningEffort,
      reasoningMode,
      refreshAgents,
      selectedConnectors,
      selectedKnowledgeBaseIds,
      selectedModel,
      t,
    ],
  );

  const workspaceMenu = useMemo<MenuProps>(
    () => ({
      items: [
        ...projects.map((item) => ({
          key: item.project_id,
          label: item.name,
        })),
        { type: "divider" as const },
        {
          key: "__new__",
          icon: <Plus size={14} />,
          label: t("workspace.newProject"),
        },
      ],
      selectedKeys: [project.project_id],
      onClick: ({ key }) => {
        if (key === "__new__") {
          navigate("/workspace", { state: { create: true } });
          return;
        }
        if (key !== project.project_id) navigate(`/workspace/${key}`);
      },
    }),
    [navigate, project.project_id, projects, t],
  );

  const permissionMenu = useMemo<MenuProps>(
    () => ({
      selectable: true,
      selectedKeys: [hitlPolicy.mode === "allow_all" ? "allow_all" : "ask"],
      items: [
        {
          key: "ask",
          icon: <Shield size={14} />,
          label: t("workspace.permissionAsk"),
        },
        {
          key: "allow_all",
          icon: <ShieldCheck size={14} />,
          label: t("workspace.permissionFullAccess"),
        },
      ],
      onClick: ({ key }) =>
        handleHitlPolicyChange(
          key === "allow_all" ? { mode: "allow_all" } : { mode: "ask" },
        ),
    }),
    [handleHitlPolicyChange, hitlPolicy.mode, t],
  );

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <h1 className={styles.title}>{project.name}</h1>
        <button
          type="button"
          className={styles.pathChip}
          title={project.working_dir ?? ""}
          onClick={() => setFilesOpen(true)}
        >
          <FolderOpen size={13} strokeWidth={1.8} />
          <span>{project.working_dir ?? "—"}</span>
        </button>

        <Segmented<HomeMode>
          className={styles.modeSwitch}
          value={mode}
          onChange={changeMode}
          options={[
            {
              value: "work",
              label: (
                <span className={styles.modeLabel}>
                  <Coffee size={14} strokeWidth={1.8} />
                  {t("workspace.modeWork")}
                </span>
              ),
            },
            {
              value: "code",
              label: (
                <span className={styles.modeLabel}>
                  <Code2 size={14} strokeWidth={1.8} />
                  {t("workspace.modeCode")}
                </span>
              ),
            },
          ]}
        />

        <div className={styles.chips}>
          {MODE_CHIPS[mode].map(({ key, icon: Icon }) => (
            <button
              key={key}
              type="button"
              className={styles.chip}
              onClick={() => prefill(t(`workspace.chips.${key}.prompt`))}
            >
              <Icon size={14} strokeWidth={1.8} />
              {t(`workspace.chips.${key}.label`)}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.composerWrap}>
        <ChatInput
          ref={composerRef}
          onSend={handleSend}
          onCancel={() => undefined}
          onNewChat={() => composerRef.current?.setPrefillComposer("")}
          isStreaming={false}
          agentId={project.agent_id}
          defaultModel={agent?.default_model ?? null}
          availableModels={availableModels}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          reasoningMode={reasoningMode}
          reasoningEffort={reasoningEffort}
          onReasoningChange={handleReasoningChange}
          conversationMode={conversationMode}
          onConversationModeChange={handleConversationModeChange}
          hitlPolicy={hitlPolicy}
          onHitlPolicyChange={handleHitlPolicyChange}
          availableConnectors={chatConnectors}
          selectedConnectors={selectedConnectors}
          onConnectorsChange={handleConnectorsChange}
          availableKnowledgeBases={chatKnowledgeBases}
          selectedKnowledgeBaseIds={selectedKnowledgeBaseIds}
          onKnowledgeBaseIdsChange={handleKnowledgeBaseIdsChange}
          availableSkills={skills}
          availableAgents={[]}
          availableExperts={[]}
        />
        <div className={styles.composerFooter}>
          <Dropdown menu={workspaceMenu} trigger={["click"]}>
            <Button type="text" size="small" className={styles.footerBtn}>
              <FolderOpen size={13} strokeWidth={1.8} />
              <span className={styles.footerLabel}>
                {t("workspace.selectWorkspace")}
              </span>
            </Button>
          </Dropdown>
          <Dropdown menu={permissionMenu} trigger={["click"]}>
            <Button type="text" size="small" className={styles.footerBtn}>
              {hitlPolicy.mode === "allow_all" ? (
                <ShieldCheck size={13} strokeWidth={1.8} />
              ) : (
                <Shield size={13} strokeWidth={1.8} />
              )}
              <span className={styles.footerLabel}>
                {hitlPolicy.mode === "allow_all"
                  ? t("workspace.permissionFullAccess")
                  : t("workspace.permissionAsk")}
              </span>
            </Button>
          </Dropdown>
        </div>
      </div>

      {mode === "code" ? (
        <WorkspaceDrawer
          agentId={project.agent_id}
          open={filesOpen}
          onClose={() => setFilesOpen(false)}
        />
      ) : null}
    </div>
  );
}
