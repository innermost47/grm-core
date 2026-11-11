const WGSL_MINER_SHADER = `
struct NodeData {
  logVal: f32,
  scale: f32,
  dim0: i32,
  dim1: i32,
  dim2: i32,
  dim3: i32,
  dim4: i32,
  _pad: i32,
};

struct BridgeHit {
  idxA: u32,
  idxB: u32,
  idxC: u32,
  wA: i32,
  wB: i32,
  wC: i32,
  residual: f32,
  targetK: f32,
};

struct Params {
  nodeCount: u32,
  maxHits: u32,
  toleranceDex: f32,
  minScaleDistance: f32,
};

@group(0) @binding(0) var<storage, read> nodes: array<NodeData>;
@group(0) @binding(1) var<storage, read_write> hits: array<BridgeHit>;
@group(0) @binding(2) var<storage, read_write> hitCounter: atomic<u32>;
@group(0) @binding(3) var<uniform> params: Params;

const CANONICAL_COMBOS = array<vec3<i32>, 24>(
  vec3<i32>(1, -1, 0),
  vec3<i32>(1, -2, 0),
  vec3<i32>(2, -1, 0),
  vec3<i32>(1, -3, 0),
  vec3<i32>(3, -1, 0),

  vec3<i32>(1, 1, -1),
  vec3<i32>(1, -1, 1),
  vec3<i32>(-1, 1, 1),
  vec3<i32>(1, -1, -1),
  vec3<i32>(-1, 1, -1),
  vec3<i32>(-1, -1, 1),

  vec3<i32>(1, -1, -2),
  vec3<i32>(1, -2, -1),
  vec3<i32>(-2, 1, -1),
  vec3<i32>(-1, 1, -2),
  vec3<i32>(-1, -2, 1),
  vec3<i32>(-2, -1, 1),

  vec3<i32>(2, -1, -1),
  vec3<i32>(-1, 2, -1),
  vec3<i32>(-1, -1, 2),
  vec3<i32>(1, 2, -1),
  vec3<i32>(1, -1, 2),
  vec3<i32>(-1, 1, 2),
  vec3<i32>(2, 1, -1)
);

const MATHEMATICAL_TARGETS = array<f32, 12>(
  0.0,          // K = 1.0 (Identity)
  0.301029995,  // K = 2.0
  -0.301029995, // K = 1/2
  0.602059991,  // K = 4.0
  -0.602059991, // K = 1/4
  0.49714987,   // K = pi
  -0.49714987,  // K = 1/pi
  0.798179868,  // K = 2*pi
  -0.798179868, // K = 1/(2*pi)
  1.099209864,  // K = 4*pi
  -1.099209864, // K = 1/(4*pi)
  -0.176091259  // K = 2/3 (Koide / Quark charge scaling)
);

@compute @workgroup_size(4, 4, 4)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  let i = id.x;
  let j = id.y;
  let k = id.z;

  if (i >= params.nodeCount || j >= params.nodeCount || k >= params.nodeCount) {
    return;
  }
  if (j <= i || k < j) {
    return;
  }

  let nodeA = nodes[i];
  let nodeB = nodes[j];
  let nodeC = nodes[k];

  if (nodeA.scale < 0.5 || nodeB.scale < 0.5 || (k != j && nodeC.scale < 0.5)) {
    return;
  }

  for (var c = 0u; c < 24u; c = c + 1u) {
    let exp = CANONICAL_COMBOS[c];
    let wA = exp.x;
    let wB = exp.y;
    let wC = exp.z;

    if (wC == 0 && k != j) {
      continue;
    }

    var d0 = wA * nodeA.dim0 + wB * nodeB.dim0;
    var d1 = wA * nodeA.dim1 + wB * nodeB.dim1;
    var d2 = wA * nodeA.dim2 + wB * nodeB.dim2;
    var d3 = wA * nodeA.dim3 + wB * nodeB.dim3;
    var d4 = wA * nodeA.dim4 + wB * nodeB.dim4;

    if (wC != 0) {
      d0 = d0 + wC * nodeC.dim0;
      d1 = d1 + wC * nodeC.dim1;
      d2 = d2 + wC * nodeC.dim2;
      d3 = d3 + wC * nodeC.dim3;
      d4 = d4 + wC * nodeC.dim4;
    }

    if (d0 != 0 || d1 != 0 || d2 != 0 || d3 != 0 || d4 != 0) {
      continue;
    }

    var maxDex = max(nodeA.logVal, nodeB.logVal);
    var minDex = min(nodeA.logVal, nodeB.logVal);
    if (wC != 0) {
      maxDex = max(maxDex, nodeC.logVal);
      minDex = min(minDex, nodeC.logVal);
    }
    if ((maxDex - minDex) < params.minScaleDistance) {
      continue;
    }

    var comboLog = f32(wA) * nodeA.logVal + f32(wB) * nodeB.logVal;
    if (wC != 0) {
      comboLog = comboLog + f32(wC) * nodeC.logVal;
    }

    for (var t = 0u; t < 12u; t = t + 1u) {
      let targetVal = MATHEMATICAL_TARGETS[t];
      let res = abs(comboLog - targetVal);

      if (res < params.toleranceDex) {
        let slot = atomicAdd(&hitCounter, 1u);
        if (slot < params.maxHits) {
          hits[slot] = BridgeHit(i, j, k, wA, wB, wC, res, targetVal);
        }
        return;
      }
    }
  }
}
`;

