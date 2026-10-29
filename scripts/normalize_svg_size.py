#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from check_svg_size import dimension_review_reason, dimensions, length_mm, read_svg


ROOT_RE = re.compile(r"<svg\b[^>]*>", re.I)


def replace_attribute(root: str, name: str, expected: str | None, replacement: str) -> str:
    pattern = re.compile(r'\s+([A-Za-z_:][-\w.:]*)\s*=\s*([\"\'])(.*?)\2', re.S)
    match = next((item for item in pattern.finditer(root) if item.group(1) == name), None)
    if not match:
        raise ValueError(f"SVG root has no {name} attribute")
    actual = match.group(3)
    if expected is not None and actual != expected:
        raise ValueError(f"Expected {name}={expected!r}, got {actual!r}")
    return root[:match.start(3)] + replacement + root[match.end(3):]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new SVG whose only changes are root physical width and height attributes.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", required=True, help="Physical root width, for example 180mm")
    parser.add_argument("--height", help="Explicit height (legacy mode); omit to preserve the raw viewport ratio")
    parser.add_argument("--max-height", help="Absolute height ceiling, for example 210mm; stop instead of compressing")
    parser.add_argument("--expect-width")
    parser.add_argument("--expect-height")
    parser.add_argument("--expect-viewbox")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing to overwrite output: {args.output}")
    try:
        source, parsed = read_svg(args.source)
        target_width_mm = length_mm(args.width)
        if args.height is None:
            if dimension_review_reason(source, parsed):
                raise ValueError('Proportional sizing requires resolved root dimensions; inspect CSS sizing in the renderer first.')
            old_width_mm, old_height_mm = dimensions(parsed)
            target_height = f"{target_width_mm * old_height_mm / old_width_mm:.12g}mm"
        else:
            target_height = args.height
        target_height_mm = length_mm(target_height)
        if args.max_height is not None and target_height_mm > length_mm(args.max_height) + 1e-9:
            raise ValueError("Proportional output exceeds max height; re-layout or obtain a constraint change. No output written.")
        original_match = next((match for match in ROOT_RE.finditer(source)
                               if source.rfind('<!--', 0, match.start()) <= source.rfind('-->', 0, match.start())), None)
        if not original_match:
            raise ValueError("SVG root element was not found")
        original_root = original_match.group(0)
        if args.expect_viewbox:
            actual_viewbox = parsed.get('viewBox')
            if actual_viewbox != args.expect_viewbox:
                raise ValueError(f"Expected viewBox={args.expect_viewbox!r}, got {actual_viewbox!r}")
        new_root = replace_attribute(original_root, "width", args.expect_width, args.width)
        new_root = replace_attribute(new_root, "height", args.expect_height, target_height)
        output = source[:original_match.start()] + new_root + source[original_match.end():]
        restored = replace_attribute(new_root, "width", args.width, parsed.get('width'))
        restored = replace_attribute(restored, "height", target_height, parsed.get('height'))
        if restored != original_root:
            raise ValueError("Unexpected root-element differences were introduced")
        output_root = ET.fromstring(output)
        if output_root.get('width') != args.width or output_root.get('height') != target_height:
            raise ValueError('Serialized root dimensions do not match the requested output.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(json.dumps({"status": "PASS", "output": str(args.output.resolve()), "width": args.width,
                          "height": target_height, "ratio_preserving_mode": args.height is None,
                          "not_checked": ["text_fit", "rendering", "minimum_font_size"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, ET.ParseError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
