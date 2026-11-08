// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// GRM in JavaScript: the same engine as grm.py, step by step (log-linear, sum and fn relations; Householder QR;
// Gauss-Newton with backtracking, then Levenberg-Marquardt; warm start on the log-linear part; continuation of
// tight nonlinear relations; uncertainties from the covariance). Checked against the Python by test_grm_js.mjs.
//
//   const net = new Network({E: {guess: 1}, m: {guess: 1}, c: {guess: 3e8}},
//                           [{name: "Einstein", terms: {E: 1, m: -1, c: -2}, rhs: 0, sigma: 1e-9}]);
//   const out = net.solve({m: [1.0, 1e-6], c: [299792458, 1e-12]});   // out.values.E, out.sigma_dex.E
//
// Nodes:      {guess, scale: "log" | "lin", fixed}     log nodes are solved as x = log10(value)
// Relations:  log  {terms: {node: power}, rhs, sigma}          sum(power * log10 node) = rhs
//             sum  {type: "sum", terms: {node: coeff}, pow: {node: p}, K, sigma}   sum(coeff * value^p) = K
//             fn   {type: "fn", nodes: [...], f: values => residual, grad?: values => {node: df/dvalue}, sigma}
// Measurements: {node: [value, sigma_dex]} (or a bare value: sigma 1e-4)

export const LN10 = Math.log(10);

const WGSL_EXPANSION_SHADER = `
struct NodeData {
  pos: vec4<f32>,
  dim: vec4<i32>,
  dim_k: i32,
  _pad0: i32,
  _pad1: i32,
  _pad2: i32,
};

struct Candidate {
  nodeA: u32,
  nodeB: u32,
  tension: f32,
  _pad: u32,
};

struct Params {
  nodeCount: u32,
  thresholdTension: f32,
  maxCandidates: u32,
  _pad: u32,
};

@group(0) @binding(0) var<storage, read> nodes: array<NodeData>;
@group(0) @binding(1) var<storage, read_write> candidates: array<Candidate>;
@group(0) @binding(2) var<storage, read_write> counter: atomic<u32>;
@group(0) @binding(3) var<uniform> params: Params;

@compute @workgroup_size(8, 8, 1)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  let i = id.x;
  let j = id.y;

  if (i >= params.nodeCount || j >= params.nodeCount || j <= i) {
    return;
  }

  let nodeA = nodes[i];
  let nodeB = nodes[j];

  if (nodeA.pos.w != nodeB.pos.w) {
    return;
  }

  let dPos = nodeA.pos.xyz - nodeB.pos.xyz;
  let dist = length(dPos);
  let tension = abs(dist - 50.0) / 50.0;

  if (tension <= params.thresholdTension && dist <= 120.0) {
    return;
  }

  let isLin = (nodeA.pos.w == 0.0);

  if (isLin) {
    if (any(nodeA.dim != nodeB.dim) || (nodeA.dim_k != nodeB.dim_k)) {
      return;
    }
  } else {
    let sumDim = nodeA.dim + nodeB.dim;
    if (((sumDim.x & 1) != 0) || ((sumDim.y & 1) != 0) || 
        ((sumDim.z & 1) != 0) || ((sumDim.w & 1) != 0) || 
        (((nodeA.dim_k + nodeB.dim_k) & 1) != 0)) {
      return;
    }
  }

  let slot = atomicAdd(&counter, 1u);
  if (slot < params.maxCandidates) {
    candidates[slot] = Candidate(i, j, tension, 0u);
  }
}
`;

function qrSolve(A, b, n) {
  const m = A.length;
  const M = A.map((row, i) => {
    const r = new Float64Array(n + 1);
    r.set(row);
    r[n] = b[i];
    return r;
  });
  const v = new Float64Array(m);
  for (let k = 0; k < n; k++) {
    let norm = 0;
    for (let i = k; i < m; i++) norm += M[i][k] * M[i][k];
    norm = Math.sqrt(norm);
    if (norm === 0) throw new RangeError("rank-deficient system");
    const alpha = M[k][k] >= 0 ? -norm : norm;
    v.fill(0);
    v[k] = M[k][k] - alpha;
    let vv = v[k] * v[k];
    for (let i = k + 1; i < m; i++) {
      v[i] = M[i][k];
      vv += v[i] * v[i];
    }
    if (vv === 0) continue;
    for (let j = k; j <= n; j++) {
      let s = 0;
      for (let i = k; i < m; i++) s += v[i] * M[i][j];
      s = (s * 2) / vv;
      if (s !== 0) for (let i = k; i < m; i++) M[i][j] -= s * v[i];
    }
  }
  const R = [];
  for (let i = 0; i < n; i++) {
    const r = new Float64Array(n);
    for (let j = i; j < n; j++) r[j] = M[i][j];
    R.push(r);
  }
  const y = new Float64Array(n);
  for (let i = 0; i < n; i++) y[i] = M[i][n];
  return { d: backSubstitution(R, y), R };
}

