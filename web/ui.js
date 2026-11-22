const form = document.querySelector("#draft-form");
const website = document.querySelector("#website");
const generate = document.querySelector("#generate");
const sample = document.querySelector("#sample");
const progress = document.querySelector("#progress");
const error = document.querySelector("#error");
const result = document.querySelector("#result");
const heading = document.querySelector("#result-heading");
const copy = document.querySelector("#copy");
const copyStatus = document.querySelector("#copy-status");
const lines = document.querySelector("#lines");
const sourceLink = document.querySelector("#source-link");
let opener = "";

async function draft(payload) {
  generate.disabled = sample.disabled = true;
  error.hidden = result.hidden = true;
  progress.textContent = payload.sample ? "Drafting the example…" : "Reading the website and drafting an opener…";
  progress.hidden = false;
  try {
    const response = await fetch("/api/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(45000),
    });
    const data = await response.json();
    if (!response.ok) {
      error.textContent = data.error;
      error.hidden = false;
      return;
    }
    opener = data.lines.join("\n");
    lines.replaceChildren(...data.lines.map((line) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      return paragraph;
    }));
    const { url, excerpt, metadata_field: metadataField } = data.source;
    document.querySelector("#excerpt").textContent = excerpt;
    document.querySelector("#source-heading").textContent = metadataField ? "Homepage metadata" : "Homepage excerpt";
    const sourceNote = document.querySelector("#source-note");
    sourceNote.hidden = !metadataField;
    sourceNote.textContent = metadataField ? `In the page source, look for the ${metadataField} meta tag.` : "";
    const sourceUrl = new URL(url, window.location.origin);
    if (!metadataField) sourceUrl.hash = `:~:text=${encodeURIComponent(excerpt).replace(/-/g, "%2D")}`;
    sourceLink.href = sourceUrl.href;
    document.querySelector("#method").textContent = data.fallback
      ? "Built-in drafting rules · local model unavailable"
      : data.method;
    copy.textContent = "Copy opener";
    copyStatus.textContent = "";
    result.hidden = false;
    heading.focus();
  } catch {
    error.textContent = "The draft could not be loaded. Try again.";
    error.hidden = false;
  } finally {
    progress.hidden = true;
    generate.disabled = sample.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  draft({ url: website.value.trim() });
});
sample.addEventListener("click", () => draft({ sample: true }));
copy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(opener);
    copy.textContent = "Copied";
    copyStatus.textContent = "Opener copied to your clipboard.";
  } catch {
    const range = document.createRange();
    range.selectNodeContents(lines);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    copyStatus.textContent = "Opener selected. Use your device’s copy command.";
  }
});
