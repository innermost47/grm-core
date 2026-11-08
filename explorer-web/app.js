import { NODE_DESCRIPTIONS } from "./descriptions.js";
import { Network } from "./grm.js";
import { DEFAULT_RELATIONS } from "./relations.js";
import { GRMSynth } from "./grm_synth.js";
import { GRMSequencer } from "./grm_sequencer.js";
import { GRMBridgeMiner } from "./grm_bridge_miner.js";
import { StateManager } from "./StateManager.js";

const GUIDE_STORAGE_KEY = "GRM_EXPLORER_HAS_SEEN_GUIDE";

const btnAddNode = document.getElementById("btn-add-node");
const btnAutoPlay = document.getElementById("btn-auto-play");
const selectInterval = document.getElementById("auto-interval-select");
const container = document.getElementById("canvas-container");
const logContainer = document.getElementById("expansion-log-content");
const menuToggleBtn = document.getElementById("btn-menu-toggle");
const dropdownMenu = document.getElementById("dropdown-menu");
const contextMenu = document.getElementById("context-menu");
const nodeModal = document.getElementById("node-modal");
const relModal = document.getElementById("relation-modal");
const netSelect = document.getElementById("network-select");

const bridgeMiner = new GRMBridgeMiner();
const state = new StateManager();
const synth = new GRMSynth();
const sequencer = new GRMSequencer(
  synth,
  getNodeFundamentalFreq,
  getRelationStringFreq,
  getHarmonyColor,
);

let scene, camera, renderer, controls;
let nodeMeshes = new Map();
let linkLines = [];
let raycaster, mouse;
let selectedNodeName = null;
let lastSolvedResult = null;
let pointerDownPos = { x: 0, y: 0 };
let isDragging = false;
let nodesVisible = true;
let relationsVisible = true;
let diagnosticVisible = window.innerWidth > 768;
let autoExpandIntervalId = null;
let isAutoExpanding = false;
let audioModeActive = false;
let expansionHistory = [];
let blueThreadLine = null;
let blueThreadActive = false;
let toolsPanelOpen = window.innerWidth > 900;
let currentMinedInvariants = [];
let redThreadLine = null;
let redThreadActive = false;
let lawMeshes = new Map();

function getRelationFormula(rel) {
  if (rel.formula && rel.formula !== rel.name) {
    return rel.formula;
  }
  if (!rel.terms) {
    return rel.name;
  }

  const parts = [];
  for (const [node, pow] of Object.entries(rel.terms)) {
    if (pow === 1) parts.push(node);
    else if (pow === -1) parts.push(`${node}^(-1)`);
    else parts.push(`${node}^(${pow})`);
  }

  const rhs = rel.rhs ?? 0.0;
  let kStr = "1.0";
  if (Math.abs(rhs - 0.30103) < 0.01) kStr = "2.0";
  else if (Math.abs(rhs - -0.30103) < 0.01) kStr = "1/2";
  else if (Math.abs(rhs - 0.60206) < 0.01) kStr = "4.0";
  else if (Math.abs(rhs - -0.60206) < 0.01) kStr = "1/4";
  else if (Math.abs(rhs - 0.49715) < 0.01) kStr = "π";
  else if (Math.abs(rhs - -0.49715) < 0.01) kStr = "1/π";
  else if (Math.abs(rhs - 0.79818) < 0.01) kStr = "2π";
  else if (Math.abs(rhs - 1.09921) < 0.01) kStr = "4π";
  else if (Math.abs(rhs - -0.17609) < 0.01) kStr = "2/3";
  else if (rhs !== 0.0) kStr = `10^(${rhs.toFixed(4)})`;

  return `${parts.join(" × ")} = ${kStr}`;
}

function resetLogContainer() {
  logContainer.innerHTML =
    "  <span class='log-empty-msg'>Awaiting generation...</span>";
}

function logExpansionEntry(nodeId, nodeSpec, relData) {
  if (!logContainer) return;

  if (expansionHistory.length === 0) {
    resetLogContainer();
  }

  const entry = {
    nodeId,
    guess: nodeSpec.guess,
    scale: nodeSpec.scale,
    relName: relData.name,
    parentA: nodeSpec.parentA,
    parentB: nodeSpec.parentB,
    formula: nodeSpec.formula || "N/A",
    relType: relData.type || relData.kind || "log-linear",
    relTerms: JSON.stringify(relData.terms),
    timestamp: new Date().toLocaleTimeString(),
  };
  expansionHistory.push(entry);

  const div = document.createElement("div");
  div.className = "log-item";
  div.innerHTML = ` 
<div><strong>[${entry.timestamp}]</strong> <span style="color:#34d399">${nodeId}</span></div> 
<div style="color:#f59e0b; font-size:10px;">📐 Equation: ${entry.formula}</div> 
<div style="color:#60a5fa; font-size:10px;">🔗 Relationship: ${entry.relName} (${entry.parentA} ⟷ ${entry.parentB})</div> 
`;

  logContainer.appendChild(div);
  logContainer.scrollTop = logContainer.scrollHeight;
}

window.copyExpansionLogs = function () {
  if (expansionHistory.length === 0) {
    alert("No logs to copy at the moment.");
    return;
  }

  const textToCopy = expansionHistory
    .map((item) => {
      const parentA = item.parentA || "unknown";
      const parentB = item.parentB || "unknown";

      return `// Node generated at ${item.timestamp}
"${item.nodeId}": { guess: ${item.guess}, scale: "${item.scale}" },
// Associated relation (Pair: ${parentA} ⟷ ${parentB}):
"${item.relName}": {
type: "${item.relType}",
terms: ${item.relTerms},
formula: "${item.formula}",
parents: ["${parentA}", "${parentB}"]
},`;
    })
    .join("\n\n");

  navigator.clipboard.writeText(textToCopy).then(() => {
    const btn =
      document.querySelector("#expansion-log-panel button") ||
      document.getElementById("btn-copy-logs");
    if (btn) {
      const originalText = btn.textContent;
      btn.textContent = "✓ Copied!";
      setTimeout(() => {
        btn.textContent = originalText;
      }, 1500);
    }
  });
};

function getNodeFundamentalFreq(nodeName) {
  if (nodeName === "f1_E2") return 82.41;
  if (nodeName === "f0_voice") return 118.0;
  if (nodeName === "f_helmholtz") return 120.0;
  if (nodeName === "fmid") return 255.0;
  if (nodeName === "F1_neutral") return 500.0;

  const curNet = state.getActive();
  const spec = curNet.nodes[nodeName];
  if (!spec) return 220.0;

  const solved = lastSolvedResult?.values?.[nodeName] ?? spec.guess;
  const raw = spec.scale === "lin" ? Math.abs(solved) : Math.abs(solved);
  const logVal = Math.log10(Math.max(raw, 1e-120));
  const frac = ((logVal % 1) + 1) % 1;

  return 130.81 * Math.pow(2, frac * 2.0);
}

function getRelationStringFreq(nodeA, nodeB) {
  const fA = getNodeFundamentalFreq(nodeA);
  const fB = getNodeFundamentalFreq(nodeB);
  return Math.sqrt(fA * fB);
}

function getHarmonyColor(pullVal) {
  const p = Math.abs(pullVal || 0);
  let hue;

  if (p <= 1.0) {
    hue = 145 - p * 45;
  } else if (p <= 2.0) {
    hue = 100 - (p - 1.0) * 55;
  } else if (p <= 3.0) {
    hue = 45 - (p - 2.0) * 45;
  } else {
    const t = Math.min((p - 3.0) / 2.0, 1.0);
    hue = 360 - t * 25;
  }

  const threeColor = new THREE.Color().setHSL(hue / 360, 0.95, 0.52);
  const cssColor = `hsl(${Math.round(hue)}, 95%, 52%)`;
  const t = Math.min(Math.max(p / 2.5, 0.0), 1.0);

  return { threeColor, cssColor, pull: p, t };
}