function backSubstitution(R, y) {
  const n = y.length;
  const x = new Float64Array(n);
  for (let i = n - 1; i >= 0; i--) {
    let s = y[i];
    for (let j = i + 1; j < n; j++) s -= R[i][j] * x[j];
    if (R[i][i] === 0) throw new RangeError("rank-deficient system");
    x[i] = s / R[i][i];
  }
  return x;
}

function covarianceFromR(R) {
  const n = R.length;
  const Rinv = Array.from({ length: n }, () => new Float64Array(n));
  for (let j = 0; j < n; j++) {
    const e = new Float64Array(n);
    e[j] = 1;
    const col = backSubstitution(R, e);
    for (let i = 0; i < n; i++) Rinv[i][j] = col[i];
  }
  return Array.from({ length: n }, (_, i) => {
    const row = new Float64Array(n);
    for (let j = 0; j < n; j++) {
      let s = 0;
      for (let k = 0; k < n; k++) s += Rinv[i][k] * Rinv[j][k];
      row[j] = s;
    }
    return row;
  });
}

function log10Checked(value, what) {
  value = Number(value);
  if (!(value > 0) || !Number.isFinite(value))
    throw new RangeError(
      `${what} must be a finite positive number (log-space), got ${value}`,
    );
  return Math.log10(value);
}

function extractPosition(p, name) {
  if (!p) return [0, 0, 0];
  let v = p instanceof Map ? p.get(name) : p[name];
  if (v && v.position) v = v.position;
  if (Array.isArray(v)) return [v[0] || 0, v[1] || 0, v[2] || 0];
  if (v && typeof v.x === "number") return [v.x, v.y, v.z];
  return [0, 0, 0];
}

export class Network {
  static CONTINUATION_START = 1e-2;
  static CONTINUATION_FACTOR = 100;
  static gpuDevice = null;
  static gpuPipeline = null;
  static gpuSupported = null;

  static async initGPU() {
    if (Network.gpuSupported !== null) return Network.gpuSupported;
    if (typeof navigator === "undefined" || !navigator.gpu) {
      Network.gpuSupported = false;
      return false;
    }
    try {
      const adapter = await navigator.gpu.requestAdapter({
        powerPreference: "high-performance",
      });
      if (!adapter) {
        Network.gpuSupported = false;
        return false;
      }
      Network.gpuDevice = await adapter.requestDevice();
      const module = Network.gpuDevice.createShaderModule({
        code: WGSL_EXPANSION_SHADER,
      });
      Network.gpuPipeline = Network.gpuDevice.createComputePipeline({
        layout: "auto",
        compute: { module, entryPoint: "main" },
      });
      Network.gpuSupported = true;
      return true;
    } catch {
      Network.gpuSupported = false;
      return false;
    }
  }

