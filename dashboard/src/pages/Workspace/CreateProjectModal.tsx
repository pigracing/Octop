import { useEffect, useState } from "react";
import { Form, Input, Modal } from "antd";
import { useTranslation } from "react-i18next";
import { message } from "@/utils/antdMessage";

import RootDirSelect from "../Experts/components/RootDirSelect";
import {
  fetchFilesystemDefaults,
  type FilesystemDefaults,
} from "../Experts/components/agentBackendForm";
import { projectsApi, type WorkspaceProject } from "../../api/modules/projects";
import { apiErrorMessage } from "../../utils/apiError";
import { notifyProjectsChanged } from "../../hooks/useWorkspaceProjects";

interface ProjectFormValues {
  name: string;
  working_dir?: string;
  description?: string;
}

interface CreateProjectModalProps {
  open: boolean;
  /** Existing project to rename; omit to create a new one. */
  editing?: WorkspaceProject | null;
  onClose: () => void;
  onSaved: (project: WorkspaceProject) => void;
}

export default function CreateProjectModal({
  open,
  editing = null,
  onClose,
  onSaved,
}: CreateProjectModalProps) {
  const { t } = useTranslation();
  const [form] = Form.useForm<ProjectFormValues>();
  const [fsDefaults, setFsDefaults] = useState<FilesystemDefaults | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    if (editing) {
      form.setFieldsValue({
        name: editing.name,
        description: editing.description ?? "",
      });
      return;
    }
    void fetchFilesystemDefaults()
      .then(setFsDefaults)
      .catch(() => setFsDefaults(null));
  }, [open, editing, form]);

  const treeRoots = fsDefaults
    ? fsDefaults.browse_roots?.length
      ? fsDefaults.browse_roots
      : fsDefaults.tree_root
    : undefined;

  const handleSubmit = async () => {
    let values: ProjectFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setSaving(true);
    try {
      const name = values.name.trim();
      const description = values.description?.trim() || undefined;
      const project = editing
        ? await projectsApi.update(editing.project_id, { name, description })
        : await projectsApi.create({
            name,
            working_dir: values.working_dir!.trim(),
            description,
          });
      notifyProjectsChanged();
      message.success(
        editing ? t("workspace.updated") : t("workspace.created"),
      );
      onSaved(project);
    } catch (err) {
      message.error(apiErrorMessage(err, t("workspace.projectSaveFailed"), t));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title={editing ? t("workspace.editProject") : t("workspace.newProject")}
      okText={editing ? t("common.save") : t("workspace.create")}
      cancelText={t("common.cancel")}
      confirmLoading={saving}
      onOk={() => void handleSubmit()}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          name="name"
          label={t("workspace.projectName")}
          rules={[
            { required: true, message: t("workspace.projectNameRequired") },
          ]}
        >
          <Input
            placeholder={t("workspace.projectNamePlaceholder")}
            maxLength={80}
            autoFocus
          />
        </Form.Item>
        {!editing && (
          <Form.Item
            name="working_dir"
            label={t("workspace.workingDir")}
            rules={[
              { required: true, message: t("workspace.workingDirRequired") },
            ]}
            extra={t("workspace.workingDirHint")}
          >
            <RootDirSelect treeRoots={treeRoots} />
          </Form.Item>
        )}
        <Form.Item name="description" label={t("workspace.description")}>
          <Input.TextArea
            placeholder={t("workspace.descriptionPlaceholder")}
            rows={2}
            maxLength={300}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
