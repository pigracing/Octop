#!/usr/bin/env python3
"""Generate build-time branding assets from ``desktop/branding.json``.

The desktop shell (Wails) and the dashboard are built from a single branding
config.  This script snapshots the config into generated files:

* ``desktop/src/build/branding/`` — plist / Windows metadata / icons
* ``desktop/src/branding_generated.go`` — display name + tray icon bytes
* ``dashboard/branding/public/`` — a copy of ``dashboard/public`` with the
  branded manifest, offline page, favicon and logos

Run it before ``make build-frontend`` and before ``wails3 task package``.
Pillow is required for icon derivation; the packaging scripts run this with
``uv run --no-project --with pillow``.
"""

from __future__ import annotations

import base64
import io
import json
import plistlib
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover - exercised by the packaging scripts
    print(
        "apply_branding.py: Pillow is required. Run with "
        "`uv run --no-project --with pillow python desktop/src/build/apply_branding.py`.",
        file=sys.stderr,
    )
    raise SystemExit(1) from None

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "desktop" / "branding.json"
BUILD_DIR = REPO_ROOT / "desktop" / "src" / "build"
BRANDING_DIR = BUILD_DIR / "branding"
DASHBOARD_PUBLIC = REPO_ROOT / "dashboard" / "public"
DASHBOARD_BRANDING_PUBLIC = REPO_ROOT / "dashboard" / "branding" / "public"
GO_BRANDING_FILE = REPO_ROOT / "desktop" / "src" / "branding_generated.go"

DEFAULT_NAME = "Octop"
UNSAFE_NAME_CHARS = set('/\\:*?"<>|')

# Paths shipped with the upstream brand. Keeping them while changing
# display_name is usually a mistake: the visible wordmark stays "Octop".
UPSTREAM_ASSETS = {
    "icon": "desktop/src/build/appicon.png",
    "icon_macos": "desktop/src/build/appicon-macos.png",
    "tray_icon": "desktop/src/assets/tray-icon.png",
    "tray_icon_template": "desktop/src/assets/tray-icon-template.png",
    "favicon": "dashboard/public/favico.svg",
    "logo_horizontal_dark": "dashboard/public/logo_horizontal_dark.png",
    "logo_horizontal_white": "dashboard/public/logo_horizontal_white.png",
    "logo_vertical_dark": "dashboard/public/logo_vertical_dark.svg",
    "logo_vertical_white": "dashboard/public/logo_vertical_white.svg",
    "dmg_background": "desktop/src/build/darwin/dmg-background.jpeg",
}

# Static font files used for the generated DMG headline. Missing entries fall
# back to Pillow's bundled font, which is regular-only.
_DMG_FONTS = {
    False: (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ),
    True: (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
}


def _fail(message: str) -> None:
    print(f"apply_branding.py: {message}", file=sys.stderr)
    raise SystemExit(1)


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        _fail(f"missing branding config: {CONFIG_PATH}")
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"invalid JSON in {CONFIG_PATH}: {exc}")
    if not isinstance(data, dict):
        _fail(f"{CONFIG_PATH} must contain a JSON object")
    return data


def _display_name(config: dict[str, Any]) -> str:
    raw = config.get("display_name", DEFAULT_NAME)
    if not isinstance(raw, str):
        _fail("branding.display_name must be a string")
    name = raw.strip()
    if not name:
        _fail("branding.display_name must not be empty")
    bad = sorted(set(name) & UNSAFE_NAME_CHARS)
    if bad:
        _fail(f"branding.display_name contains unsafe filename character(s): {''.join(bad)}")
    return name


def _source(config: dict[str, Any], key: str, *, required: bool = False) -> Path | None:
    raw = config.get(key)
    if raw is None or raw == "":
        if required:
            _fail(f"branding.{key} is required")
        return None
    if not isinstance(raw, str):
        _fail(f"branding.{key} must be a path string")
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    path = path.resolve()
    if not path.is_file():
        _fail(f"branding.{key} does not exist: {path}")
    return path


def _open_rgba(path: Path) -> Image.Image:
    try:
        return Image.open(path).convert("RGBA")
    except Exception as exc:  # noqa: BLE001 - surface a readable build error
        _fail(f"cannot read image {path}: {exc}")


def _write_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)


def _contain(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)


def _square_icon(source: Path, size: int, dest: Path) -> None:
    image = _open_rgba(source)
    if image.size == (size, size):
        _write_png(image, dest)
    else:
        _write_png(_fit(image, (size, size)), dest)


