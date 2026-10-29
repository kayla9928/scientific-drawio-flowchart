#!/usr/bin/env python3
"""Read-only baseline comparison for single-page, uncompressed draw.io files."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


class Unsupported(ValueError):
    pass


def styles(value: str) -> dict[str, str]:
    return dict(part.split('=', 1) for part in value.split(';') if '=' in part)


def load(path: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    if b'<!ENTITY' in raw.upper() or b'<!DOCTYPE' in raw.upper():
        raise Unsupported('DTD/entity-bearing source requires manual review.')
    root = ET.fromstring(raw)
    if root.tag != 'mxfile':
        raise Unsupported('Expected mxfile with one uncompressed page.')
    pages = root.findall('diagram')
    if len(pages) != 1 or pages[0].find('mxGraphModel/root') is None:
        raise Unsupported('Only one uncompressed page is supported; export it as uncompressed XML.')
    cells = pages[0].find('mxGraphModel/root')
    if any(cell.tag != 'mxCell' for cell in cells):
        raise Unsupported('Wrapped/custom cells require an explicit mapping or manual comparison.')
    ids = [cell.get('id') for cell in cells]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError('Missing or duplicate cell IDs.')
    nodes, edges = {}, {}
    for cell in cells:
        key = cell.get('id')
        st = styles(cell.get('style', ''))
        common = {'label': cell.get('value', ''), 'parent': cell.get('parent'),
                  'fontStyle': st.get('fontStyle', '0'), 'html': st.get('html', '0')}
        if cell.get('vertex') == '1':
            nodes[key] = common
        elif cell.get('edge') == '1':
            edges[key] = dict(common, source=cell.get('source'), target=cell.get('target'),
                              startArrow=st.get('startArrow', 'none'),
                              endArrow=st.get('endArrow', 'none'))
    if not nodes:
        raise Unsupported('No editable vertices found.')
    if any(not e['source'] or not e['target'] for e in edges.values()):
        raise Unsupported('Free-endpoint edges require manual comparison.')
    if any(e['source'] not in nodes or e['target'] not in nodes for e in edges.values()):
        raise ValueError('An edge references a non-vertex endpoint.')
    return nodes, edges


def without_breaks(label: str, html_enabled: bool) -> str:
    if html_enabled:
        label = re.sub(r'<br\s*/?>', '', label, flags=re.I)
    return label.replace('\r\n', '').replace('\r', '').replace('\n', '')


def compare(baseline: Path, candidate: Path, allow_linebreaks: set[str], expected_sha256: str | None = None) -> dict:
    result = {'status': 'PASS', 'baseline': str(baseline.resolve()),
              'candidate': str(candidate.resolve()), 'findings': [], 'allowed_linebreak_changes': [],
              'not_checked': ['geometry', 'physical_export_size', 'text_fit', 'scientific_correctness']}
    for name, path in (('baseline_sha256', baseline), ('candidate_sha256', candidate)):
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 is not None and result['baseline_sha256'] != expected_sha256.lower():
        raise ValueError('Baseline SHA-256 differs from the frozen original; recover the baseline before comparing.')
    try:
        old_nodes, old_edges = load(baseline)
        new_nodes, new_edges = load(candidate)
    except Unsupported as exc:
        result.update(status='REVIEW', findings=[{'category': 'UNSUPPORTED_SOURCE', 'message': str(exc)}])
        return result
    unknown = allow_linebreaks - (old_nodes.keys() | old_edges.keys())
    if unknown:
        raise ValueError(f'Unknown approved line-break IDs: {sorted(unknown)}')
    for kind, old, new in (('node', old_nodes, new_nodes), ('edge', old_edges, new_edges)):
        for key in sorted(old.keys() - new.keys()):
            result['findings'].append({'category': 'MISSING_OBJECT', 'kind': kind, 'id': key})
        for key in sorted(new.keys() - old.keys()):
            result['findings'].append({'category': 'ADDED_OBJECT', 'kind': kind, 'id': key})
        for key in sorted(old.keys() & new.keys()):
            for field in old[key]:
                a, b = old[key][field], new[key][field]
                if a == b:
                    continue
                if field == 'label' and key in allow_linebreaks:
                    if old[key]['html'] == new[key]['html'] and without_breaks(a, old[key]['html'] == '1') == without_breaks(b, new[key]['html'] == '1'):
                        result['allowed_linebreak_changes'].append(key)
                        continue
                result['findings'].append({'category': 'BASELINE_DRIFT', 'kind': kind, 'id': key,
                                           'field': field, 'before': a, 'after': b})
    result['counts'] = {'baseline_nodes': len(old_nodes), 'candidate_nodes': len(new_nodes),
                        'baseline_edges': len(old_edges), 'candidate_edges': len(new_edges)}
    if result['findings']:
        result['status'] = 'FAIL'
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--allow-linebreaks', action='append', default=[], metavar='CELL_ID',
                        help='Repeat only for IDs whose line-break-only edits were approved; spaces/emphasis remain protected.')
    parser.add_argument('--json-out', type=Path)
    parser.add_argument('--baseline-sha256', help='Digest of the independently frozen original, if recorded.')
    args = parser.parse_args()
    if args.json_out and args.json_out.exists():
        parser.error(f'refusing to overwrite report: {args.json_out}')
    try:
        result = compare(args.baseline, args.candidate, set(args.allow_linebreaks), args.baseline_sha256)
    except (OSError, ValueError, ET.ParseError) as exc:
        result = {'status': 'FAIL', 'findings': [{'category': 'INPUT_ERROR', 'message': str(exc)}]}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return {'PASS': 0, 'FAIL': 1, 'REVIEW': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
