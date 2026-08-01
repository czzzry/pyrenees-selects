"use strict";

const elements = {
  setup: document.getElementById("setupView"),
  prepare: document.getElementById("prepareView"),
  review: document.getElementById("reviewView"),
  refine: document.getElementById("refineView"),
  storyboardPrepare: document.getElementById("storyboardPrepareView"),
  storyboard: document.getElementById("storyboardView"),
  complete: document.getElementById("completeView"),
  refineComplete: document.getElementById("refineCompleteView"),
  storyboardComplete: document.getElementById("storyboardCompleteView"),
  error: document.getElementById("errorView"),
  loading: document.getElementById("loading"),
  loadingMessage: document.getElementById("loadingMessage"),
  main: document.getElementById("main"),
  reviewCount: document.getElementById("reviewCount"),
  projectsButton: document.getElementById("projectsButton"),
  completeProjectsButton: document.getElementById("completeProjectsButton"),
  projectListSection: document.getElementById("projectListSection"),
  projectList: document.getElementById("projectList"),
  projectForm: document.getElementById("projectForm"),
  projectName: document.getElementById("projectName"),
  sourceDir: document.getElementById("sourceDir"),
  chooseFolderButton: document.getElementById("chooseFolderButton"),
  scanButton: document.getElementById("scanButton"),
  formStatus: document.getElementById("formStatus"),
  prepareProjectLabel: document.getElementById("prepareProjectLabel"),
  libraryPath: document.getElementById("libraryPath"),
  preparationHeading: document.getElementById("preparationHeading"),
  preparationMessage: document.getElementById("preparationMessage"),
  currentFile: document.getElementById("currentFile"),
  progressTrack: document.getElementById("progressTrack"),
  progressBar: document.getElementById("progressBar"),
  progressCount: document.getElementById("progressCount"),
  progressPercent: document.getElementById("progressPercent"),
  startPreparationButton: document.getElementById("startPreparationButton"),
  beginReviewButton: document.getElementById("beginReviewButton"),
  beginRefinementButton: document.getElementById("beginRefinementButton"),
  beginStoryboardButton: document.getElementById("beginStoryboardButton"),
  beginHybridButton: document.getElementById("beginHybridButton"),
  cancelPreparationButton: document.getElementById("cancelPreparationButton"),
  video: document.getElementById("candidateVideo"),
  sourceVideo: document.getElementById("sourceVideo"),
  jumpToSelectionButton: document.getElementById("jumpToSelectionButton"),
  sourceFrameCaption: document.getElementById("sourceFrameCaption"),
  heroFrameNumber: document.getElementById("heroFrameNumber"),
  candidateEyebrow: document.getElementById("candidateEyebrow"),
  candidateTitle: document.getElementById("candidateTitle"),
  candidateReason: document.getElementById("candidateReason"),
  sourceName: document.getElementById("sourceName"),
  sourceRange: document.getElementById("sourceRange"),
  sourceFormat: document.getElementById("sourceFormat"),
  reviewNote: document.getElementById("reviewNote"),
  reviewNoteSaveState: document.getElementById("reviewNoteSaveState"),
  roleOptions: document.getElementById("roleOptions"),
  sessionSummary: document.getElementById("sessionSummary"),
  undoButton: document.getElementById("undoButton"),
  completeSummary: document.getElementById("completeSummary"),
  refineSelectionsButton: document.getElementById("refineSelectionsButton"),
  refinementProgress: document.getElementById("refinementProgress"),
  refinementReviewedCount: document.getElementById("refinementReviewedCount"),
  refinementVideo: document.getElementById("refinementVideo"),
  selectionWindow: document.getElementById("selectionWindow"),
  selectionRange: document.getElementById("selectionRange"),
  refinementDecision: document.getElementById("refinementDecision"),
  refinementContext: document.getElementById("refinementContext"),
  refinementTitle: document.getElementById("refinementTitle"),
  refinementReason: document.getElementById("refinementReason"),
  refinementSource: document.getElementById("refinementSource"),
  refinementSelectedRange: document.getElementById("refinementSelectedRange"),
  refinementSourceFormat: document.getElementById("refinementSourceFormat"),
  refinementNote: document.getElementById("refinementNote"),
  attachMomentButton: document.getElementById("attachMomentButton"),
  noteAnchorLabel: document.getElementById("noteAnchorLabel"),
  refinementSaveState: document.getElementById("refinementSaveState"),
  previousRefinementButton: document.getElementById("previousRefinementButton"),
  nextRefinementButton: document.getElementById("nextRefinementButton"),
  refineCompleteSummary: document.getElementById("refineCompleteSummary"),
  prepareStoryboardButton: document.getElementById("prepareStoryboardButton"),
  reviewRefinementsButton: document.getElementById("reviewRefinementsButton"),
  refineCompleteProjectsButton: document.getElementById("refineCompleteProjectsButton"),
  storyboardPreparationHeading: document.getElementById("storyboardPreparationHeading"),
  storyboardPreparationMessage: document.getElementById("storyboardPreparationMessage"),
  storyboardCurrentFile: document.getElementById("storyboardCurrentFile"),
  storyboardProgressTrack: document.getElementById("storyboardProgressTrack"),
  storyboardProgressBar: document.getElementById("storyboardProgressBar"),
  storyboardProgressCount: document.getElementById("storyboardProgressCount"),
  storyboardProgressPercent: document.getElementById("storyboardProgressPercent"),
  startStoryboardPreparationButton: document.getElementById("startStoryboardPreparationButton"),
  reviewStoryboardButton: document.getElementById("reviewStoryboardButton"),
  cancelStoryboardPreparationButton: document.getElementById("cancelStoryboardPreparationButton"),
  storyboardProgress: document.getElementById("storyboardProgress"),
  storyboardReviewedCount: document.getElementById("storyboardReviewedCount"),
  storyboardVideo: document.getElementById("storyboardVideo"),
  storyboardFrameCaption: document.getElementById("storyboardFrameCaption"),
  storyboardStrip: document.getElementById("storyboardStrip"),
  storyboardStripKey: document.getElementById("storyboardStripKey"),
  storyboardRecommendation: document.getElementById("storyboardRecommendation"),
  storyboardGroup: document.getElementById("storyboardGroup"),
  storyboardContext: document.getElementById("storyboardContext"),
  storyboardTitle: document.getElementById("storyboardTitle"),
  storyboardAppliedTreatment: document.getElementById("storyboardAppliedTreatment"),
  storyboardPreviewNote: document.getElementById("storyboardPreviewNote"),
  storyboardTreatmentLabel: document.getElementById("storyboardTreatmentLabel"),
  storyboardTreatment: document.getElementById("storyboardTreatment"),
  storyboardOwnerNoteBlock: document.getElementById("storyboardOwnerNoteBlock"),
  storyboardOwnerNote: document.getElementById("storyboardOwnerNote"),
  storyboardNote: document.getElementById("storyboardNote"),
  storyboardNoteLabel: document.getElementById("storyboardNoteLabel"),
  storyboardNoteHelp: document.getElementById("storyboardNoteHelp"),
  storyboardNoteSaveState: document.getElementById("storyboardNoteSaveState"),
  storyboardSource: document.getElementById("storyboardSource"),
  storyboardRange: document.getElementById("storyboardRange"),
  storyboardRangeLabel: document.getElementById("storyboardRangeLabel"),
  storyboardTarget: document.getElementById("storyboardTarget"),
  storyboardTargetLabel: document.getElementById("storyboardTargetLabel"),
  storyboardAlternatePicker: document.getElementById("storyboardAlternatePicker"),
  storyboardAlternateList: document.getElementById("storyboardAlternateList"),
  cancelStoryboardAlternateButton: document.getElementById("cancelStoryboardAlternateButton"),
  removeStoryboardItemButton: document.getElementById("removeStoryboardItemButton"),
  chooseStoryboardAlternateButton: document.getElementById("chooseStoryboardAlternateButton"),
  approveStoryboardItemButton: document.getElementById("approveStoryboardItemButton"),
  storyboardActions: document.getElementById("storyboardActions"),
  storyboardNavigation: document.querySelector("#storyboardView .storyboard-navigation"),
  previousStoryboardButton: document.getElementById("previousStoryboardButton"),
  nextStoryboardButton: document.getElementById("nextStoryboardButton"),
  storyboardCompleteSummary: document.getElementById("storyboardCompleteSummary"),
  storyboardCompleteEyebrow: document.getElementById("storyboardCompleteEyebrow"),
  storyboardCompleteTitle: document.getElementById("storyboardCompleteTitle"),
  storyboardCompleteNext: document.getElementById("storyboardCompleteNext"),
  reviewStoryboardAgainButton: document.getElementById("reviewStoryboardAgainButton"),
  storyboardCompleteProjectsButton: document.getElementById("storyboardCompleteProjectsButton"),
  errorMessage: document.getElementById("errorMessage"),
  retryButton: document.getElementById("retryButton"),
};

