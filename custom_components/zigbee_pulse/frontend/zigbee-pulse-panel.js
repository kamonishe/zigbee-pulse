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
    const state = String(device.state || "").toLowerCase();
    if (state === "unavailable") return "unavailable";
    if (state === "unknown" || !live?.attributes?.devices?.[device.entity_id]) return "unknown";
    return live.attributes.devices[device.entity_id].stale ? "offline" : "healthy";
  }

  _statusLabel(status) {
    return { healthy: "Healthy", offline: "Offline", unknown: "Unknown", unavailable: "Unavailable" }[status] || "Unknown";
  }

  _elapsed(seconds) {
    if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return "Unknown";
    const total = Math.max(0, Math.floor(Number(seconds) / 60));
    const days = Math.floor(total / 1440);
    const hours = Math.floor((total % 1440) / 60);
    const minutes = total % 60;
    const parts = [];
    if (days) parts.push(`${days} day${days === 1 ? "" : "s"}`);
    if (hours) parts.push(`${hours} hour${hours === 1 ? "" : "s"}`);
    if (minutes || !parts.length) parts.push(`${minutes} minute${minutes === 1 ? "" : "s"}`);
    return parts.join(" and ");
  }

  _messageValues(entry, kind) {
    const liveDevices = this._liveState()?.attributes?.devices || {};
    const devices = entry.devices || [];
    const stale = devices.filter((device) => liveDevices[device.entity_id]?.stale);
    const example = stale[0] || devices[0] || {
      name: "Example Zigbee device", entity_id: "sensor.example_last_seen",
    };
    const selected = kind === "offline" ? (stale.length ? stale : [example]) : [example];
    const staleForList = stale.length ? stale : [example];
    const names = selected.map((device) => `• ${device.name}`).join("\n");
    const staleList = staleForList.map((device, index) =>
      `${index + 1}. ${device.name} — ${this._elapsed(liveDevices[device.entity_id]?.silence_seconds)}`).join("\n");
    const recoveredList = selected.map((device, index) => `${index + 1}. ${device.name}`).join("\n");
    return {
      monitor_name: entry.settings?.name || entry.title || "Zigbee Pulse",
      event: kind === "offline" ? "Device Offline" : "Device Online",
      status: kind === "offline" ? "Offline" : "Online",
      device_name: example.name,
      entity_id: example.entity_id,
      timestamp: new Date().toLocaleString(),
      newly_stale: names,
      stale_count: Math.max(stale.length, 1),
      stale_list: staleList,
      recovered_count: selected.length,
      recovered_list: recoveredList,
    };
  }

  _renderMessageTemplate(template, values) {
    return String(template || "").replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (match, name) =>
      Object.prototype.hasOwnProperty.call(values, name) ? values[name] : `[unknown: ${name}]`);
  }

  _messagePreview(entry, kind) {
    const template = this.shadowRoot.querySelector(`#${kind}-template`)?.value
      ?? entry.settings[`${kind}_template`];
    return this._renderMessageTemplate(template, this._messageValues(entry, kind));
  }

  _updateMessagePreview(entry) {
    const allowed = new Set(["monitor_name", "event", "status", "device_name", "entity_id", "timestamp", "newly_stale", "stale_count", "stale_list", "recovered_count", "recovered_list"]);
    ["offline", "recovery"].forEach((kind) => {
      const preview = this.shadowRoot.querySelector(`#${kind}-message-preview`);
      if (preview) preview.textContent = this._messagePreview(entry, kind);
      const status = this.shadowRoot.querySelector(`#${kind}-message-parser-status`);
      if (!status) return;
      const template = this.shadowRoot.querySelector(`#${kind}-template`)?.value || "";
      const unknown = [...new Set([...template.matchAll(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g)].map((match) => match[1]).filter((name) => !allowed.has(name)))];
      status.textContent = unknown.length
        ? `Unknown variable${unknown.length === 1 ? "" : "s"}: ${unknown.map((name) => `{${name}}`).join(", ")}`
        : "";
      status.className = unknown.length ? "template-status error" : "template-status";
    });
    this._syncMessagePanelHeights();
  }

  _syncMessagePanelHeights() {
    const panels = ["offline-template", "offline-message-preview", "recovery-template", "recovery-message-preview"]
      .map((id) => this.shadowRoot.querySelector(`#${id}`))
      .filter(Boolean);
    panels.forEach((panel) => { panel.style.height = "auto"; });
    const height = Math.max(80, ...panels.map((panel) => panel.scrollHeight)) + 2;
    panels.forEach((panel) => { panel.style.height = `${height}px`; });
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
            <label>Battery timeout (minutes)<input type="number" min="1" max="10080" name="battery_timeout" value="${settings.battery_timeout}"></label>
            <label>Mains timeout (minutes)<input type="number" min="1" max="10080" name="mains_timeout" value="${settings.mains_timeout}"></label>
            <label>Startup grace (minutes)<input type="number" min="0" max="120" name="startup_grace" value="${settings.startup_grace}"></label>
            <label class="check"><input type="checkbox" name="enabled" ${settings.enabled ? "checked" : ""}> Enable notifications</label>
            <label class="check"><input type="checkbox" name="show_sidebar" ${settings.show_sidebar ? "checked" : ""}> Show Zigbee Pulse in sidebar</label>
            <button class="primary" type="submit">Save global settings</button><output id="global-result"></output>
          </form>
        </section>
        <section class="card">
          <h2>Telegram message layout</h2>
          <p class="muted">Edit the offline and recovery messages. The preview parses variables against the current device data as you type.</p>
          <form id="message-form">
            <div class="message-panels">
              <label><span class="message-label">Offline message</span><textarea id="offline-template" name="offline_template" rows="1">${this._escape(settings.offline_template)}</textarea></label>
              <div class="preview-panel">
                <div class="preview-heading"><h3>Offline live result</h3></div>
                <pre id="offline-message-preview" class="message-preview"></pre>
                <p id="offline-message-parser-status" class="template-status"></p>
              </div>
              <label><span class="message-label">Recovery message</span><textarea id="recovery-template" name="recovery_template" rows="1">${this._escape(settings.recovery_template)}</textarea></label>
              <div class="preview-panel">
                <div class="preview-heading"><h3>Recovery live result</h3></div>
                <pre id="recovery-message-preview" class="message-preview"></pre>
                <p id="recovery-message-parser-status" class="template-status"></p>
              </div>
            </div>
            <p class="muted template-legend">Variables: <code>{monitor_name}</code> <code>{event}</code> <code>{device_name}</code> <code>{entity_id}</code> <code>{newly_stale}</code> <code>{stale_count}</code> <code>{stale_list}</code> <code>{recovered_count}</code> <code>{recovered_list}</code> <code>{timestamp}</code></p>
            <div class="message-actions"><button class="primary" type="submit">Save message layout</button><output id="message-result"></output></div>
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
    const differsFromGlobal = Number(device.timeout) !== Number(device.global_timeout);
    const timeoutLabel = differsFromGlobal
      ? `Timeout (minutes; global: ${device.global_timeout})`
      : "Timeout (minutes)";
    const selectedOptions = recipientOptions.replace(`value="${this._escape(rule.recipient)}"`, `value="${this._escape(rule.recipient)}" selected`);
    const isBattery = device.power_source === "battery";
    const powerLabel = isBattery ? "Battery powered" : "Mains powered";
    const powerIcon = isBattery ? "mdi:battery" : "mdi:power-plug";
    return `<article class="device ${status}"><div class="device-title"><div><h3><span class="device-power" title="${powerLabel}" aria-label="${powerLabel}"><ha-icon icon="${powerIcon}"></ha-icon></span>${this._escape(device.name)}</h3><code>${this._escape(device.entity_id)}</code></div><span class="pill">${this._statusLabel(status)}</span></div>
      <form class="device-form" data-entity="${this._escape(device.entity_id)}">
        <label class="check"><input type="checkbox" name="enabled" ${rule.enabled ? "checked" : ""}> Monitor</label>
        <label class="check"><input type="checkbox" name="offline" ${rule.offline ? "checked" : ""}> Offline alerts</label>
        <label class="check"><input type="checkbox" name="recovery" ${rule.recovery ? "checked" : ""}> Recovery alerts</label>
        <label>${timeoutLabel}<input type="number" min="0" max="10080" name="timeout" value="${device.timeout}"></label>
        <label>Telegram chat<select name="recipient">${selectedOptions}</select></label>
        <button class="primary" type="submit">Save device</button><output></output>
      </form></article>`;
  }

  _bindDeviceForms(entry) {
    this.shadowRoot.querySelectorAll(".device-form").forEach((form) =>
      form.addEventListener("submit", (event) => this._saveDevice(event, entry)));
  }

  _bind(entry) {
    this.shadowRoot.querySelector("#refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.querySelector("#filter")?.addEventListener("input", (event) => {
      event.stopPropagation();
      this._filter = event.target.value;
      const live = this._liveState();
      const filter = this._filter.toLowerCase();
      const devices = entry.devices.filter((device) =>
        !filter || `${device.name} ${device.entity_id}`.toLowerCase().includes(filter));
      const recipientOptions = (this._data.recipients || []).map((recipient) =>
        `<option value="${this._escape(recipient.entity_id)}">${this._escape(recipient.name || recipient.entity_id)}</option>`).join("");
      const container = this.shadowRoot.querySelector(".devices");
      if (container) {
        const cards = devices.map((device) => this._deviceCard(device, entry.settings, live, recipientOptions)).join("");
        container.innerHTML = cards || "<p>No matching devices.</p>";
        this._bindDeviceForms(entry);
      }
    });
    this.shadowRoot.querySelector("#test")?.addEventListener("click", async () => {
      await this._hass.callService("telegram_bot", "send_message", {
        entity_id: entry.settings.recipient, message: this._messagePreview(entry, "offline"), parse_mode: "plain_text",
      });
    });
    this.shadowRoot.querySelector("#global-form")?.addEventListener("submit", (event) => this._saveGlobal(event, entry));
    this.shadowRoot.querySelector("#message-form")?.addEventListener("submit", (event) => this._saveMessages(event, entry));
    ["#offline-template", "#recovery-template"].forEach((selector) =>
      this.shadowRoot.querySelector(selector)?.addEventListener("input", () => this._updateMessagePreview(entry)));
    this._updateMessagePreview(entry);
    this._bindDeviceForms(entry);
    this.shadowRoot.addEventListener("focusin", () => { this._editing = true; });
    this.shadowRoot.addEventListener("focusout", () => { this._editing = false; });
  }

  _readMinutes(form, name, minimum, maximum, label, result) {
    const raw = String(form.get(name) ?? "").trim();
    if (!/^\d+$/.test(raw)) {
      result.textContent = ` ${label} must be a whole number between ${minimum} and ${maximum}`;
      return null;
    }
    const value = Number(raw);
    if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
      result.textContent = ` ${label} must be between ${minimum} and ${maximum}`;
      return null;
    }
    return value;
  }

  async _saveGlobal(event, entry) {
    event.preventDefault();
    const form = new FormData(event.target);
    const result = event.target.querySelector("output");
    const mainsTimeout = this._readMinutes(form, "mains_timeout", 1, 10080, "Mains timeout", result);
    const batteryTimeout = this._readMinutes(form, "battery_timeout", 1, 10080, "Battery timeout", result);
    const startupGrace = this._readMinutes(form, "startup_grace", 0, 120, "Startup grace", result);
    if ([mainsTimeout, batteryTimeout, startupGrace].some((value) => value === null)) return;
    await this._save({ type: "zigbee_pulse/update_config", entry_id: entry.entry_id, scope: "global", settings: {
      name: form.get("name"), recipient: form.get("recipient"), mains_timeout: mainsTimeout, battery_timeout: batteryTimeout, startup_grace: startupGrace, enabled: form.get("enabled") === "on", show_sidebar: form.get("show_sidebar") === "on",
    }}, result);
  }

  async _saveMessages(event, entry) {
    event.preventDefault();
    const form = new FormData(event.target);
    const result = event.target.querySelector("#message-result");
    await this._save({ type: "zigbee_pulse/update_config", entry_id: entry.entry_id, scope: "global", settings: {
      offline_template: form.get("offline_template"), recovery_template: form.get("recovery_template"),
    }}, result);
  }

  async _saveDevice(event, entry) {
    event.preventDefault();
    const formElement = event.target;
    const form = new FormData(formElement);
    const result = formElement.querySelector("output");
    const device = entry.devices.find((item) => item.entity_id === formElement.dataset.entity);
    const enteredTimeout = this._readMinutes(form, "timeout", 0, 10080, "Device timeout", result);
    if (enteredTimeout === null) return;
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
    return `:host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100vh}main{max-width:2400px;margin:0 auto;padding:16px}header,.device-heading,.device-title{display:flex;align-items:center;justify-content:space-between;gap:16px}h1{font-size:28px;margin:0 0 6px}.brand{display:flex;align-items:center;gap:14px}.brand-icon{display:block;width:64px;height:64px;object-fit:contain}.brand p{margin:0}h2{font-size:20px;margin:0 0 12px}h3{margin:0 0 4px;font-size:17px}.card{background:var(--card-background-color);border-radius:12px;padding:14px;margin:12px 0;box-shadow:var(--ha-card-box-shadow,0 2px 6px #0002)}.summary{display:grid;grid-template-columns:repeat(3,1fr) auto;gap:8px;margin:14px 0}.summary div{background:var(--card-background-color);border-radius:12px;padding:12px}.summary strong,.summary span{display:block}.summary strong{font-size:24px}.summary span,.muted,code{color:var(--secondary-text-color);font-size:13px}form{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;align-items:end}#message-form{display:block}.message-panels{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;align-items:start}.message-panels>label{min-width:0;display:flex;flex-direction:column;gap:8px}.message-label{height:16px;line-height:16px;box-sizing:border-box}.message-panels textarea{width:100%;min-height:0;flex:none;font-family:inherit;font-size:13px;line-height:1.4;background:var(--card-background-color,#fafafa)}.preview-panel{display:flex;flex-direction:column;gap:8px;min-width:0}.message-actions{display:flex;align-items:center;gap:8px;margin-top:10px}label{display:grid;gap:6px;font-size:13px}input,select,textarea{box-sizing:border-box;width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:6px;background:var(--primary-background-color);color:var(--primary-text-color);font:inherit}.device-heading input{width:220px;flex:0 0 220px}textarea{resize:none;min-height:0;line-height:1.4}.check{display:flex;display:flex;grid-template-columns:auto 1fr;align-items:center;gap:8px}.check input{width:auto}button,.button{border:0;border-radius:7px;padding:8px 12px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;cursor:pointer;text-decoration:none;text-align:center}.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)}output{color:var(--success-color,#4caf50);font-size:13px}.preview-heading{display:flex;flex-direction:column;align-items:stretch;gap:8px;height:16px;line-height:16px;box-sizing:border-box}.preview-heading h3{margin:0;font:inherit;font-size:13px;font-weight:400}.message-preview{box-sizing:border-box;margin:0;padding:16px;min-height:0;font-family:inherit;font-size:13px;line-height:1.4;white-space:pre-wrap;overflow:hidden;border:1px solid var(--divider-color);border-radius:8px;background:var(--secondary-background-color,#f2f2f2);}.template-status{margin:0;color:var(--secondary-text-color);font-size:13px}.template-legend{margin:0;padding-top:4px}.template-status.error{color:var(--error-color,#f44336)}.devices{display:grid;gap:14px}.device{border:1px solid var(--divider-color);border-left:5px solid var(--success-color,#4caf50);border-radius:8px;padding:16px}.device.offline{border-left-color:var(--error-color,#f44336)}.device.unknown,.device.unavailable{border-left-color:var(--disabled-text-color,var(--secondary-text-color,#9e9e9e))}.device-power{display:inline-flex;vertical-align:-3px;margin-right:7px;color:var(--secondary-text-color)}.device-power ha-icon{--mdc-icon-size:18px;width:18px;height:18px}.pill{border-radius:999px;padding:4px 9px;font-size:12px;background:#19875422;color:var(--success-color,#4caf50)}.offline .pill{background:#f4433622;color:var(--error-color,#f44336)}.unknown .pill,.unavailable .pill{background:#9e9e9e33;color:var(--disabled-text-color,var(--secondary-text-color,#9e9e9e))}@media(max-width:900px){main{padding:16px}.summary{grid-template-columns:1fr 1fr}.message-panels{grid-template-columns:1fr}.summary button{grid-column:1/-1}}@media(max-width:600px){.device-heading{align-items:stretch;flex-direction:column}.device-heading input{width:100%;flex-basis:auto}}
`;
  }
}

if (!customElements.get("zigbee-pulse-panel")) customElements.define("zigbee-pulse-panel", ZigbeePulsePanel);
