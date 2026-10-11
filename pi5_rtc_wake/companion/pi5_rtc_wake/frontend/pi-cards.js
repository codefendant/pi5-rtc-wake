/* Pi Wake & Sleep native Home Assistant cards. No external libraries or cloud calls. */
"use strict";
(() => {
  const DOMAIN = "pi5_rtc_wake";
  const names = {setup: "Pi setup", status: "Pi status", shutdown: "Next shutdown", wake: "Next wake", calendar: "Pi Sleep calendar", ups: "UPS power", controls: "Pi controls", messages: "Messages", assist: "Assist", activity: "Recent activity"};
  const icons = {setup: "shield-check-outline", status: "power", shutdown: "weather-night", wake: "white-balance-sunny", calendar: "calendar", ups: "battery", controls: "power-settings", messages: "cellphone", assist: "message-text-outline", activity: "history"};
  const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[character]));
  const icon = name => `<ha-icon icon="mdi:${esc(name)}"></ha-icon>`;
  const badge = (text, state = "") => `<span class="badge ${state}">${esc(text)}</span>`;
  const button = (action, text, style = "", disabled = false) => `<button type="button" data-action="${action}" class="${style}" ${disabled ? "disabled" : ""}>${text}</button>`;
  const link = (url, text) => `<a href="${esc(url)}">${text}</a>`;
  const check = (key, label, value, disabled = false) => `<label class="toggle"><input type="checkbox" name="${key}" ${value ? "checked" : ""} ${disabled ? "disabled" : ""}>${esc(label)}</label>`;
  const styles = `
    :host{display:block;scroll-margin-top:80px;color:var(--primary-text-color,#172033);font:14px/1.5 var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
    ha-card{display:block;border-radius:var(--ha-card-border-radius,12px);border:1px solid var(--divider-color,#dce3eb);box-shadow:var(--ha-card-box-shadow,none);background:var(--ha-card-background,var(--card-background-color,#fff));overflow:hidden}
    .power-switch{padding:0!important;border:2px solid transparent}.power-switch[aria-pressed="true"]{background:#fff0ce;color:#805600;border-color:#bd7d00}.power-switch:disabled{opacity:.5}.event-link{border:0;padding:0;min-height:0;text-align:left;justify-content:flex-start}.native-calendar{min-height:200px}
    .setup-nav{margin-bottom:16px}.setup-ready.needs-attention{background:#fff0ce;color:#805600}.setup-ready.needs-attention ha-icon{color:inherit}
    :host([dark]) .setup-ready.needs-attention{background:#4d3b12;color:#ffe3a1}
    .body{padding:20px 22px}.heading{display:flex;align-items:center;gap:10px;margin-bottom:16px}h2{font-size:18px;font-weight:600;margin:0;line-height:1.35}.heading>.badge{margin-left:auto}h3{font-size:16px;margin:12px 0}p{margin:10px 0}.muted,small{color:var(--secondary-text-color,#677386)}.hint{font-size:13px}.badge{display:inline-flex;align-items:center;gap:5px;border-radius:7px;padding:3px 9px;background:var(--secondary-background-color,#edf1f5);font-size:12px;white-space:nowrap}.badge.ok{background:#d4f2dd;color:#166534}.badge.warn{background:#fff0ce;color:#905700}.badge.error{background:#fbe1df;color:#a02620}
    .metric{display:flex;align-items:center;gap:20px}.metric .symbol{display:grid;place-items:center;width:76px;height:76px;flex-shrink:0;border-radius:50%;background:var(--pi-icon-background,#e5f7f9);color:#008595}.symbol ha-icon{--mdc-icon-size:44px}.big{font-size:35px;font-weight:700;line-height:1.3;letter-spacing:-.5px}.sub{font-size:16px}.uptime{font-size:19px;font-weight:600;margin-top:5px}
    button,a{font:inherit}button{min-height:42px;padding:9px 14px;border:1px solid var(--divider-color,#dce3eb);border-radius:8px;color:var(--primary-color,#008cff);background:transparent;cursor:pointer;font-weight:500;display:inline-flex;align-items:center;justify-content:center;gap:8px}button.primary{background:var(--primary-color,#008cff);border-color:var(--primary-color,#008cff);color:var(--text-primary-color,#fff)}button.danger{background:#e8242e;border-color:#e8242e;color:#fff}button:disabled{opacity:.48;cursor:default}.full{width:100%}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}.actions>*{flex:1}a{color:var(--primary-color,#008cff);text-decoration:none}a:hover{text-decoration:underline}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--primary-color,#008cff);outline-offset:3px}
    .row{display:flex;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--divider-color,#dce3eb)}.row:last-child{border-bottom:0}.row .end{margin-left:auto;text-align:right}.row .dates{font-size:13px}.row ha-icon{color:var(--primary-color,#008cff)}.row strong{display:block}.calendar-actions{padding-top:12px}.calendar-footer{margin-top:14px;padding-top:14px;border-top:1px solid var(--divider-color,#dce3eb)}.calendar-footer button{margin-top:8px}.dot{display:inline-block;width:12px;height:12px;border-radius:50%;background:#20a050;margin-right:8px}.battery{display:flex;gap:20px;align-items:center;margin:20px 0}.battery ha-icon{--mdc-icon-size:62px;color:#20a050}.setup-ready{color:var(--pi-ready-text,#166534);display:flex;align-items:center;gap:12px;padding:14px 20px;background:var(--pi-ready-background,#e8f7ef)}.setup-ready ha-icon{color:#199449}.setup-ready button{margin-left:auto;font-size:13px;border:0;min-height:30px}.setup-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:24px}.steps{display:flex;gap:12px;align-items:center;margin-bottom:20px}.steps span{color:var(--secondary-text-color,#677386)}.steps .current{color:var(--primary-color,#008cff);font-weight:600}.steps span+span:before{content:"›";margin-right:12px;color:var(--disabled-text-color,#a0a9b8)}.guide{border:1px solid var(--divider-color,#dce3eb);border-radius:12px;padding:16px;background:var(--secondary-background-color,#f6f8fb)}.guide .switch-row{border:2px solid #e8242e;border-radius:8px;padding:10px;display:flex;align-items:center;justify-content:space-between;gap:15px}.switch{width:44px;height:24px;border-radius:24px;background:var(--primary-color,#008cff);position:relative;flex-shrink:0}.switch:after{content:"";position:absolute;width:18px;height:18px;border-radius:50%;background:#fff;right:3px;top:3px}.guide small{display:block;margin-top:8px;color:#bc2028}.notice{border-radius:8px;padding:12px 14px;background:#fff0ce;color:#805600;margin:12px 0}.error-notice{background:var(--error-state-color,#fbe1df);color:var(--error-color,#b3261e)}.progress{padding:10px;border-left:3px solid var(--primary-color,#008cff);background:var(--secondary-background-color,#f2f5f9)}
    details{margin-top:12px}summary{cursor:pointer;color:var(--primary-color,#008cff)}.details-body{padding-top:14px}.settings{margin-top:20px;padding-top:16px;border-top:1px solid var(--divider-color,#dce3eb)}label{display:block;margin:12px 0;font-weight:500}input:not([type=checkbox]),select{box-sizing:border-box;display:block;width:100%;min-height:42px;border:1px solid var(--divider-color,#dce3eb);border-radius:8px;padding:9px 11px;margin-top:6px;background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--primary-text-color,#172033);font:inherit}.toggle{display:flex;gap:10px;align-items:flex-start;font-weight:400}.toggle input{width:19px;height:19px;flex-shrink:0;accent-color:var(--primary-color,#008cff)}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.fields{max-height:270px;overflow:auto;border:1px solid var(--divider-color,#dce3eb);border-radius:8px;padding:0 12px}.fields label{border-bottom:1px solid var(--divider-color,#dce3eb);padding-bottom:10px}.fields small{display:block;font-size:12px;font-weight:400}.selected-fields{display:flex;flex-wrap:wrap;gap:6px}.selected-fields button{font-size:12px;min-height:28px;padding:3px 8px}.preview{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;background:var(--secondary-background-color,#f5f7fa);padding:14px;border-radius:8px}.activity{list-style:none;padding:0;margin:0}.activity li{padding:9px 0;border-bottom:1px solid var(--divider-color,#dce3eb)}.activity small{display:block}.checks{padding-left:20px}.checks li{margin-bottom:5px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px;border-bottom:1px solid var(--divider-color,#dce3eb)}.outage{background:#fff0ce;color:#805600;padding:12px;border-radius:8px}.footer{margin-top:12px}
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
    constructor() { super(); this.attachShadow({mode: "open"}); this.state = null; this.error = ""; this.message = ""; this.panel = null; this.busy = false; this.dirty = false; this.setupDismissed = false; this.detailsOpen = new Map(); this.previewRequested = false; this.calendarWidget = null; this.calendarRequest = 0; }
    setConfig(config) { this.config = {...config}; this.unbind(); if (this.isConnected) this.bind(); this.render(); }
    set hass(hass) { this._hass = hass; if (this.calendarWidget) this.calendarWidget.hass = hass; this.toggleAttribute("dark", Boolean(hass.themes?.darkMode)); if (this.isConnected && !this.unsubscribe) this.bind(); }
    get kind() { return this.constructor.kind; }
    get admin() { return this._hass?.user?.is_admin === true; }
    get blocked() { return !this.admin || !this.state || Boolean(this.error) || this.busy || Boolean(this.state?.job || this.state?.pending || this.state?.shutdown_requested); }
    get pauseBlocked() { return !this.admin || !this.state || Boolean(this.error) || this.busy || Boolean(this.state?.shutdown_requested || this.state?.storage_notice); }
    connectedCallback() { this.bind(); this.render(); }
    disconnectedCallback() { this.unbind(); }
    unbind() { this.unsubscribe?.(); this.unsubscribe = null; }
    bind() { if (!this._hass || !this.config || this.unsubscribe) return; this.feed = feedFor(this._hass, this.config.entry_id || ""); this.unsubscribe = this.feed.add((state, error) => { const wasReady = this.ready; this.state = state; this.error = error; if (wasReady && !this.ready) this.setupDismissed = false; if ((!this.panel || this.panel === "setup") && !this.confirming) this.render(); }); }
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
    async call(action, payload = {}) { if (!this.admin || this.busy) return false; this.busy = true; this.message = ""; if (!this.panel || this.panel === "setup") this.render(); else this.disableForm(true); try { await this._hass.callWS({type: DOMAIN + "/action", entry_id: this.config.entry_id || "", action, payload}); await this.feed.refresh(); this.message = "Action accepted."; return true; } catch (error) { this.message = error.message || "This action could not finish. Refresh the dashboard and try again."; return false; } finally { this.busy = false; if (!this.panel || this.panel === "setup") this.render(); else { this.disableForm(false); const feedback = this.shadowRoot.querySelector(".form-feedback"); if (feedback) feedback.textContent = this.message; } } }
    disableForm(disabled) { for (const element of this.shadowRoot.querySelectorAll(".settings button,.settings input,.settings select")) element.disabled = disabled; }
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
      if (action === "close-panel") { if (this.dirty && !window.confirm("Discard your unsaved changes?")) return; this.panel = null; this.calendarWidget = null; this.dirty = false; this.message = ""; if (this.kind === "setup") this.setupDismissed = true; this.render(); if (this.kind === "setup") this.scrollIntoView({behavior: "smooth", block: "start"}); return; }
      if (action === "review-setup") { this.panel = "setup"; this.setupDismissed = false; this.render(); return; }
      if (action === "choose-calendar") { this.panel = "calendar"; this.dirty = false; this.render(); return; }
      if (action === "choose-ups") { this.panel = "ups"; this.dirty = false; this.render(); return; }
      if (action === "choose-phone") { await this.openMessages(); return; }
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
      if (action === "test") { if (await this.confirm("Run a ten-minute wake test?", "The Pi shuts down after a 30-second countdown. Home Assistant will be offline. Leave power connected. If it has not returned after 15 minutes, press the Pi power button. Scheduling and UPS recovery turn off for this test; review them afterward.", "Start wake test", true)) await this.call(action, {confirmed: true}); return; }
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
      if (!this.setupExpanded) return `<div class="setup-ready ${this.ready ? "" : "needs-attention"}">${icon(this.ready ? "check-circle" : "alert-circle-outline")}<strong>${this.ready ? "Pi ready · Wake test passed" : "Pi setup needs attention"}</strong>${button("review-setup", "Review setup")}</div>`;
      const stage = protectedMode !== false ? 0 : data.checks.ok ? 2 : 1;
      let content;
      if (stage === 0) content = `<div class="setup-grid"><div><h2>Allow access to your Pi</h2><p>${protectedMode === true ? "Turn off Protection mode on the app's Info page. Then restart the app." : "Check Protection mode on the app's Info page."}</p><ol><li>Stop the app</li><li>Turn Protection mode off</li><li>Start the app</li></ol><div class="actions">${link(this.infoUrl(), "Open app Info ↗")}${button("check", "Check again", "", this.blocked)}</div></div><div class="guide" aria-label="Illustration of the app Info page"><strong>Pi RTC Wakealarm — Info</strong><p class="muted">Stop → change setting → Start</p><div class="switch-row"><span>Protection mode</span><span class="switch" role="img" aria-label="Protection mode is on in this illustration"></span></div><small>Turn this switch off</small></div></div>`;
      else content = `<h2>${this.ready ? "Pi setup complete" : stage === 1 ? "Check this Pi" : data.test_status === "awaiting_confirmation" ? "Did Home Assistant return by itself?" : "Try a wake test"}</h2><p>${esc(data.checks.message)}</p><p class="muted">${esc(data.checks.action)}</p><details data-detail="pi-checks"><summary>Pi check details</summary><ul class="checks">${(data.checks.items || []).map(item => `<li>${item.ok ? "✓" : "○"} ${esc(item.label)} — ${esc(item.detail)}</li>`).join("")}</ul>${data.checks.details ? `<pre class="preview">${esc(JSON.stringify(data.checks.details, null, 2))}</pre>` : ""}</details><div class="actions">${button("check", "Check again", "", this.blocked)}${data.checks.can_prepare ? button("prepare", "Prepare this Pi", "primary", this.blocked) : ""}${data.checks.needs_reboot ? button("reboot-now", "Reboot Pi", "danger", this.blocked || data.keep_awake) : ""}${data.checks.ok && data.test_status !== "awaiting_confirmation" ? button("test", this.ready ? "Run test again" : "Run ten-minute test", "primary", this.blocked || data.keep_awake) : ""}${data.test_status === "awaiting_confirmation" ? button("confirm-test", "Yes, it returned by itself", "primary", this.blocked) + button("reject-test", "No / I'm not sure", "", this.blocked) : ""}</div>`;
      return `<div class="body"><div class="setup-nav">${button("close-panel", "Back to dashboard")}</div><div class="steps">${["Permissions", "Pi checks", "Wake test"].map((text, index) => `<span class="${index === stage ? "current" : ""}">${index < stage ? "✓" : index + 1} ${text}</span>`).join("")}</div>${content}${!this.ready ? `<p class="notice">Scheduling is off or paused until the wake test passes.</p>` : ""}</div>`;
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
      if (!source) return this.heading(badge("Optional")) + `<div class="metric"><div class="symbol">${icon("battery")}</div><p>Find your UPS and check its readings.</p></div><div class="actions">${button("scan-ups", "Find my UPS", "", this.blocked)}${button("choose-ups", "Choose UPS", "", this.blocked)}</div><p class="hint muted">Automatic protection off.</p>`;
      const battery = source.ok && source.battery_percent != null ? source.battery_percent + "%" : "—";
      const power = {mains: "Utility power", battery: "On battery", off: "Output off", unknown: "Unknown"}[source.power_state] || "Unknown";
      const sensors = data.ups.sensor_settings.sensors.filter(item => source.id === "nut:" + item.device_id && item.can_enable);
      const protectedNow = recovery.emergency_active || recovery.eligible;
      return this.heading(badge(data.keep_awake ? "Protection suspended" : source.ok ? protectedNow ? "Protection enabled" : "Monitoring only" : "Needs attention", source.ok && protectedNow ? "ok" : "warn")) + `<p>${source.power_state === "mains" && source.ok ? '<span class="dot"></span>' : ""}${esc(power)} · ${esc(source.name)}</p><div class="battery">${icon("battery")}<div><div class="big">${esc(battery)}</div><span class="muted">Charge</span></div></div><div class="row">${icon("timer-outline")}<div><span class="muted">Estimated runtime</span><strong>${runtime.seconds != null ? Math.floor(runtime.seconds / 60) + " min" : esc({disabled: "Battery runtime disabled", stale: "Runtime reading stale", choose: "Choose runtime reading", missing: "Runtime not available", unavailable: "Runtime sensor unavailable"}[runtime.state] || "Runtime not available")}</strong></div></div><p class="hint muted">${esc(runtime.message)}</p>${!source.ok ? `<p class="notice">${esc(source.message)}</p>` : ""}<div class="actions">${button("choose-ups", "Change UPS", "", this.blocked)}${link(this.appUrl("ups"), recovery.settings.enabled ? "Protection settings ↗" : "Set up protection ↗")}</div>${sensors.length ? `<details data-detail="nut-readings"><summary>Enable additional NUT readings (${sensors.length})</summary>${sensors.map(item => `<div class="row"><span>${esc(item.name)}</span>${button("enable-sensor:" + esc(item.entity_id), "Enable", "", this.blocked || source.power_state !== "mains")}</div>`).join("")}</details>` : ""}${recovery.calendar_paused ? `<p class="outage">${esc(recovery.message || "UPS recovery is active. Calendar shutdowns are paused.")}</p>` : ""}`;
    }
    controlsBody() {
      const data = this.state, countdown = data.pending;
      const explanation = data.keep_awake ? "All shutdowns and reboots from this app are suspended, including emergency UPS shutdowns. Keep awake stays on until you resume. Calendar dates and settings are kept. Monitoring and messages continue."
        : "Keep awake suspends all app shutdowns until you resume, including future Calendar dates and emergency UPS shutdowns.";
      return this.heading(badge(data.keep_awake ? "Keep awake on" : "Saved settings active", data.keep_awake ? "warn" : "")) + `${data.keep_awake ? '<p class="notice"><strong>All app shutdowns suspended · UPS shutdown protection suspended</strong></p>' : `<p class="muted">Calendar scheduling ${data.schedule_active ? "enabled" : data.schedule.enabled ? "paused" : "off"}.</p>`}${countdown ? `<p class="progress"><strong>${countdown.emergency ? "Emergency shutdown" : "Shutdown countdown"}</strong><br>${countdown.remaining_seconds} seconds remaining${countdown.wake_epoch ? " · Wake " + esc(this.time(countdown.wake_epoch)) : " · No timed wake"}</p>` : ""}<div class="actions">${button("toggle-keep-awake", data.keep_awake ? "Resume shutdowns" : "Keep awake", "primary", this.pauseBlocked)}${button("reboot-now", icon("restart") + " Reboot Pi", "danger", this.blocked || data.keep_awake || !data.host_shutdown_supported)}</div><p class="hint muted">${esc(explanation)}</p>${data.keep_awake && data.message?.error ? `<p class="notice error-notice">${esc(data.message.text)} ${esc(data.message.action)}</p>` : ""}`;
    }
    messagesBody() {
      const info = this.state.messages, saved = info.settings;
      if (!saved.recipient) return this.heading(badge("Optional")) + `<div class="metric"><div class="symbol">${icon("cellphone")}</div><p>Send wake updates and your chosen readings to your phone.</p></div><div class="actions">${button("choose-phone", "Choose phone", "", this.blocked)}</div><p class="hint muted">Automatic messages off.</p>`;
      return this.heading(badge(saved.enabled ? "Enabled" : "Ready — off", saved.enabled ? "ok" : "")) + `<p>Uptime, next shutdown and wake, plus ${saved.fields.length} chosen reading${saved.fields.length === 1 ? "" : "s"}.</p><p class="hint muted">${esc(info.result?.message || "Test delivery before enabling automatic wake messages.")}</p><div class="actions">${button("send-message", "Send status now", "primary", this.blocked || info.busy)}${button("choose-phone", "Settings", "", this.blocked || info.busy)}${button("preview-saved-message", "Preview", "", this.blocked || info.busy)}</div>${info.preview ? `<details data-detail="message-preview"><summary>Message preview</summary><pre class="preview">${esc(info.preview.message || info.preview.body || "")}</pre></details>` : ""}`;
    }
    assistBody() {
      const info = this.state.assist, saved = info.settings;
      return this.heading(badge(saved.enabled ? saved.allow_requests ? "Changes require approval" : "Status only" : "Optional", saved.enabled ? "ok" : "")) + `<div class="metric"><div class="symbol">${icon("message-text-outline")}</div><p>Ask about your Pi and its shutdown and wake times.</p></div><div class="actions">${saved.enabled ? button("configure-assist", "Assist settings", "", this.blocked) : button("connect-assist", "Connect Assist", "", this.blocked)}</div><p class="hint muted">${saved.enabled ? "Select Assist in your AI agent's Control Home Assistant setting." : "AI access and change requests are off."}</p>${saved.enabled ? `<details data-detail="agent-setup"><summary>Agent setup</summary><p>Open your AI integration, such as Ollama. Choose Assist under Control Home Assistant. Ask: “When will the Pi shut down and wake?”</p>${link("/config/integrations/dashboard", "Open Devices & services ↗")}</details>` : ""}${info.requests.map(item => `<div class="notice"><strong>${esc(item.summary)}</strong><div class="actions">${button("approve:" + esc(item.id), "Review and approve", "", this.blocked || item.submitted)}${button("dismiss:" + esc(item.id), "Dismiss", "", this.blocked || item.submitted)}</div></div>`).join("")}`;
    }
    activityBody() { return `<details data-detail="activity"><summary>${esc(this.config.title || names.activity)}</summary><ul class="activity">${this.state.dashboard.activity.map(item => `<li>${esc(item.text)}<small>${esc(this.time(item.time))}</small></li>`).join("") || '<li class="muted">Activity will appear here as you set up and use your Pi.</li>'}</ul><p class="hint muted">App ${esc(this.state.version)} · ${link(this.appUrl("setup"), "Advanced settings ↗")}</p>${button("restore-cards", "Restore default Pi cards", "", this.blocked)}</details>`; }
    panelBody() {
      const data = this.state;
      if (this.panel === "setup") return "";
      if (this.panel === "calendar") return `<h3>Choose a calendar</h3><label>Calendar for this Pi<select name="calendar_entity_id" required><option value="">Choose a calendar</option>${data.calendar.calendars.map(item => `<option value="${esc(item.entity_id)}" ${data.schedule.calendar_entity_id === item.entity_id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label><p class="hint muted">Changing calendars leaves scheduling off until you review and enable it.</p><label>Display time zone<input name="timezone" value="${esc(data.schedule.timezone)}" maxlength="100" required></label><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save calendar</button></div>`;
      if (this.panel === "ups") return `<h3>Choose the UPS supplying this Pi</h3><label>Power source<select name="source_id" required><option value="">Choose a UPS</option>${data.ups.sources.map(source => `<option value="${esc(source.id)}" ${data.ups.settings.source_id === source.id ? "selected" : ""}>${esc(source.name)} · ${esc(source.provider)}</option>`).join("")}</select></label>${check("notifications", "Show power notices in Home Assistant", data.ups.settings.notifications)}<label>Low battery notice threshold (%)<input type="number" name="low_battery_percent" min="5" max="95" value="${data.ups.settings.low_battery_percent}" required></label><p class="hint muted">Saving a UPS enables monitoring. Automatic shutdown protection is configured separately.</p><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save UPS</button></div>`;
      if (this.panel === "messages") { const saved = data.messages.settings, draft = this.messageDraft || saved; return `<h3>Phone and readings</h3><label>Send to phone<select name="recipient"><option value="">Choose a phone</option>${this.messageOptions.recipients.map(item => `<option value="${esc(item.id)}" ${draft.recipient === item.id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></label><p class="hint muted">Every message includes Pi uptime and the next shutdown and wake.</p><label>Find a reading<input name="search" type="search" placeholder="Battery, temperature, area…" maxlength="100"></label><div class="selected-fields"></div><div class="fields"></div>${check("enabled", "Send a message after this Pi starts", draft.enabled)}<p class="hint muted">Save and send a test message to check your phone. Automatic messages start with the next Pi boot.</p><div class="actions">${button("close-panel", "Cancel")}<button type="submit" class="primary">Save phone settings</button></div>`; }
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
      else content = `<div class="body">${["status", "shutdown", "wake"].includes(this.kind) ? this.metricBody() : this[this.kind + "Body"]()}</div>`;
      const notices = `${this.error ? `<p class="notice error-notice">${esc(this.error)} Displayed values may be out of date.</p>` : ""}${this.message && !this.panel ? `<p role="status" class="hint muted">${esc(this.message)}</p>` : ""}${this.state?.job && this.kind === "setup" ? `<p role="status" class="progress">${esc(this.state.job.label)}</p>` : ""}`;
      const panel = this.panel === "calendar-view" ? `<div class="body settings"><h3>Home Assistant Calendar</h3><p class="hint muted">Select the event, then Edit. Changes are saved in your selected calendar.</p><div class="native-calendar"></div><div class="actions">${button("close-panel", "Back to Pi dashboard")}${link("/calendar", "Open Calendar ↗")}</div><p class="form-feedback hint" role="status"></p></div>` : this.panel && this.panel !== "setup" ? `<form class="body settings">${this.panelBody()}<p class="form-feedback hint" role="status"></p></form>` : "";
      this.shadowRoot.innerHTML = `<style>${styles}</style><ha-card>${content}${notices ? `<div class="body">${notices}</div>` : ""}${panel}</ha-card>`;
      for (const detail of this.shadowRoot.querySelectorAll("details[data-detail]")) detail.open = this.detailsOpen.get(detail.dataset.detail) === true;
      for (const element of this.shadowRoot.querySelectorAll("[data-action]")) element.addEventListener("click", () => this.perform(element.dataset.action));
      const form = this.shadowRoot.querySelector("form");
      if (form) { form.addEventListener("input", () => { this.dirty = true; }); form.addEventListener("submit", event => { event.preventDefault(); this.savePanel(form); }); }
      if (this.panel === "messages") { this.renderFields(); this.shadowRoot.querySelector('[name="search"]').addEventListener("input", () => this.renderFields()); }
    }
    async openMessages() {
      if (this.blocked) return;
      if (!this.state.messages.options_revision) { await this.call("scan-messages"); this.message = "Finding phones and readings. Select Choose phone again when discovery finishes."; this.render(); return; }
      try { this.messageOptions = await this._hass.callWS({type: DOMAIN + "/message_options", entry_id: this.config.entry_id || ""}); this.messageDraft = structuredClone(this.state.messages.settings); this.panel = "messages"; this.dirty = false; this.render(); } catch (error) { this.message = error.message; this.render(); }
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
      const selected = this.messageDraft.fields;
      const rows = this.messageOptions.fields.filter(item => query ? [item.name, item.area, item.category, item.id].join(" ").toLocaleLowerCase().includes(query) : item.suggested || selected.includes(item.id)).slice(0, 60);
      fieldBox.innerHTML = rows.map(item => `<label class="toggle"><input type="checkbox" data-field="${esc(item.id)}" ${selected.includes(item.id) ? "checked" : ""} ${!selected.includes(item.id) && selected.length >= 12 ? "disabled" : ""}><span>${esc(item.name)}<small>${esc([item.category, item.area, item.unit].filter(Boolean).join(" · "))}</small></span></label>`).join("") || '<p class="muted">No matching readings. Try a search.</p>';
      selectedBox.innerHTML = selected.map(id => `<button type="button" data-remove="${esc(id)}">${esc(this.messageOptions.fields.find(item => item.id === id)?.name || id)} ×</button>`).join("");
      for (const box of fieldBox.querySelectorAll("input")) box.addEventListener("change", () => { this.messageDraft.fields = box.checked ? [...this.messageDraft.fields, box.dataset.field] : this.messageDraft.fields.filter(id => id !== box.dataset.field); this.dirty = true; this.renderFields(); });
      for (const item of selectedBox.querySelectorAll("button")) item.addEventListener("click", () => { this.messageDraft.fields = this.messageDraft.fields.filter(id => id !== item.dataset.remove); this.dirty = true; this.renderFields(); });
    }
    async savePanel(form) {
      const values = new FormData(form), read = key => values.get(key), checked = key => form.querySelector(`[name="${key}"]`)?.checked === true;
      let action, payload;
      if (this.panel === "calendar") { action = "settings"; payload = {...this.state.schedule, calendar_entity_id: read("calendar_entity_id"), timezone: read("timezone").trim(), enabled: read("calendar_entity_id") === this.state.schedule.calendar_entity_id && this.state.schedule.enabled}; }
      if (this.panel === "ups") { action = "power-settings"; payload = {source_id: read("source_id") || null, notifications: checked("notifications"), low_battery_percent: Number(read("low_battery_percent"))}; }
      if (this.panel === "messages") { action = "message-settings"; payload = {recipient: read("recipient") || null, enabled: checked("enabled"), fields: [...this.messageDraft.fields]}; }
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