let state = { project: null, summary: null, candidate: null };
let selectedRole = null;
let lastDecision = null;
let busy = false;
let desktopMode = false;
let currentVideoUrl = null;
let reviewNoteSaveTimer = null;
let reviewNoteSavePromise = null;
let reviewNoteDirty = false;
let reviewNoteRevision = 0;
let refinementVideoUrl = null;
let initialLoadStarted = false;
let preparationPoll = null;
let refinementCandidates = [];
let refinementIndex = 0;
let noteAnchorSeconds = null;
let refinementSaveTimer = null;
let refinementSavePromise = null;
let refinementDirty = false;
let refinementRevision = 0;
let storyboardPreparationPoll = null;
let storyboardItems = [];
let storyboardAlternatives = [];
let storyboardIndex = 0;
let storyboardVideoUrl = null;
let storyboardAlternativeId = null;
let storyboardNoteSaveTimer = null;
let storyboardNoteSavePromise = null;
let storyboardNoteDirty = false;
let storyboardNoteRevision = 0;
let storyboardMode = "two_minute";
let hybridSummary = { total: 0, pending: 0, add: 0, long_only: 0, unsure: 0 };
const desktopExpected = new URLSearchParams(window.location.search).get("desktop") === "1";

function activateDesktop() {
  if (desktopMode || typeof window.pywebview?.api?.state !== "function") return;
  desktopMode = true;
  elements.chooseFolderButton.hidden = false;
  startInitialLoad();
}

window.addEventListener("pywebviewready", activateDesktop);

elements.chooseFolderButton.addEventListener("click", async () => {
  const chosen = await window.pywebview.api.choose_footage_folder(elements.sourceDir.value);
  if (chosen) {
    elements.sourceDir.value = chosen;
    elements.sourceDir.setAttribute("aria-invalid", "false");
  }
});

function setView(name) {
  for (const key of ["setup", "prepare", "review", "refine", "storyboardPrepare", "storyboard", "complete", "refineComplete", "storyboardComplete", "error"]) {
    elements[key].hidden = key !== name;
  }
}

function setBusy(value, message = "Preparing the screening room…") {
  busy = value;
  elements.loading.hidden = !value;
  elements.loadingMessage.textContent = message;
  elements.main.setAttribute("aria-busy", String(value));
  document.querySelectorAll("button").forEach(button => { button.disabled = value; });
}