  constructor(
    nodesSpec,
    relationsSpec,
    { priorSigma = 1e3, undeterminedSigma = 1.0 } = {},
  ) {
    const names = Object.keys(nodesSpec);
    if (!names.length) throw new Error("the network has no nodes");
    this.nodesSpec = nodesSpec;
    this.names = names;
    this.index = Object.fromEntries(names.map((n, i) => [n, i]));
    this.priorSigma = priorSigma;
    this.undeterminedSigma = undeterminedSigma;
    this.x0 = [];
    this.lin = [];
    this.fixed = new Set();
    this.dims = [];

    for (const name of names) {
      const spec = nodesSpec[name];
      const scale = spec.scale ?? "log";
      if (scale !== "log" && scale !== "lin")
        throw new Error(`node '${name}': scale must be 'log' or 'lin'`);
      const lin = scale === "lin";
      this.lin.push(lin);
      const guess = spec.guess ?? (lin ? 0 : 1);
      this.x0.push(
        lin ? Number(guess) : log10Checked(guess, `guess of node '${name}'`),
      );
      if (spec.fixed) this.fixed.add(name);
      this.dims.push(
        Array.isArray(spec.dim) && spec.dim.length === 5
          ? spec.dim
          : [0, 0, 0, 0, 0],
      );
    }

    this.relations = [];
    relationsSpec.forEach((rel, k) => {
      const name = rel.name ?? `relation_${k}`;
      const kind = rel.type ?? "log";
      const sigma = rel.sigma ?? 1e-3;
      if (typeof sigma !== "function" && !(sigma > 0))
        throw new Error(`relation '${name}' needs a positive sigma`);
      if (kind === "fn") {
        if (!rel.nodes?.length || typeof rel.f !== "function")
          throw new Error(
            `relation '${name}' (fn) needs 'nodes' and a function 'f'`,
          );
        this.checkNames(name, rel.nodes);
        this.relations.push({
          name,
          type: "fn",
          f: rel.f,
          grad: rel.grad ?? null,
          sigma,
          nodes: rel.nodes.map((n) => this.index[n]),
        });
        return;
      }
      const terms = rel.terms;
      if (!terms || !Object.keys(terms).length)
        throw new Error(`relation '${name}' has no terms`);
      this.checkNames(name, Object.keys(terms));
      if (kind === "sum") {
        const pw = rel.pow ?? {};
        this.checkNames(name, Object.keys(pw));
        this.relations.push({
          name,
          type: "sum",
          sigma,
          K: Number(rel.K ?? 0),
          terms: Object.entries(terms).map(([n, c]) => [
            this.index[n],
            Number(c),
            Number(pw[n] ?? 1),
          ]),
        });
        return;
      }
      if (kind !== "log")
        throw new Error(`relation '${name}': unknown type '${kind}'`);
      const signed = Object.keys(terms).filter((n) => this.lin[this.index[n]]);
      if (signed.length)
        throw new Error(
          `relation '${name}' is log-linear but uses signed nodes ${signed}: use type 'sum' or 'fn'`,
        );
      this.relations.push({
        name,
        type: "log",
        sigma,
        rhs: rel.rhs ?? 0,
        terms: Object.entries(terms).map(([n, c]) => [
          this.index[n],
          Number(c),
        ]),
        depends: rel.depends ? rel.depends.map((n) => this.index[n]) : null,
      });
    });
    this.nonlinear = this.relations.some(
      (r) => r.type !== "log" || typeof r.rhs === "function",
    );
    this.hasCallables =
      this.nonlinear ||
      this.relations.some((r) => typeof r.sigma === "function");
    this.x = [...this.x0];
  }

