"""Generate the Hephaestus public-alpha brand assets.

The script intentionally uses only the Python standard library. The larger PNG
assets are rendered from SVG through a local Chromium-compatible browser when
available; the pixel mascot PNGs are encoded directly so they stay dependency
free and reproducible.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAND_DIR = ROOT / "docs" / "assets" / "brand"
REFERENCE_BOARD = BRAND_DIR / "hephaestus-brand-board.png"
REFERENCE_HERO_BANNER = BRAND_DIR / "hephaestus-readme-hero-source.png"

SOCIAL_SIZE = (1280, 640)
HERO_SIZE = (2508, 627)
PIXEL_SIZE = 48
BOARD_SIZE = (1536, 1024)
SOCIAL_BOARD_CROP = (10, 90, 735, 368)
HERO_BOARD_CROP = (764, 88, 759, 266)
PIXEL_BOARD_CROP = (190, 532, 190, 190)

PALETTE = {
    "charcoal": "#0D1117",
    "deep_iron": "#161B22",
    "iron": "#2B3138",
    "tempered_steel": "#3D4751",
    "bronze": "#B87333",
    "old_bronze": "#7B451D",
    "bright_bronze": "#D08A3A",
    "forge_gold": "#FFC14D",
    "ember": "#FF6A00",
    "core_orange": "#FF8A1D",
    "graph_cyan": "#3DD6FF",
    "mist": "#E8EDF2",
    "muted": "#95A1AD",
}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = "\n".join(line.rstrip() for line in text.strip().splitlines())
    path.write_text(clean + "\n", encoding="utf-8")


def browser_candidates() -> list[str]:
    names = ["msedge", "chrome", "chromium", "google-chrome", "google-chrome-stable"]
    paths = [found for name in names if (found := shutil.which(name))]
    windows_paths = [
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    paths.extend(str(path) for path in windows_paths if path.exists())
    return list(dict.fromkeys(paths))


def render_svg_to_png(svg_path: Path, png_path: Path, width: int, height: int) -> None:
    errors: list[str] = []
    for browser in browser_candidates():
        with tempfile.TemporaryDirectory(prefix="hephaestus-brand-browser-") as user_data:
            cmd = [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={user_data}",
                "--force-device-scale-factor=1",
                f"--window-size={width},{height}",
                f"--screenshot={png_path}",
                svg_path.as_uri(),
            ]
            result = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if result.returncode == 0 and png_path.exists():
                return
            errors.append(
                f"{browser}: exit {result.returncode}; stdout={result.stdout[-300:]!r}; stderr={result.stderr[-300:]!r}"
            )
    joined = "\n".join(errors) if errors else "No Chromium-compatible browser found."
    raise RuntimeError(f"Could not render {svg_path.name} to PNG:\n{joined}")


def powershell_candidates() -> list[str]:
    return [found for name in ["pwsh", "powershell"] if (found := shutil.which(name))]


def extract_reference_board_assets() -> bool:
    if not REFERENCE_BOARD.exists():
        return False
    powershell = powershell_candidates()
    if not powershell:
        return False

    script = r"""
param([string]$Source, [string]$OutputDir)
Add-Type -AssemblyName System.Drawing

$src = [System.Drawing.Bitmap]::new($Source)