async function request(url, options = {}) {
  if (desktopMode) {
    const payload = options.body ? JSON.parse(options.body) : {};
    if (url === "/api/state") return window.pywebview.api.state();
    if (url === "/api/projects") {
      return window.pywebview.api.create_project(payload.name, payload.source_dir);
    }
    if (url === "/api/projects/open") return window.pywebview.api.open_project(payload.project_id);
    if (url === "/api/scan") return window.pywebview.api.scan(payload.project_id);
    if (url === "/api/preparation/status") return window.pywebview.api.preparation_status(payload.project_id);
    if (url === "/api/preparation/start") return window.pywebview.api.start_preparation(payload.project_id);
    if (url === "/api/preparation/cancel") return window.pywebview.api.cancel_preparation();
    if (url === "/api/refinement") return window.pywebview.api.refinement_state(payload.project_id || "");
    if (url === "/api/storyboard") return window.pywebview.api.storyboard_state(payload.project_id || "", payload.variant_seconds || 120);
    if (url === "/api/hybrid") return window.pywebview.api.hybrid_state(payload.project_id || "");
    if (url === "/api/storyboard/preparation/status") return window.pywebview.api.storyboard_preparation_status(payload.project_id);
    if (url === "/api/storyboard/preparation/start") return window.pywebview.api.start_storyboard_preparation(payload.project_id);
    if (url === "/api/storyboard/preparation/cancel") return window.pywebview.api.cancel_storyboard_preparation();
    const decisionMatch = url.match(/^\/api\/candidates\/(\d+)\/decision$/);
    if (decisionMatch) {
      return window.pywebview.api.decide(Number(decisionMatch[1]), payload.decision, payload.story_role || null);
    }
    const candidateNoteMatch = url.match(/^\/api\/candidates\/(\d+)\/note$/);
    if (candidateNoteMatch) {
      return window.pywebview.api.save_candidate_note(
        Number(candidateNoteMatch[1]),
        payload.note || "",
      );
    }
    const refinementMatch = url.match(/^\/api\/refinements\/(\d+)$/);
    if (refinementMatch) {
      return window.pywebview.api.save_refinement(
        Number(refinementMatch[1]),
        payload.note || "",
        payload.note_anchor_seconds ?? null,
        Boolean(payload.reviewed),
      );
    }
    const storyboardNoteMatch = url.match(/^\/api\/storyboard\/items\/(\d+)\/note$/);
    if (storyboardNoteMatch) {
      return window.pywebview.api.save_storyboard_note(
        Number(storyboardNoteMatch[1]),
        payload.note || "",
      );
    }
    const hybridMatch = url.match(/^\/api\/hybrid\/items\/(\d+)$/);
    if (hybridMatch) {
      return window.pywebview.api.review_hybrid_item(
        Number(hybridMatch[1]),
        payload.decision,
      );
    }
    const storyboardMatch = url.match(/^\/api\/storyboard\/items\/(\d+)$/);
    if (storyboardMatch) {
      return window.pywebview.api.review_storyboard_item(
        Number(storyboardMatch[1]),
        payload.decision,
        payload.replacement_candidate_id ?? null,
      );
    }
    throw new Error("Unsupported desktop request.");
  }
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function formatClock(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const remaining = Math.floor(safe % 60);
  return `${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
}

function updateSummary(summary) {
  state.summary = summary;
  if (!summary) {
    elements.reviewCount.textContent = "Local project";
    return;
  }
  const decisions = summary.decisions;
  const reviewed = decisions.keep.count + decisions.maybe.count + decisions.skip.count;
  elements.reviewCount.textContent = `${reviewed} / ${summary.media_count} reviewed`;
  elements.sessionSummary.textContent = `kept ${decisions.keep.count} · maybe ${decisions.maybe.count} · skipped ${decisions.skip.count} · ${decisions.pending.count} remaining`;
}

function refinementButtonLabel() {
  const refinement = state.refinement_summary || {};
  const total = Number(refinement.total || 0);
  const reviewed = Number(refinement.reviewed || 0);
  if (reviewed > 0 && reviewed < total) return `Continue refinement · ${reviewed} of ${total}`;
  if (reviewed === total && total > 0) return `Review ${total} selections again`;
  return `Refine ${total} selected moments`;
}

function setRole(role) {
  selectedRole = selectedRole === role ? null : role;
  renderRole();
}

function renderRole() {
  elements.roleOptions.querySelectorAll("button").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.role === selectedRole));
  });
}

function renderCandidate(candidate) {
  if (reviewNoteSaveTimer) {
    clearTimeout(reviewNoteSaveTimer);
    reviewNoteSaveTimer = null;
  }
  state.candidate = candidate;
  if (!candidate) {
    elements.sourceVideo.pause();
    elements.sourceVideo.removeAttribute("src");
    elements.sourceVideo.load();
    setView("complete");
    const kept = state.summary?.decisions.keep.count || 0;
    const maybe = state.summary?.decisions.maybe.count || 0;
    elements.completeSummary.textContent = `You kept ${kept} sequences and left ${maybe} possibilities for the assembly pass.`;
    elements.refineSelectionsButton.textContent = refinementButtonLabel();
    return;
  }
  setView("review");
  reviewNoteDirty = false;
  reviewNoteRevision = 0;
  selectedRole = candidate.story_role || null;
  renderRole();
  elements.candidateEyebrow.textContent = `${candidate.captured_label} · ${candidate.chapter} · ${Math.round(candidate.duration)} seconds`;
  elements.candidateTitle.textContent = candidate.title;
  elements.candidateReason.textContent = candidate.reason;
  elements.sourceName.textContent = candidate.filename;
  elements.sourceRange.textContent = `${formatClock(candidate.start_seconds)}–${formatClock(candidate.start_seconds + candidate.duration)} + ${candidate.handle_seconds}s handles`;
  elements.sourceFormat.textContent = `${candidate.width}×${candidate.height} · ${Number(candidate.fps).toFixed(2)} fps · ${candidate.codec.toUpperCase()}`;
  elements.reviewNote.value = candidate.note || "";
  setReviewNoteSaveState(candidate.refinement_updated_at ? "Saved locally." : "Comments save locally.");
  elements.heroFrameNumber.textContent = `Candidate ${String(candidate.id).padStart(3, "0")} · review proxy 360p`;
  elements.sourceFrameCaption.textContent = `Full original · ${formatClock(candidate.source_duration)} · scrub freely`;
  elements.jumpToSelectionButton.textContent = `Jump to selected · ${formatClock(candidate.start_seconds)}`;
  elements.sourceVideo.pause();
  elements.sourceVideo.removeAttribute("src");
  elements.sourceVideo.load();
  if (desktopMode) {
    loadDesktopAssets(candidate.id);
  } else {
    elements.video.pause();
    elements.video.src = candidate.video_url;
    elements.video.load();
    elements.sourceVideo.src = candidate.source_video_url;
    elements.sourceVideo.load();
  }
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
}

function videoUrlFromBase64(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return URL.createObjectURL(new Blob([bytes], { type: "video/mp4" }));
}

async function loadDesktopAssets(candidateId) {
  setBusy(true, "Preparing low-resolution review media…");
  try {
    const assets = await window.pywebview.api.candidate_assets(candidateId);
    if (state.candidate?.id !== candidateId) return;
    elements.video.pause();
    if (currentVideoUrl) URL.revokeObjectURL(currentVideoUrl);
    currentVideoUrl = videoUrlFromBase64(assets.video_base64);
    elements.video.src = currentVideoUrl;
    elements.video.load();
    elements.sourceVideo.src = assets.source_video_url;
    elements.sourceVideo.load();
    setBusy(false);
  } catch (error) {
    showError(error);
  }
}

function setReviewNoteSaveState(message, isError = false) {
  elements.reviewNoteSaveState.textContent = message;
  elements.reviewNoteSaveState.classList.toggle("is-error", isError);
}

async function saveCurrentCandidateNote() {
  if (reviewNoteSaveTimer) {
    clearTimeout(reviewNoteSaveTimer);
    reviewNoteSaveTimer = null;
  }
  const candidate = state.candidate;
  if (!candidate || !reviewNoteDirty) return true;
  const candidateId = Number(candidate.id);
  const revision = reviewNoteRevision;
  const note = elements.reviewNote.value;
  setReviewNoteSaveState("Saving locally…");
  const previousSave = reviewNoteSavePromise;
  const save = (async () => {
    if (previousSave) await previousSave.catch(() => undefined);
    return request(`/api/candidates/${candidateId}/note`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
  })();
  reviewNoteSavePromise = save;
  try {
    const result = await save;
    if (state.candidate?.id === candidateId && reviewNoteRevision === revision) {
      state.candidate = result.candidate;
      reviewNoteDirty = false;
      setReviewNoteSaveState(result.candidate.note ? "Saved locally." : "Comments save locally.");
    }
    return true;
  } catch (error) {
    if (state.candidate?.id === candidateId) {
      reviewNoteDirty = true;
      setReviewNoteSaveState(`Could not save: ${error.message || error}`, true);
      elements.reviewNote.focus();
    }
    return false;
  } finally {
    if (reviewNoteSavePromise === save) reviewNoteSavePromise = null;
  }
}

function currentRefinement() {
  return refinementCandidates[refinementIndex] || null;
}

function setRefinementSaveState(message, isError = false) {
  elements.refinementSaveState.textContent = message;
  elements.refinementSaveState.classList.toggle("is-error", isError);
}

function updateNoteAnchorLabel() {
  elements.noteAnchorLabel.textContent = noteAnchorSeconds === null
    ? "No moment attached"
    : `Attached to source ${formatClock(noteAnchorSeconds)}`;
}

async function loadDesktopRefinementAsset(candidateId) {
  setBusy(true, "Loading the selected low-resolution preview…");
  try {
    const assets = await window.pywebview.api.refinement_asset(candidateId);
    if (currentRefinement()?.id !== candidateId) return;
    elements.refinementVideo.pause();
    if (refinementVideoUrl) URL.revokeObjectURL(refinementVideoUrl);
    refinementVideoUrl = videoUrlFromBase64(assets.video_base64);
    elements.refinementVideo.src = refinementVideoUrl;
    elements.refinementVideo.load();
    setBusy(false);
  } catch (error) {
    showError(error);
  }
}

function renderRefinementCandidate() {
  const candidate = currentRefinement();
  if (!candidate) {
    setView("refineComplete");
    const summary = state.refinement_summary || { reviewed: 0, total: 0, noted: 0 };
    elements.refineCompleteSummary.textContent = `You revisited ${summary.reviewed} of ${summary.total} selected moments and saved notes on ${summary.noted}.`;
    return;
  }
  if (refinementSaveTimer) {
    clearTimeout(refinementSaveTimer);
    refinementSaveTimer = null;
  }
  setView("refine");
  refinementDirty = false;
  refinementRevision = 0;
  noteAnchorSeconds = candidate.note_anchor_seconds ?? null;
  elements.refinementProgress.textContent = `Selection ${refinementIndex + 1} of ${refinementCandidates.length}`;
  elements.refinementReviewedCount.textContent = `${state.refinement_summary?.reviewed || 0} refined`;
  elements.refinementDecision.textContent = candidate.screening_decision;
  elements.refinementDecision.className = candidate.screening_decision === "keep" ? "is-keep" : "is-maybe";
  elements.refinementContext.textContent = `${candidate.captured_label} · ${candidate.chapter}`;
  elements.refinementTitle.textContent = candidate.title;
  elements.refinementReason.textContent = candidate.reason;
  elements.refinementSource.textContent = candidate.filename;
  elements.refinementSelectedRange.textContent = `${formatClock(candidate.start_seconds)}–${formatClock(Number(candidate.start_seconds) + Number(candidate.duration))}`;
  elements.refinementSourceFormat.textContent = `${candidate.width}×${candidate.height} · ${Number(candidate.fps).toFixed(2)} fps · ${String(candidate.codec).toUpperCase()}`;
  elements.refinementNote.value = candidate.note || "";
  updateNoteAnchorLabel();
  setRefinementSaveState(candidate.refinement_updated_at ? "Saved locally." : "Notes save locally.");
  elements.selectionWindow.style.left = "0";
  elements.selectionWindow.style.width = "100%";
  elements.selectionRange.textContent = `Selected ${Math.round(candidate.duration)}s`;
  elements.previousRefinementButton.disabled = refinementIndex === 0;
  elements.nextRefinementButton.textContent = refinementIndex === refinementCandidates.length - 1 ? "Save and finish" : "Save and next";
  if (desktopMode) {
    loadDesktopRefinementAsset(candidate.id);
  } else {
    elements.refinementVideo.pause();
    elements.refinementVideo.src = candidate.refinement_video_url;
    elements.refinementVideo.load();
  }
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
}

async function openRefinement(restart = false) {
  if (!state.project) return;
  setBusy(true, "Opening your selected moments…");
  try {
    const result = await request("/api/refinement", {
      method: desktopMode ? "POST" : "GET",
      body: desktopMode ? JSON.stringify({ project_id: state.project.id }) : undefined,
    });
    refinementCandidates = result.candidates || [];
    state.refinement_summary = result.summary;
    const firstUnreviewed = refinementCandidates.findIndex(candidate => !candidate.reviewed_at);
    refinementIndex = restart || firstUnreviewed < 0 ? 0 : firstUnreviewed;
    if (!refinementCandidates.length) {
      throw new Error("No completed Keep or Maybe selections are available to refine.");
    }
    renderRefinementCandidate();
    if (!desktopMode) setBusy(false);
  } catch (error) {
    showError(error);
  }
}

async function saveCurrentRefinement(reviewed = false) {
  const candidate = currentRefinement();
  if (!candidate) return true;
  if (refinementSaveTimer) {
    clearTimeout(refinementSaveTimer);
    refinementSaveTimer = null;
  }
  if (!refinementDirty && (!reviewed || candidate.reviewed_at)) return true;
  const candidateId = candidate.id;
  const revision = refinementRevision;
  const payload = {
    note: elements.refinementNote.value,
    note_anchor_seconds: noteAnchorSeconds,
    reviewed,
  };
  setRefinementSaveState("Saving locally…");
  const previousSave = refinementSavePromise;
  const save = (async () => {
    if (previousSave) await previousSave.catch(() => undefined);
    return request(`/api/refinements/${candidateId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  })();
  refinementSavePromise = save;
  try {
    const result = await save;
    const candidateIndex = refinementCandidates.findIndex(item => item.id === candidateId);
    if (candidateIndex >= 0) refinementCandidates[candidateIndex] = result.candidate;
    state.refinement_summary = result.summary;
    if (currentRefinement()?.id === candidateId && refinementRevision === revision) {
      refinementDirty = false;
      elements.refinementReviewedCount.textContent = `${result.summary.reviewed} refined`;
      setRefinementSaveState("Saved locally.");
    }
    return true;
  } catch (error) {
    setRefinementSaveState(`Could not save: ${error.message || error}`, true);
    return false;
  } finally {
    if (refinementSavePromise === save) refinementSavePromise = null;
  }
}

