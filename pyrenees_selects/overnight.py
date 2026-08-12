from __future__ import annotations

import errno
import json
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .analysis import ANALYSIS_VERSION, AnalyzedCandidate, analyze_video_candidates
from .candidate_planner import build_candidate_plan, estimate_artifacts
from .media import (
    MediaToolError,
    frame_signature,
    probe_video,
    render_candidate_sample,
    render_source_proxy,
    signature_hamming_distance,
)
from .preeditor import AUDIO_INTENTS, DECISIONS, STORY_ROLES, PreEditor, new_id, utc_now


RUN_TERMINAL = {"cancelled", "completed", "completed_with_warnings", "failed", "stale"}
RUN_ACTIVE = {"running", "pausing", "cancelling"}


class PowerProvider:
    def acquire(self) -> tuple[Any | None, str]:
        try:
            return subprocess.Popen(
                ["caffeinate", "-dimsu"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ), ""
        except (OSError, subprocess.SubprocessError):
            return None, "Sleep prevention is unavailable; keep this Mac connected and awake."

    def release(self, handle: Any | None) -> None:
        if handle is None:
            return
        if handle.poll() is None:
            handle.terminate()
            try:
                handle.wait(timeout=3)
            except subprocess.TimeoutExpired:
                handle.kill()
                handle.wait()


@dataclass
class ActiveRun:
    thread: threading.Thread
    cancel: threading.Event
    power_handle: Any | None = None


class AnalysisRunStore:
    def __init__(self, editor: PreEditor):
        self.editor = editor

    @staticmethod
    def brief(project: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "target_duration_seconds": project.get("target_duration_seconds"),
            "shot_rhythm": project.get("shot_rhythm") or "balanced",
            "shot_min_seconds": float(project.get("shot_min_seconds") or 6),
            "shot_max_seconds": float(project.get("shot_max_seconds") or 9),
            "candidate_breadth": project.get("candidate_breadth") or "generous",
            "orientation": project.get("orientation") or "landscape",
            "intent": project.get("intent") or "",
            "audio_preference": project.get("audio_preference") or "speech_and_distinctive",
        }

    def create_plan(self, project_id: str, cache_path: Path, *, prevent_sleep: bool) -> dict[str, Any]:
        project = self.editor.project(project_id)
        if not project:
            raise KeyError(project_id)
        brief = self.brief(project)
        sources = self.editor.sources(project_id)
        plan = build_candidate_plan(brief, sources)
        if not plan.sources:
            raise ValueError("No readable video files were found. Choose another folder or fix the files marked unreadable.")
        cache = cache_path.expanduser().resolve()
        cache.mkdir(parents=True, exist_ok=True)
        disk = estimate_artifacts(plan)
        available = shutil.disk_usage(cache).free
        disk.update({
            "available_bytes": available,
            "shortfall_bytes": max(0, disk["required_free_bytes"] - available),
            "can_start": available >= disk["required_free_bytes"],
        })
        plan_payload = plan.as_dict()
        ready_sources = [source for source in sources if source.get("status") == "ready"]
        plan_payload["inventory"] = {
            "ready": len(ready_sources),
            "unique_readable": len(plan.sources),
            "duplicates": len(plan.duplicate_source_ids),
            "portrait": sum(
                1 for source in ready_sources
                if ((int(source.get("height") or 0) > int(source.get("width") or 0))
                    != (int(source.get("rotation") or 0) in {90, 270}))
            ),
            "silent": sum(1 for source in ready_sources if not bool(source.get("has_audio"))),
            "vfr": sum(1 for source in ready_sources if bool(source.get("is_vfr"))),
            "very_short": sum(1 for source in ready_sources if float(source.get("duration") or 0) < plan.shot_min_seconds),
            "broken": sum(1 for source in sources if source.get("status") == "error"),
            "offline": sum(1 for source in sources if source.get("status") == "offline"),
            "unsupported": self.editor.unsupported_file_count(project_id),
        }
        plan_payload["disk"] = disk
        plan_payload["runtime"] = {"seconds": None, "provenance": "estimating"}
        source_lookup = {str(source["id"]): source for source in sources}
        snapshot = [
            {
                "source_id": item.source_id,
                "fingerprint": item.fingerprint,
                "duration": item.duration_seconds,
                "relative_path": item.relative_path,
                "captured_at": item.captured_at,
                "width": source_lookup[item.source_id].get("width"),
                "height": source_lookup[item.source_id].get("height"),
                "fps": source_lookup[item.source_id].get("fps"),
                "codec": source_lookup[item.source_id].get("codec"),
                "has_audio": bool(source_lookup[item.source_id].get("has_audio")),
                "rotation": source_lookup[item.source_id].get("rotation") or 0,
                "is_vfr": bool(source_lookup[item.source_id].get("is_vfr")),
                "budget_seconds": item.budget_seconds,
                "maximum_windows": item.maximum_windows,
            }
            for item in plan.sources
        ]
        active_snapshot = [item for item in snapshot if int(item["maximum_windows"]) > 0]
        task_total = sum(2 + int(item["maximum_windows"]) for item in active_snapshot)
        now = utc_now()
        run_id = new_id("run")
        with self.editor.connection() as connection:
            connection.execute(
                """INSERT INTO preeditor_analysis_runs(
                       id,project_id,algorithm_version,state,brief_json,plan_json,source_snapshot_json,
                       cache_path,prevent_sleep,progress_total,created_at,updated_at
                   ) VALUES(?,?,?,'planned',?,?,?,?,?,?,?,?)""",
                (
                    run_id, project_id, ANALYSIS_VERSION, json.dumps(brief, sort_keys=True),
                    json.dumps(plan_payload, sort_keys=True), json.dumps(snapshot, sort_keys=True),
                    str(cache), int(prevent_sleep), task_total, now, now,
                ),
            )
            connection.executemany(
                """INSERT INTO preeditor_analysis_run_sources(
                       run_id,source_id,position,fingerprint,state,updated_at
                   ) VALUES(?,?,?,?,'pending',?)""",
                [(run_id, item["source_id"], position, item["fingerprint"], now) for position, item in enumerate(active_snapshot, 1)],
            )
        return self.run(run_id)

    def recover_orphans(self) -> None:
        now = utc_now()
        with self.editor.connection() as connection:
            connection.execute(
                """UPDATE preeditor_analysis_runs SET state='paused',warning=?,updated_at=?
                   WHERE state IN ('running','pausing','cancelling')""",
                ("The app closed during preparation. Completed work was kept; resume when ready.", now),
            )
            connection.execute(
                """UPDATE preeditor_analysis_run_sources SET state='pending',stage='checkpoint',updated_at=?
                   WHERE state IN ('proxying','analyzing','rendering')""",
                (now,),
            )

    def _row_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["brief"] = json.loads(str(payload.pop("brief_json")))
        payload["plan"] = json.loads(str(payload.pop("plan_json")))
        payload["source_snapshot"] = json.loads(str(payload.pop("source_snapshot_json")))
        payload["prevent_sleep"] = bool(payload["prevent_sleep"])
        return payload

    def run(self, run_id: str) -> dict[str, Any]:
        with self.editor.connection() as connection:
            row = connection.execute("SELECT * FROM preeditor_analysis_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            source_rows = connection.execute(
                """SELECT rs.*,s.filename,s.relative_path,s.duration,s.width,s.height,s.fps,s.has_audio,s.rotation,s.is_vfr
                   FROM preeditor_analysis_run_sources rs JOIN preeditor_sources s ON s.id=rs.source_id
                   WHERE rs.run_id=? ORDER BY rs.position""",
                (run_id,),
            ).fetchall()
        payload = self._row_payload(row)
        if payload["state"] in RUN_ACTIVE and payload.get("started_at"):
            try:
                from datetime import datetime, timezone
                active_elapsed = max(
                    0.0,
                    (datetime.now(timezone.utc) - datetime.fromisoformat(str(payload["started_at"]))).total_seconds(),
                )
                payload["elapsed_seconds"] = float(payload["elapsed_seconds"] or 0) + active_elapsed
            except (TypeError, ValueError):
                pass
        payload["sources"] = [dict(item) for item in source_rows]
        payload["candidates"] = self.candidates(run_id)
        payload["progress_fraction"] = (
            min(1.0, payload["progress_processed"] / payload["progress_total"])
            if payload["progress_total"] else 0.0
        )
        payload["stale"] = self.is_stale(payload)
        return payload

    def latest(self, project_id: str) -> dict[str, Any] | None:
        with self.editor.connection() as connection:
            row = connection.execute(
                "SELECT id FROM preeditor_analysis_runs WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self.run(str(row["id"])) if row else None

    def is_stale(self, run: Mapping[str, Any]) -> bool:
        project = self.editor.project(str(run["project_id"]))
        if not project or self.brief(project) != run["brief"]:
            return True
        current = {str(source["id"]): str(source.get("fingerprint") or "") for source in self.editor.sources(str(run["project_id"]))}
        return any(current.get(item["source_id"]) != item["fingerprint"] for item in run["source_snapshot"])

    def set_run(self, run_id: str, state: str, *, warning: str | None = None, error: str | None = None, ended: bool = False) -> None:
        now = utc_now()
        assignments = ["state=?", "updated_at=?"]
        values: list[Any] = [state, now]
        if warning is not None:
            assignments.append("warning=?")
            values.append(warning[:2_000])
        if error is not None:
            assignments.append("error=?")
            values.append(error[:2_000])
        if state == "running":
            assignments.append("started_at=?")
            values.append(now)
        if ended:
            assignments.append("ended_at=?")
            values.append(now)
        values.append(run_id)
        with self.editor.connection() as connection:
            connection.execute(f"UPDATE preeditor_analysis_runs SET {','.join(assignments)} WHERE id=?", values)

    def set_source(self, run_id: str, source_id: str, state: str, stage: str, *, error: str = "", task_target: int | None = None, completed: bool = False) -> None:
        now = utc_now()
        with self.editor.connection() as connection:
            current = connection.execute(
                "SELECT processed_tasks FROM preeditor_analysis_run_sources WHERE run_id=? AND source_id=?",
                (run_id, source_id),
            ).fetchone()
            old_tasks = int(current["processed_tasks"]) if current else 0
            new_tasks = max(old_tasks, int(task_target)) if task_target is not None else old_tasks
            task_delta = new_tasks - old_tasks
            connection.execute(
                """UPDATE preeditor_analysis_run_sources
                   SET state=?,stage=?,error=?,attempt_count=attempt_count+CASE WHEN ?='proxying' THEN 1 ELSE 0 END,
                       processed_tasks=?,started_at=COALESCE(started_at,?),updated_at=?,
                       completed_at=CASE WHEN ? THEN ? ELSE completed_at END
                   WHERE run_id=? AND source_id=?""",
                (state, stage, error[:1_000], state, new_tasks, now, now, int(completed), now, run_id, source_id),
            )
            if task_delta:
                connection.execute(
                    """UPDATE preeditor_analysis_runs
                       SET progress_processed=MIN(progress_total,progress_processed+?),updated_at=? WHERE id=?""",
                    (task_delta, now, run_id),
                )

    def reduce_tasks(self, run_id: str, count: int) -> None:
        if count <= 0:
            return
        with self.editor.connection() as connection:
            connection.execute(
                """UPDATE preeditor_analysis_runs
                   SET progress_total=MAX(progress_processed,progress_total-?),updated_at=? WHERE id=?""",
                (count, utc_now(), run_id),
            )

    def add_candidate(self, run: Mapping[str, Any], source: Mapping[str, Any], candidate: AnalyzedCandidate) -> str:
        candidate_id = new_id("candidate")
        now = utc_now()
        with self.editor.connection() as connection:
            connection.execute(
                """INSERT INTO preeditor_generated_candidates(
                       id,run_id,project_id,source_id,source_fingerprint,in_us,out_us,score,
                       score_components_json,rationale,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id,source_id,in_us,out_us) DO UPDATE SET
                       score=excluded.score,score_components_json=excluded.score_components_json,
                       rationale=excluded.rationale,updated_at=excluded.updated_at""",
                (
                    candidate_id, run["id"], run["project_id"], source["id"], source["fingerprint"],
                    candidate.in_us, candidate.out_us, candidate.score,
                    json.dumps(candidate.components, sort_keys=True), candidate.rationale, now, now,
                ),
            )
            row = connection.execute(
                """SELECT id FROM preeditor_generated_candidates
                   WHERE run_id=? AND source_id=? AND in_us=? AND out_us=?""",
                (run["id"], source["id"], candidate.in_us, candidate.out_us),
            ).fetchone()
        return str(row["id"])

    def publish_candidate(self, candidate_id: str, path: Path, artifact: Mapping[str, Any]) -> None:
        with self.editor.connection() as connection:
            connection.execute(
                """UPDATE preeditor_generated_candidates SET sample_path=?,artifact_json=?,updated_at=? WHERE id=?""",
                (str(path.resolve()), json.dumps(dict(artifact), sort_keys=True), utc_now(), candidate_id),
            )

    def rank_candidates(self, run_id: str) -> None:
        with self.editor.connection() as connection:
            rows = connection.execute(
                """SELECT c.id FROM preeditor_generated_candidates c
                   JOIN preeditor_sources s ON s.id=c.source_id
                   WHERE c.run_id=? AND c.sample_path IS NOT NULL
                   ORDER BY c.score DESC,COALESCE(s.captured_at,''),s.relative_path,c.in_us""",
                (run_id,),
            ).fetchall()
            connection.executemany(
                "UPDATE preeditor_generated_candidates SET rank=? WHERE id=?",
                [(rank, row["id"]) for rank, row in enumerate(rows, 1)],
            )

    def candidates(self, run_id: str) -> list[dict[str, Any]]:
        with self.editor.connection() as connection:
            rows = connection.execute(
                """SELECT c.*,s.filename,s.relative_path,s.duration source_duration,s.width,s.height,
                          s.fps,s.has_audio,s.rotation,s.is_vfr
                   FROM preeditor_generated_candidates c JOIN preeditor_sources s ON s.id=c.source_id
                   WHERE c.run_id=? ORDER BY COALESCE(c.rank,999999),c.score DESC,s.relative_path,c.in_us""",
                (run_id,),
            ).fetchall()
        payloads = []
        for row in rows:
            item = dict(row)
            item["score_components"] = json.loads(str(item.pop("score_components_json")))
            item["artifact"] = json.loads(str(item.pop("artifact_json")))
            item["generated_in_us"] = item["in_us"]
            item["generated_out_us"] = item["out_us"]
            effective_in = item["selected_in_us"] if item["selected_in_us"] is not None else item["in_us"]
            effective_out = item["selected_out_us"] if item["selected_out_us"] is not None else item["out_us"]
            item["in_us"] = effective_in
            item["out_us"] = effective_out
            item["in_seconds"] = effective_in / 1_000_000
            item["out_seconds"] = effective_out / 1_000_000
            item["duration"] = (effective_out - effective_in) / 1_000_000
            item["sample_ready"] = bool(item.get("sample_path"))
            item.pop("sample_path", None)
            payloads.append(item)
        return payloads

    def candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self.editor.connection() as connection:
            row = connection.execute(
                """SELECT c.*,s.current_path,s.filename,s.duration source_duration,s.fps,s.is_vfr,s.fingerprint current_fingerprint
                   FROM preeditor_generated_candidates c JOIN preeditor_sources s ON s.id=c.source_id
                   WHERE c.id=?""",
                (candidate_id,),
            ).fetchone()
        return dict(row) if row else None

    def review_candidate(self, candidate_id: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        candidate = self.candidate(candidate_id)
        if not candidate:
            raise KeyError(candidate_id)
        decision = str(changes.get("decision") or candidate["review_state"])
        mapped_state = {"keep": "kept", "maybe": "maybe", "skip": "skipped", "kept": "kept", "skipped": "skipped"}.get(decision)
        if not mapped_state:
            raise ValueError("Decision must be keep, maybe, or skip.")
        current_in = candidate["selected_in_us"] if candidate.get("selected_in_us") is not None else candidate["in_us"]
        current_out = candidate["selected_out_us"] if candidate.get("selected_out_us") is not None else candidate["out_us"]
        in_us, out_us = self.editor.canonical_range(
            candidate, int(changes.get("in_us", current_in)), int(changes.get("out_us", current_out))
        )
        comment = str(changes.get("comment", candidate["comment"])).strip()[:8_000]
        story_role = changes.get("story_role", candidate["story_role"])
        audio_intent = str(changes.get("audio_intent", candidate["audio_intent"]))
        if story_role not in STORY_ROLES | {None, ""}:
            raise ValueError("Invalid story role.")
        if audio_intent not in AUDIO_INTENTS:
            raise ValueError("Invalid audio intent.")
        now = utc_now()
        selection_id = candidate.get("linked_selection_id")
        affected_selection_id = str(selection_id) if selection_id else None
        with self.editor.connection() as connection:
            if mapped_state == "skipped":
                if selection_id:
                    connection.execute(
                        """UPDATE preeditor_selections SET decision='skip',archived_at=?,updated_at=? WHERE id=?""",
                        (now, now, selection_id),
                    )
                    self.editor._record_selection_revision(connection, str(selection_id), now)
                selection_id = None
            elif selection_id:
                connection.execute(
                    """UPDATE preeditor_selections SET in_seconds=?,out_seconds=?,in_us=?,out_us=?,decision=?,comment=?,story_role=?,audio_intent=?,updated_at=?
                       WHERE id=?""",
                    (in_us / 1_000_000, out_us / 1_000_000, in_us, out_us, "keep" if mapped_state == "kept" else "maybe", comment, story_role or None, audio_intent, now, selection_id),
                )
                self.editor._record_selection_revision(connection, str(selection_id), now)
            else:
                selection_id = new_id("selection")
                connection.execute(
                    """INSERT INTO preeditor_selections(
                           id,project_id,source_id,in_seconds,out_seconds,in_us,out_us,decision,comment,story_role,audio_intent,origin,created_at,updated_at
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'generated-candidate',?,?)""",
                    (
                        selection_id, candidate["project_id"], candidate["source_id"], in_us / 1_000_000,
                        out_us / 1_000_000, in_us, out_us, "keep" if mapped_state == "kept" else "maybe", comment,
                        story_role or None, audio_intent, now, now,
                    ),
                )
                self.editor._record_selection_revision(connection, str(selection_id), now)
            connection.execute(
                """UPDATE preeditor_generated_candidates SET review_state=?,linked_selection_id=?,selected_in_us=?,selected_out_us=?,
                       comment=?,story_role=?,audio_intent=?,updated_at=? WHERE id=?""",
                (mapped_state, selection_id, in_us, out_us, comment, story_role or None, audio_intent, now, candidate_id),
            )
        if affected_selection_id:
            self.editor._revise_sequences_containing_selection(
                affected_selection_id, remove=mapped_state == "skipped"
            )
        return next(item for item in self.candidates(str(candidate["run_id"])) if item["id"] == candidate_id)


class OvernightRunManager:
    def __init__(
        self,
        editor: PreEditor,
        cache: Path,
        *,
        analyzer: Callable[..., list[AnalyzedCandidate]] = analyze_video_candidates,
        proxy_renderer: Callable[..., Path] = render_source_proxy,
        sample_renderer: Callable[..., tuple[Path, dict[str, Any]]] = render_candidate_sample,
        power_provider: PowerProvider | None = None,
    ):
        self.editor = editor
        self.default_cache = cache.expanduser().resolve() / "preeditor" / "overnight"
        self.store = AnalysisRunStore(editor)
        self.analyzer = analyzer
        self.proxy_renderer = proxy_renderer
        self.sample_renderer = sample_renderer
        self.power = power_provider or PowerProvider()
        self._lock = threading.Lock()
        self._active: dict[str, ActiveRun] = {}
        self._released_power_handles: set[int] = set()
        self.store.recover_orphans()
        self._validate_recovered_artifacts()

    def _release_power(self, handle: Any | None) -> None:
        """Release sleep prevention once, even if shutdown races worker cleanup."""
        if handle is None:
            return
        identity = id(handle)
        with self._lock:
            if identity in self._released_power_handles:
                return
            self._released_power_handles.add(identity)
        self.power.release(handle)

    @staticmethod
    def _proxy_path_for(run: Mapping[str, Any], source: Mapping[str, Any]) -> Path:
        return (
            Path(str(run["cache_path"])) / "review-proxies" / str(run["id"])
            / f"{source['source_id']}-{str(source['fingerprint'])[:12]}.mp4"
        )

    @staticmethod
    def _looks_like_disk_full(exc: BaseException) -> bool:
        current: BaseException | None = exc
        messages: list[str] = []
        while current is not None:
            messages.append(str(current))
            stderr = getattr(current, "stderr", "") or ""
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            messages.append(str(stderr))
            if isinstance(current, OSError) and current.errno == errno.ENOSPC:
                return True
            current = current.__cause__
        message = "\n".join(messages).lower()
        return any(marker in message for marker in ("no space left on device", "disk full", "enospc"))

    @staticmethod
    def _validated_proxy(path: Path, source: Mapping[str, Any]) -> bool:
        try:
            metadata = probe_video(path)
            fps = float(source.get("fps") or 0)
            tolerance = max(0.05, 1 / fps if fps > 0 else 0.05)
            return (
                abs(metadata.duration - float(source.get("duration") or 0)) <= tolerance
                and (not bool(source.get("has_audio")) or metadata.has_audio)
            )
        except (MediaToolError, OSError, ValueError):
            return False

    @staticmethod
    def _validated_sample(path: Path, candidate: Mapping[str, Any]) -> bool:
        try:
            candidate = dict(candidate)
            metadata = probe_video(path)
            expected = (int(candidate["out_us"]) - int(candidate["in_us"])) / 1_000_000
            fps = float(candidate.get("fps") or 0)
            tolerance = 0.05 if bool(candidate.get("is_vfr")) or fps <= 0 else 1 / fps
            artifact = candidate.get("artifact")
            if artifact is None:
                artifact = json.loads(str(candidate.get("artifact_json") or "{}"))
            recorded = str(artifact.get("first_frame_signature") or "")
            source_recorded = str(artifact.get("source_frame_signature") or "")
            if not recorded or not source_recorded:
                return False
            sample_signature = frame_signature(path, in_us=0)
            current_source_signature = frame_signature(
                Path(str(candidate["current_path"])), in_us=int(candidate["in_us"])
            )
            return (
                abs(metadata.duration - expected) <= tolerance
                and signature_hamming_distance(recorded, sample_signature) <= 0.05
                and signature_hamming_distance(source_recorded, current_source_signature) <= 0.05
                and signature_hamming_distance(current_source_signature, sample_signature) <= 0.22
            )
        except (MediaToolError, OSError, ValueError, KeyError):
            return False

    def _validate_recovered_artifacts(self) -> None:
        """Never trust a completed artifact merely because its row survived."""
        with self.editor.connection() as connection:
            runs = connection.execute(
                """SELECT * FROM preeditor_analysis_runs
                   WHERE state IN ('paused','completed','completed_with_warnings')"""
            ).fetchall()
        for run_row in runs:
            run = self.store._row_payload(run_row)
            snapshot = {item["source_id"]: item for item in run["source_snapshot"]}
            invalid_sources: set[str] = set()
            with self.editor.connection() as connection:
                completed = connection.execute(
                    """SELECT source_id FROM preeditor_analysis_run_sources
                       WHERE run_id=? AND state='completed'""", (run["id"],)
                ).fetchall()
                candidates = connection.execute(
                    """SELECT c.*,s.fps,s.is_vfr,s.current_path FROM preeditor_generated_candidates c
                       JOIN preeditor_sources s ON s.id=c.source_id
                       WHERE c.run_id=? AND c.sample_path IS NOT NULL""", (run["id"],)
                ).fetchall()
            for row in completed:
                source_id = str(row["source_id"])
                facts = snapshot.get(source_id)
                if not facts or not self._validated_proxy(self._proxy_path_for(run, facts), facts):
                    invalid_sources.add(source_id)
            for row in candidates:
                path = Path(str(row["sample_path"]))
                if not self._validated_sample(path, row):
                    path.unlink(missing_ok=True)
                    invalid_sources.add(str(row["source_id"]))
                    with self.editor.connection() as connection:
                        connection.execute(
                            """UPDATE preeditor_generated_candidates
                               SET sample_path=NULL,artifact_json='{}',updated_at=? WHERE id=?""",
                            (utc_now(), row["id"]),
                        )
            if invalid_sources:
                with self.editor.connection() as connection:
                    placeholders = ",".join("?" for _ in invalid_sources)
                    connection.execute(
                        f"""UPDATE preeditor_analysis_run_sources
                            SET state='pending',stage='artifact-check',processed_tasks=0,
                                error='A completed cache artifact failed validation and will be rebuilt.',updated_at=?
                            WHERE run_id=? AND source_id IN ({placeholders})""",
                        (utc_now(), run["id"], *invalid_sources),
                    )
                    connection.execute(
                        """UPDATE preeditor_analysis_runs
                           SET state='paused',progress_processed=(SELECT COALESCE(SUM(processed_tasks),0)
                               FROM preeditor_analysis_run_sources WHERE run_id=?),warning=?,updated_at=?
                           WHERE id=?""",
                        (run["id"], "Cached work failed validation. Resume to rebuild only the affected sources.", utc_now(), run["id"]),
                    )
            root = Path(str(run["cache_path"]))
            if root.is_dir():
                for partial in root.rglob("*.partial.mp4"):
                    partial.unlink(missing_ok=True)

    def plan(self, project_id: str, *, cache_path: Path | None = None, prevent_sleep: bool = True) -> dict[str, Any]:
        return self.store.create_plan(project_id, cache_path or self.default_cache, prevent_sleep=prevent_sleep)

    def start(self, run_id: str) -> dict[str, Any]:
        run = self.store.run(run_id)
        if run["stale"]:
            self.store.set_run(run_id, "stale", warning="Footage or project settings changed. Create a fresh plan.")
            raise ValueError("This plan is stale. Review the updated plan before starting.")
        available = shutil.disk_usage(Path(str(run["cache_path"]))).free
        disk = dict(run["plan"]["disk"])
        disk.update({
            "available_bytes": available,
            "shortfall_bytes": max(0, int(disk["required_free_bytes"]) - available),
            "can_start": available >= int(disk["required_free_bytes"]),
        })
        plan = dict(run["plan"]); plan["disk"] = disk
        with self.editor.connection() as connection:
            connection.execute(
                "UPDATE preeditor_analysis_runs SET plan_json=?,updated_at=? WHERE id=?",
                (json.dumps(plan, sort_keys=True), utc_now(), run_id),
            )
        if not disk["can_start"]:
            raise ValueError("There is not enough free space at the selected cache location.")
        if run["state"] not in {"planned", "paused"}:
            raise ValueError(f"A {run['state']} run cannot be started.")
        with self._lock:
            active = self._active.get(run_id)
            if active and active.thread.is_alive():
                return self.store.run(run_id)
            cancel = threading.Event()
            thread = threading.Thread(target=self._run, args=(run_id, cancel), daemon=True, name=f"overnight-{run_id}")
            self._active[run_id] = ActiveRun(thread, cancel)
            self.store.set_run(run_id, "running", warning="", error="")
            thread.start()
        return self.store.run(run_id)

    def pause(self, run_id: str) -> dict[str, Any]:
        run = self.store.run(run_id)
        if run["state"] != "running":
            raise ValueError("Only a running preparation can be paused.")
        self.store.set_run(run_id, "pausing")
        with self._lock:
            active = self._active.get(run_id)
            if active:
                active.cancel.set()
        return self.store.run(run_id)

    def cancel(self, run_id: str) -> dict[str, Any]:
        run = self.store.run(run_id)
        if run["state"] in RUN_TERMINAL:
            return run
        self.store.set_run(run_id, "cancelling")
        with self._lock:
            active = self._active.get(run_id)
            if active:
                active.cancel.set()
            else:
                with self.editor.connection() as connection:
                    connection.execute(
                        """UPDATE preeditor_analysis_run_sources
                           SET state='cancelled',stage='cancelled',updated_at=?
                           WHERE run_id=? AND state IN ('pending','proxying','analyzing','rendering')""",
                        (utc_now(), run_id),
                    )
                self.store.set_run(run_id, "cancelled", ended=True)
        return self.store.run(run_id)

    def retry(self, run_id: str, source_ids: list[str]) -> dict[str, Any]:
        run = self.store.run(run_id)
        allowed = {str(source["source_id"]) for source in run["sources"] if source["state"] in {"failed", "skipped"}}
        chosen = set(source_ids) & allowed
        if not chosen:
            raise ValueError("Choose at least one failed or skipped source to retry.")
        with self.editor.connection() as connection:
            placeholders = ",".join("?" for _ in chosen)
            credited = connection.execute(
                f"""SELECT COALESCE(SUM(processed_tasks),0) total
                    FROM preeditor_analysis_run_sources
                    WHERE run_id=? AND source_id IN ({placeholders})""",
                (run_id, *chosen),
            ).fetchone()["total"]
            connection.execute(
                f"""UPDATE preeditor_analysis_run_sources
                    SET state='pending',stage='pending',error='',processed_tasks=0,updated_at=?
                    WHERE run_id=? AND source_id IN ({placeholders})""",
                (utc_now(), run_id, *chosen),
            )
            connection.execute(
                """UPDATE preeditor_analysis_runs
                   SET progress_processed=MAX(0,progress_processed-?),updated_at=? WHERE id=?""",
                (int(credited), utc_now(), run_id),
            )
        self.store.set_run(run_id, "paused", warning="")
        return self.start(run_id)

    def skip(self, run_id: str, source_ids: list[str]) -> dict[str, Any]:
        with self.editor.connection() as connection:
            for source_id in source_ids:
                connection.execute(
                    """UPDATE preeditor_analysis_run_sources SET state='skipped',stage='skipped',error='',updated_at=?
                       WHERE run_id=? AND source_id=? AND state IN ('failed','pending')""",
                    (utc_now(), run_id, source_id),
                )
        return self.store.run(run_id)

    def relocate_cache(self, run_id: str, destination: Path) -> dict[str, Any]:
        run = self.store.run(run_id)
        if run["state"] not in {"planned", "paused"}:
            raise ValueError("Pause preparation before changing its cache location.")
        target = destination.expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        disk = dict(run["plan"]["disk"])
        available = shutil.disk_usage(target).free
        disk.update({
            "available_bytes": available,
            "shortfall_bytes": max(0, int(disk["required_free_bytes"]) - available),
            "can_start": available >= int(disk["required_free_bytes"]),
        })
        if not disk["can_start"]:
            raise ValueError("The new cache location still does not have the displayed required free space.")
        old_root = Path(str(run["cache_path"])).resolve()
        with self.editor.connection() as connection:
            candidates = connection.execute(
                "SELECT id,sample_path FROM preeditor_generated_candidates WHERE run_id=? AND sample_path IS NOT NULL",
                (run_id,),
            ).fetchall()
        moved_candidates: list[tuple[str, str]] = []
        try:
            for candidate in candidates:
                old = Path(str(candidate["sample_path"])).resolve()
                if not old.is_file() or not old.is_relative_to(old_root):
                    continue
                new = target / "samples" / run_id / f"{candidate['id']}.mp4"
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, new)
                probe_video(new)
                moved_candidates.append((str(new.resolve()), str(candidate["id"])))
            for source in run["source_snapshot"]:
                old = self._proxy_path_for(run, source)
                if not old.is_file():
                    continue
                new = target / "review-proxies" / run_id / old.name
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, new)
                probe_video(new)
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                raise ValueError("The new cache filled while copying completed work. Choose a larger location.") from exc
            raise
        plan = dict(run["plan"]); plan["disk"] = disk
        with self.editor.connection() as connection:
            connection.executemany(
                "UPDATE preeditor_generated_candidates SET sample_path=?,updated_at=? WHERE id=?",
                [(path, utc_now(), candidate_id) for path, candidate_id in moved_candidates],
            )
            connection.execute(
                """UPDATE preeditor_analysis_runs SET cache_path=?,plan_json=?,warning='',updated_at=? WHERE id=?""",
                (str(target), json.dumps(plan, sort_keys=True), utc_now(), run_id),
            )
        return self.store.run(run_id)

    def _run(self, run_id: str, cancel: threading.Event) -> None:
        run = self.store.run(run_id)
        started = time.monotonic()
        base_elapsed = float(run.get("elapsed_seconds") or 0)
        power_handle = None
        try:
            if run["prevent_sleep"]:
                power_handle, warning = self.power.acquire()
                if warning:
                    self.store.set_run(run_id, "running", warning=warning)
                with self._lock:
                    if run_id in self._active:
                        self._active[run_id].power_handle = power_handle
            snapshot = {item["source_id"]: item for item in run["source_snapshot"]}
            for row in run["sources"]:
                if row["state"] in {"completed", "skipped"}:
                    continue
                if cancel.is_set():
                    raise InterruptedError("Preparation stopped at a safe checkpoint.")
                source_id = str(row["source_id"])
                facts = snapshot[source_id]
                source = self.editor.source(source_id)
                if not source or source["status"] != "ready" or source["fingerprint"] != facts["fingerprint"]:
                    self.store.set_source(
                        run_id, source_id, "failed", "source-check",
                        error="Source changed or is unavailable.", task_target=2 + int(facts["maximum_windows"]),
                    )
                    continue
                try:
                    source = self.editor.assert_source_unchanged(source_id, str(facts["fingerprint"]))
                except (ValueError, OSError) as exc:
                    self.store.set_source(
                        run_id, source_id, "failed", "source-check", error=str(exc),
                        task_target=2 + int(facts["maximum_windows"]),
                    )
                    continue
                cache = Path(str(run["cache_path"]))
                proxy = self._proxy_path_for(run, facts)
                try:
                    self.store.set_source(run_id, source_id, "proxying", "proxying")
                    self.proxy_renderer(Path(str(source["current_path"])), proxy, cancel=cancel)
                    if not self._validated_proxy(proxy, source):
                        proxy.unlink(missing_ok=True)
                        raise MediaToolError("The review copy did not preserve source duration or audio.")
                    self.store.set_source(run_id, source_id, "analyzing", "analyzing", task_target=1)
                    candidates = self.analyzer(
                        Path(str(source["current_path"])), float(source["duration"]),
                        budget_seconds=float(facts["budget_seconds"]),
                        shot_min_seconds=float(run["plan"]["shot_min_seconds"]),
                        shot_max_seconds=float(run["plan"]["shot_max_seconds"]),
                        audio_preference=str(run["brief"]["audio_preference"]),
                        has_audio=bool(source.get("has_audio")), cancel=cancel,
                    )[: int(facts["maximum_windows"])]
                    self.store.set_source(run_id, source_id, "rendering", "rendering", task_target=2)
                    for candidate_index, candidate in enumerate(candidates, 1):
                        if cancel.is_set():
                            raise InterruptedError("Preparation stopped at a safe checkpoint.")
                        # A source may have changed while its proxy/analysis was running.
                        source = self.editor.assert_source_unchanged(source_id, str(facts["fingerprint"]))
                        candidate_in, candidate_out = self.editor.canonical_range(
                            source, candidate.in_us, candidate.out_us
                        )
                        candidate = AnalyzedCandidate(
                            candidate_in, candidate_out, candidate.score,
                            candidate.components, candidate.rationale,
                        )
                        candidate_id = self.store.add_candidate(run, source, candidate)
                        destination = cache / "samples" / run_id / f"{candidate_id}.mp4"
                        path, artifact = self.sample_renderer(
                            Path(str(source["current_path"])), destination,
                            in_us=candidate.in_us, out_us=candidate.out_us,
                            source_fps=float(source.get("fps") or 0), has_audio=bool(source.get("has_audio")),
                            is_vfr=bool(source.get("is_vfr")),
                            cancel=cancel,
                        )
                        artifact.update({
                            "source_id": source_id,
                            "source_fingerprint": source["fingerprint"],
                            "analysis_version": ANALYSIS_VERSION,
                        })
                        self.store.publish_candidate(candidate_id, path, artifact)
                        self.store.set_source(run_id, source_id, "rendering", "rendering", task_target=2 + candidate_index)
                    self.store.set_source(run_id, source_id, "completed", "completed", completed=True)
                    self.store.rank_candidates(run_id)
                    self._update_eta(run_id, started, base_elapsed)
                except InterruptedError:
                    self.store.set_source(run_id, source_id, "pending", "checkpoint")
                    raise
                except Exception as exc:
                    if self._looks_like_disk_full(exc):
                        self.store.set_source(run_id, source_id, "pending", "disk", error="The selected cache ran out of space.")
                        # Publish paused/terminal states only after this run no
                        # longer owns the Mac sleep-prevention handle.
                        self._release_power(power_handle)
                        power_handle = None
                        self.store.set_run(run_id, "paused", warning="The selected cache ran out of space. Choose another cache location and resume.")
                        return
                    self.store.set_source(
                        run_id, source_id, "failed", "failed", error=str(exc),
                        task_target=2 + int(facts["maximum_windows"]),
                    )
            final = self.store.run(run_id)
            failures = [source for source in final["sources"] if source["state"] in {"failed", "skipped"}]
            completed = [source for source in final["sources"] if source["state"] == "completed"]
            state = "completed_with_warnings" if failures else "completed"
            if not completed and failures:
                state = "failed"
            with self.editor.connection() as connection:
                connection.execute(
                    """UPDATE preeditor_analysis_runs
                       SET progress_total=progress_processed,updated_at=? WHERE id=?""",
                    (utc_now(), run_id),
                )
            self._release_power(power_handle)
            power_handle = None
            self.store.set_run(run_id, state, ended=True)
        except InterruptedError:
            state = self.store.run(run_id)["state"]
            if state == "cancelling":
                with self.editor.connection() as connection:
                    connection.execute(
                        """UPDATE preeditor_analysis_run_sources
                           SET state='cancelled',stage='cancelled',updated_at=?
                           WHERE run_id=? AND state IN ('pending','proxying','analyzing','rendering')""",
                        (utc_now(), run_id),
                    )
                self._release_power(power_handle)
                power_handle = None
                self.store.set_run(run_id, "cancelled", ended=True)
            else:
                self._release_power(power_handle)
                power_handle = None
                self.store.set_run(run_id, "paused", warning="Stopped safely. Completed samples are ready to review.")
        except Exception as exc:
            self._release_power(power_handle)
            power_handle = None
            self.store.set_run(run_id, "failed", error=str(exc), ended=True)
        finally:
            elapsed = base_elapsed + max(0.0, time.monotonic() - started)
            with self.editor.connection() as connection:
                connection.execute(
                    "UPDATE preeditor_analysis_runs SET elapsed_seconds=?,updated_at=? WHERE id=?",
                    (elapsed, utc_now(), run_id),
                )
            self._release_power(power_handle)
            with self._lock:
                self._active.pop(run_id, None)

    def _update_eta(self, run_id: str, started: float, base_elapsed: float) -> None:
        elapsed = base_elapsed + max(0.001, time.monotonic() - started)
        run = self.store.run(run_id)
        snapshot = {item["source_id"]: float(item.get("duration") or 0) for item in run["source_snapshot"]}
        active_ids = {str(source["source_id"]) for source in run["sources"]}
        completed_ids = {
            str(source["source_id"]) for source in run["sources"] if source["state"] == "completed"
        }
        completed_seconds = sum(snapshot.get(source_id, 0) for source_id in completed_ids)
        total_seconds = sum(snapshot.get(source_id, 0) for source_id in active_ids)
        eta = elapsed / completed_seconds * max(0.0, total_seconds - completed_seconds) if completed_seconds > 0 else None
        with self.editor.connection() as connection:
            connection.execute(
                """UPDATE preeditor_analysis_runs SET elapsed_seconds=?,eta_seconds=?,eta_provenance='measured_this_run',updated_at=?
                   WHERE id=?""",
                (elapsed, eta, utc_now(), run_id),
            )

    def candidate_sample(self, candidate_id: str) -> Path | None:
        candidate = self.store.candidate(candidate_id)
        if not candidate or not candidate.get("sample_path"):
            return None
        path = Path(str(candidate["sample_path"])).resolve()
        run = self.store.run(str(candidate["run_id"]))
        root = Path(str(run["cache_path"])).resolve()
        if not path.is_file() or not path.is_relative_to(root) or not self._validated_sample(path, candidate):
            return None
        return path

    def proxy_path(self, source_id: str, run_id: str) -> Path | None:
        run = self.store.run(run_id)
        if not any(item["source_id"] == source_id for item in run["source_snapshot"]):
            return None
        source = self.editor.source(source_id)
        if not source:
            return None
        facts = next((item for item in run["source_snapshot"] if item["source_id"] == source_id), None)
        if not facts:
            return None
        path = self._proxy_path_for(run, facts)
        resolved = path.resolve()
        root = Path(str(run["cache_path"])).resolve()
        if not resolved.is_file() or not resolved.is_relative_to(root) or not self._validated_proxy(resolved, facts):
            return None
        return resolved

    def full_source_path(self, source_id: str, run_id: str) -> Path | None:
        proxy = self.proxy_path(source_id, run_id)
        if proxy:
            return proxy
        run = self.store.run(run_id)
        expected = next((item for item in run["source_snapshot"] if item["source_id"] == source_id), None)
        if not expected:
            return None
        try:
            source = self.editor.assert_source_unchanged(source_id, str(expected["fingerprint"]))
        except (ValueError, OSError):
            return None
        path = Path(str(source["current_path"])).resolve()
        return path if path.is_file() else None

    def shutdown(self) -> None:
        with self._lock:
            active = list(self._active.values())
            for item in active:
                item.cancel.set()
        for item in active:
            item.thread.join(timeout=5)
            if item.thread.is_alive():
                self._release_power(item.power_handle)
