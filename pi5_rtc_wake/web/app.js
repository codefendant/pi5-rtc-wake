"use strict";
const $ = id => document.getElementById(id);
let status = null, loading = false, polling = false, actionError = "", operation = "";

function render(data) {
  status = data;
  const dashboard = data.dashboard || {};
  const active = Boolean(dashboard.active && dashboard.ready && !dashboard.restart_needed);
  const installed = dashboard.connected;
  const setupError = dashboard.setup_error;
  const blocked = loading || Boolean(data.job || data.pending || data.shutdown_requested || data.storage_notice);
  const slug = data.permissions?.slug;
  const info = slug ? "/config/app/" + encodeURIComponent(slug) + "/info" : "/config/apps";
  $("app-info").href = info;
  $("permission-info").href = info;
  $("open-dashboard").href = dashboard.path || "/pi-wake-sleep";
  $("open-dashboard").hidden = !active;
  $("open-dashboard").classList.toggle("primary", Boolean(active));
  $("connect-dashboard").hidden = Boolean(installed || active);
  $("connect-dashboard").disabled = blocked;
  $("reconnect-dashboard").disabled = blocked;
  $("connection-steps").hidden = Boolean(active);
  $("connected-help").hidden = !active;
  $("restart-link").hidden = !dashboard.restart_needed;
  $("restart-link").classList.toggle("primary", Boolean(dashboard.restart_needed));
  $("finish-dashboard").hidden = !installed || Boolean(dashboard.restart_needed) || active;
  $("finish-dashboard").classList.toggle("primary", Boolean(installed && !dashboard.restart_needed && !active));
  $("permission-guide").hidden = data.permissions?.protected === false || Boolean(active);
  $("connection-heading").textContent = active ? "Your dashboard is connected" : installed ? "Finish connecting your dashboard" : "Connect your Pi dashboard";
  $("connection-badge").textContent = active ? "Connected" : setupError ? "Needs attention" : dashboard.restart_needed ? "Restart Home Assistant" : installed ? "Finish in Devices & services" : "Not connected";
  $("connection-badge").classList.toggle("ok", Boolean(active));
  $("connection-message").textContent = active ? "Open Pi Wake & Sleep for Pi status, shutdown and wake dates, UPS protection, phone messages, and Assist." : setupError ? setupError.message + " " + setupError.action : dashboard.restart_needed ? "Restart Home Assistant to finish Pi Wake & Sleep setup. Open Settings using the button below, select its menu (⋮), then Restart Home Assistant. After it returns, finish in Devices & services and refresh the browser." + (dashboard.restart_notice_ok === false ? " The Home Assistant notification could not be created; use the button below. The app will retry the reminder." : " A reminder is also shown in Home Assistant notifications.") : installed ? "Open Devices & services below. Under Discovered, add Pi Wake & Sleep, then select Submit and Finish. The dashboard appears in the sidebar once setup succeeds. If this integration is already configured, allow up to a minute for its dashboard check." : "Start here once. You will manage your Pi and activate features from the editable Home Assistant dashboard.";
  $("companion-message").textContent = dashboard.restart_needed ? "Restart Home Assistant to load the updated companion. Then refresh the dashboard in your browser." : active ? "Home Assistant is communicating with this app. Reconnect only if you need to repair or update the companion." : dashboard.connection || "Connect the dashboard to begin.";
  $("checks-message").textContent = data.checks.message;
  $("checks-action").textContent = data.checks.ok && data.test_status === "passed" ? "Pi ready · Wake test passed. Review setup on the dashboard to run a test or prepare wake settings." : "Continue Pi setup on the dashboard. " + (data.checks.action || "");
  $("check").disabled = loading || Boolean(data.job || data.pending || data.shutdown_requested && !data.recovery_check_allowed);
  $("checks-list").replaceChildren(...(data.checks.items || []).map(item => {
    const li = document.createElement("li");
    li.textContent = (item.ok ? "✓ " : "○ ") + item.label + " — " + item.detail;
    return li;
  }));
  $("support-text").value = JSON.stringify({app_version: data.version, permissions: data.permissions, checks: data.checks.details || null, dashboard: {connected: Boolean(installed), active: Boolean(dashboard.active), ready: Boolean(dashboard.ready), restart_needed: Boolean(dashboard.restart_needed), restart_notice_ok: dashboard.restart_notice_ok, setup_error: setupError || null}, storage_notice: data.storage_notice || null}, null, 2);
  const error = actionError || data.message?.error || data.storage_notice;
  $("notice").hidden = !loading && !error;
  $("notice").classList.toggle("error", Boolean(error));
  $("notice-text").textContent = loading ? operation : actionError ? "The request could not finish." : data.storage_notice || data.message?.text || "";
  $("notice-action").textContent = loading ? "Keep this page open until the request finishes." : actionError || data.message?.action || "";
  $("version").textContent = "Pi Wake & Sleep " + data.version + " · Preview release";
  // Update values in place: maintenance and support dropdowns keep user intent.
}

async function poll() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("api/status", {cache: "no-store", signal: AbortSignal.timeout(25000)});
    if (!response.ok) throw new Error("The app did not respond.");
    render(await response.json());
  } catch {
    $("notice").hidden = false;
    $("notice").classList.toggle("error", true);
    $("notice-text").textContent = "Pi Wake & Sleep is unavailable.";
    $("notice-action").textContent = "Check that the app is running, then reopen Open Web UI. After an app restart, this page reconnects automatically.";
    for (const id of ["connect-dashboard", "reconnect-dashboard", "check"]) $(id).disabled = true;
  } finally { polling = false; }
}

async function act(path, payload = {}) {
  if (loading || !status) return;
  loading = true; actionError = ""; operation = path === "check" ? "Checking this Pi…" : "Connecting the dashboard…"; render(status);
  try {
    const response = await fetch("api/" + path, {method: "POST", cache: "no-store", headers: {"Content-Type": "application/json", "X-Pi5-CSRF": status.csrf}, body: JSON.stringify(payload), signal: AbortSignal.timeout(path === "connect-dashboard" ? 90000 : 25000)});
    const result = await response.json();
    if (!response.ok) throw new Error([result.message, result.action].filter(Boolean).join(" ") || "The request did not finish.");
    loading = false;
    await poll();
  } catch (error) {
    loading = false; actionError = error.message || "Keep the app running and try again."; render(status);
    $("notice").hidden = false; $("notice").classList.toggle("error", true);
    $("notice-text").textContent = "The request could not finish.";
    $("notice-action").textContent = error.message || "Keep the app running and try again.";
  }
}

function confirmConnection() {
  $("dialog-title").textContent = status?.dashboard?.connected ? "Update / reconnect dashboard?" : "Connect your Pi dashboard?";
  $("dialog-message").textContent = "Install or update the included Home Assistant companion and offer its connection in Devices & services. Your saved settings, Calendar dates, and personal dashboard cards are kept. AI access stays a separate choice. Restart Home Assistant only if requested.";
  $("dialog-confirm").textContent = status?.dashboard?.connected ? "Update / reconnect" : "Connect dashboard";
  return new Promise(resolve => {
    $("confirm-dialog").addEventListener("close", () => resolve($("confirm-dialog").returnValue === "confirm"), {once: true});
    $("confirm-dialog").showModal();
  });
}
async function connect() {
  if (loading || !status) return;
  if (await confirmConnection()) await act("connect-dashboard", {confirmed: true});
}
$("connect-dashboard").onclick = connect;
$("reconnect-dashboard").onclick = connect;
$("check").onclick = () => act("check");
poll();
setInterval(() => { if (!loading) poll(); }, 5000);