export class GRMBridgeMiner {
  constructor() {
    this.device = null;
    this.pipeline = null;
    this.isSupported = false;
  }

  async init() {
    if (typeof navigator === "undefined" || !navigator.gpu) return false;
    try {
      const adapter = await navigator.gpu.requestAdapter({
        powerPreference: "high-performance",
      });
      if (!adapter) return false;
      this.device = await adapter.requestDevice();
      const module = this.device.createShaderModule({
        code: WGSL_MINER_SHADER,
      });
      this.pipeline = this.device.createComputePipeline({
        layout: "auto",
        compute: { module, entryPoint: "main" },
      });
      this.isSupported = true;
      return true;
    } catch {
      this.isSupported = false;
      return false;
    }
  }

  async mineBridges(nodeNames, nodesSpec, solvedValues, options = {}) {
    if (!this.isSupported) {
      const ok = await this.init();
      if (!ok) return [];
    }

    const scientificPasses = [
      { toleranceDex: 0.001, minScaleDistance: 0.0 },
      { toleranceDex: 0.003, minScaleDistance: 0.0 },
      { toleranceDex: 0.005, minScaleDistance: 0.0 },
    ];

    for (const p of scientificPasses) {
      const tolerance =
        options.toleranceDex !== undefined
          ? options.toleranceDex
          : p.toleranceDex;
      const minDistance =
        options.minScaleDistance !== undefined
          ? options.minScaleDistance
          : p.minScaleDistance;
      const maxHits = options.maxHits || 128;

      const results = await this._executeGPUScan(
        nodeNames,
        nodesSpec,
        solvedValues,
        {
          toleranceDex: tolerance,
          minScaleDistance: minDistance,
          maxHits: maxHits,
        },
      );

      if (results.length > 0) {
        return results;
      }
    }

    return [];
  }