def _macos_icon(source: Path, dest: Path) -> None:
    image = _open_rgba(source)
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    glyph = _contain(image, (824, 824))
    canvas.alpha_composite(glyph, ((1024 - glyph.width) // 2, (1024 - glyph.height) // 2))
    _write_png(canvas, dest)


def _derive_tray_icon(icon: Path, dest: Path) -> None:
    _write_png(_fit(_open_rgba(icon), (64, 64)), dest)


def _derive_tray_template(icon: Path, dest: Path) -> None:
    image = _open_rgba(icon)
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] == 255:
        # Opaque artwork: use dark pixels as the glyph so the template still
        # reads as a silhouette on the macOS menu bar.
        alpha = ImageOps.invert(ImageOps.grayscale(image))
    glyph = _contain(image, (64, 64))
    mask = _contain(alpha.convert("L"), (64, 64))
    silhouette = Image.new("RGBA", glyph.size, (0, 0, 0, 0))
    silhouette.putalpha(mask)
    canvas = Image.new("RGBA", (88, 88), (0, 0, 0, 0))
    canvas.alpha_composite(
        silhouette, ((88 - silhouette.width) // 2, (88 - silhouette.height) // 2)
    )
    _write_png(canvas, dest)


def _wordmark_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no scalable default font
        return ImageFont.load_default()


def _fit_wordmark_font(
    draw: ImageDraw.ImageDraw, text: str, max_size: int, max_width: int
) -> tuple[ImageFont.ImageFont, tuple[int, int, int, int]]:
    size = max_size
    font = _wordmark_font(size)
    box = draw.textbbox((0, 0), text, font=font)
    while box[2] - box[0] > max_width and size > 16:
        size -= 2
        font = _wordmark_font(size)
        box = draw.textbbox((0, 0), text, font=font)
    return font, box


def _derive_horizontal_logo(icon: Path, dest: Path, display_name: str, *, white: bool) -> None:
    if display_name == DEFAULT_NAME:
        image = _open_rgba(icon)
        canvas = Image.new("RGBA", (320, 96), (0, 0, 0, 0))
        glyph = _contain(image, (96, 96))
        canvas.alpha_composite(glyph, (8, (96 - glyph.height) // 2))
        _write_png(canvas, dest)
        return

    pad, gap, height = 8, 16, 96
    glyph = _contain(_open_rgba(icon), (80, 80))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    font, box = _fit_wordmark_font(probe, display_name, 46, 360)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    canvas = Image.new("RGBA", (pad * 2 + glyph.width + gap + text_w, height), (0, 0, 0, 0))
    canvas.alpha_composite(glyph, (pad, (height - glyph.height) // 2))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (pad + glyph.width + gap - box[0], (height - text_h) // 2 - box[1]),
        display_name,
        font=font,
        fill=(255, 255, 255, 255) if white else (26, 26, 26, 255),
    )
    _write_png(canvas, dest)


def _svg_image(png: bytes, size: int) -> str:
    encoded = base64.b64encode(png).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">'
        f'<image width="{size}" height="{size}" href="data:image/png;base64,{encoded}"/></svg>\n'
    )


def _svg_png(png: bytes, width: int, height: int) -> str:
    encoded = base64.b64encode(png).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        f'<image width="{width}" height="{height}" href="data:image/png;base64,{encoded}"/></svg>\n'
    )


def _png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _wrap_vertical_png(source: Path, dest: Path) -> None:
    glyph = _contain(_open_rgba(source), (256, 256))
    dest.write_text(_svg_image(_png_bytes(glyph), 256), encoding="utf-8")


def _derive_vertical_logo(icon: Path, dest: Path, display_name: str, *, white: bool) -> None:
    if display_name == DEFAULT_NAME:
        glyph = _contain(_open_rgba(icon), (256, 256))
        dest.write_text(_svg_image(_png_bytes(glyph), 256), encoding="utf-8")
        return

    pad, gap, glyph_size = 16, 12, 128
    glyph = _contain(_open_rgba(icon), (glyph_size, glyph_size))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    font, box = _fit_wordmark_font(probe, display_name, 36, 288)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    width = max(glyph.width, text_w) + pad * 2
    height = pad * 2 + glyph.height + gap + text_h
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(glyph, ((width - glyph.width) // 2, pad))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        ((width - text_w) // 2 - box[0], pad + glyph.height + gap - box[1]),
        display_name,
        font=font,
        fill=(255, 255, 255, 255) if white else (26, 26, 26, 255),
    )
    dest.write_text(_svg_png(_png_bytes(canvas), width, height), encoding="utf-8")


def _copy_logo(
    source: Path | None,
    icon: Path,
    dest: Path,
    *,
    vertical: bool,
    display_name: str,
    white: bool,
) -> None:
    if source is not None:
        suffix = source.suffix.lower()
        if vertical and suffix == ".svg":
            shutil.copyfile(source, dest)
            return
        if not vertical and suffix == ".png":
            shutil.copyfile(source, dest)
            return
        if vertical and suffix == ".png":
            _wrap_vertical_png(source, dest)
            return
        _fail(
            f"{source} cannot be used for {dest.name}: "
            f"expected {'SVG or PNG' if vertical else 'PNG'}"
        )
    if vertical:
        _derive_vertical_logo(icon, dest, display_name, white=white)
    else:
        _derive_horizontal_logo(icon, dest, display_name, white=white)


def _write_plist(display_name: str) -> None:
    template = BUILD_DIR / "darwin" / "Info.plist"
    data = plistlib.loads(template.read_bytes())
    data["CFBundleName"] = display_name
    data["CFBundleDisplayName"] = display_name
    data["CFBundleGetInfoString"] = f"{display_name} desktop shell"
    (BRANDING_DIR / "Info.plist").write_bytes(plistlib.dumps(data))


def _write_windows_info(display_name: str) -> None:
    template = BUILD_DIR / "windows" / "info.json"
    data = json.loads(template.read_text(encoding="utf-8"))
    info = data["info"]["0000"]
    info["ProductName"] = display_name
    info["FileDescription"] = f"{display_name} desktop"
    info["Comments"] = f"{display_name} desktop shell"
    out = BRANDING_DIR / "windows" / "info.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _dmg_font(size: int, *, bold: bool) -> ImageFont.ImageFont:
    for candidate in _DMG_FONTS[bold]:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return _wordmark_font(size)


def _write_dmg_background(display_name: str, config: dict[str, Any]) -> None:
    dest = BRANDING_DIR / "dmg-background.jpeg"
    source = _source(config, "dmg_background")
    if source is not None:
        shutil.copyfile(source, dest)
        return

    template = BUILD_DIR / "darwin" / "dmg-background.jpeg"
    if display_name == DEFAULT_NAME:
        shutil.copyfile(template, dest)
        return

    image = Image.open(template).convert("RGB")
    width, _height = image.size
    # The shipped 2560x1696 template has the headline at y=190..297. Cover that
    # band by interpolating between the clean rows above and below it, then
    # redraw the sentence with the configured name.
    band_top, band_bottom = 160, 330
    strip_height = band_bottom - band_top
    top = image.crop((0, band_top, width, band_top + 1)).resize(
        (width, strip_height), Image.Resampling.NEAREST
    )
    bottom = image.crop((0, band_bottom, width, band_bottom + 1)).resize(
        (width, strip_height), Image.Resampling.NEAREST
    )
    mask = Image.linear_gradient("L").resize((width, strip_height), Image.Resampling.BILINEAR)
    image.paste(Image.composite(bottom, top, mask), (0, band_top))

    draw = ImageDraw.Draw(image)
    left_text = "Drag "
    right_text = " the self-hosted AI assistant, to your Applications folder"
    max_width = int(width * 0.902)
    scale = 1.0
    while True:
        regular = _dmg_font(int(68 * scale), bold=False)
        bold = _dmg_font(int(100 * scale), bold=True)
        total = (
            draw.textlength(left_text, font=regular)
            + draw.textlength(display_name + ".", font=bold)
            + draw.textlength(right_text, font=regular)
        )
        if total <= max_width or scale <= 0.7:
            break
        scale -= 0.05

    x = (width - total) / 2
    baseline = 263
    color = (20, 20, 20)
    for text, font in (
        (left_text, regular),
        (display_name + ".", bold),
        (right_text, regular),
    ):
        ascent, _ = font.getmetrics()
        draw.text((x, baseline - ascent), text, font=font, fill=color)
        x += draw.textlength(text, font=font)

    image.save(dest, format="JPEG", quality=95)


def _replace_brand_text(text: str, display_name: str) -> str:
    return text.replace("Octop", display_name) if display_name != "Octop" else text


def _write_dashboard_public(display_name: str, icon: Path, config: dict[str, Any]) -> None:
    if DASHBOARD_BRANDING_PUBLIC.exists():
        shutil.rmtree(DASHBOARD_BRANDING_PUBLIC)
    shutil.copytree(DASHBOARD_PUBLIC, DASHBOARD_BRANDING_PUBLIC)

    manifest_path = DASHBOARD_BRANDING_PUBLIC / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = display_name
    manifest["short_name"] = display_name
    if isinstance(manifest.get("description"), str):
        manifest["description"] = _replace_brand_text(manifest["description"], display_name)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    offline_path = DASHBOARD_BRANDING_PUBLIC / "offline.html"
    offline_path.write_text(
        _replace_brand_text(offline_path.read_text(encoding="utf-8"), display_name),
        encoding="utf-8",
    )

    favicon = DASHBOARD_BRANDING_PUBLIC / "favico.svg"
    favicon_source = _source(config, "favicon")
    if favicon_source is not None and favicon_source.suffix.lower() == ".svg":
        shutil.copyfile(favicon_source, favicon)
    else:
        favicon_image = (
            _fit(_open_rgba(favicon_source), (64, 64))
            if favicon_source is not None
            else _fit(_open_rgba(icon), (64, 64))
        )
        favicon.write_text(_svg_image(_png_bytes(favicon_image), 64), encoding="utf-8")

    for name, size in (
        ("pwa-192.png", (192, 192)),
        ("pwa-512.png", (512, 512)),
        ("apple-touch-icon.png", (180, 180)),
    ):
        _write_png(_fit(_open_rgba(icon), size), DASHBOARD_BRANDING_PUBLIC / name)

    for key, name, vertical in (
        ("logo_horizontal_dark", "logo_horizontal_dark.png", False),
        ("logo_horizontal_white", "logo_horizontal_white.png", False),
        ("logo_vertical_dark", "logo_vertical_dark.svg", True),
        ("logo_vertical_white", "logo_vertical_white.svg", True),
    ):
        _copy_logo(
            _source(config, key),
            icon,
            DASHBOARD_BRANDING_PUBLIC / name,
            vertical=vertical,
            display_name=display_name,
            white="white" in name,
        )


def _go_bytes(data: bytes) -> str:
    lines = []
    for start in range(0, len(data), 16):
        chunk = data[start : start + 16]
        lines.append("\t\t" + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    return "\n".join(lines)


def _write_go(display_name: str, tray_icon: Path, tray_template: Path) -> None:
    name_literal = json.dumps(display_name, ensure_ascii=False)
    content = (
        "// Code generated by desktop/src/build/apply_branding.py; DO NOT EDIT.\n"
        "\n"
        "package main\n"
        "\n"
        "func init() {\n"
        f"\tproductDisplayName = {name_literal}\n"
        "\ttrayIconPNG = []byte{\n"
        f"{_go_bytes(tray_icon.read_bytes())}\n"
        "\t}\n"
        "\ttrayIconTemplatePNG = []byte{\n"
        f"{_go_bytes(tray_template.read_bytes())}\n"
        "\t}\n"
        "}\n"
    )
    GO_BRANDING_FILE.write_text(content, encoding="utf-8")


def main() -> int:
    config = _load_config()
    display_name = _display_name(config)

    icon = _source(config, "icon", required=True)
    assert icon is not None

    if BRANDING_DIR.exists():
        shutil.rmtree(BRANDING_DIR)
    (BRANDING_DIR / "windows").mkdir(parents=True)

    _square_icon(icon, 512, BRANDING_DIR / "appicon.png")
    macos_source = _source(config, "icon_macos")
    if macos_source is not None:
        shutil.copyfile(macos_source, BRANDING_DIR / "appicon-macos.png")
    else:
        _macos_icon(icon, BRANDING_DIR / "appicon-macos.png")

    tray_source = _source(config, "tray_icon")
    tray_path = BRANDING_DIR / "tray-icon.png"
    if tray_source is not None:
        shutil.copyfile(tray_source, tray_path)
    else:
        _derive_tray_icon(icon, tray_path)

    template_source = _source(config, "tray_icon_template")
    template_path = BRANDING_DIR / "tray-icon-template.png"
    if template_source is not None:
        shutil.copyfile(template_source, template_path)
    else:
        _derive_tray_template(icon, template_path)

    _write_plist(display_name)
    _write_windows_info(display_name)
    _write_dmg_background(display_name, config)
    _write_dashboard_public(display_name, icon, config)
    _write_go(display_name, tray_path, template_path)

    (BRANDING_DIR / "display_name.txt").write_text(display_name + "\n", encoding="utf-8")
    print(f"apply_branding.py: {display_name}")
    if display_name != DEFAULT_NAME:
        unchanged = [key for key, rel in UPSTREAM_ASSETS.items() if config.get(key) == rel]
        if unchanged:
            print(
                "apply_branding.py: warning: these paths still use the upstream Octop "
                "artwork, so the visible wordmark/icon will not change: " + ", ".join(unchanged),
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