function init3D() {
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0b0f19, 0.0015);

  camera = new THREE.PerspectiveCamera(
    50,
    window.innerWidth / window.innerHeight,
    0.1,
    5000,
  );
  camera.position.set(0, 180, 500);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x050508, 1);

  container.appendChild(renderer.domElement);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.maxDistance = 2500;
  controls.minDistance = 20;
  controls.enablePan = true;
  controls.screenSpacePanning = true;
  controls.panSpeed = 1.2;

  controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.DOLLY,
    RIGHT: THREE.MOUSE.PAN,
  };

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
  scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0x38bdf8, 1.2);
  dirLight.position.set(200, 500, 300);
  scene.add(dirLight);

  const gridHelper = new THREE.GridHelper(3000, 60, 0x1e293b, 0x0f172a);
  gridHelper.position.y = -80;
  scene.add(gridHelper);

  raycaster = new THREE.Raycaster();
  raycaster.params.Line = { threshold: 4.5 };
  mouse = new THREE.Vector2();

  window.addEventListener("resize", onWindowResize);

  renderer.domElement.addEventListener(
    "wheel",
    (e) => {
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
        const delta = (e.shiftKey ? e.deltaY : e.deltaX) * 0.8;
        camera.position.x += delta;
        controls.target.x += delta;
      }
    },
    { passive: false },
  );

  window.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 80 : 25;
    if (e.key === "ArrowLeft" || e.key === "a" || e.key === "q") {
      camera.position.x -= step;
      controls.target.x -= step;
    } else if (e.key === "ArrowRight" || e.key === "d") {
      camera.position.x += step;
      controls.target.x += step;
    } else if (e.key === "ArrowUp" || e.key === "w" || e.key === "z") {
      camera.position.y += step;
      controls.target.y += step;
    } else if (e.key === "ArrowDown" || e.key === "s") {
      camera.position.y -= step;
      controls.target.y -= step;
    }
  });

  renderer.domElement.addEventListener("pointerdown", (e) => {
    pointerDownPos = { x: e.clientX, y: e.clientY };
    isDragging = false;
    onPointerDown(e);
  });

  renderer.domElement.addEventListener("pointermove", (e) => {
    const dist = Math.hypot(
      e.clientX - pointerDownPos.x,
      e.clientY - pointerDownPos.y,
    );
    if (dist > 5) isDragging = true;
  });

  renderer.domElement.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    if (!isDragging) {
      onContextMenu(e);
    }
  });

  setupNavigationButtons();
  setupAudioModeToggle();
}

function setupAudioModeToggle() {
  const btn = document.getElementById("btn-audio-mode");
  const statusPanel = document.getElementById("status-panel");
  const infoBubble = document.getElementById("info-bubble");
  const seqPanel = document.getElementById("sequencer-panel");
  if (!btn) return;

  btn.addEventListener("click", () => {
    audioModeActive = !audioModeActive;
    synth.ensureContext();
    btn.textContent = audioModeActive
      ? "🎵 Audio Resonance: ON"
      : "🎵 Audio Resonance: OFF";

    if (audioModeActive) {
      if (statusPanel) statusPanel.classList.add("hidden");
      if (infoBubble) infoBubble.classList.add("hidden");
      if (seqPanel) seqPanel.classList.remove("hidden");
      applyFullNetworkColors();
    } else {
      if (statusPanel) statusPanel.classList.remove("hidden");
      if (seqPanel) seqPanel.classList.add("hidden");
      if (sequencer.isPlaying) {
        sequencer.stop();
        document.getElementById("btn-seq-toggle").textContent = "▶ Start";
      }
      applyFullNetworkColors();
    }
  });

  document.getElementById("btn-seq-toggle")?.addEventListener("click", () => {
    const btnSeq = document.getElementById("btn-seq-toggle");
    if (!sequencer.isPlaying) {
      sequencer.start();
      btnSeq.textContent = "⏸ Pause";
      btnSeq.className = "btn btn-danger btn-sm";
    } else {
      sequencer.stop();
      btnSeq.textContent = "▶ Start";
      btnSeq.className = "btn btn-primary btn-sm";
      applyFullNetworkColors();
    }
  });

  document
    .getElementById("seq-mode-select")
    ?.addEventListener("change", (e) => {
      sequencer.mode = e.target.value;
    });
}

function setupNavigationButtons() {
  const panStep = 150;

  document.getElementById("btn-pan-left")?.addEventListener("click", () => {
    slideCameraX(controls.target.x - panStep);
  });

  document.getElementById("btn-pan-right")?.addEventListener("click", () => {
    slideCameraX(controls.target.x + panStep);
  });

  document.querySelectorAll(".btn-jump").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetX = parseFloat(btn.getAttribute("data-target"));
      slideCameraX(targetX);
    });
  });
}

function slideCameraX(targetX) {
  const startTargetX = controls.target.x;
  const startCamX = camera.position.x;
  const diff = targetX - startTargetX;
  const startTime = performance.now();
  const duration = 600;

  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1.0);
    const ease = 1 - Math.pow(1 - progress, 3);

    controls.target.x = startTargetX + diff * ease;
    camera.position.x = startCamX + diff * ease;

    if (progress < 1.0) {
      requestAnimationFrame(step);
    }
  }
  requestAnimationFrame(step);
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function computeNodePosition(name, spec, index) {
  const g = spec.guess;
  const absLog =
    spec.scale === "lin" ? 0 : Math.log10(Math.max(Math.abs(g), 1e-130));
  const x = (absLog + 20) * 8.5;
  const angle = index * 0.45 + absLog * 0.1;
  const radius = 35 + (index % 5) * 14;
  const y = Math.sin(angle) * radius;
  const z = Math.cos(angle) * radius;
  return new THREE.Vector3(x, y, z);
}

function applyFullNetworkColors() {
  if (!lastSolvedResult) return;
  const pulls = lastSolvedResult.relation_pulls || {};

  linkLines.forEach((line) => {
    if (line.userData.isLawLine) {
      line.material.color.setHex(0xfca5a5);
      line.material.opacity = 0.85;
      line.renderOrder = 4;
      line.visible = relationsVisible;
    } else {
      const pullVal = pulls[line.userData.relName] || 0;
      const { threeColor, t } = getHarmonyColor(pullVal);
      line.material.color.copy(threeColor);
      line.material.opacity = 0.45 + t * 0.5;
      line.renderOrder = t > 0.4 ? 2 : 1;
      line.visible = relationsVisible;
    }
  });

  nodeMeshes.forEach((mesh) => {
    mesh.material.transparent = false;
    mesh.material.opacity = 1.0;
  });

  lawMeshes.forEach((mesh) => {
    mesh.material.transparent = false;
    mesh.material.opacity = 1.0;
    mesh.scale.set(1.0, 1.0, 1.0);
  });
}

function getConnectedLinesForNode(nodeName) {
  if (!nodeName || !lastSolvedResult) return [];
  const pulls = lastSolvedResult.relation_pulls || {};
  const items = [];

  linkLines.forEach((line) => {
    const isConn =
      line.userData.nodeA === nodeName || line.userData.nodeB === nodeName;
    if (isConn) {
      const relName = line.userData.relName;
      const pullVal = pulls[relName] || 0;
      const { cssColor, pull, t } = getHarmonyColor(pullVal);
      const partner =
        line.userData.nodeA === nodeName
          ? line.userData.nodeB
          : line.userData.nodeA;
      items.push({ relName, partner, pull, cssColor, t, line });
    }
  });

  items.sort((a, b) => b.pull - a.pull);
  return items;
}

function focusNodeNetwork(nodeName) {
  if (!nodeName || !lastSolvedResult) return [];
  const pulls = lastSolvedResult.relation_pulls || {};

  const connectedPartners = new Set([nodeName]);
  const connectedItems = [];

  linkLines.forEach((line) => {
    const isConn =
      line.userData.nodeA === nodeName || line.userData.nodeB === nodeName;

    if (isConn) {
      const relName = line.userData.relName;
      const pullVal = pulls[relName] || 0;
      const { threeColor, cssColor, pull, t } = getHarmonyColor(pullVal);

      line.material.color.copy(threeColor);
      line.material.opacity = 0.95;
      line.renderOrder = 3;
      line.visible = true;

      const partner =
        line.userData.nodeA === nodeName
          ? line.userData.nodeB
          : line.userData.nodeA;
      connectedPartners.add(partner);
      connectedItems.push({ relName, partner, pull, cssColor, t, line });
    } else {
      line.material.opacity = 0.02;
      line.renderOrder = 0;
    }
  });

  nodeMeshes.forEach((mesh, name) => {
    mesh.material.transparent = true;
    if (connectedPartners.has(name)) {
      mesh.material.opacity = 1.0;
    } else {
      mesh.material.opacity = 0.08;
    }
  });

  connectedItems.sort((a, b) => b.pull - a.pull);
  return connectedItems;
}

