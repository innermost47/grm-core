import { DEFAULT_MEASURED } from "./measured.js";
import { DEFAULT_NODES } from "./nodes.js";
import { DEFAULT_RELATIONS } from "./relations.js";

const STORAGE_KEY = "GRM_EXPLORER_STORE_V2";

export class StateManager {
  constructor() {
    this.data = this.load();
    if (!this.data.networks || !this.data.networks.length) {
      this.initDefault();
    }
  }

  initDefault() {
    this.data = {
      activeId: "default",
      networks: [
        {
          id: "default",
          name: "Unified Global Network (Cosmos + Atoms + Planets)",
          nodes: JSON.parse(JSON.stringify(DEFAULT_NODES)),
          relations: JSON.parse(JSON.stringify(DEFAULT_RELATIONS)),
          customRelations: [],
          measured: JSON.parse(JSON.stringify(DEFAULT_MEASURED)),
          disabledNodes: [],
        },
      ],
    };
    this.save();
  }

  load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  }

  save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data));
  }

  getActive() {
    return (
      this.data.networks.find((n) => n.id === this.data.activeId) ||
      this.data.networks[0]
    );
  }

  exportJson(solvedValues = null) {
    const activeNet = this.getActive();
    const disabledNodes = new Set(activeNet.disabledNodes || []);

    if (solvedValues) {
      for (const [nodeName, val] of Object.entries(solvedValues)) {
        if (activeNet.nodes[nodeName] && !disabledNodes.has(nodeName)) {
          activeNet.nodes[nodeName].solved = val;
        }
      }
    }

    const activeMeasurements = {};
    for (const [name, meas] of Object.entries(activeNet.measured || {})) {
      if (!disabledNodes.has(name)) {
        activeMeasurements[name] = meas;
      }
    }
    activeNet.measured = activeMeasurements;

    const storeExport = {
      activeId: this.data["activeId"] || "default",
      networks: [activeNet],
    };

    const rawData = JSON.stringify(storeExport, null, 2);
    const fileBlob = new Blob([rawData], { type: "application/json" });
    const downloadUrl = URL.createObjectURL(fileBlob);
    const exportAnchor = document.createElement("a");

    exportAnchor.href = downloadUrl;
    exportAnchor.download = `grm_network_store_${Date.now()}.json`;
    document.body.appendChild(exportAnchor);
    exportAnchor.click();
    document.body.removeChild(exportAnchor);
    URL.revokeObjectURL(downloadUrl);
  }

  createNetwork(name) {
    const id = "net_" + Date.now();
    const current = this.getActive();
    this.data.networks.push({
      id,
      name: name || `Scenario ${this.data.networks.length + 1}`,
      nodes: JSON.parse(JSON.stringify(current.nodes)),
      customRelations: JSON.parse(
        JSON.stringify(current.customRelations || []),
      ),
      measured: JSON.parse(JSON.stringify(current.measured)),
      disabledNodes: [...(current.disabledNodes || [])],
    });
    this.data.activeId = id;
    this.save();
    return id;
  }

  resetAll() {
    localStorage.removeItem(STORAGE_KEY);
    this.initDefault();
  }
}
