// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// grm.js must give the same numbers as grm.py (golden.json, made by make_golden.py). Run: node web/tests/test_grm_js.mjs
import { readFileSync } from "node:fs";
import { Network } from "../grm.js";

const cases = JSON.parse(readFileSync(new URL("./golden.json", import.meta.url)));
const MATH = ["sqrt", "exp", "log", "log10", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "abs", "pow"];

function build(doc) {
  const nodes = {}, measured = {};
  for (const [name, s] of Object.entries(doc.nodes)) {
    nodes[name] = { guess: s.guess, scale: s.scale ?? "log", fixed: !!s.fixed };
    if (s.measured) measured[name] = s.measured;
  }
  const names = Object.keys(nodes);
  const rels = doc.relations.map((r) => {
    if (r.type !== "fn") return r;
    // test only: the expressions of the presets, as JavaScript (Python's ** is the same operator)
    let body = r.expr;
    for (const m of MATH) body = body.replace(new RegExp(`\\b${m}\\(`, "g"), `Math.${m === "log" ? "log" : m}(`);
    const used = names.filter((n) => new RegExp(`\\b${n}\\b`).test(r.expr));
    const f = new Function(...used, `return ${body};`);
    return { name: r.name, type: "fn", nodes: used, sigma: r.sigma, f: (v) => f(...used.map((n) => v[n])) };
  });
  return [new Network(nodes, rels), measured];
}

let checks = 0, failures = 0;
const close = (a, b, rel, abs) => Math.abs(a - b) <= Math.max(rel * Math.abs(b), abs);
for (const c of cases) {
  const [net, measured] = build(c.doc);
  const out = net.solve(measured);
  for (const [name, v] of Object.entries(c.values)) {
    checks++;
    if (!close(out.values[name], v, 1e-9, 1e-15)) {
      failures++;
      console.log(`FAIL ${c.id} ${name}: js ${out.values[name]}, python ${v}`);
    }
    checks++;
    if (!close(out.sigma_dex[name], c.sigma_dex[name], 1e-5, 1e-14)) {
      failures++;
      console.log(`FAIL ${c.id} sigma ${name}: js ${out.sigma_dex[name]}, python ${c.sigma_dex[name]}`);
    }
  }
  checks++;
  if (JSON.stringify(out.undetermined) !== JSON.stringify(c.undetermined) || out.converged !== c.converged) {
    failures++;
    console.log(`FAIL ${c.id}: undetermined ${out.undetermined} vs ${c.undetermined}, converged ${out.converged} vs ${c.converged}`);
  }
}
console.log(`${checks} checks, ${failures} failures`);
process.exit(failures ? 1 : 0);