function playNodeChord(nodeName, connectedItems) {
  if (!relationsVisible) return;
  if (!audioModeActive) return;

  synth.ensureContext();

  const baseFreq = getNodeFundamentalFreq(nodeName);
  synth.pluck(baseFreq, 0.0, 0.0, 0.85);

  const maxStrings = Math.min(connectedItems.length, 6);
  for (let i = 0; i < maxStrings; i++) {
    const it = connectedItems[i];
    const freq = getRelationStringFreq(nodeName, it.partner);
    const delay = 0.055 * (i + 1);
    synth.pluck(freq, it.pull, delay, 0.5);

    if (it.line) {
      const prevColor = it.line.material.color.clone();
      it.line.material.color.setHex(0xffffff);
      it.line.material.opacity = 1.0;
      setTimeout(
        () => {
          it.line.material.color.copy(prevColor);
          it.line.material.opacity = 0.8;
        },
        300 + i * 50,
      );
    }
  }

  const clickedMesh = nodeMeshes.get(nodeName);
  if (clickedMesh) {
    const origScale = clickedMesh.scale.x;
    clickedMesh.scale.set(origScale * 1.35, origScale * 1.35, origScale * 1.35);
    setTimeout(() => {
      clickedMesh.scale.set(origScale, origScale, origScale);
    }, 280);
  }
}

function playSingleRelationString(line) {
  if (!audioModeActive) return;

  synth.ensureContext();

  const nodeA = line.userData.nodeA;
  const nodeB = line.userData.nodeB;
  const relName = line.userData.relName;
  const pull = lastSolvedResult?.relation_pulls?.[relName] || 0;
  const freq = getRelationStringFreq(nodeA, nodeB);

  synth.pluck(freq, pull, 0.0, 0.9);

  const prevColor = line.material.color.clone();
  line.material.color.setHex(0xffffff);
  line.material.opacity = 1.0;

  setTimeout(() => {
    line.material.color.copy(prevColor);
    line.material.opacity = 0.75;
  }, 300);
}

function showNodeBubble(name) {
  selectedNodeName = name;
  const curNet = state.getActive();
  const spec = curNet.nodes[name];
  const bubble = document.getElementById("info-bubble");
  const title = document.getElementById("bubble-title");
  const subtitle = document.getElementById("bubble-subtitle");
  const content = document.getElementById("bubble-content");
  const toggleBtn = document.getElementById("btn-toggle-active");

  const connectedRels = focusNodeNetwork(name);
  if (audioModeActive) {
    playNodeChord(name, connectedRels);
  }

  const isDisabled = (curNet.disabledNodes || []).includes(name);
  const solvedVal = lastSolvedResult?.values?.[name];
  const unc = lastSolvedResult?.uncertainty?.[name];
  const meas = curNet.measured?.[name];

  title.textContent = name;
  subtitle.textContent = `Identifier: ${name} | Scale: ${spec.scale || "log"}`;
  title.style.color = isDisabled ? "var(--text-muted)" : "var(--primary)";

  const desc =
    NODE_DESCRIPTIONS[name] || "Physical quantity of the GRM network";

  let relsHtml = "";
  if (connectedRels.length > 0) {
    relsHtml = ` 
<div class="bubble-relations-title"> 
Relations (${connectedRels.length}) — <em>Agreement &sigma; :</em> 
</div> 
<div class="bubble-relations-list"> 
${connectedRels
  .map((r) => {
    let qualif = "Perfect match";
    if (r.pull > 3.0) qualif = "Critical Friction";
    else if (r.pull > 2.0) qualif = "Proven voltage";
    else if (r.pull > 1.0) qualif = "Normal compromise";
    else if (r.pull > 0.2) qualif = "Harmonic";

    return ` 
<div class="bubble-rel-item"> 
<span class="rel-indicator" style="background:${r.cssColor}; box-shadow:0 0 6px ${r.cssColor};"></span> 
<span class="rel-name" title="${r.relName}">${r.relName}</span> 
<span class="rel-target">⟶ ${r.partner}</span> 
<span style="font-size:9px; color:${r.cssColor};">${qualif}</span> 
<strong class="rel-pull" style="color:${r.cssColor}">${r.pull.toFixed(2)} &sigma;</strong> 
</div> 
`;
  })
  .join("")} 
</div> 
`;
  }

  content.innerHTML = ` 
<div class="bubble-desc-box">${desc}</div> 
<div><strong>Estimate value (guess):</strong> ${formatPhys(spec.guess)}</div> 
${solvedVal !== undefined ? `<div><strong>Resolved value:</strong> <span style="color:#34d399; font-weight:bold;">${formatPhys(solvedVal)}</span> ${unc ? `± ${(unc * 100).toFixed(2)}%` : ""}</div>` : ""} 
${meas ? `<div><strong>Experimental measurement:</strong> ${formatPhys(meas[0])} (&sigma; = ${meas[1]})</div>` : ""}
<div><strong>Status:</strong> ${isDisabled ? "Disabled" : spec.fixed ? "Fixed constant" : "Derived variable"}</div>
${relsHtml}
`;

  toggleBtn.textContent = isDisabled ? "Re-enable node" : "Disable node";
  toggleBtn.className = isDisabled
    ? "btn btn-primary btn-sm"
    : "btn btn-danger btn-sm";

  bubble.classList.remove("hidden");
}

function focusLawNetwork(lawName, participants) {
  if (!lawName) return;

  const activeNodeSet = new Set(participants);

  linkLines.forEach((line) => {
    if (line.userData.lawName === lawName) {
      line.material.color.setHex(0xf87171);
      line.material.opacity = 1.0;
      line.renderOrder = 6;
      line.visible = true;
    } else {
      line.material.opacity = 0.02;
      line.renderOrder = 0;
    }
  });

  nodeMeshes.forEach((mesh, name) => {
    mesh.material.transparent = true;
    if (activeNodeSet.has(name)) {
      mesh.material.opacity = 1.0;
      mesh.renderOrder = 5;
    } else {
      mesh.material.opacity = 0.06;
      mesh.renderOrder = 0;
    }
  });

  lawMeshes.forEach((mesh, name) => {
    mesh.material.transparent = true;
    if (name === lawName) {
      mesh.material.opacity = 1.0;
      mesh.scale.set(1.4, 1.4, 1.4);
      mesh.renderOrder = 7;
    } else {
      mesh.material.opacity = 0.06;
      mesh.scale.set(1.0, 1.0, 1.0);
      mesh.renderOrder = 0;
    }
  });
}

function buildSceneGraph() {
  nodeMeshes.forEach((mesh) => scene.remove(mesh));
  nodeMeshes.clear();
  linkLines.forEach((line) => scene.remove(line));
  linkLines = [];
  lawMeshes.forEach((mesh) => scene.remove(mesh));
  lawMeshes.clear();

  const curNet = state.getActive();
  const nodes = curNet.nodes;
  const disabled = new Set(curNet.disabledNodes || []);
  const nodeNames = Object.keys(nodes);

  const nodeGeometry = new THREE.SphereGeometry(3.2, 16, 16);
  nodeNames.forEach((name, idx) => {
    const spec = nodes[name];
    const isDisabled = disabled.has(name);
    const isFixed = !!spec.fixed;
    const isMeasured = curNet.measured && name in curNet.measured;
    const isAuto = name.startsWith("node_auto_");

    let color = 0x38bdf8;
    if (isDisabled) color = 0x475569;
    else if (isFixed) color = 0x3b82f6;
    else if (isMeasured) color = 0x10b981;
    else if (isAuto) color = 0xfbbf24;
    else color = 0xa855f7;

    const material = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.25,
      metalness: 0.3,
      emissive: isDisabled ? 0x000000 : color,
      emissiveIntensity: isFixed ? 0.6 : isDisabled ? 0.0 : 0.25,
    });

    const mesh = new THREE.Mesh(nodeGeometry, material);
    mesh.position.copy(computeNodePosition(name, spec, idx));
    mesh.userData = { name, spec, isDisabled };

    if (isFixed) mesh.scale.set(1.65, 1.65, 1.65);

    scene.add(mesh);
    nodeMeshes.set(name, mesh);
  });

  const allCustomRels = curNet.customRelations || [];
  const lawGeometry = new THREE.SphereGeometry(2.4, 16, 16);
  const lawMaterial = new THREE.MeshStandardMaterial({
    color: 0xf87171,
    emissive: 0xef4444,
    emissiveIntensity: 0.9,
    roughness: 0.15,
    metalness: 0.6,
  });

  allCustomRels.forEach((rel) => {
    if (rel.name.startsWith("invariant_") || rel.name.startsWith("bridge_")) {
      const participants = rel.terms ? Object.keys(rel.terms) : rel.nodes || [];
      const activePositions = [];

      participants.forEach((nodeName) => {
        const m = nodeMeshes.get(nodeName);
        if (m) activePositions.push(m.position);
      });

      if (activePositions.length >= 2) {
        const center = new THREE.Vector3();
        activePositions.forEach((pos) => center.add(pos));
        center.divideScalar(activePositions.length);

        const lawMesh = new THREE.Mesh(lawGeometry, lawMaterial.clone());
        lawMesh.position.copy(center);
        lawMesh.userData = {
          isLaw: true,
          name: rel.name,
          formula: getRelationFormula(rel),
          participants: participants,
          rhs: rel.rhs,
        };

        scene.add(lawMesh);
        lawMeshes.set(rel.name, lawMesh);

        activePositions.forEach((nodePos, i) => {
          const participantName = participants[i];
          const geom = new THREE.BufferGeometry().setFromPoints([
            center,
            nodePos,
          ]);
          const lineMat = new THREE.LineBasicMaterial({
            color: 0xfca5a5,
            transparent: true,
            opacity: 0.85,
          });
          const line = new THREE.Line(geom, lineMat);
          line.renderOrder = 4;

          line.userData = {
            isLawLine: true,
            lawName: rel.name,
            nodeA: rel.name,
            nodeB: participantName,
          };

          scene.add(line);
          linkLines.push(line);
        });
      }
    }
  });

  const standardRels = [
    ...DEFAULT_RELATIONS,
    ...allCustomRels.filter(
      (r) => !r.name.startsWith("invariant_") && !r.name.startsWith("bridge_"),
    ),
  ];
  standardRels.forEach((rel) => {
    let linked = rel.terms ? Object.keys(rel.terms) : rel.nodes;
    for (let i = 0; i < linked.length; i++) {
      for (let j = i + 1; j < linked.length; j++) {
        const m1 = nodeMeshes.get(linked[i]);
        const m2 = nodeMeshes.get(linked[j]);
        if (m1 && m2) {
          const geom = new THREE.BufferGeometry().setFromPoints([
            m1.position,
            m2.position,
          ]);
          const mat = new THREE.LineBasicMaterial({
            color: 0x10b981,
            transparent: true,
            opacity: 0.5,
          });
          const line = new THREE.Line(geom, mat);
          line.userData = {
            relName: rel.name,
            nodeA: linked[i],
            nodeB: linked[j],
          };
          scene.add(line);
          linkLines.push(line);
        }
      }
    }
  });

  applyFullNetworkColors();
}

