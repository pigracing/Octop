#!/usr/bin/env bash
# Build the desktop client for macOS, Windows and Linux in one command.
#
# The current host is packaged natively (Wails requires a native runner for the
# GUI package); every other selected platform is built by the existing
# octop-desktop.yml GitHub Actions matrix and downloaded into desktop/release/.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=desktop/portable/_common.sh
source "${REPO_ROOT}/desktop/portable/_common.sh"

usage() {
  cat <<'EOF'
Usage: desktop/package-all.sh [options]

Options:
  --platforms LIST   Comma-separated plats, or "all" (default).
                     all = darwin-arm64,darwin-amd64,linux-amd64,linux-arm64,
                           windows-amd64,windows-arm64
  --reuse-portable   Reuse an existing portable zip for the native platform.
  --skip-local       Do not build the native platform locally.
  --skip-ci          Do not dispatch the GitHub Actions matrix.
  -h, --help         Show this help.

Artifacts are collected under desktop/release/<version>/.
EOF
}

platforms_arg="all"
reuse_portable=0
skip_local=0
skip_ci=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --platforms)
      [[ $# -ge 2 ]] || { echo "--platforms needs a value" >&2; exit 2; }
      platforms_arg="$2"
      shift 2
      ;;
    --platforms=*)
      platforms_arg="${1#*=}"
      shift
      ;;
    --reuse-portable) reuse_portable=1; shift ;;
    --skip-local) skip_local=1; shift ;;
    --skip-ci) skip_ci=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$skip_local" == 1 && "$skip_ci" == 1 ]]; then
  echo "nothing to do: --skip-local and --skip-ci are both set" >&2
  exit 2
fi

selected=()
if [[ "$(printf '%s' "$platforms_arg" | tr '[:upper:]' '[:lower:]')" == "all" ]]; then
  selected=("${ALL_PLATS[@]}")
else
  IFS=',' read -r -a requested <<< "$platforms_arg"
  for plat in "${requested[@]}"; do
    plat="${plat// /}"
    [[ -z "$plat" ]] && continue
    if ! is_known_plat "$plat"; then
      echo "unknown platform: $plat" >&2
      exit 2
    fi
    selected+=("$plat")
  done
