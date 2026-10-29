#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict

from lib.drawio_model import edge_style, merge_style, node_style, stable_id


def fail(message: str) -> None:
    raise ValueError(message)


def number(value: Any, name: str) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    return str(int(parsed)) if parsed.is_integer() else format(parsed, ".12g")


def load_spec(path: Path) -> Dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1:
        fail("Only FlowchartSpec schema_version 1 is supported")
    approvals = spec.get("approvals", {})
    if approvals.get("content_topology") is not True:
        fail("content_topology approval is required before generation")
    if approvals.get("artifact_mutation") is not True:
        fail("artifact_mutation approval is required before generation")
    for field in ("metadata", "canvas", "typography", "nodes", "edges"):
        if field not in spec:
            fail(f"Missing required top-level field: {field}")
    return spec


def build(spec: Dict[str, Any]) -> ET.Element:
    canvas = spec["canvas"]
    typography = spec["typography"]
    metadata = spec["metadata"]
    nodes = spec["nodes"]
    edges = spec["edges"]

    raw_ids = [str(item.get("id", "")) for item in [*nodes, *edges]]
    if any(not item for item in raw_ids):
        fail("Every node and edge requires a non-empty id")
    stable_ids = [stable_id(item) for item in raw_ids]
    if len(set(stable_ids)) != len(stable_ids):
        fail("Node and edge IDs must be unique after normalization")

    node_ids = {str(node["id"]): stable_id(node["id"]) for node in nodes}
    for node in nodes:
        for field in ("x", "y", "width", "height"):
            if field not in node:
                fail(f"Node {node['id']} is missing geometry field {field}")
        if float(node["width"]) <= 0 or float(node["height"]) <= 0:
            fail(f"Node {node['id']} must have positive width and height")

    for edge in edges:
        semantic = edge.get("semantic", True)
        source = edge.get("source")
        target = edge.get("target")
        if semantic and (source not in node_ids or target not in node_ids):
            fail(f"Semantic edge {edge['id']} requires valid source and target IDs")
        if (not source or not target) and not (
            semantic is False and edge.get("allow_free_endpoint") is True
        ):
            fail(f"Edge {edge['id']} has an undeclared free endpoint")

    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "pages": "1"})
    diagram = ET.SubElement(mxfile, "diagram", {
        "name": str(metadata.get("page_name") or metadata.get("title") or "Scientific flowchart"),
        "id": stable_id(metadata.get("page_id", "page-1")),
    })
    model = ET.SubElement(diagram, "mxGraphModel", {
        "grid": "1", "gridSize": str(canvas.get("grid_size", 10)), "guides": "1",
        "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1",
        "page": "1", "pageScale": number(canvas.get("page_scale", 1), "page_scale"),
        "pageWidth": number(canvas["width"], "canvas width"),
        "pageHeight": number(canvas["height"], "canvas height"),
        "math": "0", "shadow": "0", "adaptiveColors": "none",
    })
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    for node in nodes:
        kind = str(node.get("kind", "node"))
        parent_raw = node.get("parent") or node.get("group") or node.get("lane")
        parent = node_ids.get(str(parent_raw), "1") if parent_raw else "1"
        base = node_style(kind, typography)
        cell = ET.SubElement(root, "mxCell", {
            "id": node_ids[str(node["id"])],
            "value": str(node.get("label", "")),
            "style": merge_style(base, node.get("style")),
            "vertex": "1",
            "parent": parent,
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": number(node["x"], f"{node['id']}.x"),
            "y": number(node["y"], f"{node['id']}.y"),
            "width": number(node["width"], f"{node['id']}.width"),
            "height": number(node["height"], f"{node['id']}.height"),
            "as": "geometry",
        })

    for edge in edges:
        attrs = {
            "id": stable_id(edge["id"]), "value": str(edge.get("label", "")),
            "style": merge_style(edge_style(edge, typography), edge.get("style")),
            "edge": "1", "parent": "1",
        }
        if edge.get("source"):
            attrs["source"] = node_ids[str(edge["source"])]
        if edge.get("target"):
            attrs["target"] = node_ids[str(edge["target"])]
        cell = ET.SubElement(root, "mxCell", attrs)
        geometry = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        points = edge.get("points") or []
        if points:
            array = ET.SubElement(geometry, "Array", {"as": "points"})
            for index, point in enumerate(points):
                if not isinstance(point, list) or len(point) != 2:
                    fail(f"Edge {edge['id']} point {index} must be [x, y]")
                ET.SubElement(array, "mxPoint", {
                    "x": number(point[0], f"{edge['id']}.points[{index}].x"),
                    "y": number(point[1], f"{edge['id']}.points[{index}].y"),
                })
        for key, tag in (("source_point", "sourcePoint"), ("target_point", "targetPoint")):
            if key in edge:
                point = edge[key]
                ET.SubElement(geometry, "mxPoint", {
                    "x": number(point[0], f"{edge['id']}.{key}.x"),
                    "y": number(point[1], f"{edge['id']}.{key}.y"),
                    "as": tag,
                })
    return mxfile


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a versioned draw.io file from an approved FlowchartSpec JSON file.")
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.output.suffix.lower() != ".drawio":
        parser.error("output must use the .drawio extension")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing output: {args.output}")

    try:
        spec = load_spec(args.spec)
        tree = ET.ElementTree(build(spec))
        ET.indent(tree, space="  ")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tree.write(args.output, encoding="utf-8", xml_declaration=True)
        summary = {
            "status": "PASS", "output": str(args.output.resolve()),
            "nodes": len(spec["nodes"]), "edges": len(spec["edges"]),
            "page_width": spec["canvas"]["width"], "page_height": spec["canvas"]["height"],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
