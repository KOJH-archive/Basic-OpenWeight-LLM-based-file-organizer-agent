# MVP decisions and threat boundaries

## Product promise

FlowGuard helps a person notice repeatable file-organization work without silently becoming an automation agent. The essential interaction is **observe → explain → preview → approve → act → undo**.

## Concrete workflow

1. The user selects exactly one root folder.
2. A read-only metadata scan gathers path, size, modification time and extension; symlinks and known tool folders are skipped.
3. Deterministic rules detect patterns. Only the aggregate descriptions are offered to the selected local-model provider.
4. Ollama or a loopback OpenAI-compatible server produces prose suggestions. Failure activates a deterministic safe fallback.
5. The planner can create only top-level moves for allowlisted extensions into `FlowGuard Organized/<category>` inside the root.
6. The executor validates all resolved source and destination paths. Dry-run is the initial mode. Real execution requires a confirmation dialog.
7. Every successful real move is recorded. Rollback processes the journal in reverse and never overwrites an occupied original path.

## Trust boundaries

- Untrusted: filenames, folder contents, local-model response text and saved journal files.
- Trusted enforcement: resolved-path checks, the constrained action data type, extension allowlist, confirmation dialog and collision policy.
- The model response is never parsed as code or an action. Provider changes cannot alter this boundary.

## Failure behavior

- Unavailable local server/model: show safe built-in advice; all non-AI features continue.
- Missing source during execution: record as skipped; continue.
- Existing destination: create `name (1).ext`, never overwrite.
- Existing original during rollback: skip, never overwrite.
- Escaped path or invalid action: stop execution with `SafetyError`.
- Scan access error on an individual file: skip that file; an invalid root fails visibly.

## Future work, not implied by this MVP

Windows notifications, native filesystem events, signed packaging, content-aware rules and richer rollback history require separate design and security review. Any future delete action should use the Recycle Bin, remain off by default and have its own explicit approval step.
