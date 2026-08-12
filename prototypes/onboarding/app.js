const variants = ["A", "B", "C"];
const names = {
  A: "1 · Project brief",
  B: "2 · Overnight plan",
  C: "3 · Review samples",
};

const mediaImage = "../../docs/assets/readme-train.jpg";

function icon(name) {
  const icons = {
    folder: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h6l2 2h9v9.5a2 2 0 0 1-2 2h-15z"/><path d="M3.5 6.5v-2h6l2 2"/></svg>',
    lock: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>',
    film: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 5v14M17 5v14M3 9h4M17 9h4M3 15h4M17 15h4"/></svg>',
    moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 15.5A8 8 0 0 1 8.5 4.5 8 8 0 1 0 19.5 15.5Z"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>',
    shield: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 20 6v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z"/><path d="m8.5 12 2.3 2.3 4.8-5"/></svg>',
    spark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z"/></svg>',
    comment: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v11H9l-4 4z"/></svg>',
  };
  return icons[name] || "";
}

function shell(content, { stage, action = "", className = "" } = {}) {
  return `
    <div class="prototype-shell ${className}">
      <header class="appbar">
        <div class="wordmark"><span class="wordmark-mark">S</span><span>Selects</span></div>
        <nav class="flow-nav" aria-label="New project progress">
          ${variants.map((key, index) => `<span class="${stage === key ? "current" : variants.indexOf(stage) > index ? "complete" : ""}"><b>${index + 1}</b>${names[key].split(" · ")[1]}</span>`).join("")}
        </nav>
        <div class="appbar-actions">${action || `<span class="privacy-mark">${icon("lock")} Local only</span>`}</div>
      </header>
      ${content}
    </div>`;
}

function variantA() {
  return shell(`
    <main class="brief-layout">
      <section class="brief-intro">
        <div class="brief-copy">
          <span class="section-label">New project</span>
          <h1>Tell Selects what kind of film you want.</h1>
          <p class="lede">Point it at the source footage, set the target duration and choose a rough shot rhythm. Selects will prepare more good options than the final cut needs.</p>
        </div>
        <div class="outcome-strip" aria-label="What this project creates">
          <span>${icon("moon")} Prepare overnight</span>
          <span>${icon("film")} Review proposed moments</span>
          <span>${icon("shield")} Finish with originals in Resolve</span>
        </div>
      </section>

      <form class="project-brief" id="guidedForm">
        <section class="form-section source-section">
          <div class="form-heading"><span class="form-number">01</span><div><h2>Source footage</h2><p>Select one parent folder. Nested folders are included.</p></div></div>
          <label class="field-label" for="folderPath">Footage folder</label>
          <div class="folder-picker">
            <span class="field-icon">${icon("folder")}</span>
            <input id="folderPath" name="source_path" placeholder="Choose the folder containing your originals" aria-label="Footage folder">
            <button id="chooseFolder" class="secondary" type="button">Choose folder</button>
          </div>
          <p class="field-help">MP4, MOV and M4V · originals stay exactly where they are</p>
        </section>

        <section class="form-section goal-section">
          <div class="form-heading"><span class="form-number">02</span><div><h2>Film goal</h2><p>These are planning targets, not hard limits.</p></div></div>
          <div class="goal-grid">
            <label class="input-field"><span>Project name</span><input name="project_name" value="Coastal weekend"></label>
            <label class="input-field"><span>Final format</span><select name="orientation"><option>Landscape · 16:9</option><option>Portrait · 9:16</option><option>Decide later</option></select></label>
            <label class="input-field duration-field"><span>Target film length</span><div class="unit-input"><input id="targetMinutes" name="target_minutes" type="number" value="4" min="1" max="180"><b>minutes</b></div><small>Used to pace the first assembly.</small></label>
            <fieldset class="rhythm-field"><legend>Typical shot length</legend><div class="rhythm-options">
              <label><input type="radio" name="rhythm" value="4"><span><b>3–5 sec</b><small>Energetic</small></span></label>
              <label><input type="radio" name="rhythm" value="8" checked><span><b>6–9 sec</b><small>Balanced</small></span></label>
              <label><input type="radio" name="rhythm" value="13"><span><b>10–16 sec</b><small>Observational</small></span></label>
            </div><small>A starting rhythm. Every proposed moment can be shorter or longer.</small></fieldset>
          </div>
        </section>

        <section class="form-section direction-section">
          <div class="form-heading"><span class="form-number">03</span><div><h2>Creative direction</h2><p>Optional, but useful when several moments are equally strong.</p></div></div>
          <label class="input-field"><span>What should the film feel like?</span><textarea name="creative_direction" rows="3">A relaxed travel film that starts quietly, keeps brief natural conversations, and builds toward the mountain views.</textarea></label>
          <details class="advanced-options"><summary>Selection breadth and advanced options</summary><div class="advanced-grid"><label class="input-field"><span>Candidate coverage</span><select name="candidate_coverage"><option>Generous · about 2× target duration</option><option>Focused · about 1.25× target</option><option>Broad · about 3× target</option></select></label><label class="input-field"><span>Source audio</span><select name="audio_preference"><option>Surface speech and distinctive sounds</option><option>Prefer visual moments</option><option>Preserve all source audio options</option></select></label></div></details>
        </section>

        <footer class="brief-footer">
          <div class="brief-summary"><span>Expected review set</span><strong>About 54–80 proposed moments</strong><small>roughly 8 minutes of options for a 4-minute film</small></div>
          <button class="primary" id="scanFolder" type="button">Scan footage and build preparation plan <span>→</span></button>
        </footer>
      </form>
    </main>
  `, { stage: "A", className: "brief-screen" });
}

