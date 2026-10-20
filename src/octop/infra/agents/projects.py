"""Workspace projects: agents bound to a user-chosen working directory.

A project is not a new persistence concept — it is a regular agent whose
backend is scoped to ``working_dir`` and whose ``workspace_dir`` *is* that
directory. The marker key :data:`PROJECT_CONFIG_KEY` lets the dashboard list
project agents separately from ordinary experts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from octop.infra.agents.settings.profile import parse_config_json
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.host_dirs import assert_safe_host_path, host_home_dir
from octop.infra.utils.paths import PathLayout

PROJECT_CONFIG_KEY = "workspace_project"


def project_working_dir(cfg: dict[str, Any] | None) -> str | None:
    """Return the project working directory stored in *cfg*, if any."""
    marker = (cfg or {}).get(PROJECT_CONFIG_KEY)
    if not isinstance(marker, dict):
        return None
    raw = marker.get("working_dir")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text or None


def is_project_config(cfg: dict[str, Any] | None) -> bool:
    return project_working_dir(cfg) is not None


def is_project_row(row: Any) -> bool:
    """True when the agent row carries the project marker."""
    return is_project_config(parse_config_json(getattr(row, "config_json", None)))


def project_config(working_dir: str) -> dict[str, Any]:
    """Harness config for a project agent bound to *working_dir*."""
    return {
        "backend": {
            "type": "local_shell",
            "root_dir": working_dir,
            "virtual_mode": True,
        },
        "workspace_dir": working_dir,
        PROJECT_CONFIG_KEY: {"working_dir": working_dir},
    }


def project_payload(row: Any) -> dict[str, Any]:
    """JSON-ready project view for the dashboard."""
    cfg = parse_config_json(getattr(row, "config_json", None))
    return {
        "project_id": row.agent_id,
        "agent_id": row.agent_id,
        "name": row.name,
        "description": row.description,
        "working_dir": project_working_dir(cfg),
        "state": row.last_state or "unknown",
        "last_error": row.last_error,
        "icon_name": row.icon_name or cfg.get("icon_name"),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _invalid_workdir(detail: str) -> OctopError:
    return OctopError(
        ErrorCode.PROJECT_WORKDIR_INVALID,
        detail,
        details={"detail": detail},
    )


def _is_self_or_parent(path: Path, child: Path) -> bool:
    """True when *path* is *child* or one of its ancestors."""
    try:
        child.relative_to(path)
        return True
    except ValueError:
        return False


def resolve_project_working_dir(raw: str, *, paths: PathLayout) -> str:
    """Validate and create the project working directory.

    Returns the canonical host path. Raises ``PROJECT_WORKDIR_INVALID`` for
    relative paths, filesystem roots, the home directory, Octop's own data
    directory, or a path that cannot be created / written.
    """
    text = (raw or "").strip()
    if not text:
        raise _invalid_workdir("working directory is required")
    candidate = Path(os.path.expanduser(text))
    if not candidate.is_absolute():
        raise _invalid_workdir("working directory must be an absolute path")
    try:
        resolved = Path(os.path.realpath(str(candidate)))
    except OSError as exc:
        raise _invalid_workdir(str(exc)) from exc

    if resolved.parent == resolved:
        raise _invalid_workdir("the filesystem root cannot be a project working directory")

    home = host_home_dir()
    if _is_self_or_parent(resolved, home):
        raise _invalid_workdir(
            "the home directory or one of its parents cannot be a project working directory"
        )

    octop_root = Path(os.path.realpath(str(paths.root.expanduser())))
    if _is_self_or_parent(resolved, octop_root) or _is_self_or_parent(octop_root, resolved):
        raise _invalid_workdir(
            "Octop's data directory cannot be used as a project working directory"
        )

    try:
        assert_safe_host_path(str(resolved), restrict_to_home=False)
    except ValueError as exc:
        raise _invalid_workdir(str(exc)) from exc

    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _invalid_workdir(str(exc)) from exc
    if not resolved.is_dir():
        raise _invalid_workdir("working directory is not a directory")
    if not os.access(resolved, os.R_OK | os.W_OK | os.X_OK):
        raise _invalid_workdir("working directory is not writable")
    return resolved.as_posix()


def find_project_by_working_dir(rows: list[Any], working_dir: str) -> Any | None:
    """Return the first project row already using *working_dir*."""
    target = os.path.normcase(working_dir)
    for row in rows:
        if not is_project_row(row):
            continue
        existing = project_working_dir(parse_config_json(getattr(row, "config_json", None)))
        if existing is None:
            continue
        if os.path.normcase(existing) == target:
            return row
    return None