function Save-Crop {
    param(
        [string]$Name,
        [int]$X,
        [int]$Y,
        [int]$W,
        [int]$H,
        [int]$OutW,
        [int]$OutH,
        [string]$Interpolation
    )

    $dest = [System.Drawing.Bitmap]::new(
        $OutW,
        $OutH,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
    )
    $graphics = [System.Drawing.Graphics]::FromImage($dest)
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::$Interpolation

    $sourceRect = [System.Drawing.Rectangle]::new($X, $Y, $W, $H)
    $destRect = [System.Drawing.Rectangle]::new(0, 0, $OutW, $OutH)
    $graphics.DrawImage($src, $destRect, $sourceRect, [System.Drawing.GraphicsUnit]::Pixel)

    $output = Join-Path $OutputDir $Name
    $dest.Save($output, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $dest.Dispose()
}

Save-Crop "hephaestus-social-preview.png" 10 90 735 368 1280 640 "HighQualityBicubic"
Save-Crop "hephaestus-readme-hero.png" 764 88 759 266 1600 560 "HighQualityBicubic"
Save-Crop "talos-pixel.png" 190 532 190 190 64 64 "NearestNeighbor"
Save-Crop "talos-pixel-4x.png" 190 532 190 190 256 256 "NearestNeighbor"

$src.Dispose()
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as temp:
        temp.write(script)
        script_path = Path(temp.name)
    try:
        result = subprocess.run(
            [
                powershell[0],
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                str(REFERENCE_BOARD),
                str(BRAND_DIR),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        script_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(
            "Could not extract brand board assets:\n"
            f"stdout={result.stdout[-800:]!r}\n"
            f"stderr={result.stderr[-800:]!r}"
        )
    return True


def svg_defs() -> str:
    return f"""
  <defs>
    <radialGradient id="emberField" cx="80%" cy="78%" r="70%">
      <stop offset="0%" stop-color="{PALETTE['ember']}" stop-opacity="0.32"/>
      <stop offset="45%" stop-color="{PALETTE['old_bronze']}" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="{PALETTE['charcoal']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="coolField" cx="22%" cy="24%" r="58%">
      <stop offset="0%" stop-color="{PALETTE['graph_cyan']}" stop-opacity="0.13"/>
      <stop offset="100%" stop-color="{PALETTE['charcoal']}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="bronzeMetal" x1="0%" x2="100%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="{PALETTE['forge_gold']}"/>
      <stop offset="22%" stop-color="{PALETTE['bright_bronze']}"/>
      <stop offset="58%" stop-color="{PALETTE['bronze']}"/>
      <stop offset="100%" stop-color="{PALETTE['old_bronze']}"/>
    </linearGradient>
    <linearGradient id="darkSteel" x1="0%" x2="100%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="{PALETTE['tempered_steel']}"/>
      <stop offset="55%" stop-color="{PALETTE['iron']}"/>
      <stop offset="100%" stop-color="#101419"/>
    </linearGradient>
    <linearGradient id="anvilTop" x1="0%" x2="100%" y1="0%" y2="0%">
      <stop offset="0%" stop-color="#202832"/>
      <stop offset="45%" stop-color="#59616C"/>
      <stop offset="100%" stop-color="#151A20"/>
    </linearGradient>
    <filter id="softGlow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="hardShadow" x="-30%" y="-30%" width="160%" height="180%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000000" flood-opacity="0.38"/>
    </filter>
    <pattern id="grid" width="44" height="44" patternUnits="userSpaceOnUse">
      <path d="M 44 0 L 0 0 0 44" fill="none" stroke="#2E3742" stroke-opacity="0.22" stroke-width="1"/>
    </pattern>
    <pattern id="sparks" width="160" height="120" patternUnits="userSpaceOnUse">
      <circle cx="26" cy="24" r="1.6" fill="{PALETTE['forge_gold']}" opacity="0.42"/>
      <circle cx="96" cy="72" r="1.2" fill="{PALETTE['ember']}" opacity="0.38"/>
      <circle cx="138" cy="38" r="1.1" fill="{PALETTE['graph_cyan']}" opacity="0.22"/>
    </pattern>
  </defs>
"""


def base_background(width: int, height: int) -> str:
    return f"""
  <rect width="{width}" height="{height}" fill="{PALETTE['charcoal']}"/>
  <rect width="{width}" height="{height}" fill="url(#grid)" opacity="0.68"/>
  <rect width="{width}" height="{height}" fill="url(#emberField)"/>
  <rect width="{width}" height="{height}" fill="url(#coolField)"/>
  <rect width="{width}" height="{height}" fill="url(#sparks)" opacity="0.75"/>
"""


def graph_nodes(prefix: str = "") -> str:
    return f"""
    <g fill="none" stroke="{PALETTE['graph_cyan']}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" filter="url(#softGlow)">
      <path d="M 64 244 C 110 211 148 211 190 244"/>
      <path d="M 190 244 C 232 216 272 219 312 250"/>
      <path d="M 150 168 L 190 244 L 108 286"/>
      <path d="M 246 170 L 190 244"/>
    </g>
    <g>
      <circle cx="64" cy="244" r="10" fill="{PALETTE['graph_cyan']}"/>
      <circle cx="150" cy="168" r="12" fill="{PALETTE['graph_cyan']}"/>
      <circle cx="190" cy="244" r="14" fill="{PALETTE['forge_gold']}"/>
      <circle cx="246" cy="170" r="10" fill="{PALETTE['graph_cyan']}"/>
      <circle cx="312" cy="250" r="9" fill="{PALETTE['graph_cyan']}"/>
      <circle cx="108" cy="286" r="8" fill="{PALETTE['ember']}"/>
      <text x="184" y="250" text-anchor="middle" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="15" font-weight="800" fill="{PALETTE['charcoal']}">{prefix}</text>
    </g>
"""


def talos_group(scale: float = 1.0) -> str:
    return f"""
  <g transform="scale({scale})" filter="url(#hardShadow)">
    <ellipse cx="190" cy="330" rx="150" ry="30" fill="#020407" opacity="0.42"/>

    <g id="anvil">
      <path d="M58 266 H282 L260 292 H88 Z" fill="url(#anvilTop)"/>
      <path d="M74 292 H232 L214 320 H102 Z" fill="url(#darkSteel)"/>
      <path d="M120 320 H198 L216 340 H102 Z" fill="#12171D"/>
      <path d="M40 262 C70 242 95 238 128 251 L58 266 Z" fill="#252D36"/>
      <path d="M282 266 C318 258 338 242 354 220 C350 254 326 279 282 286 Z" fill="#202832"/>
      <path d="M74 267 H270" stroke="#89919B" stroke-opacity="0.36" stroke-width="4" stroke-linecap="round"/>
    </g>

    <g id="forged-decision-graph" transform="translate(28 18) scale(0.82)">
      {graph_nodes("Q")}
    </g>

    <g id="talos">
      <path d="M129 218 H160 V298 H129 Z" fill="url(#bronzeMetal)" stroke="#5D3519" stroke-width="5" stroke-linejoin="round"/>
      <path d="M195 218 H226 V298 H195 Z" fill="url(#bronzeMetal)" stroke="#5D3519" stroke-width="5" stroke-linejoin="round"/>
      <path d="M112 300 H166 L158 322 H98 C98 310 103 303 112 300 Z" fill="url(#darkSteel)" stroke="#0B0F14" stroke-width="5"/>
      <path d="M188 300 H242 C251 303 256 310 256 322 H196 Z" fill="url(#darkSteel)" stroke="#0B0F14" stroke-width="5"/>

      <path d="M112 119 L238 119 L258 218 H92 Z" fill="url(#bronzeMetal)" stroke="#5A3115" stroke-width="6" stroke-linejoin="round"/>
      <path d="M132 138 H218 L230 206 H120 Z" fill="#2A1D16" opacity="0.28"/>
      <circle cx="175" cy="170" r="22" fill="{PALETTE['core_orange']}" filter="url(#softGlow)"/>
      <circle cx="175" cy="170" r="10" fill="{PALETTE['forge_gold']}"/>
      <path d="M145 206 H205" stroke="#5C3519" stroke-width="6" stroke-linecap="round" opacity="0.65"/>

      <path d="M105 75 H245 Q263 75 263 93 V123 Q263 141 245 141 H105 Q87 141 87 123 V93 Q87 75 105 75 Z" fill="url(#bronzeMetal)" stroke="#5A3115" stroke-width="6"/>
      <path d="M101 92 H249 V114 H101 Z" fill="#141A21" opacity="0.72"/>
      <circle cx="141" cy="103" r="9" fill="{PALETTE['graph_cyan']}" filter="url(#softGlow)"/>
      <circle cx="209" cy="103" r="9" fill="{PALETTE['graph_cyan']}" filter="url(#softGlow)"/>
      <path d="M125 69 L116 52 H139 L146 69 Z" fill="url(#darkSteel)" stroke="#0B0F14" stroke-width="5"/>
      <path d="M204 69 L211 52 H234 L225 69 Z" fill="url(#darkSteel)" stroke="#0B0F14" stroke-width="5"/>
      <circle cx="100" cy="132" r="6" fill="{PALETTE['forge_gold']}"/>
      <circle cx="250" cy="132" r="6" fill="{PALETTE['forge_gold']}"/>

      <path d="M93 136 C66 151 52 181 57 215" fill="none" stroke="url(#bronzeMetal)" stroke-width="18" stroke-linecap="round"/>
      <circle cx="58" cy="219" r="16" fill="url(#darkSteel)" stroke="#0B0F14" stroke-width="5"/>
      <path d="M249 136 C279 121 299 95 306 61" fill="none" stroke="url(#bronzeMetal)" stroke-width="18" stroke-linecap="round"/>
      <circle cx="307" cy="58" r="14" fill="url(#darkSteel)" stroke="#0B0F14" stroke-width="5"/>

      <g transform="rotate(-18 318 44)">
        <rect x="314" y="35" width="11" height="88" rx="5" fill="#5D3B21"/>
        <rect x="293" y="22" width="58" height="25" rx="5" fill="url(#darkSteel)" stroke="#0B0F14" stroke-width="5"/>
        <rect x="305" y="47" width="34" height="10" fill="{PALETTE['bright_bronze']}" opacity="0.75"/>
      </g>
    </g>
  </g>
"""


def board_crop_svg(
    width: int,
    height: int,
    crop: tuple[int, int, int, int],
    label: str,
) -> str:
    source_width, source_height = BOARD_SIZE
    crop_x, crop_y, crop_width, crop_height = crop
    scale_x = width / crop_width
    scale_y = height / crop_height
    image_x = -crop_x * scale_x
    image_y = -crop_y * scale_y
    image_width = source_width * scale_x
    image_height = source_height * scale_y
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{label}">
  <image href="hephaestus-brand-board.png" x="{image_x:.4f}" y="{image_y:.4f}" width="{image_width:.4f}" height="{image_height:.4f}" preserveAspectRatio="none"/>
</svg>
"""


def source_image_svg(width: int, height: int, filename: str, label: str) -> str:
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{label}">
  <image href="{filename}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="none"/>
</svg>
"""


def social_svg() -> str:
    width, height = SOCIAL_SIZE
    if REFERENCE_BOARD.exists():
        return board_crop_svg(
            width,
            height,
            SOCIAL_BOARD_CROP,
            "Hephaestus social preview with Talos forging a decision graph",
        )

    pipeline = ["Repo", "Profile", "Tasks", "Pareto", "QUBO", "Explain", "Learn"]
    chips = []
    start_x = 74
    chip_y = 526
    for index, label in enumerate(pipeline):
        x = start_x + index * 154
        chips.append(
            f"""
      <g>
        <rect x="{x}" y="{chip_y}" width="116" height="42" rx="21" fill="#111821" stroke="#34404C" stroke-width="1.5"/>
        <circle cx="{x + 20}" cy="{chip_y + 21}" r="5" fill="{PALETTE['graph_cyan']}" opacity="0.92"/>
        <text x="{x + 36}" y="{chip_y + 27}" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="18" font-weight="650" fill="{PALETTE['mist']}">{label}</text>
      </g>"""
        )
        if index < len(pipeline) - 1:
            chips.append(
                f'<path d="M{x + 116} {chip_y + 21} H{x + 150}" stroke="{PALETTE["bronze"]}" stroke-width="2.5" stroke-linecap="round" opacity="0.72"/>'
            )
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Hephaestus social preview with Talos forging a decision graph">
  {svg_defs()}
  {base_background(width, height)}
  <path d="M0 500 C240 450 390 470 560 520 C740 572 948 610 1280 520 V640 H0 Z" fill="#070A0F" opacity="0.58"/>
  <g transform="translate(842 176) scale(1.04)">
    {talos_group(1)}
  </g>
  <g transform="translate(72 84)">
    <g>
      <rect x="0" y="0" width="176" height="34" rx="17" fill="#131A21" stroke="#3A4652" stroke-width="1"/>
      <circle cx="22" cy="17" r="5" fill="{PALETTE['ember']}"/>
      <text x="38" y="23" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="16" font-weight="700" letter-spacing="1.8" fill="{PALETTE['muted']}">PUBLIC ALPHA</text>
    </g>
    <text x="0" y="112" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="82" font-weight="850" fill="{PALETTE['mist']}">Hephaestus</text>
    <text x="2" y="166" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="34" font-weight="700" fill="{PALETTE['forge_gold']}">Optimization-first agent OS</text>
    <text x="2" y="214" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="26" font-weight="450" fill="{PALETTE['muted']}">Explains decisions. Learns from outcomes.</text>
    <path d="M4 250 H512" stroke="{PALETTE['bronze']}" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
    <text x="4" y="302" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="25" font-weight="600" fill="{PALETTE['mist']}">A forge for agents that think before they act.</text>
  </g>
  <g>
    {''.join(chips)}
  </g>
</svg>
"""


def hero_svg() -> str:
    width, height = HERO_SIZE
    if REFERENCE_HERO_BANNER.exists():
        return source_image_svg(
            width,
            height,
            REFERENCE_HERO_BANNER.name,
            "Hephaestus README banner with Talos forging decisions",
        )

    if REFERENCE_BOARD.exists():
        return board_crop_svg(
            width,
            height,
            HERO_BOARD_CROP,
            "Hephaestus README hero with Talos forging an explainable decision graph",
        )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Hephaestus README hero with Talos forging an explainable decision graph">
  {svg_defs()}
  {base_background(width, height)}
  <path d="M0 394 C150 352 300 362 470 418 C680 488 880 486 1074 420 C1240 364 1410 346 1600 392 V560 H0 Z" fill="#070A0F" opacity="0.62"/>

  <g transform="translate(100 112)">
    <rect x="0" y="0" width="118" height="32" rx="16" fill="#131A21" stroke="#3A4652" stroke-width="1"/>
    <circle cx="21" cy="16" r="5" fill="{PALETTE['ember']}"/>
    <text x="36" y="22" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="14" font-weight="750" letter-spacing="1.6" fill="{PALETTE['muted']}">ALPHA</text>
    <text x="0" y="104" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="70" font-weight="850" fill="{PALETTE['mist']}">Hephaestus</text>
    <text x="1" y="154" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="31" font-weight="700" fill="{PALETTE['forge_gold']}">A forge for agents that think before they act.</text>
    <text x="1" y="207" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="23" font-weight="450" fill="{PALETTE['muted']}">Repo signals become tasks, tradeoffs, and QUBO formulations.</text>
    <text x="1" y="244" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="23" font-weight="450" fill="{PALETTE['muted']}">Explanations and learning signals stay reviewable.</text>
  </g>

  <g transform="translate(785 102) scale(1.02)">
    {talos_group(1)}
  </g>

  <g transform="translate(1124 112)">
    <path d="M22 30 C90 0 160 16 216 74 C282 142 330 135 388 98" fill="none" stroke="{PALETTE['graph_cyan']}" stroke-width="3" stroke-linecap="round" opacity="0.78" filter="url(#softGlow)"/>
    <path d="M22 190 C104 142 170 154 246 204 C302 241 362 232 424 196" fill="none" stroke="{PALETTE['bronze']}" stroke-width="3" stroke-linecap="round" opacity="0.7"/>
    <g font-family="Segoe UI, Inter, Arial, sans-serif" font-size="17" font-weight="700" fill="{PALETTE['mist']}">
      <g transform="translate(0 12)">
        <circle cx="22" cy="18" r="11" fill="{PALETTE['graph_cyan']}"/><text x="46" y="24">Inspect</text>
      </g>
      <g transform="translate(118 54)">
        <circle cx="22" cy="18" r="11" fill="{PALETTE['forge_gold']}"/><text x="46" y="24">Optimize</text>
      </g>
      <g transform="translate(234 100)">
        <circle cx="22" cy="18" r="11" fill="{PALETTE['ember']}"/><text x="46" y="24">Explain</text>
      </g>
      <g transform="translate(144 188)">
        <circle cx="22" cy="18" r="11" fill="{PALETTE['graph_cyan']}"/><text x="46" y="24">Learn</text>
      </g>
    </g>
  </g>
</svg>
"""


def icon_svg() -> str:
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256" role="img" aria-label="Talos robot head icon">
  {svg_defs()}
  <circle cx="128" cy="128" r="104" fill="#10161C" stroke="{PALETTE['bronze']}" stroke-width="6"/>
  <circle cx="128" cy="128" r="94" fill="url(#emberField)" opacity="0.75"/>
  <g filter="url(#hardShadow)">
    <path d="M128 44 V72" stroke="url(#bronzeMetal)" stroke-width="10" stroke-linecap="round"/>
    <circle cx="128" cy="38" r="10" fill="url(#bronzeMetal)" stroke="#3A1E0C" stroke-width="4"/>
    <path d="M58 130 C58 108 74 93 96 93 H160 C182 93 198 108 198 130 V154 C198 176 182 191 160 191 H96 C74 191 58 176 58 154 Z" fill="url(#bronzeMetal)" stroke="#4A260D" stroke-width="7"/>
    <path d="M70 124 H186 V152 H70 Z" fill="#10151B" opacity="0.84"/>
    <circle cx="103" cy="138" r="10" fill="{PALETTE['forge_gold']}" filter="url(#softGlow)"/>
    <circle cx="153" cy="138" r="10" fill="{PALETTE['forge_gold']}" filter="url(#softGlow)"/>
    <path d="M78 191 H178 L194 224 H62 Z" fill="url(#bronzeMetal)" stroke="#4A260D" stroke-width="7" stroke-linejoin="round"/>
    <path d="M88 204 H168" stroke="#4A260D" stroke-width="6" stroke-linecap="round" opacity="0.58"/>
    <rect x="40" y="124" width="22" height="46" rx="10" fill="url(#darkSteel)" stroke="#0A0E12" stroke-width="5"/>
    <rect x="194" y="124" width="22" height="46" rx="10" fill="url(#darkSteel)" stroke="#0A0E12" stroke-width="5"/>
  </g>
</svg>
"""


def mark_svg() -> str:
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="Hephaestus anvil decision graph mark">
  {svg_defs()}
  <g fill="none" stroke="{PALETTE['bronze']}" stroke-linecap="round" stroke-linejoin="round">
    <path d="M150 172 L205 112 L256 172 L315 122 L366 174" stroke-width="16"/>
    <path d="M205 112 L226 216 L256 172 L286 218 L315 122" stroke-width="10" opacity="0.86"/>
  </g>
  <g fill="url(#bronzeMetal)" stroke="#5A2D11" stroke-width="8">
    <circle cx="150" cy="172" r="20"/>
    <circle cx="205" cy="112" r="20"/>
    <circle cx="256" cy="172" r="20"/>
    <circle cx="315" cy="122" r="20"/>
    <circle cx="366" cy="174" r="20"/>
  </g>
  <g fill="url(#bronzeMetal)" stroke="#5A2D11" stroke-linejoin="round" stroke-width="8">
    <path d="M198 232 L226 284 L256 232 L286 284 L314 232 L326 310 H186 Z"/>
    <path d="M110 310 H402 L378 352 H136 Z"/>
    <path d="M148 352 H334 L306 406 H176 Z"/>
    <path d="M198 406 H286 L312 438 H172 Z"/>
  </g>
</svg>
"""


def badge_svg() -> str:
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="220" viewBox="0 0 720 220" role="img" aria-label="Hephaestus Talos brand badge">
  {svg_defs()}
  <rect x="3" y="3" width="714" height="214" rx="48" fill="{PALETTE['charcoal']}" stroke="{PALETTE['old_bronze']}" stroke-width="4"/>
  <rect x="3" y="3" width="714" height="214" rx="48" fill="url(#emberField)" opacity="0.7"/>
  <circle cx="116" cy="110" r="72" fill="#10161C" stroke="{PALETTE['bronze']}" stroke-width="4"/>
  <g transform="translate(52 46) scale(0.36)">
    {talos_group(1)}
  </g>
  <g transform="translate(204 68)">
    <text x="0" y="46" font-family="Bahnschrift, Segoe UI, Inter, Arial, sans-serif" font-size="48" font-weight="700" letter-spacing="3" fill="{PALETTE['mist']}">HEPHAESTUS</text>
    <text x="3" y="90" font-family="Bahnschrift, Segoe UI, Inter, Arial, sans-serif" font-size="22" font-weight="600" letter-spacing="1.5" fill="{PALETTE['ember']}">THINK BEFORE YOU ACT</text>
  </g>
</svg>
"""


RGBA = tuple[int, int, int, int]


def hex_rgba(value: str, alpha: int = 255) -> RGBA:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


def new_canvas(size: int) -> list[list[RGBA]]:
    clear = (0, 0, 0, 0)
    return [[clear for _x in range(size)] for _y in range(size)]


def rect(canvas: list[list[RGBA]], x: int, y: int, w: int, h: int, color: RGBA) -> None:
    size = len(canvas)
    for yy in range(max(0, y), min(size, y + h)):
        for xx in range(max(0, x), min(size, x + w)):
            canvas[yy][xx] = color


def line(canvas: list[list[RGBA]], x0: int, y0: int, x1: int, y1: int, color: RGBA) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        rect(canvas, x, y, 1, 1, color)
        if x == x1 and y == y1:
            break
        doubled = 2 * err
        if doubled >= dy:
            err += dy
            x += sx
        if doubled <= dx:
            err += dx
            y += sy


def write_png(path: Path, canvas: list[list[RGBA]]) -> None:
    height = len(canvas)
    width = len(canvas[0])
    raw_rows = []
    for row in canvas:
        raw_rows.append(b"\x00" + b"".join(bytes(pixel) for pixel in row))
    raw = b"".join(raw_rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def scale_canvas(canvas: list[list[RGBA]], factor: int) -> list[list[RGBA]]:
    scaled: list[list[RGBA]] = []
    for row in canvas:
        expanded_row = [pixel for pixel in row for _ in range(factor)]
        for _ in range(factor):
            scaled.append(expanded_row.copy())
    return scaled


def pixel_mascot() -> list[list[RGBA]]:
    c = new_canvas(PIXEL_SIZE)
    outline = hex_rgba("#111417")
    iron = hex_rgba("#333A42")
    steel = hex_rgba("#5B6570")
    bronze = hex_rgba(PALETTE["bronze"])
    bronze_dark = hex_rgba(PALETTE["old_bronze"])
    bronze_light = hex_rgba(PALETTE["bright_bronze"])
    ember = hex_rgba(PALETTE["ember"])
    gold = hex_rgba(PALETTE["forge_gold"])
    cyan = hex_rgba(PALETTE["graph_cyan"])
    glow = hex_rgba("#A9EEFF")

    # Hammer, lifted over the right shoulder.
    line(c, 32, 18, 40, 8, outline)
    line(c, 33, 18, 41, 8, bronze_dark)
    rect(c, 38, 6, 8, 3, outline)
    rect(c, 39, 5, 6, 5, iron)
    rect(c, 40, 5, 2, 5, steel)

    # Head with small furnace horns.
    rect(c, 15, 7, 18, 3, outline)
    rect(c, 14, 10, 20, 10, outline)
    rect(c, 16, 9, 16, 10, bronze)
    rect(c, 17, 10, 5, 2, bronze_light)
    rect(c, 20, 13, 3, 2, glow)
    rect(c, 27, 13, 3, 2, glow)
    rect(c, 19, 12, 5, 4, cyan)
    rect(c, 26, 12, 5, 4, cyan)
    rect(c, 12, 6, 4, 5, outline)
    rect(c, 13, 5, 3, 5, iron)
    rect(c, 32, 6, 4, 5, outline)
    rect(c, 32, 5, 3, 5, iron)

    # Body and glowing core.
    rect(c, 15, 21, 18, 14, outline)
    rect(c, 16, 20, 16, 15, bronze)
    rect(c, 18, 22, 12, 10, bronze_dark)
    rect(c, 23, 24, 4, 4, ember)
    rect(c, 24, 25, 2, 2, gold)
    rect(c, 17, 20, 4, 2, bronze_light)

    # Arms.
    rect(c, 10, 22, 6, 4, outline)
    rect(c, 9, 23, 6, 3, bronze)
    rect(c, 7, 24, 4, 4, iron)
    rect(c, 32, 21, 4, 5, outline)
    rect(c, 32, 20, 3, 5, bronze)

    # Legs and feet.
    rect(c, 17, 34, 5, 7, outline)
    rect(c, 18, 34, 3, 7, bronze_dark)
    rect(c, 27, 34, 5, 7, outline)
    rect(c, 28, 34, 3, 7, bronze_dark)
    rect(c, 14, 41, 10, 3, outline)
    rect(c, 25, 41, 10, 3, outline)
    rect(c, 15, 40, 8, 3, iron)
    rect(c, 26, 40, 8, 3, iron)

    # Anvil and tiny decision graph.
    rect(c, 7, 37, 22, 3, outline)
    rect(c, 8, 36, 20, 3, steel)
    rect(c, 11, 39, 13, 3, outline)
    rect(c, 12, 39, 11, 2, iron)
    line(c, 17, 35, 20, 32, cyan)
    line(c, 20, 32, 24, 35, cyan)
    rect(c, 16, 34, 3, 3, cyan)
    rect(c, 19, 31, 3, 3, gold)
    rect(c, 23, 34, 3, 3, cyan)

    # Sparks.
    rect(c, 5, 15, 1, 1, gold)
    rect(c, 8, 12, 1, 1, ember)
    rect(c, 42, 20, 1, 1, gold)
    rect(c, 37, 29, 1, 1, cyan)
    return c


def palette_doc() -> str:
    rows = "\n".join(
        f"| `{name}` | `{value}` | {description} |"
        for name, value, description in [
            ("charcoal", PALETTE["charcoal"], "Primary dark background; GitHub-dark friendly."),
            ("deep_iron", PALETTE["deep_iron"], "Panels, bands, and quiet UI surfaces."),
            ("iron", PALETTE["iron"], "Anvil and machine-shadow forms."),
            ("tempered_steel", PALETTE["tempered_steel"], "Metal highlights and outlines."),
            ("bronze", PALETTE["bronze"], "Talos body, forge craft, primary warm brand color."),
            ("old_bronze", PALETTE["old_bronze"], "Bronze shadow and worn-metal depth."),
            ("bright_bronze", PALETTE["bright_bronze"], "Bronze edge highlights."),
            ("forge_gold", PALETTE["forge_gold"], "Decision emphasis and key sparks."),
            ("ember", PALETTE["ember"], "Heat, action, and forge energy."),
            ("graph_cyan", PALETTE["graph_cyan"], "Subtle cool accent for decision graph glow."),
            ("mist", PALETTE["mist"], "Primary text on dark backgrounds."),
            ("muted", PALETTE["muted"], "Secondary text and labels."),
        ]
    )
    return f"""
# Hephaestus Brand Palette

Hephaestus uses a restrained forge palette: dark engineering surfaces, bronze
craft, ember heat, and one cool graph accent. The goal is premium open-source
tooling, not fantasy poster art.

| Token | Hex | Use |
| --- | --- | --- |
{rows}

## Usage Notes

- Keep dark charcoal or deep iron as the dominant field.
- Use bronze and ember as warm emphasis, not as a full orange wash.
- Reserve graph cyan for explainability, graph nodes, and decision traces.
- Prefer high-contrast text on dark backgrounds for README and social use.
- Talos should stay small, tool-oriented, and connected to the decision forge.
"""


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)

    social_source = BRAND_DIR / "hephaestus-social-preview.svg"
    hero_source = BRAND_DIR / "hephaestus-readme-hero.svg"
    write_text(social_source, social_svg())
    write_text(hero_source, hero_svg())
    write_text(BRAND_DIR / "talos-icon.svg", icon_svg())
    write_text(BRAND_DIR / "talos-mark.svg", mark_svg())
    write_text(BRAND_DIR / "talos-badge.svg", badge_svg())
    write_text(BRAND_DIR / "palette.md", palette_doc())

    if not extract_reference_board_assets():
        render_svg_to_png(
            social_source,
            BRAND_DIR / "hephaestus-social-preview.png",
            *SOCIAL_SIZE,
        )
        render_svg_to_png(
            hero_source,
            BRAND_DIR / "hephaestus-readme-hero.png",
            *HERO_SIZE,
        )

        mascot = pixel_mascot()
        write_png(BRAND_DIR / "talos-pixel.png", mascot)
        write_png(BRAND_DIR / "talos-pixel-4x.png", scale_canvas(mascot, 4))

    if REFERENCE_HERO_BANNER.exists():
        shutil.copyfile(REFERENCE_HERO_BANNER, BRAND_DIR / "hephaestus-readme-hero.png")

    print(f"Generated brand assets in {BRAND_DIR}")


if __name__ == "__main__":
    main()