  async findExpansionCandidatesGPU(
    positions,
    { thresholdTension = 0.75, maxCandidates = 64 } = {},
  ) {
    const isReady = await Network.initGPU();
    if (!isReady || this.names.length < 2) return null;

    const count = this.names.length;
    const stride = 12;
    const arrayBuffer = new ArrayBuffer(count * stride * 4);
    const floatView = new Float32Array(arrayBuffer);
    const intView = new Int32Array(arrayBuffer);

    for (let i = 0; i < count; i++) {
      const name = this.names[i];
      const pos = extractPosition(positions, name);
      const isLin = this.lin[i];
      const dim = this.dims[i];
      const offset = i * stride;

      floatView[offset + 0] = pos[0];
      floatView[offset + 1] = pos[1];
      floatView[offset + 2] = pos[2];
      floatView[offset + 3] = isLin ? 0.0 : 1.0;

      intView[offset + 4] = dim[0];
      intView[offset + 5] = dim[1];
      intView[offset + 6] = dim[2];
      intView[offset + 7] = dim[3];
      intView[offset + 8] = dim[4];
      intView[offset + 9] = 0;
      intView[offset + 10] = 0;
      intView[offset + 11] = 0;
    }

    const device = Network.gpuDevice;
    const nodeBuffer = device.createBuffer({
      size: arrayBuffer.byteLength,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });
    device.queue.writeBuffer(nodeBuffer, 0, arrayBuffer);

    const candidateBufferSize = maxCandidates * 16;
    const candidateBuffer = device.createBuffer({
      size: candidateBufferSize,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC,
    });

    const counterBuffer = device.createBuffer({
      size: 4,
      usage:
        GPUBufferUsage.STORAGE |
        GPUBufferUsage.COPY_SRC |
        GPUBufferUsage.COPY_DST,
    });
    device.queue.writeBuffer(counterBuffer, 0, new Uint32Array([0]));

    const paramBuffer = device.createBuffer({
      size: 16,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    const paramData = new ArrayBuffer(16);
    new Uint32Array(paramData, 0, 1)[0] = count;
    new Float32Array(paramData, 4, 1)[0] = thresholdTension;
    new Uint32Array(paramData, 8, 1)[0] = maxCandidates;
    device.queue.writeBuffer(paramBuffer, 0, paramData);

    const readCounterBuffer = device.createBuffer({
      size: 4,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    });
    const readCandidateBuffer = device.createBuffer({
      size: candidateBufferSize,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    });

    const bindGroup = device.createBindGroup({
      layout: Network.gpuPipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: { buffer: nodeBuffer } },
        { binding: 1, resource: { buffer: candidateBuffer } },
        { binding: 2, resource: { buffer: counterBuffer } },
        { binding: 3, resource: { buffer: paramBuffer } },
      ],
    });

    const encoder = device.createCommandEncoder();
    const pass = encoder.beginComputePass();
    pass.setPipeline(Network.gpuPipeline);
    pass.setBindGroup(0, bindGroup);
    pass.dispatchWorkgroups(Math.ceil(count / 8), Math.ceil(count / 8), 1);
    pass.end();

    encoder.copyBufferToBuffer(counterBuffer, 0, readCounterBuffer, 0, 4);
    encoder.copyBufferToBuffer(
      candidateBuffer,
      0,
      readCandidateBuffer,
      0,
      candidateBufferSize,
    );
    device.queue.submit([encoder.finish()]);

    await readCounterBuffer.mapAsync(GPUMapMode.READ);
    await readCandidateBuffer.mapAsync(GPUMapMode.READ);

    const foundCount = Math.min(
      new Uint32Array(readCounterBuffer.getMappedRange())[0],
      maxCandidates,
    );
    const candidateDataFloat = new Float32Array(
      readCandidateBuffer.getMappedRange(),
    );
    const candidateDataUint = new Uint32Array(
      readCandidateBuffer.getMappedRange(),
    );

    const results = [];
    for (let c = 0; c < foundCount; c++) {
      const base = c * 4;
      const idxA = candidateDataUint[base + 0];
      const idxB = candidateDataUint[base + 1];
      const tension = candidateDataFloat[base + 2];
      results.push({
        nodeA: this.names[idxA],
        nodeB: this.names[idxB],
        idxA,
        idxB,
        tension,
      });
    }

    readCounterBuffer.unmap();
    readCandidateBuffer.unmap();
    nodeBuffer.destroy();
    candidateBuffer.destroy();
    counterBuffer.destroy();
    paramBuffer.destroy();
    readCounterBuffer.destroy();
    readCandidateBuffer.destroy();

    return results;
  }

