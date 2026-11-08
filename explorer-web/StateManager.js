import { DEFAULT_MEASURED } from "./measured.js";
import { DEFAULT_NODES } from "./nodes.js";

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
