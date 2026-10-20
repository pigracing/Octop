"""Workspace projects router.

A project is an agent whose backend and workspace are bound to a user-chosen
host directory; see :mod:`octop.infra.agents.projects`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from octop.api.common.agent import assert_agent_owner
from octop.api.common.validators import assert_user_backend_root_dirs
from octop.api.deps import current_user, get_server
from octop.infra.agents import projects as project_service
from octop.infra.errors import ErrorCode, OctopError

router = APIRouter()


class ProjectCreateBody(BaseModel):
    name: str = Field(..., min_length=1, description="Project name, unique per user")
    working_dir: str = Field(
        ...,
        description="Absolute host directory the project agent works in",
    )
    description: str | None = Field(None, description="Optional project description")


class ProjectPatchBody(BaseModel):
    name: str | None = Field(None, min_length=1, description="New project name")
    description: str | None = Field(None, description="New project description")


def _project_row(server: Any, project_id: str, user: Any) -> Any:
    assert server.app_runtime is not None
    row = server.app_runtime.agent_registry.get_row(project_id)
    if row is None or not project_service.is_project_row(row):
        raise OctopError(
            ErrorCode.PROJECT_NOT_FOUND,
            f"project {project_id!r} not found",
        )
    assert_agent_owner(row, user)
    return row


@router.get("", summary="List workspace projects")
async def list_projects(
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> list[dict[str, Any]]:
    """Return the current user's projects (newest first)."""
    assert server.app_runtime is not None
    rows = server.app_runtime.agent_registry.list_agents(user.id)
    payloads = [
        project_service.project_payload(row) for row in rows if project_service.is_project_row(row)
    ]
    return sorted(payloads, key=lambda item: item["created_at"], reverse=True)


@router.post("", status_code=201, summary="Create a workspace project")
async def create_project(
    body: ProjectCreateBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    """Create a project agent bound to ``working_dir`` and start it."""
    from octop.infra.agents.manager import AgentCreateSpec  # noqa: PLC0415

    assert server.app_runtime is not None
    registry = server.app_runtime.agent_registry
    working_dir = project_service.resolve_project_working_dir(
        body.working_dir,
        paths=server.services.paths,
    )
    config = project_service.project_config(working_dir)
    assert_user_backend_root_dirs(
        user,
        config.get("backend"),
        policy_repo=server.services.user_policy_repo,
    )
    existing = project_service.find_project_by_working_dir(
        registry.list_agents(user.id),
        working_dir,
    )
    if existing is not None:
        raise OctopError(
            ErrorCode.PROJECT_WORKDIR_INVALID,
            f"working directory already used by project {existing.name!r}",
            details={"detail": f"already used by project {existing.name!r}"},
        )
    row = await registry.create(
        AgentCreateSpec(
            name=body.name.strip(),
            user_id=user.id,
            description=body.description,
            config=config,
        )
    )
    return project_service.project_payload(row)


@router.patch("/{project_id}", summary="Update a workspace project")
async def update_project(
    project_id: str,
    body: ProjectPatchBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    """Rename a project or change its description."""
    assert server.app_runtime is not None
    _project_row(server, project_id, user)
    updates = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None
    }
    row = (
        await server.app_runtime.agent_registry.update(project_id, **updates)
        if updates
        else server.app_runtime.agent_registry.get_row(project_id)
    )
    assert row is not None
    return project_service.project_payload(row)


@router.delete("/{project_id}", status_code=204, summary="Delete a workspace project")
async def delete_project(
    project_id: str,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> None:
    """Remove the project agent. The working directory itself is kept."""
    assert server.app_runtime is not None
    _project_row(server, project_id, user)
    await server.app_runtime.agent_registry.delete(project_id)