  async autoExpand(positions, { thresholdTension = 0.75, maxAdded = 2 } = {}) {
    let candidates = await this.findExpansionCandidatesGPU(positions, {
      thresholdTension,
      maxCandidates: 32,
    });
    const newNodes = JSON.parse(JSON.stringify(this.nodesSpec));
    const newRelations = [];
    const added = [];

    if (!candidates || candidates.length === 0) {
      candidates = [];
      const count = this.names.length;
      for (let i = 0; i < count; i++) {
        for (let j = i + 1; j < count; j++) {
          if (this.lin[i] !== this.lin[j]) continue;
          const posA = extractPosition(positions, this.names[i]);
          const posB = extractPosition(positions, this.names[j]);
          const dist = Math.hypot(
            posA[0] - posB[0],
            posA[1] - posB[1],
            posA[2] - posB[2],
          );
          const tension = Math.abs(dist - 50.0) / 50.0;
          if (tension <= thresholdTension && dist <= 120.0) continue;

          let valid = true;
          const dimA = this.dims[i];
          const dimB = this.dims[j];

          if (this.lin[i]) {
            for (let k = 0; k < 5; k++) {
              if (dimA[k] !== dimB[k]) {
                valid = false;
                break;
              }
            }
          } else {
            for (let k = 0; k < 5; k++) {
              if (((dimA[k] + dimB[k]) & 1) !== 0) {
                valid = false;
                break;
              }
            }
          }
          if (valid) {
            candidates.push({
              nodeA: this.names[i],
              nodeB: this.names[j],
              idxA: i,
              idxB: j,
              tension,
            });
          }
        }
      }
    }

    candidates.sort(() => Math.random() - 0.5);

    let countAdded = 0;
    for (const cand of candidates) {
      if (countAdded >= maxAdded) break;
      const nodeA = cand.nodeA;
      const nodeB = cand.nodeB;
      const specA = this.nodesSpec[nodeA];
      const specB = this.nodesSpec[nodeB];
      const isLin = specA.scale === "lin";
      const dimA = specA.dim || [0, 0, 0, 0, 0];
      const dimB = specB.dim || [0, 0, 0, 0, 0];

      const newDim = [0, 0, 0, 0, 0];
      for (let k = 0; k < 5; k++) {
        newDim[k] = isLin ? dimA[k] : (dimA[k] + dimB[k]) / 2;
      }

      const timestamp = Date.now();
      const randSuffix = Math.floor(Math.random() * 1000);
      const newId = `node_auto_${timestamp}_${randSuffix}`;
      const relName = `rel_exp_${timestamp}_${randSuffix}`;

      let newGuess, formulaDesc;
      if (isLin) {
        newGuess = (specA.guess + specB.guess) / 2;
        formulaDesc = `(${nodeA} + ${nodeB}) / 2`;
      } else {
        newGuess = Math.sqrt(Math.abs(specA.guess * specB.guess));
        formulaDesc = `√(${nodeA} × ${nodeB})`;
      }

      newNodes[newId] = {
        guess: newGuess,
        scale: isLin ? "lin" : "log",
        dim: newDim,
        parentA: nodeA,
        parentB: nodeB,
        formula: formulaDesc,
      };

      const relData = {
        name: relName,
        parents: [nodeA, nodeB],
        formula: formulaDesc,
        sigma: 1.0,
      };

      if (isLin) {
        relData.type = "sum";
        relData.terms = { [nodeA]: 0.5, [nodeB]: 0.5, [newId]: -1.0 };
        relData.K = 0.0;
      } else {
        relData.type = "log";
        relData.terms = { [nodeA]: 0.5, [nodeB]: 0.5, [newId]: -1.0 };
        relData.rhs = 0.0;
      }

      newRelations.push(relData);
      added.push({ nodeId: newId, nodeSpec: newNodes[newId], relData });
      countAdded++;
    }

    return { updatedNodes: newNodes, updatedRelations: newRelations, added };
  }

  checkNames(relName, names) {
    const unknown = names.filter((n) => !(n in this.index));
    if (unknown.length)
      throw new Error(`relation '${relName}' uses unknown nodes: ${unknown}`);
  }

  setSigma(name, sigma) {
    const r = this.relations.find((q) => q.name === name);
    if (!r) throw new Error(`unknown relation '${name}'`);
    r.sigma = sigma;
    this.hasCallables =
      this.nonlinear ||
      this.relations.some((q) => typeof q.sigma === "function");
  }

  toValue(i, xi) {
    return this.lin[i] ? xi : 10 ** xi;
  }
  valuesOf(x) {
    const v = {};
    this.names.forEach((n, i) => {
      v[n] = this.toValue(i, x[i]);
    });
    return v;
  }
  static evalParam(p, values) {
    return typeof p === "function" ? Number(p(values)) : Number(p);
  }

  residual(rel, x, values) {
    if (rel.type === "log") {
      let r = -Network.evalParam(rel.rhs, values);
      for (const [i, c] of rel.terms) r += c * x[i];
      return r;
    }
    if (rel.type === "sum") {
      let r = -rel.K;
      for (const [i, c, p] of rel.terms) r += c * this.toValue(i, x[i]) ** p;
      return r;
    }
    return Number(rel.f(values));
  }

  fdStep(i, xi) {
    return this.lin[i] ? 1e-6 * Math.max(1, Math.abs(xi)) : 1e-6;
  }

