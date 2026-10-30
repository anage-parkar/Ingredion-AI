// Assemble and write both build guides.
const path = require("path");
const { buildDoc } = require("./lib");
const shared = require("./shared");
const A = require("./agent_a");
const B = require("./agent_b");

const OUT_DIR = process.argv[2] || ".";
const DATE = "26 October 2026";
const AUTHOR = "Abhishek Nage";
const ORG = "Parkar";
const BASIS = "Statement of Work No. 07, Ingredion redline v2 (20 October 2026); Order Intake and Pre-bill Validation WBS (23 October 2026); client requirements list v1.2; the Ingredion/ code baseline as of 23 October 2026";

function assemble(mod) {
  const a = mod.agent;
  return [
    ...shared.howToUse(a),
    ...mod.whatYouBuild(),
    ...shared.week0(a),
    ...mod.timeline(),
    ...shared.platform(a),
    ...shared.model(a),
    ...shared.documentAI(a),
    ...mod.steps(),
    ...mod.connectors(),
    ...mod.reviewScreen(),
    ...shared.observability(a),
    ...shared.cicd(a),
    ...mod.testing(),
    ...shared.production(a),
    ...mod.deliverables(),
    ...shared.appendices(a),
  ];
}

(async () => {
  const a = await buildDoc({
    kicker: "INGREDION AGENTIC AI FACTORY · SOW NO. 07 PART A · BUILD GUIDE",
    title: "Agent A build guide: Email Order Intake Agent on Google Cloud",
    subtitle: "Step-by-step plan to build, test, release and hand over steps A1 to A10, with the component deadlines of the SOW plan",
    author: AUTHOR, org: ORG, date: DATE, version: "1.0", basis: BASIS,
    keywords: "Ingredion, Email Order Intake, Agent A, Google Cloud, Vertex AI, Gemini, Document AI, Cloud Run, SOW No. 07",
    header: "Agent A build guide · Email Order Intake · Parkar internal",
  }, assemble(A), path.join(OUT_DIR, "Build-Guide-Agent-A-Email-Order-Intake.docx"));

  const b = await buildDoc({
    kicker: "INGREDION AGENTIC AI FACTORY · SOW NO. 07 PART B · BUILD GUIDE",
    title: "Agent B build guide: Pre-bill Validation and Dispute Prevention Agent on Google Cloud",
    subtitle: "Step-by-step plan to build, test, release and hand over steps B1 to B8, with the component deadlines of the SOW plan",
    author: AUTHOR, org: ORG, date: DATE, version: "1.0", basis: BASIS,
    keywords: "Ingredion, Pre-bill Validation, Agent B, Google Cloud, Vertex AI, Gemini, Document AI, Cloud Run, SOW No. 07",
    header: "Agent B build guide · Pre-bill Validation · Parkar internal",
  }, assemble(B), path.join(OUT_DIR, "Build-Guide-Agent-B-Prebill-Validation.docx"));

  console.log(JSON.stringify({ agentA_bytes: a, agentB_bytes: b }));
})().catch((e) => { console.error(e); process.exit(1); });
