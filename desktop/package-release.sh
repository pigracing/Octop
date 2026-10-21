#!/usr/bin/env bash
# Build one native Octop desktop release: Dashboard → portable runtime → Wails package.
# Run once per native platform; the GitHub Actions matrix runs all six variants.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=desktop/portable/_common.sh
source "${REPO_ROOT}/desktop/portable/_common.sh"

if ! command -v npm >/dev/null 2>&1 && [[ -s "${HOME}/.nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/.nvm/nvm.sh"
  nvm use 24 >/dev/null
fi

usage() {
  cat <<'EOF'
Usage: desktop/package-release.sh [platform] [--reuse-portable] [--skip-frontend]

Platforms:
  darwin-arm64 darwin-amd64 linux-arm64 linux-amd64
  windows-arm64 windows-amd64

The platform defaults to the current native host. --reuse-portable skips
rebuilding desktop/portable/release/<display-name>-portable-<platform>-<version>.zip
when it already exists. <display-name> comes from desktop/branding.json.
--skip-frontend reuses an already-built dashboard (desktop/package-all.sh builds it once).
EOF
}

plat=""
reuse_portable=0
skip_frontend=0
for arg in "$@"; do
  case "$arg" in
    --reuse-portable) reuse_portable=1 ;;
    --skip-frontend) skip_frontend=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; usage >&2; exit 2 ;;
    *)
      if [[ -n "$plat" ]]; then
        echo "only one platform may be specified" >&2
        exit 2
      fi
      plat="$arg"
      ;;
  esac
done

if [[ -z "$plat" ]]; then
  plat="$(host_plat)"
fi
if ! is_known_plat "$plat"; then
  echo "unknown platform: $plat" >&2
  exit 2
fi
host="$(host_plat)"
if [[ "$plat" != "$host" ]]; then
  echo "Wails release packages require a native runner: requested=${plat}, host=${host}" >&2
  exit 2
fi
if ! command -v wails3 >/dev/null 2>&1; then
  echo "wails3 is required: go install github.com/wailsapp/wails/v3/cmd/wails3@v3.0.0-beta.13" >&2
  exit 1
fi
if [[ "$plat" == windows-* ]] && ! command -v makensis >/dev/null 2>&1; then
  echo "makensis is required for the Windows installer: choco install nsis" >&2
  exit 1
fi

arch="${plat##*-}"
ver="$(octop_version)"
portable_zip="${REPO_ROOT}/desktop/portable/release/$(portable_zip_basename "$plat")"

echo "[desktop-release] platform=${plat}"
echo "[desktop-release] applying branding"
if python3 -c "import PIL" >/dev/null 2>&1; then
  python3 "${REPO_ROOT}/desktop/src/build/apply_branding.py"
elif command -v uv >/dev/null 2>&1; then
  uv run --no-project --with pillow python "${REPO_ROOT}/desktop/src/build/apply_branding.py"
else
  echo "[desktop-release] Pillow is required; run 'python3 -m pip install pillow' or install uv." >&2
  exit 1
fi
display_name="$(cat "${REPO_ROOT}/desktop/src/build/branding/display_name.txt")"
echo "[desktop-release] display_name=${display_name}"

if [[ "$skip_frontend" == 1 ]]; then
  echo "[desktop-release] reusing built Dashboard"
else
  echo "[desktop-release] building Dashboard"
  make -C "$REPO_ROOT" build-frontend
fi

if [[ "$reuse_portable" == 1 && -f "$portable_zip" ]]; then
  echo "[desktop-release] reusing ${portable_zip}"
else
  echo "[desktop-release] building portable runtime"
  bash "${REPO_ROOT}/desktop/portable/bootstrap-runtime.sh" "$plat"
  bash "${REPO_ROOT}/desktop/portable/package.sh" "$plat"
fi

staging="${REPO_ROOT}/desktop/portable/release/Octop-${plat}"
requirements="${REPO_ROOT}/desktop/portable/requirements-${plat}.txt"
if [[ "$plat" == windows-* ]]; then
  portable_python="${staging}/runtime/python.exe"
else
  portable_python="${staging}/runtime/bin/python3"
fi
if [[ ! -f "$portable_python" || ! -f "$requirements" ]]; then
  echo "portable staging is incomplete for ${plat}" >&2
  exit 1
fi

verify_args=(--packages "${staging}/packages" --requirements "$requirements")
override_file="${REPO_ROOT}/desktop/portable/overrides-${plat}.txt"
if [[ -f "$override_file" ]]; then
  verify_args+=(--overrides "$override_file")
fi
echo "[desktop-release] verifying portable imports"
PYTHONNOUSERSITE=1 "$portable_python" \
  "${REPO_ROOT}/desktop/portable/verify_imports.py" "${verify_args[@]}"

echo "[desktop-release] packaging Wails application"
(
  cd "${REPO_ROOT}/desktop/src"
  wails3 task package "ARCH=${arch}" "PORTABLE_ZIP=${portable_zip}" "VERSION=${ver}" \
    "APP_DISPLAY_NAME=${display_name}"
)

output="${REPO_ROOT}/desktop/src/bin/$(desktop_pkg_basename "$plat")"
if [[ ! -s "$output" ]]; then
  echo "desktop release was not created: ${output}" >&2
  exit 1
fi

echo "[desktop-release] complete"
echo "$output"
