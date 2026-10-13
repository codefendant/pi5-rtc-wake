/* Pi Wake & Sleep native Home Assistant cards. No external libraries or cloud calls. */
"use strict";
(() => {
  const DOMAIN = "pi5_rtc_wake";
  const names = {setup: "Pi setup", status: "Pi status", shutdown: "Next shutdown", wake: "Next wake", calendar: "Pi Sleep calendar", ups: "UPS power", controls: "Pi controls", devices: "Wake other devices", messages: "Messages", assist: "Assist", activity: "Recent activity"};
  const icons = {setup: "shield-check-outline", status: "power", shutdown: "weather-night", wake: "white-balance-sunny", calendar: "calendar", ups: "battery", controls: "power-settings", devices: "lan-connect", messages: "cellphone", assist: "message-text-outline", activity: "history"};
  const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[character]));
  const icon = name => `<ha-icon icon="mdi:${esc(name)}"></ha-icon>`;
  const badge = (text, state = "") => `<span class="badge ${state}">${esc(text)}</span>`;
  const button = (action, text, style = "", disabled = false) => `<button type="button" data-action="${action}" class="${style}" ${disabled ? "disabled" : ""}>${text}</button>`;
  const link = (url, text) => `<a href="${esc(url)}">${text}</a>`;
  const check = (key, label, value, disabled = false) => `<label class="toggle"><input type="checkbox" name="${key}" ${value ? "checked" : ""} ${disabled ? "disabled" : ""}>${esc(label)}</label>`;
  const sleepTestMessage = "After a 30-second countdown, the Pi and Home Assistant will shut down. Home Assistant and its automations will be unavailable for roughly ten minutes, plus startup time. The RTC is set to wake the Pi automatically about ten minutes after the test starts. Leave main power connected. When Home Assistant returns, open Pi Wake & Sleep, confirm whether it returned by itself, and continue setup. If it has not returned after 15 minutes, press the Pi power button and choose No / I'm not sure. Scheduling and UPS recovery turn off for this test; review them afterward.";
  const recoveryFields = {
    shutdown_runtime_minutes: ["Shut down at remaining runtime (minutes)", 5, 240],
    first_retry_minutes: ["First retry after shutdown (minutes)", 10, 120],
    max_retry_minutes: ["Maximum retry interval (minutes)", 10, 360],
    max_retries: ["Maximum RTC retries per outage", 1, 8],
    retry_reserve_minutes: ["Keep this runtime reserve after a retry (minutes)", 3, 60],
    min_charge_percent: ["Low-battery charge threshold (%)", 5, 80],
    boot_grace_minutes: ["Boot/readings allowance (minutes)", 1, 15],
    emergency_runtime_minutes: ["Emergency shutdown at remaining runtime (minutes)", 2, 60],
    stable_power_minutes: ["Utility power must stay stable (minutes)", 1, 15],
    outage_delay_minutes: ["Early shutdown after outage lasts (minutes)", 1, 120]
  };
  const recoveryFlags = ["enabled", "retry_enabled", "emergency_enabled", "early_shutdown", "owner_confirmed", "supply_confirmed", "final_shutdown_confirmed"];
  const styles = `
    :host{display:block;scroll-margin-top:80px;color:var(--primary-text-color,#172033);font:14px/1.5 var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
    ha-card{display:block;border-radius:var(--ha-card-border-radius,12px);border:1px solid var(--divider-color,#dce3eb);box-shadow:var(--ha-card-box-shadow,none);background:var(--ha-card-background,var(--card-background-color,#fff));overflow:hidden}
    .power-switch{padding:0!important;border:2px solid transparent}.power-switch[aria-pressed="true"]{background:#fff0ce;color:#805600;border-color:#bd7d00}.power-switch:disabled{opacity:.5}.event-link{border:0;padding:0;min-height:0;text-align:left;justify-content:flex-start}.native-calendar{min-height:200px}
    .setup-nav{margin-bottom:16px}.setup-ready.needs-attention{background:#fff0ce;color:#805600}.setup-ready.needs-attention ha-icon{color:inherit}
    :host([dark]) .setup-ready.needs-attention{background:#4d3b12;color:#ffe3a1}
    .body{padding:20px 22px}.heading{display:flex;align-items:center;gap:10px;margin-bottom:16px}h2{font-size:18px;font-weight:600;margin:0;line-height:1.35}.heading>.badge{margin-left:auto}.setup-ready a{font-size:13px}.setup-links{display:flex;gap:12px;align-items:center;margin-left:auto;flex-wrap:wrap}.setup-links button{margin-left:0}.retry-plan{overflow-x:auto}.settings-header{margin-bottom:0}h3{font-size:16px;margin:12px 0}p{margin:10px 0}.muted,small{color:var(--secondary-text-color,#677386)}.hint{font-size:13px}.badge{display:inline-flex;align-items:center;gap:5px;border-radius:7px;padding:3px 9px;background:var(--secondary-background-color,#edf1f5);font-size:12px;white-space:nowrap}.badge.ok{background:#d4f2dd;color:#166534}.badge.warn{background:#fff0ce;color:#905700}.badge.error{background:#fbe1df;color:#a02620}
    .metric{display:flex;align-items:center;gap:20px}.metric .symbol{display:grid;place-items:center;width:76px;height:76px;flex-shrink:0;border-radius:50%;background:var(--pi-icon-background,#e5f7f9);color:#008595}.symbol ha-icon{--mdc-icon-size:44px}.big{font-size:35px;font-weight:700;line-height:1.3;letter-spacing:-.5px}.sub{font-size:16px}.uptime{font-size:19px;font-weight:600;margin-top:5px}
    button,a{font:inherit}button{min-height:42px;padding:9px 14px;border:1px solid var(--divider-color,#dce3eb);border-radius:8px;color:var(--primary-color,#008cff);background:transparent;cursor:pointer;font-weight:500;display:inline-flex;align-items:center;justify-content:center;gap:8px}button.primary{background:var(--primary-color,#008cff);border-color:var(--primary-color,#008cff);color:var(--text-primary-color,#fff)}button.danger{background:#e8242e;border-color:#e8242e;color:#fff}button:disabled{opacity:.48;cursor:default}.full{width:100%}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}.actions>*{flex:1}a{color:var(--primary-color,#008cff);text-decoration:none}a:hover{text-decoration:underline}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--primary-color,#008cff);outline-offset:3px}
    .row{display:flex;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--divider-color,#dce3eb)}.row:last-child{border-bottom:0}.row .end{margin-left:auto;text-align:right}.row .dates{font-size:13px}.row ha-icon{color:var(--primary-color,#008cff)}.row strong{display:block}.calendar-actions{padding-top:12px}.calendar-footer{margin-top:14px;padding-top:14px;border-top:1px solid var(--divider-color,#dce3eb)}.calendar-footer button{margin-top:8px}.dot{display:inline-block;width:12px;height:12px;border-radius:50%;background:#20a050;margin-right:8px}.battery{display:flex;gap:20px;align-items:center;margin:20px 0}.battery ha-icon{--mdc-icon-size:62px;color:#20a050}.setup-ready{color:var(--pi-ready-text,#166534);display:flex;align-items:center;gap:12px;padding:14px 20px;background:var(--pi-ready-background,#e8f7ef)}.setup-ready ha-icon{color:#199449}.setup-ready button{margin-left:auto;font-size:13px;border:0;min-height:30px}.setup-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:24px}.steps{display:flex;gap:12px;align-items:center;margin-bottom:20px}.steps span{color:var(--secondary-text-color,#677386)}.steps .current{color:var(--primary-color,#008cff);font-weight:600}.steps span+span:before{content:"›";margin-right:12px;color:var(--disabled-text-color,#a0a9b8)}.guide{border:1px solid var(--divider-color,#dce3eb);border-radius:12px;padding:16px;background:var(--secondary-background-color,#f6f8fb)}.guide .switch-row{border:2px solid #e8242e;border-radius:8px;padding:10px;display:flex;align-items:center;justify-content:space-between;gap:15px}.switch{width:44px;height:24px;border-radius:24px;background:var(--primary-color,#008cff);position:relative;flex-shrink:0}.switch:after{content:"";position:absolute;width:18px;height:18px;border-radius:50%;background:#fff;right:3px;top:3px}.guide small{display:block;margin-top:8px;color:#bc2028}.notice{border-radius:8px;padding:12px 14px;background:#fff0ce;color:#805600;margin:12px 0}.error-notice{background:var(--error-state-color,#fbe1df);color:var(--error-color,#b3261e)}.progress{padding:10px;border-left:3px solid var(--primary-color,#008cff);background:var(--secondary-background-color,#f2f5f9)}
    details{margin-top:12px}summary{cursor:pointer;color:var(--primary-color,#008cff)}.details-body{padding-top:14px}.settings{margin-top:20px;padding-top:16px;border-top:1px solid var(--divider-color,#dce3eb)}label{display:block;margin:12px 0;font-weight:500}input:not([type=checkbox]),select{box-sizing:border-box;display:block;width:100%;min-height:42px;border:1px solid var(--divider-color,#dce3eb);border-radius:8px;padding:9px 11px;margin-top:6px;background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--primary-text-color,#172033);font:inherit}.toggle{display:flex;gap:10px;align-items:flex-start;font-weight:400}.toggle input{width:19px;height:19px;flex-shrink:0;accent-color:var(--primary-color,#008cff)}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.fields{max-height:270px;overflow:auto;border:1px solid var(--divider-color,#dce3eb);border-radius:8px;padding:0 12px}.fields label{border-bottom:1px solid var(--divider-color,#dce3eb);padding-bottom:10px}.fields small{display:block;font-size:12px;font-weight:400}.selected-fields{display:flex;flex-wrap:wrap;gap:6px}.selected-fields button{font-size:12px;min-height:28px;padding:3px 8px}.preview{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;background:var(--secondary-background-color,#f5f7fa);padding:14px;border-radius:8px}.activity{list-style:none;padding:0;margin:0}.activity li{padding:9px 0;border-bottom:1px solid var(--divider-color,#dce3eb)}.activity small{display:block}.checks{padding-left:20px}.checks li{margin-bottom:5px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px;border-bottom:1px solid var(--divider-color,#dce3eb)}.outage{background:#fff0ce;color:#805600;padding:12px;border-radius:8px}.footer{margin-top:12px}
    .sleep-test-guide{margin:16px 0;border-color:var(--primary-color,#008cff)}.sleep-cycle{display:flex;align-items:center;justify-content:space-between;gap:7px;font-size:13px;color:var(--primary-color,#008cff)}.sleep-cycle span{display:flex;align-items:center;gap:5px}.sleep-cycle ha-icon{--mdc-icon-size:19px}.sleep-test-guide p:last-child{margin-bottom:0}
    :host([dark]){--pi-icon-background:#163e44;--pi-ready-background:#173f2f;--pi-ready-text:#b7eccb}
    @media(max-width:550px){.body{padding:18px}.setup-grid,.form-grid{grid-template-columns:1fr}.steps{font-size:12px;gap:8px}.steps span+span:before{margin-right:8px}.big{font-size:30px}.row{align-items:flex-start;flex-wrap:wrap}.row .end{flex-basis:100%;text-align:left;margin-left:36px}.setup-ready{flex-wrap:wrap}}
  `;

  const connections = new WeakMap();
  class Feed {
    constructor(hass, entry) { this.hass = hass; this.entry = entry; this.listeners = new Set(); this.state = null; this.error = ""; this.timer = null; this.running = false; }
    add(listener) { this.listeners.add(listener); if (this.state || this.error) listener(this.state, this.error); if (!this.timer) { this.refresh(); this.timer = setInterval(() => this.refresh(), 5000); } return () => { this.listeners.delete(listener); if (!this.listeners.size) { clearInterval(this.timer); this.timer = null; } }; }
    async refresh() { if (this.running) return; this.running = true; try { this.state = await this.hass.callWS({type: DOMAIN + "/status", entry_id: this.entry}); this.error = ""; } catch (error) { this.error = error.message || "Pi Wake & Sleep is unavailable. Check that the app is running."; } finally { this.running = false; for (const listener of this.listeners) listener(this.state, this.error); } }
  }
  function feedFor(hass, entry) { const key = hass.connection || hass; let entries = connections.get(key); if (!entries) { entries = new Map(); connections.set(key, entries); } if (!entries.has(entry)) entries.set(entry, new Feed(hass, entry)); const feed = entries.get(entry); feed.hass = hass; return feed; }

  class PiCard extends HTMLElement {
    constructor() { super(); this.attachShadow({mode: "open"}); this.state = null; this.error = ""; this.message = ""; this.panel = null; this.busy = false; this.dirty = false; this.setupDismissed = false; this.detailsOpen = new Map(); this.previewRequested = false; this.calendarWidget = null; this.calendarRequest = 0; this.waitingForMessages = false; this.awaitingDraftPreview = false; this.refreshingOptions = false; }
    setConfig(config) { this.config = {...config}; this.unbind(); if (this.isConnected) this.bind(); this.render(); }
    set hass(hass) { this._hass = hass; if (this.calendarWidget) this.calendarWidget.hass = hass; this.toggleAttribute("dark", Boolean(hass.themes?.darkMode)); if (this.isConnected && !this.unsubscribe) this.bind(); }
    get kind() { return this.constructor.kind; }
    get admin() { return this._hass?.user?.is_admin === true; }
    get blocked() { return !this.admin || !this.state || Boolean(this.error) || this.busy || Boolean(this.state?.job || this.state?.pending || this.state?.shutdown_requested); }
    get pauseBlocked() { return !this.admin || !this.state || Boolean(this.error) || this.busy || Boolean(this.state?.shutdown_requested || this.state?.storage_notice); }
    connectedCallback() { this.bind(); this.render(); }
    disconnectedCallback() { this.unbind(); }
    unbind() { this.unsubscribe?.(); this.unsubscribe = null; }
    bind() { if (!this._hass || !this.config || this.unsubscribe) return; this.feed = feedFor(this._hass, this.config.entry_id || ""); this.unsubscribe = this.feed.add((state, error) => { const wasReady = this.ready; this.state = state; this.error = error; if (wasReady && !this.ready) this.setupDismissed = false; if (this.waitingForMessages && !this.busy && !state?.messages?.busy) { this.waitingForMessages = false; if (state?.messages?.options_revision) this.loadMessageOptions(); else this.message = [state?.messages?.result?.message, state?.messages?.result?.action].filter(Boolean).join(" ") || "Phone discovery did not finish. Select Choose phone to try again."; } if ((!this.panel || this.panel === "setup") && !this.confirming) this.render(); else if (!this.confirming) { this.disableForm(this.blocked); if (this.panel === "messages" && !this.busy) this.updateMessagePreview(); } }); }
    getCardSize() { return this.kind === "setup" && !this.setupExpanded ? 1 : this.kind === "activity" ? 1 : 4; }
    getGridOptions() { return {columns: 12, rows: "auto", min_columns: 6, min_rows: this.kind === "setup" || this.kind === "activity" ? 1 : 3}; }
    get ready() { return Boolean(this.state?.checks?.ok && this.state?.test_status === "passed"); }
    get setupExpanded() { return this.panel === "setup" || !this.ready && !this.setupDismissed; }
    time(epoch, compact = false) { if (!epoch) return "—"; return new Intl.DateTimeFormat(this._hass?.locale?.language || undefined, {timeZone: this.state.schedule.timezone, hour: "numeric", minute: "2-digit", ...(compact ? {} : {month: "short", day: "numeric", timeZoneName: "short"})}).format(new Date(epoch * 1000)); }
    day(epoch) { const tz = this.state.schedule.timezone; const format = new Intl.DateTimeFormat("en-CA", {timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit"}); const now = new Date(this.state.current_epoch * 1000), date = new Date(epoch * 1000); if (format.format(now) === format.format(date)) return "Today"; const parts = Object.fromEntries(format.formatToParts(now).map(part => [part.type,part.value])); const tomorrow = new Date(Date.UTC(Number(parts.year),Number(parts.month)-1,Number(parts.day)+1)); const next = new Intl.DateTimeFormat("en-CA", {timeZone:"UTC",year:"numeric",month:"2-digit",day:"2-digit"}); if (next.format(tomorrow) === format.format(date)) return "Tomorrow"; return new Intl.DateTimeFormat(this._hass?.locale?.language || undefined, {timeZone: tz, weekday: "long", month: "short", day: "numeric"}).format(date); }
    relative(epoch) { const minutes = Math.max(0, Math.round((epoch - this.state.current_epoch) / 60)); return minutes < 60 ? `in ${minutes} min` : minutes < 1440 ? `in ${Math.floor(minutes / 60)} h${minutes % 60 ? " " + minutes % 60 + " min" : ""}` : `in ${Math.round(minutes / 1440)} days`; }
    appUrl(view = "") { const slug = this.state?.permissions?.slug; return slug ? `/app/${encodeURIComponent(slug)}${view ? "#" + view : ""}` : "/config/apps"; }
    infoUrl() { const slug = this.state?.permissions?.slug; return slug ? `/config/app/${encodeURIComponent(slug)}/info` : "/config/apps"; }
    heading(extra = "") { return `<div class="heading"><h2>${esc(this.config?.title || names[this.kind])}</h2>${extra}</div>`; }
    async call(action, payload = {}) { if (!this.admin || this.busy) return false; this.busy = true; this.message = ""; if (!this.panel || this.panel === "setup") this.render(); else this.disableForm(true); try { await this._hass.callWS({type: DOMAIN + "/action", entry_id: this.config.entry_id || "", action, payload}); await this.feed.refresh(); this.message = "Action accepted."; return true; } catch (error) { this.message = error.message || "This action could not finish. Refresh the dashboard and try again."; return false; } finally { this.busy = false; if (!this.panel || this.panel === "setup") this.render(); else { this.disableForm(this.blocked); const feedback = this.shadowRoot.querySelector(".form-feedback"); if (feedback) feedback.textContent = this.message; } } }
    disableForm(disabled) {
      disabled = disabled || Boolean(this.panel === "messages" && (this.state?.messages?.busy || this.refreshingOptions)) || Boolean(this.panel === "devices" && (this.state?.wake_devices?.busy || this.refreshingDevices));
      for (const element of this.shadowRoot.querySelectorAll(".settings button,.settings input,.settings select")) if (element.dataset.action !== "close-panel") element.disabled = disabled || !this.admin;
      if (this.panel === "protection") this.updateProtectionForm();
    }
    async confirm(title, text, label, danger = false) {
      this.confirming = true;
      return new Promise(resolve => {
        const dialog = document.createElement("dialog");
        dialog.style.cssText = "max-width:460px;width:calc(100% - 60px);border:1px solid var(--divider-color,#dce3eb);border-radius:12px;padding:24px;background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--primary-text-color,#172033);font:inherit";
        dialog.innerHTML = `<h2>${esc(title)}</h2><p>${esc(text)}</p><form method="dialog"><div class="actions"><button value="cancel">Go back</button><button value="confirm" class="${danger ? "danger" : "primary"}">${esc(label)}</button></div></form>`;
        dialog.addEventListener("close", () => { const confirmed = dialog.returnValue === "confirm"; dialog.remove(); this.confirming = false; resolve(confirmed); }, {once: true});
        this.shadowRoot.append(dialog); dialog.showModal();
      });
    }
    async perform(action) {
      if (action === "close-panel") { if (this.dirty && !window.confirm("Discard your unsaved changes?")) return; this.panel = null; this.calendarWidget = null; this.awaitingDraftPreview = false; this.refreshingOptions = false; this.dirty = false; this.message = ""; if (this.kind === "setup") this.setupDismissed = true; this.render(); if (this.kind === "setup") this.scrollIntoView({behavior: "smooth", block: "start"}); return; }
      if (action === "review-setup") { this.panel = "setup"; this.setupDismissed = false; this.render(); return; }
      if (action === "choose-calendar") { this.panel = "calendar"; this.dirty = false; this.render(); return; }
      if (action === "choose-ups") { this.panel = "ups"; this.dirty = false; this.render(); return; }
      if (action === "configure-protection") { if (this.blocked) return; this.protectionTargets = {source_id: this.state.ups.settings.source_id, calendar_id: this.state.schedule.calendar_entity_id}; this.protectionDraft = structuredClone(this.state.recovery.settings); this.panel = "protection"; this.dirty = false; this.render(); return; }
      if (action === "pause-rtc-retries") { if (await this.confirm("Pause timed retries for this outage?", "Cancel timed retry work for this outage. Emergency low-battery protection stays active if enabled. Use Keep awake to suspend every app shutdown instead.", "Pause timed retries")) await this.call(action); return; }
      if (action === "preview-message-draft") { if (this.blocked || this.state.messages.busy || this.refreshingOptions) return; const form = this.shadowRoot.querySelector("form"); this.awaitingDraftPreview = true; const settings = {recipient: form.querySelector('[name="recipient"]').value || null, enabled: form.querySelector('[name="enabled"]').checked, fields: [...this.messageDraft.fields]}; if (!await this.call("preview-message", {settings})) this.awaitingDraftPreview = false; this.updateMessagePreview(); return; }
      if (action === "refresh-message-options") { await this.refreshMessageOptions(); return; }
      if (action === "choose-phone") { await this.openMessages(); return; }
      if (action === "choose-wake-devices") { await this.openWakeDevices(); return; }
      if (action === "refresh-wake-devices") { await this.openWakeDevices(true); return; }
      if (action === "wake-devices") {
        if (this.blocked || this.state.wake_devices.busy) return;
        const settings = structuredClone(this.state.wake_devices.settings);
        if (await this.confirm("Wake selected devices?", "Send a Wake on LAN request to " + settings.devices.map(row => row.name).join(", ") + ". A Ping check, when selected, confirms network reachability. The Pi's own schedule stays as configured.", "Wake selected")) await this.call(action, {confirmed: true, expected_settings: settings});
        return;
      }
      if (action === "configure-assist") { this.panel = "assist"; this.dirty = false; this.render(); return; }
      if (action === "create-calendar") { await this.call(action, {confirmed: true}); return; }
      if (action.startsWith("calendar-event:")) { await this.openCalendar(action.slice(15)); return; }
      if (action === "toggle-keep-awake") {
        if (this.pauseBlocked) return;
        const active = !this.state.keep_awake;
        const text = active ? "Suspend every shutdown and reboot from this app, including emergency low-battery UPS shutdowns. The Pi stays awake until you resume, even after an app restart. Calendar dates and settings are kept. Other apps retain their own power controls."
          : `Resume your saved settings: Calendar scheduling ${this.state.schedule.enabled ? "on" : "off"}; UPS protection ${this.state.recovery.settings.enabled ? "on" : "off"}. Normal setup and fresh-reading checks still apply. A low UPS reserve may trigger shutdown immediately.`;
        if (await this.confirm(active ? "Keep awake?" : "Resume shutdowns?", text, active ? "Keep awake" : "Resume shutdowns", active && this.state.recovery.settings.enabled)) await this.call("keep-awake", {active, confirmed: true});
        return;
      }
      if (action === "toggle-scheduling") { const enabled = !this.state.schedule.enabled; if (!enabled || await this.confirm("Enable Calendar scheduling?", "Every timed event in the selected calendar becomes a shutdown-to-wake period. Review the dates shown here first.", "Enable scheduling")) await this.call("settings", {...this.state.schedule, enabled}); return; }
      if (action === "reboot-now") { if (await this.confirm("Reboot the Pi?", "Home Assistant will be unavailable for a few minutes. Leave the power connected.", "Reboot Pi", true)) await this.call(action, {confirmed: true}); return; }
      if (action === "prepare") { if (await this.confirm("Prepare wake settings?", "Your existing boot order will be kept. Leave power connected. A Pi reboot is needed afterward.", "Prepare this Pi")) await this.call(action, {confirmed: true}); return; }
      if (action === "test") { const first = !this.ready && this.state.test_status === "not_started"; if (await this.confirm(first ? "Start your first sleep & wake cycle?" : "Run a ten-minute sleep & wake test?", sleepTestMessage, "Start sleep & wake test", true)) await this.call(action, {confirmed: true}); return; }
      if (action === "confirm-test") { await this.call(action, {returned_automatically: true}); return; }
      if (action === "reject-test") { await this.call(action); return; }
      if (action === "restore-cards") { if (await this.confirm("Restore default Pi cards?", "This replaces the Pi cards in the Pi dashboard. Your pictures, graphs, other cards, settings, and calendars are kept.", "Restore Pi cards")) await this.call(action, {confirmed: true}); return; }
      if (action === "send-message") { if (await this.confirm("Send Pi status to your saved phone?", "The message includes uptime, the next shutdown and wake times, and your selected readings.", "Send status")) await this.call(action, {confirmed: true, expected_settings: this.state.messages.settings}); return; }
      if (action === "preview-saved-message") { this.previewRequested = true; await this.call("preview-message", {settings: this.state.messages.settings}); return; }
      if (action === "connect-assist") { if (await this.confirm("Enable Assist status access?", "Use Assist in your existing conversation agent's Control Home Assistant setting. AI change requests remain off.", "Enable Assist")) await this.call("assist-settings", {enabled: true, allow_requests: false}); return; }
      if (action === "cancel") { await this.call("cancel"); return; }
      if (action === "check" || action === "scan-ups") { await this.call(action); return; }
      if (action === "scan-messages") { if (await this.call(action)) this.message = "Finding phones and readings…"; return; }
      if (action.startsWith("enable-sensor:")) { const id = action.slice(14); if (await this.confirm("Enable this NUT reading?", "Home Assistant may reload NUT. Wait for fresh readings afterward.", "Enable reading")) await this.call("enable-nut-sensor", {confirmed: true, expected_source_id: this.state.ups.settings.source_id, entity_id: id}); return; }
      if (action.startsWith("approve:") || action.startsWith("dismiss:")) { const id = action.split(":")[1], request = this.state.assist.requests.find(item => item.id === id); if (!request) return; const approve = action.startsWith("approve:"); if (!approve || await this.confirm("Approve Assist request?", request.summary + " Leave power connected for Pi operations.", "Approve", request.kind === "reboot" || request.kind === "wake_test")) await this.call("assist-review", {id, approve, confirmed: true}); }
    }
    setupBody() {
      const data = this.state, protectedMode = data.permissions?.protected;
      if (!this.setupExpanded) return `<div class="setup-ready ${this.ready ? "" : "needs-attention"}">${icon(this.ready ? "check-circle" : "alert-circle-outline")}<strong>${this.ready ? "Pi ready · Wake test passed" : "Pi setup needs attention"}</strong>${button("review-setup", "Review setup")}${this.admin ? link(this.appUrl(), "Setup & maintenance ↗") : ""}</div>`;
      const stage = protectedMode !== false ? 0 : data.checks.ok ? 2 : 1;
      const returning = data.test_status === "awaiting_confirmation";
      const firstCycle = data.test_status === "not_started";
      const testing = data.pending?.kind === "test";
      const testGuide = stage === 2 && !this.ready && !returning ? `<div class="guide sleep-test-guide"><div class="sleep-cycle" aria-label="Test sequence: awake, asleep, awake again"><span>${icon("power")}Awake now</span><span aria-hidden="true">→</span><span>${icon("weather-night")}Asleep</span><span aria-hidden="true">→</span><span>${icon("white-balance-sunny")}Awake again</span></div><p><strong>Home Assistant will shut down and be unavailable for roughly ten minutes, plus startup time.</strong></p><p>This checks that your Pi can sleep and start itself again. ${testing ? `The wake alarm is set for ${esc(this.time(data.pending.wake_epoch))}.` : "The RTC is set to wake the Pi automatically about ten minutes after the test starts."} Leave main power connected.</p><p>When Home Assistant returns, open Pi Wake &amp; Sleep, confirm whether it returned by itself, and continue setup.</p><p class="hint muted">If it has not returned after 15 minutes, press the Pi power button and choose No / I'm not sure.</p></div>` : "";
      const returnGuide = returning ? `<p class="notice"><strong>Welcome back.</strong> If the Pi woke automatically, select Yes, it returned by itself below. You can then continue setup on the Calendar and other dashboard cards. If you powered it on yourself, select No / I'm not sure.</p>` : "";
      let content;
      if (stage === 0) content = `<div class="setup-grid"><div><h2>Allow access to your Pi</h2><p>${protectedMode === true ? "Turn off Protection mode on the app's Info page. Then restart the app." : "Check Protection mode on the app's Info page."}</p><ol><li>Stop the app</li><li>Turn Protection mode off</li><li>Start the app</li></ol><div class="actions">${link(this.infoUrl(), "Open app Info ↗")}${button("check", "Check again", "", this.blocked)}</div></div><div class="guide" aria-label="Illustration of the app Info page"><strong>Pi RTC Wakealarm — Info</strong><p class="muted">Stop → change setting → Start</p><div class="switch-row"><span>Protection mode</span><span class="switch" role="img" aria-label="Protection mode is on in this illustration"></span></div><small>Turn this switch off</small></div></div>`;
      else content = `<h2>${this.ready ? "Pi setup complete" : stage === 1 ? "Check this Pi" : returning ? "Did Home Assistant return by itself?" : testing ? "Sleep &amp; wake test starting" : firstCycle ? "Your first sleep &amp; wake cycle" : "Test sleep &amp; automatic wake"}</h2><p>${esc(data.checks.message)}</p><p class="muted">${esc(data.checks.action)}</p>${testGuide}${returnGuide}<details data-detail="pi-checks"><summary>Pi check details</summary><ul class="checks">${(data.checks.items || []).map(item => `<li>${item.ok ? "✓" : "○"} ${esc(item.label)} — ${esc(item.detail)}</li>`).join("")}</ul>${data.checks.details ? `<pre class="preview">${esc(JSON.stringify(data.checks.details, null, 2))}</pre>` : ""}</details><div class="actions">${button("check", "Check again", "", this.blocked)}${data.checks.can_prepare ? button("prepare", "Prepare this Pi", "primary", this.blocked) : ""}${data.checks.needs_reboot ? button("reboot-now", "Reboot Pi", "danger", this.blocked || data.keep_awake) : ""}${data.checks.ok && !returning ? button("test", this.ready ? "Run test again" : "Start ten-minute sleep &amp; wake test", "primary", this.blocked || data.keep_awake) : ""}${returning ? button("confirm-test", "Yes, it returned by itself", "primary", this.blocked) + button("reject-test", "No / I'm not sure", "", this.blocked) : ""}</div>`;
      return `<div class="body"><div class="setup-nav">${button("close-panel", "Back to dashboard")}</div><div class="steps">${["Permissions", "Pi checks", "Wake test"].map((text, index) => `<span class="${index === stage ? "current" : ""}">${index < stage ? "✓" : index + 1} ${text}</span>`).join("")}</div>${content}${!this.ready ? `<p class="notice">Scheduling is off or paused until the wake test passes.</p>` : ""}${this.admin ? `<p class="hint muted">${link(this.appUrl(), "Setup & maintenance ↗")} · Connection repair and support details.</p>` : ""}</div>`;
    }
    metricBody() {
      const data = this.state;
      if (this.kind === "status") { const hours = Math.floor((data.uptime_seconds || 0) / 3600), days = Math.floor(hours / 24); return this.heading() + `<div class="metric"><button type="button" class="symbol power-switch" data-action="toggle-keep-awake" aria-label="${data.keep_awake ? "Resume all shutdowns" : "Suspend all shutdowns"}" aria-pressed="${Boolean(data.keep_awake)}" ${this.pauseBlocked ? "disabled" : ""}>${icon(icons.status)}</button><div>${badge(data.keep_awake ? "Keep awake on" : this.ready ? "Ready" : "Needs attention", data.keep_awake || !this.ready ? "warn" : "ok")}<p class="muted">Uptime</p><div class="uptime">${days ? days + (days === 1 ? " day, " : " days, ") : ""}${hours % 24} ${hours % 24 === 1 ? "hour" : "hours"}</div></div></div><p class="hint muted">${data.keep_awake ? "All app shutdowns suspended. Select the power icon to resume." : "Select the power icon to Keep awake and suspend all app shutdowns."}</p>`; }
      const epoch = this.kind === "shutdown" ? data.next_sleep_epoch : data.next_wake_epoch;
      const active = data.schedule_active && epoch;
      const reason = data.keep_awake ? "Keep awake on" : !data.schedule.enabled ? "Scheduling is off" : !this.ready ? "Complete Pi setup" : !data.calendar.ok ? "Calendar needs attention" : data.recovery.calendar_paused ? "Paused during UPS recovery" : "No upcoming off period";
      return this.heading() + `<div class="metric"><div class="symbol">${icon(icons[this.kind])}</div><div><div class="big">${active ? esc(this.time(epoch, true)) : "—"}</div><div class="sub">${active ? esc(this.day(epoch)) : esc(reason)}</div>${active ? `<small>${esc(this.relative(epoch))} · ${esc(data.schedule.timezone)}</small>` : ""}</div></div>`;
    }
    calendarBody() {
      const data = this.state, selected = data.schedule.calendar_entity_id, label = data.calendar.calendars.find(item => item.entity_id === selected)?.name || selected;
      if (!selected) return this.heading(badge("No calendar selected", "warn")) + `<div class="metric"><div class="symbol">${icon("calendar")}</div><p>Keep your sleep and wake dates in Home Assistant.</p></div><div class="actions">${button("create-calendar", "Create Pi Sleep calendar", "primary full", this.blocked)}</div><div class="actions">${button("choose-calendar", "Choose existing calendar", "full", this.blocked)}</div><p class="hint muted">Creating a calendar leaves scheduling off.</p>`;
      const periods = data.calendar.periods.filter(item => item.end_epoch > data.current_epoch).slice(0, 3);
      return `<div class="heading"><h2>${esc(this.config.title || label)}</h2>${badge(data.keep_awake ? "Paused · Keep awake" : data.schedule_active ? "Enabled" : data.schedule.enabled ? "Paused" : "Ready — off", data.schedule_active ? "ok" : data.keep_awake || data.schedule.enabled ? "warn" : "")}</div>${periods.map(item => `<div class="row">${icon("calendar")}<div>${button("calendar-event:" + esc(item.key), esc(this.day(item.start_epoch)) + " · " + esc(item.title) + " ↗", "event-link")}</div><div class="end dates">${esc(this.time(item.start_epoch))}<br>→ ${item.power_action === "stop" ? "Final stop · no timed wake" : esc(this.time(item.end_epoch))}</div></div>`).join("")}${!periods.length || !data.calendar.ok ? `<p class="muted">${esc(data.calendar.message)} ${esc(data.calendar.action)}</p>` : ""}<div class="actions calendar-actions">${link("/calendar", "Open Calendar ↗")}${button("choose-calendar", "Change calendar", "", this.blocked)}</div><div class="calendar-footer">${button("toggle-scheduling", data.schedule.enabled ? "Turn scheduling off" : "Enable scheduling", data.schedule.enabled ? "" : "primary", this.blocked || (!data.schedule.enabled && (!this.ready || !data.calendar.ok)))}<p class="hint muted">Event start = shutdown. Event end = wake. ${esc(data.schedule.timezone)}.</p></div>`;
    }
    upsBody() {
      const data = this.state, source = data.ups.selected, recovery = data.recovery, runtime = data.ups.runtime || {seconds: null, state: "unavailable", message: "Check the UPS runtime reading."};
      if (!source) return this.heading(badge("Optional")) + `<div class="metric"><div class="symbol">${icon("battery")}</div><p>Find your UPS and check its readings.</p></div><div class="actions">${button("scan-ups", "Find my UPS", "", this.blocked)}${button("choose-ups", "Choose UPS", "", this.blocked)}</div><p class="hint muted">Automatic protection off. Connect your UPS to Home Assistant, then find it here.</p>${data.ups.sources.length ? "" : `<p class="hint muted">No UPS found. Check the Network UPS Tools integration in Devices & services, then select Find my UPS. ${link("/config/integrations/dashboard", "Open Devices & services ↗")}</p>`}`;
      const battery = source.ok && source.battery_percent != null ? source.battery_percent + "%" : "—";
      const power = {mains: "Utility power", battery: "On battery", off: "Output off", unknown: "Unknown"}[source.power_state] || "Unknown";
      const sensors = data.ups.sensor_settings.sensors.filter(item => source.id === "nut:" + item.device_id && (item.can_enable || item.disabled_by != null));
      const protectedNow = recovery.emergency_active || recovery.eligible;
      return this.heading(badge(data.keep_awake ? "Protection suspended" : source.ok ? protectedNow ? "Protection enabled" : "Monitoring only" : "Needs attention", source.ok && protectedNow ? "ok" : "warn")) + `<p>${source.power_state === "mains" && source.ok ? '<span class="dot"></span>' : ""}${esc(power)} · ${esc(source.name)}</p><div class="battery">${icon("battery")}<div><div class="big">${esc(battery)}</div><span class="muted">Charge</span></div></div><div class="row">${icon("timer-outline")}<div><span class="muted">Estimated runtime</span><strong>${runtime.seconds != null ? Math.floor(runtime.seconds / 60) + " min" : esc({disabled: "Battery runtime disabled", stale: "Runtime reading stale", choose: "Choose runtime reading", missing: "Runtime not available", unavailable: "Runtime sensor unavailable"}[runtime.state] || "Runtime not available")}</strong></div></div><p class="hint muted">${esc(runtime.message)}</p>${!source.ok ? `<p class="notice">${esc(source.message)}</p>` : ""}<div class="actions">${button("choose-ups", "Change UPS", "", this.blocked)}${button("configure-protection", recovery.settings.enabled ? "Protection settings" : "Set up protection", "", this.blocked)}</div>${sensors.length ? `<details data-detail="nut-readings"><summary>Enable additional NUT readings (${sensors.length})</summary>${sensors.map(item => `<div class="row"><span>${esc(item.name)}${!item.can_enable ? " · enable its device or integration first" : ""}</span>${button("enable-sensor:" + esc(item.entity_id), "Enable", "", this.blocked || !item.can_enable || source.power_state !== "mains" || recovery.phase !== "idle")}</div>`).join("")}</details>` : ""}${source.readings?.length ? `<details data-detail="ups-readings"><summary>Active UPS readings</summary><ul class="activity">${source.readings.map(item => `<li>${esc(item.name)}: ${esc(item.value)}${item.unit ? " " + esc(item.unit) : ""}</li>`).join("")}</ul></details>` : ""}<p class="hint muted">${button("scan-ups", "Refresh UPS readings", "", this.blocked)}${source.id.startsWith("nut:") ? " · " + link("/config/devices/device/" + encodeURIComponent(source.id.slice(4)), "Open UPS device ↗") : ""}</p><details data-detail="ups-protection-state"><summary>Protection status</summary><p>${esc(recovery.message)}${recovery.notifications_ok ? "" : " The Home Assistant recovery notification could not be updated."}</p><p class="hint">Saved policy: ${recovery.settings.enabled ? "enabled" : "off"}. Emergency protection: ${data.keep_awake ? "suspended · Keep awake" : recovery.emergency_active ? "active" : "off / needs review"}. Timed retries: ${recovery.eligible ? "available when reserve permits" : "off / paused"}.</p><p class="hint">Attempts this outage: ${recovery.attempts} / ${recovery.settings.max_retries}. Next conditional interval: ${recovery.next_retry_minutes} minutes.${recovery.next_wake_epoch ? " Calendar wake: " + esc(this.time(recovery.next_wake_epoch)) + "." : ""}</p>${recovery.settings.enabled && !["idle", "paused", "stopped", "submitted"].includes(recovery.phase) ? button("pause-rtc-retries", "Pause timed retries for this outage", "", this.blocked) : ""}</details>${recovery.calendar_paused ? `<p class="outage">${esc(recovery.message || "UPS recovery is active. Calendar shutdowns are paused.")}</p>` : ""}`;
    }
    controlsBody() {
      const data = this.state, countdown = data.pending;
      const explanation = data.keep_awake ? "All shutdowns and reboots from this app are suspended, including emergency UPS shutdowns. Keep awake stays on until you resume. Calendar dates and settings are kept. Monitoring and messages continue."
        : "Keep awake suspends all app shutdowns until you resume, including future Calendar dates and emergency UPS shutdowns.";
      return this.heading(badge(data.keep_awake ? "Keep awake on" : "Saved settings active", data.keep_awake ? "warn" : "")) + `${data.keep_awake ? '<p class="notice"><strong>All app shutdowns suspended · UPS shutdown protection suspended</strong></p>' : `<p class="muted">Calendar scheduling ${data.schedule_active ? "enabled" : data.schedule.enabled ? "paused" : "off"}.</p>`}${countdown ? `<p class="progress"><strong>${countdown.emergency ? "Emergency shutdown" : "Shutdown countdown"}</strong><br>${countdown.remaining_seconds} seconds remaining${countdown.wake_epoch ? " · Wake " + esc(this.time(countdown.wake_epoch)) : " · No timed wake"}</p>` : ""}<div class="actions">${button("toggle-keep-awake", data.keep_awake ? "Resume shutdowns" : "Keep awake", "primary", this.pauseBlocked)}${button("reboot-now", icon("restart") + " Reboot Pi", "danger", this.blocked || data.keep_awake || !data.host_shutdown_supported)}</div><p class="hint muted">${esc(explanation)}</p>${data.keep_awake && data.message?.error ? `<p class="notice error-notice">${esc(data.message.text)} ${esc(data.message.action)}</p>` : ""}`;
    }
    messagesBody() {
      const info = this.state.messages, saved = info.settings;
      if (!saved.recipient) return this.heading(badge("Optional")) + `<div class="metric"><div class="symbol">${icon("cellphone")}</div><div><p>Send wake updates and your chosen readings to your phone.</p><p class="hint muted">First connect the Home Assistant Companion app on your phone and allow notifications.</p></div></div><div class="actions">${button("choose-phone", this.waitingForMessages ? "Finding phones and readings…" : "Choose phone", "", this.blocked || info.busy || this.waitingForMessages)}</div><p class="hint muted">Automatic messages off.</p>`;
      return this.heading(badge(saved.enabled ? "Enabled" : "Ready — off", saved.enabled ? "ok" : "")) + `<p>Uptime, next shutdown and wake, plus ${saved.fields.length} chosen reading${saved.fields.length === 1 ? "" : "s"}.</p><p class="hint muted">${esc(info.result?.message || "Test delivery before enabling automatic wake messages.")}</p><div class="actions">${button("send-message", "Send status now", "primary", this.blocked || info.busy)}${button("choose-phone", "Settings", "", this.blocked || info.busy)}${button("preview-saved-message", "Preview", "", this.blocked || info.busy)}</div>${info.preview ? `<details data-detail="message-preview"><summary>Message preview</summary><pre class="preview">${esc(info.preview.message || info.preview.body || "")}</pre></details>` : ""}`;
    }
    devicesBody() {
      const info = this.state.wake_devices;
      if (!info) return this.heading() + '<p class="muted">Update the app to use this card.</p>';
      const saved = info.settings, run = info.last_run || {}, labels = {waiting: "Waiting", checking: "Checking…", online: "Reachable", submitted: "Requested", unconfirmed: "Not confirmed", not_reachable: "Not confirmed", unavailable: "Needs attention"};
      const rows = saved.devices.map(target => { const outcome = run.devices?.find(row => row.entity_id === target.entity_id); return `<div class="row">${icon("desktop-tower-monitor")}<div><strong>${esc(target.name)}</strong><small>${esc(outcome?.message || "Ready to send a wake request.")}</small></div><div class="end">${badge(outcome ? labels[outcome.state] || "Not confirmed" : "Ready", outcome?.state === "online" ? "ok" : ["unconfirmed", "not_reachable", "unavailable"].includes(outcome?.state) ? "warn" : "")}</div></div>`; }).join("");
      return this.heading(badge(saved.enabled ? "Automatic waking on" : saved.devices.length ? "Automatic waking off" : "Optional", saved.enabled ? "ok" : "")) + `<p class="hint muted">Pi wakes through RTC → Home Assistant starts → Selected devices wake.</p>${rows || '<div class="metric"><div class="symbol">' + icon("lan-connect") + '</div><p>Wake compatible computers using your Home Assistant Wake on LAN buttons.</p></div>'}${info.busy ? `<p class="progress" role="status">${esc(info.busy)}</p>` : `<p class="hint ${info.result?.error ? "notice" : "muted"}" role="status">${esc(info.result?.message || "")}${info.result?.action ? " " + esc(info.result.action) : ""}</p>`}${run.at ? `<small>Last run: ${esc(this.time(run.at))} · ${esc(run.trigger)}. Reachability is checked at that time.</small>` : ""}<div class="actions">${saved.devices.length ? button("wake-devices", "Wake selected", "primary", this.blocked || info.busy || !info.history_ok) : ""}${button("choose-wake-devices", saved.devices.length ? "Settings" : "Choose devices", "", this.blocked || info.busy || this.refreshingDevices)}</div><p class="hint muted">${saved.enabled ? saved.after_every_boot ? "After every Pi boot" : "After a recorded Calendar wake" : "Automatic waking stays off until enabled"}${saved.require_mains && saved.devices.length ? " · Utility power required" : ""}. A wake request does not guarantee the target starts.</p>`;
    }
    wakeDevicePanel() {
      const draft = this.wakeDraft, options = this.wakeOptions, chosen = new Map(draft.devices.map(row => [row.entity_id, row]));
      const rows = [...options.devices, ...draft.devices.filter(row => !options.devices.some(option => option.entity_id === row.entity_id))];
      return `<h3>Choose devices to wake</h3><p class="hint muted">Set up each computer with Home Assistant's Wake on LAN integration. Enable wake support on the computer itself.</p><div class="actions">${link("/config/integrations/dashboard/add?domain=wake_on_lan", "Add Wake on LAN device ↗")}${link("/config/integrations/dashboard/add?domain=ping", "Add Ping online check ↗")}${button("refresh-wake-devices", "Find devices", "", this.blocked || this.state.wake_devices.busy || this.refreshingDevices)}</div><div class="fields">${rows.map(row => { const selected = chosen.get(row.entity_id), actual = selected || row, available = options.devices.some(option => option.entity_id === row.entity_id && option.identity === actual.identity); const pings = selected?.online_entity_id && !options.pings.some(item => item.entity_id === selected.online_entity_id) ? [{entity_id: selected.online_entity_id, identity: selected.online_identity, name: "Saved Ping sensor (unavailable)"}, ...options.pings] : options.pings; return `<div data-wake-row="${esc(row.entity_id)}"><label class="toggle"><input type="checkbox" data-wake-device="${esc(row.entity_id)}" ${selected ? "checked" : ""}><span>${esc(row.name)}<small>${esc(row.area || row.entity_id)}${available ? "" : " · Saved device changed or unavailable; remove and choose it again."}</small></span></label><label class="hint">Online check for ${esc(row.name)}<select data-wake-ping="${esc(row.entity_id)}" aria-label="Online check for ${esc(row.name)}"><option value="">No online check</option>${pings.map(ping => `<option value="${esc(ping.entity_id)}" ${selected?.online_entity_id === ping.entity_id ? "selected" : ""}>${esc(ping.name)}</option>`).join("")}</select></label></div>`; }).join("") || '<p class="muted">No Wake on LAN buttons found. Add the integration above, then select Find devices.</p>'}</div><h3>When to wake</h3>${check("enabled", "Enable automatic waking", draft.enabled)}${check("after_scheduled_wake", "After a scheduled Calendar wake", draft.after_scheduled_wake)}${check("after_every_boot", "After every Pi boot", draft.after_every_boot)}${check("require_mains", "Only wake on utility power", draft.require_mains)}<p class="hint muted">Utility power uses the UPS selected on your UPS card and requires a fresh reading from this Pi boot. ${!this.state.ups.settings.source_id ? "Choose a UPS or turn this option off." : ""}</p><details data-detail="wake-device-timing"><summary>Timing</summary><div class="form-grid"><label>Startup delay (seconds)<input name="delay_seconds" type="number" min="30" max="600" value="${draft.delay_seconds}" required></label><label>Wait for online check (seconds)<input name="check_timeout_seconds" type="number" min="15" max="300" value="${draft.check_timeout_seconds}" required></label></div></details><p class="hint muted">Save does not wake any devices. Automatic waking begins with the next Pi boot. One request per device; uncertain requests are not repeated automatically. Dates stay in Calendar. Up to 12 devices.</p><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save device settings</button></div>`;
    }
    wakeDevicePayload(form) {
      const saved = this.wakeDraft, selected = new Map(saved.devices.map(row => [row.entity_id, row]));
      const devices = [...form.querySelectorAll("[data-wake-device]:checked")].map(box => {
        const id = box.dataset.wakeDevice, old = selected.get(id), row = old || this.wakeOptions.devices.find(item => item.entity_id === id);
        const pingId = form.querySelector(`[data-wake-ping="${id}"]`).value || null;
        const ping = this.wakeOptions.pings.find(item => item.entity_id === pingId);
        return {entity_id: id, identity: row.identity, name: row.name, online_entity_id: pingId,
          online_identity: pingId ? old?.online_entity_id === pingId ? old.online_identity : ping?.identity : null};
      });
      return {devices, ...Object.fromEntries(["enabled", "after_scheduled_wake", "after_every_boot", "require_mains"].map(key => [key, form.querySelector(`[name="${key}"]`).checked])), delay_seconds: Number(form.querySelector('[name="delay_seconds"]').value), check_timeout_seconds: Number(form.querySelector('[name="check_timeout_seconds"]').value)};
    }
    async openWakeDevices(refresh = false) {
      if (this.blocked || this.state.wake_devices.busy || this.refreshingDevices) return;
      const form = this.panel === "devices" ? this.shadowRoot.querySelector("form") : null;
      this.wakeDraft = form ? this.wakeDevicePayload(form) : structuredClone(this.state.wake_devices.settings);
      const wasDirty = this.dirty;
      this.refreshingDevices = true;
      try {
        if (refresh || !this.state.wake_devices.options_revision) {
          if (!await this.call("scan-wake-devices")) return;
          for (let attempt = 0; this.state.wake_devices.busy && attempt < 40; attempt++) {
            await new Promise(resolve => setTimeout(resolve, 500));
            if (!this.isConnected || form && this.shadowRoot.querySelector("form") !== form) return;
            await this.feed.refresh();
          }
          if (this.state.wake_devices.busy) throw new Error("Device discovery is still running. Try Choose devices again when it finishes.");
          if (this.state.wake_devices.result?.error) throw new Error([this.state.wake_devices.result.message, this.state.wake_devices.result.action].filter(Boolean).join(" "));
        }
        const options = await this._hass.callWS({type: DOMAIN + "/wake_device_options", entry_id: this.config.entry_id || ""});
        if (!this.isConnected || form && this.shadowRoot.querySelector("form") !== form) return;
        this.wakeOptions = options; this.panel = "devices"; this.dirty = form ? wasDirty : false; this.message = ""; this.render();
      } catch (error) { this.message = error.message || "Update / reconnect dashboard in Setup & maintenance, then restart Home Assistant if requested."; if (form) form.querySelector(".form-feedback").textContent = this.message; else this.render(); }
      finally { this.refreshingDevices = false; if (this.panel === "devices") this.disableForm(this.blocked); else this.render(); }
    }
    assistBody() {
      const info = this.state.assist, saved = info.settings;
      return this.heading(badge(saved.enabled ? saved.allow_requests ? "Changes require approval" : "Status only" : "Optional", saved.enabled ? "ok" : "")) + `<div class="metric"><div class="symbol">${icon("message-text-outline")}</div><p>Ask about your Pi and its shutdown and wake times.</p></div><div class="actions">${saved.enabled ? button("configure-assist", "Assist settings", "", this.blocked) : button("connect-assist", "Connect Assist", "", this.blocked)}</div><p class="hint muted">${saved.enabled ? "Select Assist in your AI agent's Control Home Assistant setting." : "AI access and change requests are off."}</p>${saved.enabled ? `<details data-detail="agent-setup"><summary>Agent setup</summary><p>Open your AI integration, such as Ollama. Choose Assist under Control Home Assistant. Ask: “When will the Pi shut down and wake?”</p>${link("/config/integrations/dashboard", "Open Devices & services ↗")}</details>` : ""}${info.requests.map(item => `<div class="notice"><strong>${esc(item.summary)}</strong><div class="actions">${button("approve:" + esc(item.id), "Review and approve", "", this.blocked || item.submitted)}${button("dismiss:" + esc(item.id), "Dismiss", "", this.blocked || item.submitted)}</div></div>`).join("")}`;
    }
    activityBody() { return `<details data-detail="activity"><summary>${esc(this.config.title || names.activity)}</summary><ul class="activity">${this.state.dashboard.activity.map(item => `<li>${esc(item.text)}<small>${esc(this.time(item.time))}</small></li>`).join("") || '<li class="muted">Activity will appear here as you set up and use your Pi.</li>'}</ul><p class="hint muted">App ${esc(this.state.version)}</p>${button("restore-cards", "Restore default Pi cards", "", this.blocked)}</details>`; }
    protectionBody() {
      const data = this.state, saved = this.protectionDraft, source = data.ups.selected, typed = source?.id.startsWith("hook:"), owner = data.ups.shutdown_controller;
      const field = key => { const [label, min, max] = recoveryFields[key]; return `<label>${esc(label)}<input name="${key}" type="number" min="${min}" max="${max}" step="1" value="${saved[key]}" required></label>`; };
      const candidates = source?.runtime_candidates || [];
      const choices = saved.runtime_entity_id && !candidates.some(item => item.entity_id === saved.runtime_entity_id) ? [...candidates, {entity_id: saved.runtime_entity_id, name: "Saved runtime reading (currently unavailable)"}] : candidates;
      return `<h3>UPS protection settings</h3><p class="hint muted">Monitoring stays on independently. Automatic protection can shut down this Home Assistant Pi during an outage. Retry wake dates are stored in your selected Home Assistant Calendar.</p>${data.keep_awake ? '<p class="notice">Keep awake is on. Saving these settings will keep all app shutdowns suspended until you resume.</p>' : ""}<div class="guide"><strong>Who shuts down this Pi?</strong><p class="hint">${esc(owner.message)}</p>${owner.addon_id ? link("/config/app/" + encodeURIComponent(owner.addon_id) + "/config", "Open NUT app settings ↗") : ""}<p class="hint muted">For timed retries, turn off NUT's Host shutdown option and restart NUT. Review other host-shutdown automations/controllers too. This app keeps NUT's settings unchanged.</p></div>
      ${check("retry_enabled", "Allow timed RTC retries during an outage", saved.retry_enabled)}
      ${check("emergency_enabled", "Keep emergency low-battery protection active when retries are paused", saved.emergency_enabled)}
      <p class="hint muted">Pausing timed retries keeps emergency protection active if enabled. Keep awake suspends every app shutdown.</p>
      <label>Remaining-runtime reading<select name="runtime_entity_id"><option value="">${typed ? "Provided by this power hook" : "Choose Battery runtime"}</option>${choices.map(item => `<option value="${esc(item.entity_id)}" ${saved.runtime_entity_id === item.entity_id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label>
      <p class="hint muted">${typed ? "This hook supplies a typed remaining-runtime estimate." : "Choose the remaining Battery runtime measurement. Enable a disabled reading from the UPS card first. A low-runtime setpoint or startup/shutdown delay is a different reading."}</p>
      <div class="form-grid" data-retries>${field("shutdown_runtime_minutes")}${field("first_retry_minutes")}</div>
      <div class="retry-plan" data-retries><strong>Runtime required at each retry decision</strong><table><thead><tr><th>Retry</th><th>Off interval</th><th>Minimum estimated runtime</th></tr></thead><tbody data-requirements></tbody></table><p class="hint muted" data-feasibility></p></div>
      <details data-detail="ups-protection-advanced"><summary>Advanced recovery settings</summary><div class="form-grid"><div data-retries>${field("max_retry_minutes")}</div><div data-retries>${field("max_retries")}</div><div data-retries>${field("retry_reserve_minutes")}</div>${field("min_charge_percent")}${field("boot_grace_minutes")}${field("emergency_runtime_minutes")}${field("stable_power_minutes")}</div><div data-retries>${check("early_shutdown", "Also shut down early to conserve battery", saved.early_shutdown)}${field("outage_delay_minutes")}<p class="hint muted">Intervals double up to your maximum. Runtime must cover the wait, boot allowance, and reserve. An estimate cannot guarantee that UPS power lasts.</p></div></details>
      ${check("owner_confirmed", "I have reviewed shutdown ownership. If I changed NUT's Host shutdown option, I restarted NUT. Other controllers will not shut down this Pi independently during timed retries.", saved.owner_confirmed)}
      <div data-retries>${check("supply_confirmed", "I have confirmed a wake test on this UPS supply path, and the UPS keeps supplying the Pi while it is off.", saved.supply_confirmed)}</div>
      ${check("final_shutdown_confirmed", "I understand that low reserve, exhausted retries, or lost readings can cause a final shutdown without a timed wake. Restart may require restored UPS output, a power cycle, or the Pi's power button.", saved.final_shutdown_confirmed)}
      ${check("enabled", "Enable automatic UPS protection", saved.enabled)}
      <p class="hint muted" data-enable-help></p><p class="hint muted" data-draft-help>Unsaved changes do not change your saved policy.</p>
      <div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save UPS protection</button></div>`;
    }
    protectionPayload(form) {
      const read = key => form.querySelector(`[name="${key}"]`);
      const payload = {runtime_entity_id: read("runtime_entity_id").value || null, expected_source_id: this.protectionTargets.source_id, expected_calendar_entity_id: this.protectionTargets.calendar_id};
      for (const key of Object.keys(recoveryFields)) payload[key] = Number(read(key).value);
      for (const key of recoveryFlags) payload[key] = read(key).checked;
      return payload;
    }
    updateProtectionForm() {
      const form = this.shadowRoot.querySelector("form");
      if (!form || this.panel !== "protection") return;
      const payload = this.protectionPayload(form), data = this.state, source = data.ups.selected, blocked = this.blocked;
      for (const element of form.querySelectorAll("input,select,button")) if (element.dataset.action !== "close-panel") element.disabled = blocked;
      form.querySelector('[name="runtime_entity_id"]').disabled = blocked || Boolean(source?.id.startsWith("hook:"));
      form.querySelector('[name="outage_delay_minutes"]').disabled = blocked || !payload.early_shutdown;
      for (const element of form.querySelectorAll("[data-retries]")) element.hidden = !payload.retry_enabled;
      const reason = !source ? "Choose the UPS supplying this Pi first." : !data.host_shutdown_supported ? "Use Check again in Pi setup before enabling protection." : payload.retry_enabled && !this.ready ? "Complete Pi setup and confirm a wake test before enabling timed retries." : payload.retry_enabled && !data.schedule.calendar_entity_id ? "Choose a Calendar on the Calendar card before enabling timed retries." : "";
      form.querySelector('[name="enabled"]').disabled = blocked || Boolean(!data.recovery.settings.enabled && reason);
      form.querySelector("[data-enable-help]").textContent = reason;
      const changed = this.protectionTargets.source_id !== data.ups.settings.source_id || this.protectionTargets.calendar_id !== data.schedule.calendar_entity_id;
      form.querySelector("[data-draft-help]").textContent = changed ? "The selected UPS or Calendar changed while this form was open. Cancel and reopen protection settings before enabling protection. Your draft has not been saved." : this.dirty ? "Protection settings have unsaved changes. The saved policy remains active." : "Unsaved changes do not change your saved policy.";
      const count = Math.min(8, Math.max(0, payload.max_retries || 0)), overhead = payload.boot_grace_minutes + payload.retry_reserve_minutes + 1;
      const rows = Array.from({length: count}, (_, n) => { const interval = Math.min(payload.max_retry_minutes, payload.first_retry_minutes * 2 ** n); return {interval, minimum: interval + overhead}; });
      form.querySelector("[data-requirements]").innerHTML = rows.map((row, n) => `<tr><td>${n + 1}</td><td>${row.interval} min</td><td>${row.minimum} min</td></tr>`).join("");
      form.querySelector("[data-feasibility]").textContent = "Each attempt needs this much fresh estimated runtime at that decision, including boot and reserve allowances. " + (rows.some(row => row.minimum > payload.shutdown_runtime_minutes) ? `Your ${payload.shutdown_runtime_minutes}-minute shutdown threshold cannot normally fund the entire sequence at unchanged load. Later retries are conditional on the runtime reported after wake.` : "Intervals are conditional; reserve is checked again after every wake.");
    }
    async saveProtection(form) {
      const payload = this.protectionPayload(form), old = this.state.recovery.settings;
      if (old.enabled && old.emergency_enabled && (!payload.enabled || !payload.emergency_enabled)) {
        if (!await this.confirm("Disable emergency low-battery protection?", "The Pi may remain running until UPS power fails. Pausing a timed retry already keeps emergency protection active; this change disables that protection.", "Disable protection", true)) return;
        payload.confirmed_disable_emergency = true;
      }
      if (payload.enabled && (!old.enabled || !old.owner_confirmed || payload.retry_enabled && !old.retry_enabled) && !await this.confirm("Enable automatic UPS protection?", "This policy can shut down the Home Assistant Pi during an outage. RTC retries are conditional on fresh reserve and continuous UPS output. A final stop has no timed wake. Confirmations must reflect this supply path and the chosen host-shutdown controller.", "Enable UPS protection", true)) return;
      if (await this.call("recovery-settings", payload)) { this.panel = null; this.dirty = false; this.message = "UPS protection settings saved."; this.render(); }
    }
    panelBody() {
      const data = this.state;
      if (this.panel === "setup") return "";
      if (this.panel === "calendar") return `<h3>Choose a calendar</h3><label>Calendar for this Pi<select name="calendar_entity_id" required><option value="">Choose a calendar</option>${data.calendar.calendars.map(item => `<option value="${esc(item.entity_id)}" ${data.schedule.calendar_entity_id === item.entity_id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label><p class="hint muted">Changing calendars leaves scheduling off until you review and enable it.</p><label>Display time zone<input name="timezone" value="${esc(data.schedule.timezone)}" maxlength="100" required></label><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save calendar</button></div>`;
      if (this.panel === "ups") return `<h3>Choose the UPS supplying this Pi</h3><label>Power source<select name="source_id" required><option value="">Choose a UPS</option>${data.ups.sources.map(source => `<option value="${esc(source.id)}" ${data.ups.settings.source_id === source.id ? "selected" : ""}>${esc(source.name)} · ${esc(source.provider)}</option>`).join("")}</select></label>${check("notifications", "Show power notices in Home Assistant", data.ups.settings.notifications)}<label>Low battery notice threshold (%)<input type="number" name="low_battery_percent" min="5" max="95" value="${data.ups.settings.low_battery_percent}" required></label><p class="hint muted">Saving a UPS enables monitoring. Automatic shutdown protection is configured separately.</p><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save UPS</button></div>`;
      if (this.panel === "protection") return this.protectionBody();
      if (this.panel === "devices") return this.wakeDevicePanel();
      if (this.panel === "messages") { const saved = data.messages.settings, draft = this.messageDraft || saved; return `<h3>Phone and readings</h3><label>Send to phone<select name="recipient"><option value="">Choose a phone</option>${(!this.messageOptions.recipients.some(item => item.id === draft.recipient) && draft.recipient ? [{id: draft.recipient, name: "Saved phone (currently unavailable)"}, ...this.messageOptions.recipients] : this.messageOptions.recipients).map(item => `<option value="${esc(item.id)}" ${draft.recipient === item.id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label><p class="hint muted">Every message includes Pi uptime and the next shutdown and wake.</p>${!this.messageOptions.recipients.length ? `<p class="notice">No connected phone was found. Connect the Home Assistant Companion app on your phone, allow notifications, then select Find phones and readings. ${link("https://companion.home-assistant.io/docs/getting_started/", "Phone setup help ↗")}</p>` : ""}<div class="actions">${button("refresh-message-options", "Find phones and readings", "", this.blocked || data.messages.busy)}</div><label>Show readings<select name="category"><option value="suggested">Suggested readings</option><option value="all">All available readings</option>${[...new Set(this.messageOptions.fields.map(item => item.category))].filter(Boolean).sort().map(category => `<option value="${esc(category)}">${esc(category)}</option>`).join("")}</select></label><label>Find a reading<input name="search" type="search" placeholder="Battery, temperature, area…" maxlength="100"></label><div class="selected-fields"></div><div class="fields"></div>${check("enabled", "Send a message after this Pi starts", draft.enabled)}<p class="hint muted">Save and send a test message to check your phone. Automatic messages start with the next Pi boot.</p><div class="actions">${button("preview-message-draft", "Preview message", "", this.blocked || data.messages.busy)}</div><details class="draft-preview" data-detail="message-draft-preview" hidden><summary>Preview of the last requested draft</summary><pre class="preview"></pre></details><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save phone settings</button></div>`; }
      if (this.panel === "assist") return `<h3>Assist access</h3>${check("enabled", "Allow Assist to read Pi status", data.assist.settings.enabled)}${check("allow_requests", "Allow AI change requests for review", data.assist.settings.allow_requests)}<p class="hint muted">Change requests wait for approval here before dates are saved or the Pi is rebooted. Turning AI access off keeps the dashboard available.</p><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save Assist settings</button></div>`;
      return "";
    }
    render() {
      if (!this.config) return;
      for (const detail of this.shadowRoot.querySelectorAll("details[data-detail]")) this.detailsOpen.set(detail.dataset.detail, detail.open);
      if (this.previewRequested && this.state?.messages?.preview) { this.detailsOpen.set("message-preview", true); this.previewRequested = false; }
      let content;
      if (!this.state) content = `<div class="body">${this.heading()}<p class="muted">${esc(this.error || "Connecting to your Pi…")}</p></div>`;
      else if (this.kind === "setup") content = this.setupBody();
      else if (this.panel) content = `<div class="body settings-header">${this.heading()}</div>`;
      else content = `<div class="body">${["status", "shutdown", "wake"].includes(this.kind) ? this.metricBody() : this[this.kind + "Body"]()}</div>`;
      const notices = `${this.kind === "setup" && this.state?.storage_notice ? `<p class="notice error-notice">${esc(this.state.storage_notice)}</p>` : ""}${this.kind === "setup" && this.state?.migration_notice ? `<p class="notice">${esc(this.state.migration_notice)}</p>` : ""}${this.error ? `<p class="notice error-notice">${esc(this.error)} Displayed values may be out of date.</p>` : ""}${this.message && !this.panel ? `<p role="status" class="hint muted">${esc(this.message)}</p>` : ""}${this.state?.job && this.kind === "setup" ? `<p role="status" class="progress">${esc(this.state.job.label)}</p>` : ""}`;
      const panel = this.panel === "calendar-view" ? `<div class="body settings"><h3>Home Assistant Calendar</h3><p class="hint muted">Select the event, then Edit. Changes are saved in your selected calendar.</p><div class="native-calendar"></div><div class="actions">${button("close-panel", "Back to Pi dashboard")}${link("/calendar", "Open Calendar ↗")}</div><p class="form-feedback hint" role="status"></p></div>` : this.panel && this.panel !== "setup" ? `<form class="body settings">${this.panelBody()}<p class="form-feedback hint" role="status"></p></form>` : "";
      this.shadowRoot.innerHTML = `<style>${styles}</style><ha-card>${content}${notices ? `<div class="body">${notices}</div>` : ""}${panel}</ha-card>`;
      for (const detail of this.shadowRoot.querySelectorAll("details[data-detail]")) detail.open = this.detailsOpen.get(detail.dataset.detail) === true;
      for (const element of this.shadowRoot.querySelectorAll("[data-action]")) element.addEventListener("click", () => this.perform(element.dataset.action));
      const form = this.shadowRoot.querySelector("form");
      if (form) { form.addEventListener("input", () => { this.dirty = true; if (this.panel === "protection") this.updateProtectionForm(); }); form.addEventListener("submit", event => { event.preventDefault(); this.savePanel(form); }); }
      if (this.panel === "messages") { this.renderFields(); this.shadowRoot.querySelector('[name="search"]').addEventListener("input", () => this.renderFields()); this.shadowRoot.querySelector('[name="category"]').addEventListener("change", () => this.renderFields()); }
      if (this.panel === "protection") this.updateProtectionForm();
      if (this.panel === "devices") for (const box of this.shadowRoot.querySelectorAll("[data-wake-device]")) box.addEventListener("change", () => { if (!box.checked) this.wakeDraft.devices = this.wakeDraft.devices.filter(row => row.entity_id !== box.dataset.wakeDevice); });
      if (this.panel && this.panel !== "setup" && this.panel !== "calendar-view") this.disableForm(this.blocked);
    }
    async openMessages() {
      if (this.blocked) return;
      if (!this.state.messages.options_revision) {
        this.waitingForMessages = true;
        if (!await this.call("scan-messages")) { this.waitingForMessages = false; return; }
        if (!this.state.messages.busy && this.state.messages.options_revision) { this.waitingForMessages = false; await this.loadMessageOptions(); }
        else { this.message = "Finding phones and readings. The settings will open when discovery finishes."; this.render(); }
        return;
      }
      await this.loadMessageOptions();
    }
    async loadMessageOptions() {
      try { this.messageOptions = await this._hass.callWS({type: DOMAIN + "/message_options", entry_id: this.config.entry_id || ""}); this.messageDraft = structuredClone(this.state.messages.settings); this.panel = "messages"; this.dirty = false; this.render(); } catch (error) { this.message = error.message; this.render(); }
    }
    updateMessagePreview() {
      if (!this.awaitingDraftPreview || this.state.messages.busy) return;
      this.awaitingDraftPreview = false;
      const info = this.state.messages, preview = this.shadowRoot.querySelector(".draft-preview"), feedback = this.shadowRoot.querySelector(".form-feedback");
      if (!preview) return;
      if (info.result?.error) { if (feedback) feedback.textContent = [info.result.message, info.result.action].filter(Boolean).join(" "); return; }
      if (info.preview) { preview.hidden = false; preview.open = true; preview.querySelector("pre").textContent = info.preview.message || info.preview.body || ""; if (feedback) feedback.textContent = "Preview ready. Nothing was sent to your phone."; }
    }
    async refreshMessageOptions() {
      if (this.blocked || this.state.messages.busy || this.refreshingOptions) return;
      const form = this.shadowRoot.querySelector("form"), recipient = form.querySelector('[name="recipient"]').value;
      this.messageDraft = {...this.messageDraft, recipient: recipient || null, enabled: form.querySelector('[name="enabled"]').checked};
      const search = form.querySelector('[name="search"]').value, category = form.querySelector('[name="category"]').value;
      this.refreshingOptions = true;
      try {
        if (!await this.call("scan-messages")) return;
        for (let attempt = 0; attempt < 30; attempt++) {
          if (this.panel !== "messages" || this.shadowRoot.querySelector("form") !== form || !this.isConnected) return;
          await new Promise(resolve => setTimeout(resolve, 500));
          await this.feed.refresh();
          if (!this.state.messages.busy) {
            this.messageOptions = await this._hass.callWS({type: DOMAIN + "/message_options", entry_id: this.config.entry_id || ""});
            if (this.panel !== "messages" || this.shadowRoot.querySelector("form") !== form) return;
            this.refreshingOptions = false; this.render(); this.shadowRoot.querySelector('[name="search"]').value = search; this.shadowRoot.querySelector('[name="category"]').value = category; this.renderFields(); this.shadowRoot.querySelector(".form-feedback").textContent = "Phones and readings refreshed. Unsaved choices are kept.";
            return;
          }
        }
        form.querySelector(".form-feedback").textContent = "Discovery is still running. Try Find phones and readings again when it finishes. Your draft is kept.";
      } catch (error) { if (this.panel === "messages") this.shadowRoot.querySelector(".form-feedback").textContent = error.message; }
      finally { this.refreshingOptions = false; if (this.panel === "messages") this.disableForm(this.blocked); }
    }
    async openCalendar(key) {
      const period = this.state?.calendar?.periods.find(item => item.key === key), entity = this.state?.schedule?.calendar_entity_id;
      if (!period || !entity) return;
      const request = ++this.calendarRequest;
      this.panel = "calendar-view"; this.dirty = false; this.render();
      try {
        if (typeof window.loadCardHelpers !== "function") throw new Error("Open Calendar below to edit this event in Home Assistant.");
        const helpers = await window.loadCardHelpers();
        if (this.panel !== "calendar-view" || request !== this.calendarRequest || !this.isConnected) return;
        const widget = helpers.createCardElement({type: "calendar", entities: [entity], initial_view: "dayGridDay"});
        this.calendarWidget = widget; widget.hass = this._hass;
        this.shadowRoot.querySelector(".native-calendar").replaceChildren(widget);
        // Home Assistant owns event loading, permissions, recurrence, and editing.
        // Its current FullCalendar bridge can focus/open the selected occurrence.
        // If that bridge changes, the native calendar and Open Calendar link remain.
        let focused = false;
        for (let attempt = 0; attempt < 60 && this.panel === "calendar-view" && this.calendarWidget === widget; attempt++) {
          await new Promise(resolve => setTimeout(resolve, 100));
          if (this.panel !== "calendar-view" || this.calendarWidget !== widget || request !== this.calendarRequest || !this.isConnected) return;
          const native = widget.shadowRoot?.querySelector("ha-full-calendar"), api = native?.calendar;
          if (!api?.gotoDate || !api?.getEvents || !api?.getOption) continue;
          if (!focused) {
            api.gotoDate(new Date(period.start_epoch * 1000)); focused = true;
            native.dispatchEvent(new CustomEvent("view-changed", {detail: {start: api.view.activeStart, end: api.view.activeEnd, view: api.view.type}, bubbles: true, composed: true}));
          }
          const matches = api.getEvents().filter(event => event.extendedProps?.calendar === entity && event.start?.getTime() === period.start_epoch * 1000 && event.end?.getTime() === period.end_epoch * 1000);
          const open = api.getOption("eventClick");
          if (matches.length === 1 && typeof open === "function") { open({event: matches[0]}); return; }
        }
      } catch (error) {
        if (this.panel === "calendar-view") this.shadowRoot.querySelector(".form-feedback").textContent = error.message || "Open Calendar below to edit this event in Home Assistant.";
      }
    }
    renderFields() {
      const fieldBox = this.shadowRoot.querySelector(".fields"), selectedBox = this.shadowRoot.querySelector(".selected-fields"); if (!fieldBox) return;
      const query = this.shadowRoot.querySelector('[name="search"]').value.trim().toLocaleLowerCase();
      const selected = this.messageDraft.fields, category = this.shadowRoot.querySelector('[name="category"]').value || "suggested";
      const rows = this.messageOptions.fields.filter(item => query ? [item.name, item.area, item.category, item.id].join(" ").toLocaleLowerCase().includes(query) : category === "all" || category === "suggested" && item.suggested || category === item.category || selected.includes(item.id)).slice(0, 60);
      fieldBox.innerHTML = rows.map(item => `<label class="toggle"><input type="checkbox" data-field="${esc(item.id)}" ${selected.includes(item.id) ? "checked" : ""} ${!selected.includes(item.id) && selected.length >= 12 ? "disabled" : ""}><span>${esc(item.name)}<small>${esc([item.category, item.area, item.unit].filter(Boolean).join(" · "))}</small></span></label>`).join("") || '<p class="muted">No matching readings. Try a search.</p>';
      selectedBox.innerHTML = selected.map(id => `<button type="button" data-remove="${esc(id)}">${esc(this.messageOptions.fields.find(item => item.id === id)?.name || id)} ×</button>`).join("");
      for (const box of fieldBox.querySelectorAll("input")) box.addEventListener("change", () => { this.messageDraft.fields = box.checked ? [...this.messageDraft.fields, box.dataset.field] : this.messageDraft.fields.filter(id => id !== box.dataset.field); this.dirty = true; this.renderFields(); });
      for (const item of selectedBox.querySelectorAll("button")) item.addEventListener("click", () => { this.messageDraft.fields = this.messageDraft.fields.filter(id => id !== item.dataset.remove); this.dirty = true; this.renderFields(); });
    }
    async savePanel(form) {
      if (this.blocked) return;
      if (this.panel === "protection") { await this.saveProtection(form); return; }
      const values = new FormData(form), read = key => values.get(key), checked = key => form.querySelector(`[name="${key}"]`)?.checked === true;
      let action, payload;
      if (this.panel === "calendar") { action = "settings"; payload = {...this.state.schedule, calendar_entity_id: read("calendar_entity_id"), timezone: read("timezone").trim(), enabled: read("calendar_entity_id") === this.state.schedule.calendar_entity_id && this.state.schedule.enabled}; }
      if (this.panel === "ups") { action = "power-settings"; payload = {source_id: read("source_id") || null, notifications: checked("notifications"), low_battery_percent: Number(read("low_battery_percent"))}; }
      if (this.panel === "messages") { action = "message-settings"; payload = {recipient: read("recipient") || null, enabled: checked("enabled"), fields: [...this.messageDraft.fields]}; }
      if (this.panel === "devices") { action = "wake-device-settings"; payload = this.wakeDevicePayload(form); if (payload.enabled && !this.state.wake_devices.settings.enabled && !await this.confirm("Enable automatic device waking?", "From the next qualifying Pi boot, wake " + payload.devices.map(row => row.name).join(", ") + ". Utility-power and fresh-reading checks apply when selected.", "Enable waking")) return; }
      if (this.panel === "assist") { action = "assist-settings"; payload = {enabled: checked("enabled"), allow_requests: checked("enabled") && checked("allow_requests")}; }
      if (action && await this.call(action, payload)) { this.panel = null; this.dirty = false; this.message = "Settings saved."; this.render(); }
    }
  }

  class PiEditor extends HTMLElement {
    constructor() { super(); this.attachShadow({mode: "open"}); }
    setConfig(config) { this.config = {...config}; this.render(); }
    set hass(hass) { this._hass = hass; if (!this.entries) hass.callWS({type: DOMAIN + "/entries"}).then(entries => { this.entries = entries; this.render(); }).catch(() => { this.entries = []; this.render(); }); }
    render() { if (!this.config) return; this.shadowRoot.innerHTML = `<style>${styles}</style><label>Card title<input name="title" value="${esc(this.config.title || "")}" placeholder="Default title"></label><label>Pi integration<select name="entry_id"><option value="">Use the only connected Pi</option>${(this.entries || []).map(entry => `<option value="${esc(entry.entry_id)}" ${this.config.entry_id === entry.entry_id ? "selected" : ""}>${esc(entry.title)}</option>`).join("")}</select></label>`; for (const input of this.shadowRoot.querySelectorAll("input,select")) input.addEventListener("change", () => { this.config[input.name] = input.value; this.dispatchEvent(new CustomEvent("config-changed", {detail: {config: {...this.config}}, bubbles: true, composed: true})); }); }
  }
  if (!customElements.get("pi-wake-card-editor")) customElements.define("pi-wake-card-editor", PiEditor);
  window.customCards = window.customCards || [];
  for (const [kind, name] of Object.entries(names)) {
    const tag = "pi-wake-" + kind + "-card";
    if (customElements.get(tag)) continue;
    class Card extends PiCard { static kind = kind; static getConfigElement() { return document.createElement("pi-wake-card-editor"); } static getStubConfig() { return {entry_id: ""}; } }
    customElements.define(tag, Card);
    window.customCards.push({type: tag, name: "Pi Wake & Sleep · " + name, description: "Native Pi card. Move it, resize it, and add other Home Assistant cards alongside it.", preview: true});
  }
})();
