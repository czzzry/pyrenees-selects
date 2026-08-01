const elements = {
  workspace: document.getElementById("reviewWorkspace"),
  completeView: document.getElementById("completeView"),
  errorView: document.getElementById("errorView"),
  errorMessage: document.getElementById("errorMessage"),
  retryButton: document.getElementById("retryButton"),
  progressCopy: document.getElementById("progressCopy"),
  positionCopy: document.getElementById("positionCopy"),
  currentDecision: document.getElementById("currentDecision"),
  includeCount: document.getElementById("includeCount"),
  maybeCount: document.getElementById("maybeCount"),
  excludeCount: document.getElementById("excludeCount"),
  reviewPhoto: document.getElementById("reviewPhoto"),
  photoLoading: document.getElementById("photoLoading"),
  captureDate: document.getElementById("captureDate"),
  filename: document.getElementById("filename"),
  comment: document.getElementById("comment"),
  commentCount: document.getElementById("commentCount"),
  saveStatus: document.getElementById("saveStatus"),
  previousButton: document.getElementById("previousButton"),
  nextButton: document.getElementById("nextButton"),
  excludeButton: document.getElementById("excludeButton"),
  maybeButton: document.getElementById("maybeButton"),
  includeButton: document.getElementById("includeButton"),
  undoButton: document.getElementById("undoButton"),
  completeSummary: document.getElementById("completeSummary"),
  reviewIncludedButton: document.getElementById("reviewIncludedButton"),
  reviewAllButton: document.getElementById("reviewAllButton"),
};

let photos = [];
let summary = { total: 0, reviewed: 0, remaining: 0, include: 0, maybe: 0, exclude: 0 };
let currentIndex = 0;
let visibleIndices = [];
let reviewFilter = "all";
let undoEntry = null;
let busy = false;
let commentTimer = null;
let commentPromise = null;
let commentRevision = 0;
let commentDirty = false;

const decisionLabels = {
  include: "Included",
  maybe: "Maybe",
  exclude: "Not included",
};

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function currentPhoto() {
  return photos[currentIndex] || null;
}

function setBusy(value) {
  busy = value;
  document.querySelectorAll(".decision-button").forEach(button => { button.disabled = value; });
  elements.previousButton.disabled = value || neighborIndex(-1) === -1;
  elements.nextButton.disabled = value || neighborIndex(1) === -1;
  elements.comment.disabled = value;
  elements.workspace.setAttribute("aria-busy", String(value));
}

function setSaveStatus(message, state = "saved") {
  elements.saveStatus.textContent = message;
  elements.saveStatus.classList.toggle("is-saving", state === "saving");
  elements.saveStatus.classList.toggle("is-error", state === "error");
}

function renderSummary() {
  elements.includeCount.textContent = String(summary.include || 0);
  elements.maybeCount.textContent = String(summary.maybe || 0);
  elements.excludeCount.textContent = String(summary.exclude || 0);
  elements.progressCopy.textContent = `${summary.reviewed} of ${summary.total} reviewed`;
}

function renderDecision(photo) {
  document.querySelectorAll(".decision-button").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.decision === photo.decision));
  });
  elements.currentDecision.textContent = photo.decision
    ? decisionLabels[photo.decision]
    : "Not yet reviewed";
}

function preloadAround(index) {
  for (const nextIndex of [index - 1, index + 1, index + 2]) {
    const photo = photos[nextIndex];
    if (!photo) continue;
    const image = new Image();
    image.src = photo.image_url;
  }
}

