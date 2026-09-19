const STORAGE_KEY = "RELEX_MEMORY_SHARED_STATE";

const INITIAL_DATA = {
  currentRole: "basic_with_rights",
  assignedProjects: ["PRJ-001"],
  projects: [
    {
      id: "PRJ-001",
      code: "ACME-FRESH-2025",
      name: "Fresh Food Forecasting & Replenishment (Phase 2)",
      org: "Acme Org GmbH",
      desc: "Produce, dairy, and chilled replenishment roll-out to eliminate food waste.",
      metrics: {
        baselineWaste: "4.1%",
        currentWaste: "3.4%",
        targetWaste: "3.2%",
        status: "On Track"
      }
    },
    {
      id: "PRJ-002",
      code: "ACME-AMBIENT-2024",
      name: "Ambient Core Replenishment Rollout",
      org: "Acme Org GmbH",
      desc: "Dry grocery and shelf forecasting implemented across 120 stores.",
      metrics: {
        baselineWaste: "1.2%",
        currentWaste: "0.8%",
        targetWaste: "0.8%",
        status: "Completed"
      }
    }
  ],
  documents: [
    {
      id: "doc_01",
      fileName: "01_shelf-life-field-mapping.txt",
      projectId: "PRJ-001",
      projectName: "Fresh Food Forecasting & Replenishment (Phase 2)",
      fileType: "Email Thread",
      aiStatus: "ACTIVE",
      content: [
        "*** SYNTHETIC DATA. Generated for RELEX Challenge 2026.",
        "Subject: Shelf life field mapping - fresh export",
        "From: Nadia Haddad <n.haddad@relexsolutions.example>",
        "Date: Thursday, October 30, 2025 12:02 PM",
        "To: Ana Duarte <ana.duarte@relexsolutions.example>",
        "",
        "We proceeded. Nobody objected.",
        "",
        "--------------------------------------------------",
        "From: Ana Duarte <ana.duarte@relexsolutions.example>",
        "Sent: Thursday, October 30, 2025 11:45 AM",
        "Subject: Re: Shelf life field mapping - fresh export",
        "",
        "Was the approximation approach ever confirmed by Acme, or did we just proceed?",
        "I am writing up the config decisions and I cannot find an agreement anywhere.",
        "",
        "--------------------------------------------------",
        "From: Priya Nair <priya.nair@acme-org.example>",
        "Sent: Thursday, September 11, 2025 17:22",
        "Subject: Re: Shelf life field mapping - fresh export",
        "",
        "It is not impossible, it is unowned, which in practice is the same thing this year.",
        "Proceed with your approximation.",
        "",
        "Priya Nair",
        "IT Integration Lead | Acme Org GmbH",
        "",
        "--------------------------------------------------",
        "From: Nadia Haddad <n.haddad@relexsolutions.example>",
        "Sent: Thursday, September 4, 2025 14:20",
        "Subject: Re: Shelf life field mapping - fresh export",
        "",
        "Since remaining shelf life is not available, I propose we proceed with an approximation:",
        "total shelf life from MHDHB minus average days-in-warehouse per article group, which we",
        "can derive from stock turn.",
        "It is not exact. For fast movers it will be close. For slow movers it will be wrong in",
        "the direction of assuming the stock is fresher than it is.",
        "If nobody objects I will build it that way so we are not blocked."
      ]
    },
    {
      id: "doc_02",
      fileName: "01_weekly-status-thread.txt",
      projectId: "PRJ-001",
      projectName: "Fresh Food Forecasting & Replenishment (Phase 2)",
      fileType: "Weekly Status",
      aiStatus: "ACTIVE",
      content: [
        "Subject: Weekly Acme update",
        "From: Ana Duarte <ana.duarte@relexsolutions.example>",
        "Date: Monday, November 24, 2025 16:20 (Week 48)",
        "",
        "Update 24-11-2025 (Week 48) - On Track",
        "Note that the plan has been reissued on a two delivery basis.",
        "Earlier plan documents showing three waves for fresh are superseded and should not be used.",
        "",
        "Topics worked on last week:",
        "1. Go/no-go held. Produce, dairy and chilled approved. Bakery descoped.",
        "2. OP_ID field exclusion agreed and confirmed in writing."
      ]
    },
    {
      id: "doc_03",
      fileName: "00_ambient-master-spec.txt",
      projectId: "PRJ-002",
      projectName: "Ambient Core Replenishment Rollout",
      fileType: "Specification",
      aiStatus: "ACTIVE",
      content: [
        "Ambient Master Specification - Document Version 1.4",
        "Phase 1 dry grocery inventory parameters confirmed for central distribution."
      ]
    }
  ],
  users: [
    {
      id: "usr_001",
      name: "Alex Vance",
      email: "alex.vance@acme-org.example",
      org: "Acme Org GmbH",
      rights: ["PRJ-001"]
    },
    {
      id: "usr_002",
      name: "Clara Oswald",
      email: "clara.o@meridian.example",
      org: "Meridian Consulting",
      rights: []
    },
    {
      id: "usr_003",
      name: "Tomas Lindholm",
      email: "tomas.l@relexsolutions.example",
      org: "RELEX Solutions",
      rights: ["PRJ-001", "PRJ-002"]
    }
  ]
};