function solveActiveNetwork() {
  const curNet = state.getActive();
  const disabled = new Set(curNet.disabledNodes || []);

  const activeNodesSpec = {};
  for (const [name, spec] of Object.entries(curNet.nodes)) {
    if (!disabled.has(name)) activeNodesSpec[name] = spec;
  }

  const activeMeasurements = {};
  for (const [name, meas] of Object.entries(curNet.measured || {})) {
    if (!disabled.has(name)) activeMeasurements[name] = meas;
  }

  const candidateRelations = [
    ...DEFAULT_RELATIONS,
    ...(curNet.customRelations || []),
  ];
  const activeRelations = candidateRelations.filter((rel) => {
    let participants = rel.terms ? Object.keys(rel.terms) : rel.nodes;
    return participants.every((p) => !disabled.has(p));
  });

  try {
    const netSolver = new Network(activeNodesSpec, activeRelations);
    const result = netSolver.solve(activeMeasurements, { maxIterations: 60 });
    lastSolvedResult = result;
    sequencer.setResult(result);
    updateStatusUI(result, null);

    if (!selectedNodeName || audioModeActive) {
      applyFullNetworkColors();
    } else {
      focusNodeNetwork(selectedNodeName);
    }
  } catch (err) {
    updateStatusUI(null, err.message);
  }
}

function updateStatusUI(result, errorMsg) {
  const badge = document.getElementById("net-badge");
  const stabilityStatus = document.getElementById("stability-status");
  const costVal = document.getElementById("cost-val");
  const chi2Val = document.getElementById("chi2-val");
  const dofVal = document.getElementById("dof-val");
  const energyVal = document.getElementById("energy-val");
  const energyHint = document.getElementById("energy-hint");
  const pullsList = document.getElementById("top-pulls");
  const disabledCount = document.getElementById("disabled-count");
  const disabledTags = document.getElementById("disabled-tags");

  const curNet = state.getActive();
  const disabled = curNet.disabledNodes || [];
  if (disabledCount) disabledCount.textContent = disabled.length;

  if (disabledTags) {
    disabledTags.innerHTML = "";
    disabled.forEach((name) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = `${name} ✕`;
      tag.title = "Click to reactivate";
      tag.onclick = () => toggleNodeActive(name);
      disabledTags.appendChild(tag);
    });
  }

  if (errorMsg || !result || !Number.isFinite(result.cost)) {
    if (badge) {
      badge.className = "badge unstable";
      badge.textContent = "Friction";
    }
    if (stabilityStatus) {
      stabilityStatus.textContent = "Divergence / Blocked Manifold";
      stabilityStatus.style.color = "var(--danger)";
    }
    if (costVal) costVal.textContent = "∞";
    if (chi2Val) chi2Val.textContent = "---";
    if (dofVal) dofVal.textContent = "---";
    if (energyVal) {
      energyVal.textContent = "Infinite";
      energyVal.style.color = "var(--danger)";
    }
    if (energyHint)
      energyHint.textContent = `Error: ${errorMsg || "Incompatible constraint"}`;
    if (pullsList) pullsList.innerHTML = "<li>No stationary state</li>";
    return;
  }

  const rawCost = Math.max(0, Number(result.cost) || 0);
  const dof = Math.max(1, Number(result.dof) || 1);
  const chi2 =
    Number.isFinite(result.reduced_chi2) && result.reduced_chi2 !== null
      ? Math.max(0, Number(result.reduced_chi2))
      : rawCost / dof;

  if (costVal)
    costVal.textContent =
      rawCost >= 1e5 ? rawCost.toExponential(3) : rawCost.toFixed(2);
  if (chi2Val)
    chi2Val.textContent = chi2 >= 1e4 ? chi2.toExponential(3) : chi2.toFixed(3);
  if (dofVal) dofVal.textContent = result.dof;

  const rmsStrain = Math.sqrt(chi2);
  if (energyVal) energyVal.textContent = rmsStrain.toFixed(3);

  if (result.converged && chi2 <= 1.0) {
    if (badge) {
      badge.className = "badge stable";
      badge.textContent = "Harmonized";
    }
    if (stabilityStatus) {
      stabilityStatus.textContent = "Absolute zero-point equilibrium";
      stabilityStatus.style.color = "#34d399";
    }
    if (energyVal) energyVal.style.color = "#34d399";
    if (energyHint)
      energyHint.textContent =
        "The network is relaxed: no friction between the atom and the cosmos.";
  } else if (result.converged && chi2 <= 2.5) {
    if (badge) {
      badge.className = "voltage badge";
      badge.textContent = "Compromise";
    }
    if (stabilityStatus) {
      stabilityStatus.textContent = "Acceptable moderate tension";
      stabilityStatus.style.color = "#fbbf24";
    }
    if (energyVal) energyVal.style.color = "#fbbf24";
    if (energyHint)
      energyHint.textContent = `Residual tension: it would be necessary to relax ~${(rmsStrain * 0.1).toFixed(2)} dex to close the zero point.`;
  } else {
    if (badge) {
      badge.className = "badge unstable";
      badge.textContent = "Friction";
    }
    if (stabilityStatus) {
      stabilityStatus.textContent = "Critical projection voltage";
      stabilityStatus.style.color = "#f87171";
    }
    if (energyVal) energyVal.style.color = "#f87171";
    if (energyHint)
      energyHint.textContent = `Critical friction: ~${(rmsStrain * 0.1).toFixed(2)} voltage dex to release.`;
  }

  if (pullsList) {
    pullsList.innerHTML = "";
    if (result.relation_pulls) {
      const sorted = Object.entries(result.relation_pulls)
        .map(([k, p]) => [k, Math.abs(Number(p) || 0)])
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

      sorted.forEach(([name, pull]) => {
        const { cssColor } = getHarmonyColor(pull);
        const li = document.createElement("li");
        li.innerHTML = `<span>${name}</span> <strong style="color:${cssColor}">${pull.toFixed(2)} &sigma;</strong>`;
        pullsList.appendChild(li);
      });
    }
  }
}