function renderPhoto() {
  const photo = currentPhoto();
  if (!photo) return;
  elements.workspace.hidden = false;
  elements.completeView.hidden = true;
  elements.errorView.hidden = true;
  elements.positionCopy.textContent = `Photo ${currentIndex + 1} of ${photos.length}`;
  elements.captureDate.textContent = photo.captured_label;
  elements.filename.textContent = photo.filename;
  elements.filename.title = photo.filename;
  elements.comment.value = photo.comment || "";
  elements.commentCount.textContent = String(elements.comment.value.length);
  commentDirty = false;
  commentRevision = 0;
  if (commentTimer) clearTimeout(commentTimer);
  commentTimer = null;
  setSaveStatus(photo.updated_at ? "Saved locally" : "Notes save locally");
  renderDecision(photo);
  elements.previousButton.disabled = neighborIndex(-1) === -1;
  elements.nextButton.disabled = neighborIndex(1) === -1;

  elements.reviewPhoto.classList.add("is-loading");
  elements.photoLoading.hidden = false;
  elements.reviewPhoto.alt = `Selfie captured ${photo.captured_label}`;
  elements.reviewPhoto.onload = () => {
    if (elements.reviewPhoto.dataset.photoId !== String(photo.id)) return;
    elements.photoLoading.hidden = true;
    elements.reviewPhoto.classList.remove("is-loading");
  };
  elements.reviewPhoto.onerror = () => {
    if (elements.reviewPhoto.dataset.photoId !== String(photo.id)) return;
    elements.photoLoading.textContent = "This photo could not be displayed.";
    elements.photoLoading.hidden = false;
  };
  elements.reviewPhoto.dataset.photoId = String(photo.id);
  elements.reviewPhoto.src = photo.image_url;
  preloadAround(currentIndex);
}

function applySavedPhoto(saved) {
  const index = photos.findIndex(photo => photo.id === saved.id);
  if (index !== -1) photos[index] = saved;
}

async function saveCurrent(fields, message = "Saving locally…") {
  const photo = currentPhoto();
  if (!photo) return null;
  setSaveStatus(message, "saving");
  try {
    const payload = await request(`/api/photos/${photo.id}`, {
      method: "POST",
      body: JSON.stringify(fields),
    });
    applySavedPhoto(payload.photo);
    summary = payload.summary;
    renderSummary();
    setSaveStatus("Saved locally");
    return payload.photo;
  } catch (error) {
    setSaveStatus("Could not save — try again", "error");
    throw error;
  }
}

function scheduleCommentSave() {
  commentDirty = true;
  commentRevision += 1;
  const revision = commentRevision;
  if (commentTimer) clearTimeout(commentTimer);
  setSaveStatus("Saving note…", "saving");
  commentTimer = setTimeout(() => {
    const comment = elements.comment.value;
    commentPromise = saveCurrent({ comment }, "Saving note…")
      .then(saved => {
        if (revision === commentRevision && saved) commentDirty = false;
      })
      .catch(() => {})
      .finally(() => { commentPromise = null; });
  }, 350);
}

async function flushComment() {
  if (commentTimer) {
    clearTimeout(commentTimer);
    commentTimer = null;
  }
  if (commentPromise) await commentPromise;
  if (!commentDirty) return;
  const revision = commentRevision;
  const saved = await saveCurrent({ comment: elements.comment.value }, "Saving note…");
  if (revision === commentRevision && saved) commentDirty = false;
}

function nextPendingIndex(afterIndex) {
  for (let index = afterIndex + 1; index < photos.length; index += 1) {
    if (!photos[index].decision) return index;
  }
  for (let index = 0; index <= afterIndex; index += 1) {
    if (!photos[index].decision) return index;
  }
  return -1;
}

async function decide(decision) {
  if (busy) return;
  const photo = currentPhoto();
  if (!photo) return;
  setBusy(true);
  try {
    await flushComment();
    undoEntry = {
      index: currentIndex,
      decision: photo.decision ?? null,
    };
    const saved = await saveCurrent({ decision, comment: elements.comment.value });
    if (!saved) return;
    elements.undoButton.disabled = false;
    const nextIndex = nextPendingIndex(currentIndex);
    if (nextIndex === -1) {
      showComplete();
    } else {
      currentIndex = nextIndex;
      renderPhoto();
    }
  } catch (error) {
    showTransientError(error);
  } finally {
    setBusy(false);
  }
}