fi
if [[ ${#selected[@]} -eq 0 ]]; then
  echo "no platforms selected" >&2
  exit 2
fi

contains() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

version="$(octop_version)"
release_dir="${REPO_ROOT}/desktop/release/${version}"
mkdir -p "$release_dir"

echo "[package-all] version=${version} platforms=${selected[*]}"
echo "[package-all] applying branding"
if python3 -c "import PIL" >/dev/null 2>&1; then
  python3 "${REPO_ROOT}/desktop/src/build/apply_branding.py"
elif command -v uv >/dev/null 2>&1; then
  uv run --no-project --with pillow python "${REPO_ROOT}/desktop/src/build/apply_branding.py"
else
  echo "[package-all] Pillow is required; run 'python3 -m pip install pillow' or install uv." >&2
  exit 1
fi
display_name="$(cat "${REPO_ROOT}/desktop/src/build/branding/display_name.txt")"
echo "[package-all] display_name=${display_name}"

host="$(host_plat 2>/dev/null || true)"
local_platform=""
if [[ "$skip_local" == 0 && -n "$host" ]] && contains "$host" "${selected[@]}"; then
  local_platform="$host"
fi

if [[ -n "$local_platform" ]] && ! command -v wails3 >/dev/null 2>&1; then
  echo "[package-all] wails3 is required for local packaging:" >&2
  echo "[package-all]   go install github.com/wailsapp/wails/v3/cmd/wails3@v3.0.0-beta.13" >&2
  local_platform=""
fi

if [[ -n "$local_platform" ]]; then
  echo "[package-all] building Dashboard once"
  make -C "$REPO_ROOT" build-frontend
fi

failed=()
completed=()

if [[ -n "$local_platform" ]]; then
  echo "[package-all] building ${local_platform} natively"
  local_args=("$local_platform" --skip-frontend)
  if [[ "$reuse_portable" == 1 ]]; then
    local_args+=(--reuse-portable)
  fi
  if bash "${REPO_ROOT}/desktop/package-release.sh" "${local_args[@]}"; then
    pkg="${REPO_ROOT}/desktop/src/bin/$(desktop_pkg_basename "$local_platform")"
    zip="${REPO_ROOT}/desktop/portable/release/$(portable_zip_basename "$local_platform")"
    if [[ -s "$pkg" ]]; then
      cp -f "$pkg" "$release_dir/"
    else
      echo "[package-all] missing local package: ${pkg}" >&2
      failed+=("$local_platform")
    fi
    if [[ -s "$zip" ]]; then
      cp -f "$zip" "$release_dir/"
    fi
    completed+=("$local_platform")
  else
    echo "[package-all] local build failed for ${local_platform}; falling back to CI" >&2
  fi
fi

remaining=()
for plat in "${selected[@]}"; do
  if [[ ${#completed[@]} -gt 0 && "$plat" == "$local_platform" ]] && contains "$local_platform" "${completed[@]}"; then
    continue
  fi
  remaining+=("$plat")
done

if [[ ${#remaining[@]} -gt 0 && "$skip_ci" == 0 ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "[package-all] gh CLI is required for non-native platforms: ${remaining[*]}" >&2
    failed+=("${remaining[@]}")
  elif ! gh auth status >/dev/null 2>&1; then
    echo "[package-all] gh is not authenticated; run 'gh auth login'" >&2
    failed+=("${remaining[@]}")
  else
    branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
    if [[ -z "$branch" || "$branch" == "HEAD" ]]; then
      echo "[package-all] CI builds need a branch with an upstream" >&2
      failed+=("${remaining[@]}")
    elif ! git -C "$REPO_ROOT" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
      echo "[package-all] branch ${branch} has no upstream; push it first" >&2
      failed+=("${remaining[@]}")
    elif [[ "$(git -C "$REPO_ROOT" rev-list --count '@{u}..HEAD')" != "0" ]]; then
      echo "[package-all] branch ${branch} has unpushed commits; push them first" >&2
      failed+=("${remaining[@]}")
    elif [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- desktop dashboard src/octop/i18n)" ]]; then
      echo "[package-all] uncommitted branding/build changes; CI would use the pushed ref." >&2
      echo "[package-all] commit and push desktop/, dashboard/, src/octop/i18n/ first." >&2
      failed+=("${remaining[@]}")
    else
      plats_csv="$(IFS=,; echo "${remaining[*]}")"
      echo "[package-all] dispatching CI for ${plats_csv}"
      before="$(gh run list --workflow octop-desktop.yml --branch "$branch" \
        --limit 1 --json databaseId --jq '.[0].databaseId // empty' 2>/dev/null || true)"
      if ! gh workflow run octop-desktop.yml --ref "$branch" \
        -f platforms="$plats_csv" -f attach_release=false; then
        failed+=("${remaining[@]}")
      else
        run_id=""
        for _ in $(seq 1 30); do
          sleep 5
          latest="$(gh run list --workflow octop-desktop.yml --branch "$branch" \
            --limit 1 --json databaseId --jq '.[0].databaseId // empty' 2>/dev/null || true)"
          if [[ -n "$latest" && "$latest" != "$before" ]]; then
            run_id="$latest"
            break
          fi
        done
        if [[ -z "$run_id" ]]; then
          echo "[package-all] could not find the dispatched CI run" >&2
          failed+=("${remaining[@]}")
        elif ! gh run watch "$run_id" --exit-status; then
          echo "[package-all] CI run ${run_id} failed" >&2
          failed+=("${remaining[@]}")
        else
          tmp="$(mktemp -d "${TMPDIR:-/tmp}/octop-release.XXXXXX")"
          if gh run download "$run_id" -D "$tmp"; then
            while IFS= read -r -d '' artifact; do
              cp -f "$artifact" "$release_dir/"
            done < <(find "$tmp" -type f -name "${display_name}-*" -print0)
            completed+=("${remaining[@]}")
          else
            failed+=("${remaining[@]}")
          fi
          rm -rf "$tmp"
        fi
      fi
    fi
  fi
elif [[ ${#remaining[@]} -gt 0 ]]; then
  echo "[package-all] skipping CI for: ${remaining[*]}"
  failed+=("${remaining[@]}")
fi

echo "[package-all] artifacts under ${release_dir}"
ls -lh "$release_dir" || true

if [[ ${#failed[@]} -gt 0 ]]; then
  echo "[package-all] failed platforms: ${failed[*]}" >&2
  exit 1
fi
echo "[package-all] complete"