function storyboardPreparationPercent(status) {
  if (!status?.total) return 0;
  return Math.max(0, Math.min(100, Math.round((Number(status.processed || 0) / Number(status.total)) * 100)));
}

function displayStoryboardPreparationStatus(status) {
  const percent = storyboardPreparationPercent(status);
  const running = status.state === "running";
  const complete = status.state === "complete";
  const blocked = status.state === "blocked";
  const resumable = ["interrupted", "failed"].includes(status.state) || Number(status.processed || 0) > 0;
  elements.storyboardProgressBar.style.width = `${percent}%`;
  elements.storyboardProgressTrack.setAttribute("aria-valuenow", String(percent));
  elements.storyboardProgressPercent.textContent = `${percent}%`;
  elements.storyboardProgressCount.textContent = status.total
    ? `${status.processed || 0} of ${status.total} proposed shots`
    : "20 proposed shots";
  elements.storyboardCurrentFile.textContent = status.current_file ? `Now preparing: ${status.current_file}` : "";
  elements.storyboardPreparationHeading.textContent = complete
    ? "Ready for your review"
    : running
      ? "Preparing the two-minute cut"
      : resumable
        ? "Ready to resume"
        : "Ready when you are";
  elements.storyboardPreparationMessage.textContent = status.message || "Only changed proposed ranges need new disposable previews.";
  elements.startStoryboardPreparationButton.hidden = running || complete || blocked;
  elements.startStoryboardPreparationButton.textContent = resumable ? "Resume preparation" : "Start preparation";
  elements.cancelStoryboardPreparationButton.hidden = !running;
  elements.reviewStoryboardButton.hidden = !complete;
  if (running && !storyboardPreparationPoll) {
    storyboardPreparationPoll = setInterval(refreshStoryboardPreparationStatus, 2000);
  }
  if (!running && storyboardPreparationPoll) {
    clearInterval(storyboardPreparationPoll);
    storyboardPreparationPoll = null;
  }
}

async function refreshStoryboardPreparationStatus() {
  if (!state.project) return;
  if (!desktopMode) {
    displayStoryboardPreparationStatus({
      state: "complete",
      processed: 20,
      total: 20,
      message: "The two-minute storyboard is ready for your review.",
    });
    return;
  }
  try {
    const status = await request("/api/storyboard/preparation/status", {
      method: "POST",
      body: JSON.stringify({ project_id: state.project.id }),
    });
    displayStoryboardPreparationStatus(status);
  } catch (error) {
    displayStoryboardPreparationStatus({ state: "failed", message: error instanceof Error ? error.message : String(error) });
  }
}

async function openStoryboardPreparation() {
  if (!state.project) return;
  setView("storyboardPrepare");
  await refreshStoryboardPreparationStatus();
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
}

function currentStoryboardItem() {
  return storyboardItems[storyboardIndex] || null;
}

function currentStoryboardSummary() {
  if (storyboardMode === "hybrid") return hybridSummary;
  return state.storyboard_summary?.["120"] || { total: storyboardItems.length, pending: 0, approved: 0, removed: 0, target_duration: 0 };
}

function storyboardItemDecision(item) {
  return storyboardMode === "hybrid" ? item.hybrid_decision : item.review_state;
}

function setStoryboardVideoUrl(url) {
  elements.storyboardVideo.pause();
  if (storyboardVideoUrl) URL.revokeObjectURL(storyboardVideoUrl);
  storyboardVideoUrl = url;
  elements.storyboardVideo.src = url || "";
  elements.storyboardVideo.load();
}

function updateStoryboardNavigation() {
  elements.previousStoryboardButton.disabled = storyboardIndex === 0;
  elements.nextStoryboardButton.disabled = storyboardIndex === storyboardItems.length - 1;
}

function setStoryboardNoteSaveState(message, isError = false) {
  elements.storyboardNoteSaveState.textContent = message;
  elements.storyboardNoteSaveState.classList.toggle("is-error", isError);
}

