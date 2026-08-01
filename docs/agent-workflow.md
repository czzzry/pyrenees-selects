# Agent workflow

Selects treats Codex, Claude, and other LLM agents as optional collaborators, not database administrators.

## Install for a user

From a checked-out repository, verify Python 3.11 or later plus `ffmpeg` and `ffprobe`, then run:

```bash
./scripts/bootstrap_selects.sh
./scripts/run_selects.sh
```

Do not move, rename, transcode, or write into the user’s footage folders. Selects stores its database, cache, and exports under `~/Library/Application Support/Selects` on macOS (or the platform-equivalent local data directory).

## Work on a project

1. Ask the user to create a project and review footage in the app.
2. Find the project ID:

   ```bash
   selects --json project list
   ```

3. Read bounded context:

   ```bash
   selects --json project context PROJECT_ID
   ```

   This contains project intent, source metadata, selections, comments, and sequence versions. It omits footage bytes, source paths, and fingerprints.

4. Write a proposal JSON object. For a sequence proposal, the payload is:

   ```json
   {
     "selection_ids": ["selection_…"],
     "name": "Agent first cut",
     "note": "Narrative rationale"
   }
   ```

5. Record it without applying it:

   ```bash
   selects proposal create PROJECT_ID \
     --provider codex \
     --kind sequence \
     --payload proposal.json \
     --explanation "Why this order serves the user's intent"
   ```

6. Tell the user the proposal is ready to inspect in the Assistant tab. Do not apply it unless they explicitly ask you to do so.

Accepted proposals create a new immutable sequence version. Rejected proposals remain in history. Direct SQLite edits are outside the supported contract.

## Built-in API mode

The Assistant tab can call OpenAI’s Responses API with a key supplied for that single request. The server sends only the path-free project context and sets `store: false`. The key is not persisted. The result still enters Selects as a pending proposal.
