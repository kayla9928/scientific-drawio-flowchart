# Layout and typography

## Select the layout from graph structure

- **Linear:** one dominant ordered path with little branching.
- **Tree or DAG:** topologically ordered branches and merges. A tree has at most one semantic parent per ordinary node; use DAG treatment when paths merge or share descendants.
- **Swimlane:** responsibility, experimental stage, system, or actor ownership is a primary meaning. Do not add lanes as decoration.
- **Hub-and-spoke:** one central entity relates to many comparatively independent nodes and strict temporal order is weak.
- **Cyclic or feedback:** feedback is scientifically meaningful. Establish a readable forward backbone and reserve outer corridors for return edges.
- **Mixed:** create a global skeleton, then use local sublayouts inside groups. Keep group portals and inter-group edges explicit.

Rank candidates by semantic fidelity, risk of false spatial implication, crossings and long edges, canvas fit, long-label capacity, edit stability, and downstream aspect ratio. Scientific truth outranks symmetry.

## Text states

- `draft`: wording or relations may change; do not request exact coordinates or pixel-perfect boxes.
- `semantic-frozen`: meaning and material wording are approved; measure the actual intended font.
- `typography-frozen`: font, size, emphasis, line breaks, and box geometry are approved enough for final routing.

Preserve both authoritative source text and serialized display text. A line break may change only when it does not alter wording or emphasis. Never silently paraphrase, truncate, or shrink text.

## Measurement and boxes

Measure with the intended font and record the font file or fallback, size, line height, engine, and resulting bounds. Rich text spans, italics, symbols, and smaller explanatory text need independent handling. `overflow=hidden` is not evidence that text fits.

Calculate each box from measured text plus padding, stroke, and a small rendering safety allowance. Store measurements so layout can be recomputed when wording changes.

When reliable measurements are unavailable, report text-fit evidence as
unmeasured or approximate and inspect the rendered output. The optional
`scripts/lib/typography.py` Pillow helper is not called automatically by the
generator or validator. Its width measurement and estimated line height are
not a full rich-text/wrapping engine. Never label an approximation as verified
fitting text. For publication resizing, follow [resize-existing.md](resize-existing.md).

## Fixed canvas solving

1. Reserve margins and semantic group or lane separators.
2. Compute minimum box sizes from frozen text.
3. Allocate rows, columns, and routing corridors together rather than sizing each box independently.
4. Check width, height, minimum gaps, arrow approaches, and text fit.
5. If infeasible, present the smallest relaxations: semantic line breaks, local width redistribution, row-height changes, orientation or rank changes, font changes, canvas changes, or splitting only if the user allows it.

Do not encode any publication size, clinical layer, font, coordinate, or palette as a universal default.

## Geometry freeze

Final connectors depend on final node geometry. After moving or resizing a node, invalidate all incident routes and recheck neighboring boxes, corridors, perceived parent-child alignment, bounds, and wrapping. Preliminary abstract edges may guide layout, but final waypoints are generated only after geometry freeze.
