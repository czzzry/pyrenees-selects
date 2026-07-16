"use strict";

const elements = {
  setup: document.getElementById("setupView"),
  review: document.getElementById("reviewView"),
  complete: document.getElementById("completeView"),
  error: document.getElementById("errorView"),
  loading: document.getElementById("loading"),
  loadingMessage: document.getElementById("loadingMessage"),
  main: document.getElementById("main"),
  reviewCount: document.getElementById("reviewCount"),
  projectForm: document.getElementById("projectForm"),
  sourceDir: document.getElementById("sourceDir"),
  chooseFolderButton: document.getElementById("chooseFolderButton"),
  scanButton: document.getElementById("scanButton"),
  formStatus: document.getElementById("formStatus"),
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
  for (const key of ["setup", "review", "complete", "error"]) {
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
    if (url === "/api/scan") return window.pywebview.api.scan(payload.project_id);
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

async function loadState() {
  setBusy(true);
  try {
    state = await request("/api/state");
    elements.sourceDir.value = state.project?.source_dir || state.default_source || "";
    updateSummary(state.summary);
    if (!state.project || !state.summary?.media_count) {
      setView("setup");
      elements.scanButton.textContent = state.project ? "Scan footage" : "Create project and scan footage";
    } else {
      renderCandidate(state.candidate);
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
      body: JSON.stringify({ name: "Pyrenees 2024", source_dir: sourceDir }),
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
    renderCandidate(state.candidate);
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
