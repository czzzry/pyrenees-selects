const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = { projects: [], project: null, sources: [], selections: [], sequences: [], proposals: [], review_proxies: null, latest_run: null, source: null, filter: "all", search: "", sequenceIds: [], sequence: null, playingRange: false, editingSelection: null, mediaMode: "original", proxyTimer: null, runTimer: null, candidate: null, candidateFilter: "all", candidateMediaMode: "sample" };

async function request(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { message = (await response.json()).error || message; } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}
function seconds(value) { const n = Number(value || 0); return `${Math.floor(n / 60)}:${String(Math.round(n % 60)).padStart(2, "0")}`; }
function exact(value) { return Number(value || 0).toFixed(2); }
function bytes(value) { const n = Number(value || 0); if (n < 1024 ** 2) return `${Math.max(0, Math.round(n / 1024))} KB`; if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`; return `${(n / 1024 ** 3).toFixed(1)} GB`; }
function setStatus(element, message, error = false) { element.textContent = message; element.classList.toggle("is-error", error); }
function toast(message) { const node = $("#toast"); node.textContent = message; node.hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => { node.hidden = true; }, 3000); }

async function loadProjects(preferred) {
  state.projects = (await request("/api/projects")).projects;
  if (!state.projects.length) { showWelcome(); return; }
  const id = preferred || localStorage.getItem("selects-project") || state.projects[0].id;
  await openProject(state.projects.some(project => project.id === id) ? id : state.projects[0].id);
}
function showWelcome() {
  if (state.proxyTimer) clearTimeout(state.proxyTimer);
  if (state.runTimer) clearTimeout(state.runTimer);
  $("#welcome").hidden = false; $$(".readiness, .workspace, .assemble, .assistant, .product-stage, .candidate-workspace, .tabs, .project-switcher").forEach(node => node.hidden = true);
}
async function openProject(id, options = {}) {
  const payload = await request(`/api/projects/${id}`);
  Object.assign(state, payload, { source: null, sequenceIds: [] });
  state.sequence = null;
  if (state.sequences.length) {
    state.sequence = await request(`/api/sequences/${state.sequences[0].id}`);
    state.sequenceIds = state.sequence.items.map(item => item.id);
  }
  localStorage.setItem("selects-project", id);
  $("#welcome").hidden = true; $(".tabs").hidden = false; $(".project-switcher").hidden = false;
  $("#projectSelect").innerHTML = state.projects.map(project => `<option value="${project.id}" ${project.id === id ? "selected" : ""}>${escapeHtml(project.name)}</option>`).join("");
  populateProjectSettings(); renderReview(); renderAssembly(); renderAssistant(); renderProxyBanner();
  if (!state.latest_run && state.sources.length && state.project.target_duration_seconds) {
    try { state.latest_run = await request(`/api/projects/${id}/overnight-plan`, { method: "POST", body: JSON.stringify({ prevent_sleep: true }) }); }
    catch (error) { setStatus($("#projectStatus"), error.message, true); }
  }
  if (options.view === "candidates" && state.latest_run?.candidates?.length) switchView("candidates");
  else if (state.latest_run?.state === "planned") switchView("prepare");
  else if (state.latest_run && !["completed", "completed_with_warnings"].includes(state.latest_run.state)) switchView("prepare");
  else if (state.latest_run?.candidates?.length) switchView("candidates");
  else switchView("prepare");
  if (state.review_proxies?.state === "running") startProxyPolling();
  if (["running", "pausing", "cancelling"].includes(state.latest_run?.state)) startRunPolling();
}
function switchView(view) {
  $("#readinessView").hidden = true; $(".tabs").hidden = false;
  $("#planView").hidden = true; $("#runView").hidden = true; $("#candidateView").hidden = view !== "candidates";
  $("#reviewView").hidden = view !== "sources"; $("#assembleView").hidden = view !== "assemble"; $("#assistantView").hidden = view !== "assistant";
  if (view === "prepare") {
    if (state.latest_run && state.latest_run.state !== "planned") { $("#runView").hidden = false; renderRun(); }
    else { $("#planView").hidden = false; renderPlan(); }
  }
  $$(".tabs button").forEach(button => button.setAttribute("aria-current", button.dataset.view === view ? "page" : "false"));
  if (view === "candidates") renderCandidates(); if (view === "sources") renderReview();
  if (view === "assemble") renderAssembly(); if (view === "assistant") renderAssistant();
}
function renderReadiness() {
  $("#welcome").hidden = true; $(".tabs").hidden = true; $$(".workspace, .assemble, .assistant").forEach(node => node.hidden = true); $("#readinessView").hidden = false;
  $("#readinessTitle").textContent = `${state.summary.source_count} clip${state.summary.source_count === 1 ? "" : "s"}. Ready to screen without surprises.`;
  $("#readinessSize").textContent = `${seconds(state.summary.total_seconds)} · ${bytes(state.summary.total_bytes)}`;
  $("#readinessReady").textContent = `${state.summary.ready_count} clips`;
  $("#readinessPortrait").textContent = `${state.summary.portrait_count} clips`;
  $("#readinessSilent").textContent = `${state.summary.silent_count} clips`;
  $("#readinessAttention").textContent = `${state.summary.attention_count} clips`;
  $("#proxyEstimate").textContent = bytes(state.review_proxies?.estimated_bytes);
  setStatus($("#readinessStatus"), state.summary.attention_count ? "Clips that need attention remain visible and will not stop the rest." : "All readable clips are ready.");
}
function applyProxyStatus(status) {
  const currentHadReviewCopy = Boolean(state.source?.review_media_url);
  state.review_proxies = status;
  const ready = new Set(status.ready_source_ids || []);
  state.sources.forEach(source => { source.review_media_url = ready.has(source.id) ? `/api/sources/${source.id}/review-media` : null; });
  if (state.source) state.source = state.sources.find(source => source.id === state.source.id) || state.source;
  if (state.source?.review_media_url && !currentHadReviewCopy && $("#sourceVideo").paused) setSourceMedia("review", $("#sourceVideo").currentTime);
  renderProxyBanner(); updateMediaModeButton();
}
function renderProxyBanner() {
  const proxy = state.review_proxies; const banner = $("#proxyBanner");
  if (!proxy || (!proxy.ready && proxy.state === "idle")) { banner.hidden = true; return; }
  banner.hidden = false; $("#proxyProgress").max = Math.max(1, proxy.total); $("#proxyProgress").value = proxy.ready;
  if (proxy.state === "running") { $("#proxyBannerTitle").textContent = `Preparing smoother review copies · ${proxy.ready} of ${proxy.total}`; $("#proxyBannerDetail").textContent = proxy.running_filename ? `Now preparing ${proxy.running_filename}. You can keep reviewing.` : "Starting the background queue…"; }
  else if (proxy.state === "ready") { $("#proxyBannerTitle").textContent = `All ${proxy.ready} review copies are ready`; $("#proxyBannerDetail").textContent = "Selects uses them by default; the full original remains one click away."; }
  else { $("#proxyBannerTitle").textContent = `${proxy.ready} review copies ready · ${proxy.failed} need attention`; $("#proxyBannerDetail").textContent = "Retry preparation to continue past failed files."; }
}
function startProxyPolling() {
  if (state.proxyTimer) clearTimeout(state.proxyTimer);
  const poll = async () => {
    try { const status = await request(`/api/projects/${state.project.id}/review-proxies`); applyProxyStatus(status); if (status.state === "running") state.proxyTimer = setTimeout(poll, 1200); else if (status.state === "ready") toast("Smooth review copies are ready"); }
    catch (error) { toast(error.message); }
  };
  state.proxyTimer = setTimeout(poll, 600);
}
async function prepareReviewProxies() {
  try { $("#prepareProxiesButton").disabled = true; setStatus($("#readinessStatus"), "Starting the resumable background queue…"); const status = await request(`/api/projects/${state.project.id}/review-proxies`, { method: "POST", body: "{}" }); applyProxyStatus(status); localStorage.setItem(`selects-readiness-${state.project.id}`, "done"); switchView("sources"); startProxyPolling(); }
  catch (error) { setStatus($("#readinessStatus"), error.message, true); }
  finally { $("#prepareProxiesButton").disabled = false; }
}
function reviewOriginals() { localStorage.setItem(`selects-readiness-${state.project.id}`, "done"); switchView("sources"); }
function escapeHtml(value) { const div = document.createElement("div"); div.textContent = String(value ?? ""); return div.innerHTML; }

function renderPlan() {
  const run = state.latest_run;
  const empty = Number(state.summary?.ready_count || 0) === 0;
  $("#planEmptyState").hidden = !empty;
  $("#planView > .metric-strip").hidden = empty;
  $("#planView > .plan-grid").hidden = empty;
  if (empty) return;
  if (!run) {
    setStatus($("#planStatus"), state.sources.length ? "Choose a target length in project settings to calculate the overnight plan." : "Add a readable footage folder first.", true);
    $("#startOvernightButton").disabled = true;
    return;
  }
  const plan = run.plan; const disk = plan.disk;
  $("#planFootage").textContent = seconds(plan.readable_source_duration);
  $("#planCandidateTime").textContent = seconds(plan.candidate_duration_target);
  $("#planCandidateCount").textContent = plan.minimum_candidate_count === plan.maximum_candidate_count ? String(plan.minimum_candidate_count) : `${plan.minimum_candidate_count}–${plan.maximum_candidate_count}`;
  $("#planRuntime").textContent = plan.runtime?.seconds ? seconds(plan.runtime.seconds) : "Estimating…";
  $("#planReady").textContent = `${run.source_snapshot.length} clips`;
  $("#planDuplicates").textContent = `${plan.duplicate_source_ids.length} clips`;
  const inventory = plan.inventory || {};
  $("#planPortrait").textContent = `${inventory.portrait || 0} clips`;
  $("#planSilent").textContent = `${inventory.silent || 0} clips`;
  $("#planVfr").textContent = `${inventory.vfr || 0} clips`;
  $("#planShort").textContent = `${inventory.very_short || 0} clips`;
  $("#planAttention").textContent = `${(inventory.broken || 0) + (inventory.offline || 0)} clips`;
  $("#planUnsupported").textContent = `${inventory.unsupported || 0} files`;
  $("#planArtifacts").textContent = bytes(disk.estimated_artifact_bytes);
  $("#planReserve").textContent = bytes(disk.safety_reserve_bytes);
  $("#planAvailable").textContent = bytes(disk.available_bytes);
  $("#preventSleep").checked = Boolean(run.prevent_sleep);
  $("#planDiskWarning").hidden = disk.can_start;
  $("#planDiskDetail").textContent = disk.can_start ? "" : `${bytes(disk.shortfall_bytes)} more is required, including the safety reserve.`;
  $("#startOvernightButton").disabled = !disk.can_start || run.stale;
  setStatus($("#planStatus"), run.stale ? "This plan is stale because footage or settings changed. Create a fresh plan." : `Calculated from ${run.source_snapshot.length} unique readable sources.`, run.stale);
}

async function rebuildPlan(cachePath = "") {
  try {
    setStatus($("#planStatus"), "Recalculating from the current folder and project brief…");
    state.latest_run = await request(`/api/projects/${state.project.id}/overnight-plan`, { method: "POST", body: JSON.stringify({ cache_path: cachePath || undefined, prevent_sleep: $("#preventSleep").checked }) });
    renderPlan();
  } catch (error) { setStatus($("#planStatus"), error.message, true); }
}

async function startOvernight() {
  if (!state.latest_run) return;
  try {
    $("#startOvernightButton").disabled = true;
    setStatus($("#planStatus"), "Starting the checkpointed queue…");
    state.latest_run = await request(`/api/runs/${state.latest_run.id}/start`, { method: "POST", body: "{}" });
    switchView("prepare"); startRunPolling();
  } catch (error) { setStatus($("#planStatus"), error.message, true); $("#startOvernightButton").disabled = false; }
}

function renderRun() {
  const run = state.latest_run; if (!run) return;
  const activeSource = run.sources.find(item => ["proxying", "analyzing", "rendering"].includes(item.state));
  const percent = Math.round(Number(run.progress_fraction || 0) * 100);
  const labels = { planned: "Ready", running: "Running", pausing: "Pausing", paused: "Paused safely", cancelling: "Cancelling", cancelled: "Cancelled", completed: "Complete", completed_with_warnings: "Complete with warnings", failed: "Needs attention", stale: "Plan changed" };
  $("#runState").textContent = labels[run.state] || run.state;
  $("#runState").classList.toggle("is-warning", ["failed", "completed_with_warnings", "stale"].includes(run.state));
  $("#runStageLabel").textContent = activeSource ? activeSource.stage : labels[run.state] || run.state;
  $("#runFilename").textContent = activeSource?.filename || (run.state === "completed" ? "Every readable source is prepared" : "Stopped at a saved checkpoint");
  $("#runPercent").textContent = `${percent}%`; $("#runProgress").value = Number(run.progress_fraction || 0);
  $("#runCompleted").textContent = `${run.progress_processed} of ${run.progress_total} tasks`;
  $("#runElapsed").textContent = `Elapsed ${seconds(run.elapsed_seconds)}`;
  $("#runEta").textContent = run.eta_seconds == null ? "Estimating…" : `About ${seconds(run.eta_seconds)} left · measured here`;
  $("#pauseRunButton").hidden = run.state !== "running"; $("#resumeRunButton").hidden = run.state !== "paused";
  $("#cancelRunButton").hidden = ["cancelled", "completed", "completed_with_warnings", "failed"].includes(run.state);
  $("#reviewReadyButton").disabled = !run.candidates.length;
  $("#runCacheRecovery").hidden = !(run.state === "paused" && /space|disk|cache/i.test(run.warning || ""));
  $("#sleepGuarantee").textContent = run.prevent_sleep ? "This Mac stays awake only while the run is active" : "Sleep prevention is off for this run";
  const failures = run.sources.filter(item => ["failed", "skipped"].includes(item.state));
  $("#runFailures").innerHTML = failures.map(item => `<article class="failure-card"><strong>${escapeHtml(item.filename)}</strong><p>${escapeHtml(item.error || "Skipped from this run")}</p><div class="button-row"><button class="quiet" data-retry-source="${item.source_id}" type="button">Retry</button><button class="quiet" data-skip-source="${item.source_id}" type="button">Skip</button></div></article>`).join("");
  $$('[data-retry-source]').forEach(button => button.addEventListener("click", () => retryRunSource(button.dataset.retrySource)));
  $$('[data-skip-source]').forEach(button => button.addEventListener("click", () => skipRunSource(button.dataset.skipSource)));
  setStatus($("#runStatus"), run.error || run.warning || (run.candidates.length ? `${run.candidates.length} playable proposal${run.candidates.length === 1 ? "" : "s"} ready now.` : "The first playable proposal will appear after one source completes."), Boolean(run.error));
}

function startRunPolling() {
  if (state.runTimer) clearTimeout(state.runTimer);
  const poll = async () => {
    try {
      state.latest_run = await request(`/api/runs/${state.latest_run.id}`); renderRun();
      if (!$("#candidateView").hidden) renderCandidates(true);
      if (["running", "pausing", "cancelling"].includes(state.latest_run.state)) state.runTimer = setTimeout(poll, 1000);
      else if (["completed", "completed_with_warnings"].includes(state.latest_run.state)) toast("Overnight proposals are ready to review");
    } catch (error) { setStatus($("#runStatus"), error.message, true); }
  };
  state.runTimer = setTimeout(poll, 500);
}

async function runAction(action) {
  try { state.latest_run = await request(`/api/runs/${state.latest_run.id}/${action}`, { method: "POST", body: "{}" }); renderRun(); if (action === "start") startRunPolling(); }
  catch (error) { setStatus($("#runStatus"), error.message, true); }
}
async function retryRunSource(sourceId) { try { state.latest_run = await request(`/api/runs/${state.latest_run.id}/retry`, { method: "POST", body: JSON.stringify({ source_ids: [sourceId] }) }); renderRun(); startRunPolling(); } catch (error) { setStatus($("#runStatus"), error.message, true); } }
async function skipRunSource(sourceId) { try { state.latest_run = await request(`/api/runs/${state.latest_run.id}/skip`, { method: "POST", body: JSON.stringify({ source_ids: [sourceId] }) }); renderRun(); } catch (error) { setStatus($("#runStatus"), error.message, true); } }
async function moveRunCache() {
  const input = $("#runCachePath");
  if (window.pywebview?.api?.choose_folder && !input.value) { const chosen = await window.pywebview.api.choose_folder(""); if (chosen) input.value = chosen; }
  if (!input.value) { input.focus(); toast("Choose or paste a new cache folder."); return; }
  try { setStatus($("#runStatus"), "Copying completed samples to the new cache…"); state.latest_run = await request(`/api/runs/${state.latest_run.id}/cache`, { method: "POST", body: JSON.stringify({ path: input.value }) }); renderRun(); }
  catch (error) { setStatus($("#runStatus"), error.message, true); }
}

function renderCandidates(preserveEditor = false) {
  const run = state.latest_run; if (!run) return;
  const all = run.candidates.filter(item => item.sample_ready);
  const visible = all.filter(item => state.candidateFilter === "all" || item.review_state === state.candidateFilter);
  const reviewed = all.filter(item => item.review_state !== "unreviewed").length;
  const remaining = run.sources.filter(item => !["completed", "failed", "skipped", "cancelled"].includes(item.state)).length;
  $("#candidateSummary").textContent = `${reviewed} of ${all.length} ready proposals reviewed${remaining ? ` · ${remaining} source${remaining === 1 ? "" : "s"} still preparing` : ""} · ranking is only a suggestion`;
  const currentId = state.candidate?.id;
  const freshCurrent = currentId ? all.find(item => item.id === currentId) : null;
  if (freshCurrent) state.candidate = freshCurrent;
  $("#candidateList").innerHTML = visible.map(item => `<button class="candidate-card ${state.candidate?.id === item.id ? "is-current" : ""}" data-candidate="${item.id}" type="button"><span class="rank">${String(item.rank || "—").padStart(2, "0")}</span><span><strong>${escapeHtml(item.filename)}</strong><small>${exact(item.in_seconds)}–${exact(item.out_seconds)} · ${exact(item.duration)} s</small></span><span class="review-pill ${item.review_state}">${item.review_state}</span></button>`).join("") || `<p class="status source-limit">No proposals match this filter yet.</p>`;
  $$('[data-candidate]').forEach(button => button.addEventListener("click", () => chooseCandidate(button.dataset.candidate)));
  if (!state.candidate || !all.some(item => item.id === state.candidate.id)) state.candidate = visible[0] || all[0] || null;
  if (state.candidate && !(preserveEditor && freshCurrent)) showCandidate(state.candidate.id);
  else if (!state.candidate) clearCandidate();
}

function clearCandidate() {
  $("#candidateTitle").textContent = "No playable proposals yet"; $("#candidateFacts").textContent = "You can review full sources while preparation continues.";
  $("#candidateVideo").removeAttribute("src"); $("#candidateVideo").load(); $("#saveCandidateButton").disabled = true;
}
function chooseCandidate(id) { const candidate = state.latest_run.candidates.find(item => item.id === id); if (!candidate) return; state.candidate = candidate; state.candidateMediaMode = "sample"; renderCandidates(); }
function showCandidate(id) {
  const candidate = state.latest_run.candidates.find(item => item.id === id); if (!candidate) return;
  state.candidate = candidate; $("#saveCandidateButton").disabled = false;
  $("#candidateTitle").textContent = candidate.filename;
  $("#candidateFacts").textContent = `${exact(candidate.in_seconds)}–${exact(candidate.out_seconds)} · ${candidate.width || "?"}×${candidate.height || "?"} · source time`;
  $("#candidateIn").value = exact(candidate.in_seconds); $("#candidateOut").value = exact(candidate.out_seconds);
  $("#candidateIn").max = candidate.source_duration; $("#candidateOut").max = candidate.source_duration;
  $("#candidateComment").value = candidate.comment || ""; $("#candidateRole").value = candidate.story_role || ""; $("#candidateAudio").value = candidate.audio_intent || "undecided";
  const decision = candidate.review_state === "kept" ? "keep" : candidate.review_state === "skipped" ? "skip" : candidate.review_state === "maybe" ? "maybe" : "maybe";
  const radio = $(`input[name="candidateDecision"][value="${decision}"]`); if (radio) radio.checked = true;
  $("#candidateRationale").textContent = candidate.rationale;
  setCandidateMedia(state.candidateMediaMode);
  updateCandidateRange();
}
function setCandidateMedia(mode) {
  const candidate = state.candidate; if (!candidate) return; const video = $("#candidateVideo");
  state.candidateMediaMode = mode === "source" ? "source" : "sample";
  video.src = state.candidateMediaMode === "source" ? `/api/runs/${state.latest_run.id}/sources/${candidate.source_id}/media` : `/api/candidates/${candidate.id}/media`;
  video.load();
  if (state.candidateMediaMode === "source") video.addEventListener("loadedmetadata", () => { video.currentTime = Number($("#candidateIn").value); }, { once: true });
  $("#candidateMediaMode").textContent = state.candidateMediaMode === "source" ? "Back to proposed sample" : "Open full source";
  const generatedIn = Number(candidate.generated_in_us) / 1e6; const generatedOut = Number(candidate.generated_out_us) / 1e6;
  $("#candidateScrubber").min = state.candidateMediaMode === "source" ? 0 : generatedIn;
  $("#candidateScrubber").max = state.candidateMediaMode === "source" ? candidate.source_duration : generatedOut;
  $("#candidateScrubber").value = state.candidateMediaMode === "source" ? candidate.in_seconds : generatedIn;
}
function updateCandidateRange() { const start = Number($("#candidateIn").value); const end = Number($("#candidateOut").value); $("#candidateRangeLabel").textContent = `${exact(Math.max(0, end - start))} seconds selected`; }
async function saveCandidateDecision() {
  if (!state.candidate) return;
  const selected = $('input[name="candidateDecision"]:checked');
  const body = { decision: selected?.value || "maybe", in_us: Math.round(Number($("#candidateIn").value) * 1e6), out_us: Math.round(Number($("#candidateOut").value) * 1e6), comment: $("#candidateComment").value, story_role: $("#candidateRole").value || null, audio_intent: $("#candidateAudio").value };
  try {
    setStatus($("#candidateStatus"), "Saving your exact range and comment…");
    const saved = await request(`/api/candidates/${state.candidate.id}`, { method: "PATCH", body: JSON.stringify(body) });
    const index = state.latest_run.candidates.findIndex(item => item.id === saved.id); state.latest_run.candidates[index] = saved; state.candidate = saved;
    const payload = await request(`/api/projects/${state.project.id}`); state.selections = payload.selections; state.sequences = payload.sequences;
    renderCandidates(); renderAssembly(); setStatus($("#candidateStatus"), "Saved. This decision and comment will survive regeneration."); toast("Editorial decision saved");
  } catch (error) { setStatus($("#candidateStatus"), error.message, true); }
}

function sourceSelections(sourceId) { return state.selections.filter(selection => selection.source_id === sourceId); }
function renderReview() {
  $("#reviewProgress").textContent = `${state.summary.reviewed_count} of ${state.summary.source_count} sources reviewed`;
  const visible = state.sources.filter(source => {
    const selections = sourceSelections(source.id);
    const matchesFilter = state.filter === "all" || (state.filter === "unreviewed" && !selections.length) || (state.filter === "keep" && selections.some(item => item.decision === "keep"));
    return matchesFilter && (!state.search || source.filename.toLocaleLowerCase().includes(state.search));
  });
  const shown = visible.slice(0, 300);
  $("#sourceList").innerHTML = shown.map((source, index) => {
    const selections = sourceSelections(source.id); const decision = selections.some(item => item.decision === "keep") ? "keep" : selections.length ? "maybe" : "";
    return `<button class="source-row ${state.source?.id === source.id ? "is-current" : ""}" data-source="${source.id}" type="button"><span class="ordinal">${String(index + 1).padStart(2, "0")}</span><span><strong>${escapeHtml(source.filename)}</strong><small>${seconds(source.duration)} · ${source.width || "?"}×${source.height || "?"}</small></span><span class="decision-dot ${decision}" title="${selections.length} selections" aria-label="${selections.length} saved selections"></span></button>`;
  }).join("") + (visible.length > shown.length ? `<p class="status source-limit">Showing the first ${shown.length} of ${visible.length}. Search to narrow the list.</p>` : "") || `<p class="status">No sources match this filter.</p>`;
  $$('[data-source]').forEach(button => button.addEventListener("click", () => chooseSource(button.dataset.source)));
  const coachDone = state.project && localStorage.getItem(`selects-first-selection-${state.project.id}`) === "done";
  $("#firstSelectionCoach").hidden = coachDone || !state.source || sourceSelections(state.source.id).length > 0;
  if (!state.source && visible.length) chooseSource((visible.find(source => !sourceSelections(source.id).length) || visible[0]).id);
}
function chooseSource(id) {
  state.source = state.sources.find(source => source.id === id); if (!state.source) return;
  $("#sourceTitle").textContent = state.source.filename;
  $("#sourceFacts").textContent = `${seconds(state.source.duration)} · ${state.source.width || "?"}×${state.source.height || "?"} · ${Number(state.source.fps || 0).toFixed(2)} fps`;
  $("#sourceStatus").textContent = state.source.status;
  const video = $("#sourceVideo");
  $("#offlineRelinkForm").hidden = state.source.status === "ready";
  state.mediaMode = state.source.review_media_url ? "review" : "original";
  if (state.source.status === "ready") { setSourceMedia(state.mediaMode, 0); }
  else { video.removeAttribute("src"); video.load(); }
  $("#inTime").max = state.source.duration || 0; $("#outTime").max = state.source.duration || 0; $("#rangeScrubber").max = state.source.duration || 0;
  $("#inTime").value = 0; $("#outTime").value = Math.min(Number(state.project.ideal_clip_duration || 8), Number(state.source.duration || 0)); updateRangeLabel();
  resetSelectionForm();
  renderSourceSelections(); renderReview();
}
function setSourceMedia(mode, resumeAt) {
  if (!state.source) return;
  const review = mode === "review" && state.source.review_media_url;
  state.mediaMode = review ? "review" : "original";
  const video = $("#sourceVideo"); const timestamp = Number(resumeAt || 0);
  video.src = review ? state.source.review_media_url : state.source.original_media_url || state.source.media_url;
  video.load();
  if (timestamp) video.addEventListener("loadedmetadata", () => { video.currentTime = Math.min(timestamp, video.duration || timestamp); }, { once: true });
  updateMediaModeButton();
}
function updateMediaModeButton() {
  const button = $("#sourceMediaModeButton");
  if (!state.source?.review_media_url) { button.hidden = true; return; }
  button.hidden = false; button.textContent = state.mediaMode === "review" ? "View full original" : "Use smoother review copy";
}
function toggleSourceMedia() { const video = $("#sourceVideo"); setSourceMedia(state.mediaMode === "review" ? "original" : "review", video.currentTime); }
function updateRangeLabel() { const start = Number($("#inTime").value); const end = Number($("#outTime").value); $("#rangeDuration").textContent = `${exact(Math.max(0, end - start))} s selected`; }
function renderSourceSelections() {
  const items = state.source ? sourceSelections(state.source.id) : [];
  $("#sourceSelectionCount").textContent = items.length;
  $("#sourceSelections").innerHTML = items.map(item => `<button class="saved-selection" data-selection="${item.id}" type="button"><strong>${exact(item.in_seconds)}–${exact(item.out_seconds)}</strong><span>${item.decision}</span><p>${escapeHtml(item.comment || "No comment")}</p></button>`).join("") || `<p class="status">No ranges saved yet.</p>`;
  $$('[data-selection]').forEach(button => button.addEventListener("click", () => loadSelection(button.dataset.selection)));
}
function loadSelection(id) {
  const item = state.selections.find(selection => selection.id === id); if (!item) return;
  state.editingSelection = item.id;
  $("#inTime").value = item.in_seconds; $("#outTime").value = item.out_seconds; $("#selectionComment").value = item.comment || "";
  $("#storyRole").value = item.story_role || ""; $("#audioIntent").value = item.audio_intent; $(`input[name="decision"][value="${item.decision}"]`).checked = true;
  $("#sourceVideo").currentTime = item.in_seconds; updateRangeLabel();
  $("#saveSelectionButton").textContent = "Update this selection"; $("#newSelectionButton").hidden = false; $("#archiveSelectionButton").hidden = false;
}
function resetSelectionForm() { state.editingSelection = null; $("#selectionComment").value = ""; $("#storyRole").value = ""; $("#audioIntent").value = "undecided"; const keep = $('input[name="decision"][value="keep"]'); if (keep) keep.checked = true; $("#saveSelectionButton").textContent = "Save as a new selection"; $("#newSelectionButton").hidden = true; $("#archiveSelectionButton").hidden = true; }
async function archiveSelection() {
  if (!state.editingSelection || !window.confirm("Archive this selection? Earlier saved cuts will still keep it.")) return;
  try {
    await request(`/api/selections/${state.editingSelection}/archive`, { method: "POST", body: "{}" });
    state.selections = state.selections.filter(item => item.id !== state.editingSelection);
    state.sequenceIds = state.sequenceIds.filter(id => id !== state.editingSelection);
    resetSelectionForm(); renderSourceSelections(); renderReview(); renderAssembly(); toast("Selection archived");
  } catch (error) { setStatus($("#selectionStatus"), error.message, true); }
}
async function saveSelection() {
  if (!state.source) return;
  const body = { project_id: state.project.id, source_id: state.source.id, in_seconds: Number($("#inTime").value), out_seconds: Number($("#outTime").value), decision: $('input[name="decision"]:checked').value, comment: $("#selectionComment").value, story_role: $("#storyRole").value || null, audio_intent: $("#audioIntent").value };
  try { setStatus($("#selectionStatus"), "Saving…"); let selection; if (state.editingSelection) { const { project_id, source_id, ...changes } = body; selection = await request(`/api/selections/${state.editingSelection}`, { method: "PATCH", body: JSON.stringify(changes) }); const index = state.selections.findIndex(item => item.id === selection.id); state.selections[index] = selection; } else { selection = await request("/api/selections", { method: "POST", body: JSON.stringify(body) }); state.selections.push(selection); } state.summary.reviewed_count = new Set(state.selections.map(item => item.source_id)).size; state.summary.keep_seconds = state.selections.filter(item => item.decision === "keep").reduce((sum, item) => sum + item.duration, 0); const wasEditing = Boolean(state.editingSelection); state.editingSelection = selection.id; localStorage.setItem(`selects-first-selection-${state.project.id}`, "done"); $("#firstSelectionCoach").hidden = true; renderSourceSelections(); renderReview(); loadSelection(selection.id); setStatus($("#selectionStatus"), wasEditing ? "Selection updated." : "Saved. Choose Start another range to pull a second moment from this source."); toast(wasEditing ? "Selection updated" : "Selection saved"); } catch (error) { setStatus($("#selectionStatus"), error.message, true); }
}
function playRange() { const video = $("#sourceVideo"); state.playingRange = true; video.currentTime = Number($("#inTime").value); video.play(); }

function renderAssembly() {
  if (!state.project) return;
  const sequenceSelect = $("#sequenceSelect");
  sequenceSelect.innerHTML = `<option value="">New sequence</option>${state.sequences.map(item => `<option value="${item.id}" ${state.sequence?.sequence_id === item.id ? "selected" : ""}>${escapeHtml(item.name)} · v${item.latest_version || 1}</option>`).join("")}`;
  const selected = new Set(state.sequenceIds); const available = state.selections.filter(item => ["keep", "maybe"].includes(item.decision) && !selected.has(item.id));
  $("#alternateList").innerHTML = available.map(item => `<button class="alternate-row" data-add="${item.id}" type="button"><strong>${escapeHtml(item.filename)}</strong><span>＋</span><small>${exact(item.in_seconds)}–${exact(item.out_seconds)} · ${item.decision}${item.comment ? ` · ${escapeHtml(item.comment)}` : ""}</small></button>`).join("") || `<p class="status">No unused keep or maybe selections.</p>`;
  $("#sequenceList").innerHTML = state.sequenceIds.map((id, index) => { const item = state.selections.find(selection => selection.id === id); if (!item) return ""; return `<li class="sequence-item"><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(item.filename)}</strong><small>${exact(item.in_seconds)}–${exact(item.out_seconds)} · ${escapeHtml(item.comment || item.story_role || "No note")}</small></div><div class="item-actions"><button data-move="up" data-index="${index}" aria-label="Move up">↑</button><button data-move="down" data-index="${index}" aria-label="Move down">↓</button><button data-remove="${index}" aria-label="Remove from sequence">×</button></div></li>`; }).join("") || `<li class="status">Add selections from the left. Nothing is deleted when omitted.</li>`;
  const duration = state.sequenceIds.reduce((sum, id) => sum + Number(state.selections.find(item => item.id === id)?.duration || 0), 0);
  $("#sequenceDuration").textContent = seconds(duration); $("#targetDuration").textContent = state.project.target_duration ? `Target ${seconds(state.project.target_duration)} · ${duration > state.project.target_duration ? `${seconds(duration - state.project.target_duration)} over` : `${seconds(state.project.target_duration - duration)} available`}` : "No target set";
  $("#sequenceHeading").textContent = state.sequence ? `${state.sequence.sequence_name} · version ${state.sequence.version}` : "New sequence";
  $("#saveSequenceButton").textContent = state.sequence ? "Save new version" : "Save first cut";
  $$('[data-add]').forEach(button => button.addEventListener("click", () => { state.sequenceIds.push(button.dataset.add); renderAssembly(); }));
  $$('[data-remove]').forEach(button => button.addEventListener("click", () => { state.sequenceIds.splice(Number(button.dataset.remove), 1); renderAssembly(); }));
  $$('[data-move]').forEach(button => button.addEventListener("click", () => { const from = Number(button.dataset.index); const to = button.dataset.move === "up" ? from - 1 : from + 1; if (to < 0 || to >= state.sequenceIds.length) return; [state.sequenceIds[from], state.sequenceIds[to]] = [state.sequenceIds[to], state.sequenceIds[from]]; renderAssembly(); }));
}
async function loadSequence(sequenceId) {
  if (!sequenceId) { state.sequence = null; state.sequenceIds = []; renderAssembly(); return; }
  try {
    state.sequence = await request(`/api/sequences/${sequenceId}`);
    state.sequenceIds = state.sequence.items.map(item => item.id);
    $("#sequencePreview").hidden = true; renderAssembly();
  } catch (error) { setStatus($("#sequenceStatus"), error.message, true); }
}
async function saveSequence() {
  if (!state.sequenceIds.length) { setStatus($("#sequenceStatus"), "Add at least one selection first.", true); return; }
  try { setStatus($("#sequenceStatus"), "Saving a reversible version…"); const path = state.sequence ? `/api/sequences/${state.sequence.sequence_id}/versions` : "/api/sequences"; const body = state.sequence ? { selection_ids: state.sequenceIds, note: "Reordered in Selects" } : { project_id: state.project.id, name: "First cut", selection_ids: state.sequenceIds, target_duration: state.project.target_duration }; state.sequence = await request(path, { method: "POST", body: JSON.stringify(body) }); state.sequences = (await request(`/api/projects/${state.project.id}`)).sequences; $("#sequencePreview").hidden = true; setStatus($("#sequenceStatus"), `Saved version ${state.sequence.version}. Earlier versions remain intact.`); renderAssembly(); } catch (error) { setStatus($("#sequenceStatus"), error.message, true); }
}
async function renderSequencePreview() { if (!state.sequence) { await saveSequence(); if (!state.sequence) return; } const video = $("#sequencePreview"); setStatus($("#sequenceStatus"), "Rendering a lightweight end-to-end preview…"); video.hidden = false; video.src = `/api/sequences/${state.sequence.sequence_id}/preview?version=${state.sequence.version}&t=${Date.now()}`; video.load(); video.addEventListener("canplay", () => setStatus($("#sequenceStatus"), "Preview ready. This is intentionally low resolution; Resolve remains linked to originals."), { once: true }); video.addEventListener("error", () => setStatus($("#sequenceStatus"), "The preview could not be rendered. Check that every source is online, then try again.", true), { once: true }); }
async function exportSequence() { if (!state.sequence) { setStatus($("#sequenceStatus"), "Save the sequence before exporting.", true); return; } try { const result = await request(`/api/sequences/${state.sequence.sequence_id}/export`, { method: "POST", body: "{}" }); setStatus($("#sequenceStatus"), "Resolve handoff written successfully."); $("#exportPath").textContent = result.fcpxml; $("#exportNextSteps").hidden = false; toast("DaVinci Resolve handoff ready"); } catch (error) { setStatus($("#sequenceStatus"), error.message, true); } }

function renderAssistant() {
  if (!state.project) return;
  $("#agentCommand").textContent = `selects --json project context ${state.project.id}`;
  $("#proposalCount").textContent = state.proposals.length;
  $("#proposalList").innerHTML = state.proposals.map(proposal => `<article class="proposal-card"><header><strong>${escapeHtml(proposal.kind)}</strong><span>${proposal.status}</span></header><p>${escapeHtml(proposal.explanation || "No explanation supplied")}</p><pre>${escapeHtml(JSON.stringify(proposal.payload, null, 2))}</pre>${proposal.status === "pending" ? `<div class="button-row"><button data-apply-proposal="${proposal.id}" type="button">Accept and apply</button><button data-reject-proposal="${proposal.id}" type="button">Reject</button></div>` : ""}</article>`).join("") || `<p class="status">No assistant proposals yet.</p>`;
  $$('[data-apply-proposal]').forEach(button => button.addEventListener("click", () => decideProposal(button.dataset.applyProposal, true)));
  $$('[data-reject-proposal]').forEach(button => button.addEventListener("click", () => decideProposal(button.dataset.rejectProposal, false)));
}
async function copyContext() { const context = await request(`/api/projects/${state.project.id}/context`); await navigator.clipboard.writeText(JSON.stringify(context, null, 2)); toast("Path-free project context copied"); }
async function importProposal() { try { const raw = JSON.parse($("#proposalJson").value); if (!raw.kind || !raw.payload) throw new Error("Proposal needs kind and payload."); const proposal = await request("/api/proposals", { method: "POST", body: JSON.stringify({ project_id: state.project.id, provider: $("#proposalProvider").value, kind: raw.kind, payload: raw.payload, explanation: raw.explanation || "" }) }); state.proposals.unshift(proposal); $("#proposalJson").value = ""; setStatus($("#proposalStatus"), "Saved as pending. Nothing was changed."); renderAssistant(); } catch (error) { setStatus($("#proposalStatus"), error.message, true); } }
async function askAssistant() { const button = $("#askAssistantButton"); try { button.disabled = true; setStatus($("#assistantStatus"), "Sending the path-free project summary and waiting for a proposal…"); const proposal = await request(`/api/projects/${state.project.id}/assist`, { method: "POST", body: JSON.stringify({ api_key: $("#openaiKey").value, model: $("#openaiModel").value, direction: $("#assistantDirection").value }) }); $("#openaiKey").value = ""; state.proposals.unshift(proposal); setStatus($("#assistantStatus"), "Proposal received. Nothing changed; inspect it in Proposal history before accepting."); renderAssistant(); } catch (error) { setStatus($("#assistantStatus"), error.message, true); } finally { button.disabled = false; } }
async function decideProposal(id, apply) { try { await request(`/api/proposals/${id}/${apply ? "apply" : "reject"}`, { method: "POST", body: "{}" }); const payload = await request(`/api/projects/${state.project.id}`); Object.assign(state, payload); if (apply) { const latest = state.sequences[0]; if (latest) { state.sequence = await request(`/api/sequences/${latest.id}`); state.sequenceIds = state.sequence.items.map(item => item.id); } } renderAssistant(); renderAssembly(); toast(apply ? "Proposal applied" : "Proposal rejected"); } catch (error) { setStatus($("#proposalStatus"), error.message, true); } }

function populateProjectSettings() {
  const form = $("#projectSettingsForm");
  for (const key of ["name", "target_duration_seconds", "shot_rhythm", "shot_min_seconds", "shot_max_seconds", "candidate_breadth", "audio_preference", "orientation", "intent"]) {
    if (form.elements[key]) form.elements[key].value = state.project[key] ?? "";
  }
}
async function saveProjectSettings(event) {
  event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget));
  try {
    state.project = await request(`/api/projects/${state.project.id}`, { method: "PATCH", body: JSON.stringify(body) });
    state.projects = (await request("/api/projects")).projects; populateProjectSettings(); renderAssembly();
    state.latest_run = await request(`/api/projects/${state.project.id}/overnight-plan`, { method: "POST", body: JSON.stringify({ prevent_sleep: true }) });
    $("#projectSelect").selectedOptions[0].textContent = state.project.name;
    setStatus($("#settingsStatus"), "Project brief saved and a fresh plan calculated."); toast("Project brief saved");
  } catch (error) { setStatus($("#settingsStatus"), error.message, true); }
}
async function backupDatabase() {
  try { const result = await request(`/api/projects/${state.project.id}/backup`, { method: "POST", body: "{}" }); setStatus($("#settingsStatus"), `Backup written to ${result.backup}`); toast("Backup created"); }
  catch (error) { setStatus($("#settingsStatus"), error.message, true); }
}
async function chooseFolder(button) {
  const form = button.closest("form"); const input = form.elements[button.dataset.folderTarget];
  if (!window.pywebview?.api?.choose_folder) { input.focus(); toast("Paste the folder path here, or use the Selects desktop app for a folder picker."); return; }
  const selected = await window.pywebview.api.choose_folder(input.value || ""); if (selected) input.value = selected;
}
async function chooseFile(button) {
  const form = button.closest("form"); const input = form.elements[button.dataset.fileTarget];
  if (!window.pywebview?.api?.choose_file) { input.focus(); toast("Paste the file path here, or use the Selects desktop app for a file picker."); return; }
  const selected = await window.pywebview.api.choose_file(input.value || ""); if (selected) input.value = selected;
}
async function relinkSource(event) {
  event.preventDefault(); const path = new FormData(event.currentTarget).get("path");
  try {
    setStatus($("#relinkStatus"), "Checking that this is the same source…");
    const source = await request(`/api/sources/${state.source.id}/relink`, {method:"POST", body:JSON.stringify({path})});
    const index = state.sources.findIndex(item => item.id === source.id); state.sources[index] = source;
    chooseSource(source.id); setStatus($("#relinkStatus"), ""); toast("Original relinked");
  } catch (error) { setStatus($("#relinkStatus"), error.message, true); }
}

$("#projectForm").addEventListener("submit", async event => { event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget)); try { setStatus($("#projectStatus"), "Inspecting every nested folder. A broken clip will not stop the rest…"); const payload = await request("/api/projects", { method: "POST", body: JSON.stringify(body) }); state.projects = (await request("/api/projects")).projects; Object.assign(state, payload); await openProject(payload.project.id); } catch (error) { setStatus($("#projectStatus"), error.message, true); } });
$("#sampleProjectButton").addEventListener("click", async () => { try { $("#sampleProjectButton").disabled = true; setStatus($("#projectStatus"), "Building three small local sample clips…"); const payload = await request("/api/sample-project", { method: "POST", body: "{}" }); state.projects = (await request("/api/projects")).projects; await openProject(payload.project.id); toast("Sample project ready"); } catch (error) { setStatus($("#projectStatus"), error.message, true); } finally { $("#sampleProjectButton").disabled = false; } });
$("#prepareProxiesButton").addEventListener("click", prepareReviewProxies); $("#reviewOriginalsButton").addEventListener("click", reviewOriginals);
$("#newProjectButton").addEventListener("click", showWelcome); $("#projectSelect").addEventListener("change", event => openProject(event.target.value));
$$(".tabs button").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
$("#projectForm").elements.shot_rhythm.addEventListener("change", event => { $("#customRhythm").hidden = event.target.value !== "custom"; });
$("#startOvernightButton").addEventListener("click", startOvernight);
$("#manualReviewButton").addEventListener("click", () => switchView("sources"));
$("#emptyReviewSources").addEventListener("click", () => switchView("sources"));
$("#emptyChooseFolder").addEventListener("click", () => { switchView("sources"); $("#addFolderButton").click(); });
$("#editBriefButton").addEventListener("click", () => { switchView("assemble"); $(".project-settings").open = true; $(".project-settings").scrollIntoView({ behavior: "smooth" }); });
$("#preventSleep").addEventListener("change", () => rebuildPlan($("#cachePath").value));
$("#chooseCacheButton").addEventListener("click", async () => { const input = $("#cachePath"); if (!window.pywebview?.api?.choose_folder) { input.focus(); toast("Paste a cache folder path here, then press Enter."); return; } const chosen = await window.pywebview.api.choose_folder(input.value || ""); if (chosen) { input.value = chosen; await rebuildPlan(chosen); } });
$("#cachePath").addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); rebuildPlan(event.currentTarget.value); } });
$("#pauseRunButton").addEventListener("click", () => runAction("pause"));
$("#resumeRunButton").addEventListener("click", () => runAction("start"));
$("#cancelRunButton").addEventListener("click", () => { if (window.confirm("Cancel this preparation run? Completed proposals will remain available.")) runAction("cancel"); });
$("#reviewReadyButton").addEventListener("click", () => switchView("candidates"));
$("#moveRunCacheButton").addEventListener("click", moveRunCache);
$$("[data-candidate-filter]").forEach(button => button.addEventListener("click", () => { state.candidateFilter = button.dataset.candidateFilter; $$("[data-candidate-filter]").forEach(item => item.classList.toggle("is-active", item === button)); renderCandidates(); }));
$("#candidateMediaMode").addEventListener("click", () => setCandidateMedia(state.candidateMediaMode === "sample" ? "source" : "sample"));
$("#candidateIn").addEventListener("input", updateCandidateRange); $("#candidateOut").addEventListener("input", updateCandidateRange);
$("#candidateScrubber").addEventListener("input", event => { if (!state.candidate) return; const sourceTime = Number(event.target.value); $("#candidateVideo").currentTime = state.candidateMediaMode === "source" ? sourceTime : Math.max(0, sourceTime - state.candidate.in_seconds); });
$("#candidateVideo").addEventListener("timeupdate", event => { if (!state.candidate) return; const generatedIn = Number(state.candidate.generated_in_us) / 1e6; $("#candidateScrubber").value = state.candidateMediaMode === "source" ? event.target.currentTime : generatedIn + event.target.currentTime; });
$("#saveCandidateButton").addEventListener("click", saveCandidateDecision);
$$(".filters button").forEach(button => button.addEventListener("click", () => { state.filter = button.dataset.filter; $$(".filters button").forEach(item => item.classList.toggle("is-active", item === button)); renderReview(); }));
$("#sourceSearch").addEventListener("input", event => { state.search = event.target.value.trim().toLocaleLowerCase(); renderReview(); });
$("#rescanButton").addEventListener("click", async () => { try { $("#rescanButton").disabled = true; await request(`/api/projects/${state.project.id}/scan`, { method: "POST", body: "{}" }); await openProject(state.project.id); toast("Folder rescanned"); } catch (error) { toast(error.message); } finally { $("#rescanButton").disabled = false; } });
$("#addFolderButton").addEventListener("click", () => { $("#addFolderForm").hidden = false; $("#addFolderButton").disabled = true; }); $("#cancelFolderButton").addEventListener("click", () => { $("#addFolderForm").hidden = true; $("#addFolderButton").disabled = false; });
$("#addFolderForm").addEventListener("submit", async event => { event.preventDefault(); const path = new FormData(event.currentTarget).get("path"); try { setStatus($("#folderStatus"), "Adding and scanning…"); await request(`/api/projects/${state.project.id}/roots`, { method: "POST", body: JSON.stringify({path}) }); await request(`/api/projects/${state.project.id}/scan`, { method: "POST", body: "{}" }); await openProject(state.project.id); toast("Footage folder added"); } catch (error) { setStatus($("#folderStatus"), error.message, true); } });
$("#setInButton").addEventListener("click", () => { $("#inTime").value = exact($("#sourceVideo").currentTime); updateRangeLabel(); });
$("#setOutButton").addEventListener("click", () => { $("#outTime").value = exact($("#sourceVideo").currentTime); updateRangeLabel(); });
$("#playRangeButton").addEventListener("click", playRange); $("#inTime").addEventListener("input", updateRangeLabel); $("#outTime").addEventListener("input", updateRangeLabel);
$("#sourceMediaModeButton").addEventListener("click", toggleSourceMedia);
$("#sourceVideo").addEventListener("timeupdate", event => { $("#rangeScrubber").value = event.target.currentTime; if (state.playingRange && event.target.currentTime >= Number($("#outTime").value)) { event.target.pause(); state.playingRange = false; } });
$("#rangeScrubber").addEventListener("input", event => { $("#sourceVideo").currentTime = Number(event.target.value); }); $("#saveSelectionButton").addEventListener("click", saveSelection);
$("#archiveSelectionButton").addEventListener("click", archiveSelection);
$("#newSelectionButton").addEventListener("click", () => { resetSelectionForm(); $("#inTime").value = exact($("#sourceVideo").currentTime || 0); $("#outTime").value = exact(Math.min(Number(state.source.duration), Number($("#inTime").value) + Number(state.project.ideal_clip_duration || 8))); updateRangeLabel(); $("#selectionComment").focus(); });
document.addEventListener("keydown", event => { if (event.target.matches("input, textarea, select")) return; const video = $("#sourceVideo"); if (!$("#reviewView").hidden && state.source) { if (event.key === " ") { event.preventDefault(); video.paused ? video.play() : video.pause(); } if (event.key.toLowerCase() === "i") $("#setInButton").click(); if (event.key.toLowerCase() === "o") $("#setOutButton").click(); if (event.key === "/") { event.preventDefault(); playRange(); } if (event.key === "ArrowLeft") video.currentTime = Math.max(0, video.currentTime - 1); if (event.key === "ArrowRight") video.currentTime = Math.min(video.duration || Infinity, video.currentTime + 1); } });
$("#saveSequenceButton").addEventListener("click", saveSequence); $("#previewSequenceButton").addEventListener("click", renderSequencePreview); $("#exportSequenceButton").addEventListener("click", exportSequence); $("#sequenceSelect").addEventListener("change", event => loadSequence(event.target.value));
$("#projectSettingsForm").addEventListener("submit", saveProjectSettings); $("#backupButton").addEventListener("click", backupDatabase); $$(".choose-folder").forEach(button => button.addEventListener("click", () => chooseFolder(button)));
$("#offlineRelinkForm").addEventListener("submit", relinkSource); $$(".choose-file").forEach(button => button.addEventListener("click", () => chooseFile(button)));
$("#copyAgentCommand").addEventListener("click", async () => { await navigator.clipboard.writeText($("#agentCommand").textContent); toast("Agent command copied"); }); $("#copyContextButton").addEventListener("click", copyContext); $("#importProposalButton").addEventListener("click", importProposal);
$("#askAssistantButton").addEventListener("click", askAssistant);
loadProjects().catch(error => { showWelcome(); setStatus($("#projectStatus"), error.message, true); });