async function saveCurrentStoryboardNote() {
  if (storyboardNoteSaveTimer) {
    clearTimeout(storyboardNoteSaveTimer);
    storyboardNoteSaveTimer = null;
  }
  const item = currentStoryboardItem();
  if (!item || !storyboardNoteDirty) return true;
  const itemId = Number(item.storyboard_item_id);
  const note = elements.storyboardNote.value;
  const revision = storyboardNoteRevision;
  storyboardNoteDirty = false;
  setStoryboardNoteSaveState("Saving locally…");
  try {
    const pending = request(`/api/storyboard/items/${itemId}/note`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
    storyboardNoteSavePromise = pending;
    const saved = await pending;
    if (storyboardNoteSavePromise === pending) storyboardNoteSavePromise = null;
    const stored = storyboardItems.find(entry => Number(entry.storyboard_item_id) === itemId);
    if (stored) stored.storyboard_note = saved.storyboard_note || "";
    if (
      Number(currentStoryboardItem()?.storyboard_item_id) === itemId
      && storyboardNoteRevision === revision
      && !storyboardNoteDirty
    ) {
      setStoryboardNoteSaveState(saved.storyboard_note ? "Saved" : "No additional note");
    }
    return true;
  } catch (error) {
    if (Number(currentStoryboardItem()?.storyboard_item_id) === itemId) {
      storyboardNoteDirty = true;
      setStoryboardNoteSaveState("Could not save. Your text is still here; try again.", true);
      elements.storyboardNote.focus();
    }
    return false;
  }
}

async function loadDesktopStoryboardAsset(candidateId, planned = true) {
  const hybrid = storyboardMode === "hybrid";
  setBusy(true, hybrid ? "Loading the finished longer-cut shot…" : planned ? "Loading the proposed source range…" : "Loading the alternate preview…");
  try {
    const assets = hybrid
      ? await window.pywebview.api.hybrid_asset(candidateId)
      : planned
      ? await window.pywebview.api.storyboard_asset(candidateId)
      : await window.pywebview.api.refinement_asset(candidateId);
    const expected = planned ? currentStoryboardItem()?.candidate_id : storyboardAlternativeId;
    if (Number(expected) !== Number(candidateId)) return;
    setStoryboardVideoUrl(videoUrlFromBase64(assets.video_base64));
    setBusy(false);
    updateStoryboardNavigation();
  } catch (error) {
    showError(error);
  }
}

function renderStoryboardDetails(item, isAlternative = false) {
  const current = currentStoryboardItem();
  if (!item || !current) return;
  if (storyboardMode === "hybrid") {
    elements.storyboardRecommendation.textContent = "Long-cut option";
    elements.storyboardRecommendation.className = item.hybrid_decision === "add" ? "is-keep" : "";
    elements.storyboardGroup.textContent = `${String(item.story_group).replaceAll("-", " ")} · extra from the 3:47 cut`;
    elements.storyboardContext.textContent = `${item.captured_label} · candidate ${String(item.candidate_id).padStart(3, "0")} · ${item.screening_decision} from your first pass`;
    elements.storyboardTitle.textContent = item.title;
    elements.storyboardAppliedTreatment.textContent = "The finished treatment from the longer cut";
    elements.storyboardPreviewNote.textContent = "This is the exact 360p shot you saw in the 3:47 version, including its speed and stabilization treatment.";
    elements.storyboardTreatmentLabel.textContent = "Why it was added to the longer cut";
    elements.storyboardTreatment.textContent = item.hybrid_rationale;
    elements.storyboardOwnerNoteBlock.hidden = !item.note;
    elements.storyboardOwnerNote.textContent = item.note || "";
    elements.storyboardSource.textContent = item.filename;
    elements.storyboardRange.textContent = `${formatClock(item.hybrid_source_start_seconds)}–${formatClock(Number(item.hybrid_source_start_seconds) + Number(item.hybrid_source_duration))}`;
    elements.storyboardRangeLabel.textContent = "Source range";
    elements.storyboardTarget.textContent = `${Number(item.hybrid_output_duration).toFixed(1)} seconds as shown`;
    elements.storyboardTargetLabel.textContent = "Clip length";
    elements.storyboardFrameCaption.textContent = `Candidate ${String(item.candidate_id).padStart(3, "0")} · finished longer-cut treatment · 360p`;
    elements.storyboardNoteLabel.textContent = "Optional hybrid note";
    elements.storyboardNoteHelp.textContent = "For example: add this, but place it later. This saves separately from your original note.";
    elements.storyboardNote.placeholder = "For example: add this, but place it later.";
    return;
  }
  elements.storyboardRecommendation.textContent = isAlternative ? "Alternate" : item.recommendation;
  elements.storyboardRecommendation.className = item.review_state === "approved" && !isAlternative ? "is-keep" : "";
  elements.storyboardGroup.textContent = `${String(item.story_group).replaceAll("-", " ")} · ${isAlternative ? "alternate preview" : "proposed edit"}`;
  elements.storyboardContext.textContent = `${item.captured_label} · ${item.chapter} · ${item.screening_decision} from your first pass`;
  elements.storyboardTitle.textContent = item.title;
  elements.storyboardAppliedTreatment.textContent = isAlternative
    ? "The original selected range only"
    : "The proposed start and end points only";
  elements.storyboardPreviewNote.textContent = "Speed, stabilization, smoothing and crops are not visible yet.";
  elements.storyboardTreatmentLabel.textContent = "Planned for the treated rough cut";
  elements.storyboardTreatment.textContent = item.treatment;
  elements.storyboardOwnerNoteBlock.hidden = !item.note;
  elements.storyboardOwnerNote.textContent = item.note || "";
  elements.storyboardSource.textContent = item.filename;
  elements.storyboardRange.textContent = `${formatClock(item.proposed_start_seconds)}–${formatClock(Number(item.proposed_start_seconds) + Number(item.proposed_duration))}`;
  elements.storyboardTarget.textContent = `${Math.round(Number(current.target_duration))} seconds in the cut`;
  elements.storyboardRangeLabel.textContent = "Proposed";
  elements.storyboardTargetLabel.textContent = "Cut";
  elements.storyboardFrameCaption.textContent = isAlternative
    ? `Candidate ${String(item.candidate_id).padStart(3, "0")} · original selected range`
    : `Candidate ${String(item.candidate_id).padStart(3, "0")} · proposed source range · 360p`;
  elements.storyboardNoteLabel.textContent = "Add a note for this shot";
  elements.storyboardNoteHelp.textContent = "This stays separate from your original note and saves automatically.";
  elements.storyboardNote.placeholder = "For example: this still feels too fast, or hold the mountain view longer.";
}

function renderStoryboardStrip() {
  elements.storyboardStrip.replaceChildren();
  elements.storyboardStrip.style.gridTemplateColumns = `repeat(${Math.min(storyboardItems.length, 20)}, minmax(10px, 1fr))`;
  elements.storyboardStrip.setAttribute("aria-label", storyboardMode === "hybrid" ? "Long-only shots for the hybrid" : "Two-minute cut shots");
  elements.storyboardStripKey.innerHTML = storyboardMode === "hybrid"
    ? '<span></span> Not decided &nbsp; <span class="is-approved"></span> Add &nbsp; <span class="is-removed"></span> Long only &nbsp; <span class="is-unsure"></span> Unsure'
    : '<span></span> Pending &nbsp; <span class="is-approved"></span> Approved &nbsp; <span class="is-removed"></span> Removed';
  for (const [index, item] of storyboardItems.entries()) {
    const decision = storyboardItemDecision(item);
    const button = document.createElement("button");
    button.type = "button";
    button.classList.toggle("is-current", index === storyboardIndex);
    button.classList.toggle("is-approved", decision === "approved" || decision === "add");
    button.classList.toggle("is-removed", decision === "removed" || decision === "long_only");
    button.classList.toggle("is-unsure", decision === "unsure");
    button.setAttribute("aria-label", `Shot ${index + 1}: ${decision}`);
    button.title = `Shot ${index + 1} · candidate ${item.candidate_id} · ${decision}`;
    button.addEventListener("click", async () => {
      if (!await saveCurrentStoryboardNote()) return;
      storyboardIndex = index;
      renderStoryboardItem();
    });
    elements.storyboardStrip.append(button);
  }
}

function renderStoryboardItem() {
  const item = currentStoryboardItem();
  if (!item) return;
  storyboardAlternativeId = null;
  setView("storyboard");
  elements.storyboardAlternatePicker.hidden = true;
  const summary = currentStoryboardSummary();
  if (storyboardMode === "hybrid") {
    elements.storyboardProgress.textContent = `Long-only shot ${storyboardIndex + 1} of ${storyboardItems.length}`;
    elements.storyboardReviewedCount.textContent = `${Number(summary.total || 0) - Number(summary.pending || 0)} decided · ${summary.add || 0} to add`;
    elements.approveStoryboardItemButton.textContent = item.hybrid_decision === "add" ? "Added to hybrid" : "Add to hybrid";
    elements.removeStoryboardItemButton.textContent = item.hybrid_decision === "long_only" ? "Kept in long version only" : "Long version only";
    elements.chooseStoryboardAlternateButton.textContent = item.hybrid_decision === "unsure" ? "Marked unsure" : "Unsure for now";
    document.querySelector("#storyboardView .preview-status").after(elements.storyboardActions);
    elements.storyboardActions.after(elements.storyboardNavigation);
  } else {
    elements.storyboardProgress.textContent = `Shot ${storyboardIndex + 1} of ${storyboardItems.length}`;
    elements.storyboardReviewedCount.textContent = `${Number(summary.total || 0) - Number(summary.pending || 0)} reviewed · ${summary.approved || 0} approved`;
    elements.approveStoryboardItemButton.textContent = item.review_state === "approved" ? "Shot approved and edits planned" : "Approve shot and planned edits";
    elements.removeStoryboardItemButton.textContent = item.review_state === "removed" ? "Removed from cut" : "Remove from cut";
    elements.chooseStoryboardAlternateButton.textContent = "Choose another shot";
    elements.storyboardAlternatePicker.after(elements.storyboardActions);
    elements.storyboardActions.after(elements.storyboardNavigation);
  }
  storyboardNoteDirty = false;
  elements.storyboardNote.value = item.storyboard_note || "";
  setStoryboardNoteSaveState(item.storyboard_note ? "Saved" : "No additional note");
  updateStoryboardNavigation();
  renderStoryboardDetails(item);
  renderStoryboardStrip();
  if (desktopMode) {
    loadDesktopStoryboardAsset(item.candidate_id, true);
  } else {
    setStoryboardVideoUrl(storyboardMode === "hybrid" ? item.hybrid_video_url : item.storyboard_video_url);
  }
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
}

function finishStoryboardReview() {
  const summary = currentStoryboardSummary();
  const replacements = storyboardItems.filter(item => item.replacement_candidate_id !== null).length;
  const additionalNotes = storyboardItems.filter(item => String(item.storyboard_note || "").trim()).length;
  setView("storyboardComplete");
  if (storyboardMode === "hybrid") {
    const addedSeconds = storyboardItems
      .filter(item => item.hybrid_decision === "add")
      .reduce((total, item) => total + Number(item.hybrid_output_duration || 0), 0);
    const estimated = 160.16 + addedSeconds;
    elements.storyboardCompleteEyebrow.textContent = "Hybrid choices complete";
    elements.storyboardCompleteTitle.textContent = "The best of both cuts is selected.";
    elements.storyboardCompleteSummary.textContent = `You chose ${summary.add || 0} long-only shot${summary.add === 1 ? "" : "s"} to add, kept ${summary.long_only || 0} in the long version only, and marked ${summary.unsure || 0} unsure. The resulting hybrid is estimated at about ${formatClock(estimated)} before any final trim.`;
    elements.storyboardCompleteNext.textContent = "The hybrid can now be assembled as another separate preview. Your 2:40 and 3:47 versions remain untouched.";
    elements.reviewStoryboardAgainButton.textContent = "Review the hybrid choices again";
    return;
  }
  elements.storyboardCompleteEyebrow.textContent = "Two-minute storyboard complete";
  elements.storyboardCompleteTitle.textContent = "The journey has a shape.";
  elements.storyboardCompleteSummary.textContent = `You approved ${summary.approved || 0} shots, removed ${summary.removed || 0}, chose ${replacements} alternate${replacements === 1 ? "" : "s"}, and saved ${additionalNotes} additional shot note${additionalNotes === 1 ? "" : "s"}. The working cut is about ${Math.round(summary.target_duration || 0)} seconds before transitions. Effects have not been rendered yet.`;
  elements.storyboardCompleteNext.textContent = "Render the treated rough cut with the non-bird speed, smoothing, stabilization and crop changes. The local benchmark estimates about 10–20 minutes; no rental is needed.";
  elements.reviewStoryboardAgainButton.textContent = "Review the cut again";
}

async function openStoryboardReview(restart = false) {
  if (!state.project) return;
  storyboardMode = "two_minute";
  setBusy(true, "Opening the two-minute cut…");
  try {
    const result = await request("/api/storyboard", {
      method: desktopMode ? "POST" : "GET",
      body: desktopMode ? JSON.stringify({ project_id: state.project.id, variant_seconds: 120 }) : undefined,
    });
    storyboardItems = result.items || [];
    storyboardAlternatives = result.alternatives || [];
    state.storyboard_summary = result.summary || {};
    if (!storyboardItems.length) throw new Error("The two-minute edit plan is not available for this project.");
    const firstPending = storyboardItems.findIndex(item => item.review_state === "pending");
    storyboardIndex = restart || firstPending < 0 ? 0 : firstPending;
    renderStoryboardItem();
    if (!desktopMode) {
      setBusy(false);
      updateStoryboardNavigation();
    }
  } catch (error) {
    showError(error);
  }
}

async function openHybridReview(restart = false) {
  if (!state.project) return;
  storyboardMode = "hybrid";
  setBusy(true, "Opening the 13 long-only shots…");
  try {
    const result = await request("/api/hybrid", {
      method: desktopMode ? "POST" : "GET",
      body: desktopMode ? JSON.stringify({ project_id: state.project.id }) : undefined,
    });
    storyboardItems = result.items || [];
    storyboardAlternatives = [];
    hybridSummary = result.summary || { total: storyboardItems.length, pending: storyboardItems.length, add: 0, long_only: 0, unsure: 0 };
    state.hybrid_summary = hybridSummary;
    if (!storyboardItems.length) throw new Error("The longer-cut selection review is not available for this project.");
    const firstPending = storyboardItems.findIndex(item => item.hybrid_decision === "pending");
    storyboardIndex = restart || firstPending < 0 ? 0 : firstPending;
    renderStoryboardItem();
    if (!desktopMode) {
      setBusy(false);
      updateStoryboardNavigation();
    }
  } catch (error) {
    showError(error);
  }
}

function advanceStoryboardAfterReview() {
  const pendingAfter = storyboardItems.findIndex((item, index) => index > storyboardIndex && storyboardItemDecision(item) === "pending");
  const pendingBefore = storyboardItems.findIndex((item, index) => index <= storyboardIndex && storyboardItemDecision(item) === "pending");
  const next = pendingAfter >= 0 ? pendingAfter : pendingBefore;
  if (next < 0) {
    finishStoryboardReview();
    return;
  }
  storyboardIndex = next;
  renderStoryboardItem();
}

async function reviewCurrentStoryboard(decision, replacementCandidateId = null) {
  const item = currentStoryboardItem();
  if (!item || busy) return;
  if (!await saveCurrentStoryboardNote()) return;
  setBusy(true, "Saving your storyboard decision…");
  try {
    const endpoint = storyboardMode === "hybrid"
      ? `/api/hybrid/items/${item.storyboard_item_id}`
      : `/api/storyboard/items/${item.storyboard_item_id}`;
    const result = await request(endpoint, {
      method: "POST",
      body: JSON.stringify({ decision, replacement_candidate_id: replacementCandidateId }),
    });
    storyboardItems = result.items || [];
    storyboardAlternatives = result.alternatives || [];
    if (storyboardMode === "hybrid") {
      hybridSummary = result.summary || hybridSummary;
      state.hybrid_summary = hybridSummary;
    } else {
      state.storyboard_summary = result.summary || {};
    }
    setBusy(false);
    advanceStoryboardAfterReview();
  } catch (error) {
    showError(error);
  }
}

function matchingStoryboardAlternatives(item) {
  return storyboardAlternatives.filter(alternate => alternate.story_group === item.story_group);
}

function renderStoryboardAlternatives() {
  const item = currentStoryboardItem();
  if (!item) return;
  storyboardAlternativeId = null;
  elements.storyboardAlternatePicker.hidden = false;
  elements.storyboardAlternateList.replaceChildren();
  if (item.replacement_candidate_id !== null) {
    const restore = document.createElement("button");
    restore.type = "button";
    restore.className = "alternate-row";
    restore.innerHTML = `<span>↶</span><div><strong>Restore the original proposed shot</strong><small>Candidate ${String(item.planned_candidate_id).padStart(3, "0")}</small></div><span>Restore</span>`;
    restore.addEventListener("click", () => reviewCurrentStoryboard("restore"));
    elements.storyboardAlternateList.append(restore);
  }
  const alternatives = matchingStoryboardAlternatives(item);
  for (const alternate of alternatives) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "alternate-row";
    button.dataset.candidateId = String(alternate.candidate_id);
    button.setAttribute("aria-pressed", "false");
    const number = document.createElement("span");
    number.textContent = String(alternate.candidate_id).padStart(3, "0");
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = alternate.title;
    const note = document.createElement("small");
    note.textContent = alternate.note || alternate.treatment;
    copy.append(title, note);
    const action = document.createElement("span");
    action.textContent = "Preview";
    button.append(number, copy, action);
    button.addEventListener("click", () => {
      storyboardAlternativeId = alternate.candidate_id;
      elements.storyboardAlternateList.querySelectorAll("button[aria-pressed]").forEach(row => row.setAttribute("aria-pressed", String(row === button)));
      elements.approveStoryboardItemButton.textContent = "Use this alternate and planned edits";
      renderStoryboardDetails(alternate, true);
      if (desktopMode) loadDesktopStoryboardAsset(alternate.candidate_id, false);
      else setStoryboardVideoUrl(`/media/candidates/${alternate.candidate_id}.mp4`);
    });
    elements.storyboardAlternateList.append(button);
  }
  if (!alternatives.length && item.replacement_candidate_id === null) {
    const empty = document.createElement("p");
    empty.className = "field-note";
    empty.textContent = "No unused alternate remains for this part of the journey.";
    elements.storyboardAlternateList.append(empty);
  }
}

