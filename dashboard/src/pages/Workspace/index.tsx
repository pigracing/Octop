import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button, Dropdown, Empty, Spin, Tooltip } from "antd";
import type { MenuProps } from "antd";
import {
  FolderKanban,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { message } from "@/utils/antdMessage";

import PageShell from "../../layouts/PageShell";
import { projectsApi, type WorkspaceProject } from "../../api/modules/projects";
import {
  notifyProjectsChanged,
  useWorkspaceProjects,
} from "../../hooks/useWorkspaceProjects";
import { showConfirmModal } from "../../utils/confirmModal";
import { apiErrorMessage } from "../../utils/apiError";
import { formatServerDateTime } from "../../utils/formatMessageTime";
import { useServerTimezone } from "../../hooks/useServerTimezone";
import CreateProjectModal from "./CreateProjectModal";
import styles from "./index.module.less";

export default function WorkspacePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const timeZone = useServerTimezone();
  const { projects, loading, refresh } = useWorkspaceProjects();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<WorkspaceProject | null>(null);

  useEffect(() => {
    if ((location.state as { create?: boolean } | null)?.create) {
      setEditing(null);
      setModalOpen(true);
      navigate(location.pathname, { replace: true, state: null });
    }
    // Only on mount / when the one-shot router state arrives.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  const openCreate = () => {
    setEditing(null);
    setModalOpen(true);
  };

  const openEdit = (project: WorkspaceProject) => {
    setEditing(project);
    setModalOpen(true);
  };

  const handleDelete = (project: WorkspaceProject) => {
    showConfirmModal({
      title: t("workspace.deleteTitle", { name: project.name }),
      content: t("workspace.deleteBody"),
      okText: t("common.delete"),
      okButtonProps: { danger: true },
      cancelText: t("common.cancel"),
      onOk: async () => {
        try {
          await projectsApi.remove(project.project_id);
          notifyProjectsChanged();
          message.success(t("workspace.deleted"));
        } catch (err) {
          message.error(
            apiErrorMessage(err, t("workspace.projectDeleteFailed"), t),
          );
          throw err;
        }
      },
    });
  };

  const menuFor = useMemo(
    () =>
      (project: WorkspaceProject): MenuProps => ({
        items: [
          {
            key: "edit",
            icon: <Pencil size={14} />,
            label: t("common.edit"),
          },
          { type: "divider" },
          {
            key: "delete",
            danger: true,
            icon: <Trash2 size={14} />,
            label: t("common.delete"),
          },
        ],
        onClick: ({ key, domEvent }) => {
          domEvent.stopPropagation();
          if (key === "edit") openEdit(project);
          if (key === "delete") handleDelete(project);
        },
      }),
    // openEdit/handleDelete close over t only; recreating per render is fine.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  return (
    <PageShell
      title={t("workspace.title")}
      subtitle={t("workspace.subtitle")}
      fill
      actions={
        <div className={styles.actions}>
          <Tooltip title={t("common.refresh")}>
            <Button
              icon={<RefreshCw size={15} />}
              onClick={() => void refresh()}
            />
          </Tooltip>
          <Button type="primary" icon={<Plus size={15} />} onClick={openCreate}>
            {t("workspace.newProject")}
          </Button>
        </div>
      }
    >
      <div className={styles.scroll}>
        {loading ? (
          <div className={styles.centered}>
            <Spin />
          </div>
        ) : projects.length === 0 ? (
          <div className={styles.centered}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <div className={styles.emptyText}>
                  <div className={styles.emptyTitle}>
                    {t("workspace.emptyTitle")}
                  </div>
                  <div>{t("workspace.emptyHint")}</div>
                </div>
              }
            >
              <Button
                type="primary"
                icon={<Plus size={15} />}
                onClick={openCreate}
              >
                {t("workspace.newProject")}
              </Button>
            </Empty>
          </div>
        ) : (
          <div className={styles.grid}>
            {projects.map((project) => (
              <div
                key={project.project_id}
                className={styles.card}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/workspace/${project.project_id}`)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    navigate(`/workspace/${project.project_id}`);
                  }
                }}
              >
                <div className={styles.cardTop}>
                  <span className={styles.cardIcon}>
                    <FolderKanban size={18} strokeWidth={1.8} />
                  </span>
                  <Dropdown
                    menu={menuFor(project)}
                    trigger={["click"]}
                    placement="bottomRight"
                  >
                    <Button
                      type="text"
                      size="small"
                      className={styles.cardMenuBtn}
                      icon={<MoreHorizontal size={16} />}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={t("workspace.projectActions")}
                    />
                  </Dropdown>
                </div>
                <div className={styles.cardName}>{project.name}</div>
                <div
                  className={styles.cardPath}
                  title={project.working_dir ?? ""}
                >
                  {project.working_dir ?? "—"}
                </div>
                {project.description ? (
                  <div className={styles.cardDesc}>{project.description}</div>
                ) : null}
                <div className={styles.cardMeta}>
                  {t("workspace.updatedAt", {
                    time: formatServerDateTime(project.updated_at, timeZone),
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <CreateProjectModal
        open={modalOpen}
        editing={editing}
        onClose={() => setModalOpen(false)}
        onSaved={(project) => {
          setModalOpen(false);
          if (editing) {
            void refresh();
            return;
          }
          navigate(`/workspace/${project.project_id}`);
        }}
      />
    </PageShell>
  );
}
