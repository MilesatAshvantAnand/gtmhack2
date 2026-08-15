const scenarios = {
  northstar: {
    kind: "Recommended demo",
    name: "Northstar Analytics",
    detail: "Active trial · permitted contact · partial competitor coverage",
    status: "ready",
    headline: "A verified competitor is active in public LinkedIn ads. Turn that signal into one focused ABM experiment.",
    fact: "Orbit Metrics is canonically verified and has a public ad observation. Public visibility is partial, so impressions, spend, clicks, creative, and targeting stay unknown.",
    actions: [
      ["Open one ZenABM experiment", "Review Orbit Metrics’ verified public-ad observation against Northstar’s campaign objective and choose one test.", "obs_001 · directional"],
      ["Prioritize the interested account", "Use ZenABM engagement context to prepare a human-reviewed first-week conversation.", "trial_fixture_001 · review required"],
      ["Measure the first-week outcome", "Record whether an experiment is created; do not claim causality from public-ad data.", "coverage: partial"],
    ],
    draft: "Hi {{first_name}}, we pulled together a first-week ABM brief with one evidence-linked experiment to consider. Would it be useful to review it together?",
  },
  optedOut: {
    kind: "Safety gate",
    name: "Harbor Studio",
    detail: "Active trial · contact opted out · flow stops before drafting",
    status: "blocked",
    reason: "This contact has opted out. The system stops before research, enrichment, or any draft is created.",
  },
  unknown: {
    kind: "Honest fallback",
    name: "Juniper Cloud",
    detail: "Active trial · public-ad evidence unavailable · asks for more data",
    status: "blocked",
    reason: "Public-ad coverage is unknown. The system does not turn missing information into a zero, a competitor claim, or a message draft.",
  },
};

const flowSteps = [
  ["Trial gatekeeper", "Checks active trial, identity, and marketing permission."],
  ["ABM + market analysts", "Read permitted campaign data and verified competitor context."],
  ["Unify enrichment", "Prepares an account brief or a DataTable - never auto-enrolls contacts."],
  ["Value synthesizer", "Ranks up to three evidence-linked next steps."],
  ["Policy guard", "Blocks unsupported claims, opt-outs, and sends."],
];

let selected = "northstar";
let running = false;
const cards = document.querySelector("#scenarioCards");
const flow = document.querySelector("#flow");
const runButton = document.querySelector("#runButton");
const resetButton = document.querySelector("#resetButton");
const status = document.querySelector("#runStatus");
const brief = document.querySelector("#briefSection");
const content = document.querySelector("#briefContent");

function renderCards() {
  cards.innerHTML = "";
  Object.entries(scenarios).forEach(([key, item]) => {
    const node = document.querySelector("#scenarioTemplate").content.cloneNode(true);
    const button = node.querySelector("button");
    button.setAttribute("aria-pressed", key === selected ? "true" : "false");
    button.addEventListener("click", () => { if (!running) { selected = key; reset(); renderCards(); } });
    node.querySelector(".scenario-kind").textContent = item.kind;
    node.querySelector(".scenario-name").textContent = item.name;
    node.querySelector(".scenario-detail").textContent = item.detail;
    cards.append(node);
  });
}

function renderFlow(active = -1, done = -1) {
  flow.innerHTML = flowSteps.map(([name, description], index) => `<li class="${index === active ? "active" : ""} ${index <= done ? "done" : ""}"><span class="num">0${index + 1}</span><strong>${name}</strong><small>${description}</small></li>`).join("");
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

async function runDemo() {
  if (running) return;
  running = true;
  runButton.disabled = true;
  brief.hidden = true;
  status.className = "run-status running";
  for (let step = 0; step < flowSteps.length; step += 1) {
    renderFlow(step, step - 1);
    status.textContent = `${flowSteps[step][0]} is working…`;
    await sleep(580);
    if (scenarios[selected].status === "blocked" && step === 0) break;
  }
  renderFlow(-1, scenarios[selected].status === "ready" ? 4 : 0);
  showBrief();
  running = false;
  runButton.disabled = false;
}

function showBrief() {
  const scenario = scenarios[selected];
  brief.hidden = false;
  brief.scrollIntoView({ behavior: "smooth", block: "start" });
  if (scenario.status === "blocked") {
    status.className = "run-status blocked";
    status.textContent = "Stopped safely - no enrichment, draft, or send was attempted.";
    content.innerHTML = `<article class="blocked-panel"><span class="tag">Safety stop</span><h3>${scenario.name}: the system did the safe thing.</h3><p>${scenario.reason}</p></article>`;
    return;
  }
  status.className = "run-status safe";
  status.textContent = "Plan ready for human review. No messages were sent.";
  content.innerHTML = `
    <div class="brief-grid">
      <article class="brief-main"><p class="meta">${scenario.name} · fixture run · 5-minute plan</p><h3>${scenario.headline}</h3><div class="fact"><strong>What we observed</strong><p>${scenario.fact}</p></div><div class="fact"><strong>What this does not claim</strong><p>Spend, clicks, creative, targeting, and causality are not available from this public source.</p></div></article>
      <div class="brief-side"><article class="mini"><span class="tag">3 next steps</span><ol class="action-list">${scenario.actions.map(([title, copy, evidence]) => `<li><strong>${title}</strong><span>${copy}</span><i class="evidence">Evidence: ${evidence}</i></li>`).join("")}</ol></article><article class="mini unify"><span class="tag">Unify bridge</span><h3>Account research, safely bounded</h3><p>In production, this step asks Unify for a DataTable or account brief. For this demo it uses a sanitized fixture and never enrolls a contact.</p><button id="unifyButton" type="button">Preview Unify handoff</button><p id="unifyResult" class="unify-result" hidden></p></article><article class="draft"><span class="tag">Draft only</span><h3>Human-reviewable email</h3><p>${scenario.draft}</p></article></div>
    </div>`;
  document.querySelector("#unifyButton").addEventListener("click", () => {
    const result = document.querySelector("#unifyResult");
    result.hidden = false;
    result.textContent = "Demo handoff complete: a bounded account brief is ready. Contacts remain un-enrolled and no sequence exists.";
  });
}

function reset() { brief.hidden = true; content.innerHTML = ""; status.className = "run-status"; status.textContent = "Ready when you are."; renderFlow(); }
runButton.addEventListener("click", runDemo);
resetButton.addEventListener("click", reset);
renderCards();
renderFlow();
