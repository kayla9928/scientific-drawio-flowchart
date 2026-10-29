#!/usr/bin/env python3
"""Read-only SVG physical-size checks; PASS covers only the requested checks."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


SVG = 'http://www.w3.org/2000/svg'
UNIT_MM = {'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': 25.4 / 72, 'pc': 25.4 / 6, 'px': 25.4 / 96, '': 25.4 / 96}


def length_mm(value: str) -> float:
    match = re.fullmatch(r'\s*([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(mm|cm|in|pt|pc|px)?\s*', value or '')
    if not match:
        raise ValueError(f'Unsupported absolute SVG length: {value!r}')
    number = float(match[1]) * UNIT_MM[match[2] or '']
    if not math.isfinite(number) or number <= 0:
        raise ValueError('Lengths must be positive and finite.')
    return number


def read_svg(path: Path) -> tuple[str, ET.Element]:
    text = path.read_text(encoding='utf-8')
    if '<!ENTITY' in text.upper():
        raise ValueError('Entity declarations are not supported.')
    root = ET.fromstring(text)
    if root.tag not in ('svg', f'{{{SVG}}}svg'):
        raise ValueError('Expected an SVG root.')
    return text, root


def viewbox(root: ET.Element) -> list[float]:
    values = [float(v) for v in re.split(r'[\s,]+', root.get('viewBox', '').strip()) if v]
    if len(values) != 4 or not all(math.isfinite(v) for v in values) or min(values[2:]) <= 0:
        raise ValueError('A finite, positive-size viewBox is required.')
    return values


def dimensions(root: ET.Element) -> tuple[float, float]:
    return length_mm(root.get('width')), length_mm(root.get('height'))


def dimension_review_reason(text: str, root: ET.Element) -> str | None:
    if '<?xml-stylesheet' in text or any(e.tag.rsplit('}', 1)[-1] == 'style' for e in root.iter()):
        return 'Stylesheet rules may override SVG dimensions; verify in the renderer.'
    if re.search(r'(^|;)\s*(width|height|min-width|max-width|min-height|max-height|transform)\s*:', root.get('style', ''), re.I):
        return 'Root CSS sizing/transform may override declared attributes; verify in the renderer.'
    return None


def root_size_free(root: ET.Element) -> bytes:
    clean = copy.deepcopy(root)
    clean.attrib.pop('width', None)
    clean.attrib.pop('height', None)
    return ET.tostring(clean, encoding='utf-8')


def simple_transform(value: str) -> bool:
    # Translation and identity scale/matrix only; reject unaccounted font scaling.
    remainder = value
    for match in list(re.finditer(r'([A-Za-z]+)\s*\(([^)]*)\)', value)):
        try:
            numbers = [float(v) for v in re.split(r'[\s,]+', match[2].strip()) if v]
        except ValueError:
            return False
        if not all(math.isfinite(v) for v in numbers):
            return False
        if match[1] == 'translate' and len(numbers) in (1, 2):
            pass
        elif match[1] == 'scale' and numbers in ([1.0], [1.0, 1.0]):
            pass
        elif match[1] == 'matrix' and len(numbers) == 6 and numbers[:4] == [1, 0, 0, 1]:
            pass
        else:
            return False
        remainder = remainder.replace(match[0], '', 1)
    return not remainder.strip()


def declared_font_points(root: ET.Element, width_mm: float, height_mm: float) -> tuple[list[float], str | None]:
    try:
        vb = viewbox(root)
    except ValueError as exc:
        return [], str(exc)
    if abs(width_mm / height_mm - vb[2] / vb[3]) > 1e-6:
        return [], 'Viewport/viewBox ratios differ; font conversion needs renderer review.'
    if root.get('preserveAspectRatio', 'xMidYMid meet').strip() not in ('xMidYMid meet', 'xMidYMid', ''):
        return [], 'Non-default preserveAspectRatio requires renderer review.'
    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1]
        style = element.get('style', '')
        if tag in ('style', 'foreignObject', 'use', 'script') or (tag == 'svg' and element is not root):
            return [], f'{tag} may alter font inheritance or scale; inspect the renderer.'
        if not simple_transform(element.get('transform', '')) or re.search(r'(^|;)\s*(transform|font|font-size-adjust|writing-mode)\s*:', style):
            return [], 'Transform or font shorthand requires renderer review.'
        if element.get('textLength') or element.get('lengthAdjust'):
            return [], 'Adjusted text length requires renderer review.'
    values = []

    def walk(element: ET.Element, inherited: float | None, in_text: bool = False):
        st = dict(part.split(':', 1) for part in element.get('style', '').split(';') if ':' in part)
        st = {k.strip(): v.strip() for k, v in st.items()}
        size = st.get('font-size', element.get('font-size'))
        current = length_mm(size) / (25.4 / 96) if size is not None else inherited
        tag = element.tag.rsplit('}', 1)[-1]
        in_text = in_text or tag == 'text'
        if in_text and element.text and element.text.strip():
            if current is None:
                raise ValueError('Visible text has no resolvable declared font size.')
            values.append(current * width_mm / vb[2] * 72 / 25.4)
        for child in element:
            walk(child, current, in_text)
            if in_text and child.tail and child.tail.strip():
                if current is None:
                    raise ValueError('Visible text has no resolvable declared font size.')
                values.append(current * width_mm / vb[2] * 72 / 25.4)
    try:
        walk(root, None)
    except ValueError as exc:
        return [], str(exc)
    return (values, None) if values else ([], 'No measurable visible SVG text found.')


def check(path: Path, target_width: float, max_height: float, reference: Path | None = None,
          min_font_pt: float | None = None, tolerance_mm: float = .01) -> dict:
    if any(not math.isfinite(v) or v <= 0 for v in (target_width, max_height)):
        raise ValueError('Target dimensions must be positive and finite.')
    if not math.isfinite(tolerance_mm) or tolerance_mm < 0:
        raise ValueError('Tolerance must be finite and non-negative.')
    if min_font_pt is not None and (not math.isfinite(min_font_pt) or min_font_pt <= 0):
        raise ValueError('Minimum font must be positive and finite.')
    text, root = read_svg(path)
    width, height = dimensions(root)
    errors, review = [], []
    dimension_reason = dimension_review_reason(text, root)
    if dimension_reason:
        review.append('CSS_DIMENSIONS_REQUIRE_RENDERER_REVIEW')
    if abs(width - target_width) > tolerance_mm:
        errors.append('WIDTH_MISMATCH')
    if height > max_height + tolerance_mm:
        errors.append('HEIGHT_EXCEEDED')
    aspect = 'NOT_CHECKED'
    if reference:
        _, previous = read_svg(reference)
        old_width, old_height = dimensions(previous)
        same_ratio = math.isclose(width / height, old_width / old_height, rel_tol=1e-7, abs_tol=1e-9)
        same_content = root_size_free(root) == root_size_free(previous)
        aspect = 'PASS' if same_ratio and same_content else 'FAIL'
        if not same_ratio:
            errors.append('VIEWPORT_RATIO_CHANGED')
        if not same_content:
            errors.append('RAW_EXPORT_CONTENT_CHANGED')
    font = {'status': 'NOT_REQUESTED'}
    if min_font_pt is not None:
        values, reason = declared_font_points(root, width, height)
        if reason:
            font = {'status': 'REVIEW', 'reason': reason}
            review.append('FONT_REQUIRES_RENDERER_REVIEW')
        else:
            minimum = min(values)
            font = {'status': 'PASS' if minimum + 1e-7 >= min_font_pt else 'FAIL',
                    'minimum_declared_pt': minimum, 'required_pt': min_font_pt}
            if font['status'] == 'FAIL':
                errors.append('FONT_BELOW_MINIMUM')
    return {'status': 'FAIL' if errors else ('REVIEW' if review else 'PASS'),
            'source': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'width_mm': width, 'height_mm': height, 'target_width_mm': target_width,
            'max_height_mm': max_height, 'tolerance_mm': tolerance_mm,
            'dimension_status': ('FAIL' if any(e in errors for e in ('WIDTH_MISMATCH', 'HEIGHT_EXCEEDED'))
                                 else ('REVIEW' if dimension_reason else 'PASS')),
            'dimension_evidence': 'absolute root attributes', 'dimension_review_reason': dimension_reason,
            'raw_export_comparison_status': aspect, 'declared_font_check': font,
            'errors': errors, 'review': review,
            'not_checked': ['text_fit', 'glyph_or_font_availability', 'rendering', 'scientific_correctness']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('svg', type=Path)
    parser.add_argument('--width-mm', type=float, required=True)
    parser.add_argument('--max-height-mm', type=float, required=True)
    parser.add_argument('--reference', type=Path, help='Raw SVG export before root-dimension normalization, not the old layout.')
    parser.add_argument('--min-font-pt', type=float)
    parser.add_argument('--tolerance-mm', type=float, default=.01)
    parser.add_argument('--json-out', type=Path)
    args = parser.parse_args()
    if args.json_out and args.json_out.exists():
        parser.error(f'refusing to overwrite report: {args.json_out}')
    try:
        result = check(args.svg, args.width_mm, args.max_height_mm, args.reference, args.min_font_pt, args.tolerance_mm)
    except (OSError, ValueError, ET.ParseError) as exc:
        result = {'status': 'FAIL', 'errors': ['INPUT_ERROR'], 'message': str(exc)}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return {'PASS': 0, 'FAIL': 1, 'REVIEW': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
