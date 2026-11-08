const G_CONSTANT = 6.6743e-11;
const BASE_BPM = 66.743;
const STEP_TIME_MS = (60.0 / BASE_BPM) * 1000;

export class GRMSequencer {
  constructor(synth, getNodeFreqFn, getRelFreqFn, getHarmonyColorFn) {
    this.synth = synth;
    this.getNodeFreq = getNodeFreqFn;
    this.getRelFreq = getRelFreqFn;
    this.getHarmonyColor = getHarmonyColorFn;

    this.isPlaying = false;
    this.timer = null;
    this.mode = "mixed";

    this.activeFades = [];
    this.nodeMeshes = null;
    this.linkLines = null;
    this.lastResult = null;

    this.sequenceIndex = 0;
  }

  init(nodeMeshes, linkLines) {
    this.nodeMeshes = nodeMeshes;
    this.linkLines = linkLines;
  }

  setResult(result) {
    this.lastResult = result;
  }

  start() {
    if (this.isPlaying) return;
    this.isPlaying = true;
    this.sequenceIndex = 0;
    this.synth.ensureContext();
    this.blackoutUniverse();
    this.scheduleNextStep(0);
  }

  stop() {
    this.isPlaying = false;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.activeFades = [];
  }

  blackoutUniverse() {
    if (!this.nodeMeshes || !this.linkLines) return;

    this.nodeMeshes.forEach((mesh) => {
      mesh.material.transparent = true;
      mesh.material.opacity = 0.03;
    });

    this.linkLines.forEach((line) => {
      line.material.opacity = 0.0;
      line.visible = false;
    });
  }

  scheduleNextStep(delay = STEP_TIME_MS) {
    if (!this.isPlaying) return;

    this.timer = setTimeout(() => {
      if (!this.isPlaying) return;
      this.playRandomStep();

      const gMod = Math.abs(Math.log10(G_CONSTANT)) * 0.01;
      const rhythmRatios = [1.0, 2 / 3 + gMod, 4 / 3 - gMod, 2.0];
      const ratio = rhythmRatios[this.sequenceIndex % rhythmRatios.length];
      this.scheduleNextStep(STEP_TIME_MS * ratio);
    }, delay);
  }

  playRandomStep() {
    if (!this.nodeMeshes || !this.linkLines || this.linkLines.length === 0)
      return;

    const sortedNodeNames = Array.from(this.nodeMeshes.keys()).sort((a, b) => {
      return this.getNodeFreq(a) - this.getNodeFreq(b);
    });

    if (sortedNodeNames.length === 0) return;

    const targetNode =
      sortedNodeNames[this.sequenceIndex % sortedNodeNames.length];
    this.sequenceIndex++;

    const pullMap = this.lastResult?.relation_pulls || {};
    const doChord =
      this.mode === "nodes" ||
      (this.mode === "mixed" && this.sequenceIndex % 3 !== 0);

    if (doChord) {
      this.triggerNodeConstellation(targetNode, pullMap);
    } else {
      const connectedLines = this.linkLines.filter(
        (l) =>
          l.userData.nodeA === targetNode || l.userData.nodeB === targetNode,
      );
      if (connectedLines.length > 0) {
        const line = connectedLines[this.sequenceIndex % connectedLines.length];
        this.triggerSingleString(line, pullMap);
      } else {
        this.triggerNodeConstellation(targetNode, pullMap);
      }
    }
  }

  triggerSingleString(line, pullMap) {
    const nodeA = line.userData.nodeA;
    const nodeB = line.userData.nodeB;
    const relName = line.userData.relName;
    const pull = pullMap[relName] || 0;

    const freq = this.getRelFreq(nodeA, nodeB);

    // Calculate physical velocity using G_CONSTANT and relation pull intensity
    const velocity = Math.min(
      0.98,
      Math.max(0.4, 0.7 + pull * 0.3 + (Math.log10(G_CONSTANT) + 10.5) * 0.05),
    );
    this.synth.pluck(freq, pull, 0.0, velocity);

    const { threeColor } = this.getHarmonyColor(pull);

    line.visible = true;
    line.material.color.copy(threeColor);
    line.material.opacity = 1.0;
    line.renderOrder = 3;

    const meshA = this.nodeMeshes.get(nodeA);
    const meshB = this.nodeMeshes.get(nodeB);

    if (meshA) {
      meshA.material.opacity = 1.0;
      this.pulseMesh(meshA);
    }
    if (meshB) {
      meshB.material.opacity = 1.0;
      this.pulseMesh(meshB);
    }

    const duration = 2200;
    this.activeFades.push({
      type: "string",
      line,
      meshA,
      meshB,
      startTime: performance.now(),
      duration,
    });
  }

