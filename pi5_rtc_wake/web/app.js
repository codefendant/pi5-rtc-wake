"use strict";
const $ = id => document.getElementById(id);
let status = null, dirty = false, loading = false, localMessage = null, calendarOptions = "";
let powerDirty = false, powerOptions = "";
let recoveryDirty = false, runtimeOptions = "";
let messagesDirty = false, messageDraftFields = [], messageOptions = {recipients: [], fields: []}, messageOptionsRevision = 0, messageOptionsLoading = false, messageChoiceSignature = "", recipientSignature = "";
let activeView = null, lastSetupNeeded = null, sensorOptions = "", openedPowerSettings = false, recoveryDraftTargets = null;
let assistDirty = false, assistRequestSignature = "";
const views = ["overview", "calendar", "ups", "messages", "assist", "setup"];
const recoveryNumbers = {outage_delay_minutes: "recovery-outage-delay", shutdown_runtime_minutes: "recovery-shutdown-runtime", first_retry_minutes: "recovery-first-retry", max_retry_minutes: "recovery-max-interval", max_retries: "recovery-max-retries", retry_reserve_minutes: "recovery-reserve", min_charge_percent: "recovery-min-charge", boot_grace_minutes: "recovery-boot-grace", stable_power_minutes: "recovery-stable", emergency_runtime_minutes: "recovery-emergency-runtime"};
const recoveryChecks = {enabled: "recovery-enabled", early_shutdown: "recovery-early", supply_confirmed: "recovery-supply", final_shutdown_confirmed: "recovery-final", owner_confirmed: "recovery-owner", retry_enabled: "recovery-retries", emergency_enabled: "recovery-emergency"};
const form = $("schedule-form");
form.addEventListener("input", () => { dirty = true; $("unsaved").hidden = false; if (status) sourceControls(); });

function selectView(view) {
  activeView = view;
  for (const name of views) {
    $("view-" + name).hidden = name !== view;
    $("nav-" + name).setAttribute("aria-pressed", String(name === view));
  }
}
for (const name of views) $("nav-" + name).onclick = () => selectView(name);
$("review-setup").onclick = () => selectView("setup");

function renderOverview(data) {
  const needed = !data.checks.ok || data.test_status !== "passed";
  if (!activeView) selectView(needed ? "setup" : "overview");
  else if (needed && lastSetupNeeded === false && !dirty && !powerDirty && !recoveryDirty && !messagesDirty && !assistDirty && !data.pending && !data.job) selectView("setup");
  else if (!needed && lastSetupNeeded === true && activeView === "setup" && !loading) selectView("overview");
  lastSetupNeeded = needed;
  $("nav-setup").textContent = needed ? "Setup · attention" : "Setup ✓";
  $("nav-setup").classList.toggle("attention", needed);
  $("review-setup").hidden = !needed || activeView === "setup";
  $("overview-pi").textContent = needed ? "Needs attention" : "Ready · test confirmed";
  $("overview-calendar").textContent = data.schedule_active ? "Enabled" : data.schedule.enabled ? "Paused" : "Off";
  const source = data.ups.selected;
  $("overview-power").textContent = source ? {mains: "Utility available", battery: "On battery", off: "Output off", unknown: "Unknown"}[source.power_state] : "Not selected";
  $("overview-charge").textContent = source?.battery_percent != null ? "Battery " + source.battery_percent + "%" : "";
  $("overview-protection").textContent = data.recovery.emergency_active ? "Active" : data.recovery.settings.enabled && data.recovery.settings.emergency_enabled ? "Needs review" : "Off";
  $("overview-retry").textContent = data.recovery.eligible ? "RTC retries available" : data.recovery.settings.enabled ? "RTC retries paused/off" : "";
}

