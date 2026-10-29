# Validation and export

## Profiles

- `strict`: for new output. Semantic edges require bound endpoints; undeclared topology, collisions, orphan helpers, and content drift are errors.
- `legacy-audit`: for historical artifacts. Report legacy free endpoints and unsupported structures without rewriting the file. A warning is not a strict pass.

## Validation layers

1. **Parse and structure:** XML, pages, unique IDs, parents, geometry, styles, and references.
2. **Content and topology:** exact or declared normalized labels, rich-text emphasis, approved source-target pairs, degrees, required paths, forbidden edges, terminals, merges, and feedback.
3. **Geometry:** bounds, overlap, rank or lane alignment, text fit, route corridors, and change impact.
4. **Connectors:** binding, orthogonality, non-endpoint box and text intersections, arrow direction, final approach, junction references, and unintended crossings.
5. **Visual and editability:** rendered hierarchy, parallelism, ambiguous trunks, selectable nodes and connectors, and target-application behavior.

Machine reports should identify page, object ID, severity, category, evidence, and proposed next action. Distinguish safe geometric regeneration from changes requiring scientific or aesthetic approval.

For dimension adaptation, [resize-existing.md](resize-existing.md) owns the
baseline comparison and final export workflow. Report their results separately
from structural validation. `TEXT_OVERFLOW` checks use supplied `measured_text`
only; its absence is unmeasured, not a text-fit PASS. Physical-size checks do
not establish clipping, glyph/font availability, or target-application quality.

## Numeric tolerance

Default coordinate epsilon is `max(0.05 draw.io unit, long_canvas_side * 1e-4)`. Treat an axis delta within epsilon as serialization noise for orthogonality. Use a separate clearance parameter for collision tests; never use epsilon to excuse a line running through a box.

## SVG model

Keep distinct:

1. draw.io page coordinates and page size;
2. SVG `viewBox`;
3. SVG root `width` and `height`;
4. target-application artboard, font, clipping, and resave behavior.

Choose the export invariant from downstream use:

- physical page fidelity: verified PDF or physical SVG when appropriate;
- convenient vector editing: SVG followed by target-application inspection;
- final publication raster: render from the final composition at required size and resolution;
- long-term editability: retain `.drawio` and the final composition source.

Preserve raw draw.io SVG separately from a physical-size-normalized or application-resaved derivative. Export-dialog preview dimensions are not authoritative; inspect the serialized file and, when physical size or typography matters, measure it in the actual target application.
