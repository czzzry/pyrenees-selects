"use strict";

const elements = {
  setup: document.getElementById("setupView"),
  prepare: document.getElementById("prepareView"),
  review: document.getElementById("reviewView"),
  complete: document.getElementById("completeView"),
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
  cancelPreparationButton: document.getElementById("cancelPreparationButton"),
  video: document.getElementById("candidateVideo"),
  contextOne: document.getElementById("contextOne"),
  contextTwo: document.getElementById("contextTwo"),
  heroFrameNumber: document.getElementById("heroFrameNumber"),
  candidateEyebrow: document.getElementById("candidateEyebrow"),
  candidateTitle: document.getElementById("candidateTitle"),
  candidateReason: document.getElementById("candidateReason"),
  sourceName: document.getElementById("sourceName"),
  sourceRange: document.getElementById("sourceRange"),
  sourceFormat: document.getElementById("sourceFormat"),
  roleOptions: document.getElementById("roleOptions"),
  sessionSummary: document.getElementById("sessionSummary"),
  undoButton: document.getElementById("undoButton"),
  completeSummary: document.getElementById("completeSummary"),
  errorMessage: document.getElementById("errorMessage"),
  retryButton: document.getElementById("retryButton"),
};

let state = { project: null, summary: null, candidate: null };
let selectedRole = null;
let lastDecision = null;
let busy = false;
let desktopMode = false;
let currentVideoUrl = null;
let initialLoadStarted = false;
let preparationPoll = null;
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
  for (const key of ["setup", "prepare", "review", "complete", "error"]) {
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
    const decisionMatch = url.match(/^\/api\/candidates\/(\d+)\/decision$/);
    if (decisionMatch) {
      return window.pywebview.api.decide(Number(decisionMatch[1]), payload.decision, payload.story_role || null);
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
  state.candidate = candidate;
  if (!candidate) {
    setView("complete");
    const kept = state.summary?.decisions.keep.count || 0;
    const maybe = state.summary?.decisions.maybe.count || 0;
    elements.completeSummary.textContent = `You kept ${kept} sequences and left ${maybe} possibilities for the assembly pass.`;
    return;
  }
  setView("review");
  selectedRole = candidate.story_role || null;
  renderRole();
  elements.candidateEyebrow.textContent = `${candidate.captured_label} · ${candidate.chapter} · ${Math.round(candidate.duration)} seconds`;
  elements.candidateTitle.textContent = candidate.title;
  elements.candidateReason.textContent = candidate.reason;
  elements.sourceName.textContent = candidate.filename;
  elements.sourceRange.textContent = `${formatClock(candidate.start_seconds)}–${formatClock(candidate.start_seconds + candidate.duration)} + ${candidate.handle_seconds}s handles`;
  elements.sourceFormat.textContent = `${candidate.width}×${candidate.height} · ${Number(candidate.fps).toFixed(2)} fps · ${candidate.codec.toUpperCase()}`;
  elements.heroFrameNumber.textContent = `Candidate ${String(candidate.id).padStart(3, "0")} · review proxy 360p`;
  if (desktopMode) {
    loadDesktopAssets(candidate.id);
  } else {
    elements.video.pause();
    elements.video.src = candidate.video_url;
    elements.video.load();
    elements.contextOne.src = candidate.context_urls[0];
    elements.contextTwo.src = candidate.context_urls[1];
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
    elements.contextOne.src = assets.context_data_urls[0];
    elements.contextTwo.src = assets.context_data_urls[1];
    setBusy(false);
  } catch (error) {
    showError(error);
  }
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
  elements.beginReviewButton.hidden = !complete;
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
    displayPreparationStatus({ state: "idle", message: "Overnight preparation is available in the installed Mac app." });
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

function showProjects() {
  if (preparationPoll) {
    clearInterval(preparationPoll);
    preparationPoll = null;
  }
  renderProjectList();
  elements.sourceDir.value = "";
  elements.formStatus.textContent = "";
  setView("setup");
}

elements.projectsButton.addEventListener("click", showProjects);
elements.completeProjectsButton.addEventListener("click", showProjects);

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

elements.roleOptions.addEventListener("click", event => {
  const button = event.target.closest("button[data-role]");
  if (button) setRole(button.dataset.role);
});

async function decide(decision) {
  if (busy || !state.candidate) return;
  const decidedCandidate = state.candidate;
  setBusy(true, "Recording decision…");
  try {
    const result = await request(`/api/candidates/${decidedCandidate.id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, story_role: selectedRole }),
    });
    lastDecision = { ...decidedCandidate, decision, story_role: selectedRole };
    elements.undoButton.hidden = false;
    updateSummary(result.summary);
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
    const result = await request(`/api/candidates/${lastDecision.id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision: "pending", story_role: null }),
    });
    updateSummary(result.summary);
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