  triggerNodeConstellation(nodeName, pullMap) {
    const rootMesh = this.nodeMeshes.get(nodeName);
    if (!rootMesh) return;

    const rootFreq = this.getNodeFreq(nodeName);
    this.synth.pluck(rootFreq, 0.0, 0.0, 0.85);

    rootMesh.material.opacity = 1.0;
    this.pulseMesh(rootMesh, 1.6);

    const connectedLines = this.linkLines.filter(
      (l) => l.userData.nodeA === nodeName || l.userData.nodeB === nodeName,
    );

    const maxNotes = Math.min(connectedLines.length, 6);
    const slicedLines = connectedLines.slice(0, maxNotes);

    slicedLines.forEach((line, idx) => {
      const partner =
        line.userData.nodeA === nodeName
          ? line.userData.nodeB
          : line.userData.nodeA;
      const relName = line.userData.relName;
      const pull = pullMap[relName] || 0;
      const freq = this.getRelFreq(nodeName, partner);
      const delaySec = 0.055 * (idx + 1);

      const velocity = Math.min(0.95, Math.max(0.35, 0.6 + pull * 0.25));
      this.synth.pluck(freq, pull, delaySec, velocity);

      const { threeColor } = this.getHarmonyColor(pull);
      const partnerMesh = this.nodeMeshes.get(partner);

      setTimeout(() => {
        if (!this.isPlaying) return;
        line.visible = true;
        line.material.color.copy(threeColor);
        line.material.opacity = 1.0;
        line.renderOrder = 3;

        if (partnerMesh) {
          partnerMesh.material.opacity = 1.0;
          this.pulseMesh(partnerMesh, 1.25);
        }

        this.activeFades.push({
          type: "branch",
          line,
          partnerMesh,
          startTime: performance.now(),
          duration: 2500,
        });
      }, delaySec * 1000);
    });

    this.activeFades.push({
      type: "root",
      mesh: rootMesh,
      startTime: performance.now(),
      duration: 3000,
    });
  }

  pulseMesh(mesh, scaleFactor = 1.35) {
    const baseScale = mesh.scale.x;
    mesh.scale.set(
      baseScale * scaleFactor,
      baseScale * scaleFactor,
      baseScale * scaleFactor,
    );
    setTimeout(() => {
      mesh.scale.set(baseScale, baseScale, baseScale);
    }, 250);
  }

  updateFades(now) {
    if (!this.isPlaying) return;

    for (let i = this.activeFades.length - 1; i >= 0; i--) {
      const item = this.activeFades[i];
      const elapsed = now - item.startTime;
      const progress = Math.min(elapsed / item.duration, 1.0);
      const fade = Math.pow(1.0 - progress, 2);

      if (item.type === "string") {
        item.line.material.opacity = Math.max(0.0, fade * 1.0);
        if (item.meshA)
          item.meshA.material.opacity = Math.max(0.03, fade * 1.0);
        if (item.meshB)
          item.meshB.material.opacity = Math.max(0.03, fade * 1.0);
        if (progress >= 1.0) item.line.visible = false;
      } else if (item.type === "branch") {
        item.line.material.opacity = Math.max(0.0, fade * 1.0);
        if (item.partnerMesh)
          item.partnerMesh.material.opacity = Math.max(0.03, fade * 1.0);
        if (progress >= 1.0) item.line.visible = false;
      } else if (item.type === "root") {
        if (item.mesh) item.mesh.material.opacity = Math.max(0.03, fade * 1.0);
      }

      if (progress >= 1.0) {
        this.activeFades.splice(i, 1);
      }
    }
  }
}
