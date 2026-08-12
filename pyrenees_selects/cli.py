from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

from .config import AppPaths
from .media import MediaToolError, require_media_tools
from .preeditor import PreEditor, ProjectOptions, SelectionDraft


def _database(data_dir: Path | None) -> Path:
    return AppPaths.build_selects(data_dir).database


def _emit(payload: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, str):
        print(payload)
        return
    if isinstance(payload, list):
        if not payload:
            print("No results.")
            return
        for item in payload:
            if isinstance(item, dict):
                label = item.get("name") or item.get("filename") or item.get("id")
                print(f"{item.get('id', '')}\t{label}")
            else:
                print(item)
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                print(f"{key}: {json.dumps(value, sort_keys=True)}")
            else:
                print(f"{key}: {value}")
        return
    print(payload)


def _load_ids(value: str) -> list[str]:
    path = Path(value).expanduser()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise ValueError("Selection ID file must contain a JSON string array.")
        return payload
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="selects",
        description="Local, LLM-assisted footage pre-editor.",
    )
    parser.add_argument("--data-dir", type=Path, help="Override the application-data directory.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="Check the local installation.")
    serve = commands.add_parser("serve", help="Open the reusable local pre-editor.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8741)
    serve.add_argument("--no-browser", action="store_true")

    project = commands.add_parser("project", help="Create and inspect projects.")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_commands.add_parser("list")
    create = project_commands.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--target-duration", "--target-duration-seconds", dest="target_duration", type=float, default=120)
    create.add_argument("--orientation", choices=("landscape", "portrait", "undecided"), default="landscape")
    create.add_argument("--intent", default="")
    create.add_argument("--ideal-clip-duration", type=float, default=8.0)
    create.add_argument("--shot-rhythm", choices=("energetic", "balanced", "observational", "custom"))
    create.add_argument("--shot-min-seconds", type=float, default=6.0)
    create.add_argument("--shot-max-seconds", type=float, default=9.0)
    create.add_argument("--candidate-breadth", choices=("focused", "generous", "broad"), default="generous")
    create.add_argument("--audio-preference", choices=("speech_and_distinctive", "visual", "all"), default="speech_and_distinctive")
    show = project_commands.add_parser("show")
    show.add_argument("project_id")
    manifest = project_commands.add_parser("manifest")
    manifest.add_argument("project_id")
    manifest.add_argument("--output", type=Path)
    context = project_commands.add_parser("context")
    context.add_argument("project_id")
    context.add_argument("--output", type=Path)
    update_project = project_commands.add_parser("update")
    update_project.add_argument("project_id")
    update_project.add_argument("--name")
    update_project.add_argument("--target-duration", type=float)
    update_project.add_argument("--clear-target-duration", action="store_true")
    update_project.add_argument("--orientation", choices=("landscape", "portrait", "undecided"))
    update_project.add_argument("--intent")
    update_project.add_argument("--ideal-clip-duration", type=float)
    update_project.add_argument("--shot-rhythm", choices=("energetic", "balanced", "observational", "custom"))
    update_project.add_argument("--shot-min-seconds", type=float)
    update_project.add_argument("--shot-max-seconds", type=float)
    update_project.add_argument("--candidate-breadth", choices=("focused", "generous", "broad"))
    update_project.add_argument("--audio-preference", choices=("speech_and_distinctive", "visual", "all"))
    backup = project_commands.add_parser("backup")
    backup.add_argument("--output", type=Path)

    source = commands.add_parser("source", help="Manage footage folders and sources.")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    add = source_commands.add_parser("add")
    add.add_argument("project_id")
    add.add_argument("path", type=Path)
    add.add_argument("--label", default="")
    add.add_argument("--top-level-only", action="store_true")
    scan = source_commands.add_parser("scan")
    scan.add_argument("project_id")
    source_list = source_commands.add_parser("list")
    source_list.add_argument("project_id")
    source_list.add_argument("--status", choices=("ready", "offline", "error", "unsupported"))
    relink = source_commands.add_parser("relink")
    relink.add_argument("source_id")
    relink.add_argument("path", type=Path)

    selection = commands.add_parser("selection", help="Create and edit exact source ranges.")
    selection_commands = selection.add_subparsers(dest="selection_command", required=True)
    selection_list = selection_commands.add_parser("list")
    selection_list.add_argument("project_id")
    selection_list.add_argument("--decision", choices=("keep", "maybe", "skip"))
    selection_show = selection_commands.add_parser("show")
    selection_show.add_argument("selection_id")
    selection_create = selection_commands.add_parser("create")
    selection_create.add_argument("project_id")
    selection_create.add_argument("source_id")
    selection_create.add_argument("--in", dest="in_seconds", type=float, required=True)
    selection_create.add_argument("--out", dest="out_seconds", type=float, required=True)
    selection_create.add_argument("--decision", choices=("keep", "maybe", "skip"), default="maybe")
    selection_create.add_argument("--comment", default="")
    selection_create.add_argument("--story-role", choices=("opening", "transition", "peak", "ending"))
    selection_create.add_argument(
        "--audio-intent",
        choices=("undecided", "mute", "preserve", "speech", "background"),
        default="undecided",
    )
    selection_update = selection_commands.add_parser("update")
    selection_update.add_argument("selection_id")
    selection_update.add_argument("--in", dest="in_seconds", type=float)
    selection_update.add_argument("--out", dest="out_seconds", type=float)
    selection_update.add_argument("--decision", choices=("keep", "maybe", "skip"))
    selection_update.add_argument("--comment")
    selection_update.add_argument("--story-role", choices=("opening", "transition", "peak", "ending", "none"))
    selection_update.add_argument(
        "--audio-intent", choices=("undecided", "mute", "preserve", "speech", "background")
    )
    marker = selection_commands.add_parser("marker")
    marker.add_argument("selection_id")
    marker.add_argument("--at", type=float, required=True)
    marker.add_argument("--comment", required=True)
    selection_archive = selection_commands.add_parser("archive")
    selection_archive.add_argument("selection_id")

    sequence = commands.add_parser("sequence", help="Create immutable ordered sequence versions.")
    sequence_commands = sequence.add_subparsers(dest="sequence_command", required=True)
    sequence_list = sequence_commands.add_parser("list")
    sequence_list.add_argument("project_id")
    sequence_create = sequence_commands.add_parser("create")
    sequence_create.add_argument("project_id")
    sequence_create.add_argument("--name", default="First cut")
    sequence_create.add_argument("--selection-ids", required=True, help="Comma-separated IDs or a JSON file.")
    sequence_create.add_argument("--target-duration", type=float)
    sequence_create.add_argument("--note", default="Initial sequence")
    sequence_revise = sequence_commands.add_parser("revise")
    sequence_revise.add_argument("sequence_id")
    sequence_revise.add_argument("--selection-ids", required=True, help="Comma-separated IDs or a JSON file.")
    sequence_revise.add_argument("--note", default="")
    sequence_show = sequence_commands.add_parser("show")
    sequence_show.add_argument("sequence_id")
    sequence_export = sequence_commands.add_parser("export")
    sequence_export.add_argument("sequence_id")
    sequence_export.add_argument("--output", type=Path, required=True)

    proposal = commands.add_parser("proposal", help="Record inspectable assistant proposals.")
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    proposal_list = proposal_commands.add_parser("list")
    proposal_list.add_argument("project_id")
    proposal_list.add_argument("--status", choices=("pending", "accepted", "rejected"))
    proposal_create = proposal_commands.add_parser("create")
    proposal_create.add_argument("project_id")
    proposal_create.add_argument("--provider", required=True)
    proposal_create.add_argument("--model", default="")
    proposal_create.add_argument("--kind", required=True)
    proposal_create.add_argument("--payload", type=Path, required=True)
    proposal_create.add_argument("--explanation", default="")
    proposal_show = proposal_commands.add_parser("show")
    proposal_show.add_argument("proposal_id")
    proposal_decide = proposal_commands.add_parser("decide")
    proposal_decide.add_argument("proposal_id")
    proposal_decide.add_argument("decision", choices=("accepted", "rejected"))
    proposal_apply = proposal_commands.add_parser("apply")
    proposal_apply.add_argument("proposal_id")

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    editor = PreEditor(_database(args.data_dir))
    try:
        if args.command == "serve":
            from .preeditor_server import serve as serve_app

            serve_app(host=args.host, port=args.port, data_dir=args.data_dir, open_browser=not args.no_browser)
            return 0
        if args.command == "doctor":
            try:
                ffmpeg, ffprobe = require_media_tools()
                tools: dict[str, Any] = {"ok": True, "ffmpeg": ffmpeg, "ffprobe": ffprobe}
            except MediaToolError as exc:
                tools = {"ok": False, "error": str(exc)}
            root = _database(args.data_dir).parent
            payload = {
                "ok": bool(tools["ok"]),
                "database": str(_database(args.data_dir)),
                "data_dir_writable": root.exists() and root.is_dir(),
                "free_bytes": shutil.disk_usage(root).free,
                "media_tools": tools,
            }
        elif args.command == "project":
            if args.project_command == "list":
                payload = editor.projects()
            elif args.project_command == "create":
                payload = editor.create_project(
                    ProjectOptions(
                        name=args.name, target_duration=args.target_duration, orientation=args.orientation,
                        intent=args.intent, ideal_clip_duration=args.ideal_clip_duration,
                        shot_rhythm=args.shot_rhythm or min(
                            (("energetic", 4.0), ("balanced", 7.5), ("observational", 13.0)),
                            key=lambda item: abs(item[1] - args.ideal_clip_duration),
                        )[0],
                        shot_min_seconds=(3.0 if args.shot_rhythm is None and args.ideal_clip_duration < 5.75 else 10.0 if args.shot_rhythm is None and args.ideal_clip_duration > 10.25 else args.shot_min_seconds),
                        shot_max_seconds=(5.0 if args.shot_rhythm is None and args.ideal_clip_duration < 5.75 else 16.0 if args.shot_rhythm is None and args.ideal_clip_duration > 10.25 else args.shot_max_seconds),
                        candidate_breadth=args.candidate_breadth,
                        audio_preference=args.audio_preference,
                    )
                )
            elif args.project_command == "show":
                payload = editor.project(args.project_id)
                if payload is None:
                    raise KeyError(args.project_id)
            elif args.project_command in {"manifest", "context"}:
                payload = (
                    editor.project_manifest(args.project_id)
                    if args.project_command == "manifest"
                    else editor.project_context(args.project_id)
                )
                if args.output:
                    args.output.expanduser().resolve().write_text(
                        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
                    )
                    payload = {"written": str(args.output.expanduser().resolve())}
            elif args.project_command == "update":
                values = {
                    "name": args.name, "orientation": args.orientation, "intent": args.intent,
                    "ideal_clip_duration": args.ideal_clip_duration,
                    "shot_rhythm": args.shot_rhythm, "shot_min_seconds": args.shot_min_seconds,
                    "shot_max_seconds": args.shot_max_seconds, "candidate_breadth": args.candidate_breadth,
                    "audio_preference": args.audio_preference,
                    "target_duration": None if args.clear_target_duration else args.target_duration,
                }
                changes = {key: value for key, value in values.items() if value is not None}
                if args.clear_target_duration:
                    changes["target_duration"] = None
                payload = editor.update_project(args.project_id, **changes)
            elif args.project_command == "backup":
                payload = {"backup": str(editor.backup_database(args.output))}
        elif args.command == "source":
            if args.source_command == "add":
                payload = editor.add_source_root(
                    args.project_id,
                    args.path,
                    label=args.label,
                    recursive=not args.top_level_only,
                )
            elif args.source_command == "scan":
                payload = editor.scan(args.project_id)
            elif args.source_command == "list":
                payload = editor.sources(args.project_id, status=args.status)
            elif args.source_command == "relink":
                payload = editor.relink_source(args.source_id, args.path)
        elif args.command == "selection":
            if args.selection_command == "list":
                payload = editor.selections(args.project_id, decision=args.decision)
            elif args.selection_command == "show":
                payload = editor.selection(args.selection_id)
                if payload is None:
                    raise KeyError(args.selection_id)
            elif args.selection_command == "create":
                payload = editor.create_selection(
                    args.project_id,
                    SelectionDraft(
                        source_id=args.source_id,
                        in_seconds=args.in_seconds,
                        out_seconds=args.out_seconds,
                        decision=args.decision,
                        comment=args.comment,
                        story_role=args.story_role,
                        audio_intent=args.audio_intent,
                        origin="cli",
                    ),
                )
            elif args.selection_command == "update":
                changes = {
                    key: value
                    for key, value in {
                        "in_seconds": args.in_seconds,
                        "out_seconds": args.out_seconds,
                        "decision": args.decision,
                        "comment": args.comment,
                        "story_role": None if args.story_role == "none" else args.story_role,
                        "audio_intent": args.audio_intent,
                    }.items()
                    if value is not None or (key == "story_role" and args.story_role == "none")
                }
                payload = editor.update_selection(args.selection_id, **changes)
            elif args.selection_command == "marker":
                payload = editor.add_marker(args.selection_id, args.at, args.comment)
            elif args.selection_command == "archive":
                payload = editor.archive_selection(args.selection_id)
        elif args.command == "sequence":
            if args.sequence_command == "list":
                payload = editor.sequences(args.project_id)
            elif args.sequence_command == "create":
                payload = editor.create_sequence(
                    args.project_id,
                    args.name,
                    _load_ids(args.selection_ids),
                    target_duration=args.target_duration,
                    note=args.note,
                )
            elif args.sequence_command == "revise":
                payload = editor.revise_sequence(
                    args.sequence_id, _load_ids(args.selection_ids), note=args.note
                )
            elif args.sequence_command == "show":
                payload = editor.latest_sequence_version(args.sequence_id)
            elif args.sequence_command == "export":
                from .sequence_export import write_handoff

                version = editor.latest_sequence_version(args.sequence_id)
                project = editor.project(version["project_id"])
                if not project:
                    raise KeyError(version["project_id"])
                for item in version.get("items") or []:
                    source = editor.assert_source_unchanged(
                        str(item["source_id"]), str(item.get("source_fingerprint") or "") or None
                    )
                    item["current_path"] = source["current_path"]
                    item["source_status"] = source["status"]
                payload = write_handoff(
                    version, args.output.expanduser().resolve(), project_name=project["name"],
                    orientation=version.get("orientation") or "landscape"
                )
        elif args.command == "proposal":
            if args.proposal_command == "list":
                payload = editor.proposals(args.project_id, status=args.status)
            elif args.proposal_command == "create":
                raw = json.loads(args.payload.expanduser().read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("Proposal payload must be a JSON object.")
                payload = editor.create_proposal(
                    args.project_id,
                    provider=args.provider,
                    model=args.model,
                    kind=args.kind,
                    payload=raw,
                    explanation=args.explanation,
                )
            elif args.proposal_command == "show":
                payload = editor.proposal(args.proposal_id)
                if payload is None:
                    raise KeyError(args.proposal_id)
            elif args.proposal_command == "decide":
                payload = editor.decide_proposal(args.proposal_id, args.decision)
            elif args.proposal_command == "apply":
                payload = editor.apply_proposal(args.proposal_id)
        else:
            parser.error("Unsupported command.")
            return 2
        _emit(payload, as_json=args.json)
        return 0
    except (KeyError, ValueError, FileNotFoundError, NotADirectoryError, MediaToolError) as exc:
        error = {"error": str(exc), "type": type(exc).__name__}
        if args.json:
            print(json.dumps(error, sort_keys=True), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