function onPointerDown(event) {
  if (event.button !== 0) return;
  hideContextMenu();

  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);

  const lawIntersects = raycaster.intersectObjects(
    Array.from(lawMeshes.values()),
  );
  if (lawIntersects.length > 0) {
    const hitLaw = lawIntersects[0].object.userData;
    selectedNodeName = hitLaw.name;

    focusLawNetwork(hitLaw.name, hitLaw.participants);

    const bubble = document.getElementById("info-bubble");
    const title = document.getElementById("bubble-title");
    const subtitle = document.getElementById("bubble-subtitle");
    const content = document.getElementById("bubble-content");

    title.textContent = "⚡ Invariant Law Nexus";
    title.style.color = "#f87171";
    subtitle.textContent = hitLaw.name;

    content.innerHTML = `
      <div class="bubble-desc-box" style="border-left-color: #f87171;">
        Discovered Physical Invariant (WebGPU Law Nexus)
      </div>
      <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">Exact Mathematical Formula :</div>
      <div style="font-size: 14px; font-weight: 800; color: #fca5a5; font-family: monospace; background: rgba(0,0,0,0.3); padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(248, 113, 113, 0.3); margin: 4px 0;">
        ${hitLaw.formula}
      </div>
      <div><strong>Target Scaling (K) :</strong> <span style="color:#38bdf8; font-weight:bold;">${hitLaw.rhs !== undefined ? `10^(${hitLaw.rhs.toFixed(4)})` : "1.0"}</span></div>
      <div><strong>Connected Entities :</strong> ${hitLaw.participants.join(", ")}</div>
    `;
    bubble.classList.remove("hidden");
    return;
  }

  if (nodesVisible) {
    const nodeIntersects = raycaster.intersectObjects(
      Array.from(nodeMeshes.values()).filter((m) => m.visible),
    );
    if (nodeIntersects.length > 0) {
      const hitNodeName = nodeIntersects[0].object.userData.name;

      if (audioModeActive) {
        const connected = getConnectedLinesForNode(hitNodeName);
        playNodeChord(hitNodeName, connected);
      } else {
        showNodeBubble(hitNodeName);
      }
      return;
    }
  }

  if (relationsVisible) {
    const lineIntersects = raycaster.intersectObjects(
      linkLines.filter((l) => l.visible),
    );
    if (lineIntersects.length > 0) {
      if (audioModeActive) {
        playSingleRelationString(lineIntersects[0].object);
      }
      return;
    }
  }

  if (!isDragging && !audioModeActive) {
    document.getElementById("info-bubble").classList.add("hidden");
    selectedNodeName = null;
    applyFullNetworkColors();
  }
}

function formatPhys(val) {
  if (val === undefined || val === null) return "---";
  const num = Number(val);
  if (Math.abs(num) >= 1e4 || (Math.abs(num) < 1e-3 && num !== 0)) {
    return num.toExponential(4);
  }
  return num.toFixed(4);
}

function toggleNodeActive(name) {
  const curNet = state.getActive();
  curNet.disabledNodes = curNet.disabledNodes || [];
  const idx = curNet.disabledNodes.indexOf(name);
  if (idx >= 0) curNet.disabledNodes.splice(idx, 1);
  else curNet.disabledNodes.push(name);

  state.save();
  buildSceneGraph();
  solveActiveNetwork();
  if (selectedNodeName === name) showNodeBubble(name);
}

function onContextMenu(event) {
  event.preventDefault();
  contextMenu.style.left = `${event.clientX}px`;
  contextMenu.style.top = `${event.clientY}px`;
  contextMenu.classList.remove("hidden");
}

function hideContextMenu() {
  contextMenu.classList.add("hidden");
}

function refreshNetworkSelect() {
  netSelect.innerHTML = "";
  state.data.networks.forEach((net) => {
    const opt = document.createElement("option");
    opt.value = net.id;
    opt.textContent = net.name;
    if (net.id === state.data.activeId) opt.selected = true;
    netSelect.appendChild(opt);
  });
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();

  if (sequencer.isPlaying) {
    sequencer.updateFades(performance.now());
  }

  renderer.render(scene, camera);
}

function checkFirstVisitGuide() {
  const hasSeenGuide = localStorage.getItem(GUIDE_STORAGE_KEY);
  const guideModalEl = document.getElementById("guide-modal");

  if (!hasSeenGuide && guideModalEl) {
    guideModalEl.classList.remove("hidden");
  }
}

function markGuideAsSeen() {
  localStorage.setItem(GUIDE_STORAGE_KEY, "true");
}

function toggleRedThread() {
  redThreadActive = !redThreadActive;
  const btn = document.getElementById("btn-red-thread");
  if (btn) {
    btn.textContent = redThreadActive
      ? "🔴 Red Thread: ON"
      : "🔴 Red Thread: OFF";
  }

  if (redThreadActive) {
    buildRedThread();
  } else {
    removeRedThread();
  }
}

function buildThread(isTop) {
  if (isTop) {
    removeRedThread();
  } else {
    removeBlueThread();
  }

  if (!nodeMeshes || nodeMeshes.size === 0) return;

  const filteredNodes = Array.from(nodeMeshes.values()).filter((mesh) =>
    isTop ? mesh.position.y >= 0 : mesh.position.y <= 0,
  );

  if (filteredNodes.length < 2) return;

  filteredNodes.sort((a, b) => a.position.x - b.position.x);
  const minX = filteredNodes[0].position.x;
  const maxX = filteredNodes[filteredNodes.length - 1].position.x;

  const numBins = 160;
  const binWidth = (maxX - minX) / numBins;
  const rawPoints = [];

  for (let i = 0; i <= numBins; i++) {
    const binMinX = minX + i * binWidth;
    const binMaxX = binMinX + binWidth;

    const binNodes = filteredNodes.filter(
      (n) =>
        n.position.x >= binMinX &&
        (i === numBins ? n.position.x <= binMaxX : n.position.x < binMaxX),
    );

    if (binNodes.length > 0) {
      let extreme = binNodes[0];
      binNodes.forEach((n) => {
        const condition = isTop
          ? n.position.y > extreme.position.y
          : n.position.y < extreme.position.y;
        if (condition) extreme = n;
      });
      rawPoints.push(extreme.position.clone());
    }
  }

  if (rawPoints.length < 2) return;

  const envelopePoints = [];
  for (let i = 0; i < rawPoints.length; i++) {
    let sumX = 0,
      sumY = 0,
      sumZ = 0,
      count = 0;
    for (
      let j = Math.max(0, i - 1);
      j <= Math.min(rawPoints.length - 1, i + 1);
      j++
    ) {
      sumX += rawPoints[j].x;
      sumY += rawPoints[j].y;
      sumZ += rawPoints[j].z;
      count++;
    }
    envelopePoints.push(
      new THREE.Vector3(sumX / count, sumY / count, sumZ / count),
    );
  }

  const curve = new THREE.CatmullRomCurve3(
    envelopePoints,
    false,
    "catmullrom",
    0.35,
  );
  const tubeGeometry = new THREE.TubeGeometry(curve, 500, 0.8, 8, false);

  const material = new THREE.MeshStandardMaterial({
    color: isTop ? 0xff0033 : 0x00d2ff,
    emissive: isTop ? 0xff0022 : 0x0088ff,
    emissiveIntensity: 1.5,
    roughness: 0.2,
    metalness: 0.8,
    transparent: true,
    opacity: 1.0,
  });

  const threadMesh = new THREE.Mesh(tubeGeometry, material);
  threadMesh.renderOrder = isTop ? 10 : 9;
  scene.add(threadMesh);

  if (isTop) {
    redThreadLine = threadMesh;
  } else {
    blueThreadLine = threadMesh;
  }
}

function buildRedThread() {
  buildThread(true);
}

function buildBlueThread() {
  buildThread(false);
}

function toggleNodesVisibility() {
  nodesVisible = !nodesVisible;
  const btn = document.getElementById("btn-toggle-nodes");
  if (btn) {
    btn.textContent = nodesVisible
      ? "🟢 Nodes Display: ON"
      : "⚪ Nodes Display: OFF";
  }

  nodeMeshes.forEach((mesh) => {
    mesh.visible = nodesVisible;
  });
}

function toggleRelationsVisibility() {
  relationsVisible = !relationsVisible;
  const btn = document.getElementById("btn-toggle-rels");
  if (btn) {
    btn.textContent = relationsVisible
      ? "🔗 Relations Display: ON"
      : "⚪ Relations Display: OFF";
  }

  linkLines.forEach((line) => {
    line.visible = relationsVisible;
  });
}

function removeRedThread() {
  if (redThreadLine) {
    scene.remove(redThreadLine);
    redThreadLine.geometry.dispose();
    redThreadLine.material.dispose();
    redThreadLine = null;
  }
}

function toggleBlueThread() {
  blueThreadActive = !blueThreadActive;
  const btn = document.getElementById("btn-blue-thread");
  if (btn) {
    btn.textContent = blueThreadActive
      ? "🔵 Blue Thread: ON"
      : "🔵 Blue Thread: OFF";
  }

  if (blueThreadActive) {
    buildBlueThread();
  } else {
    removeBlueThread();
  }
}

