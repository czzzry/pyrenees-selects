# Getting started with Selects

Selects is an Intel Mac-first, local footage pre-editor. It turns a folder into lightweight ranked proposals, lets you verify them against every full source, saves exact ranges and comments, assembles reversible cuts, and exports to DaVinci Resolve. It never modifies your originals.

## Before you begin

You need:

- an Intel Mac running macOS 12 or later;
- Python 3.11 or later;
- FFmpeg and ffprobe; and
- a folder containing MP4, MOV, or M4V footage.

The current public alpha is source-installed. A signed and notarized downloadable app is a release gate, not a completed claim.

## Install from source

1. Install the system prerequisites with [Homebrew](https://brew.sh/) if they are not already present:

   ```bash
   brew install python@3.13 ffmpeg
   ```

2. Download the repository:

   ```bash
   git clone https://github.com/czzzry/pyrenees-selects.git
   cd pyrenees-selects
   ```

3. Run the checked-in installer:

   ```bash
   ./scripts/bootstrap_selects.sh
   ```

4. Start Selects:

   ```bash
   ./scripts/run_selects.sh
   ```

Selects opens at <http://localhost:8741>. Keep that terminal window open while you use the app. Press `Control-C` there to stop it.

## Your first project

1. Name the project and choose a footage folder.
2. Choose a target film duration and rough shot rhythm. These determine how much material Selects proposes; they never delete footage. Use **Advanced planning** only if you want fewer/more options or visual-only ranking.
3. Check the calculated overnight plan. If the disk gate is red, choose another cache folder or use **Review full sources without analysis**.
4. Start preparation. You can close the loop by pausing safely, resuming later, reviewing completed proposals before the run ends, and retrying or skipping individual failures.
5. In **Review**, play a proposal, open the full source at the same source timestamp, adjust In/Out, leave a useful comment, and save Keep, Maybe, or Skip.
6. Open **Assemble**. Add Keep and Maybe selections to the cut; unused choices remain available as alternates.
7. Save a frozen sequence version, render a lightweight preview, then export the FCPXML/JSON handoff for DaVinci Resolve.

The first proof of value is one saved range whose comment and source timing survive all the way into the Resolve handoff.

## Where data is stored

On macOS, Selects stores its database, previews, backups, and exports under:

```text
~/Library/Application Support/Selects/
```

Your footage remains in the folders you chose. Disconnecting a drive marks a source offline; it does not erase selections.

## Troubleshooting

Run the installation check:

```bash
.venv-selects/bin/selects doctor
```

- **`ffmpeg` or `ffprobe` missing:** run `brew install ffmpeg`, then retry the installer.
- **Python is too old:** run `brew install python@3.13`, then ensure `python3 --version` reports 3.11 or newer.
- **A source is offline:** reconnect its drive and use **Relink original**. Selects verifies the file before retaining the old decisions.
- **Large HEVC originals stutter:** use the overnight plan or **Sources** to prepare disposable full-length review copies. The full original remains available and the Resolve handoff always links to it.
- **The overnight run was interrupted:** reopen the project. In-progress work becomes **Paused safely**; completed proposals and checkpoint data remain available.
- **The cache fills up:** partial output is removed and the run pauses. Choose a cache on a drive with the displayed required space plus reserve, then build a fresh plan.
- **A source changed after planning:** rescan it. Selects marks the old plan stale rather than applying old timestamps to different bytes.
- **Port 8741 is busy:** run `./scripts/run_selects.sh --port 8742` and open the displayed address.

## Update or uninstall

To update a source installation, pull the new code and rerun the installer:

```bash
git pull --ff-only
./scripts/bootstrap_selects.sh
```

To remove only the source-installed runtime, delete `.venv-selects` inside the repository. To remove local Selects projects as well, first make any desired backups and then delete `~/Library/Application Support/Selects`. Neither action deletes original footage.