function variantB() {
  return shell(`
    <main class="plan-layout">
      <header class="plan-heading">
        <div><span class="section-label">Coastal weekend</span><h1>Your overnight run is ready.</h1><p>Selects inspected 86 source clips and made a preparation plan for this Mac. Nothing has been copied or changed yet.</p></div>
        <button class="secondary" id="editBrief" type="button">Edit project brief</button>
      </header>

      <section class="project-recap" aria-label="Project brief summary">
        <div><span>Source</span><strong>6 h 14 m</strong><small>86 clips · 97.8 GB</small></div>
        <div><span>Target film</span><strong>4:00</strong><small>Landscape · 16:9</small></div>
        <div><span>Shot rhythm</span><strong>6–9 sec</strong><small>Balanced</small></div>
        <div><span>Expected output</span><strong>54–80</strong><small>proposed moments</small></div>
      </section>

      <div class="plan-columns">
        <section class="run-plan">
          <div class="panel-title"><div><h2>What Selects will do</h2><p>Every result stays connected to its full original.</p></div><span class="status-chip">Ready</span></div>
          <ol class="run-stages">
            <li><span class="stage-icon">${icon("film")}</span><div><strong>Prepare smooth review copies</strong><small>720p local copies make 4K and HEVC footage responsive on this Mac.</small></div><b>≈ 2h</b></li>
            <li><span class="stage-icon">${icon("spark")}</span><div><strong>Find sustained candidate moments</strong><small>Sample movement, clarity and continuity; one bad file will not stop the run.</small></div><b>≈ 5–7h</b></li>
            <li><span class="stage-icon">${icon("film")}</span><div><strong>Render a review contact sheet</strong><small>54–80 lightweight samples, plus full-source playback for every suggestion.</small></div><b>≈ 35m</b></li>
          </ol>
          <div class="issues-row"><span class="good">82 ready</span><span>7 portrait</span><span>29 without audio</span><span class="warning">4 need attention</span></div>
        </section>

        <aside class="run-card">
          <div class="moon-icon">${icon("moon")}</div>
          <span class="section-label">Estimated on this Intel Mac</span>
          <strong class="run-time">7–10 hours</strong>
          <p>Plug in power and leave Selects open. The queue resumes at the next file if interrupted.</p>
          <dl><div><dt>Temporary space</dt><dd>3.4 GB</dd></div><div><dt>Uploaded</dt><dd>0 bytes</dd></div><div><dt>Originals modified</dt><dd>Never</dd></div></dl>
          <label class="check-option"><input name="prevent_sleep" type="checkbox" checked><span>Prevent this Mac from sleeping while the run is active</span></label>
          <button id="startOvernight" class="primary" type="button">Start overnight preparation</button>
          <button class="text-button" type="button">Skip analysis and review full sources now</button>
        </aside>
      </div>
      <p class="honesty-note">Time is an estimate. Codec, drive speed and thermal limits can change it. You can review completed samples while the rest continue.</p>
    </main>
  `, { stage: "B", className: "plan-screen", action: '<span class="privacy-mark">' + icon("lock") + ' 0 bytes uploaded</span>' });
}

