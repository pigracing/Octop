import { useCallback, useEffect, useState } from "react";
import { projectsApi, type WorkspaceProject } from "../api/modules/projects";

/** Fired after a project is created / renamed / deleted. */
export const PROJECTS_CHANGED_EVENT = "octop:projects-changed";

export function notifyProjectsChanged(): void {
  window.dispatchEvent(new Event(PROJECTS_CHANGED_EVENT));
}

/**
 * Load the current user's workspace projects.
 *
 * Every mounted caller refetches on {@link PROJECTS_CHANGED_EVENT} so the
 * sidebar and the workspace pages stay in sync without a shared store.
 */
export function useWorkspaceProjects(): {
  projects: WorkspaceProject[];
  loading: boolean;
  error: unknown;
  refresh: () => Promise<void>;
} {
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await projectsApi.list();
      setProjects(list);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onChange = () => void refresh();
    window.addEventListener(PROJECTS_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(PROJECTS_CHANGED_EVENT, onChange);
  }, [refresh]);

  return { projects, loading, error, refresh };
}
