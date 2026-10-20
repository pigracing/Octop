import { request } from "../request";

export interface WorkspaceProject {
  project_id: string;
  agent_id: string;
  name: string;
  description: string | null;
  working_dir: string | null;
  state: string;
  last_error: string | null;
  icon_name: string | null;
  created_at: number;
  updated_at: number;
}

export interface ProjectCreateInput {
  name: string;
  working_dir: string;
  description?: string;
}

export interface ProjectUpdateInput {
  name?: string;
  description?: string;
}

export const projectsApi = {
  list: () => request<WorkspaceProject[]>("/projects"),

  create: (body: ProjectCreateInput) =>
    request<WorkspaceProject>("/projects", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  update: (projectId: string, body: ProjectUpdateInput) =>
    request<WorkspaceProject>(`/projects/${encodeURIComponent(projectId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  remove: (projectId: string) =>
    request<void>(`/projects/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
    }),
};
