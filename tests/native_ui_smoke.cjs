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
    // Simulated native-calendar bridge. Actual Core/calendar APIs are checked
    // separately; this does not claim to test Home Assistant's complete frontend.
    await page.addInitScript(()=>{
      class CalendarBridge extends HTMLElement {
        constructor(){super();this.attachShadow({mode:'open'});}
        async connectedCallback(){
          const status=await this.hass.callWS({type:'pi5_rtc_wake/status',entry_id:'demo-entry'});
          const native=document.createElement('ha-full-calendar');
          const view={activeStart:new Date(),activeEnd:new Date(Date.now()+86400000),type:'dayGridDay'};
          native.calendar={view,gotoDate(date){window.focusedCalendarDate=date.toISOString();view.activeStart=date;},
            getEvents:()=>status.calendar.periods.map(item=>({start:new Date(item.start_epoch*1000),end:new Date(item.end_epoch*1000),extendedProps:{calendar:this.config.entities[0],eventData:{summary:item.title}}})),
            getOption:()=>info=>{window.openedCalendarEvent={calendar:info.event.extendedProps.calendar,title:info.event.extendedProps.eventData.summary,start:info.event.start.toISOString()};}};
          this.shadowRoot.append(native);
        }
      }
      customElements.define('preview-native-calendar',CalendarBridge);
      window.loadCardHelpers=async()=>({createCardElement(config){window.createdCalendarConfig=config;const widget=document.createElement('preview-native-calendar');widget.config=config;return widget;}});
    });
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
    await page.locator('[data-kind="setup"] summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await page.locator('[data-kind="setup"] details').evaluate(el=>el.open),true);
    await page.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    await page.getByText('Pi ready · Wake test passed',{exact:true}).waitFor();
    const upsCard=page.locator('[data-kind="ups"]');
    await upsCard.getByRole('button',{name:'Set up protection',exact:true}).click();
    await page.getByRole('heading',{name:'UPS protection settings',exact:true}).waitFor();
    assert.equal(await page.getByLabel(/^Remaining-runtime reading/).isDisabled(),true); // Typed hook estimate.
    assert.deepEqual(await upsCard.locator('[data-requirements] tr').allTextContents(),['115 min24 min','230 min39 min','360 min69 min']);
    await page.getByLabel('First retry after shutdown (minutes)',{exact:true}).fill('20');
    await page.waitForTimeout(5500);
    assert.equal(await page.getByLabel('First retry after shutdown (minutes)',{exact:true}).inputValue(),'20');
    assert.match(await upsCard.locator('[data-feasibility]').innerText(),/conditional/);
    await page.getByRole('button',{name:'Save UPS protection',exact:true}).click();
    await upsCard.getByRole('button',{name:'Set up protection',exact:true}).waitFor();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).recovery.settings.first_retry_minutes,20);
    await upsCard.getByRole('button',{name:'Set up protection',exact:true}).click();
    await page.getByRole('checkbox',{name:/I have reviewed shutdown ownership/}).check();
    await page.getByRole('checkbox',{name:/I have confirmed a wake test/}).check();
    await page.getByRole('checkbox',{name:/I understand that low reserve/}).check();
    await page.getByRole('checkbox',{name:'Enable automatic UPS protection',exact:true}).check();
    await upsCard.locator('details[data-detail="ups-protection-advanced"] > summary').click();
    await page.screenshot({path:'ui-artifacts/ups-protection-desktop.png',fullPage:true});
    await page.getByRole('button',{name:'Save UPS protection',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).recovery.settings.enabled,false);
    assert.equal(await page.getByRole('checkbox',{name:'Enable automatic UPS protection',exact:true}).isChecked(),true);
    await page.getByRole('button',{name:'Save UPS protection',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Enable UPS protection',exact:true}).click();
    await upsCard.getByRole('button',{name:'Protection settings',exact:true}).waitFor();
    const protectedSettings=(await (await page.request.get(ready.url+'api/status')).json()).recovery.settings;
    assert.equal(protectedSettings.enabled,true);
    assert.equal(protectedSettings.emergency_enabled,true);
    assert.equal(protectedSettings.retry_enabled,true);
    assert.equal(protectedSettings.qualification.source_id,'hook:sensor.demo_local_power');
    assert.equal(protectedSettings.qualification.calendar_entity_id,'calendar.demo_pi_sleep');
    const protectionPost=posts.find(post=>post.action==='recovery-settings'&&post.payload.enabled);
    assert.equal(protectionPost.payload.expected_source_id,'hook:sensor.demo_local_power');
    assert.equal(protectionPost.payload.expected_calendar_entity_id,'calendar.demo_pi_sleep');
    assert.equal('qualification' in protectionPost.payload,false);
    await upsCard.getByRole('button',{name:'Protection settings',exact:true}).click();
    // Every saved number and confirmation is surfaced without another app page.
    for(const key of ['shutdown_runtime_minutes','first_retry_minutes','max_retry_minutes','max_retries','retry_reserve_minutes','min_charge_percent','boot_grace_minutes','emergency_runtime_minutes','stable_power_minutes','outage_delay_minutes'])assert.equal(Number(await upsCard.locator(`[name="${key}"]`).inputValue()),protectedSettings[key]);
    for(const key of ['enabled','retry_enabled','emergency_enabled','early_shutdown','owner_confirmed','supply_confirmed','final_shutdown_confirmed'])assert.equal(await upsCard.locator(`[name="${key}"]`).isChecked(),protectedSettings[key]);
    await page.getByRole('checkbox',{name:'Enable automatic UPS protection',exact:true}).uncheck();
    await page.getByRole('button',{name:'Save UPS protection',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).recovery.settings.enabled,true);
    await page.getByRole('button',{name:'Save UPS protection',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Disable protection',exact:true}).click();
    await upsCard.getByRole('button',{name:'Set up protection',exact:true}).waitFor();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).recovery.settings.enabled,false);
    assert.equal(posts.some(post=>post.action==='recovery-settings'&&post.payload.confirmed_disable_emergency===true),true);
    const controls=page.locator('[data-kind="controls"]'), piStatus=page.locator('[data-kind="status"]');
    const beforePause = (await (await page.request.get(ready.url+'api/status')).json());
    await controls.getByRole('button',{name:'Keep awake',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).keep_awake,false);
    await controls.getByRole('button',{name:'Keep awake',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Keep awake',exact:true}).click();
    await controls.getByRole('button',{name:'Resume shutdowns',exact:true}).waitFor();
    const paused = (await (await page.request.get(ready.url+'api/status')).json());
    assert.equal(paused.keep_awake,true);
    assert.equal(paused.schedule.enabled,true);
    assert.equal(paused.schedule_active,false);
    assert.deepEqual(paused.calendar.periods,beforePause.calendar.periods);
    assert.deepEqual(paused.recovery.settings,beforePause.recovery.settings);
    assert.equal(paused.test_status,beforePause.test_status);
    await page.reload();
    await controls.getByRole('button',{name:'Resume shutdowns',exact:true}).waitFor();
    assert.equal(await controls.getByRole('button',{name:'Reboot Pi',exact:true}).isDisabled(),true);
    await piStatus.getByRole('button',{name:'Resume all shutdowns',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).keep_awake,true);
    await piStatus.getByRole('button',{name:'Resume all shutdowns',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Resume shutdowns',exact:true}).click();
    await controls.getByRole('button',{name:'Keep awake',exact:true}).waitFor();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).schedule.enabled,true);
    const activity=page.locator('[data-kind="activity"]');
    await activity.locator('summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await activity.locator('details').evaluate(el=>el.open),true);
    await activity.locator('summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await activity.locator('details').evaluate(el=>el.open),false);
    const calendar=page.locator('[data-kind="calendar"]');
    await calendar.getByRole('button',{name:/Demo Pi off/}).first().click();
    await page.waitForFunction(()=>Boolean(window.openedCalendarEvent));
    assert.deepEqual(await page.evaluate(()=>window.createdCalendarConfig),{type:'calendar',entities:['calendar.demo_pi_sleep'],initial_view:'dayGridDay'});
    assert.equal(await page.evaluate(()=>window.openedCalendarEvent.start),new Date(beforePause.calendar.periods[0].start_epoch*1000).toISOString());
    await page.waitForTimeout(5500);
    assert.equal(await calendar.getByRole('button',{name:'Back to Pi dashboard'}).isVisible(),true);
    await calendar.getByRole('button',{name:'Back to Pi dashboard'}).click();
    await page.evaluate(()=>{window.savedCalendarHelpers=window.loadCardHelpers;window.loadCardHelpers=undefined;});
    await calendar.getByRole('button',{name:/Demo Pi off/}).first().click();
    await calendar.getByText('Open Calendar below to edit this event in Home Assistant.',{exact:true}).waitFor();
    assert.equal(await calendar.locator('.settings').getByRole('link',{name:'Open Calendar ↗'}).getAttribute('href'),'/calendar');
    await calendar.getByRole('button',{name:'Back to Pi dashboard'}).click();
    await page.evaluate(()=>{window.loadCardHelpers=window.savedCalendarHelpers;});
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
    await page.getByLabel(/^Send to phone/).waitFor(); // Discovery opens the form without a second click.
    await page.getByLabel(/^Send to phone/).selectOption('entity:notify.demo_phone');
    await page.getByLabel('Show readings').selectOption('all');
    await page.getByLabel('Find a reading').fill('UPS');
    await page.getByRole('checkbox',{name:/UPS battery/i}).check();
    await page.getByRole('button',{name:'Find phones and readings',exact:true}).click();
    await page.getByText('Phones and readings refreshed. Unsaved choices are kept.',{exact:true}).waitFor();
    assert.equal(await page.getByLabel(/^Send to phone/).inputValue(),'entity:notify.demo_phone');
    assert.equal(await page.getByLabel('Find a reading').inputValue(),'UPS');
    assert.equal(await page.getByLabel('Show readings').inputValue(),'all');
    assert.equal(await page.getByRole('checkbox',{name:/UPS battery/i}).isChecked(),true);
    await page.getByRole('button',{name:'Preview message',exact:true}).click();
    await page.getByText('Preview ready. Nothing was sent to your phone.',{exact:true}).waitFor();
    assert.match(await page.locator('.draft-preview pre').innerText(),/Uptime:/);
    assert.match(await page.locator('.draft-preview pre').innerText(),/Next shutdown:/);
    assert.equal(posts.some(post=>post.action==='send-message'),false);
    await page.locator('.draft-preview > summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await page.locator('.draft-preview').evaluate(el=>el.open),false);
    await page.getByRole('button',{name:'Save phone settings',exact:true}).click();
    await page.getByRole('button',{name:'Send status now',exact:true}).waitFor();
    const saved = (await (await page.request.get(ready.url+'api/status')).json()).messages.settings;
    assert.equal(saved.enabled,false);
    assert.equal(saved.fields.length,1);
    const messages=page.locator('[data-kind="messages"]');
    await messages.getByRole('button',{name:'Preview',exact:true}).click();
    await messages.locator('pre').waitFor();
    assert.equal(await messages.locator('details').evaluate(el=>el.open),true);
    await page.waitForTimeout(5500);
    assert.equal(await messages.locator('details').evaluate(el=>el.open),true);
    await messages.locator('summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await messages.locator('details').evaluate(el=>el.open),false);
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
    let runtime={seconds:4320,state:'fresh',message:'Live runtime from Battery runtime.'};
    await page.route('**/demo/ha-ws',async route=>{
      if(route.request().postDataJSON()?.type!=='pi5_rtc_wake/status')return route.fallback();
      const response=await route.fetch();const state=await response.json();
      await route.fulfill({response,json:{...state,pending,
        ups:{...state.ups,runtime,selected:{...state.ups.selected,id:'nut:device_apc'},sensor_settings:{...state.ups.sensor_settings,sensors:[{entity_id:'sensor.battery_runtime',device_id:'device_apc',name:'Battery runtime',can_enable:true}]}},
        assist:{...state.assist,settings:{...state.assist.settings,enabled:true}}}});
    });
    await page.getByRole('button',{name:'Keep awake',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Keep awake',exact:true}).isEnabled(),true);
    pending = {...pending,kind:'ups',emergency:true};
    await controls.getByText('Emergency shutdown',{exact:true}).waitFor();
    assert.equal(await controls.getByRole('button',{name:'Keep awake',exact:true}).isEnabled(),true);
    const ups=page.locator('[data-kind="ups"]'), assist=page.locator('[data-kind="assist"]');
    await ups.getByText('72 min',{exact:true}).waitFor();
    runtime={...runtime,seconds:3900};
    await ups.getByText('65 min',{exact:true}).waitFor();
    runtime={seconds:null,state:'disabled',message:'Enable Battery runtime below.'};
    await ups.getByText('Battery runtime disabled',{exact:true}).waitFor();
    await ups.locator('details[data-detail="nut-readings"] > summary').click();
    await assist.locator('summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await ups.locator('details[data-detail="nut-readings"]').evaluate(el=>el.open),true);
    assert.equal(await assist.locator('details').evaluate(el=>el.open),true);
    pending = null;
    await controls.getByText('Calendar scheduling enabled.',{exact:true}).waitFor();
    await page.evaluate(()=>{window.previewHass.user.is_admin=false;});
    await page.waitForTimeout(5500);
    assert.equal(await page.getByRole('button',{name:'Reboot Pi',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'Assist settings',exact:true}).isDisabled(),true);
    assert.equal(await controls.getByRole('button',{name:'Keep awake',exact:true}).isDisabled(),true);
    assert.equal(await piStatus.getByRole('button',{name:'Suspend all shutdowns',exact:true}).isDisabled(),true);
    assert.equal(await ups.getByRole('button',{name:'Set up protection',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('link',{name:'Advanced settings ↗'}).count(),0);
    assert.deepEqual(errors,[]);
    console.log('Native cards passed: dashboard-only UPS commissioning/draft retention/enable-disable confirmations, automatic phone setup/refresh, setup exit, persistent global Keep awake/resume and Pi status icon, preserved settings/dates, dropdown persistence, Calendar bridge/focus, runtime updates, emergency/admin controls, editor, phone setup, confirmations, and mobile fit. Hardware, Calendar frontend bridge, and HA chrome are simulated; real Core APIs are checked separately.');
  } finally {await browser.close();first.child.kill('SIGTERM');ready.child.kill('SIGTERM');}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
