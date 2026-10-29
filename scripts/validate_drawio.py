#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lib.drawio_model import parse_style, plain_label, stable_id
from lib.geometry import Rect, is_axis_aligned, polyline_segments, rectangles_overlap, segment_intersects_rect_interior


def f(value: Optional[str], default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


class Report:
    def __init__(self, source: Path, profile: str) -> None:
        self.source = str(source.resolve())
        self.profile = profile
        self.findings: List[Dict[str, Any]] = []
        self.pages: List[Dict[str, Any]] = []

    def add(self, severity: str, category: str, message: str, page: str = "", cell_id: str = "", evidence: Any = None) -> None:
        finding = {"severity": severity, "category": category, "message": message}
        if page:
            finding["page"] = page
        if cell_id:
            finding["cell_id"] = cell_id
        if evidence is not None:
            finding["evidence"] = evidence
        self.findings.append(finding)

    def data(self) -> Dict[str, Any]:
        counts = Counter(item["severity"] for item in self.findings)
        return {
            "status": "PASS" if counts["ERROR"] == 0 else "FAIL",
            "source": self.source,
            "profile": self.profile,
            "counts": {key: counts[key] for key in ("ERROR", "WARNING", "INFO")},
            "pages": self.pages,
            "findings": self.findings,
        }


def load_spec(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1:
        raise ValueError("Only FlowchartSpec schema_version 1 is supported")
    return spec


def absolute_rects(cells: Dict[str, ET.Element]) -> Dict[str, Rect]:
    cache: Dict[str, Rect] = {}
    visiting: set[str] = set()

    def resolve(cell_id: str) -> Rect:
        if cell_id in cache:
            return cache[cell_id]
        if cell_id in visiting:
            raise ValueError(f"Parent cycle includes {cell_id}")
        visiting.add(cell_id)
        cell = cells[cell_id]
        geometry = cell.find("mxGeometry")
        x = f(geometry.get("x") if geometry is not None else None)
        y = f(geometry.get("y") if geometry is not None else None)
        width = f(geometry.get("width") if geometry is not None else None)
        height = f(geometry.get("height") if geometry is not None else None)
        parent_id = cell.get("parent")
        if parent_id in cells and cells[parent_id].get("vertex") == "1":
            parent_rect = resolve(parent_id)
            x += parent_rect.x
            y += parent_rect.y
        rect = Rect(cell_id, x, y, width, height)
        cache[cell_id] = rect
        visiting.remove(cell_id)
        return rect

    for cell_id, cell in cells.items():
        if cell.get("vertex") == "1":
            resolve(cell_id)
    return cache


def point_element(geometry: Optional[ET.Element], point_as: str) -> Optional[Tuple[float, float]]:
    if geometry is None:
        return None
    point = geometry.find(f"mxPoint[@as='{point_as}']")
    return (f(point.get("x")), f(point.get("y"))) if point is not None else None


def anchor(rect: Rect, style: Dict[str, str], prefix: str, default: Tuple[float, float]) -> Tuple[float, float]:
    return rect.anchor(f(style.get(f"{prefix}X"), default[0]), f(style.get(f"{prefix}Y"), default[1]))


def edge_points(edge: ET.Element, rects: Dict[str, Rect]) -> List[Tuple[float, float]]:
    style = parse_style(edge.get("style", ""))
    geometry = edge.find("mxGeometry")
    points: List[Tuple[float, float]] = []
    source = edge.get("source")
    target = edge.get("target")
    if source in rects:
        points.append(anchor(rects[source], style, "exit", (0.5, 1.0)))
    else:
        free = point_element(geometry, "sourcePoint")
        if free:
            points.append(free)
    if geometry is not None:
        array = geometry.find("Array[@as='points']")
        if array is not None:
            points.extend((f(point.get("x")), f(point.get("y"))) for point in array.findall("mxPoint"))
    if target in rects:
        points.append(anchor(rects[target], style, "entry", (0.5, 0.0)))
    else:
        free = point_element(geometry, "targetPoint")
        if free:
            points.append(free)
    return points


def is_container(cell: ET.Element) -> bool:
    style = parse_style(cell.get("style", ""))
    return "swimlane" in style or "group" in style or style.get("container") == "1"


def is_auxiliary_label(cell: ET.Element, cells: Dict[str, ET.Element]) -> bool:
    geometry = cell.find("mxGeometry")
    if geometry is not None and geometry.get("relative") == "1":
        return True
    parent = cells.get(cell.get("parent", ""))
    return parent is not None and parent.get("edge") == "1"


def ancestor_of(candidate: str, cell_id: str, cells: Dict[str, ET.Element]) -> bool:
    seen = set()
    current = cells.get(cell_id)
    while current is not None and current.get("parent") not in (None, "0", "1"):
        parent = current.get("parent")
        if parent == candidate:
            return True
        if parent in seen:
            break
        seen.add(parent)
        current = cells.get(parent)
    return False


def validate_page(diagram: ET.Element, report: Report, spec: Optional[Dict[str, Any]], page_index: int) -> None:
    page = diagram.get("name", f"page-{page_index + 1}")
    model = diagram.find("mxGraphModel")
    if model is None:
        report.add("ERROR", "UNSUPPORTED_COMPRESSED_PAGE", "Compressed or unsupported diagram content cannot be audited without decoding.", page)
        return
    root = model.find("root")
    if root is None:
        report.add("ERROR", "MISSING_ROOT", "mxGraphModel has no root.", page)
        return
    cell_list = root.findall("mxCell")
    ids = [cell.get("id", "") for cell in cell_list]
    duplicates = [cell_id for cell_id, count in Counter(ids).items() if cell_id and count > 1]
    for cell_id in duplicates:
        report.add("ERROR", "DUPLICATE_ID", "Cell ID is duplicated.", page, cell_id)
    cells = {cell.get("id", ""): cell for cell in cell_list if cell.get("id")}
    for cell in cell_list:
        parent = cell.get("parent")
        if parent and parent not in cells:
            report.add("ERROR", "MISSING_PARENT", f"Parent {parent} does not exist.", page, cell.get("id", ""))

    try:
        rects = absolute_rects(cells)
    except ValueError as exc:
        report.add("ERROR", "PARENT_CYCLE", str(exc), page)
        return
    vertices = [cell for cell in cell_list if cell.get("vertex") == "1"]
    edges = [cell for cell in cell_list if cell.get("edge") == "1"]
    width = f(model.get("pageWidth"))
    height = f(model.get("pageHeight"))
    epsilon = max(0.05, max(width, height) * 1e-4)
    if spec:
        epsilon = float(spec.get("validation", {}).get("coordinate_epsilon", epsilon))
    report.pages.append({
        "name": page, "width": width, "height": height,
        "vertices": len(vertices), "edges": len(edges),
        "fully_bound_edges": sum(bool(edge.get("source") and edge.get("target")) for edge in edges),
        "coordinate_epsilon": epsilon,
    })

    referenced = set()
    for edge in edges:
        edge_id = edge.get("id", "")
        source, target = edge.get("source"), edge.get("target")
        for endpoint_name, endpoint in (("source", source), ("target", target)):
            if endpoint:
                referenced.add(endpoint)
                if endpoint not in rects:
                    report.add("ERROR", "MISSING_ENDPOINT", f"Edge {endpoint_name} {endpoint} does not exist or is not a vertex.", page, edge_id)
            else:
                severity = "ERROR" if report.profile == "strict" else "WARNING"
                report.add(severity, "FREE_ENDPOINT", f"Edge has no bound {endpoint_name}.", page, edge_id)

    for vertex in vertices:
        cell_id = vertex.get("id", "")
        rect = rects[cell_id]
        if rect.width <= 0 or rect.height <= 0:
            report.add("ERROR", "INVALID_RECT", "Vertex width and height must be positive.", page, cell_id)
        if width > 0 and (rect.x < -epsilon or rect.right > width + epsilon):
            report.add("ERROR", "OUT_OF_BOUNDS", "Vertex exceeds horizontal page bounds.", page, cell_id, [rect.x, rect.right, width])
        if height > 0 and (rect.y < -epsilon or rect.bottom > height + epsilon):
            report.add("ERROR", "OUT_OF_BOUNDS", "Vertex exceeds vertical page bounds.", page, cell_id, [rect.y, rect.bottom, height])
        if not plain_label(vertex.get("value", "")).strip() and not is_container(vertex):
            if cell_id not in referenced:
                report.add("ERROR", "ORPHAN_HELPER", "Empty vertex is not referenced by any edge.", page, cell_id)
            else:
                style = parse_style(vertex.get("style", ""))
                hidden = style.get("opacity") == "0" or (style.get("fillColor") == "none" and style.get("strokeColor") == "none")
                if hidden:
                    report.add("ERROR" if report.profile == "strict" else "WARNING", "INVISIBLE_HELPER", "Referenced empty vertex is not visibly inspectable.", page, cell_id)

    ordinary = [vertex for vertex in vertices if not is_container(vertex) and not is_auxiliary_label(vertex, cells)]
    for index, first in enumerate(ordinary):
        first_id = first.get("id", "")
        for second in ordinary[index + 1:]:
            second_id = second.get("id", "")
            if ancestor_of(first_id, second_id, cells) or ancestor_of(second_id, first_id, cells):
                continue
            if rectangles_overlap(rects[first_id], rects[second_id], epsilon):
                report.add("ERROR", "BOX_OVERLAP", f"Vertices overlap: {first_id} and {second_id}.", page, first_id, second_id)

    for edge in edges:
        edge_id = edge.get("id", "")
        points = edge_points(edge, rects)
        style = parse_style(edge.get("style", ""))
        requires_orthogonal = style.get("edgeStyle") == "orthogonalEdgeStyle"
        geometry = edge.find("mxGeometry")
        array = geometry.find("Array[@as='points']") if geometry is not None else None
        has_explicit_waypoints = array is not None and bool(array.findall("mxPoint"))
        if len(points) < 2:
            report.add("ERROR" if report.profile == "strict" else "WARNING", "UNRESOLVED_ROUTE", "Edge has fewer than two resolvable route points.", page, edge_id)
            continue
        if requires_orthogonal and not has_explicit_waypoints and not is_axis_aligned(points[0], points[-1], epsilon):
            report.add(
                "ERROR" if report.profile == "strict" else "WARNING",
                "AUTO_ROUTE_UNRESOLVED",
                "Orthogonal routing is delegated to draw.io and cannot be collision-checked from serialized endpoints alone.",
                page,
                edge_id,
                [points[0], points[-1]],
            )
            continue
        for start, end in polyline_segments(points):
            if requires_orthogonal and not is_axis_aligned(start, end, epsilon):
                report.add("ERROR" if report.profile == "strict" else "WARNING", "NON_ORTHOGONAL_SEGMENT", "Orthogonal edge contains a diagonal segment.", page, edge_id, [start, end])
                continue
            for vertex in ordinary:
                vertex_id = vertex.get("id", "")
                if vertex_id in (edge.get("source"), edge.get("target")):
                    continue
                if segment_intersects_rect_interior(start, end, rects[vertex_id], epsilon):
                    report.add("ERROR" if report.profile == "strict" else "WARNING", "EDGE_CROSSES_BOX", f"Edge crosses non-endpoint vertex {vertex_id}.", page, edge_id, vertex_id)

    if not spec:
        return
    spec_nodes = {stable_id(node["id"]): node for node in spec.get("nodes", [])}
    spec_edges = {stable_id(edge["id"]): edge for edge in spec.get("edges", [])}
    allowed_extra_edges = {stable_id(edge_id) for edge_id in spec.get("validation", {}).get("allowed_extra_edges", [])}
    for edge in edges:
        edge_id = edge.get("id", "")
        if edge_id not in spec_edges and edge_id not in allowed_extra_edges:
            report.add("ERROR", "UNEXPECTED_EDGE", "Edge is not declared by the specification.", page, edge_id)
    for cell_id, node in spec_nodes.items():
        cell = cells.get(cell_id)
        if cell is None:
            report.add("ERROR", "MISSING_SPEC_NODE", "Expected node from specification is missing.", page, cell_id)
            continue
        policy = spec.get("validation", {}).get("label_policy", "exact")
        expected = str(node.get("label", ""))
        actual = cell.get("value", "")
        same = actual == expected if policy == "exact" else plain_label(actual) == plain_label(expected)
        if not same:
            report.add("ERROR", "TEXT_DRIFT", "Node label differs from specification.", page, cell_id)
        measured = node.get("measured_text")
        if measured:
            padding = float(spec.get("typography", {}).get("padding", 0))
            rect = rects.get(cell_id)
            if rect and (float(measured.get("width", 0)) + 2 * padding > rect.width + epsilon or float(measured.get("height", 0)) + 2 * padding > rect.height + epsilon):
                report.add("ERROR", "TEXT_OVERFLOW", "Measured text and padding exceed the node rectangle.", page, cell_id)

    indegree: Dict[str, int] = defaultdict(int)
    outdegree: Dict[str, int] = defaultdict(int)
    pairs = set()
    for cell_id, expected in spec_edges.items():
        cell = cells.get(cell_id)
        if cell is None:
            report.add("ERROR", "MISSING_SPEC_EDGE", "Expected edge from specification is missing.", page, cell_id)
            continue
        source = stable_id(expected["source"]) if expected.get("source") else None
        target = stable_id(expected["target"]) if expected.get("target") else None
        actual_source = cell.get("source")
        actual_target = cell.get("target")
        if actual_source != source or actual_target != target:
            report.add("ERROR", "EDGE_ENDPOINT_DRIFT", "Edge endpoints differ from specification.", page, cell_id)
        if actual_source:
            outdegree[actual_source] += 1
        if actual_target:
            indegree[actual_target] += 1
        pairs.add((actual_source, actual_target))
        arrow = parse_style(cell.get("style", "")).get("endArrow", "")
        if expected.get("arrow", "block") != arrow:
            report.add("ERROR", "ARROW_STYLE_DRIFT", f"Expected endArrow={expected.get('arrow', 'block')}, got {arrow}.", page, cell_id)

    validation = spec.get("validation", {})
    for raw_id, expected in validation.get("expected_degrees", {}).items():
        cell_id = stable_id(raw_id)
        actual = [indegree[cell_id], outdegree[cell_id]]
        if list(expected) != actual:
            report.add("ERROR", "DEGREE_MISMATCH", f"Expected degree {list(expected)}, got {actual}.", page, cell_id)
    for source, target in validation.get("forbidden_edges", []):
        pair = (stable_id(source), stable_id(target))
        if pair in pairs:
            report.add("ERROR", "FORBIDDEN_EDGE", "A forbidden semantic edge exists.", page, f"{pair[0]}->{pair[1]}")
    adjacency: Dict[str, set[str]] = defaultdict(set)
    for source, target in pairs:
        if source and target:
            adjacency[source].add(target)
    for raw_path in validation.get("required_paths", []):
        path = [stable_id(node_id) for node_id in raw_path]
        missing_steps = [(a, b) for a, b in zip(path, path[1:]) if b not in adjacency[a]]
        if missing_steps:
            report.add("ERROR", "REQUIRED_PATH_MISSING", "A required path is missing one or more direct steps.", page, "->".join(path), missing_steps)
    for cell_id, node in spec_nodes.items():
        if node.get("terminal") is True and outdegree[cell_id] != 0:
            report.add("ERROR", "TERMINAL_HAS_OUTGOING", "Declared terminal has an outgoing semantic edge.", page, cell_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only structural and geometry validation for draw.io flowcharts.")
    parser.add_argument("drawio", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--profile", choices=("strict", "legacy-audit"), default="strict")
    parser.add_argument("--json-out", type=Path, help="Optional report path; refuses to overwrite")
    args = parser.parse_args()
    if args.json_out and args.json_out.exists():
        parser.error(f"refusing to overwrite report: {args.json_out}")
    report = Report(args.drawio, args.profile)
    try:
        spec = load_spec(args.spec)
        tree = ET.parse(args.drawio)
        root = tree.getroot()
        if root.tag != "mxfile":
            report.add("ERROR", "INVALID_ROOT", "Root element must be mxfile.")
        else:
            diagrams = root.findall("diagram")
            if not diagrams:
                report.add("ERROR", "NO_DIAGRAM", "mxfile contains no diagram pages.")
            for index, diagram in enumerate(diagrams):
                validate_page(diagram, report, spec, index)
    except (ET.ParseError, OSError, ValueError, json.JSONDecodeError) as exc:
        report.add("ERROR", "VALIDATION_EXCEPTION", str(exc))
    data = report.data()
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if data["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
