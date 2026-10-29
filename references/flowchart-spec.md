# FlowchartSpec

Use this schema as the auditable contract among concept discovery, generation, and validation. The canonical on-disk form is JSON. In conversation, present compact tables rather than raw JSON unless the user asks for it.

## Required top-level fields

- `schema_version`: currently `1`.
- `metadata`: `title`, `page_name`, and optional `language`, `purpose`, `downstream_application`, and `version`.
- `authority`: identify authoritative content and topology sources; record whether reference images have content authority. Default `reference_images_are_content_authority` to `false`.
- `canvas`: `width`, `height`, optional `unit`, `page_scale`, `margin`, and `fixed`.
- `typography`: default `font_family`, `font_size`, `line_height`, and padding.
- `nodes`: stable IDs, exact labels, geometry when layout-frozen, and semantic roles.
- `edges`: stable IDs, source and target IDs, semantic type, and optional route points.
- `approvals`: at minimum `content_topology` and `artifact_mutation` booleans.
- `validation`: optional expected degrees, forbidden edges, required paths, tolerances, and intentional exceptions.

## Optional publication adaptation fields

- `baseline`: `path` and `sha256` identify the preserved original. Resolve the
  path against the spec location when relative; verify the digest before use.
- `publication`: `target_width_mm`, `max_height_mm`, `format` (currently SVG
  for automated physical-export checks), `size_basis` (`page` or `cropped`),
  optional `min_font_pt`, `allowed_changes`, and `assumptions`.

These fields are backward-compatible task records, not implicit approval or
automatic generator/validator enforcement. Existing scripts still require
explicit command arguments. Node geometry and font_size remain draw.io user
units; do not enter millimeters directly as node coordinates. The adaptation
workflow and checker meanings are owned by [resize-existing.md](resize-existing.md).

## Node fields

Required before generation:

- `id`: stable and unique within the specification.
- `label`: authoritative serialized label; rich HTML is allowed.
- `kind`: `node`, `junction`, `lane`, `group`, or `annotation`.
- `role`: such as `start`, `process`, `decision`, `terminal`, `merge`, `feedback-target`, or a user-defined role.
- `x`, `y`, `width`, `height`: required only after geometry freeze.

Coordinates are page-local for top-level nodes and parent-local for nodes inside a lane or group. A layout plan must state which coordinate space it uses.

Optional:

- `rank`, `lane`, `group`, or `parent`.
- `terminal`: explicit semantic terminal flag.
- `style`: draw.io style overrides or named style tokens.
- `text_state`: `draft`, `semantic-frozen`, or `typography-frozen`.
- `measured_text`: measured width, height, font identity, and measurement engine.
- `intentional_duplicate_label`: distinguish repeated display text from accidental duplication.

## Edge fields

- `id`, `source`, and `target` are required for semantic edges.
- `type`: `main`, `branch`, `merge`, `feedback`, or `annotation`.
- `semantic`: defaults to `true`; annotations may set it to `false`.
- `points`: ordered orthogonal or declared non-orthogonal waypoints.
- `source_anchor` and `target_anchor`: normalized `x`, `y` pairs in `[0,1]`.
- `arrow`: `block`, `open`, or `none`.
- `style`: optional scoped overrides.
- `allow_free_endpoint`: allowed only for a non-semantic annotation and must be paired with an explicit source or target point.

## Validation fields

Useful entries include:

- `coordinate_epsilon`: default is `max(0.05, long_canvas_side * 1e-4)`.
- `clearance`: independent of coordinate epsilon.
- `expected_degrees`: map node IDs to `[indegree, outdegree]`.
- `forbidden_edges`: source-target pairs that must not exist.
- `required_paths`: ordered node sequences.
- `intentional_free_edges`, `intentional_crossings`, and `intentional_overlaps`.
- `label_policy`: `exact`, `normalized`, or a per-node override.

## Approval semantics

`content_topology=true` means the user has approved wording and material relations sufficiently for layout. `artifact_mutation=true` means the user has approved the complete design and verification plan and authorized the specified file creation or modification. A script flag must not be used to manufacture approval; if a legacy spec lacks the fields, return to the user for confirmation.

## Minimal generation example

```json
{
  "schema_version": 1,
  "metadata": {"title": "Example", "page_name": "Example v1"},
  "authority": {"reference_images_are_content_authority": false},
  "canvas": {"width": 600, "height": 400, "fixed": true, "margin": 20},
  "typography": {"font_family": "Arial", "font_size": 12, "line_height": 1.2, "padding": 6},
  "approvals": {"content_topology": true, "artifact_mutation": true},
  "nodes": [
    {"id": "start", "label": "Start", "kind": "node", "role": "start", "x": 220, "y": 20, "width": 160, "height": 40},
    {"id": "end", "label": "End", "kind": "node", "role": "terminal", "terminal": true, "x": 220, "y": 120, "width": 160, "height": 40}
  ],
  "edges": [
    {"id": "e1", "source": "start", "target": "end", "type": "main", "points": []}
  ],
  "validation": {"expected_degrees": {"start": [0, 1], "end": [1, 0]}}
}
```
