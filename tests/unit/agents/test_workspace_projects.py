"""Workspace project helpers and working-directory safety."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from octop.infra.agents.projects import (
    PROJECT_CONFIG_KEY,
    find_project_by_working_dir,
    is_project_row,
    project_config,
    project_payload,
    project_working_dir,
    resolve_project_working_dir,
)
from octop.infra.agents.workspace.dir import agent_host_data_dirs
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.paths import PathLayout


def _row(agent_id: str, name: str, cfg: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        agent_id=agent_id,
        name=name,
        description=None,
        config_json=json.dumps(cfg),
        last_state="running",
        last_error=None,
        icon_name=None,
        created_at=1,
        updated_at=2,
    )


@pytest.fixture
def paths(tmp_path: Path) -> PathLayout:
    return PathLayout(tmp_path / ".octop")


def test_project_config_binds_backend_and_workspace(tmp_path: Path) -> None:
    workdir = str(tmp_path / "project")
    cfg = project_config(workdir)

    assert cfg["workspace_dir"] == workdir
    assert cfg["backend"] == {
        "type": "local_shell",
        "root_dir": workdir,
        "virtual_mode": True,
    }
    assert project_working_dir(cfg) == workdir


def test_resolve_creates_folder(paths: PathLayout, tmp_path: Path) -> None:
    target = tmp_path / "new" / "project"

    resolved = resolve_project_working_dir(str(target), paths=paths)

    assert Path(resolved).is_dir()
    assert Path(resolved) == target.resolve()


def test_resolve_rejects_relative_path(paths: PathLayout) -> None:
    with pytest.raises(OctopError) as exc:
        resolve_project_working_dir("relative/project", paths=paths)
    assert exc.value.code is ErrorCode.PROJECT_WORKDIR_INVALID


def test_resolve_rejects_home(paths: PathLayout) -> None:
    with pytest.raises(OctopError):
        resolve_project_working_dir(str(Path.home()), paths=paths)


def test_resolve_rejects_octop_home(paths: PathLayout) -> None:
    with pytest.raises(OctopError):
        resolve_project_working_dir(str(paths.root / "somewhere"), paths=paths)


def test_resolve_rejects_existing_file(paths: PathLayout, tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")

    with pytest.raises(OctopError):
        resolve_project_working_dir(str(target), paths=paths)


def test_find_project_by_working_dir_matches_resolved_path(
    tmp_path: Path,
) -> None:
    workdir = str((tmp_path / "project").resolve())
    rows = [_row("abc", "Demo", project_config(workdir))]

    assert find_project_by_working_dir(rows, workdir) is rows[0]
    assert find_project_by_working_dir(rows, str(tmp_path / "other")) is None


def test_payload_and_row_marker(tmp_path: Path) -> None:
    workdir = str(tmp_path / "project")
    row = _row("abc", "Demo", project_config(workdir))

    assert is_project_row(row) is True
    payload = project_payload(row)
    assert payload["project_id"] == "abc"
    assert payload["working_dir"] == workdir


def test_delete_dirs_skip_project_working_directory(
    paths: PathLayout,
    tmp_path: Path,
) -> None:
    """A project workspace *is* user data: never delete it with the agent."""
    workdir = (tmp_path / "project").resolve()
    cfg = project_config(str(workdir))

    dirs = agent_host_data_dirs(cfg, paths=paths, agent_id="abc")

    assert workdir not in dirs
    assert paths.agent_workspace("abc") in dirs


def test_delete_dirs_keep_regular_workspace(
    paths: PathLayout,
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "agent-home"
    cfg = {
        "workspace_dir": str(workdir),
        "backend": {"type": "local_shell", "root_dir": "/", "virtual_mode": True},
    }

    dirs = agent_host_data_dirs(cfg, paths=paths, agent_id="abc")

    assert workdir.resolve() in dirs


def test_project_marker_absent_for_normal_agent() -> None:
    assert is_project_row(_row("abc", "Expert", {"workspace_dir": "/tmp/x"})) is False
    assert project_working_dir({PROJECT_CONFIG_KEY: "bad"}) is None