  derivative(rel, x, h, rhsOnly, values, i) {
    const name = this.names[i];
    const x0 = x[i];
    const v0 = values ? values[name] : undefined;
    const g = (xi) => {
      x[i] = xi;
      let vz;
      if (values) {
        values[name] = this.toValue(i, xi);
        vz = values;
      } else vz = this.valuesOf(x);
      const out = rhsOnly
        ? -Network.evalParam(rel.rhs, vz)
        : this.residual(rel, x, vz);
      return Number.isFinite(out) ? out : null;
    };
    let fp,
      fm,
      f0 = null;
    try {
      fp = g(x0 + h);
      fm = g(x0 - h);
      if (fp === null || fm === null) f0 = g(x0);
    } finally {
      x[i] = x0;
      if (values) values[name] = v0;
    }
    if (fp !== null && fm !== null) return (fp - fm) / (2 * h);
    if (fp !== null && f0 !== null) return (fp - f0) / h;
    if (fm !== null && f0 !== null) return (f0 - fm) / h;
    return 0;
  }

  rows(x, measurements, col, jacobian = true) {
    const values = this.hasCallables ? this.valuesOf(x) : null;
    const rows = [];
    let cost = 0;
    for (const rel of this.relations) {
      const r = this.residual(rel, x, values);
      const w = 1 / Math.max(Network.evalParam(rel.sigma, values), 1e-300);
      cost += (w * r) ** 2;
      const entries = new Map();
      const add = (a, d) => entries.set(a, (entries.get(a) ?? 0) + d);
      if (jacobian) {
        let probe = [],
          rhsOnly = false;
        if (rel.type === "log") {
          for (const [i, c] of rel.terms) if (col.has(i)) add(col.get(i), c);
          if (typeof rel.rhs === "function")
            probe = rel.depends ?? [...col.keys()];
          rhsOnly = true;
        } else if (rel.type === "sum") {
          for (const [i, c, p] of rel.terms)
            if (col.has(i)) {
              const v = this.toValue(i, x[i]);
              const dv = this.lin[i] ? 1 : v * LN10;
              add(col.get(i), c * p * v ** (p - 1) * dv);
            }
        } else if (rel.grad) {
          for (const [name, dfdv] of Object.entries(rel.grad(values))) {
            const i = this.index[name];
            if (col.has(i))
              add(col.get(i), dfdv * (this.lin[i] ? 1 : values[name] * LN10));
          }
        } else probe = rel.nodes;
        for (const i of probe) {
          if (!col.has(i)) continue;
          const d = this.derivative(
            rel,
            x,
            this.fdStep(i, x[i]),
            rhsOnly,
            values,
            i,
          );
          if (d) add(col.get(i), d);
        }
      }
      rows.push([entries, r, w]);
    }
    for (const [i, [target, sigma]] of measurements) {
      const r = x[i] - target;
      const w = 1 / sigma;
      cost += (w * r) ** 2;
      const entries = new Map();
      if (jacobian && col.has(i)) entries.set(col.get(i), 1);
      rows.push([entries, r, w]);
    }
    return [rows, cost];
  }

  cost(x, measurements) {
    try {
      const c = this.rows(x, measurements, new Map(), false)[1];
      return Number.isFinite(c) ? c : Infinity;
    } catch {
      return Infinity;
    }
  }

  step(rows, n, lam) {
    const A = [],
      b = [];
    const colnorm = new Float64Array(n);
    for (const [entries, r, w] of rows) {
      if (!entries.size) continue;
      const row = new Float64Array(n);
      for (const [a, d] of entries) {
        row[a] = w * d;
        colnorm[a] += (w * d) ** 2;
      }
      A.push(row);
      b.push(-w * r);
    }
    for (let a = 0; a < n; a++) {
      const row = new Float64Array(n);
      row[a] = 1 / this.priorSigma;
      A.push(row);
      b.push(0);
    }
    if (lam > 0)
      for (let a = 0; a < n; a++) {
        const row = new Float64Array(n);
        row[a] = Math.sqrt(lam) * (colnorm[a] > 0 ? Math.sqrt(colnorm[a]) : 1);
        A.push(row);
        b.push(0);
      }
    return qrSolve(A, b, n);
  }

