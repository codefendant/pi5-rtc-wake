/* Real Chromium against simulated backend services; never a real HA host or phone. */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const {mkdir} = require('node:fs/promises');

async function start(args = []) {
  const child = spawn('python3', ['tools/preview.py', '--port', '0', ...args], {stdio: ['ignore', 'pipe', 'pipe']});
  const url = await new Promise((resolve,reject) => {
    let output = ''; const timeout = setTimeout(() => reject(new Error('Native preview did not start')),10000);
    child.stdout.on('data', data => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\//); if(match){clearTimeout(timeout);resolve(match[0]);} });
    child.once('exit', code => {clearTimeout(timeout);reject(new Error('Native preview exited '+code));});
  });
  return {child,url};
}

async function main() {
  const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
  await mkdir('ui-artifacts', {recursive:true});
  const first = await start(['--protected']), ready = await start(['--ready']);
  try {
    const page = await browser.newPage({viewport:{width:1536,height:1050},locale:'en-US'}), errors = [], posts=[];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request',request=>{if(request.url().endsWith('/demo/ha-ws')&&request.method()==='POST')posts.push(request.postDataJSON());});
    await page.goto(first.url+'native');
    await page.getByRole('heading',{name:'Allow access to your Pi'}).waitFor();
    await page.screenshot({path:'ui-artifacts/setup-desktop.png',fullPage:true});
    await page.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    await page.getByText('Pi setup needs attention',{exact:true}).waitFor();
    assert.equal((await (await page.request.get(first.url+'api/status')).json()).checks.ok,false);
    await page.getByRole('button',{name:'Review setup',exact:true}).click();
    await page.getByRole('heading',{name:'Allow access to your Pi'}).waitFor();
    assert.equal(await page.getByRole('link',{name:'Open app Info ↗'}).getAttribute('href'),'/config/app/local_pi5_rtc_wake/info');
    assert.equal(await page.getByRole('button',{name:'Create Pi Sleep calendar',exact:true}).isEnabled(),true);
    await page.getByRole('button',{name:'Create Pi Sleep calendar',exact:true}).click();
    await page.getByRole('heading',{name:'Pi Sleep',exact:true}).waitFor();
    assert.equal((await (await page.request.get(first.url+'api/status')).json()).schedule.enabled,false);
    assert.equal(await page.getByRole('button',{name:'Enable scheduling',exact:true}).isDisabled(),true);
    await page.getByRole('button',{name:'Change calendar',exact:true}).click();
    await page.getByLabel('Calendar for this Pi').selectOption('calendar.demo_pi_sleep');
    await page.waitForTimeout(5500); // Poll must preserve this unsaved draft.
    assert.equal(await page.getByLabel('Calendar for this Pi').inputValue(),'calendar.demo_pi_sleep');
    await page.getByRole('button',{name:'Save calendar',exact:true}).click();
    await page.getByRole('heading',{name:'Demo Pi Sleep',exact:true}).waitFor();
    assert.equal((await (await page.request.get(first.url+'api/status')).json()).schedule.enabled,false);

    await page.goto(ready.url+'native');
    await page.getByText('Pi ready · Wake test passed',{exact:true}).waitFor();
    await page.screenshot({path:'ui-artifacts/dashboard-desktop.png',fullPage:true});
    assert.equal(await page.locator('[data-kind="setup"]').getByRole('button',{name:'Review setup'}).isVisible(),true);
    await page.getByRole('button',{name:'Review setup',exact:true}).click();
    await page.getByRole('heading',{name:'Pi setup complete',exact:true}).waitFor();
    await page.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    await page.getByText('Pi ready · Wake test passed',{exact:true}).waitFor();
    const beforePause = (await (await page.request.get(ready.url+'api/status')).json());
    assert.equal(await page.getByRole('button',{name:'Keep awake',exact:true}).count(),0);
    await page.getByRole('button',{name:'Pause calendar',exact:true}).click();
    await page.getByRole('button',{name:'Resume calendar',exact:true}).waitFor();
    const paused = (await (await page.request.get(ready.url+'api/status')).json());
    assert.equal(paused.schedule.enabled,false);
    assert.deepEqual(paused.calendar.periods,beforePause.calendar.periods);
    assert.deepEqual(paused.recovery.settings,beforePause.recovery.settings);
    assert.equal(paused.test_status,beforePause.test_status);
    await page.getByRole('button',{name:'Resume calendar',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).schedule.enabled,false);
    await page.getByRole('button',{name:'Resume calendar',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Enable scheduling',exact:true}).click();
    await page.getByRole('button',{name:'Pause calendar',exact:true}).waitFor();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).schedule.enabled,true);
    await page.locator('[data-kind="ups"]').getByText('Monitoring only',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Connect Assist',exact:true}).isVisible(),true);
    await page.getByRole('button',{name:'Reboot Pi',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal(posts.some(post=>post.action==='reboot-now'),false);
    await page.getByRole('button',{name:'Edit dashboard',exact:true}).click();
    const editor = page.locator('pi-wake-card-editor');
    await editor.getByLabel('Card title').fill('My HA Pi');
    await editor.getByLabel('Card title').blur();
    await page.locator('[data-kind="status"]').getByRole('heading',{name:'My HA Pi'}).waitFor();
    await page.getByRole('button',{name:'Done',exact:true}).click();
    await page.getByRole('button',{name:'Choose phone',exact:true}).click();
    await page.waitForTimeout(5500);
    await page.getByRole('button',{name:'Choose phone',exact:true}).click();
    await page.getByLabel('Send to phone').selectOption('entity:notify.demo_phone');
    await page.getByLabel('Find a reading').fill('UPS');
    await page.getByRole('checkbox',{name:/UPS battery/i}).check();
    await page.getByRole('button',{name:'Save phone settings',exact:true}).click();
    await page.getByRole('button',{name:'Send status now',exact:true}).waitFor();
    const saved = (await (await page.request.get(ready.url+'api/status')).json()).messages.settings;
    assert.equal(saved.enabled,false);
    assert.equal(saved.fields.length,1);
    await page.getByRole('button',{name:'Send status now',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal(posts.some(post=>post.action==='send-message'),false);
    await page.getByRole('button',{name:'Connect Assist',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).assist.settings.enabled,false);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
    await page.screenshot({path:'ui-artifacts/dashboard-mobile.png',fullPage:true});
    // Replay pending states without starting any simulated or real shutdown.
    let pending = {kind:'schedule',emergency:false,remaining_seconds:30,wake_epoch:beforePause.next_wake_epoch};
    await page.route('**/demo/ha-ws',async route=>{
      if(route.request().postDataJSON()?.type!=='pi5_rtc_wake/status')return route.fallback();
      const response=await route.fetch();const state=await response.json();
      await route.fulfill({response,json:{...state,pending}});
    });
    await page.getByRole('button',{name:'Keep awake',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Keep awake',exact:true}).isEnabled(),true);
    pending = {...pending,kind:'ups',emergency:true};
    await page.getByText('Emergency low-battery shutdown cannot be cancelled here.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Cancel this retry',exact:true}).isDisabled(),true);
    pending = null;
    await page.getByRole('button',{name:'Pause calendar',exact:true}).waitFor();
    await page.evaluate(()=>{window.previewHass.user.is_admin=false;});
    await page.waitForTimeout(5500);
    assert.equal(await page.getByRole('button',{name:'Reboot Pi',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'Connect Assist',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'Pause calendar',exact:true}).isDisabled(),true);
    assert.deepEqual(errors,[]);
    console.log('Native cards passed: setup exit before/after readiness, calendar pause/resume preserving dates and protection, countdown-only cancellation, emergency and admin boundaries, editor, phone setup, confirmations, and mobile fit. Hardware and HA frontend chrome are simulated.');
  } finally {await browser.close();first.child.kill('SIGTERM');ready.child.kill('SIGTERM');}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
