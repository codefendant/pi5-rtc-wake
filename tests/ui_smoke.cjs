/* Real Chromium against simulated installation/maintenance services only. */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const {mkdir} = require('node:fs/promises');
async function main() {
  const child = spawn('python3', ['tools/preview.py', '--port', '0', '--protected'], {stdio: ['ignore', 'pipe', 'pipe']});
  let browser;
  try {
    const url = await new Promise((resolve,reject)=>{
      let output=''; const timeout=setTimeout(()=>reject(new Error('Maintenance preview did not start')),10000);
      child.stdout.on('data',data=>{output+=data;const match=output.match(/http:\/\/127\.0\.0\.1:\d+\//);if(match){clearTimeout(timeout);resolve(match[0]);}});
      child.once('exit',code=>{clearTimeout(timeout);reject(new Error('Preview exited '+code));});
    });
    await mkdir('ui-artifacts',{recursive:true});
    browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[],posts=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(request.url().includes('/api/')&&request.method()==='POST')posts.push(request.postDataJSON());});
    await page.goto(url);
    await page.getByRole('heading',{name:'Allow access to your Pi',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Connect dashboard',exact:true}).isEnabled(),true);
    assert.equal(await page.locator('#permission-info').getAttribute('href'),'/config/app/local_pi5_rtc_wake/info');
    assert.equal(await page.locator('#maintenance').evaluate(el=>el.open),false);
    assert.equal(await page.locator('form:not(dialog form)').count(),0);
    await page.screenshot({path:'ui-artifacts/install-desktop.png',fullPage:true});
    const before=await (await page.request.get(url+'api/status')).json();
    await page.getByRole('button',{name:'Connect dashboard',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal(posts.length,0);
    await page.getByRole('button',{name:'Connect dashboard',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Connect dashboard',exact:true}).click();
    await page.getByText('Restart Home Assistant',{exact:true}).waitFor();
    const installed=await (await page.request.get(url+'api/status')).json();
    for(const key of ['assist','schedule','messages','test_status','keep_awake'])assert.deepEqual(installed[key],before[key]);
    assert.deepEqual(installed.recovery.settings,before.recovery.settings);
    assert.equal(installed.dashboard.active,false);
    assert.equal(await page.locator('#connection-steps').isVisible(),true);
    // Simulate the companion completing its connection; real Core does this in
    // the separately required integration/API job.
    await page.goto(url+'native');
    await page.getByRole('heading',{name:'Allow access to your Pi',exact:true}).waitFor();
    await page.goto(url);
    await page.getByRole('heading',{name:'Your dashboard is connected',exact:true}).waitFor();
    assert.equal(await page.locator('#connection-steps').isVisible(),false);
    assert.equal(await page.locator('#permission-guide').isVisible(),false);
    assert.equal(await page.getByRole('link',{name:'Open Pi Wake & Sleep ↗'}).getAttribute('href'),'/pi-wake-sleep');
    await page.locator('#maintenance > summary').click();
    await page.locator('#check-details > summary').click();
    await page.waitForTimeout(5500);
    assert.equal(await page.locator('#maintenance').evaluate(el=>el.open),true);
    assert.equal(await page.locator('#check-details').evaluate(el=>el.open),true);
    assert.match(await page.getByLabel('Details for support').inputValue(),/app_version/);
    assert.equal(await page.getByRole('button',{name:'Keep awake',exact:true}).count(),0);
    assert.equal(await page.getByRole('button',{name:'Save UPS protection',exact:true}).count(),0);
    await page.screenshot({path:'ui-artifacts/maintenance-desktop.png',fullPage:true});
    await page.getByRole('button',{name:'Update / reconnect dashboard',exact:true}).click();
    await page.getByRole('button',{name:'Go back',exact:true}).click();
    assert.equal(posts.length,1);
    await page.route('**/api/connect-dashboard',route=>route.fulfill({status:409,json:{message:'Companion files need attention.',action:'Contact the app maintainer. Your files were kept.'}}));
    await page.getByRole('button',{name:'Update / reconnect dashboard',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Update / reconnect',exact:true}).click();
    await page.getByText('Contact the app maintainer. Your files were kept.',{exact:false}).waitFor();
    await page.waitForTimeout(5500);
    assert.equal(await page.locator('#notice').isVisible(),true); // Keep the error through polling.
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
    await page.screenshot({path:'ui-artifacts/maintenance-mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('Maintenance browser passed: first-run permissions and connection, consent/settings retention, connected-screen cleanup, support/dropdown persistence, repair errors, and mobile fit. All services simulated.');
  } finally {if(browser)await browser.close();child.kill('SIGTERM');}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