  solve(
    measured = {},
    {
      maxIterations = 50,
      damping = 1e-3,
      tolerance = 1e-12,
      measurementSigma = 1e-4,
      computeUncertainty = true,
      start = null,
      continuation = true,
    } = {},
  ) {
    const measurements = [];
    for (const [name, m] of Object.entries(measured)) {
      if (!(name in this.index))
        throw new Error(`unknown measured node '${name}'`);
      const [value, sigma] = Array.isArray(m) ? m : [m, measurementSigma];
      if (!(sigma > 0))
        throw new Error(`measurement of '${name}' needs a positive sigma`);
      const i = this.index[name];
      measurements.push([
        i,
        [
          this.lin[i]
            ? Number(value)
            : log10Checked(value, `measurement of '${name}'`),
          Number(sigma),
        ],
      ]);
    }
    let x = [...this.x0];
    if (start)
      for (const [name, v] of Object.entries(start)) {
        if (!(name in this.index)) continue;
        const i = this.index[name];
        x[i] = this.lin[i]
          ? Number(v)
          : log10Checked(v, `start value of '${name}'`);
      }
    for (const [i, [target]] of measurements)
      if (this.fixed.has(this.names[i])) x[i] = target;
    const free = this.names
      .map((_, i) => i)
      .filter((i) => !this.fixed.has(this.names[i]));
    const col = new Map(free.map((i, a) => [i, a]));
    const n = free.length;
    let iterations = 0,
      converged = true,
      R = null;
    if (n && !this.nonlinear) {
      for (iterations = 1; iterations <= 4; iterations++) {
        const [rows] = this.rows(x, measurements, col);
        const s = this.step(rows, n, 0);
        R = s.R;
        free.forEach((i, a) => {
          x[i] += s.d[a];
        });
        if (Math.max(...s.d.map(Math.abs)) < 1e-13) break;
      }
    } else if (n) {
      x = this.warmStart(x, measurements, free, col);
      if (!Number.isFinite(this.cost(x, measurements)))
        throw new RangeError(
          "the starting point is outside the domain of a relation: change the guesses",
        );
      const xStart = [...x];
      [x, iterations, converged] = this.descend(
        x,
        measurements,
        free,
        col,
        n,
        maxIterations,
        damping,
        tolerance,
      );
      if (!converged && continuation)
        [x, iterations, converged] = this.continuationSolve(
          xStart,
          x,
          measurements,
          free,
          col,
          n,
          maxIterations,
          damping,
          tolerance,
          iterations,
        );
    }
    this.x = x;
    const [, cost] = this.rows(x, measurements, new Map(), false);
    const dof = this.relations.length + measurements.length - n;
    const result = {
      values: this.valuesOf(x),
      cost,
      iterations,
      converged,
      dof,
      reduced_chi2: dof > 0 ? cost / dof : null,
    };
    const pulls = this.rows(x, [], new Map(), false)[0];
    result.relation_pulls = Object.fromEntries(
      this.relations.map((rel, k) => [rel.name, pulls[k][1] * pulls[k][2]]),
    );
    if (computeUncertainty) {
      const sigmaDex = Object.fromEntries(this.names.map((nm) => [nm, 0]));
      if (n) {
        if (R === null || this.nonlinear) {
          const [rows] = this.rows(x, measurements, col);
          R = this.step(rows, n, 0).R;
        }
        const cov = covarianceFromR(R);
        result.covariance = {};
        free.forEach((i, a) => {
          sigmaDex[this.names[i]] = Math.sqrt(Math.max(cov[a][a], 0));
          free.forEach((j, b) => {
            result.covariance[`${this.names[i]}|${this.names[j]}`] = cov[a][b];
          });
        });
      }
      result.sigma_dex = sigmaDex;
      result.uncertainty = Object.fromEntries(
        this.names.map((nm) => [
          nm,
          this.lin[this.index[nm]] ? sigmaDex[nm] : LN10 * sigmaDex[nm],
        ]),
      );
      result.undetermined = this.names
        .filter((nm) => {
          const i = this.index[nm];
          return (
            sigmaDex[nm] >
            this.undeterminedSigma *
              (this.lin[i] ? Math.max(1, Math.abs(x[i])) : 1)
          );
        })
        .sort();
    }
    return result;
  }