function removeBlueThread() {
  if (blueThreadLine) {
    scene.remove(blueThreadLine);
    blueThreadLine.geometry.dispose();
    blueThreadLine.material.dispose();
    blueThreadLine = null;
  }
}

function toggleDiagnosticPanel(forceState) {
  diagnosticVisible =
    typeof forceState === "boolean" ? forceState : !diagnosticVisible;

  const panel = document.getElementById("status-panel");
  const floatingBtn = document.getElementById("btn-floating-diag");
  const btnToggle = document.getElementById("btn-toggle-diag");

  if (panel) {
    panel.classList.toggle("collapsed", !diagnosticVisible);
  }

  if (floatingBtn) {
    floatingBtn.classList.toggle("hidden", diagnosticVisible);
  }

  if (btnToggle) {
    btnToggle.textContent = diagnosticVisible
      ? "📊 Diagnostics Panel: ON"
      : "📊 Diagnostics Panel: OFF";
  }
}

function autoExpandNetwork(nodes, relations, thresholdTension = 0.75) {
  let newNodes = JSON.parse(JSON.stringify(nodes));
  let newRelations = JSON.parse(JSON.stringify(relations));
  let addedCount = 0;

  let nodeKeys = Object.keys(newNodes);
  nodeKeys.sort(() => Math.random() - 0.5);

  for (let i = 0; i < nodeKeys.length && addedCount < 2; i++) {
    const nodeAName = nodeKeys[i];
    const meshA = nodeMeshes.get(nodeAName);
    if (!meshA) continue;

    for (let j = i + 1; j < nodeKeys.length; j++) {
      const nodeBName = nodeKeys[j];
      const meshB = nodeMeshes.get(nodeBName);

      if (meshB) {
        const distance = meshA.position.distanceTo(meshB.position);
        const tension = Math.abs(distance - 50) / 50;

        if ((tension > thresholdTension || distance > 120) && addedCount < 2) {
          const nodeASpec = newNodes[nodeAName] || { guess: 1.0 };
          const nodeBSpec = newNodes[nodeBName] || { guess: 1.0 };

          const scaleA = nodeASpec.scale || "log";
          const scaleB = nodeBSpec.scale || "log";

          if (scaleA !== scaleB) continue;

          if (!nodeASpec.dim || !nodeBSpec.dim) {
            continue;
          }

          const dimA = nodeASpec.dim || [0, 0, 0, 0, 0];
          const dimB = nodeBSpec.dim || [0, 0, 0, 0, 0];

          let newDim = [0, 0, 0, 0, 0];
          let isValidPhysics = true;

          if (scaleA === "lin") {
            for (let k = 0; k < 5; k++) {
              if (dimA[k] !== dimB[k]) {
                isValidPhysics = false;
                break;
              }
              newDim[k] = dimA[k];
            }
          } else {
            for (let k = 0; k < 5; k++) {
              const sum = dimA[k] + dimB[k];
              if (sum % 2 !== 0) {
                isValidPhysics = false;
                break;
              }
              newDim[k] = sum / 2;
            }
          }

          if (!isValidPhysics) continue;

          const timestamp = Date.now();
          const randSuffix = Math.floor(Math.random() * 1000);
          const newId = `node_auto_${timestamp}_${randSuffix}`;
          const relName = `rel_exp_${timestamp}_${randSuffix}`;

          let newGuess, formulaDesc;

          if (scaleA === "lin") {
            newGuess = (nodeASpec.guess + nodeBSpec.guess) / 2;
            formulaDesc = `(${nodeAName} + ${nodeBName}) / 2`;
          } else {
            newGuess = Math.sqrt(Math.abs(nodeASpec.guess * nodeBSpec.guess));
            formulaDesc = `√(${nodeAName} × ${nodeBName})`;
          }

          newNodes[newId] = {
            guess: newGuess,
            scale: scaleA,
            dim: newDim,
            parentA: nodeAName,
            parentB: nodeBName,
            formula: formulaDesc,
          };

          const relData = {
            name: relName,
            parents: [nodeAName, nodeBName],
            formula: formulaDesc,
            sigma: 1.0,
          };

          if (scaleA === "lin") {
            relData.type = "sum";
            relData.terms = {
              [nodeAName]: 0.5,
              [nodeBName]: 0.5,
              [newId]: -1.0,
            };
            relData.K = 0.0;
          } else {
            relData.kind = "claim";
            relData.terms = {
              [nodeAName]: 0.5,
              [nodeBName]: 0.5,
              [newId]: -1.0,
            };
            relData.rhs = 0.0;
          }

          newRelations.push(relData);

          if (typeof logExpansionEntry === "function") {
            logExpansionEntry(newId, newNodes[newId], relData);
          }

          addedCount++;
          break;
        }
      }
    }
  }

  return { updatedNodes: newNodes, updatedRelations: newRelations };
}

function stopAutoExpansion() {
  isAutoExpanding = false;
  const btnAutoPlay = document.getElementById("btn-auto-play");
  if (btnAutoPlay) {
    btnAutoPlay.textContent = "▶ Auto-Expand & Log";
    btnAutoPlay.className = "btn btn-primary";
  }

  if (autoExpandIntervalId) {
    clearInterval(autoExpandIntervalId);
    autoExpandIntervalId = null;
  }

  nodesVisible = true;
  relationsVisible = true;
  if (typeof scene !== "undefined") scene.visible = true;
  if (typeof buildSceneGraph === "function") buildSceneGraph();
  if (typeof solveActiveNetwork === "function") solveActiveNetwork();
}

function triggerNodeInsertion() {
  const curNet = state.getActive();
  const allRels = [...DEFAULT_RELATIONS, ...(curNet.customRelations || [])];

  const result = autoExpandNetwork(curNet.nodes, allRels);

  if (
    Object.keys(result.updatedNodes).length === Object.keys(curNet.nodes).length
  )
    return;

  const oldNodeKeys = Object.keys(curNet.nodes);
  curNet.nodes = result.updatedNodes;
  curNet.customRelations = result.updatedRelations.filter(
    (r) =>
      r.name.startsWith("rel_exp_") ||
      curNet.customRelations.some((cr) => cr.name === r.name),
  );
  state.save();

  const newNodeKeys = Object.keys(curNet.nodes);
  const addedKeys = newNodeKeys.filter((k) => !oldNodeKeys.includes(k));
  const nodeGeometry = new THREE.SphereGeometry(3.2, 16, 16);

  addedKeys.forEach((name, idx) => {
    const spec = curNet.nodes[name];
    const color = 0xa855f7;

    const material = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.25,
      metalness: 0.3,
      emissive: color,
      emissiveIntensity: 0.25,
    });

    const mesh = new THREE.Mesh(nodeGeometry, material);

    const parentMesh = nodeMeshes.values().next().value;
    const basePos = parentMesh
      ? parentMesh.position
      : new THREE.Vector3(0, 0, 0);
    mesh.position.set(
      basePos.x + (Math.random() - 0.5) * 100,
      basePos.y + (Math.random() - 0.5) * 100,
      basePos.z + (Math.random() - 0.5) * 100,
    );

    mesh.userData = { name, spec, isDisabled: false };
    scene.add(mesh);
    nodeMeshes.set(name, mesh);

    curNet.customRelations.forEach((rel) => {
      if (rel.name.startsWith("rel_exp_") && rel.terms && rel.terms[name]) {
        const partners = Object.keys(rel.terms).filter((p) => p !== name);
        partners.forEach((partnerName) => {
          const mPartner = nodeMeshes.get(partnerName);
          if (mPartner) {
            const geom = new THREE.BufferGeometry().setFromPoints([
              mesh.position,
              mPartner.position,
            ]);
            const mat = new THREE.LineBasicMaterial({
              color: 0x10b981,
              transparent: true,
              opacity: 0.55,
            });
            const line = new THREE.Line(geom, mat);
            line.userData = {
              relName: rel.name,
              nodeA: name,
              nodeB: partnerName,
            };
            scene.add(line);
            linkLines.push(line);
          }
        });
      }
    });
  });
}

function toggleToolsPanel(forceState) {
  toolsPanelOpen =
    typeof forceState === "boolean" ? forceState : !toolsPanelOpen;
  const panel = document.getElementById("tools-panel");
  const btnToggle = document.getElementById("btn-tools-toggle");

  if (panel) {
    panel.classList.toggle("open", toolsPanelOpen);
  }
  if (btnToggle) {
    btnToggle.classList.toggle("btn-primary", !toolsPanelOpen);
    btnToggle.classList.toggle("btn-warning", toolsPanelOpen);
  }
}

btnAddNode.addEventListener("click", () => {
  triggerNodeInsertion();
});

