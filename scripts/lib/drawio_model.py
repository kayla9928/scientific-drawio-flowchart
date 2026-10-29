from __future__ import annotations

import html
import re
from typing import Any, Dict, Iterable, Tuple


ID_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def stable_id(raw: str) -> str:
    cleaned = ID_RE.sub("-", str(raw).strip()).strip("-")
    if not cleaned:
        raise ValueError("A cell ID became empty after normalization")
    return f"SDF-{cleaned}"


def parse_style(style: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            result[key] = value
        else:
            result[part] = ""
    return result


def style_string(parts: Iterable[Tuple[str, Any]]) -> str:
    rendered = []
    for key, value in parts:
        if value is None:
            continue
        rendered.append(str(key) if value == "" else f"{key}={value}")
    return ";".join(rendered) + ";"


def merge_style(base: str, overrides: Any) -> str:
    values = parse_style(base)
    if isinstance(overrides, str):
        values.update(parse_style(overrides))
    elif isinstance(overrides, dict):
        values.update({str(k): str(v) for k, v in overrides.items()})
    return style_string(values.items())


def plain_label(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).replace("\u00a0", " ")


def node_style(kind: str, typography: Dict[str, Any]) -> str:
    font = typography.get("font_family", "Arial")
    size = typography.get("font_size", 12)
    padding = typography.get("padding", 6)
    common = [
        ("html", 1), ("whiteSpace", "wrap"), ("svgWhiteSpace", "wrap"),
        ("fontFamily", font), ("fontSize", size), ("align", "center"),
        ("verticalAlign", "middle"), ("spacing", padding), ("overflow", "hidden"),
        ("strokeWidth", 1), ("container", 0), ("convertToSvg", 1),
    ]
    if kind == "junction":
        return style_string([
            ("ellipse", ""), ("html", 1), ("aspect", "fixed"),
            ("fillColor", "#666666"), ("strokeColor", "#666666"),
            ("connectable", 1), ("resizable", 0), ("editable", 0),
        ])
    if kind == "lane":
        return style_string([
            ("swimlane", ""), ("horizontal", 0), ("html", 1),
            ("startSize", 28), ("fillColor", "#f5f5f5"),
            ("strokeColor", "#808080"), ("fontFamily", font), ("fontSize", size),
            ("container", 1), ("collapsible", 0),
        ])
    if kind == "group":
        return style_string([
            ("rounded", 1), ("html", 1), ("whiteSpace", "wrap"),
            ("fillColor", "none"), ("strokeColor", "#808080"),
            ("dashed", 1), ("fontFamily", font), ("fontSize", size),
            ("container", 1), ("collapsible", 0),
        ])
    if kind == "annotation":
        return style_string([
            ("text", ""), ("html", 1), ("strokeColor", "none"),
            ("fillColor", "none"), ("fontFamily", font), ("fontSize", size),
            ("align", "left"), ("verticalAlign", "top"), ("whiteSpace", "wrap"),
        ])
    return style_string([
        ("rounded", 1), ("fillColor", "#ffffff"), ("strokeColor", "#666666"),
        *common,
    ])


def edge_style(edge: Dict[str, Any], typography: Dict[str, Any]) -> str:
    source_anchor = edge.get("source_anchor", [0.5, 1])
    target_anchor = edge.get("target_anchor", [0.5, 0])
    arrow = edge.get("arrow", "block")
    routing = edge.get("routing", "orthogonal")
    parts = [
        ("edgeStyle", "orthogonalEdgeStyle" if routing == "orthogonal" else "none"),
        ("rounded", 0), ("orthogonalLoop", 1), ("jettySize", "auto"),
        ("strokeColor", edge.get("stroke_color", "#000000")),
        ("strokeWidth", edge.get("stroke_width", 1)),
        ("endArrow", arrow), ("endFill", 0 if arrow == "none" else 1),
        ("exitX", source_anchor[0]), ("exitY", source_anchor[1]),
        ("exitDx", 0), ("exitDy", 0),
        ("entryX", target_anchor[0]), ("entryY", target_anchor[1]),
        ("entryDx", 0), ("entryDy", 0),
        ("html", 1), ("fontFamily", typography.get("font_family", "Arial")),
        ("fontSize", typography.get("font_size", 12)), ("convertToSvg", 1),
    ]
    return style_string(parts)