async function undo() {
  if (!undoEntry || busy) return;
  setBusy(true);
  try {
    await flushComment();
    currentIndex = undoEntry.index;
    const photo = photos[currentIndex];
    const payload = await request(`/api/photos/${photo.id}`, {
      method: "POST",
      body: JSON.stringify({ decision: undoEntry.decision }),
    });
    applySavedPhoto(payload.photo);
    summary = payload.summary;
    undoEntry = null;
    elements.undoButton.disabled = true;
    renderSummary();
    renderPhoto();
  } catch (error) {
    showTransientError(error);
  } finally {
    setBusy(false);
  }
}

async function navigate(index) {
  if (busy || index < 0 || index >= photos.length || index === currentIndex) return;
  setBusy(true);
  try {
    await flushComment();
    currentIndex = index;
    renderPhoto();
  } catch (error) {
    showTransientError(error);
  } finally {
    setBusy(false);
  }
}

function neighborIndex(direction) {
  if (reviewFilter === "all") {
    const candidate = currentIndex + direction;
    return candidate >= 0 && candidate < photos.length ? candidate : -1;
  }
  const position = visibleIndices.indexOf(currentIndex);
  if (position === -1) return -1;
  return visibleIndices[position + direction] ?? -1;
}

function showComplete() {
  elements.workspace.hidden = true;
  elements.errorView.hidden = true;
  elements.completeView.hidden = false;
  elements.completeSummary.textContent =
    `${summary.include} included · ${summary.maybe} maybe · ${summary.exclude} not included.`;
  window.scrollTo({ top: 0, behavior: "auto" });
}

function beginReview(filter) {
  reviewFilter = filter;
  visibleIndices = photos
    .map((photo, index) => ({ photo, index }))
    .filter(({ photo }) => filter === "all" || photo.decision === "include")
    .map(({ index }) => index);
  if (!visibleIndices.length) return;
  currentIndex = visibleIndices[0];
  elements.completeView.hidden = true;
  renderPhoto();
}

function showTransientError(error) {
  setSaveStatus(error.message || "Could not save — try again", "error");
}

function showFatalError(error) {
  elements.workspace.hidden = true;
  elements.completeView.hidden = true;
  elements.errorView.hidden = false;
  elements.errorMessage.textContent = error.message || "Reload the page to try again.";
}

async function start() {
  try {
    const payload = await request("/api/state");
    photos = payload.photos;
    summary = payload.summary;
    renderSummary();
    const firstPending = photos.findIndex(photo => !photo.decision);
    if (firstPending === -1) {
      showComplete();
    } else {
      currentIndex = firstPending;
      renderPhoto();
    }
    elements.workspace.setAttribute("aria-busy", "false");
  } catch (error) {
    showFatalError(error);
  }
}

elements.excludeButton.addEventListener("click", () => decide("exclude"));
elements.maybeButton.addEventListener("click", () => decide("maybe"));
elements.includeButton.addEventListener("click", () => decide("include"));
elements.undoButton.addEventListener("click", undo);
elements.previousButton.addEventListener("click", () => navigate(neighborIndex(-1)));
elements.nextButton.addEventListener("click", () => navigate(neighborIndex(1)));
elements.comment.addEventListener("input", () => {
  elements.commentCount.textContent = String(elements.comment.value.length);
  scheduleCommentSave();
});
elements.reviewIncludedButton.addEventListener("click", () => beginReview("include"));
elements.reviewAllButton.addEventListener("click", () => beginReview("all"));
elements.retryButton.addEventListener("click", () => window.location.reload());

document.addEventListener("keydown", event => {
  const typing = event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLInputElement;
  if (typing || event.metaKey || event.ctrlKey || event.altKey) return;
  if (event.key === "1") decide("exclude");
  else if (event.key === "2") decide("maybe");
  else if (event.key === "3") decide("include");
  else if (event.key.toLowerCase() === "u") undo();
  else if (event.key === "ArrowLeft") navigate(neighborIndex(-1));
  else if (event.key === "ArrowRight") navigate(neighborIndex(1));
});

window.addEventListener("beforeunload", event => {
  if (!commentDirty) return;
  event.preventDefault();
  event.returnValue = "";
});

start();
