const MAX_CHARS = 100000;
const EXTENSIONS = {
  py: "python", js: "javascript", mjs: "javascript", jsx: "javascript", ts: "typescript", tsx: "typescript",
  java: "java", go: "go", rs: "rust", c: "c", h: "c", cpp: "cpp", cc: "cpp", hpp: "cpp", cs: "csharp",
  rb: "ruby", php: "php", kt: "kotlin", swift: "swift", sql: "sql", sh: "bash",
};

const $ = (id) => document.getElementById(id);
const form = $("analyze-form");
const codeInput = $("code");
const fileInput = $("file");
const languageSelect = $("language");
const typeSelect = $("analysis-type");
const button = $("analyze-btn");
const errorBox = $("error");
const results = $("results");
const charCount = $("char-count");

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = !message;
}

function updateCount() {
  charCount.textContent = `${codeInput.value.length} / ${MAX_CHARS}`;
}

function setLoading(loading) {
  button.disabled = loading;
  button.classList.toggle("loading", loading);
  button.querySelector(".label").textContent = loading ? "Analyzing…" : "Analyze";
  results.setAttribute("aria-busy", String(loading));
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;
  const text = await file.text();
  if (text.length > MAX_CHARS) {
    showError(`File is too large (${text.length} characters, max ${MAX_CHARS}).`);
    fileInput.value = "";
    return;
  }
  codeInput.value = text;
  updateCount();
  const ext = file.name.split(".").pop().toLowerCase();
  if (EXTENSIONS[ext]) languageSelect.value = EXTENSIONS[ext];
  showError("");
});

codeInput.addEventListener("input", updateCount);
codeInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) form.requestSubmit();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (button.disabled) return;
  const code = codeInput.value;
  if (!code.trim()) return showError("Paste or upload some code first.");
  if (code.length > MAX_CHARS) return showError(`Code is too long (max ${MAX_CHARS} characters).`);

  showError("");
  setLoading(true);
  try {
    const res = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, language: languageSelect.value, analysis_type: typeSelect.value }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(errorMessage(res.status, body));
    render(body, res.headers.get("X-Cache") === "HIT");
  } catch (err) {
    showError(err instanceof TypeError ? "Network error: could not reach the server." : err.message);
  } finally {
    setLoading(false);
  }
});

function errorMessage(status, body) {
  const detail = body && body.detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  return detail || `Request failed (HTTP ${status}).`;
}

function render(data, cached) {
  results.replaceChildren();

  const meta = el("div", "meta");
  meta.append(
    el("span", "chip", `Language: ${data.language}`),
    el("span", "chip", `Analysis: ${data.analysis_type}`),
    el("span", "chip", `${data.issues.length} issue${data.issues.length === 1 ? "" : "s"}`),
  );
  if (cached) meta.append(el("span", "chip", "Cached"));
  results.append(el("h2", null, "Summary"), meta, el("p", null, data.summary));

  results.append(el("h2", null, "Metrics"));
  const metrics = el("div", "metrics");
  const entries = [
    ["Complexity", data.metrics.complexity],
    ["Readability", data.metrics.readability],
    ["Test coverage (est.)", data.metrics.test_coverage_estimate],
    ["Lines of code", data.stats.code_lines],
    ["Total lines", data.stats.total_lines],
    ["Max nesting", data.stats.max_indent_depth],
  ];
  for (const [name, value] of entries) {
    const card = el("div", "metric");
    card.append(el("div", "name", name), el("div", "value", String(value)));
    metrics.append(card);
  }
  results.append(metrics);

  results.append(el("h2", null, "Issues"));
  if (data.issues.length === 0) {
    results.append(el("p", "muted", "No issues found."));
  } else {
    const list = el("ul", "issues");
    for (const issue of data.issues) {
      const item = el("li", `issue sev-${issue.severity}`);
      const header = el("header");
      header.append(
        el("span", "badge", issue.severity),
        el("span", "chip", issue.category),
        el("span", "muted", issue.line ? `Line ${issue.line}` : "Whole file"),
      );
      item.append(header, el("p", null, issue.description), el("p", "fix", `Fix: ${issue.suggestion}`));
      list.append(item);
    }
    results.append(list);
  }

  results.append(el("h2", null, "Suggestions"));
  const suggestions = el("ul", "suggestions");
  for (const s of data.suggestions) suggestions.append(el("li", null, s));
  results.append(data.suggestions.length ? suggestions : el("p", "muted", "No general suggestions."));
}

updateCount();
