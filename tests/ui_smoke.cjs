/* Browser check against the simulated loopback demo; never a real Pi or UPS. */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {chromium} = require('playwright');
async function main() {
  const child = spawn('python3', ['tools/preview.py', '--port', '0'], {stdio: ['ignore', 'pipe', 'pipe']});
  let browser;
  try {
    let output = '';
    const url = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Local demo did not start.')), 10000);
      child.stdout.on('data', data => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\//); if (match) { clearTimeout(timer); resolve(match[0]); } });
      child.once('exit', code => { clearTimeout(timer); reject(new Error('Demo exited: ' + code)); });
    });
    browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
    const page = await browser.newPage({viewport: {width: 1100, height: 1050}, locale: 'en-US'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await page.waitForFunction(() => document.getElementById('calendar-entity').options.length > 1);
    assert.equal(await page.getByLabel('Enable schedule').isDisabled(), true);
    assert.equal(await page.locator('#sleep-time, #wake-time, #schedule-source, #sleep-now').count(), 0);
    assert.equal(await page.getByRole('link', {name: 'Open Home Assistant Calendar ↗'}).isVisible(), true);
    await page.locator('#nav-calendar').click();
    // A wrapping select label also contains option text; retain the label check
    // while matching its stable leading text rather than the changing options.
    await page.getByLabel(/^Calendar for this Pi/).selectOption('calendar.demo_pi_sleep');
    assert.match(await page.locator('#saved-times').innerText(), /Not selected/);
    assert.equal(await page.locator('#unsaved').isVisible(), true);
    await page.getByRole('button', {name: 'Save calendar settings', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('saved-times').textContent.includes('Demo Pi Sleep'));
    assert.equal(await page.locator('#periods-list li').count(), 3);
    assert.equal(await page.locator('#unsaved').isVisible(), false);
    await page.reload();
    await page.waitForFunction(() => document.getElementById('calendar-entity').value === 'calendar.demo_pi_sleep');
    assert.equal(await page.locator('#periods-list li').count(), 3);
    const saved = (await (await page.request.get(url + 'api/status')).json()).schedule;
    assert.equal('sleep_time' in saved, false);
    assert.equal('wake_time' in saved, false);
    await page.locator('#nav-setup').click();
    await page.getByRole('button', {name: 'Run ten-minute test', exact: true}).click();
    await page.getByRole('button', {name: 'Go back', exact: true}).click();
    assert.equal((await (await page.request.get(url + 'api/status')).json()).pending, null);
    await page.getByRole('button', {name: 'Run ten-minute test', exact: true}).click();
    await page.getByRole('button', {name: 'Start wake test', exact: true}).click();
    await page.locator('#countdown:not([hidden])').waitFor();
    await page.getByRole('button', {name: 'Keep Pi awake', exact: true}).click();
    await page.locator('#countdown').waitFor({state: 'hidden'});
    await page.locator('#nav-ups').click();
    await page.getByRole('button', {name: 'Find power sources', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('scan-ups').disabled === false && document.getElementById('ups-source').options.length > 1);
    await page.getByLabel(/^Power source for this Pi/).selectOption('hook:sensor.demo_local_power');
    await page.getByLabel('Show power notices in Home Assistant', {exact: true}).check();
    await page.getByRole('button', {name: 'Save power monitor', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('ups-summary').textContent.includes('Demo UPS'));
    assert.match(await page.locator('#ups-summary').innerText(), /Utility power available/);
    assert.match(await page.locator('#ups-summary').innerText(), /monitor only/);
    await page.locator('#recovery-settings-panel summary').first().click();
    assert.equal(await page.getByLabel('Enable automatic UPS protection', {exact: true}).isChecked(), false);
    assert.equal(await page.getByLabel('Enable automatic UPS protection', {exact: true}).isDisabled(), true);
    assert.match(await page.locator('#retry-requirements').innerText(), /24 min/);
    assert.match(await page.locator('#retry-requirements').innerText(), /39 min/);
    assert.match(await page.locator('#retry-requirements').innerText(), /69 min/);
    await page.getByRole('button', {name: 'Save UPS recovery', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('recovery-message').textContent.includes('off'));
    assert.equal((await (await page.request.get(url + 'api/status')).json()).recovery.settings.enabled, false);
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const readyStatus = await (await page.request.get(url + 'api/status')).json();
    readyStatus.test_status = 'passed';
    readyStatus.checks.ok = true;
    await page.route('**/api/status', route => route.fulfill({json: readyStatus}));
    await page.reload();
    await page.locator('#view-overview:not([hidden])').waitFor();
    assert.equal(await page.locator('#view-setup').isVisible(), false);
    await page.locator('#nav-setup').click();
    assert.equal(await page.locator('#view-setup').isVisible(), true);
    assert.deepEqual(errors, []);
    console.log('UI smoke passed: calendar-only settings, native link, saved list, reload, countdown cancellation, UPS discovery/selection/notices, and mobile width.');
  } finally {
    if (browser) await browser.close();
    child.kill('SIGTERM');
    if (child.exitCode === null) await once(child, 'exit');
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
