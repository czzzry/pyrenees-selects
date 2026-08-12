const states = ["running", "paused", "attention", "lowdisk", "empty"];
const labels = {
  running: "Running",
  paused: "Paused safely",
  attention: "Completed with warnings",
  lowdisk: "Low disk space",
  empty: "No readable footage",
};

function icon(path) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
}
const icons = {
  lock: icon("M7 10V7a5 5 0 0 1 10 0v3M5 10h14v10H5z"),
  check: icon("m5 12 4 4L19 6"),
  media: icon("M4 6h16v12H4zM8 6v12m8-12v12"),
  pause: icon("M8 5v14m8-14v14"),
  alert: icon("M12 3 2 20h20zM12 9v5m0 3v1"),
  disk: icon("M4 5h16v14H4zM7 5v5h10V5m-9 9h8"),
  folder: icon("M3.5 6.5h6l2 2h9V19h-17z"),
};

function current() {
  const value = new URLSearchParams(location.search).get("state");
  return states.includes(value) ? value : "running";
}

function header(action = "") {
  return `<header class="appbar"><div class="wordmark"><span class="wordmark-mark">S</span><span>Selects</span></div><nav class="flow-nav" aria-label="Project flow"><span class="complete"><b>1</b>Project brief</span><span class="current"><b>2</b>Overnight plan</span><span><b>3</b>Review samples</span></nav><div class="appbar-actions">${action || `<span class="privacy-mark">${icons.lock} Local only</span>`}</div></header>`;
}

function progressHeader(title, body, tag) {
  return `<header class="state-heading"><div><span class="section-label">Coastal weekend</span><h1>${title}</h1><p>${body}</p></div>${tag ? `<span class="large-status">${tag}</span>` : ""}</header>`;
}

function progressBar(percent, label) {
  return `<div class="state-progress"><div><span>${label}</span><strong>${percent}%</strong></div><progress max="100" value="${percent}">${percent}%</progress></div>`;
}

function running() {
  return `${header('<span class="run-status"><i></i> Running locally</span>')}<main class="state-layout">${progressHeader("Preparation is underway.", "You can close other apps. Selects is working one source at a time and publishing completed samples as soon as they are valid.", "34 of 86 sources")}
  <div class="state-columns"><section class="state-panel">${progressBar(40, "Overall preparation")}
    <div class="current-task"><span class="task-icon">${icons.media}</span><div><span class="section-label">Analyzing source 35</span><strong>DJI_20240615_0054.MP4</strong><small>Finding sustained 6–9 second moments · 02:18 of 04:41 sampled</small></div><span class="live-dot">ACTIVE</span></div>
    <ol class="stage-list"><li class="done">${icons.check}<div><strong>Review copies</strong><small>34 complete · 1.9 GB</small></div><b>34 / 86</b></li><li class="active">${icons.media}<div><strong>Candidate analysis</strong><small>Measured throughput · 0.71× source duration</small></div><b>34 / 86</b></li><li>${icons.media}<div><strong>Sample rendering</strong><small>Published after validation</small></div><b>31 / 54–80</b></li></ol>
  </section><aside class="state-actions"><span class="section-label">Measured this run</span><strong class="eta">5h 42m remaining</strong><dl><div><dt>Elapsed</dt><dd>3h 11m</dd></div><div><dt>Available now</dt><dd>31 samples</dd></div><div><dt>Temporary space</dt><dd>2.1 of 3.4 GB</dd></div></dl><button class="primary">Review 31 completed samples</button><button class="secondary">Pause after this source</button><button class="text-button danger-text">Cancel preparation…</button><p>Sleep prevention is active and releases automatically when work stops.</p></aside></div></main>`;
}

function paused() {
  return `${header()}<main class="state-layout">${progressHeader("Paused at a safe checkpoint.", "Everything completed so far is saved. No FFmpeg process or sleep assertion is still running.", "Paused · 41 of 86")}
  <div class="state-columns"><section class="state-panel paused-panel"><div class="state-symbol">${icons.pause}</div><h2>Ready to continue with source 42</h2><p>The first 41 sources do not need to be processed again. Thirty-seven validated samples are already available for review.</p>${progressBar(48, "Saved progress")}<div class="checkpoint-list"><span>${icons.check} 41 review copies valid</span><span>${icons.check} 41 sources analyzed</span><span>${icons.check} 37 samples published</span></div></section><aside class="state-actions"><span class="section-label">Last checkpoint</span><strong class="eta">Today · 02:14</strong><dl><div><dt>Next source</dt><dd>42 of 86</dd></div><div><dt>Remaining estimate</dt><dd>4h 58m</dd></div><div><dt>Failures</dt><dd>0</dd></div></dl><button class="primary">Resume preparation</button><button class="secondary">Review 37 completed samples</button><button class="text-button danger-text">Cancel this run…</button></aside></div></main>`;
}

