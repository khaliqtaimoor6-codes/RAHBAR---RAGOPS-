// Builds docs/report/RAHBAR-A3-Report.docx (Assignment 03 report, Part G).
//   npm install docx@9.5.1   (once, anywhere on NODE_PATH)
//   node docs/report/build_report.js
// Parts A, D and F (data side) are filled from our own runs (docs/RAGOPS.md,
// docs/evidence/a3/). Parts owned by Ali are yellow placeholders, edited in Word.
// After the first build, edit the .docx in Word; rebuild only if you want to start over.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, HeadingLevel,
  AlignmentType, WidthType, ShadingType, BorderStyle, LevelFormat, PageBreak, Footer,
  PageNumber, TableLayoutType, PageOrientation,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const SHOTS = path.join(ROOT, "docs", "screenshots");
const OUT = path.join(__dirname, "RAHBAR-A3-Report.docx");

const FONT = "Calibri";
const PAGE_W = 11906, PAGE_H = 16838, MARGIN = 1080;           // A4, 0.75 in margins
const TEXT_W = PAGE_W - 2 * MARGIN;                             // 9746 DXA
const border = { style: BorderStyle.SINGLE, size: 4, color: "B7B7B7" };
const borders = { top: border, bottom: border, left: border, right: border };

// ---------------------------------------------------------------- helpers
function runs(text, opts = {}) {
  // **bold** and `code` inside a string
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...opts }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...opts }));
    else out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: (opts.size || 20) - 2, ...opts }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...opts }));
  return out;
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 100 }, ...opts });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const bullet = (text) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: runs(text), spacing: { after: 40 } });
const TODO = (text) => new Paragraph({
  spacing: { after: 100 },
  children: [new TextRun({ text: "[ALI] " + text.replace(/`/g, ""), highlight: "yellow", italics: true })],
});
const todoCell = (text) => [new TextRun({ text: "[ALI] " + text, highlight: "yellow", italics: true, size: 17 })];

function table(widths, header, rows, size = 17) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (cells, head) => new TableRow({
    tableHeader: head,
    cantSplit: true,
    children: cells.map((c, i) => new TableCell({
      borders, width: { size: widths[i], type: WidthType.DXA },
      shading: head ? { fill: "DCE6F1", type: ShadingType.CLEAR, color: "auto" } : undefined,
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      children: [new Paragraph({
        children: Array.isArray(c) ? c : runs(String(c), { size, bold: head || undefined }),
      })],
    })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED,
    rows: [mk(header, true), ...rows.map((r) => mk(r, false))],
  });
}
const gap = () => new Paragraph({ spacing: { after: 60 }, children: [] });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}
function shot(label, file, caption) {
  const p = path.join(SHOTS, file);
  const { w, h, data } = pngSize(p);
  const maxW = 960, maxH = 600;                       // px at 96 dpi: landscape A4 text area
  const scale = Math.min(maxW / w, maxH / h, 1);
  return [
    new Paragraph({ keepNext: true, spacing: { before: 160, after: 60 }, children: [
      new TextRun({ text: label + "  ", bold: true }), ...runs(caption, { size: 18 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [
      new ImageRun({ type: "png", data, transformation: { width: Math.round(w * scale), height: Math.round(h * scale) },
        altText: { title: label, description: caption, name: label } })] }),
  ];
}

// ---------------------------------------------------------------- content
const body = [];

body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [
  new TextRun({ text: "RAHBAR RAGOps", bold: true, size: 40 })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [
  new TextRun({ text: "Assignment 03 · Software Construction and Development (CS4032) · Fall 2026", size: 22 })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [
  new TextRun({ text: "Taimoor Khaliq — ", size: 22 }), new TextRun({ text: "[roll number]", size: 22, highlight: "yellow" }),
  new TextRun({ text: "     Ali Haider Bajwa — ", size: 22 }), new TextRun({ text: "[roll number]", size: 22, highlight: "yellow" })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
  new TextRun({ text: "Repository: github.com/khaliqtaimoor6-codes/RAHBAR---RAGOPS-", size: 20 })] }));

body.push(H1("1. Overview"));
body.push(P("RAHBAR answers questions about FAST-NUCES rules only from the university's own documents, with citations, and abstains when the documents do not cover a question (Assignment 02). This assignment adds the RAGOps layer of Xu et al.: a data-management lifecycle (ingest, verify, update the data lake, update the retrieval sources), testing at three levels with a release gate, tracing and monitoring of every query, and coverage checks. Everything runs on minikube (3 GB, 2 CPUs): ingestion and evaluation are Jobs, data and traces live on PersistentVolumeClaims, thresholds are ConfigMaps. Embeddings: `nomic-embed-text` through Ollama; answers: `openai/gpt-oss-20b` on Groq, temperature 0.2. All numbers below come from our own runs; raw output is in `docs/evidence/a3/` and `eval/results/`."));

// ---- G1
body.push(H1("2. Figure 3 stages in RAHBAR"));
body.push(table([1500, 4300, 2046, 1900], ["Stage", "What our pipeline does", "File", "Missing"], [
  ["Ingest", "Init container mirrors the 9 public documents into the lake PVC and checks each SHA-256 against the manifest; new batches are copied into `inbox/`.", "`corpus/fetch.py`, `scripts/lake.sh`", "No push-based source; batches are copied by hand."],
  ["Verify", "Quality, completeness, recency, uniqueness per document, plus an advisory injection flag; failures go to `quarantine/<run>/` with a reason file; one JSON report per run.", "`indexer/pipeline/verify.py`, `ingest.py`", "No check of facts across documents."],
  ["Update data lake", "`current/`, `archive/<family>/<version>/`, `deleted/<run>/`, registry, cached extracted text (no re-OCR).", "`indexer/pipeline/lake.py`", "No retention policy for quarantine/deleted."],
  ["Update retrieval sources", "Reconcile Chroma with the registry: embed only new or changed chunks, metadata-only archive/restore, delete by `doc_id`; a new `index_id` invalidates the cache.", "`indexer/pipeline/reconcile.py`", "Not atomic across documents within one run."],
  ["Offline testing", todoCell("golden set, three-level suite, release gate"), todoCell("eval/…"), todoCell("…")],
  ["Live testing", "One trace per query (stdout + volume), `/metrics`, a summary over a time window, a tool that rebuilds the prompt of any trace.", "`api/app/services/trace.py`, `api/app/tools/`", "No alerting; metrics are pulled by hand."],
  ["Check coverage", todoCell("live-query log, coverage vs golden set"), todoCell("…"), todoCell("…")],
]));

// ---- G2
body.push(H1("3. RAGOps qualities (paper Table 2)"));
body.push(table([1500, 3600, 1450, 3196], ["Quality", "What we measure", "Threshold", "Evidence"], [
  ["Adaptability", "Chunks embedded when re-running on an unchanged corpus; time to build a candidate collection.", "0 chunks", "0 chunks in 3.3 s; candidates in 34 s and 55 s without re-download or re-OCR."],
  ["Monitorability", "Top-1 similarity, abstention rate, cache hit rate, p95 per stage, injections flagged, over a window.", "—", "16 traces: abstention 0.44, cache hit 0.25, 6 injected chunks dropped (D3)."],
  ["Observability", "Fields per trace record; per-stage latency.", "all D1 fields", "18 top-level fields; embed/cache/retrieve/rails/generate/total in every trace."],
  ["Traceability", "Rebuilt prompt hash equals the recorded hash.", "100 %", "MATCH on every trace checked (D2)."],
  ["Reliability", "Orphan chunks after delete; index after a vector-store restart.", "0; unchanged", "0 orphans in every run; after `chroma-0` restarted all 3 collections were intact."],
]));
body.push(TODO("add the offline-testing and gate thresholds (recall@5, faithfulness, p95, abstention) to the rows above."));

// ---- Results
body.push(H1("4. Results"));
body.push(H2("4.1 Part A: verification (A1) of Batch B"));
body.push(table([2700, 760, 860, 760, 760, 1150, 2756], ["Document", "quality", "complete", "recency", "unique", "action", "reason"], [
  ["b01 midterm notice", "PASS", "PASS", "PASS", "PASS", "index", ""],
  ["b02 library rules", "PASS", "PASS", "PASS", "PASS", "index", ""],
  ["b03 midterm COPY", "SKIP", "SKIP", "SKIP", "FAIL", "quarantine", "exact duplicate of b01 (same file hash)"],
  ["b04 library reformatted", "PASS", "PASS", "PASS", "FAIL", "quarantine", "exact duplicate of b02 (same text)"],
  ["b05 lab policy draft", "PASS", "PASS", "PASS", "PASS", "index", "arrived first"],
  ["b06 final exam notice", "PASS", "FAIL", "PASS", "PASS", "quarantine", "ends mid-sentence"],
  ["b07 scholarship PDF", "FAIL", "SKIP", "PASS", "PASS", "quarantine", "PdfminerException: Unexpected EOF"],
  ["b08 sports facilities", "PASS", "FAIL", "PASS", "PASS", "quarantine", "missing source, title, doc_version"],
  ["b09 fee structure 2027-28", "PASS", "PASS", "PASS", "PASS", "index", "supersedes the 2026-27 fee page"],
  ["b10 attendance notice", "PASS", "PASS", "PASS", "PASS", "index + flag", "\"Ignore all previous instructions\""],
  ["b11 lab policy", "PASS", "PASS", "PASS", "FAIL", "quarantine", "near-duplicate of b05, cosine 0.9997"],
  ["b12 transcript procedure", "PASS", "PASS", "PASS", "PASS", "index", ""],
], 16));
body.push(gap());
body.push(P("Every planted problem was caught. `NEAR_DUP_THRESHOLD` = 0.985: the most similar pair of genuinely different documents is Annual Report 2019-20 vs 2023-24 at 0.9606, the planted near-duplicate scored 0.9997. A PDF or HTML page dropped without metadata gets `source`, `doc_version` and `title` derived from the file (PDF dates and Title, first line); a rehearsal with two plain PDFs indexed both, while an HTML page with no date was quarantined for missing `doc_version`."));

body.push(H2("4.2 Part A: incremental update (A2)"));
body.push(table([3300, 1500, 4946], ["Run", "Chunks embedded", "Other"], [
  ["First run (9 documents, 24 OCR pages)", "1,008", "8 indexed, 1 archived (2023 rules, by recency); 370 s"],
  ["Same corpus again", "**0**", "9 unchanged, `index_id` kept (cache stays valid); 3.3 s"],
  ["Batch B", "26", "6 indexed, 5 quarantined, the 2026-27 fee page relabelled `superseded` (9 chunks)"],
  ["Delete `b12-transcript-request-procedure`", "0", "b12 chunks 4 → 0; orphan chunks 0; file kept in `deleted/<run>/`"],
  ["Restore `fee-structure-page` (rollback)", "**0**", "13 chunks relabelled; 2.7 s"],
]));
body.push(gap());
body.push(P("Two defects were found on the cluster and fixed with tests: (1) a byte-for-byte copy under another file name carried the original's `doc_id` in its front matter and was treated as \"unchanged\" instead of a duplicate (b03 in the first Batch B run); (2) the trace tool crashed on traces of cache hits."));

body.push(H2("4.3 Part B: offline testing at three levels"));
body.push(TODO("golden set (≥25: answerable/unanswerable/hard, human vs synthetic), module level (paraphrase vs unrelated cosine, gap, ms/chunk, determinism), component level (recall@3/5, MRR, nDCG@5, noise test), end-to-end (faithfulness + judge agreement, abstention, citation validity, latency p50/p95), stochasticity (two seeded runs)."));
body.push(H2("4.4 Part C: change experiment and release gate"));
body.push(TODO("baseline vs candidate on all three levels, gate thresholds and their justification, one failing and one passing candidate, the release decision. Candidate collections `rahbar-cand-cs300` (chunk 300, 834 chunks) and `rahbar-cand-cs100` (chunk 100, 1,262 chunks) are already built on the cluster."));

body.push(H2("4.5 Part D: observability and traceability"));
body.push(table([3800, 1100, 4846], ["Question", "Answered", "Behaviour"], [
  ["CGPA to stay off academic warning", "yes", "2.00, cites 5.4 Academic Warning/Probation (2026 handbook)"],
  ["Until when can a student withdraw", "yes", "last day of the makeup week (2026 edition)"],
  ["Is attendance optional?", "yes", "No; the injected Batch B chunks were dropped by the rail before the model"],
  ["What did the 2023 rules say about withdrawal", "yes", "last day of classes: the archived version, retrieved because the question asks for it"],
  ["How many guests at convocation (new PDF)", "yes", "two guests, cites the convocation notice ingested in the rehearsal batch"],
  ["How do I apply for a hostel room", "no", "the model declined (not in the corpus)"],
  ["Capital of France", "no", "relevance floor 0.66: abstained without a model call"],
]));
body.push(gap());
body.push(bullet("**D1** every query writes one JSON line (stdout and the `rahbar-traces` volume) with trace id, timestamp, query, rewritten query (none), embedding model and Ollama digest, collection and `index_id`, retrieved chunk ids with doc ids, versions and scores, filters, dense vs reranked order, the exact context, prompt hash and template, model parameters, response, citations, guardrail actions, per-stage latency and cache result."));
body.push(bullet("**D2** `app.tools.trace_show <id>` rebuilds the prompt from the recorded context and compares its SHA-256 with the recorded one: MATCH."));
body.push(bullet("**D3** `/metrics` exposes `rahbar_top1_similarity`, `rahbar_abstention_rate`, `rahbar_cache_hit_ratio`, `rahbar_stage_seconds{stage}` and `rahbar_injection_flagged_total`; `app.tools.trace_summary --since 6h` summarises the log (16 traces: top-1 p50 0.755, abstention 0.44, cache hit 0.25, embed p50 65 ms, generate p50 480 ms, total p95 10.0 s, dominated by the first, cold embedding)."));
body.push(bullet("**D4** the retrieval rail drops chunks that read like instructions or whose document was flagged at ingest; each action is a `guardrails` entry in the trace. With Batch B's injected notice, 3 chunks were dropped and the answer stayed \"No\"."));
body.push(TODO("D5: one wrong or abstained answer from Part B, root cause from its trace only, 5 lines."));

body.push(H2("4.6 Part E: drift and coverage"));
body.push(TODO("live query log (≥40), coverage vs golden set with a justified threshold, uncovered topics, drift after Batch B (the fee answers now come from the 2027-28 version until rolled back), ≥6 new golden questions and the coverage before/after."));

body.push(H2("4.7 Part F: Kubernetes"));
body.push(table([2700, 7046], ["Item", "Object / evidence"], [
  ["F1 deploy", "Deployment `api` (2 replicas on the laptop), StatefulSet `chroma` with `volumeClaimTemplates`, Service `api`; PVC `rahbar-lake` holds the lake, quarantine and archive and survives restarts."],
  ["F2 ingestion", "Job `ingest` and nightly CronJob `ingest` (`concurrencyPolicy: Forbid`, plus a lock file in the lake); the only writer to Chroma (NetworkPolicy admits only `app=api` and `app=indexer`)."],
  ["F2 evaluation, gate ConfigMap", todoCell("eval Job, result file on a volume, failing exit on gate failure, threshold change without rebuild")],
  ["F3 controlled release", todoCell("candidate Deployment + Service + collection, gate, rolling update with maxUnavailable 0, rollout undo, trace showing the previous collection and embedding version")],
  ["F4 observability", "Trace lines in `kubectl logs` and on the `rahbar-traces` volume; `/metrics` through `kubectl port-forward`."],
]));
body.push(gap());
body.push(table([1700, 4300, 3746], ["Workload (F5)", "Measured", "requests → limits"], [
  ["api", "5–8m CPU, 69–95 Mi", "50m / 128Mi → 500m / 256Mi"],
  ["chroma", "2–24m CPU, 159 Mi with 3 collections", "25m / 192Mi → 500m / 384Mi"],
  ["ingest Job", "peak RSS 111 Mi embedding 1,262 chunks, 85 Mi no-op; OCR peak 186 Mi / 1411m (A2)", "250m / 256Mi → 1500m / 512Mi"],
  ["eval Job", todoCell("measure"), todoCell("set")],
]));
body.push(gap());
body.push(P("A Job that finishes in under a minute is never sampled by metrics-server, so the ingestion Job logs its own peak RSS."));

// ---- G4
body.push(H1("5. Short answers"));
body.push(P("**(a)** Uniqueness caught the most problems in Batch B (3 of 7: a byte copy, a re-wrapped text copy, a near-duplicate); completeness caught 2, quality 1, and recency handled the newer fee page. At first we missed the byte copy that reused the original's `doc_id` (fixed). We would still not catch a new, well-formed, unique document that is wrong or contradicts another policy; a contradiction check (NLI or an LLM) over documents on the same topic would. Which copy of a near-duplicate survives depends on arrival order; preferring the newer `doc_version` would fix that."));
body.push(TODO("(b) a module-level metric that looked fine while a component or end-to-end metric did not, or why we did not see one."));
body.push(P("**(c)** We archive superseded versions: their chunks stay indexed with `superseded=true` and retrieval filters them out unless a question asks for an older edition. Deleting them would break rollback (a restore relabels 13 chunks in 2.7 s with no re-embedding; after a delete it means re-fetching and re-embedding), questions about older editions (the 2023 withdrawal rule was answered from the archive), and audits of old traces whose chunk ids would point at nothing. Operator deletions move the file to `deleted/<run>/`, so even those are recoverable."));
body.push(TODO("(d) the metric we trust least, and why."));
body.push(TODO("(e) the hardest idea of the paper to apply and what we changed. Taimoor's half: verification needs metadata the public PDFs do not carry, so we derive it from the file and record that it was derived; and the paper's single update step became two (lake registry, then reconcile each collection)."));
body.push(P("**(f)** Job `ingest` (with the CronJob's `concurrencyPolicy: Forbid` and a lake lock) is the only writer to the vector store, enforced by NetworkPolicy `chroma-from-api-and-indexer`. PVC `rahbar-lake` holds the data lake, quarantine, archive and reports. StatefulSet `chroma` with its volume holds the retrieval sources. ConfigMap `rahbar-config` holds the verification thresholds, `NEAR_DUP_THRESHOLD`, `INJECTION_ACTION` and the embedding pin `EMBED_MODEL`. PVC `rahbar-traces` plus stdout give traceability. The api's readiness probe refuses traffic when the index was built with another embedding model. Secret `rahbar-secret` holds the LLM key, created from the command line."));

// ---- contribution + AI
body.push(H1("6. Contribution and AI statement"));
body.push(table([2400, 7346], ["Member", "Work"], [
  ["Taimoor Khaliq", "Part A (verification stage, data lake, incremental update, Batch B), Part D1–D4 (trace record, trace tool, metrics and summary, injection rail), Part F1, F2 ingestion, F4, F5 (PVCs, ingestion Job and CronJob, traces on stdout and a volume, measured resources), repository setup, cluster runs and evidence for these parts."],
  ["Ali Haider Bajwa", todoCell("Parts B, C, E, D5, F2 evaluation Job and gate ConfigMap, F3 controlled release.")],
]));
body.push(gap());
body.push(new Paragraph({ spacing: { after: 100 }, children: [
  new TextRun({ text: "AI statement (draft, agree on the wording together): ", bold: true }),
  new TextRun({ text: "We used Claude Code (Anthropic) to help write code, tests, Kubernetes manifests and drafts of this report. Every number comes from runs of our own pipeline on our own cluster, and both members reviewed the work and can explain every part of it.", highlight: "yellow" })] }));

// ---- appendix (its own landscape section: wide terminal screenshots stay readable)
const appendix = [];
const _push = body.push.bind(body);
body.push = (...items) => appendix.push(...items);
body.push(H1("Appendix: screenshots"));
body.push(P("Each screenshot is a real PowerShell window on our laptop, running the command shown against our minikube cluster (captured with `scripts/capture_screenshots.ps1`)."));
body.push(...shot("A1", "A1.png", "Verification report for Batch B: pass/fail per check with reasons (`scripts/lake.ps1 report`)."));
body.push(...shot("A1b", "A1b.png", "The byte copy b03 quarantined after the fix."));
body.push(...shot("A2", "A2.png", "Second ingestion on the unchanged corpus: 0 chunks embedded, 0 orphans, chunks per doc_id."));
body.push(...shot("D1", "D1.png", "One full trace record, read with `kubectl logs` (also F4)."));
body.push(...shot("D2 (1/3)", "D2-1.png", "Trace tool: the trace header, retrieved chunks and the context sent to the model."));
body.push(...shot("D2 (2/3)", "D2-2.png", "Trace tool: the rebuilt system prompt."));
body.push(...shot("D2 (3/3)", "D2-3.png", "Trace tool: the rebuilt user message, prompt hash MATCH, response and citations."));
body.push(...shot("D3", "D3.png", "Trace summary over a time window."));
body.push(...shot("F1", "F1.png", "`kubectl get all,pvc,configmap,cronjob,job` for our namespace."));
body.push(...shot("F2", "F2.png", "Logs of a completed ingestion Job."));
body.push(...shot("F5", "F5.png", "`kubectl top` for the measured resources."));
body.push(TODO("B: evaluation summary (three levels). C: gate failing and gate passing. E: coverage before and after. F: logs of a completed evaluation Job; the gate result changing after a ConfigMap edit; `kubectl rollout status` and `kubectl rollout undo` with a trace afterwards."));

// ---------------------------------------------------------------- document
function footer() {
  return new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
    new TextRun({ children: ["Page ", PageNumber.CURRENT], size: 16 })] })] });
}
const doc = new Document({
  creator: "Taimoor Khaliq, Ali Haider Bajwa",
  title: "RAHBAR RAGOps: Assignment 03 report",
  styles: {
    default: { document: { run: { font: FONT, size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "1F3864" },
        paragraph: { spacing: { before: 220, after: 100 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 22, bold: true, color: "2E5395" },
        paragraph: { spacing: { before: 160, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
    alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: { default: footer() },
    children: body,
  }, {
    properties: { page: { size: { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.LANDSCAPE },
      margin: { top: 720, bottom: 720, left: MARGIN, right: MARGIN } } },
    footers: { default: footer() },
    children: appendix,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote " + OUT); });
