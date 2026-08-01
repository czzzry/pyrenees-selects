const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = { projects: [], project: null, sources: [], selections: [], sequences: [], proposals: [], source: null, filter: "all", search: "", sequenceIds: [], sequence: null, playingRange: false, editingSelection: null };

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
function setStatus(element, message, error = false) { element.textContent = message; element.classList.toggle("is-error", error); }
function toast(message) { const node = $("#toast"); node.textContent = message; node.hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => { node.hidden = true; }, 3000); }

async function loadProjects(preferred) {
  state.projects = (await request("/api/projects")).projects;
  if (!state.projects.length) { showWelcome(); return; }
  const id = preferred || localStorage.getItem("selects-project") || state.projects[0].id;
  await openProject(state.projects.some(project => project.id === id) ? id : state.projects[0].id);
}
function showWelcome() {
  $("#welcome").hidden = false; $$(".workspace, .assemble, .assistant, .tabs, .project-switcher").forEach(node => node.hidden = true);
}
async function openProject(id) {
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
  populateProjectSettings(); renderReview(); renderAssembly(); renderAssistant(); switchView("review");
}
function switchView(view) {
  $("#reviewView").hidden = view !== "review"; $("#assembleView").hidden = view !== "assemble"; $("#assistantView").hidden = view !== "assistant";
  $$(".tabs button").forEach(button => button.setAttribute("aria-current", button.dataset.view === view ? "page" : "false"));
  if (view === "assemble") renderAssembly(); if (view === "assistant") renderAssistant();
}
function escapeHtml(value) { const div = document.createElement("div"); div.textContent = String(value ?? ""); return div.innerHTML; }
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
  if (!state.source && visible.length) chooseSource(visible[0].id);
}
function chooseSource(id) {
  state.source = state.sources.find(source => source.id === id); if (!state.source) return;
  $("#sourceTitle").textContent = state.source.filename;
  $("#sourceFacts").textContent = `${seconds(state.source.duration)} · ${state.source.width || "?"}×${state.source.height || "?"} · ${Number(state.source.fps || 0).toFixed(2)} fps`;
  $("#sourceStatus").textContent = state.source.status;
  const video = $("#sourceVideo");
  $("#offlineRelinkForm").hidden = state.source.status === "ready";
  if (state.source.status === "ready") { video.src = state.source.media_url; video.load(); }
  else { video.removeAttribute("src"); video.load(); }
  $("#inTime").max = state.source.duration || 0; $("#outTime").max = state.source.duration || 0; $("#rangeScrubber").max = state.source.duration || 0;
  $("#inTime").value = 0; $("#outTime").value = Math.min(Number(state.project.ideal_clip_duration || 8), Number(state.source.duration || 0)); updateRangeLabel();
  resetSelectionForm();
  renderSourceSelections(); renderReview();
}
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
  try { setStatus($("#selectionStatus"), "Saving…"); let selection; if (state.editingSelection) { const { project_id, source_id, ...changes } = body; selection = await request(`/api/selections/${state.editingSelection}`, { method: "PATCH", body: JSON.stringify(changes) }); const index = state.selections.findIndex(item => item.id === selection.id); state.selections[index] = selection; } else { selection = await request("/api/selections", { method: "POST", body: JSON.stringify(body) }); state.selections.push(selection); } state.summary.reviewed_count = new Set(state.selections.map(item => item.source_id)).size; state.summary.keep_seconds = state.selections.filter(item => item.decision === "keep").reduce((sum, item) => sum + item.duration, 0); const wasEditing = Boolean(state.editingSelection); state.editingSelection = selection.id; renderSourceSelections(); renderReview(); loadSelection(selection.id); setStatus($("#selectionStatus"), wasEditing ? "Selection updated." : "Saved. Choose Start another range to pull a second moment from this source."); toast(wasEditing ? "Selection updated" : "Selection saved"); } catch (error) { setStatus($("#selectionStatus"), error.message, true); }
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
async function exportSequence() { if (!state.sequence) { setStatus($("#sequenceStatus"), "Save the sequence before exporting.", true); return; } try { const result = await request(`/api/sequences/${state.sequence.sequence_id}/export`); setStatus($("#sequenceStatus"), `Resolve handoff written to ${result.fcpxml}`); toast("DaVinci Resolve handoff ready"); } catch (error) { setStatus($("#sequenceStatus"), error.message, true); } }

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
  for (const key of ["name", "target_duration", "ideal_clip_duration", "orientation", "intent"]) {
    if (form.elements[key]) form.elements[key].value = state.project[key] ?? "";
  }
}
async function saveProjectSettings(event) {
  event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget));
  try {
    state.project = await request(`/api/projects/${state.project.id}`, { method: "PATCH", body: JSON.stringify(body) });
    state.projects = (await request("/api/projects")).projects; populateProjectSettings(); renderAssembly();
    $("#projectSelect").selectedOptions[0].textContent = state.project.name;
    setStatus($("#settingsStatus"), "Project settings saved."); toast("Project settings saved");
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

$("#projectForm").addEventListener("submit", async event => { event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget)); try { setStatus($("#projectStatus"), "Inspecting the folder. A broken clip will not stop the rest…"); const payload = await request("/api/projects", { method: "POST", body: JSON.stringify(body) }); state.projects = (await request("/api/projects")).projects; Object.assign(state, payload); await openProject(payload.project.id); } catch (error) { setStatus($("#projectStatus"), error.message, true); } });
$("#newProjectButton").addEventListener("click", showWelcome); $("#projectSelect").addEventListener("change", event => openProject(event.target.value));
$$(".tabs button").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
$$(".filters button").forEach(button => button.addEventListener("click", () => { state.filter = button.dataset.filter; $$(".filters button").forEach(item => item.classList.toggle("is-active", item === button)); renderReview(); }));
$("#sourceSearch").addEventListener("input", event => { state.search = event.target.value.trim().toLocaleLowerCase(); renderReview(); });
$("#rescanButton").addEventListener("click", async () => { try { $("#rescanButton").disabled = true; await request(`/api/projects/${state.project.id}/scan`, { method: "POST", body: "{}" }); await openProject(state.project.id); toast("Folder rescanned"); } catch (error) { toast(error.message); } finally { $("#rescanButton").disabled = false; } });
$("#addFolderButton").addEventListener("click", () => { $("#addFolderForm").hidden = false; $("#addFolderButton").disabled = true; }); $("#cancelFolderButton").addEventListener("click", () => { $("#addFolderForm").hidden = true; $("#addFolderButton").disabled = false; });
$("#addFolderForm").addEventListener("submit", async event => { event.preventDefault(); const path = new FormData(event.currentTarget).get("path"); try { setStatus($("#folderStatus"), "Adding and scanning…"); await request(`/api/projects/${state.project.id}/roots`, { method: "POST", body: JSON.stringify({path}) }); await request(`/api/projects/${state.project.id}/scan`, { method: "POST", body: "{}" }); await openProject(state.project.id); toast("Footage folder added"); } catch (error) { setStatus($("#folderStatus"), error.message, true); } });
$("#setInButton").addEventListener("click", () => { $("#inTime").value = exact($("#sourceVideo").currentTime); updateRangeLabel(); });
$("#setOutButton").addEventListener("click", () => { $("#outTime").value = exact($("#sourceVideo").currentTime); updateRangeLabel(); });
$("#playRangeButton").addEventListener("click", playRange); $("#inTime").addEventListener("input", updateRangeLabel); $("#outTime").addEventListener("input", updateRangeLabel);
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
