#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_drawio.py"
VALIDATE = ROOT / "scripts" / "validate_drawio.py"
NORMALIZE = ROOT / "scripts" / "normalize_svg_size.py"
SPEC = ROOT / "tests" / "cases" / "branching-dag.json"


def run(arguments: list[str], expected_code: int = 0) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(arguments, text=True, encoding="utf-8", capture_output=True, env=environment)
    if result.returncode != expected_code:
        raise AssertionError(
            f"Expected exit {expected_code}, got {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def report(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def clone_xml(source: Path, target: Path, mutation) -> None:
    tree = ET.parse(source)
    mutation(tree)
    ET.indent(tree, space="  ")
    tree.write(target, encoding="utf-8", xml_declaration=True)


def find_cell(tree: ET.ElementTree, cell_id: str) -> ET.Element:
    cell = tree.getroot().find(f".//mxCell[@id='{cell_id}']")
    if cell is None:
        raise AssertionError(f"Missing test cell {cell_id}")
    return cell


def assert_category(data: dict, category: str) -> None:
    categories = {item["category"] for item in data["findings"]}
    if category not in categories:
        raise AssertionError(f"Expected category {category}, got {sorted(categories)}")


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory(prefix="scientific-drawio-flowchart-") as temp_name:
        temp = Path(temp_name)
        valid = temp / "valid.drawio"
        run([sys.executable, str(BUILD), str(SPEC), str(valid)])
        valid_report = report(run([sys.executable, str(VALIDATE), str(valid), "--spec", str(SPEC)]))
        if valid_report["status"] != "PASS":
            raise AssertionError("Synthetic valid fixture did not pass strict validation")
        results.append("valid-branching-dag")

        free = temp / "free.drawio"
        clone_xml(valid, free, lambda tree: find_cell(tree, "SDF-e-start-decision").attrib.pop("source"))
        free_report = report(run([sys.executable, str(VALIDATE), str(free)], expected_code=1))
        assert_category(free_report, "FREE_ENDPOINT")
        results.append("free-endpoint")

        overlap = temp / "overlap.drawio"
        def overlap_mutation(tree: ET.ElementTree) -> None:
            geometry = find_cell(tree, "SDF-branch-b").find("mxGeometry")
            geometry.set("x", "80")
        clone_xml(valid, overlap, overlap_mutation)
        overlap_report = report(run([sys.executable, str(VALIDATE), str(overlap)], expected_code=1))
        assert_category(overlap_report, "BOX_OVERLAP")
        results.append("box-overlap")

        diagonal = temp / "diagonal.drawio"
        def diagonal_mutation(tree: ET.ElementTree) -> None:
            point = find_cell(tree, "SDF-e-decision-a").find("./mxGeometry/Array/mxPoint")
            point.set("x", "355")
        clone_xml(valid, diagonal, diagonal_mutation)
        diagonal_report = report(run([sys.executable, str(VALIDATE), str(diagonal)], expected_code=1))
        assert_category(diagonal_report, "NON_ORTHOGONAL_SEGMENT")
        results.append("diagonal-route")

        orphan = temp / "orphan.drawio"
        def orphan_mutation(tree: ET.ElementTree) -> None:
            root = tree.getroot().find(".//mxGraphModel/root")
            cell = ET.SubElement(root, "mxCell", {"id": "SDF-orphan", "value": "", "vertex": "1", "parent": "1"})
            ET.SubElement(cell, "mxGeometry", {"x": "10", "y": "410", "width": "2", "height": "2", "as": "geometry"})
        clone_xml(valid, orphan, orphan_mutation)
        orphan_report = report(run([sys.executable, str(VALIDATE), str(orphan)], expected_code=1))
        assert_category(orphan_report, "ORPHAN_HELPER")
        results.append("orphan-helper")

        wrong_merge = temp / "wrong-merge.drawio"
        def wrong_merge_mutation(tree: ET.ElementTree) -> None:
            find_cell(tree, "SDF-e-a-merge").set("source", "SDF-terminal-exception")
        clone_xml(valid, wrong_merge, wrong_merge_mutation)
        wrong_merge_report = report(run([sys.executable, str(VALIDATE), str(wrong_merge), "--spec", str(SPEC)], expected_code=1))
        assert_category(wrong_merge_report, "FORBIDDEN_EDGE")
        assert_category(wrong_merge_report, "TERMINAL_HAS_OUTGOING")
        assert_category(wrong_merge_report, "REQUIRED_PATH_MISSING")
        results.append("wrong-terminal-merge")

        raw_svg = temp / "raw.svg"
        raw_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="600px" height="400px" viewBox="0 0 600 400"><rect width="10" height="10"/></svg>', encoding="utf-8")
        physical_svg = temp / "physical.svg"
        run([
            sys.executable, str(NORMALIZE), str(raw_svg), str(physical_svg),
            "--width", "160mm", "--height", "100mm",
            "--expect-width", "600px", "--expect-height", "400px",
            "--expect-viewbox", "0 0 600 400",
        ])
        if 'width="160mm"' not in physical_svg.read_text(encoding="utf-8"):
            raise AssertionError("Physical SVG width was not normalized")
        results.append("scoped-svg-normalization")

        behavioral = json.loads((ROOT / "tests" / "cases" / "behavioral-cases.json").read_text(encoding="utf-8"))
        modes = {case["expected_mode"] for case in behavioral if case["expected_mode"] != "none"}
        if modes != {"concept-to-spec", "spec-to-drawio", "validate-and-export"}:
            raise AssertionError(f"Behavioral routing cases do not cover all modes: {sorted(modes)}")
        if not any(case["expected_mode"] == "none" for case in behavioral):
            raise AssertionError("Behavioral routing cases require negative activation coverage")
        if not all(case.get("must") for case in behavioral):
            raise AssertionError("Each behavioral case requires observable positive expectations")
        results.append("behavioral-routing-coverage")

    print(json.dumps({"status": "PASS", "tests": results, "count": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