function attention() {
  return `${header('<span class="run-status warning-status">Completed with warnings</span>')}<main class="state-layout">${progressHeader("69 samples are ready. Four files need attention.", "The successful work is complete and reviewable. Failed sources did not stop the rest of the project.", "82 completed · 4 failed")}
  <div class="state-columns attention-columns"><section class="state-panel"><div class="panel-title"><div><h2>Files needing attention</h2><p>Retry after fixing the source, or skip it for this run.</p></div><span class="status-chip warning-chip">4 files</span></div><div class="failure-table"><div><strong>PXL_20240614_035900600.TS.mp4</strong><span>No readable analysis frames</span><button>Retry</button><button>Skip</button></div><div><strong>DJI_0099.MP4</strong><span>Source changed after planning</span><button>Rescan</button><button>Skip</button></div><div><strong>broken.mp4</strong><span>Invalid media container</span><button>Choose file</button><button>Skip</button></div><div><strong>card-copy-07.MOV</strong><span>Original is offline</span><button>Relink</button><button>Skip</button></div></div></section><aside class="state-actions"><span class="section-label">Successful output</span><strong class="eta">69 proposed moments</strong><dl><div><dt>Reviewable duration</dt><dd>8m 06s</dd></div><div><dt>Originals modified</dt><dd>Never</dd></div><div><dt>Sleep prevention</dt><dd>Released</dd></div></dl><button class="primary">Review available samples</button><button class="secondary">Retry all four</button><p>Skipping only affects this run. The files stay visible in the project.</p></aside></div></main>`;
}

function lowdisk() {
  return `${header()}<main class="state-layout compact-state">${progressHeader("There is not enough free space to start.", "Selects has not created any review media. Choose another cache location, free space, or review the originals without analysis.", "Preparation blocked")}
  <div class="state-columns"><section class="state-panel disk-panel"><div class="state-symbol alert-symbol">${icons.disk}</div><h2>2.3 GB more space is required</h2><div class="disk-meter"><span style="width:57%"></span><i style="left:57%"></i></div><div class="disk-labels"><span>3.1 GB available</span><span>5.4 GB required</span></div><dl class="disk-breakdown"><div><dt>Estimated review media</dt><dd>3.4 GB</dd></div><div><dt>Safety reserve</dt><dd>2.0 GB</dd></div><div><dt>Shortfall</dt><dd>2.3 GB</dd></div></dl></section><aside class="state-actions"><span class="section-label">Recovery</span><h2>Keep the originals where they are.</h2><p>Only the disposable cache needs another location.</p><button class="primary">Choose another cache folder</button><button class="secondary">Check free space again</button><button class="text-button">Review full originals without preparing</button></aside></div></main>`;
}

function empty() {
  return `${header()}<main class="state-layout compact-state">${progressHeader("No readable video was found.", "Your project brief is saved. Choose another folder or fix the files, then scan again.", "0 valid sources")}
  <div class="empty-state"><div class="state-symbol">${icons.folder}</div><h2>Choose the parent folder containing your originals</h2><p>Selects scans nested folders for MP4, MOV and M4V. It found three unsupported files and one empty folder in the previous location.</p><div class="empty-path">/Movies/Coastal weekend/exports</div><div class="empty-actions"><button class="primary">Choose another folder</button><button class="secondary">Scan this folder again</button></div><dl><div><dt>Target film</dt><dd>4:00</dd></div><div><dt>Shot rhythm</dt><dd>6–9 seconds</dd></div><div><dt>Creative direction</dt><dd>Saved</dd></div></dl></div></main>`;
}

const renderers = { running, paused, attention, lowdisk, empty };
function render() {
  const state = current();
  document.getElementById("prototype").innerHTML = `<div class="prototype-shell state-screen">${renderers[state]()}</div>`;
  document.getElementById("stateLabel").textContent = labels[state];
  document.title = `${labels[state]} · Selects state reference`;
}
function navigate(delta) { const index = states.indexOf(current()); const next = states[(index + delta + states.length) % states.length]; const url = new URL(location.href); url.searchParams.set("state", next); location.href = url; }
document.getElementById("previousState").addEventListener("click", () => navigate(-1));
document.getElementById("nextState").addEventListener("click", () => navigate(1));
document.addEventListener("keydown", event => { if (["INPUT","TEXTAREA","SELECT"].includes(event.target.tagName)) return; if (event.key === "ArrowLeft") navigate(-1); if (event.key === "ArrowRight") navigate(1); });
render();
if (new URLSearchParams(location.search).get("capture") === "1") document.querySelector(".variant-switcher")?.setAttribute("hidden", "");