async function cancelStoryboardAlternate() {
  if (!await saveCurrentStoryboardNote()) return;
  storyboardAlternativeId = null;
  elements.storyboardAlternatePicker.hidden = true;
  renderStoryboardItem();
}

function showError(error) {
  setBusy(false);
  setView("error");
  elements.errorMessage.textContent = error instanceof Error ? error.message : String(error);
}

function renderProjectList() {
  const projects = state.projects || [];
  elements.projectListSection.hidden = projects.length === 0;
  elements.projectList.replaceChildren();
  for (const project of projects) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "project-row";
    button.dataset.projectId = project.id;
    const name = document.createElement("strong");
    name.textContent = project.name;
    const path = document.createElement("span");
    path.textContent = project.source_dir;
    button.append(name, path);
    button.addEventListener("click", () => openProject(project.id));
    elements.projectList.append(button);
  }
}

async function openProject(projectId) {
  setBusy(true, "Opening project…");
  try {
    state = await request("/api/projects/open", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
    });
    updateSummary(state.summary);
    await renderPreparation();
    setBusy(false);
  } catch (error) {
    showError(error);
  }
}

function preparationPercent(status) {
  if (!status?.total) return 0;
  return Math.max(0, Math.min(100, Math.round((Number(status.processed) / Number(status.total)) * 100)));
}