const samples = [
  { time: "00:14–00:22", title: "Train enters the tree line", source: "DJI_0054.MP4", score: "Strong continuity", position: "50% 63%", duration: "8.2 s" },
  { time: "00:41–00:49", title: "Clouds clear over the ridge", source: "DJI_0118.MP4", score: "Scenic movement", position: "68% 34%", duration: "7.8 s" },
  { time: "01:05–01:13", title: "Approach across the bridge", source: "PXL_20240615.mp4", score: "Useful transition", position: "22% 52%", duration: "8.0 s" },
  { time: "00:08–00:17", title: "Morning light on the valley", source: "DJI_0031.MP4", score: "Color and detail", position: "78% 78%", duration: "9.1 s" },
  { time: "00:53–01:01", title: "A quiet pause at the lake", source: "PXL_20240617.mp4", score: "Matches brief", position: "38% 42%", duration: "8.4 s" },
  { time: "02:14–02:21", title: "Train disappears behind trees", source: "DJI_0054.MP4", score: "Possible ending", position: "48% 58%", duration: "7.2 s" },
];

function sampleCards() {
  return samples.map((sample, index) => `<button class="sample-card ${index === 0 ? "active" : ""}" type="button" data-sample="${index}">
    <span class="sample-frame"><img src="${mediaImage}" alt=""><i>${index + 1}</i><b>▶</b></span>
    <span class="sample-copy"><span class="sample-time">${sample.time} · ${sample.duration}</span><strong>${sample.title}</strong><small>${sample.source}</small><em>${sample.score}</em></span>
  </button>`).join("");
}

function variantC() {
  return shell(`
    <main class="review-layout">
      <aside class="review-sidebar">
        <header><span class="section-label">Coastal weekend</span><h2>Proposed moments</h2><p><strong>62</strong> ready · 7 still processing</p></header>
        <label class="search-field"><span>⌕</span><input name="sample_search" placeholder="Search filenames or notes" aria-label="Search proposed moments"></label>
        <div class="review-filters"><button class="active" type="button">All 69</button><button type="button">Unreviewed</button><button type="button">Keeps</button></div>
        <div class="sample-list">${sampleCards()}</div>
      </aside>

      <section class="review-player">
        <header class="source-heading"><div><span class="sample-time">PROPOSAL 01 OF 69</span><h1 id="sampleTitle">Train enters the tree line</h1><p id="sampleSource">DJI_0054.MP4 · original 4K · 29.97 fps · audio</p></div><button class="secondary compact-button" type="button">Open full source</button></header>
        <div class="actual-video"><img id="viewerImage" src="${mediaImage}" alt="Train moving through a green landscape"><span class="proposal-window">Proposed range · <b id="viewerTime">00:14–00:22</b></span><button class="play-button" type="button" aria-label="Play proposed range">▶</button></div>
        <div class="transport"><button type="button">Set In <kbd>I</kbd></button><button class="play-range" type="button">▶ Play proposed range</button><button type="button">Set Out <kbd>O</kbd></button></div>
        <div class="source-timeline"><div class="time-labels"><span>00:00</span><strong id="rangeLabel">8.2 seconds proposed</strong><span>02:28</span></div><div class="timeline-track"><span class="range-window"></span><i class="playhead"></i></div></div>
        <div class="why-row"><span>${icon("spark")}</span><div><strong>Why Selects surfaced this</strong><p>Continuous scenic movement, stable exposure and a clear subject entrance. Verify against the full source before keeping it.</p></div></div>
      </section>

      <aside class="decision-pane">
        <div class="decision-heading"><span class="section-label">Your decision</span><h2>Does this moment belong?</h2><p>Adjust the range, then keep it, leave it as an alternate, or skip it.</p></div>
        <fieldset class="decision-options"><legend>Decision</legend><label><input type="radio" name="decision" checked><span>Keep</span></label><label><input type="radio" name="decision"><span>Maybe</span></label><label><input type="radio" name="decision"><span>Skip</span></label></fieldset>
        <label class="input-field comment-field"><span>${icon("comment")} Comment</span><textarea name="comment" rows="5" placeholder="What should happen in the final edit?">Keep the train sound. Start just before it enters frame.</textarea></label>
        <div class="decision-fields"><label class="input-field"><span>Story role</span><select name="story_role"><option>Opening</option><option>Transition</option><option>Peak</option><option>Ending</option></select></label><label class="input-field"><span>Source audio</span><select name="audio_intent"><option>Preserve</option><option>Important speech</option><option>Background only</option><option>Mute</option></select></label></div>
        <button id="saveReview" class="primary save-review" type="button">Save and review next <span>→</span></button>
        <div class="review-progress"><span><b id="reviewedCount">12</b> of 69 reviewed</span><div><i></i></div><small>Unused keeps remain available as alternates.</small></div>
      </aside>
    </main>
  `, { stage: "C", className: "review-screen", action: '<span class="run-status"><i></i> Preparing · 7 remaining</span>' });
}

