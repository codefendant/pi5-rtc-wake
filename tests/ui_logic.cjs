/* Interaction assertions with a small DOM fixture. This is not browser rendering. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const markup = fs.readFileSync(path.join(root, 'pi5_rtc_wake/web/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'pi5_rtc_wake/web/app.js'), 'utf8');
const initial = JSON.parse(execFileSync('python3', ['-c', `
import json, sys, unittest
sys.path.insert(0,'tests')
from test_setup import Fixture
from test_power_sources import nut_rows
from test_phone_messages import configure_phone
class Demo(unittest.TestCase,Fixture): pass
d=Demo(); d.setup_app(); d.pass_test(); d.enable()
d.supervisor.power_rows=nut_rows(d.now, 'OL TEST')
d.supervisor.sensor_registry=[{'entity_id':'sensor.battery_runtime','device_id':'device_apc','name':'Battery runtime','disabled_by':'integration','can_enable':True,'runtime_measurement':True}]
d.app.refresh_power(settings=True)
d.app.save_power_settings({'source_id':'nut:device_apc','notifications':False,'low_battery_percent':25})
configure_phone(d.supervisor,d.now)
d.app.messages.begin('scan',{}); d.app.messages.process_task()
print(json.dumps({'status':d.app.snapshot(),'options':d.app.messages.options}))
d.doCleanups()
`], {cwd: root, encoding: 'utf8'}));

class Element {
  constructor(tag='div') {
    this.tag = tag; this.children = []; this.attributes = {}; this.listeners = new Map();
    this._text = ''; this._value = ''; this.checked = false; this.disabled = false; this.hidden = false;
    const classes = new Set();
    this.classList = {toggle: (name, state) => { if (state) classes.add(name); else classes.delete(name); }};
  }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text+this.children.map(child=>child.textContent).join(''); }
  set value(value) { this._value=String(value); }
  get value() { return this._value; }
  setAttribute(name,value) { this.attributes[name]=String(value); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text=''; this.children=[...children]; }
  addEventListener(name,fn,options={}) { const listeners=this.listeners.get(name)||[]; listeners.push({fn,options}); this.listeners.set(name,listeners); }
  dispatch(name) { const listeners=this.listeners.get(name)||[]; this.listeners.set(name,listeners.filter(item=>!item.options.once)); for(const item of listeners) item.fn({preventDefault(){}}); }
  showModal() { this.open=true; }
}
async function setup() {
  const nodes = new Map();
  for(const match of markup.matchAll(/<([a-z][a-z0-9]*)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
    const node = new Element(match[1]); node.hidden=/\bhidden\b/.test(match[0]); nodes.set(match[2],node);
  }
  const document = {getElementById: id => { assert(nodes.has(id), 'Missing element: '+id); return nodes.get(id); }, createElement: tag=>new Element(tag), createTextNode: text=>({textContent:String(text)})};
  const fixture=structuredClone(initial.status), options=structuredClone(initial.options), requests=[];
  const context=vm.createContext({document, Intl, Date, Number, Boolean, JSON, Math, String, Object, Array, Promise, AbortSignal, setInterval:()=>0,
    fetch: async (url,requestOptions) => { requests.push({url,options:requestOptions}); if(url==='api/enable-nut-sensor' && requestOptions.method==='POST') fixture.ups.sensor_settings.sensors=[]; if(url==='api/message-settings') fixture.messages.settings=JSON.parse(requestOptions.body); return {ok:true,json:async()=>structuredClone(url==='api/message-options'?options:fixture)}; }});
  vm.runInContext(script,context);
  await new Promise(setImmediate);
  return {context, fixture, requests, node:id=>document.getElementById(id), render:()=>context.render(structuredClone(fixture)), close:value=>{const dialog=document.getElementById('confirm-dialog');dialog.returnValue=value;dialog.dispatch('close');}};
}

async function main() {
  let ui=await setup();
  assert.equal(ui.node('view-overview').hidden,false);
  assert.equal(ui.node('view-setup').hidden,true);
  ui.node('nav-setup').onclick(); ui.render();
  assert.equal(ui.node('view-setup').hidden,false); // Intentional review remains available.
  ui.node('nav-overview').onclick();
  ui.fixture.checks.ok=false; ui.fixture.test_status='needs_retest'; ui.render();
  assert.equal(ui.node('view-setup').hidden,false);
  ui.fixture.checks.ok=true; ui.fixture.test_status='passed'; ui.render();
  assert.equal(ui.node('view-overview').hidden,false);

  ui=await setup(); ui.node('nav-calendar').onclick(); ui.node('schedule-form').dispatch('input');
  ui.fixture.checks.ok=false; ui.render();
  assert.equal(ui.node('view-calendar').hidden,false);
  assert.equal(ui.node('review-setup').hidden,false);

  ui=await setup();
  assert.deepEqual(ui.node('retry-requirements').children.map(row=>row.children.map(cell=>cell.textContent)), [['1','15 min','24 min'],['2','30 min','39 min'],['3','60 min','69 min']]);
  assert.match(ui.node('retry-feasibility').textContent,/conditional/);
  ui.node('recovery-first-retry').value=20; ui.node('recovery-form').dispatch('input');
  ui.render(); assert.equal(ui.node('recovery-first-retry').value,'20');
  assert.equal(ui.node('retry-requirements').children[0].children[2].textContent,'29 min');

  ui=await setup(); ui.node('nav-ups').onclick();
  const enable=ui.node('nut-sensor-list').children[0].children[1];
  assert.equal(enable.disabled,false);
  const enabling=enable.onclick(); ui.close('confirm'); await enabling;
  const post=ui.requests.find(request=>request.url==='api/enable-nut-sensor' && request.options.method==='POST');
  assert.deepEqual(JSON.parse(post.options.body),{confirmed:true,expected_source_id:'nut:device_apc',entity_id:'sensor.battery_runtime'});
  assert.equal(ui.node('nut-sensor-list').children.length,0);

  ui=await setup(); ui.fixture.ups.selected.power_state='battery'; ui.render();
  assert.equal(ui.node('nut-sensor-list').children[0].children[1].disabled,true);
  assert.equal(ui.requests.some(request=>request.options.method==='POST'),false);

  ui=await setup(); ui.fixture.checks.ok=false; ui.fixture.test_status='needs_retest';
  ui.fixture.schedule.calendar_entity_id=null; ui.render();
  assert.equal(ui.node('recovery-enabled').disabled,true);
  ui.node('recovery-retries').checked=false; ui.node('recovery-form').dispatch('input');
  assert.equal(ui.node('recovery-enabled').disabled,false);
  assert.equal(ui.node('rtc-retry-plan').hidden,true);
  assert.equal(ui.node('rtc-supply-confirmation').hidden,true);

  ui=await setup();
  ui.fixture.checks.ok=false; ui.fixture.recovery.settings.enabled=true; ui.fixture.recovery.settings.owner_confirmed=true;
  ui.fixture.recovery.protection_eligible=true; ui.fixture.recovery.emergency_active=true;
  ui.fixture.pending={kind:'ups',emergency:true,wake_epoch:null,remaining_seconds:30}; ui.render();
  assert.equal(ui.node('overview-protection').textContent,'Active');
  assert.equal(ui.node('cancel').hidden,false);
  assert.equal(ui.node('recovery-badge').textContent,'Enabled');
  ui.fixture.pending=null; ui.render();
  ui.node('recovery-enabled').checked=false; ui.node('recovery-form').dispatch('input');
  let disabling=ui.node('recovery-form').onsubmit({preventDefault(){}}); ui.close('cancel'); await disabling;
  assert.equal(ui.requests.some(request=>request.options.method==='POST'),false);
  disabling=ui.node('recovery-form').onsubmit({preventDefault(){}}); ui.close('confirm'); await disabling;
  const disable=ui.requests.find(request=>request.url==='api/recovery-settings' && request.options.method==='POST');
  assert.equal(JSON.parse(disable.options.body).confirmed_disable_emergency,true);

  ui=await setup(); ui.node('recovery-form').dispatch('input');
  ui.fixture.ups.settings.source_id='nut:changed_elsewhere'; ui.render();
  const saving=ui.node('recovery-form').onsubmit({preventDefault(){}}); await saving;
  const saved=ui.requests.find(request=>request.url==='api/recovery-settings' && request.options.method==='POST');
  assert.equal(JSON.parse(saved.options.body).expected_source_id,'nut:device_apc');

  ui=await setup(); ui.node('nav-messages').onclick();
  assert.equal(ui.node('view-messages').hidden,false);
  assert.equal(ui.node('message-enabled').checked,false);
  assert.equal(ui.node('send-message').disabled,true);
  assert.equal(ui.requests.some(request=>request.options.method==='POST'),false);
  ui.node('message-recipient').value='entity:notify.demo_phone'; ui.node('message-recipient').onchange();
  const include=ui.node('message-field-options').children[0].children[0].children[0];
  include.checked=true; include.onchange();
  assert.equal(ui.node('message-selected-fields').children.length,1);
  ui.fixture.checks.ok=false; ui.render();
  assert.equal(ui.node('view-messages').hidden,false); // Preserve the phone draft.
  assert.equal(ui.node('message-unsaved').hidden,false);
  await ui.node('preview-message').onclick();
  const preview=ui.requests.find(request=>request.url==='api/preview-message');
  assert.equal(JSON.parse(preview.options.body).settings.fields.length,1);
  assert.equal(ui.requests.some(request=>request.url==='api/send-message'),false);
  await ui.node('messages-form').onsubmit({preventDefault(){}});
  await new Promise(setImmediate);
  assert.equal(ui.node('message-unsaved').hidden,true);
  assert.equal(ui.node('send-message').disabled,false);
  let sending=ui.node('send-message').onclick(); ui.close('cancel'); await sending;
  assert.equal(ui.requests.some(request=>request.url==='api/send-message'),false);
  sending=ui.node('send-message').onclick(); ui.close('confirm'); await sending;
  const push=ui.requests.find(request=>request.url==='api/send-message');
  assert.equal(JSON.parse(push.options.body).confirmed,true);
  assert.equal(JSON.parse(push.options.body).expected_settings.recipient,'entity:notify.demo_phone');
  assert.equal(JSON.parse(push.options.body).expected_settings.fields.length,1);
  console.log('UI interaction checks passed: setup/tasks, draft retention, UPS boundaries, and phone discovery, field selection, preview, save, and explicit send confirmation. DOM fixture only; browser rendering is separate.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
