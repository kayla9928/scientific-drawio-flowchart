# Concept to specification

Use this mode when the user has scientific content but not a complete graph, path, or canvas.

## Sequence

1. Identify the communication objective, audience, downstream application, language, and required editability.
2. Build an authority map: separate authoritative wording, authoritative relationships, optional style references, inferred assumptions, and unknowns.
3. Create a node inventory without assigning exact geometry. Give each concept a stable temporary ID and a tentative role.
4. Create an edge inventory. Mark each relation as confirmed, inferred, disputed, or unknown.
5. Identify branches, merges, terminals, feedback, annotations, lanes, and groups. Do not infer a scientific relation solely from visual proximity in a reference image.
6. Compare plausible topology and layout families. Show material tradeoffs; avoid cosmetic alternatives that do not change the decision.
7. Produce an approval-ready specification and a complete file/version/verification plan.

## Stop conditions

Stop and request a decision when any unresolved point would change:

- the direction or existence of a semantic edge;
- whether a node is parallel, nested, terminal, merged, or part of feedback;
- authoritative wording or scientific qualifiers;
- whether a visual reference may supply scientific content;
- a fixed constraint that makes the layout infeasible.

Do not stop for details that can be safely parameterized, such as provisional colors or small gap adjustments, provided they are disclosed.

## Approval-ready output

Present:

- objective and authority map;
- node and edge tables;
- unresolved assumptions;
- recommended topology and rejected alternatives;
- major hierarchy, lanes, groups, branches, merges, terminals, feedback, and annotations;
- canvas policy and downstream export invariant;
- wording and typography state;
- output location and version policy;
- automated checks and required human review;
- exact files that would be created or modified.

Wait for explicit approval before writing a specification file, draw.io file, preview, export, or validation report to disk.