  descend(x, measurements, free, col, n, maxIterations, damping, tolerance) {
    let lam = damping,
      converged = false,
      iterations = 0;
    let cost = this.cost(x, measurements);
    let delta = null,
      xNew = null,
      newCost = 0;
    for (iterations = 1; iterations <= maxIterations; iterations++) {
      const [rows, c] = this.rows(x, measurements, col);
      cost = c;
      let accepted = false;
      let gn = null;
      try {
        gn = this.step(rows, n, 0).d;
      } catch {
        gn = null;
      }
      if (gn) {
        let alpha = 1;
        for (let t = 0; t < 25; t++) {
          delta = Array.from(gn, (d) => alpha * d);
          xNew = [...x];
          free.forEach((i, a) => {
            xNew[i] += delta[a];
          });
          newCost = this.cost(xNew, measurements);
          if (newCost <= cost) {
            accepted = true;
            break;
          }
          alpha *= 0.5;
        }
      }
      if (!accepted)
        for (let t = 0; t < 30; t++) {
          let s;
          try {
            s = this.step(rows, n, lam);
          } catch {
            lam *= 10;
            continue;
          }
          delta = Array.from(s.d);
          xNew = [...x];
          free.forEach((i, a) => {
            xNew[i] += delta[a];
          });
          newCost = this.cost(xNew, measurements);
          if (newCost <= cost) {
            accepted = true;
            break;
          }
          lam *= 10;
        }
      if (!accepted) {
        converged = true;
        break;
      }
      const stepSize = Math.max(...delta.map(Math.abs));
      const drop = cost - newCost;
      x = xNew;
      cost = newCost;
      lam = Math.max(lam / 10, 1e-15);
      if (stepSize < 1e-12 || drop <= tolerance * Math.max(1, cost)) {
        converged = true;
        break;
      }
    }
    return [x, iterations, converged];
  }

  continuationSolve(
    xStart,
    xDirect,
    measurements,
    free,
    col,
    n,
    maxIterations,
    damping,
    tolerance,
    itDirect,
  ) {
    const tight = this.relations.filter(
      (r) =>
        r.type !== "log" &&
        typeof r.sigma !== "function" &&
        r.sigma < Network.CONTINUATION_START,
    );
    if (!tight.length) return [xDirect, itDirect, false];
    const trueSigma = tight.map((r) => r.sigma);
    const levels = [Network.CONTINUATION_START];
    while (levels[levels.length - 1] > Math.min(...trueSigma))
      levels.push(levels[levels.length - 1] / Network.CONTINUATION_FACTOR);
    const budget = Math.max(5, Math.floor(maxIterations / levels.length));
    let x = [...xStart],
      total = itDirect,
      converged = false;
    try {
      for (const level of levels) {
        tight.forEach((r, k) => {
          r.sigma = Math.max(trueSigma[k], level);
        });
        if (!Number.isFinite(this.cost(x, measurements))) break;
        let it;
        [x, it, converged] = this.descend(
          x,
          measurements,
          free,
          col,
          n,
          budget,
          damping,
          tolerance,
        );
        total += it;
      }
    } finally {
      tight.forEach((r, k) => {
        r.sigma = trueSigma[k];
      });
    }
    if (
      converged &&
      this.cost(x, measurements) <= this.cost(xDirect, measurements)
    )
      return [x, total, true];
    return [xDirect, total, false];
  }

  warmStart(x, measurements, free, col) {
    const linear = this.relations.filter(
      (r) => r.type === "log" && typeof r.rhs !== "function",
    );
    if (!linear.length) return x;
    const saved = [this.relations, this.hasCallables];
    this.relations = linear;
    this.hasCallables = linear.some((r) => typeof r.sigma === "function");
    let xw = [...x];
    try {
      for (let t = 0; t < 3; t++) {
        const [rows] = this.rows(xw, measurements, col);
        const s = this.step(rows, free.length, 0);
        free.forEach((i, a) => {
          xw[i] += s.d[a];
        });
      }
    } catch {
      xw = null;
    } finally {
      [this.relations, this.hasCallables] = saved;
    }
    if (!xw) return x;
    const cw = this.cost(xw, measurements),
      c0 = this.cost(x, measurements);
    return Number.isFinite(cw) && (cw <= c0 || !Number.isFinite(c0)) ? xw : x;
  }
}