  async _executeGPUScan(
    nodeNames,
    nodesSpec,
    solvedValues,
    { toleranceDex, minScaleDistance, maxHits },
  ) {
    const count = nodeNames.length;
    const stride = 8;
    const bufferData = new ArrayBuffer(count * stride * 4);
    const floatView = new Float32Array(bufferData);
    const intView = new Int32Array(bufferData);

    for (let i = 0; i < count; i++) {
      const name = nodeNames[i];
      const spec = nodesSpec[name];
      const val = solvedValues?.[name] ?? spec.guess;
      const isLin = spec.scale === "lin";
      const logVal = isLin ? 0.0 : Math.log10(Math.max(Math.abs(val), 1e-120));
      const dim = spec.dim || [0, 0, 0, 0, 0];
      const offset = i * stride;

      floatView[offset + 0] = logVal;
      floatView[offset + 1] = isLin ? 0.0 : 1.0;
      intView[offset + 2] = dim[0];
      intView[offset + 3] = dim[1];
      intView[offset + 4] = dim[2];
      intView[offset + 5] = dim[3];
      intView[offset + 6] = dim[4];
      intView[offset + 7] = 0;
    }

    const nodeBuffer = this.device.createBuffer({
      size: bufferData.byteLength,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });
    this.device.queue.writeBuffer(nodeBuffer, 0, bufferData);

    const hitBufferSize = maxHits * 32;
    const hitBuffer = this.device.createBuffer({
      size: hitBufferSize,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC,
    });

    const counterBuffer = this.device.createBuffer({
      size: 4,
      usage:
        GPUBufferUsage.STORAGE |
        GPUBufferUsage.COPY_SRC |
        GPUBufferUsage.COPY_DST,
    });
    this.device.queue.writeBuffer(counterBuffer, 0, new Uint32Array([0]));

    const paramBuffer = this.device.createBuffer({
      size: 16,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    const paramData = new ArrayBuffer(16);
    new Uint32Array(paramData, 0, 1)[0] = count;
    new Uint32Array(paramData, 4, 1)[0] = maxHits;
    new Float32Array(paramData, 8, 1)[0] = toleranceDex;
    new Float32Array(paramData, 12, 1)[0] = minScaleDistance;
    this.device.queue.writeBuffer(paramBuffer, 0, paramData);

    const readCounter = this.device.createBuffer({
      size: 4,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    });
    const readHits = this.device.createBuffer({
      size: hitBufferSize,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    });

    const bindGroup = this.device.createBindGroup({
      layout: this.pipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: { buffer: nodeBuffer } },
        { binding: 1, resource: { buffer: hitBuffer } },
        { binding: 2, resource: { buffer: counterBuffer } },
        { binding: 3, resource: { buffer: paramBuffer } },
      ],
    });

    const encoder = this.device.createCommandEncoder();
    const pass = encoder.beginComputePass();
    pass.setPipeline(this.pipeline);
    pass.setBindGroup(0, bindGroup);
    pass.dispatchWorkgroups(
      Math.ceil(count / 4),
      Math.ceil(count / 4),
      Math.ceil(count / 4),
    );
    pass.end();

    encoder.copyBufferToBuffer(counterBuffer, 0, readCounter, 0, 4);
    encoder.copyBufferToBuffer(hitBuffer, 0, readHits, 0, hitBufferSize);
    this.device.queue.submit([encoder.finish()]);

    await readCounter.mapAsync(GPUMapMode.READ);
    await readHits.mapAsync(GPUMapMode.READ);

    const counterBufferData = readCounter.getMappedRange();
    const totalHits = Math.min(new Uint32Array(counterBufferData)[0], maxHits);

    const hitsBufferData = readHits.getMappedRange();
    const hitUint = new Uint32Array(hitsBufferData);
    const hitInt = new Int32Array(hitsBufferData);
    const hitFloat = new Float32Array(hitsBufferData);

    const discovered = [];
    const seenSignatures = new Set();
    const seenCanonicalForms = new Set();

    for (let h = 0; h < totalHits; h++) {
      const base = h * 8;
      const idxA = hitUint[base + 0];
      const idxB = hitUint[base + 1];
      const idxC = hitUint[base + 2];
      const wA = hitInt[base + 3];
      const wB = hitInt[base + 4];
      const wC = hitInt[base + 5];
      const res = hitFloat[base + 6];
      const targetLog = hitFloat[base + 7];

      if (res > 0.01) continue;

      const nameA = nodeNames[idxA];
      const nameB = nodeNames[idxB];
      const nameC = wC !== 0 ? nodeNames[idxC] : null;

      const terms = {};
      terms[nameA] = (terms[nameA] || 0) + wA;
      terms[nameB] = (terms[nameB] || 0) + wB;
      if (nameC && wC !== 0) {
        terms[nameC] = (terms[nameC] || 0) + wC;
      }

      for (const k in terms) {
        if (terms[k] === 0) delete terms[k];
      }

      const activeKeys = Object.keys(terms).sort();
      if (activeKeys.length < 2) continue;

      const sigKey = activeKeys.map((k) => `${k}:${terms[k]}`).join("|");
      if (seenSignatures.has(sigKey)) continue;
      seenSignatures.add(sigKey);
      const powers = activeKeys.map((k) => terms[k]);
      let commonGcd = powers[0];
      for (let i = 1; i < powers.length; i++) {
        let x = commonGcd,
          y = powers[i];
        while (y) {
          let t = y;
          y = x % y;
          x = t;
        }
        commonGcd = x;
      }
      commonGcd = Math.abs(commonGcd);

      // Si le premier coefficient non nul est négatif, on inverse tout pour stabiliser la forme
      let signMultiplier = 1;
      const firstNonZero = powers.find((p) => p !== 0);
      if (firstNonZero < 0) {
        signMultiplier = -1;
      }

      const canonicalParts = activeKeys.map((k, i) => {
        const reducedPower = (powers[i] * signMultiplier) / commonGcd;
        return `${k}:${reducedPower}`;
      });

      const normalizedTargetLog = targetLog * signMultiplier;
      const canonicalKey =
        canonicalParts.join("|") + `_rhs:${normalizedTargetLog.toFixed(3)}`;

      if (seenCanonicalForms.has(canonicalKey)) continue;
      seenCanonicalForms.add(canonicalKey);

      const netDim = [0, 0, 0, 0, 0];
      let isDimValid = true;
      for (const nodeName of activeKeys) {
        const d = nodesSpec[nodeName]?.dim || [0, 0, 0, 0, 0];
        const p = terms[nodeName];
        for (let k = 0; k < 5; k++) {
          netDim[k] += p * d[k];
        }
      }
      for (let k = 0; k < 5; k++) {
        if (netDim[k] !== 0) {
          isDimValid = false;
          break;
        }
      }
      if (!isDimValid) continue;

      const numerators = [];
      for (const k of activeKeys) {
        const p = terms[k];
        if (p > 0) numerators.push(p === 1 ? k : `${k}^${p}`);
        else numerators.push(p === -1 ? `${k}^(-1)` : `${k}^(${p})`);
      }

      let kDisplay = "1.0";
      if (Math.abs(targetLog - 0.301) < 0.01) kDisplay = "2.0";
      else if (Math.abs(targetLog - -0.301) < 0.01) kDisplay = "1/2";
      else if (Math.abs(targetLog - 0.602) < 0.01) kDisplay = "4.0";
      else if (Math.abs(targetLog - -0.602) < 0.01) kDisplay = "1/4";
      else if (Math.abs(targetLog - 0.497) < 0.01) kDisplay = "π";
      else if (Math.abs(targetLog - -0.497) < 0.01) kDisplay = "1/π";
      else if (Math.abs(targetLog - 0.798) < 0.01) kDisplay = "2π";
      else if (Math.abs(targetLog - -0.798) < 0.01) kDisplay = "1/(2π)";
      else if (Math.abs(targetLog - 1.099) < 0.01) kDisplay = "4π";
      else if (Math.abs(targetLog - -1.099) < 0.01) kDisplay = "1/(4π)";
      else if (Math.abs(targetLog - -0.176) < 0.01) kDisplay = "2/3";
      else if (targetLog !== 0.0) kDisplay = `10^(${targetLog.toFixed(4)})`;

      const formulaString = `${numerators.join(" × ")} = ${kDisplay}`;

      const logA = Math.log10(
        Math.abs(solvedValues?.[nameA] ?? nodesSpec[nameA]?.guess ?? 1.0),
      );
      const logB = Math.log10(
        Math.abs(solvedValues?.[nameB] ?? nodesSpec[nameB]?.guess ?? 1.0),
      );
      const logC = nameC
        ? Math.log10(
            Math.abs(solvedValues?.[nameC] ?? nodesSpec[nameC]?.guess ?? 1.0),
          )
        : 0.0;
      const comboLog = wA * logA + wB * logB + wC * logC;

      discovered.push({
        name: `invariant_${activeKeys.join("_")}`,
        terms,
        nodes: activeKeys,
        rhs: targetLog,
        sigma: Math.max(res, 0.005),
        residualDex: res,
        accuracyPercent: Math.min(
          100.0,
          Math.max(0.0, 100.0 - (Math.pow(10.0, res) - 1.0) * 100.0),
        ).toFixed(3),
        formula: formulaString,

        proofTrace: {
          logA,
          logB,
          logC,
          comboLog,
          targetLog,
          netDimensions: netDim,
          formulaString,
          residualDex: res,
        },
      });
    }

    readCounter.unmap();
    readHits.unmap();
    nodeBuffer.destroy();
    hitBuffer.destroy();
    counterBuffer.destroy();
    paramBuffer.destroy();
    readCounter.destroy();
    readHits.destroy();

    return discovered.sort((a, b) => a.residualDex - b.residualDex);
  }
}
