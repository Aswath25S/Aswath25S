#!/usr/bin/env python3
"""Convert the project portrait into GitHub-safe inline SVG vector paths.

GitHub intentionally blocks raster images nested inside SVG files, including
data URIs. This script turns the generated terminal portrait into three layers
of compact horizontal vector runs so the profile card remains self-contained.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SVG_NS = "http://www.w3.org/2000/svg"
NS = f"{{{SVG_NS}}}"
SIZE = (200, 300)
THRESHOLDS = (45, 80, 125)

THEMES = {
    "dark_mode.svg": {
        "background": "#0d1117",
        "layers": ("#30363d", "#6e7681", "#c9d1d9"),
    },
    "light_mode.svg": {
        "background": "#f6f8fa",
        "layers": ("#d0d7de", "#8c959f", "#24292f"),
    },
}


def horizontal_runs(image: Image.Image, threshold: int) -> str:
    """Encode pixels above a threshold as compact one-pixel-high SVG paths."""
    commands: list[str] = []
    pixels = image.load()
    width, height = image.size

    for y in range(height):
        x = 0
        while x < width:
            while x < width and pixels[x, y] <= threshold:
                x += 1
            start = x
            while x < width and pixels[x, y] > threshold:
                x += 1
            if x > start:
                length = x - start
                commands.append(f"M{start} {y}h{length}v1h-{length}z")
    return "".join(commands)


def direct_children(root: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in list(root) if child.tag == f"{NS}{local_name}"]


def update_svg(path: Path, image: Image.Image, theme: dict[str, object]) -> None:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(path, parser=parser)
    root = tree.getroot()

    for child in list(root):
        if child.tag == f"{NS}image" or child.get("id") == "portrait_vectors":
            root.remove(child)
        elif (
            child.tag == f"{NS}rect"
            and child.get("x") == "8"
            and child.get("y") == "8"
            and child.get("width") == "365"
        ):
            root.remove(child)

    defs = next(iter(direct_children(root, "defs")), None)
    if defs is None:
        defs = ET.Element(f"{NS}defs")
        root.insert(2, defs)
    for child in list(defs):
        if child.get("id") in {"invert", "portrait-clip"}:
            defs.remove(child)

    clip = ET.SubElement(defs, f"{NS}clipPath", {"id": "portrait-clip"})
    ET.SubElement(
        clip,
        f"{NS}rect",
        {"x": "8", "y": "8", "width": "365", "height": "524", "rx": "12"},
    )

    portrait = ET.Element(
        f"{NS}g",
        {
            "id": "portrait_vectors",
            "clip-path": "url(#portrait-clip)",
            "transform": "translate(8 -4) scale(1.825)",
        },
    )
    ET.SubElement(
        portrait,
        f"{NS}rect",
        {"width": "200", "height": "300", "fill": str(theme["background"])},
    )
    for threshold, color in zip(THRESHOLDS, theme["layers"], strict=True):
        ET.SubElement(
            portrait,
            f"{NS}path",
            {"fill": str(color), "d": horizontal_runs(image, threshold)},
        )

    border_index = max(
        index
        for index, child in enumerate(list(root))
        if child.tag == f"{NS}rect" and child.get("class") == "border"
    )
    root.insert(border_index + 1, portrait)

    ET.register_namespace("", SVG_NS)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main() -> None:
    portrait = Image.open(ROOT / "assets" / "aswath-ascii.jpg").convert("L")
    portrait = portrait.resize(SIZE, Image.Resampling.LANCZOS)
    for filename, theme in THEMES.items():
        update_svg(ROOT / filename, portrait, theme)
        print(f"Vectorized portrait into {filename}")


if __name__ == "__main__":
    main()