btnAutoPlay.addEventListener("click", () => {
  isAutoExpanding = !isAutoExpanding;

  if (isAutoExpanding) {
    btnAutoPlay.textContent = "⏹ Stop Auto-Log";
    btnAutoPlay.className = "btn btn-danger";

    const selectedValue = selectInterval.value;
    const isSilentMode = selectedValue === "silent";
    const intervalTime = isSilentMode ? 20 : parseInt(selectedValue) || 200;

    if (isSilentMode) {
      nodesVisible = false;
      relationsVisible = false;
      scene.visible = false;
    }

    autoExpandIntervalId = setInterval(() => {
      const curNet = state.getActive();

      const { updatedNodes, updatedRelations } = autoExpandNetwork(
        curNet.nodes,
        [...DEFAULT_RELATIONS, ...(curNet.customRelations || [])],
      );

      curNet.nodes = updatedNodes;

      const defaultNames = new Set(DEFAULT_RELATIONS.map((r) => r.name));
      curNet.customRelations = updatedRelations.filter(
        (r) => !defaultNames.has(r.name),
      );

      state.save();
      solveActiveNetwork();
    }, intervalTime);
  } else {
    stopAutoExpansion();
  }
});

selectInterval.addEventListener("change", () => {
  if (isAutoExpanding) {
    clearInterval(autoExpandIntervalId);
    const intervalMs = parseInt(selectInterval.value, 10) || 500;
    autoExpandIntervalId = setInterval(triggerNodeInsertion, intervalMs);
  }
});

document.getElementById("btn-tools-toggle")?.addEventListener("click", () => {
  toggleToolsPanel();
});

document.getElementById("btn-close-tools")?.addEventListener("click", () => {
  toggleToolsPanel(false);
});

document.getElementById("btn-add-net").onclick = () => {
  const name = prompt("Nom du nouveau scénario de test :");
  if (name) {
    state.createNetwork(name);
    refreshNetworkSelect();
    buildSceneGraph();
    solveActiveNetwork();
  }
};

document.getElementById("btn-reset").onclick = () => {
  if (confirm("Reset all scenarios and restore the standard GRM model?")) {
    state.resetAll();
    refreshNetworkSelect();
    buildSceneGraph();
    solveActiveNetwork();
    resetLogContainer();
  }
};

document.getElementById("bubble-close").onclick = () => {
  document.getElementById("info-bubble").classList.add("hidden");
  selectedNodeName = null;
  applyFullNetworkColors();
};

document.getElementById("btn-toggle-active").onclick = () => {
  if (selectedNodeName) toggleNodeActive(selectedNodeName);
};

document
  .getElementById("btn-mine-bridges")
  ?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-mine-bridges");
    const origText = btn.textContent;
    btn.textContent = "⚡ GPU Mining All Invariants...";
    btn.disabled = true;

    const curNet = state.getActive();
    const allExistingRels = [
      ...DEFAULT_RELATIONS,
      ...(curNet.customRelations || []),
    ];

    const knownSignatures = new Set(
      allExistingRels.map((r) => {
        const keys = r.terms ? Object.keys(r.terms) : r.nodes || [];
        return [...keys].sort().join("|");
      }),
    );

    const nodeNames = Object.keys(curNet.nodes);
    const t0 = performance.now();

    const discoveredBridges = await bridgeMiner.mineBridges(
      nodeNames,
      curNet.nodes,
      lastSolvedResult?.values,
      {
        maxHits: 256,
      },
    );

    const elapsed = (performance.now() - t0).toFixed(1);
    btn.textContent = origText;
    btn.disabled = false;

    const novelInvariants = discoveredBridges.filter((b) => {
      const sig = [...b.nodes].sort().join("|");
      return !knownSignatures.has(sig);
    });

    if (novelInvariants.length === 0) {
      alert(
        `WebGPU Search Completed in ${elapsed} ms.\n\n` +
          `Tested Combinations: ~${Math.round(nodeNames.length ** 3 / 6).toLocaleString()}\n` +
          `Result: All invariant relations for current nodes are already connected.`,
      );
      return;
    }

    currentMinedInvariants = novelInvariants;

    const modal = document.getElementById("invariants-modal");
    const subtitle = document.getElementById("invariants-modal-subtitle");
    const countBadge = document.getElementById("invariants-count-badge");
    const listContainer = document.getElementById("invariants-list");

    subtitle.textContent = `Mined in ${elapsed} ms across ${Math.round(nodeNames.length ** 3 / 6).toLocaleString()} triplet combinations`;
    countBadge.textContent = `${novelInvariants.length} Novel Invariant(s)`;

    listContainer.innerHTML = novelInvariants
      .map(
        (inv, idx) => `
      <div class="invariant-card-item">
        <div class="invariant-info-left">
          <div class="invariant-formula-display">#${idx + 1} : ${inv.formula}</div>
          <div class="invariant-meta-text">Identifier: ${inv.name} | Target: 10^(${inv.rhs.toFixed(4)})</div>
        </div>
        <div class="invariant-badges-right">
          <span class="accuracy-badge">${inv.accuracyPercent}%</span>
          <span class="residual-badge">&sigma; = ${inv.residualDex.toFixed(6)} dex</span>
        </div>
      </div>
    `,
      )
      .join("");

    modal.classList.remove("hidden");
  });

document
  .getElementById("invariants-modal-close")
  ?.addEventListener("click", () => {
    document.getElementById("invariants-modal")?.classList.add("hidden");
  });

document
  .getElementById("btn-copy-all-invariants")
  ?.addEventListener("click", () => {
    if (currentMinedInvariants.length === 0) return;

    const curNet = state.getActive();

    const latexSymbolMap = {
      alpha: "\\alpha",
      re: "r_e",
      a0_bohr: "a_{0,\\text{bohr}}",
      Odark: "\\Omega_{\\text{dark}}",
      Ry: "R_y",
      aS: "\\alpha_S",
      Sigma: "\\Sigma",
      fpi: "f_\\pi",
      rF: "r_F",
      cosW: "\\cos W",
      teq: "t_{\\text{eq}}",
      tturn: "t_{\\text{turn}}",
    };

    function formatLatexFormula(formulaStr) {
      let res = formulaStr;
      const sortedKeys = Object.keys(latexSymbolMap).sort(
        (a, b) => b.length - a.length,
      );
      for (const key of sortedKeys) {
        const val = latexSymbolMap[key];
        res = res.replace(new RegExp("\\b" + key + "\\b", "g"), val);
      }
      res = res.replace(
        /\^(\(([^)]+)\)|([a-zA-Z0-9_-]+))/g,
        (match, fullGroup, innerParens, singleToken) => {
          const cleanContent = innerParens || singleToken;
          return `^{${cleanContent}}`;
        },
      );
      res = res.replace(/\s*\*\s*/g, " \\times ");
      res = res.replace(
        new RegExp("\\b([0-9]+)\\s*/\\s*([0-9]+)\\b", "g"),
        "\\\\frac{$1}{$2}",
      );

      return res;
    }

    const proofsPayload = currentMinedInvariants
      .map((inv, idx) => {
        const p = inv.proofTrace;
        const rank = idx + 1;

        const cleanFormula = formatLatexFormula(inv.formula);

        return [
          `### Identity #${rank}`,
          `  `,
          `#### $$` + cleanFormula + `$$`,
          `  `,
          `- **Target Identifier**: \`${inv.name}\`  `,
          `- **Target Log Value**: $10^{(${inv.rhs.toFixed(4)})}$  `,
          `- **Accuracy Level**: **${inv.accuracyPercent}%**`,
          `- **Residual ($\\sigma$)**: \`${inv.residualDex.toFixed(6)} dex\`  `,
          `  `,
          `#### 1. Dimensional Homogeneity Proof ($\mathbb{Z}^5$ SI Base Units)  `,
          `> Net Sum Vector: \`[${p.netDimensions.join(", ")}]\` → **[Mass, Length, Time, Current, Θ] = 0 (ADIMENSIONAL)**  `,
          `  `,
          `#### 2. Participating Nodes & Logarithmic Values  `,
          Object.entries(inv.terms)
            .map(([nodeName, weight]) => {
              const spec = curNet.nodes[nodeName] || {};
              const val =
                lastSolvedResult?.values?.[nodeName] ?? spec.guess ?? 1.0;
              const logVal =
                spec.scale === "lin"
                  ? 0.0
                  : Math.log10(Math.max(Math.abs(val), 1e-120));
              const prettyName = latexSymbolMap[nodeName]
                ? `$${latexSymbolMap[nodeName]}$`
                : `\`${nodeName}\``;
              return `* **${prettyName}** (Weight: \`${weight}\`, Log10: \`${logVal.toFixed(6)}\`)  `;
            })
            .join("\n"),
          `  `,
          `- **Combo Log Sum**: \`${p.comboLog.toFixed(6)}\``,
          `- **Target Log**: \`${p.targetLog.toFixed(6)}\``,
          `- **Absolute Difference**: \`${Math.abs(p.comboLog - p.targetLog).toExponential(2)} dex\``,
          `  `,
          `#### 3. Combinatorial Integrity`,
          `- **Weights**: Integer canonical coefficients only (Zero Free Parameters)`,
          `  `,
          `---`,
          `  `,
        ]
          .filter(Boolean)
          .join("\n");
      })
      .join("\n");

    const markdownPayload = [
      `# GRM Hard-Math Proof Log — Automatic GPU Miner  `,
      `> **Certified Invariant Relations (Zero-Fit Architecture)**  `,
      `  `,
      `- **Total Certified Identities**: ${currentMinedInvariants.length}  `,
      `- **Execution Timestamp**: ${new Date().toLocaleString()}  `,
      `- **Verification Engine**: WebGPU Compute Parallel Pipeline`,
      `  `,
      `---`,
      `  `,
      proofsPayload,
      `  `,
      `*End of Certified Markdown Proof Payload*`,
    ].join("\n");

    navigator.clipboard.writeText(markdownPayload).then(() => {
      const btnCopy = document.getElementById("btn-copy-all-invariants");
      const orig = btnCopy.textContent;
      btnCopy.textContent = "✓ LaTeX Identities Copied!";
      setTimeout(() => {
        btnCopy.textContent = orig;
      }, 1800);
    });
  });