function showMessage(text, action = "", error = false) {
  $("feedback-text").textContent = text;
  $("feedback-action").textContent = action;
  $("feedback").classList.toggle("error", error);
}
function dateText(epoch) {
  if (!epoch) return "";
  return new Intl.DateTimeFormat(undefined, {timeZone: status.schedule.timezone, weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short"}).format(new Date(epoch * 1000));
}
function sourceControls() {
  const busy = Boolean(status.job || status.pending || status.shutdown_requested || loading);
  $("calendar-entity").disabled = busy;
  $("enable-help").textContent = status.test_status === "passed" && status.checks.ok ? "Save to check this calendar. You can turn scheduling off here at any time." : "Complete the checks and confirm a successful wake test to enable scheduling. You can choose a calendar now.";
}
function renderCalendarOptions(data) {
  const choices = data.calendar?.calendars || [];
  const saved = data.schedule.calendar_entity_id || "";
  const signature = JSON.stringify([choices, saved]);
  if (signature === calendarOptions) return;
  calendarOptions = signature;
  const previous = $("calendar-entity").value;
  const selected = dirty ? previous : saved;
  const placeholder = document.createElement("option"); placeholder.value = ""; placeholder.textContent = "Choose a calendar";
  const options = choices.map(item => { const option = document.createElement("option"); option.value = item.entity_id; option.textContent = item.name; return option; });
  if (selected && !choices.some(item => item.entity_id === selected)) {
    const unavailable = document.createElement("option"); unavailable.value = selected; unavailable.textContent = selected + " (unavailable)"; options.push(unavailable);
  }
  $("calendar-entity").replaceChildren(placeholder, ...options);
  $("calendar-entity").value = selected;
}
function renderSaved(data) {
  const schedule = data.schedule;
  const rows = [["Managed in", "Home Assistant Calendar"], ["Calendar", (data.calendar?.calendars || []).find(item => item.entity_id === schedule.calendar_entity_id)?.name || schedule.calendar_entity_id || "Not selected"]];
  rows.push(["Time zone", schedule.timezone]);
  $("saved-times").replaceChildren(...rows.map(([label, value]) => { const li = document.createElement("li"), name = document.createElement("strong"); name.textContent = label + ": "; li.append(name, document.createTextNode(value)); return li; }));
  $("schedule-badge").textContent = !schedule.enabled ? "Off" : data.schedule_active ? "Enabled" : "Paused";
  $("schedule-badge").classList.toggle("ok", Boolean(data.schedule_active));
  $("calendar-periods").hidden = !schedule.calendar_entity_id;
  const now = Date.now() / 1000;
  const periods = (data.calendar?.periods || []).filter(item => item.start_epoch > now);
  $("periods-list").replaceChildren(...periods.slice(0, 10).map(item => { const li = document.createElement("li"), title = document.createElement("strong"), sleep = document.createElement("span"), wake = document.createElement("span"); title.textContent = item.title; sleep.textContent = "Shutdown: " + dateText(item.start_epoch); wake.textContent = item.power_action === "stop" ? "Final stop record · no timed wake" : "Wake: " + dateText(item.end_epoch); li.append(title, sleep, wake); return li; }));
  $("periods-empty").textContent = data.calendar?.ok ? (periods.length ? (periods.length > 10 ? "Showing the next ten off periods. Open Home Assistant Calendar to see all dates and repeats." : "") : "No upcoming off periods. Add an event in Home Assistant's Calendar; scheduling can stay enabled.") : [data.calendar?.message, data.calendar?.action].filter(Boolean).join(" ");
  if (!schedule.enabled) $("next-sleep").textContent = "Scheduling is off. Your saved schedule is kept.";
  else if (!data.schedule_active) $("next-sleep").textContent = data.recovery?.calendar_paused ? "Normal Calendar shutdowns are paused by UPS recovery. Review the recovery state below." : data.checks.ok && data.test_status === "passed" ? "Scheduling is paused until the calendar can be checked. The Pi will stay on." : "Scheduling is paused until the setup checks and wake test pass.";
  else if (data.next_sleep_epoch) $("next-sleep").textContent = "Next shutdown: " + dateText(data.next_sleep_epoch) + " · Wake: " + dateText(data.next_wake_epoch);
  else $("next-sleep").textContent = "Scheduling is enabled. Waiting for the next calendar off period.";
}
function renderPower(data, busy) {
  const power = data.ups;
  if (!power) return;
  if (!openedPowerSettings) { $("power-settings-panel").open = !power.settings.source_id; openedPowerSettings = true; }
  const selectedId = powerDirty ? $("ups-source").value : power.settings.source_id || "";
  const signature = JSON.stringify([power.sources, power.settings.source_id]);
  if (powerOptions !== signature) {
    powerOptions = signature;
    const placeholder = document.createElement("option"); placeholder.value = ""; placeholder.textContent = "Choose a power source";
    const options = power.sources.map(source => { const option = document.createElement("option"); option.value = source.id; option.textContent = source.name + " · " + source.provider; return option; });
    if (selectedId && !power.sources.some(source => source.id === selectedId)) {
      const missing = document.createElement("option"); missing.value = selectedId; missing.textContent = "Saved source (unavailable)"; options.push(missing);
    }
    $("ups-source").replaceChildren(placeholder, ...options); $("ups-source").value = selectedId;
  }
  if (!powerDirty) { $("ups-source").value = power.settings.source_id || ""; $("ups-notifications").checked = power.settings.notifications; $("ups-low-battery").value = power.settings.low_battery_percent; }
  for (const id of ["ups-source", "ups-notifications", "ups-low-battery", "save-ups", "scan-ups"]) $(id).disabled = busy;
  $("ups-message").textContent = [power.message, ...power.warnings, power.notifications_ok ? "" : "The Home Assistant power notification could not be updated."].filter(Boolean).join(" ");
  const source = power.selected;
  const stateText = {mains: "Utility power available", battery: "On battery", off: "Output off", unknown: "Unknown"};
  $("ups-mode").textContent = power.mode === "rtc_recovery" ? data.recovery.protection_eligible ? "UPS protection enabled" : "Protection needs review" : "Monitor only";
  const protectionText = power.mode !== "rtc_recovery" ? "Off · monitor only" : !data.recovery.protection_eligible ? "Paused · review the saved UPS and shutdown ownership" : data.recovery.settings.retry_enabled ? "RTC retries and configured emergency protection" : "Emergency protection only";
  const rows = [["Source", source?.name || (power.settings.source_id ? "Saved source unavailable" : "Not selected")], ["Power", source ? stateText[source.power_state] : "Unknown"], ["Battery", source?.battery_percent != null ? source.battery_percent + "%" : "Not available"], ["Protection", protectionText]];
  if (data.ups.runtime?.seconds != null) rows.push(["Runtime", Math.round(data.ups.runtime.seconds / 60) + " minutes"]);
  else if (source && data.ups.runtime?.message) rows.push(["Runtime", data.ups.runtime.message]);
  $("ups-summary").replaceChildren(...rows.map(([name, value]) => { const li = document.createElement("li"), label = document.createElement("strong"); label.textContent = name + ": "; li.append(label, document.createTextNode(value)); return li; }));
  $("ups-readings").hidden = !source?.readings?.length;
  $("ups-readings-list").replaceChildren(...(source?.readings || []).map(item => { const li = document.createElement("li"); li.textContent = item.name + ": " + item.value + (item.unit ? " " + item.unit : ""); return li; }));
  renderNutSensors(data, busy);
}
function renderNutSensors(data, busy) {
  const info = data.ups.sensor_settings, identity = data.ups.settings.source_id;
  const nut = identity?.startsWith("nut:");
  $("nut-sensors").hidden = !nut;
  if (!nut) return;
  $("nut-device-link").href = "/config/devices/device/" + encodeURIComponent(identity.slice(4));
  const sensors = (info?.sensors || []).filter(row => row.device_id === identity.slice(4) && row.disabled_by != null);
  const blocked = busy || data.recovery.phase !== "idle" || ["battery", "off"].includes(data.ups.selected?.power_state);
  const signature = JSON.stringify([identity, sensors, blocked]);
  $("nut-sensor-message").textContent = !info?.ok ? info?.message || "Open the UPS device page to enable sensors." : sensors.length ? "Enable only the readings you want. Home Assistant may briefly reload NUT; wait for stable utility power before making changes." : "All registered NUT readings for this UPS are enabled. Readings the UPS does not publish cannot be added here.";
  if (signature === sensorOptions) return;
  sensorOptions = signature;
  $("nut-sensor-list").replaceChildren(...sensors.map(row => {
    const li = document.createElement("li"), name = document.createElement("span"), button = document.createElement("button");
    name.textContent = row.name + (row.runtime_measurement ? " · remaining battery runtime" : "") + (!row.can_enable ? " · enable its device or integration in Home Assistant first" : row.disabled_by === "integration" ? " · off by default" : " · disabled");
    button.textContent = "Enable"; button.type = "button"; button.disabled = blocked || !row.can_enable;
    button.setAttribute("aria-label", "Enable " + row.name);
    button.onclick = async () => {
      if (await confirmAction("Enable " + row.name + "?", "This enables the Home Assistant sensor for your saved UPS. NUT may briefly reload and its readings may be unavailable. Make this change while utility power is available.", "Enable sensor")) await act("enable-nut-sensor", {confirmed: true, expected_source_id: identity, entity_id: row.entity_id});
    };
    li.append(name, button); return li;
  }));
}
function renderRetryRequirements() {
  const value = key => Number($(recoveryNumbers[key]).value);
  const count = Math.min(8, Math.max(0, value("max_retries")));
  const first = value("first_retry_minutes"), cap = value("max_retry_minutes"), overhead = value("boot_grace_minutes") + value("retry_reserve_minutes") + 1;
  const rows = Array.from({length: count}, (_, n) => ({interval: Math.min(cap, first * 2 ** n), minimum: Math.min(cap, first * 2 ** n) + overhead}));
  $("retry-requirements").replaceChildren(...rows.map((row, n) => {
    const tr = document.createElement("tr");
    for (const text of [String(n + 1), row.interval + " min", row.minimum + " min"]) { const td = document.createElement("td"); td.textContent = text; tr.append(td); }
    return tr;
  }));
  $("retry-feasibility").textContent = "Each attempt needs this much fresh estimated runtime at that decision, including boot and reserve allowances. " + (rows.some(row => row.minimum > value("shutdown_runtime_minutes")) ? "Your " + value("shutdown_runtime_minutes") + "-minute shutdown threshold cannot normally fund the entire sequence at unchanged load. Later retries are conditional on the runtime reported after wake." : "Intervals are conditional; reserve is checked again after every wake.");
}
function renderRecovery(data, busy) {
  const recovery = data.recovery;
  if (!recovery) return;
  const settings = recovery.settings, source = data.ups.selected;
  const typed = source?.id.startsWith("hook:");
  const selectedId = recoveryDirty ? $("recovery-runtime").value : settings.runtime_entity_id || "";
  const choices = source?.runtime_candidates || [];
  const signature = JSON.stringify([source?.id, choices.map(item => [item.entity_id, item.name]), settings.runtime_entity_id]);
  if (runtimeOptions !== signature) {
    runtimeOptions = signature;
    const placeholder = document.createElement("option"); placeholder.value = ""; placeholder.textContent = typed ? "Provided by this power hook" : "Choose Battery runtime";
    const options = choices.map(item => { const option = document.createElement("option"); option.value = item.entity_id; option.textContent = item.name; return option; });
    if (selectedId && !choices.some(item => item.entity_id === selectedId)) { const missing = document.createElement("option"); missing.value = selectedId; missing.textContent = "Saved runtime reading (unavailable)"; options.push(missing); }
    $("recovery-runtime").replaceChildren(placeholder, ...options); $("recovery-runtime").value = selectedId;
  }
  if (!recoveryDirty) {
    for (const [key, id] of Object.entries(recoveryNumbers)) $(id).value = settings[key];
    for (const [key, id] of Object.entries(recoveryChecks)) $(id).checked = settings[key];
    $("recovery-runtime").value = settings.runtime_entity_id || "";
  }
  for (const id of [...Object.values(recoveryNumbers), ...Object.values(recoveryChecks), "save-recovery"]) $(id).disabled = busy;
  $("recovery-runtime").disabled = busy || Boolean(typed);
  $("recovery-outage-delay").disabled = busy || !$("recovery-early").checked;
  $("recovery-enabled").disabled = busy || (!settings.enabled && (!data.host_shutdown_supported || !source || $("recovery-retries").checked && (!data.checks.ok || data.test_status !== "passed" || !data.schedule.calendar_entity_id)));
  $("recovery-runtime-help").textContent = typed ? "The hook supplies a typed remaining-runtime estimate." : "Select the remaining Battery runtime measurement, not a low-runtime setpoint or delay. Renamed readings are supported.";
  $("recovery-unsaved").hidden = !recoveryDirty;
  $("recovery-badge").textContent = !settings.enabled ? "Off" : recovery.protection_eligible ? "Enabled" : "Needs review";
  $("recovery-badge").classList.toggle("ok", settings.enabled && recovery.protection_eligible);
  const phaseNames = {idle: "Ready", observing: "Watching UPS reserve", planning: "Preparing shutdown", countdown: "Shutdown countdown", submitted: "Shutdown requested", blocked: "RTC retry blocked", paused: "Timed retries paused", stopped: "Final shutdown requested"};
  const rows = [["Saved policy", settings.enabled ? "Enabled" : "Off"], ["Emergency protection", data.keep_awake ? "Suspended · Keep awake on" : recovery.emergency_active ? "Active · independent of RTC readiness" : settings.emergency_enabled && settings.enabled ? "Needs review" : "Off"], ["RTC retries", recovery.eligible ? "Available when reserve permits" : "Off / paused"], ["State", phaseNames[recovery.phase] || "Needs review"], ["Remaining runtime", recovery.runtime_seconds != null ? Math.round(recovery.runtime_seconds / 60) + " minutes" : "Not available"], ["RTC attempts this outage", recovery.attempts + " / " + settings.max_retries], ["Next conditional interval", recovery.next_retry_minutes + " minutes"]];
  if (recovery.next_wake_epoch) rows.push(["Calendar wake", dateText(recovery.next_wake_epoch)]);
  $("recovery-summary").replaceChildren(...rows.map(([name, value]) => { const li = document.createElement("li"), label = document.createElement("strong"); label.textContent = name + ": "; li.append(label, document.createTextNode(value)); return li; }));
  $("recovery-message").textContent = recovery.message + (recovery.notifications_ok ? "" : " The Home Assistant recovery notification could not be updated.");
  $("pause-retries").hidden = !settings.enabled || ["idle", "paused", "stopped", "submitted"].includes(recovery.phase);
  $("pause-retries").disabled = busy;
  $("shutdown-owner-message").textContent = data.ups.shutdown_controller.message;
  $("nut-owner-link").hidden = !data.ups.shutdown_controller.addon_id;
  for (const id of ["rtc-retry-thresholds", "rtc-retry-plan", "rtc-max-interval-field", "rtc-max-retries-field", "rtc-reserve-field", "rtc-early-settings", "rtc-supply-confirmation"]) $(id).hidden = !$("recovery-retries").checked;
  renderRetryRequirements();
}
function messageSettings() {
  return {enabled: $("message-enabled").checked, recipient: $("message-recipient").value || null, fields: [...messageDraftFields]};
}
function messageEdited() {
  messagesDirty = true;
  if (status) renderMessages(status, Boolean(status.job || status.pending || status.shutdown_requested || loading));
}
function renderMessageChoices(busy) {
  const selected = messageDraftFields;
  const category = $("message-category").value || "suggested", search = $("message-search").value.trim().toLocaleLowerCase();
  const signature = JSON.stringify([messageOptionsRevision, selected, category, search, busy]);
  if (signature === messageChoiceSignature) return;
  messageChoiceSignature = signature;
  $("message-field-count").textContent = "(" + selected.length + " / 12)";
  const matches = messageOptions.fields.filter(item => (search || category === "all" || category === "suggested" && item.suggested || category === item.category) && (!search || [item.name, item.id, item.area, item.category].join(" ").toLocaleLowerCase().includes(search)));
  $("message-fields-help").textContent = !messageOptions.fields.length ? "Find phones and readings to list the readings Home Assistant already monitors." : !matches.length ? "No matching readings. Try another search or choose All available readings." : "Showing " + Math.min(60, matches.length) + " of " + matches.length + " matching readings." + (matches.length > 60 ? " Search by name or area to narrow the list." : "");
  $("message-field-options").replaceChildren(...matches.slice(0, 60).map(item => {
    const li = document.createElement("li"), label = document.createElement("label"), checkbox = document.createElement("input"), name = document.createElement("span"), detail = document.createElement("span");
    checkbox.type = "checkbox"; checkbox.checked = selected.includes(item.id); checkbox.disabled = busy || !checkbox.checked && selected.length >= 12;
    checkbox.setAttribute("aria-label", "Include " + item.name);
    name.textContent = item.name; detail.className = "hint"; detail.textContent = [item.category, item.area, item.unit, item.id].filter(Boolean).join(" · ");
    checkbox.onchange = () => { messageDraftFields = checkbox.checked ? [...messageDraftFields, item.id] : messageDraftFields.filter(id => id !== item.id); messageEdited(); };
    const text = document.createElement("span"); text.append(name, detail); label.append(checkbox, text); li.append(label); return li;
  }));
  $("message-selected-fields").replaceChildren(...selected.map(id => {
    const item = messageOptions.fields.find(row => row.id === id), li = document.createElement("li"), name = document.createElement("span"), remove = document.createElement("button");
    name.textContent = item ? item.name + (item.area ? " · " + item.area : "") : id + " (not currently available)";
    remove.type = "button"; remove.textContent = "Remove"; remove.disabled = busy; remove.setAttribute("aria-label", "Remove " + (item?.name || id));
    remove.onclick = () => { messageDraftFields = messageDraftFields.filter(field => field !== id); messageEdited(); };
    li.append(name, remove); return li;
  }));
}
async function loadMessageOptions(revision) {
  if (messageOptionsLoading) return;
  messageOptionsLoading = true;
  try {
    messageOptions = await request("message-options"); messageOptionsRevision = revision;
    if (status) renderMessages(status, Boolean(status.job || status.pending || status.shutdown_requested || loading));
  } catch (error) {
    $("messages-result").textContent = "The reading list could not be loaded. Select Find phones and readings to try again.";
  } finally { messageOptionsLoading = false; }
}
function renderMessages(data, busy) {
  const info = data.messages;
  if (!info) return;
  const blocked = busy || Boolean(info.busy);
  if (!messagesDirty) {
    messageDraftFields = [...info.settings.fields]; $("message-enabled").checked = info.settings.enabled;
  }
  const selected = messagesDirty ? $("message-recipient").value : info.settings.recipient || "";
  const signature = JSON.stringify([messageOptionsRevision, selected]);
  if (signature !== recipientSignature) {
    recipientSignature = signature;
    const placeholder = document.createElement("option"); placeholder.value = ""; placeholder.textContent = "Choose a phone";
    const choices = messageOptions.recipients.map(item => { const option = document.createElement("option"); option.value = item.id; option.textContent = item.name + " · " + item.kind; return option; });
    if (selected && !messageOptions.recipients.some(item => item.id === selected)) { const option = document.createElement("option"); option.value = selected; option.textContent = "Saved phone (find phones to check)"; choices.push(option); }
    $("message-recipient").replaceChildren(placeholder, ...choices); $("message-recipient").value = selected;
  }
  if (!messagesDirty) $("message-recipient").value = info.settings.recipient || "";
  for (const id of ["message-recipient", "message-enabled", "save-messages", "scan-messages", "preview-message"]) $(id).disabled = blocked;
  $("send-message").disabled = blocked || messagesDirty || !info.settings.recipient;
  $("message-unsaved").hidden = !messagesDirty;
  $("messages-badge").textContent = info.settings.enabled ? "Wake messages on" : info.settings.recipient ? "Manual only" : "Off";
  $("messages-badge").classList.toggle("ok", info.settings.enabled);
  $("messages-result").textContent = info.busy || [info.result.message, info.result.action].filter(Boolean).join(" ");
  $("messages-result").classList.toggle("message-error", info.result.error);
  $("message-preview-panel").hidden = !info.preview;
  $("message-preview-title").textContent = info.preview?.title || "";
  $("message-preview").textContent = info.preview?.message || "";
  renderMessageChoices(blocked);
  if (info.options_revision !== messageOptionsRevision && !messageOptionsLoading) loadMessageOptions(info.options_revision);
}
function renderAssist(data, busy) {
  const info = data.assist;
  if (!info) return;
  if (!assistDirty) { $("assist-enabled").checked = info.settings.enabled; $("assist-requests-enabled").checked = info.settings.allow_requests; }
  $("assist-badge").textContent = !info.settings.enabled ? "Off" : info.settings.allow_requests ? "Requests allowed" : "Status only";
  $("assist-badge").classList.toggle("ok", info.settings.enabled);
  $("nav-assist").textContent = info.requests.length ? "Assist · " + info.requests.length : "Assist";
  $("nav-assist").classList.toggle("attention", info.requests.length > 0);
  $("assist-connection").textContent = info.connection;
  $("assist-restart").hidden = !info.restart_needed;
  $("assist-unsaved").hidden = !assistDirty;
  $("connect-assist").disabled = busy || data.recovery.phase !== "idle";
  for (const id of ["assist-enabled", "assist-requests-enabled", "save-assist"]) $(id).disabled = loading;
  $("assist-requests-empty").hidden = info.requests.length > 0;
  const signature = JSON.stringify([info.requests, busy]);
  if (signature === assistRequestSignature) return;
  assistRequestSignature = signature;
  $("assist-requests").replaceChildren(...info.requests.map(item => {
    const row = document.createElement("li"), text = document.createElement("span"), actions = document.createElement("div"), approve = document.createElement("button"), dismiss = document.createElement("button");
    text.textContent = item.summary + (item.submitted ? " Calendar save awaiting confirmation; approving checks for the saved event." : "");
    actions.className = "actions";
    approve.textContent = item.submitted ? "Check saved event" : "Approve request";
    approve.className = item.kind === "reboot" ? "danger" : "primary";
    approve.disabled = busy && !(item.kind === "set_scheduling" && !item.enabled && !loading);
    dismiss.textContent = "Dismiss"; dismiss.disabled = loading;
    approve.onclick = async () => {
      const detail = item.summary + (item.kind === "wake_test" ? " Leave the power connected. Confirm the automatic return afterward. Calendar scheduling and UPS recovery turn off for this test; review them afterward." : item.kind === "create_period" ? " This saves one event in Calendar. It does not enable scheduling." : "");
      if (await confirmAction("Approve Assist request?", detail, item.kind === "reboot" ? "Reboot Pi" : "Approve request", item.kind === "reboot" || item.kind === "wake_test")) await act("assist-review", {id: item.id, approve: true, confirmed: true});
    };
    dismiss.onclick = () => act("assist-review", {id: item.id, approve: false, confirmed: true});
    actions.append(approve, dismiss); row.append(text, actions); return row;
  }));
}
async function request(path, payload) {
  const options = {cache: "no-store", signal: AbortSignal.timeout(["recovery-settings", "connect-assist", "connect-dashboard", "create-calendar", "assist-review"].includes(path) ? 90000 : 25000)};
  if (payload !== undefined) Object.assign(options, {method: "POST", headers: {"Content-Type": "application/json", "X-Pi5-CSRF": status?.csrf || ""}, body: JSON.stringify(payload)});
  const response = await fetch("api/" + path, options);
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.message || "The action could not finish."), {action: data.action || "Reopen this screen from Home Assistant and try again."});
  return data;
}
function render(data) {
  status = data;
  const busy = Boolean(data.job || data.pending || data.shutdown_requested || loading);
  const ready = Boolean(data.checks.ok), passed = data.test_status === "passed";
  const dashboard = data.dashboard;
  $("dashboard-connection").textContent = dashboard?.connection || "Connect once to add the native Home Assistant dashboard. AI access is optional.";
  $("connect-dashboard").textContent = dashboard?.connected ? "Update / reconnect dashboard" : "Connect dashboard";
  $("connect-dashboard").disabled = busy;
  $("open-dashboard").hidden = !dashboard?.connected;
  $("finish-dashboard").hidden = !dashboard?.connected;
  $("permission-guide").hidden = data.permissions?.protected === false;
  $("app-info").href = data.permissions?.slug ? "/config/app/" + encodeURIComponent(data.permissions.slug) + "/info" : "/config/apps";
  $("create-calendar").hidden = Boolean(data.schedule.calendar_entity_id);
  $("create-calendar").disabled = busy;
  $("version").textContent = "Pi Wake & Sleep · " + data.version;
  $("ready-badge").textContent = ready ? "Ready" : "Needs attention";
  $("ready-badge").classList.toggle("ok", ready);
  $("checks-list").replaceChildren(...data.checks.items.map(item => {
    const li = document.createElement("li"), mark = document.createElement("span"), label = document.createElement("span"), detail = document.createElement("span");
    mark.className = "check-mark"; mark.textContent = item.ok ? "✓" : "○";
    label.textContent = item.label; detail.className = "detail"; detail.textContent = item.detail;
    li.append(mark, label, detail); return li;
  }));
  $("checks-message").textContent = data.checks.message;
  $("checks-action").textContent = data.checks.action;
  const details = data.message.details || data.checks.details;
  $("check-details").hidden = !details;
  const supportText = details ? JSON.stringify({app_version: data.version, ...details}, null, 2) : "";
  if ($("support-text").value !== supportText) $("support-text").value = supportText;
  $("check").disabled = busy && !(data.recovery_check_allowed && !data.job && !loading);
  $("prepare").disabled = busy || !data.checks.can_prepare;
  $("prepare").hidden = Boolean(data.checks.wake_configured);
  $("prepare-description").textContent = data.checks.wake_configured ? "Your wake settings are already prepared." : "Wake settings are checked automatically. Preparation keeps your existing boot order.";
  $("reboot").hidden = !data.checks.needs_reboot;
  $("reboot").disabled = busy || data.keep_awake;
  $("reboot-reminder").hidden = !data.checks.needs_reboot;
  $("reboot-reminder").textContent = data.reboot_notice_ok ? "A reboot reminder also appears in Home Assistant's Notifications and clears after reboot and successful checks." : "The Home Assistant notification could not be updated. Use Reboot Pi here, or reboot the system from Settings → System.";
  $("test").disabled = busy || !ready || data.keep_awake;
  $("test").textContent = passed ? "Run test again" : "Run ten-minute test";
  $("test").hidden = data.test_status === "awaiting_confirmation";
  $("confirm-test").hidden = data.test_status !== "awaiting_confirmation";
  $("confirm-yes").disabled = busy || !ready;
  $("confirm-no").disabled = busy;
  const testText = {passed: "Confirmed", waiting: "Waiting for Pi", awaiting_confirmation: "Confirm return", failed: "Try again", needs_retest: "Test again"};
  $("test-badge").textContent = testText[data.test_status] || "Not tested";
  $("test-badge").classList.toggle("ok", passed);
  if (data.test_status === "failed") $("test-description").textContent = "A return near the wake time was not confirmed. The schedule stays off until a new test succeeds.";
  else if (data.test_status === "needs_retest") $("test-description").textContent = "The Pi's firmware or wake settings changed. Run the test again before scheduling resumes.";
  else $("test-description").textContent = "The Pi shuts down and should wake about ten minutes later. Home Assistant will be offline while it is off.";
  if (!dirty) {
    $("timezone").value = data.schedule.timezone;
    $("enabled").checked = data.schedule.enabled;
  }
  renderCalendarOptions(data);
  if (!dirty) $("calendar-entity").value = data.schedule.calendar_entity_id || "";
  $("calendar-message").textContent = [data.calendar?.message, data.calendar?.action].filter(Boolean).join(" ");
  $("unsaved").hidden = !dirty;
  // Turning an existing schedule OFF is always available after an operation.
  $("enabled").disabled = busy || (!data.schedule.enabled && (!ready || !passed));
  for (const id of ["timezone", "save"]) $(id).disabled = busy;
  sourceControls();
  renderSaved(data);
  $("migration-notice").hidden = !data.migration_notice;
  $("migration-notice").textContent = data.migration_notice || "";
  renderPower(data, busy);
  renderRecovery(data, busy);
  renderMessages(data, busy);
  renderAssist(data, busy);
  renderOverview(data);
  $("countdown").hidden = !data.pending;
  $("awake-state").textContent = data.keep_awake ? "Keep awake is on · all app shutdowns and reboots, including emergency UPS shutdowns, are suspended." : "Your saved Calendar and UPS settings control shutdowns.";
  $("keep-awake").textContent = data.keep_awake ? "Resume shutdowns" : "Keep awake";
  $("keep-awake").disabled = loading || data.shutdown_requested || Boolean(data.storage_notice);
  $("keep-awake").setAttribute("aria-pressed", Boolean(data.keep_awake));
  $("cancel").hidden = false;
  $("cancel").textContent = "Keep awake";
  $("cancel").disabled = loading || data.shutdown_requested;
  if (data.pending) {
    $("countdown-title").textContent = "Shutting down in " + data.pending.remaining_seconds + " seconds";
    $("countdown-wake").textContent = data.pending.wake_epoch ? "Wake time: " + dateText(data.pending.wake_epoch) + ". Home Assistant will be offline until the Pi returns." : "Final shutdown · no timed wake. Restart may require restored UPS output, a power cycle, or the Pi's power button.";
  }
  if (localMessage) showMessage(localMessage.message, localMessage.action, true);
  else if (data.job) showMessage(data.job.label, "Keep the Pi's power supply connected.");
  else showMessage(data.message.text, data.message.action, data.message.error);
}
async function poll() {
  try {
    render(await request("status"));
    $("connection").hidden = true;
  } catch (error) {
    $("connection").hidden = false;
    $("connection").textContent = status?.pending ? "Home Assistant may be shutting down. Leave the power connected and reopen this app after the wake time." : "This screen cannot reach Home Assistant. If the Pi is rebooting or off, leave the power connected and reopen this app when it returns.";
  }
}
async function act(path, payload = {}) {
  if (loading) return;
  loading = true; localMessage = null;
  if (status) render(status);
  try {
    await request(path, payload);
    if (path === "settings") dirty = false;
    if (path === "power-settings") powerDirty = false;
    if (path === "recovery-settings") { recoveryDirty = false; recoveryDraftTargets = null; }
    if (path === "message-settings") messagesDirty = false;
    if (path === "assist-settings") assistDirty = false;
  } catch (error) {
    localMessage = {message: error.message || "The action could not finish.", action: error.action || "Check the connection, then try again."};
  } finally {
    loading = false;
    await poll();
  }
}
function confirmAction(title, message, label, danger = false) {
  $("dialog-title").textContent = title; $("dialog-message").textContent = message; $("dialog-confirm").textContent = label;
  $("dialog-confirm").classList.toggle("danger", danger);
  $("confirm-dialog").returnValue = "";
  $("confirm-dialog").showModal();
  return new Promise(resolve => $("confirm-dialog").addEventListener("close", () => resolve($("confirm-dialog").returnValue === "confirm"), {once: true}));
}
$("check").onclick = () => act("check");
$("connect-dashboard").onclick = async () => {
  if (await confirmAction("Connect your Pi dashboard?", "This installs or updates the Home Assistant companion. Restart Home Assistant if requested, then add the discovered Pi Wake & Sleep integration in Devices & services. Your existing settings and personal dashboard cards are kept. AI access is optional and is not turned on by this step.", "Connect dashboard")) await act("connect-dashboard", {confirmed: true});
};
$("create-calendar").onclick = () => act("create-calendar", {confirmed: true});
$("connect-assist").onclick = async () => {
  if (await confirmAction("Connect Assist?", "This installs or updates the app's Home Assistant companion. Home Assistant will discover the connection automatically. A Home Assistant restart may be needed. Status access starts on; change requests start off unless you previously enabled them.", "Connect Assist")) { assistDirty = false; await act("connect-assist", {confirmed: true}); }
};
$("assist-form").addEventListener("input", () => { assistDirty = true; $("assist-unsaved").hidden = false; });
$("assist-form").onsubmit = event => { event.preventDefault(); act("assist-settings", {enabled: $("assist-enabled").checked, allow_requests: $("assist-requests-enabled").checked}); };
async function toggleKeepAwake() {
  const active = !status.keep_awake;
  const message = active ? "Suspend every shutdown and reboot from this app, including emergency low-battery UPS shutdowns. This stays on until you resume, even after an app restart. Calendar dates and settings are kept. Other apps retain their own power controls." : "Resume your saved Calendar and UPS settings. Normal setup and fresh-reading checks still apply. Low UPS reserve may trigger an immediate shutdown.";
  if (await confirmAction(active ? "Keep awake?" : "Resume shutdowns?", message, active ? "Keep awake" : "Resume shutdowns", active && status.recovery.settings.enabled)) await act("keep-awake", {active, confirmed: true});
}
$("cancel").onclick = toggleKeepAwake;
$("keep-awake").onclick = toggleKeepAwake;
$("scan-ups").onclick = () => act("scan-ups");
$("scan-messages").onclick = () => act("scan-messages");
$("message-recipient").onchange = messageEdited;
$("message-enabled").onchange = messageEdited;
$("message-search").oninput = () => { messageChoiceSignature = ""; if (status) renderMessages(status, loading); };
$("message-category").onchange = () => { messageChoiceSignature = ""; if (status) renderMessages(status, loading); };
$("messages-form").onsubmit = event => { event.preventDefault(); act("message-settings", messageSettings()); };
$("preview-message").onclick = () => act("preview-message", {settings: messageSettings()});
$("send-message").onclick = async () => {
  const saved = status.messages.settings;
  const phone = messageOptions.recipients.find(row => row.id === saved.recipient)?.name || "your saved phone";
  if (await confirmAction("Send Pi status to " + phone + "?", "This sends the next shutdown and wake times, Pi uptime, and your saved readings through Home Assistant. Check the phone to confirm delivery.", "Send status")) await act("send-message", {confirmed: true, expected_settings: saved});
};
$("pause-retries").onclick = () => act("pause-rtc-retries");
$("ups-form").addEventListener("input", () => { powerDirty = true; });
$("ups-form").onsubmit = event => { event.preventDefault(); act("power-settings", {source_id: $("ups-source").value || null, notifications: $("ups-notifications").checked, low_battery_percent: Number($("ups-low-battery").value)}); };
$("recovery-form").addEventListener("input", () => { if (!recoveryDirty && status) recoveryDraftTargets = {source_id: status.ups.settings.source_id, calendar_id: status.schedule.calendar_entity_id}; recoveryDirty = true; $("recovery-unsaved").hidden = false; if (status) renderRecovery(status, loading); });
$("recovery-form").onsubmit = async event => {
  event.preventDefault();
  const payload = {runtime_entity_id: $("recovery-runtime").value || null, expected_source_id: recoveryDraftTargets?.source_id ?? status.ups.settings.source_id, expected_calendar_entity_id: recoveryDraftTargets ? recoveryDraftTargets.calendar_id : status.schedule.calendar_entity_id};
  for (const [key, id] of Object.entries(recoveryNumbers)) payload[key] = Number($(id).value);
  for (const [key, id] of Object.entries(recoveryChecks)) payload[key] = $(id).checked;
  const old = status.recovery.settings;
  if (old.enabled && old.emergency_enabled && (!payload.enabled || !payload.emergency_enabled)) {
    if (!await confirmAction("Disable emergency low-battery protection?", "The Pi may remain running until UPS power fails. Cancelling a timed retry already leaves emergency protection active; this change disables that protection.", "Disable protection", true)) return;
    payload.confirmed_disable_emergency = true;
  }
  if (payload.enabled && (!old.enabled || !old.owner_confirmed || payload.retry_enabled && !old.retry_enabled) && !await confirmAction("Enable automatic UPS protection?", "This policy can shut down the Home Assistant Pi during an outage. RTC retries are conditional on fresh reserve and continuous UPS output. A final stop has no timed wake. Confirmations must reflect this supply path and the chosen host-shutdown controller.", "Enable UPS protection", true)) return;
  await act("recovery-settings", payload);
};
$("confirm-yes").onclick = () => act("confirm-test", {returned_automatically: true});
$("confirm-no").onclick = () => act("reject-test");
$("prepare").onclick = async () => {
  if (await confirmAction("Prepare this Pi?", "This changes only the two wake settings and keeps your current boot order. Leave the power connected. Do not start another Pi firmware update during preparation. A reboot is needed afterward.", "Prepare this Pi")) await act("prepare", {confirmed: true});
};
$("reboot").onclick = async () => {
  if (await confirmAction("Reboot the Pi?", "Home Assistant will be unavailable for a few minutes. Leave the power connected, then reopen this app.", "Reboot Pi", true)) await act("reboot", {confirmed: true});
};
$("test").onclick = async () => {
  if (await confirmAction("Run a ten-minute wake test?", "The Pi will shut down after a 30-second countdown. Home Assistant and its automations will be offline. Leave the power connected and check whether it returns by itself. If it has not returned after 15 minutes, press the Pi's power button once. Calendar scheduling and UPS recovery are turned off for this test; review and enable them afterward.", "Start wake test")) await act("test", {confirmed: true});
};
form.onsubmit = event => {
  event.preventDefault();
  const payload = {source: "calendar", calendar_entity_id: $("calendar-entity").value || null, timezone: $("timezone").value.trim(), enabled: $("enabled").checked};
  act("settings", payload);
};
poll().finally(() => { let hash = globalThis.location?.hash; try { hash = hash || globalThis.parent?.location?.hash; } catch {} const view = hash?.slice(1); if (views.includes(view)) selectView(view); setInterval(() => { if (!loading) poll(); }, 1000); });