function getStorage() {
  const item = localStorage.getItem(STORAGE_KEY);
  if (!item) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(INITIAL_DATA));
    return INITIAL_DATA;
  }
  return JSON.parse(item);
}

function setStorage(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

const Shared = {
  getRole() {
    return getStorage().currentRole;
  },

  isAdmin() {
    return this.getRole() === "admin";
  },

  setRole(role) {
    const data = getStorage();
    data.currentRole = role;
    if (role === "basic_user") {
      data.assignedProjects = [];
    } else if (role === "basic_with_rights") {
      data.assignedProjects = ["PRJ-001"];
    } else if (role === "admin") {
      data.assignedProjects = ["PRJ-001", "PRJ-002"];
    }
    setStorage(data);
  },

  hasProjectRight(projectId) {
    if (this.isAdmin()) return true;
    return getStorage().assignedProjects.includes(projectId);
  },

  getAuthorizedProjects() {
    const data = getStorage();
    if (this.isAdmin()) return data.projects;
    return data.projects.filter(p => data.assignedProjects.includes(p.id));
  },

  getAuthorizedDocuments() {
    const data = getStorage();
    if (this.isAdmin()) return data.documents;
    return data.documents.filter(d => data.assignedProjects.includes(d.projectId));
  },

  getAllDocuments() {
    return getStorage().documents;
  },

  getDocument(docId) {
    const data = getStorage();
    const doc = data.documents.find(d => d.id === docId);
    if (!doc) throw new Error("NOT_FOUND");
    if (!this.hasProjectRight(doc.projectId)) throw new Error("ACCESS_DENIED");
    return doc;
  },

  toggleDocAI(docId) {
    const data = getStorage();
    const doc = data.documents.find(d => d.id === docId);
    if (doc) {
      doc.aiStatus = doc.aiStatus === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    }
    setStorage(data);
  },

  deleteDoc(docId) {
    const data = getStorage();
    data.documents = data.documents.filter(d => d.id !== docId);
    setStorage(data);
  },

  getUsers() {
    return getStorage().users;
  },

  grantRight(userId, projectId) {
    const data = getStorage();
    const user = data.users.find(u => u.id === userId);
    if (user && !user.rights.includes(projectId)) {
      user.rights.push(projectId);
    }
    setStorage(data);
  },

  revokeRight(userId, projectId) {
    const data = getStorage();
    const user = data.users.find(u => u.id === userId);
    if (user) {
      user.rights = user.rights.filter(id => id !== projectId);
    }
    setStorage(data);
  },

  deleteUser(userId) {
    const data = getStorage();
    data.users = data.users.filter(u => u.id !== userId);
    setStorage(data);
  },

  mountHeader(activeNav) {
    const role = this.getRole();
    const header = document.getElementById("app-header");
    if (!header) return;

    header.innerHTML = `
      <div class="flex items-center gap-6">
        <a href="projects.html" class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center font-bold text-slate-950 text-base shadow-sm">R</div>
          <span class="font-semibold text-sm text-white">RELEX Memory</span>
        </a>
        <nav class="hidden md:flex items-center gap-1 border-l border-slate-800 pl-6 text-xs font-medium text-slate-400">
          <a href="chat.html" class="px-3 py-2 hover:text-white transition flex items-center gap-1.5 ${activeNav === 'chat' ? 'text-white border-b-2 border-emerald-500 font-semibold' : ''}">
            <i data-lucide="message-square" class="w-3.5 h-3.5"></i>
            <span>AI Chat</span>
          </a>
          <a href="documents.html" class="px-3 py-2 hover:text-white transition flex items-center gap-1.5 ${activeNav === 'documents' ? 'text-white border-b-2 border-emerald-500 font-semibold' : ''}">
            <i data-lucide="folder" class="w-3.5 h-3.5"></i>
            <span>Document Library</span>
          </a>
          <a href="projects.html" class="px-3 py-2 hover:text-white transition flex items-center gap-1.5 ${activeNav === 'projects' ? 'text-white border-b-2 border-emerald-500 font-semibold' : ''}">
            <i data-lucide="layout-grid" class="w-3.5 h-3.5"></i>
            <span>Projects</span>
          </a>
          ${this.isAdmin() ? `
            <a href="admin.html" class="px-3 py-2 hover:text-white transition flex items-center gap-1.5 text-indigo-400 ${activeNav === 'admin' ? 'text-white border-b-2 border-indigo-500 font-semibold' : ''}">
              <i data-lucide="settings" class="w-3.5 h-3.5"></i>
              <span>Administration</span>
            </a>
          ` : ''}
        </nav>
      </div>
      <div class="flex items-center gap-3">
        <label class="hidden sm:flex items-center gap-2 text-xs text-slate-400 font-mono">Role:</label>
        <select id="globalRoleSelect" onchange="Shared.handleRoleChange(this.value)" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 font-mono">
          <option value="basic_user" ${role === 'basic_user' ? 'selected' : ''}>Basic User (No Rights)</option>
          <option value="basic_with_rights" ${role === 'basic_with_rights' ? 'selected' : ''}>Basic User (Acme Fresh Rights)</option>
          <option value="admin" ${role === 'admin' ? 'selected' : ''}>Administrator</option>
        </select>
      </div>
    `;
    lucide.createIcons();
  },

  handleRoleChange(newRole) {
    this.setRole(newRole);
    window.location.reload();
  }
};