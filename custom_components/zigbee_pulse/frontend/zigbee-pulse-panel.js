class ZigbeePulsePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._loading = false;
    this._editing = false;
    this._filter = "";
  }

  connectedCallback() {
    this._timer = window.setInterval(() => this._load(), 30000);
    this._render();
  }

  disconnectedCallback() {
    window.clearInterval(this._timer);
  }

  set hass(value) {
    this._hass = value;
    if (!this._data) this._load();
    if (!this._editing) this._render();
  }

  set narrow(value) {
    this._narrow = value;
  }

  _escape(value) {
    return String(value ?? "").replace(/[&<>\"]/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;",
    }[char]));
  }

  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      this._data = await this._hass.callWS({ type: "zigbee_pulse/get_config" });
      this._render();
    } catch (error) {
      this._error = error.message || "Unable to load Zigbee Pulse";
      this._render();
    } finally {
      this._loading = false;
    }
  }

  _entry() {
    return this._data?.entries?.[0];
  }

  _liveState() {
    if (!this._hass) return null;
    return Object.values(this._hass.states).find((state) =>
      state.attributes && state.attributes.devices &&
      state.attributes.monitored_count !== undefined);
  }

  _status(device, live) {
    const liveDevice = live?.attributes?.devices?.[device.entity_id];
    return liveDevice?.stale ? "offline" : "healthy";
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const entry = this._entry();
    if (!entry) {
      this.shadowRoot.innerHTML = `<style>${this._styles()}</style><main><h1>Zigbee Pulse</h1><p>No Zigbee Pulse monitor is configured.</p><a class="button" href="/config/integrations">Add the integration</a></main>`;
      return;
    }
    const settings = entry.settings;
    const live = this._liveState();
    const staleCount = live?.state ?? entry.devices.filter((d) => this._status(d, live) === "offline").length;
    const ready = live?.attributes?.notifications_ready ? "Ready" : "Starting baseline";
    const filter = this._filter.toLowerCase();
    const devices = entry.devices.filter((device) =>
      !filter || `${device.name} ${device.entity_id}`.toLowerCase().includes(filter));
    const recipientOptions = (this._data.recipients || []).map((recipient) =>
      `<option value="${this._escape(recipient.entity_id)}">${this._escape(recipient.name || recipient.entity_id)}</option>`).join("");
    const deviceCards = devices.map((device) => this._deviceCard(device, settings, live, recipientOptions)).join("");
    this.shadowRoot.innerHTML = `<style>${this._styles()}</style>
      <main>
        <header><div class="brand"><img class="brand-icon" src="/zigbee_pulse_panel/zigbee-pulse-icon.png" alt=""><div><h1>Zigbee Pulse</h1><p>Live Zigbee2MQTT health and Telegram notification controls</p></div></div><button id="refresh">Refresh</button></header>
        <section class="summary">
          <div><strong>${this._escape(staleCount)}</strong><span>stale devices</span></div>
          <div><strong>${entry.devices.length}</strong><span>monitored devices</span></div>
          <div><strong>${this._escape(ready)}</strong><span>notification status</span></div>
          <button id="test">Send test notification</button>
        </section>
        <section class="card"><h2>Global settings</h2>
          <form id="global-form">
            <label>Monitor name<input name="name" value="${this._escape(settings.name)}"></label>
            <label>Default Telegram chat<select name="recipient">${recipientOptions}</select></label>
            <label>Other device timeout (minutes)<input type="number" min="1" name="default_timeout" value="${settings.default_timeout}"></label>
            <label>Mains timeout (minutes)<input type="number" min="1" name="mains_timeout" value="${settings.mains_timeout}"></label>
            <label>Temperature timeout (minutes)<input type="number" min="1" name="temperature_timeout" value="${settings.temperature_timeout}"></label>
            <label>Startup grace (minutes)<input type="number" min="0" name="startup_grace" value="${settings.startup_grace}"></label>
            <label class="check"><input type="checkbox" name="enabled" ${settings.enabled ? "checked" : ""}> Enable notifications</label>
            <label class="check"><input type="checkbox" name="show_sidebar" ${settings.show_sidebar ? "checked" : ""}> Show Zigbee Pulse in sidebar</label>
            <button class="primary" type="submit">Save global settings</button><output id="global-result"></output>
          </form>
        </section>
        <section class="card"><div class="device-heading"><h2>Per-device settings</h2><input id="filter" placeholder="Filter devices" value="${this._escape(this._filter)}"></div>
          <p class="muted">This list refreshes every 30 seconds and includes newly discovered Zigbee2MQTT last_seen sensors.</p>
          <div class="devices">${deviceCards || "<p>No matching devices.</p>"}</div>
        </section>
      </main>`;
    this._bind(entry);
  }

  _deviceCard(device, settings, live, recipientOptions) {
    const rule = device.rule;
    const status = this._status(device, live);
    const inherited = Number(rule.timeout) === 0;
    const timeoutLabel = inherited
      ? `Timeout (minutes; global: ${device.timeout})`
      : "Timeout (minutes)";
    const selectedOptions = recipientOptions.replace(`value="${this._escape(rule.recipient)}"`, `value="${this._escape(rule.recipient)}" selected`);
    return `<article class="device ${status}"><div class="device-title"><div><h3>${this._escape(device.name)}</h3><code>${this._escape(device.entity_id)}</code></div><span class="pill">${status === "offline" ? "Offline" : "Healthy"}</span></div>
      <form class="device-form" data-entity="${this._escape(device.entity_id)}">
        <label class="check"><input type="checkbox" name="enabled" ${rule.enabled ? "checked" : ""}> Monitor</label>
        <label class="check"><input type="checkbox" name="offline" ${rule.offline ? "checked" : ""}> Offline alerts</label>
        <label class="check"><input type="checkbox" name="recovery" ${rule.recovery ? "checked" : ""}> Recovery alerts</label>
        <label>${timeoutLabel}<input type="number" min="0" name="timeout" value="${device.timeout}"></label>
        <label>Telegram chat<select name="recipient">${selectedOptions}</select></label>
        <button class="primary" type="submit">Save device</button><output></output>
      </form></article>`;
  }

  _bind(entry) {
    this.shadowRoot.querySelector("#refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.querySelector("#filter")?.addEventListener("input", (event) => {
      this._filter = event.target.value;
      this._render();
    });
    this.shadowRoot.querySelector("#test")?.addEventListener("click", async () => {
      await this._hass.callService("telegram_bot", "send_message", {
        entity_id: entry.settings.recipient, message: `Zigbee Pulse test: ${entry.title}`, parse_mode: "plain_text",
      });
    });
    this.shadowRoot.querySelector("#global-form")?.addEventListener("submit", (event) => this._saveGlobal(event, entry));
    this.shadowRoot.querySelectorAll(".device-form").forEach((form) =>
      form.addEventListener("submit", (event) => this._saveDevice(event, entry)));
    this.shadowRoot.addEventListener("focusin", () => { this._editing = true; });
    this.shadowRoot.addEventListener("focusout", () => { this._editing = false; });
  }

  async _saveGlobal(event, entry) {
    event.preventDefault();
    const form = new FormData(event.target);
    const result = event.target.querySelector("output");
    await this._save({ type: "zigbee_pulse/update_config", entry_id: entry.entry_id, scope: "global", settings: {
      name: form.get("name"), recipient: form.get("recipient"), default_timeout: Number(form.get("default_timeout")), mains_timeout: Number(form.get("mains_timeout")), temperature_timeout: Number(form.get("temperature_timeout")), startup_grace: Number(form.get("startup_grace")), enabled: form.get("enabled") === "on", show_sidebar: form.get("show_sidebar") === "on",
    }}, result);
  }

  async _saveDevice(event, entry) {
    event.preventDefault();
    const formElement = event.target;
    const form = new FormData(formElement);
    const result = formElement.querySelector("output");
    const device = entry.devices.find((item) => item.entity_id === formElement.dataset.entity);
    const enteredTimeout = Number(form.get("timeout"));
    const timeout = device && Number(device.rule.timeout) === 0 && enteredTimeout === Number(device.timeout)
      ? 0 : enteredTimeout;
    await this._save({ type: "zigbee_pulse/update_config", entry_id: entry.entry_id, scope: "device", entity_id: formElement.dataset.entity, settings: {
      enabled: form.get("enabled") === "on", offline: form.get("offline") === "on", recovery: form.get("recovery") === "on", timeout, recipient: form.get("recipient"),
    }}, result);
  }

  async _save(message, result) {
    try {
      await this._hass.callWS(message);
      result.textContent = " Saved";
      await this._load();
    } catch (error) {
      result.textContent = ` ${error.message || "Save failed"}`;
    }
  }

  _styles() {
    return `:host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100vh}main{max-width:1200px;margin:0 auto;padding:28px}header,.device-heading,.device-title{display:flex;align-items:center;justify-content:space-between;gap:16px}h1{font-size:28px;margin:0 0 6px}.brand{display:flex;align-items:center;gap:14px}.brand-icon{display:block;width:64px;height:64px;object-fit:contain}.brand p{margin:0}h2{font-size:20px;margin:0 0 18px}h3{margin:0 0 4px;font-size:17px}.card{background:var(--card-background-color);border-radius:12px;padding:22px;margin:20px 0;box-shadow:var(--ha-card-box-shadow,0 2px 6px #0002)}.summary{display:grid;grid-template-columns:repeat(3,1fr) auto;gap:12px;margin:24px 0}.summary div{background:var(--card-background-color);border-radius:12px;padding:18px}.summary strong,.summary span{display:block}.summary strong{font-size:24px}.summary span,.muted,code{color:var(--secondary-text-color);font-size:13px}form{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;align-items:end}label{display:grid;gap:6px;font-size:13px}input,select{box-sizing:border-box;width:100%;padding:10px;border:1px solid var(--divider-color);border-radius:6px;background:var(--primary-background-color);color:var(--primary-text-color);font:inherit}.check{display:flex;display:flex;grid-template-columns:auto 1fr;align-items:center;gap:8px}.check input{width:auto}button,.button{border:0;border-radius:7px;padding:10px 14px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;cursor:pointer;text-decoration:none;text-align:center}.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)}output{color:var(--success-color,#4caf50);font-size:13px}.devices{display:grid;gap:14px}.device{border:1px solid var(--divider-color);border-left:5px solid var(--success-color,#4caf50);border-radius:8px;padding:16px}.device.offline{border-left-color:var(--error-color,#f44336)}.pill{border-radius:999px;padding:4px 9px;font-size:12px;background:#19875422;color:var(--success-color,#4caf50)}.offline .pill{background:#f4433622;color:var(--error-color,#f44336)}@media(max-width:700px){main{padding:16px}.summary{grid-template-columns:1fr 1fr}.summary button{grid-column:1/-1}}
`;
  }
}

customElements.define("zigbee-pulse-panel", ZigbeePulsePanel);
