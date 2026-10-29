"""Impact-scoped tests with synthetic fixtures and temporary outputs.

Use a writable TEMP/TMP directory when a sandbox's default temporary location
cannot support file creation by child processes. No installed Skill is changed.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_svg_size import check, read_svg
from compare_flowcharts import compare


def run_tool(name, arguments):
    return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(ROOT / 'scripts' / name), *map(str, arguments)],
                          text=True, encoding='utf-8', capture_output=True,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1'))


class ResizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='drawio-resize-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def svg(self, name='raw.svg', width='307px', height='632px', extra='', body=None):
        body = body if body is not None else '<g font-size="10.6666666667px"><text x="10" y="20">Synthetic label</text></g>'
        path = self.path / name
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 307 632" {extra}>{body}</svg>', encoding='utf-8')
        return path

    def generated(self):
        spec = ROOT / 'tests' / 'cases' / 'branching-dag.json'
        old = self.path / 'baseline.drawio'
        result = run_tool('build_drawio.py', [spec, old])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return old

    def mutate(self, baseline, change, name='candidate.drawio'):
        tree = ET.parse(baseline)
        change(tree)
        target = self.path / name
        tree.write(target, encoding='utf-8', xml_declaration=True)
        return target

    def cell(self, tree, key):
        return tree.getroot().find(f".//mxCell[@id='{key}']")

    def test_geometry_only_and_old_spec(self):
        old = self.generated()
        new = self.mutate(old, lambda t: self.cell(t, 'SDF-start').find('mxGeometry').set('x', '250'))
        self.assertEqual(compare(old, new, set())['status'], 'PASS')
        proc = run_tool('validate_drawio.py', [old, '--spec', ROOT / 'tests/cases/branching-dag.json'])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_frozen_baseline_digest(self):
        old = self.generated()
        digest = hashlib.sha256(old.read_bytes()).hexdigest()
        self.assertEqual(compare(old, old, set(), digest)['status'], 'PASS')
        with self.assertRaises(ValueError):
            compare(old, old, set(), '0' * 64)

    def test_approved_linebreak_not_spaces_or_emphasis(self):
        old = self.generated()
        new = self.mutate(old, lambda t: self.cell(t, 'SDF-decision').set('value', 'Assess<br> condition'))
        self.assertEqual(compare(old, new, set())['status'], 'FAIL')
        self.assertEqual(compare(old, new, {'SDF-decision'})['status'], 'PASS')
        for text in ('Assesscondition', 'Assess<br>condition', '<b>Assess condition</b>'):
            candidate = self.mutate(old, lambda t: self.cell(t, 'SDF-decision').set('value', text))
            self.assertEqual(compare(old, candidate, {'SDF-decision'})['status'], 'FAIL')

    def test_changed_text_topology_identity_and_fontstyle(self):
        old = self.generated()
        changes = [
            lambda t: self.cell(t, 'SDF-start').set('value', 'Wrong'),
            lambda t: self.cell(t, 'SDF-e-a-merge').set('source', 'SDF-terminal-exception'),
            lambda t: self.cell(t, 'SDF-start').set('id', 'renamed-start'),
            lambda t: self.cell(t, 'SDF-start').set('style', self.cell(t, 'SDF-start').get('style') + 'fontStyle=1;'),
        ]
        for change in changes:
            with self.subTest(change=change):
                candidate = self.mutate(old, change)
                try:
                    status = compare(old, candidate, set())['status']
                except ValueError:
                    status = 'FAIL'
                self.assertEqual(status, 'FAIL')

    def test_unsupported_sources_are_review(self):
        old = self.generated()
        for xml in ('<mxfile><diagram>compressed</diagram></mxfile>',
                    '<mxfile><diagram/><diagram/></mxfile>',
                    '<mxfile><diagram><mxGraphModel><root><object/></root></mxGraphModel></diagram></mxfile>'):
            path = self.path / 'unsupported.drawio'
            path.write_text(xml, encoding='utf-8')
            self.assertEqual(compare(old, path, set())['status'], 'REVIEW')

    def test_proportional_normalization_and_checks(self):
        raw = self.svg()
        output = self.path / 'physical.svg'
        proc = run_tool('normalize_svg_size.py', [raw, output, '--width', '86mm', '--max-height', '210mm'])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        data = check(output, 86, 210, raw, 8)
        self.assertEqual(data['status'], 'PASS', data)
        self.assertAlmostEqual(data['height_mm'], 86 * 632 / 307, places=7)
        self.assertAlmostEqual(data['declared_font_check']['minimum_declared_pt'], 8.4700813, places=5)
        self.assertIn('text_fit', data['not_checked'])

    def test_width_height_and_min_font_failures(self):
        wrong_width = self.svg('width.svg', '85mm', '177mm')
        self.assertIn('WIDTH_MISMATCH', check(wrong_width, 86, 210)['errors'])
        tall = self.svg('tall.svg', '86mm', '211mm')
        self.assertIn('HEIGHT_EXCEEDED', check(tall, 86, 210)['errors'])
        small = self.svg('small.svg', '86mm', f'{86 * 632 / 307}mm', body='<text font-size="5px">Small</text>')
        self.assertIn('FONT_BELOW_MINIMUM', check(small, 86, 210, min_font_pt=8)['errors'])

    def test_ratio_and_non_root_content_drift(self):
        raw = self.svg()
        distorted = self.svg('distorted.svg', '86mm', '100mm')
        self.assertIn('VIEWPORT_RATIO_CHANGED', check(distorted, 86, 210, raw)['errors'])
        altered = self.svg('altered.svg', '86mm', f'{86 * 632 / 307}mm', body='<text font-size="11px">Changed</text>')
        self.assertIn('RAW_EXPORT_CONTENT_CHANGED', check(altered, 86, 210, raw)['errors'])

    def test_unresolved_font_is_review_not_text_fit_pass(self):
        bodies = [
            '<g transform="scale(2)"><text font-size="12px">Scale</text></g>',
            '<text font-size="80%">Relative</text>',
            '<foreignObject><div>HTML text</div></foreignObject>',
            '<text>Unspecified</text>',
            '<style>text { font-size: 12px; }</style><text>CSS</text>',
        ]
        for body in bodies:
            path = self.svg('review.svg', '86mm', f'{86 * 632 / 307}mm', body=body)
            result = check(path, 86, 210, min_font_pt=8)
            self.assertEqual(result['status'], 'REVIEW', result)
            self.assertIn(result['dimension_status'], ('PASS', 'REVIEW'))

    def test_smaller_tspan_is_not_missed(self):
        path = self.svg('smallspan.svg', '86mm', f'{86 * 632 / 307}mm',
                        body='<g font-size="12px"><text>Large<tspan style="font-size:4px">small</tspan></text></g>')
        self.assertIn('FONT_BELOW_MINIMUM', check(path, 86, 210, min_font_pt=8)['errors'])

    def test_height_ceiling_stops_without_output(self):
        raw = self.svg(height='1000px')
        output = self.path / 'must-not-exist.svg'
        before = raw.read_bytes()
        proc = run_tool('normalize_svg_size.py', [raw, output, '--width', '86mm', '--max-height', '210mm'])
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(output.exists())
        self.assertEqual(raw.read_bytes(), before)

    def test_legacy_explicit_size_and_root_only_replacement(self):
        raw = self.svg(extra='data-width="keep" style="width: 99px;"')
        # CSS root sizing is reviewed separately; root serialization must still be scoped correctly.
        output = self.path / 'legacy.svg'
        proc = run_tool('normalize_svg_size.py', [raw, output, '--width', '160mm', '--height', '100mm',
                     '--expect-width', '307px', '--expect-height', '632px', '--expect-viewbox', '0 0 307 632'])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        _, root = read_svg(output)
        self.assertEqual(root.get('width'), '160mm')
        self.assertEqual(root.get('data-width'), 'keep')
        self.assertEqual(root.get('style'), 'width: 99px;')
        self.assertEqual(check(output, 160, 210)['dimension_status'], 'REVIEW')
        proc_again = run_tool('normalize_svg_size.py', [raw, output, '--width', '160mm', '--height', '100mm'])
        self.assertNotEqual(proc_again.returncode, 0)

    def test_report_overwrite_and_bad_input(self):
        raw = self.svg()
        target = self.path / 'report.json'
        target.write_text('preserved', encoding='utf-8')
        proc = run_tool('check_svg_size.py', [raw, '--width-mm', '86', '--max-height-mm', '210', '--json-out', target])
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(target.read_text(encoding='utf-8'), 'preserved')
        bad = self.svg('bad.svg', '100%', '632px')
        proc = run_tool('check_svg_size.py', [bad, '--width-mm', '86', '--max-height-mm', '210'])
        self.assertEqual(proc.returncode, 1)

    def test_css_dimensions_are_not_certified(self):
        raw = self.svg(width='86mm', height='180mm', extra='style="width:99px"')
        result = check(raw, 86, 210)
        self.assertEqual(result['status'], 'REVIEW')
        self.assertEqual(result['dimension_status'], 'REVIEW')
        output = self.path / 'no-css-inference.svg'
        proc = run_tool('normalize_svg_size.py', [raw, output, '--width', '86mm', '--max-height', '210mm'])
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(output.exists())

    def test_commented_svg_is_not_the_output_root(self):
        raw = self.svg()
        raw.write_text('<!-- <svg width="bogus" height="bogus"> -->' + raw.read_text(encoding='utf-8'), encoding='utf-8')
        output = self.path / 'comment.svg'
        proc = run_tool('normalize_svg_size.py', [raw, output, '--width', '86mm', '--max-height', '210mm'])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(read_svg(output)[1].get('width'), '86mm')


if __name__ == '__main__':
    unittest.main(verbosity=2)
