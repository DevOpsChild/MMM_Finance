Module.register("MMM-Finanzen", {
  defaults: {
    apiUrl: "http://localhost:8081/api/finanzen",
    updateInterval: 60 * 1000,
    animationSpeed: 1000,
    maxEinkaeufe: 5,
  },

  start() {
    this.finanzData = null;
    this.scheduleUpdate();
    this.updateData();
  },

  scheduleUpdate() {
    setInterval(() => this.updateData(), this.config.updateInterval);
  },

  updateData() {
    fetch(this.config.apiUrl)
      .then((res) => res.json())
      .then((data) => {
        this.finanzData = data;
        this.updateDom(this.config.animationSpeed);
      })
      .catch((err) => console.error("[MMM-Finanzen] Fetch error:", err));
  },

  getDom() {
    const wrapper = document.createElement("div");
    wrapper.className = "mmm-finanzen";

    if (!this.finanzData) {
      wrapper.innerHTML = '<div class="loading">Lade Finanzdaten...</div>';
      return wrapper;
    }

    wrapper.classList.add("budget-mode");
    const { budget, einkaeufe, vermoegen } = this.finanzData;

    // --- Wochenbudget ---
    const budgetSection = document.createElement("div");
    budgetSection.className = "section";

    const budgetTitle = document.createElement("div");
    budgetTitle.className = "section-title";
    budgetTitle.innerText = "💰 WOCHENBUDGET";
    budgetSection.appendChild(budgetTitle);

    const budgetBetraege = document.createElement("div");
    budgetBetraege.className = "budget-betraege";
    budgetBetraege.innerHTML =
      `<span class="verbleibend ${budget.verbleibend < 20 ? "kritisch" : ""}">${this._formatEur(budget.verbleibend)}</span>` +
      `<span class="von-gesamt"> / ${this._formatEur(budget.gesamt)}</span>`;
    budgetSection.appendChild(budgetBetraege);

    // Fortschrittsbalken
    const barWrap = document.createElement("div");
    barWrap.className = "progress-wrap";
    const bar = document.createElement("div");
    bar.className = "progress-bar";
    const pct = Math.min(budget.prozent_verbraucht, 100);
    bar.style.width = pct + "%";
    if (pct >= 85) bar.classList.add("kritisch");
    else if (pct >= 60) bar.classList.add("warnung");
    barWrap.appendChild(bar);
    budgetSection.appendChild(barWrap);

    const ausgegeben = document.createElement("div");
    ausgegeben.className = "ausgegeben";
    ausgegeben.innerText = `Ausgegeben: ${this._formatEur(budget.ausgegeben)} (${pct}%)`;
    budgetSection.appendChild(ausgegeben);

    wrapper.appendChild(budgetSection);

    // --- Letzte Einkäufe ---
    if (einkaeufe && einkaeufe.length > 0) {
      const einkaufSection = document.createElement("div");
      einkaufSection.className = "section";

      const einkaufTitle = document.createElement("div");
      einkaufTitle.className = "section-title";
      einkaufTitle.innerText = "🛒 Letzte Einkäufe";
      einkaufSection.appendChild(einkaufTitle);

      einkaeufe.slice(0, this.config.maxEinkaeufe).forEach((e) => {
        const row = document.createElement("div");
        row.className = "einkauf-row";
        row.innerHTML =
          `<span class="einkauf-notiz">${e.notiz}</span>` +
          `<span class="einkauf-kategorie">${e.kategorie}</span>` +
          `<span class="einkauf-betrag">${this._formatEur(e.betrag)}</span>`;
        einkaufSection.appendChild(row);
      });

      wrapper.appendChild(einkaufSection);
    }

    // --- Vermögen ---
    const vermSection = document.createElement("div");
    vermSection.className = "section";

    const vermTitle = document.createElement("div");
    vermTitle.className = "section-title";
    vermTitle.innerText = "📈 Vermögen";
    vermSection.appendChild(vermTitle);

    const vermRows = [
      { label: "📈 ETF", betrag: vermoegen.etf },
      { label: "🏦 Sparkonto", betrag: vermoegen.sparkonto },
      { label: "💼 Gesamt", betrag: vermoegen.gesamt, bold: true },
    ];

    vermRows.forEach(({ label, betrag, bold }) => {
      const row = document.createElement("div");
      row.className = "verm-row" + (bold ? " gesamt" : "");
      row.innerHTML =
        `<span class="verm-label">${label}</span>` +
        `<span class="verm-betrag">${this._formatEur(betrag)}</span>`;
      vermSection.appendChild(row);
    });

    wrapper.appendChild(vermSection);

    return wrapper;
  },

  _formatEur(val) {
    return new Intl.NumberFormat("de-DE", {
      style: "currency",
      currency: "EUR",
    }).format(val);
  },

  getStyles() {
    return ["MMM-Finanzen.css"];
  },
});