const renderers = { A: variantA, B: variantB, C: variantC };

function currentVariant() {
  const value = new URLSearchParams(window.location.search).get("variant")?.toUpperCase();
  return variants.includes(value) ? value : "A";
}

function goTo(key) {
  const url = new URL(window.location.href);
  url.searchParams.set("variant", key);
  window.location.href = url;
}

function render() {
  const key = currentVariant();
  document.getElementById("prototype").innerHTML = renderers[key]();
  document.getElementById("variantLabel").textContent = names[key];
  document.title = `${names[key]} · Selects product flow`;
  wireInteractions(key);
}

function navigate(delta) {
  const index = variants.indexOf(currentVariant());
  goTo(variants[(index + delta + variants.length) % variants.length]);
}

function wireInteractions(key) {
  if (key === "A") {
    document.getElementById("chooseFolder")?.addEventListener("click", () => {
      document.getElementById("folderPath").value = "/Movies/Coastal weekend";
    });
    document.getElementById("scanFolder")?.addEventListener("click", () => goTo("B"));
  }
  if (key === "B") {
    document.getElementById("editBrief")?.addEventListener("click", () => goTo("A"));
    document.getElementById("startOvernight")?.addEventListener("click", (event) => {
      event.currentTarget.textContent = "Preparation started · view completed samples →";
      event.currentTarget.addEventListener("click", () => goTo("C"), { once: true });
    });
  }
  if (key === "C") {
    document.querySelectorAll("[data-sample]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-sample]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const sample = samples[Number(button.dataset.sample)];
      document.getElementById("sampleTitle").textContent = sample.title;
      document.getElementById("sampleSource").textContent = `${sample.source} · original 4K · 29.97 fps · audio`;
      document.getElementById("viewerTime").textContent = sample.time;
      document.getElementById("rangeLabel").textContent = `${sample.duration} proposed`;
      document.getElementById("viewerImage").style.objectPosition = sample.position;
    }));
    document.getElementById("saveReview")?.addEventListener("click", (event) => {
      const button = event.currentTarget;
      const count = document.getElementById("reviewedCount");
      count.textContent = String(Number(count.textContent) + 1);
      button.textContent = "Saved · loading next moment…";
      setTimeout(() => { button.innerHTML = "Save and review next <span>→</span>"; }, 650);
    });
  }
}

document.getElementById("previousVariant").addEventListener("click", () => navigate(-1));
document.getElementById("nextVariant").addEventListener("click", () => navigate(1));
document.addEventListener("keydown", (event) => {
  const target = event.target;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable) return;
  if (event.key === "ArrowLeft") navigate(-1);
  if (event.key === "ArrowRight") navigate(1);
});

render();
if (new URLSearchParams(window.location.search).get("capture") === "1") {
  document.querySelector(".variant-switcher")?.setAttribute("hidden", "");
}
