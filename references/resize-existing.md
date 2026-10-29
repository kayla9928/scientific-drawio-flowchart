# Adapt an existing flowchart to publication dimensions

Use for a new column width, bounded height, or changed submission dimensions of
an existing editable flowchart. Compose the existing generation and export
modes; do not restart scientific content discovery when content is confirmed.

## Freeze the actual target

Record the approved baseline file and SHA-256, delivered format, target width,
maximum height, and units. Distinguish whole-page size from cropped drawing
size. Record any minimum final font size and allowed changes to fonts, line
width, wrapping, orientation, canvas, and splitting. Missing typography limits
may use disclosed assumptions; they do not establish journal compliance.
Publication width, height, and font size have no universal defaults.

Use the optional `publication` and `baseline` objects in
[FlowchartSpec](flowchart-spec.md) to retain these task constraints. They do not
authorize edits, change coordinate units, or activate checks by themselves.
Keep source text, meaningful emphasis, nodes, and relations authoritative.

## Baseline and strategy

- Preserve the original. Use one explicitly selected baseline, independent of
  the newly edited specification, and write a separately named output.
- Prefer proportional scaling only if final typography, lines, and legibility
  remain acceptable. Otherwise change geometry, allowed line breaks, spacing,
  and edge corridors under the approved constraints. A changed node geometry
  invalidates its routes; recheck before export.
- Never silently shrink a font below the approved limit, delete text, merge
  nodes, change relations, or split a figure to force a fit. Report infeasible
  constraints and the smallest useful relaxation.
- The deterministic baseline comparator supports stable IDs in single-page,
  uncompressed draw.io XML with bound edges. Compressed/multipage files,
  wrapped/custom cells, free endpoints, or a wholesale ID change require an
  explicit mapping or reviewed extraction/export, not guessed matches. Do not
  turn the file into a flattened picture to pass comparison.

## Compare before exporting

Run `scripts/compare_flowcharts.py BASELINE.drawio CANDIDATE.drawio` and pass
`--baseline-sha256 DIGEST` when the original was frozen with a recorded hash.
It checks node/edge identity, parents, labels, emphasis flags, and edge ends
and arrows; geometry, sizing, and font family/size can differ. This is not
scientific fact-checking or a check of every color/style convention.

Only when line-break-only changes were approved, repeat
`--allow-linebreaks CELL_ID` for the affected stable IDs. It allows literal
newlines and simple HTML `<br>` changes, not deletion of ordinary spaces,
nonbreaking spaces, words, or emphasis markup. Other desired content/structure
changes belong to a newly approved baseline, not a permissive comparison flag.

Then run `validate_drawio.py` with the approved new spec and appropriate
profile. Neither this structural PASS nor the baseline PASS certifies physical
dimensions or text fit.

## Check the exported file

Render/export using available draw.io tooling. Retain the raw SVG export and
write its physical-size derivative using the existing normalizer:

```text
normalize_svg_size.py RAW.svg FINAL.svg --width TARGETmm --max-height LIMITmm
check_svg_size.py FINAL.svg --width-mm TARGET --max-height-mm LIMIT --reference RAW.svg
```

Omitting `--height` computes a proportional height from the raw SVG viewport;
exceeding the height ceiling stops without writing output. Explicit `--height`
retains legacy behavior and can change viewport proportions: do not treat that
successful write as aspect-ratio validation. Re-layout when necessary.

The reference for `check_svg_size.py` is the raw export of the **new layout**,
not the pre-adaptation diagram. It verifies viewport ratio and unchanged XML
content except the root width/height. Default dimension tolerance is 0.01 mm;
use an explicit tighter tolerance if needed. Unsupported absolute dimensions
must be resolved, not interpreted as a pass. No command changes page layout.
Stylesheets or root CSS sizing may override root attributes: the checker marks
dimension evidence REVIEW, and proportional normalization refuses unresolved
CSS sizing. Resolve it with renderer evidence instead of claiming a numeric pass.

If a final minimum font was confirmed, add `--min-font-pt LIMIT`. Declaration
conversion covers simple SVG text with resolvable absolute sizes and supported
inheritance. Foreign objects, stylesheets, nontrivial transforms, nested SVG,
and other unresolved typography produce REVIEW. Declared font size is not
proof of available glyphs, fitting text, or matching target-application fonts.
Inspect the final physical artifact in a renderer/target application.

## Report independent results and stop

Report baseline consistency, structural/geometry validation, final physical
dimensions, typography evidence, and rendered/editable output separately.
Tool exit codes are PASS=0, FAIL=1, REVIEW=2 for the new checkers. PASS covers
their declared scope only; not-checked checks must remain visible. Missing
`measured_text` is not evidence that text fits. Optional Pillow measurement
helpers are not automatically invoked; do not make Pillow installation a
prerequisite for this resize workflow or invent measurement results.

Check final labels, clipping, arrows, branch/merge meaning, font substitution,
and editability using the actual artifact. If rendering tools are unavailable,
hand off the preserved source and mark that check incomplete. Stop when the
approved constraints and applicable checks are met, or report the exact
infeasible constraint; do not enter unbounded automatic retries.
