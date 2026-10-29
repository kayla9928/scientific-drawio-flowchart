# Routing and connectors

## Binding and ports

Every newly generated semantic edge must bind to valid source and target IDs. Choose source and target sides from the dominant flow direction, available corridors, and semantic reading. Record normalized anchors when the default center-side attachment is insufficient.

Use orthogonal routing by default for dense directed publication workflows. Hub-and-spoke, feedback, or explicitly curved designs may use another declared routing type. Do not claim orthogonality solely because the draw.io style names an orthogonal router; verify the serialized or rendered segments.

## Branches

A source may have multiple bound outgoing edges. Use a visible split junction when a shared trunk is semantically meaningful or improves inspectability. Do not serialize parallel concepts as a chain merely to simplify routing.

## Merges and junctions

Multiple edges may enter a target directly when the merge is unambiguous. Use a visible, referenced junction when paths join into a shared bus or the merge itself must be inspectable. A junction is a semantic vertex with expected degrees, not an invisible routing hack.

Reject unreferenced hidden or tiny helper vertices. Waypoints belong to edge geometry and do not need helper cells.

## Terminals and feedback

A declared terminal has semantic outdegree zero unless an explicitly approved feedback edge creates an exception. Do not attach a terminal to a nearby merge for symmetry or convenience.

Route feedback outside the forward-flow core when possible. Mark it as feedback, preserve arrow direction, and avoid sharing an ambiguous trunk with ordinary merges.

## Clearance and arrow approaches

- Do not cross non-endpoint node interiors or text safety regions.
- Reserve a clean final approach long enough for the arrowhead.
- Verify the final segment enters the intended side and is axis-aligned within coordinate tolerance when orthogonality is required.
- Avoid crossings; if unavoidable, document them as intentional and verify that the export does not create a false junction.
- Recompute incident routes after every node move or resize.

Annotation edges are excluded from semantic degree checks. A free annotation endpoint is allowed only when explicitly declared and visually unambiguous.
