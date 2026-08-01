# Privacy

Selects is local-first. Creating and reviewing a project does not upload footage, thumbnails, filenames, comments, or usage data.

## Data stored on the computer

On macOS, the reusable app stores its database, lightweight preview cache, backups, and Resolve exports under:

```text
~/Library/Application Support/Selects/
```

Original footage stays in the folders the user selected. Selects reads those files and never modifies them. Removing a drive marks its sources offline without deleting decisions. Deleting Selects' application-data directory removes local project state and generated previews but does not remove originals.

## Optional assistant requests

Manual review, sequence assembly, preview rendering, and Resolve export work without an LLM.

If the user enters an OpenAI API key and requests a proposal, Selects sends a bounded project summary to OpenAI. It contains project settings, source metadata, exact selections, decisions, and comments. It excludes media bytes, local folder paths, source fingerprints, and the API key from persistent storage. The request uses `store: false`. OpenAI's own service terms and retention policies still apply to that request.

Codex, Claude, or another external agent sees only the information the user or agent explicitly reads. The documented `selects project context` command produces the same bounded, path-free summary.

Selects contains no analytics or telemetry in version 0.7.0.