function displayPreparationStatus(status) {
  const percent = preparationPercent(status);
  const running = status.state === "running";
  const complete = status.state === "complete";
  const blocked = status.state === "blocked";
  const analyzed = Number(state.summary?.analyzed_count || 0);
  const totalClips = Number(state.summary?.media_count || 0);
  const resumable = analyzed > 0 || ["interrupted", "failed"].includes(status.state);
  const screeningComplete = Number(state.summary?.decisions.pending.count || 0) === 0 && totalClips > 0;
  const refinable = Number(state.refinement_summary?.total || 0) > 0;
  const refinementComplete = refinable && Number(state.refinement_summary?.reviewed || 0) === Number(state.refinement_summary?.total || 0);
  const shortStoryboard = state.storyboard_summary?.["120"] || {};
  const longerStoryboard = state.storyboard_summary?.["180"] || {};
  const shortStoryboardComplete = Number(shortStoryboard.total || 0) > 0 && Number(shortStoryboard.pending || 0) === 0;
  const hybridAvailable = shortStoryboardComplete && Number(longerStoryboard.total || 0) > 0;
  const hybrid = state.hybrid_summary || {};
  const hybridReviewed = Number(hybrid.total || 0) - Number(hybrid.pending || 0);
  elements.progressBar.style.width = `${percent}%`;
  elements.progressTrack.setAttribute("aria-valuenow", String(percent));
  elements.progressPercent.textContent = `${percent}%`;
  elements.progressCount.textContent = status.total ? `${status.processed || 0} of ${status.total} preparation tasks` : `${analyzed} of ${totalClips} clips analyzed`;
  elements.currentFile.textContent = status.current_file ? `Now processing: ${status.current_file}` : "";
  elements.preparationMessage.textContent = status.message || "Leave the Mac plugged in with this app open. It is safe to leave running overnight.";
  elements.preparationHeading.textContent = complete ? "Ready for review" : running ? (status.stage === "proxies" ? "Preparing the review queue" : "Finding sustained moments") : resumable ? "Ready to resume" : "Ready to prepare";
  elements.startPreparationButton.hidden = running || complete || blocked;
  elements.startPreparationButton.textContent = resumable ? "Resume overnight preparation" : "Start overnight preparation";
  elements.cancelPreparationButton.hidden = !running;
  elements.beginReviewButton.hidden = !complete || screeningComplete;
  elements.beginRefinementButton.hidden = !complete || !screeningComplete || !refinable;
  elements.beginRefinementButton.textContent = refinementButtonLabel();
  elements.beginStoryboardButton.hidden = !complete || !screeningComplete || !refinementComplete;
  elements.beginHybridButton.hidden = !complete || !screeningComplete || !refinementComplete || !hybridAvailable;
  elements.beginHybridButton.textContent = Number(hybrid.pending || 0) === 0 && Number(hybrid.total || 0) > 0
    ? "Review your hybrid choices"
    : hybridReviewed > 0
      ? `Continue hybrid choices · ${hybridReviewed} of ${hybrid.total}`
      : `Choose ${hybrid.total || 13} long-only shots for the hybrid`;
  document.querySelector('[data-step="prepare"]').classList.toggle("is-current", running);
  document.querySelector('[data-step="prepare"]').classList.toggle("is-complete", complete);
  if (running && !preparationPoll) {
    preparationPoll = setInterval(refreshPreparationStatus, 2000);
  }
  if (!running && preparationPoll) {
    clearInterval(preparationPoll);
    preparationPoll = null;
  }
}

async function refreshPreparationStatus() {
  if (!state.project || !desktopMode) return;
  try {
    const status = await request("/api/preparation/status", {
      method: "POST",
      body: JSON.stringify({ project_id: state.project.id }),
    });
    displayPreparationStatus(status);
    if (status.state === "complete") {
      const refreshed = await request("/api/state");
      state = refreshed;
      updateSummary(state.summary);
    }
  } catch (error) {
    displayPreparationStatus({ state: "failed", message: String(error) });
  }
}

async function renderPreparation() {
  setView("prepare");
  elements.prepareProjectLabel.textContent = state.project?.name || "Local project";
  elements.libraryPath.textContent = state.project?.source_dir || "";
  if (!desktopMode) {
    const screeningComplete = Number(state.summary?.decisions.pending.count || 0) === 0 && Number(state.summary?.media_count || 0) > 0;
    displayPreparationStatus(screeningComplete
      ? { state: "complete", processed: state.summary.media_count, total: state.summary.media_count, message: "Screening is complete. Your selected moments are ready to refine." }
      : { state: "idle", message: "Overnight preparation is available in the installed Mac app." });
    return;
  }
  await refreshPreparationStatus();
}

async function loadState() {
  setBusy(true);
  try {
    state = await request("/api/state");
    elements.sourceDir.value = state.project?.source_dir || state.default_source || "";
    updateSummary(state.summary);
    if (!state.project || !state.summary?.media_count) {
      renderProjectList();
      setView("setup");
      elements.scanButton.textContent = state.project ? "Scan footage" : "Create project and scan footage";
    } else {
      await renderPreparation();
    }
    setBusy(false);
  } catch (error) {
    showError(error);
  }
}

elements.projectForm.addEventListener("submit", async event => {
  event.preventDefault();
  const sourceDir = elements.sourceDir.value.trim();
  if (!sourceDir) return;
  elements.sourceDir.setAttribute("aria-invalid", "false");
  setBusy(true, "Inspecting 79 source files…");
  elements.formStatus.textContent = "Reading metadata only. Original footage will not be changed.";
  try {
    const created = await request("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name: elements.projectName.value.trim() || "Untitled journey", source_dir: sourceDir }),
    });
    state.project = created.project;
    const scanned = await request("/api/scan", {
      method: "POST",
      body: JSON.stringify({ project_id: state.project.id }),
    });
    updateSummary(scanned.summary);
    const refreshed = await request("/api/state");
    state = refreshed;
    updateSummary(state.summary);
    await renderPreparation();
    setBusy(false);
  } catch (error) {
    elements.formStatus.textContent = error.message;
    if (/folder|exist/i.test(error.message)) {
      elements.sourceDir.setAttribute("aria-invalid", "true");
      elements.sourceDir.focus();
    }
    setBusy(false);
  }
});

async function showProjects() {
  if (!elements.review.hidden && !await saveCurrentCandidateNote()) return;
  if (!elements.refine.hidden && !await saveCurrentRefinement(false)) return;
  if (!elements.storyboard.hidden && !await saveCurrentStoryboardNote()) return;
  if (preparationPoll) {
    clearInterval(preparationPoll);
    preparationPoll = null;
  }
  if (storyboardPreparationPoll) {
    clearInterval(storyboardPreparationPoll);
    storyboardPreparationPoll = null;
  }
  if (storyboardVideoUrl) {
    URL.revokeObjectURL(storyboardVideoUrl);
    storyboardVideoUrl = null;
  }
  renderProjectList();
  elements.sourceDir.value = "";
  elements.formStatus.textContent = "";
  setView("setup");
}

elements.projectsButton.addEventListener("click", showProjects);
elements.completeProjectsButton.addEventListener("click", showProjects);
elements.refineCompleteProjectsButton.addEventListener("click", showProjects);
elements.storyboardCompleteProjectsButton.addEventListener("click", showProjects);

elements.startPreparationButton.addEventListener("click", async () => {
  if (!state.project) return;
  elements.startPreparationButton.disabled = true;
  try {
    const status = await request("/api/preparation/start", {
      method: "POST",
      body: JSON.stringify({ project_id: state.project.id }),
    });
    displayPreparationStatus(status);
  } catch (error) {
    displayPreparationStatus({ state: "failed", message: error instanceof Error ? error.message : String(error) });
  } finally {
    elements.startPreparationButton.disabled = false;
  }
});

elements.cancelPreparationButton.addEventListener("click", async () => {
  await request("/api/preparation/cancel", { method: "POST", body: "{}" });
  elements.preparationMessage.textContent = "Pausing after the current safe checkpoint…";
});

elements.beginReviewButton.addEventListener("click", async () => {
  setBusy(true, "Opening the prepared review queue…");
  try {
    state = await request("/api/state");
    updateSummary(state.summary);
    renderCandidate(state.candidate);
    setBusy(false);
  } catch (error) {
    showError(error);
  }
});

elements.beginRefinementButton.addEventListener("click", () => openRefinement());
elements.refineSelectionsButton.addEventListener("click", () => openRefinement());
elements.reviewRefinementsButton.addEventListener("click", () => openRefinement(true));
elements.beginStoryboardButton.addEventListener("click", openStoryboardPreparation);
elements.prepareStoryboardButton.addEventListener("click", openStoryboardPreparation);
elements.beginHybridButton.addEventListener("click", () => openHybridReview());

