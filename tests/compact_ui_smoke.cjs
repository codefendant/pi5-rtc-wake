/* Current dashboard in real Chromium with simulated backend/power services. */
const assert = require('node:assert/strict');

module.exports = async function compactDashboard({browser, start}) {
  const ready = await start(['--ready']), fresh = await start(['--protected']);
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000},locale:'en-US'}), posts=[], errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(request.url().endsWith('/demo/ha-ws')&&request.method()==='POST')posts.push(request.postDataJSON());});
    await page.goto(ready.url+'native');
    const summary=page.locator('[data-kind="summary"]');
    await summary.getByText('Awake',{exact:true}).waitFor();
    assert.equal(await page.locator('#cards > *').count(),7);
    assert.equal(await summary.locator('.pi-artwork').count(),1);
    assert.equal(await summary.getByText('Raspberry Pi 5',{exact:false}).count(),1);
    assert.equal(await summary.locator('.setup-ready').count(),0);
    assert.equal(await summary.getByRole('button',{name:'Review setup',exact:true}).count(),0);
    assert.equal(await summary.getByRole('button',{name:'Reboot Pi',exact:true}).count(),0);
    assert.equal(await summary.getByText('Next shutdown',{exact:true}).count(),1);
    assert.equal(await summary.getByText('Next wake',{exact:true}).count(),1);
    assert.equal(await summary.getByRole('button',{name:'Keep awake',exact:true}).isEnabled(),true);
    assert((await summary.boundingBox()).height < 240,'Ready summary should fit in one compact desktop row');
    const before=(await (await page.request.get(ready.url+'api/status')).json());
    await page.screenshot({path:'ui-artifacts/compact-dashboard-desktop.png',fullPage:true});

    await summary.getByRole('button',{name:'Settings',exact:true}).click();
    await summary.getByRole('heading',{name:'Pi settings',exact:true}).waitFor();
    assert.equal(await summary.getByRole('link',{name:'Setup & maintenance ↗'}).getAttribute('href'),'/app/local_pi5_rtc_wake');
    assert.equal(await summary.getByRole('button',{name:'Reboot Pi',exact:true}).evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(232, 36, 46)');
    await summary.locator('[data-detail="dashboard-maintenance"] > summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await summary.locator('[data-detail="dashboard-maintenance"]').evaluate(el=>el.open),true);
    await summary.getByRole('button',{name:'Reboot Pi',exact:true}).click();
    await summary.getByRole('dialog').getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal(posts.some(post=>post.action==='reboot-now'),false);
    await summary.getByRole('button',{name:'Review setup',exact:true}).click();
    await summary.getByRole('heading',{name:'Pi setup complete',exact:true}).waitFor();
    await summary.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    assert.equal(await summary.getByRole('heading',{name:'Pi setup complete',exact:true}).count(),0);

    await summary.getByRole('button',{name:'Keep awake',exact:true}).click();
    await summary.getByRole('dialog').getByRole('button',{name:'Keep awake',exact:true}).click();
    await summary.getByRole('button',{name:'Resume shutdowns',exact:true}).waitFor();
    assert.equal(await summary.getByText('All app shutdowns and UPS shutdown protection suspended.',{exact:true}).isVisible(),true);
    assert.deepEqual(await summary.locator('.summary-time strong').allTextContents(),['—','—']);
    const paused=(await (await page.request.get(ready.url+'api/status')).json());
    assert.equal(paused.keep_awake,true);
    for(const key of ['schedule','test_status','messages','recovery','ups']) {
      const old=key==='messages'||key==='recovery'||key==='ups'?before[key].settings:before[key];
      const current=key==='messages'||key==='recovery'||key==='ups'?paused[key].settings:paused[key];
      assert.deepEqual(current,old,key+' preferences must be retained');
    }
    await summary.getByRole('button',{name:'Resume shutdowns',exact:true}).click();
    await summary.getByRole('dialog').getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).keep_awake,true);
    await summary.getByRole('button',{name:'Resume all shutdowns',exact:true}).click();
    await summary.getByRole('dialog').getByRole('button',{name:'Resume shutdowns',exact:true}).click();
    await summary.getByRole('button',{name:'Keep awake',exact:true}).waitFor();
    assert.equal((await (await page.request.get(ready.url+'api/status')).json()).schedule.enabled,before.schedule.enabled);

    const messages=page.locator('[data-kind="messages"]');
    await messages.getByRole('button',{name:'Choose phone',exact:true}).click();
    await messages.getByRole('heading',{name:'Phone and readings',exact:true}).waitFor();
    await messages.locator('input[type="radio"][name="recipient"]').first().check();
    await messages.getByRole('button',{name:'Save phone settings',exact:true}).click();
    await messages.getByRole('button',{name:'Settings',exact:true}).waitFor();
    assert.equal(await messages.getByRole('heading',{name:'Phone and readings',exact:true}).count(),0);
    assert.equal(posts.some(post=>post.action==='send-message'),false);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.equal(await summary.getByRole('button',{name:'Keep awake',exact:true}).isVisible(),true);
    await page.screenshot({path:'ui-artifacts/compact-dashboard-mobile.png',fullPage:true});
    await summary.getByRole('button',{name:'Settings',exact:true}).click();
    await summary.getByRole('heading',{name:'Pi settings',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:'ui-artifacts/compact-settings-mobile.png',fullPage:true});
    await summary.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    await page.evaluate(()=>{window.previewHass.themes={darkMode:true};for(const card of document.querySelectorAll('#cards > *'))card.hass=window.previewHass;document.body.style.cssText='--ha-card-background:#111827;--primary-text-color:#f1f5f9;--secondary-text-color:#aab7c9;--divider-color:#334155;--secondary-background-color:#1e293b;background:#0f172a;color:#f1f5f9';});
    await page.screenshot({path:'ui-artifacts/compact-dashboard-dark-mobile.png',fullPage:true});

    let pending={kind:'ups',emergency:true,remaining_seconds:30};
    await page.route('**/demo/ha-ws',async route=>{if(route.request().postDataJSON()?.type!=='pi5_rtc_wake/status')return route.fallback();const response=await route.fetch();const state=await response.json();await route.fulfill({response,json:{...state,pending}});});
    await summary.getByText('Emergency shutdown',{exact:true}).waitFor();
    assert.equal(await summary.getByRole('button',{name:'Keep awake',exact:true}).isEnabled(),true);
    await summary.getByRole('button',{name:'Settings',exact:true}).click();
    assert.equal(await summary.getByRole('button',{name:'Reboot Pi',exact:true}).isDisabled(),true);
    await page.evaluate(()=>{window.previewHass.user.is_admin=false;});
    await page.waitForTimeout(5500);
    assert.equal(await summary.getByRole('button',{name:'Keep awake',exact:true}).isDisabled(),true);
    assert.equal(await summary.getByRole('button',{name:'Reboot Pi',exact:true}).isDisabled(),true);
    await summary.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    await page.unroute('**/demo/ha-ws');
    await page.route('**/demo/ha-ws',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({message:'App unavailable'})}));
    await summary.getByText('Unavailable',{exact:true}).waitFor();
    assert.equal(await summary.getByText('Awake',{exact:true}).count(),0);

    const initial=await browser.newPage({viewport:{width:390,height:844},locale:'en-US'});
    await initial.goto(fresh.url+'native');
    const setup=initial.locator('[data-kind="summary"]');
    await setup.getByRole('heading',{name:'Allow access to your Pi',exact:true}).waitFor();
    await setup.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    await setup.getByText('Pi setup needs attention',{exact:true}).waitFor();
    await initial.waitForTimeout(5500);
    assert.equal(await setup.getByRole('heading',{name:'Allow access to your Pi',exact:true}).count(),0);
    await setup.getByRole('button',{name:'Review setup',exact:true}).click();
    await setup.getByRole('heading',{name:'Allow access to your Pi',exact:true}).waitFor();
    assert.equal(await initial.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await initial.screenshot({path:'ui-artifacts/compact-setup-mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);
    await initial.close(); await page.close();
    console.log('Compact summary passed: Pi artwork/Awake, compact height, Settings/reboot cancellation, setup exit, persistent details, Keep awake/resume with saved preferences, Messages collapse without sending, mobile/dark fit, emergency/non-admin controls, and truthful disconnected status.');
  } finally {ready.child.kill('SIGTERM');fresh.child.kill('SIGTERM');}
};