document
  .getElementById("btn-inject-all-invariants")
  ?.addEventListener("click", () => {
    if (currentMinedInvariants.length === 0) return;

    const curNet = state.getActive();
    curNet.customRelations = curNet.customRelations || [];

    let countInjected = 0;
    currentMinedInvariants.forEach((inv) => {
      if (!curNet.customRelations.some((r) => r.name === inv.name)) {
        curNet.customRelations.push({
          name: inv.name,
          terms: inv.terms,
          rhs: inv.rhs,
          sigma: inv.sigma,
          formula: inv.formula,
          kind: "log",
        });
        countInjected++;
      }
    });

    state.save();
    buildSceneGraph();
    solveActiveNetwork();

    const logContent = document.getElementById("expansion-log-content");
    if (logContent) {
      const entry = document.createElement("div");
      entry.className = "log-item";
      entry.style.borderLeft = "3px solid #f59e0b";
      entry.innerHTML = `
      <div style="color: #fbbf24; font-weight: bold;">⚡ MASS INJECTION COMPLETED</div>
      <div>${countInjected} novel physical invariants mapped to 3D manifold</div>
    `;
      logContent.prepend(entry);
    }

    document.getElementById("invariants-modal")?.classList.add("hidden");
    alert(
      `Successfully injected ${countInjected} novel physical laws into the relational manifold!`,
    );
  });

menuToggleBtn?.addEventListener("click", (e) => {
  e.stopPropagation();
  dropdownMenu.classList.toggle("hidden");
});

document.addEventListener("click", () => {
  if (dropdownMenu && !dropdownMenu.classList.contains("hidden")) {
    dropdownMenu.classList.add("hidden");
  }
});

dropdownMenu?.addEventListener("click", (e) => {
  e.stopPropagation();
});

document.getElementById("btn-close-diag")?.addEventListener("click", () => {
  toggleDiagnosticPanel(false);
});

document.getElementById("btn-floating-diag")?.addEventListener("click", () => {
  toggleDiagnosticPanel(true);
});

document.getElementById("btn-toggle-diag")?.addEventListener("click", () => {
  toggleDiagnosticPanel();
});

document.getElementById("btn-blue-thread")?.addEventListener("click", () => {
  toggleBlueThread();
});

document.getElementById("btn-red-thread")?.addEventListener("click", () => {
  toggleRedThread();
});

document.getElementById("guide-modal-close")?.addEventListener("click", () => {
  markGuideAsSeen();
});

document.getElementById("btn-guide-close")?.addEventListener("click", () => {
  markGuideAsSeen();
});

document
  .getElementById("btn-toggle-nodes")
  ?.addEventListener("click", toggleNodesVisibility);
document
  .getElementById("btn-toggle-rels")
  ?.addEventListener("click", toggleRelationsVisibility);

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    markGuideAsSeen();
  }
});

document.getElementById("cm-solve").onclick = () => solveActiveNetwork();
document.getElementById("cm-center").onclick = () => {
  controls.target.set(0, 0, 0);
  camera.position.set(0, 180, 500);
};

document.getElementById("cm-add-node").onclick = () => {
  hideContextMenu();
  nodeModal.classList.remove("hidden");
};

document.getElementById("btn-add-relation").onclick = () => {
  relModal.classList.remove("hidden");
};

document.getElementById("cm-add-relation").onclick = () => {
  hideContextMenu();
  relModal.classList.remove("hidden");
};

document.querySelectorAll(".modal-cancel-btn").forEach((btn) => {
  btn.onclick = () => {
    nodeModal.classList.add("hidden");
    relModal.classList.add("hidden");
  };
});

document.getElementById("modal-close").onclick = () =>
  nodeModal.classList.add("hidden");
document.getElementById("rel-modal-close").onclick = () =>
  relModal.classList.add("hidden");

document.getElementById("node-measured").onchange = (e) => {
  document
    .getElementById("measured-fields")
    .classList.toggle("hidden", !e.target.checked);
};

const guideModal = document.getElementById("guide-modal");
document.getElementById("btn-guide")?.addEventListener("click", () => {
  guideModal.classList.remove("hidden");
});
document.getElementById("guide-modal-close")?.addEventListener("click", () => {
  guideModal.classList.add("hidden");
});
document.getElementById("btn-guide-close")?.addEventListener("click", () => {
  guideModal.classList.add("hidden");
});
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") guideModal.classList.add("hidden");
});

document.addEventListener("click", () => hideContextMenu());

document.getElementById("btn-export-json")?.addEventListener("click", () => {
  state.exportJson();
});

netSelect.onchange = (e) => {
  state.data.activeId = e.target.value;
  state.save();
  buildSceneGraph();
  solveActiveNetwork();
};

document.getElementById("add-node-form").onsubmit = (e) => {
  e.preventDefault();
  const id = document.getElementById("node-id").value.trim();
  const desc = document.getElementById("node-desc").value.trim();
  const scale = document.getElementById("node-scale").value;
  const guess = parseFloat(document.getElementById("node-guess").value);
  const isMeas = document.getElementById("node-measured").checked;

  if (!id) return;

  const curNet = state.getActive();
  curNet.nodes[id] = { guess, scale };
  if (desc) NODE_DESCRIPTIONS[id] = desc;

  if (isMeas) {
    const val =
      parseFloat(document.getElementById("node-meas-val").value) || guess;
    const sig =
      parseFloat(document.getElementById("node-meas-sigma").value) || 0.01;
    curNet.measured[id] = [val, sig];
  }

  state.save();
  nodeModal.classList.add("hidden");
  e.target.reset();
  buildSceneGraph();
  solveActiveNetwork();
  showNodeBubble(id);
};

document.getElementById("add-relation-form").onsubmit = (e) => {
  e.preventDefault();
  const name = document.getElementById("rel-name").value.trim();
  const termsRaw = document.getElementById("rel-terms").value.trim();
  const rhs = parseFloat(document.getElementById("rel-rhs").value) || 0.0;
  const sigma = parseFloat(document.getElementById("rel-sigma").value) || 0.01;

  if (!name || !termsRaw) return;

  const terms = {};
  termsRaw.split(",").forEach((part) => {
    const [k, v] = part.split(":").map((s) => s.trim());
    if (k && !isNaN(parseFloat(v))) {
      terms[k] = parseFloat(v);
    }
  });

  const curNet = state.getActive();
  curNet.customRelations = curNet.customRelations || [];
  curNet.customRelations.push({ name, terms, rhs, sigma, kind: "claim" });

  state.save();
  relModal.classList.add("hidden");
  e.target.reset();
  buildSceneGraph();
  solveActiveNetwork();
};

window.addEventListener("DOMContentLoaded", () => {
  toggleDiagnosticPanel(window.innerWidth > 768);
  toggleToolsPanel(window.innerWidth > 900);
  bridgeMiner.init();
  refreshNetworkSelect();
  init3D();
  buildSceneGraph();
  sequencer.init(nodeMeshes, linkLines);
  solveActiveNetwork();
  animate();
  checkFirstVisitGuide();
});