elements.startStoryboardPreparationButton.addEventListener("click", async () => {
  if (!state.project) return;
  elements.startStoryboardPreparationButton.disabled = true;
  try {
    const status = await request("/api/storyboard/preparation/start", {
      method: "POST",
      body: JSON.stringify({ project_id: state.project.id }),
    });
    displayStoryboardPreparationStatus(status);
  } catch (error) {
    displayStoryboardPreparationStatus({ state: "failed", message: error instanceof Error ? error.message : String(error) });
  } finally {
    elements.startStoryboardPreparationButton.disabled = false;
  }
});

elements.cancelStoryboardPreparationButton.addEventListener("click", async () => {
  await request("/api/storyboard/preparation/cancel", { method: "POST", body: "{}" });
  elements.storyboardPreparationMessage.textContent = "Pausing after the current safe checkpoint…";
});

elements.reviewStoryboardButton.addEventListener("click", () => openStoryboardReview());
elements.reviewStoryboardAgainButton.addEventListener("click", () => {
  if (storyboardMode === "hybrid") openHybridReview(true);
  else openStoryboardReview(true);
});
elements.removeStoryboardItemButton.addEventListener("click", () => {
  if (storyboardMode === "hybrid") reviewCurrentStoryboard("long_only");
  else reviewCurrentStoryboard("remove");
});
elements.chooseStoryboardAlternateButton.addEventListener("click", () => {
  if (storyboardMode === "hybrid") reviewCurrentStoryboard("unsure");
  else renderStoryboardAlternatives();
});
elements.cancelStoryboardAlternateButton.addEventListener("click", cancelStoryboardAlternate);
elements.approveStoryboardItemButton.addEventListener("click", () => {
  if (storyboardMode === "hybrid") reviewCurrentStoryboard("add");
  else if (storyboardAlternativeId !== null) reviewCurrentStoryboard("replace", storyboardAlternativeId);
  else reviewCurrentStoryboard("approve");
});
elements.previousStoryboardButton.addEventListener("click", async () => {
  if (storyboardIndex <= 0) return;
  if (!await saveCurrentStoryboardNote()) return;
  storyboardIndex -= 1;
  renderStoryboardItem();
});
elements.nextStoryboardButton.addEventListener("click", async () => {
  if (storyboardIndex >= storyboardItems.length - 1) return;
  if (!await saveCurrentStoryboardNote()) return;
  storyboardIndex += 1;
  renderStoryboardItem();
});

elements.storyboardNote.addEventListener("input", () => {
  storyboardNoteDirty = true;
  storyboardNoteRevision += 1;
  setStoryboardNoteSaveState("Saving locally…");
  if (storyboardNoteSaveTimer) clearTimeout(storyboardNoteSaveTimer);
  storyboardNoteSaveTimer = setTimeout(saveCurrentStoryboardNote, 700);
});

elements.storyboardNote.addEventListener("blur", () => {
  if (storyboardNoteDirty) saveCurrentStoryboardNote();
});

elements.reviewNote.addEventListener("input", () => {
  reviewNoteDirty = true;
  reviewNoteRevision += 1;
  setReviewNoteSaveState("Saving locally…");
  if (reviewNoteSaveTimer) clearTimeout(reviewNoteSaveTimer);
  reviewNoteSaveTimer = setTimeout(saveCurrentCandidateNote, 700);
});

elements.reviewNote.addEventListener("blur", () => {
  if (reviewNoteDirty) saveCurrentCandidateNote();
});

elements.video.addEventListener("play", () => {
  if (!elements.sourceVideo.paused) elements.sourceVideo.pause();
});

elements.sourceVideo.addEventListener("play", () => {
  if (!elements.video.paused) elements.video.pause();
});

elements.sourceVideo.addEventListener("error", () => {
  elements.sourceFrameCaption.textContent = "Full original unavailable in this player";
});

elements.jumpToSelectionButton.addEventListener("click", () => {
  const candidate = state.candidate;
  if (!candidate) return;
  const seekAndPlay = () => {
    elements.sourceVideo.currentTime = Math.min(
      Number(candidate.source_duration),
      Number(candidate.start_seconds),
    );
    elements.sourceVideo.play().catch(() => undefined);
    elements.sourceVideo.focus();
  };
  if (elements.sourceVideo.readyState >= 1) {
    seekAndPlay();
  } else {
    elements.sourceVideo.addEventListener("loadedmetadata", seekAndPlay, { once: true });
  }
});

elements.refinementNote.addEventListener("input", () => {
  refinementDirty = true;
  refinementRevision += 1;
  setRefinementSaveState("Saving locally…");
  if (refinementSaveTimer) clearTimeout(refinementSaveTimer);
  refinementSaveTimer = setTimeout(() => saveCurrentRefinement(false), 700);
});

elements.refinementNote.addEventListener("blur", () => {
  if (refinementDirty) saveCurrentRefinement(false);
});

elements.attachMomentButton.addEventListener("click", async () => {
  const candidate = currentRefinement();
  if (!candidate) return;
  noteAnchorSeconds = Math.min(
    Number(candidate.source_duration),
    Number(candidate.preview_start_seconds) + Number(elements.refinementVideo.currentTime || 0),
  );
  refinementDirty = true;
  refinementRevision += 1;
  updateNoteAnchorLabel();
  await saveCurrentRefinement(false);
});

elements.previousRefinementButton.addEventListener("click", async () => {
  if (refinementIndex <= 0) return;
  if (!await saveCurrentRefinement(false)) return;
  refinementIndex -= 1;
  renderRefinementCandidate();
});

elements.nextRefinementButton.addEventListener("click", async () => {
  if (!await saveCurrentRefinement(true)) return;
  if (refinementIndex >= refinementCandidates.length - 1) {
    setView("refineComplete");
    const summary = state.refinement_summary || { reviewed: 0, total: 0, noted: 0 };
    elements.refineCompleteSummary.textContent = `You revisited ${summary.reviewed} of ${summary.total} selected moments and saved notes on ${summary.noted}.`;
    return;
  }
  refinementIndex += 1;
  renderRefinementCandidate();
});

elements.roleOptions.addEventListener("click", event => {
  const button = event.target.closest("button[data-role]");
  if (button) setRole(button.dataset.role);
});

async function decide(decision) {
  if (busy || !state.candidate) return;
  const decidedCandidate = state.candidate;
  setBusy(true, reviewNoteDirty ? "Saving comment and recording decision…" : "Recording decision…");
  try {
    if (!await saveCurrentCandidateNote()) {
      setBusy(false);
      return;
    }
    const result = await request(`/api/candidates/${decidedCandidate.id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, story_role: selectedRole }),
    });
    lastDecision = { ...decidedCandidate, decision, story_role: selectedRole };
    elements.undoButton.hidden = false;
    updateSummary(result.summary);
    state.refinement_summary = result.refinement_summary;
    renderCandidate(result.next_candidate);
    setBusy(false);
  } catch (error) {
    showError(error);
  }
}

document.querySelectorAll("[data-decision]").forEach(button => {
  button.addEventListener("click", () => decide(button.dataset.decision));
});

elements.undoButton.addEventListener("click", async () => {
  if (!lastDecision || busy) return;
  setBusy(true, "Restoring candidate…");
  try {
    if (!await saveCurrentCandidateNote()) {
      setBusy(false);
      return;
    }
    const result = await request(`/api/candidates/${lastDecision.id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision: "pending", story_role: null }),
    });
    updateSummary(result.summary);
    state.refinement_summary = result.refinement_summary;
    renderCandidate(result.next_candidate);
    lastDecision = null;
    elements.undoButton.hidden = true;
    setBusy(false);
  } catch (error) {
    showError(error);
  }
});

document.addEventListener("keydown", event => {
  const target = event.target;
  const editing = ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName) || target.isContentEditable;
  if (editing || busy || elements.review.hidden) return;
  if (event.key === "1") decide("skip");
  if (event.key === "2") decide("maybe");
  if (event.key === "3") decide("keep");
  if (event.key === " ") {
    event.preventDefault();
    if (elements.video.paused) elements.video.play(); else elements.video.pause();
  }
});

elements.retryButton.addEventListener("click", loadState);

function startInitialLoad() {
  if (initialLoadStarted) return;
  initialLoadStarted = true;
  loadState();
}

if (desktopExpected) {
  const bridgePoll = setInterval(() => {
    activateDesktop();
    if (desktopMode) clearInterval(bridgePoll);
  }, 50);
} else {
  startInitialLoad();
}
