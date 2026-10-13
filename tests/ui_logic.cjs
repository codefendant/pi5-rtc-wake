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
class Demo(unittest.TestCase,Fixture): pass
d=Demo(); d.setup_app()
print(json.dumps({'status':d.app.snapshot()}))
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
  const fixture=structuredClone(initial.status), requests=[];
  const context=vm.createContext({document, Intl, Date, Number, Boolean, JSON, Math, String, Object, Array, Promise, AbortSignal, setInterval:()=>0,
    fetch: async (url,requestOptions) => { requests.push({url,options:requestOptions}); if(url==='api/connect-dashboard') fixture.dashboard={...fixture.dashboard,connected:true,restart_needed:true}; return {ok:true,json:async()=>structuredClone(fixture)}; }});
  vm.runInContext(script,context);
  await new Promise(setImmediate);
  return {context, fixture, requests, node:id=>document.getElementById(id), render:()=>context.render(structuredClone(fixture)), close:value=>{const dialog=document.getElementById('confirm-dialog');dialog.returnValue=value;dialog.dispatch('close');}};
}

async function main() {
  const ui=await setup();
  assert.equal(ui.node('connect-dashboard').hidden,false);
  assert.equal(ui.node('connect-dashboard').disabled,false);
  assert.equal(ui.node('open-dashboard').hidden,true);
  assert.equal(ui.node('connection-steps').hidden,false);
  assert.equal(ui.node('permission-guide').hidden,true);
  assert.equal(ui.requests.some(request=>request.options.method==='POST'),false);
  let connecting=ui.node('connect-dashboard').onclick(); ui.close('cancel'); await connecting;
  assert.equal(ui.requests.some(request=>request.options.method==='POST'),false);
  connecting=ui.node('connect-dashboard').onclick(); ui.close('confirm'); await connecting;
  const post=ui.requests.find(request=>request.url==='api/connect-dashboard');
  assert.deepEqual(JSON.parse(post.options.body),{confirmed:true});
  assert.equal(post.options.headers['X-Pi5-CSRF'],ui.fixture.csrf);
  assert.equal(ui.node('restart-link').hidden,false);
  assert.match(ui.node('connection-message').textContent,/Restart Home Assistant to finish Pi Wake & Sleep setup/);
  ui.fixture.dashboard.restart_notice_ok=false; ui.render();
  assert.match(ui.node('connection-message').textContent,/notification could not be created/);
  ui.fixture.dashboard.restart_notice_ok=true; ui.render();
  assert.equal(ui.node('connect-dashboard').hidden,true);
  assert.equal(ui.node('connection-steps').hidden,false); // Installation is not a live connection.
  assert.equal(ui.node('open-dashboard').hidden,true); // A new install must not link to a nonexistent dashboard.
  ui.fixture.dashboard.restart_needed=false; ui.render();
  assert.match(ui.node('connection-message').textContent,/Under Discovered/);
  ui.fixture.dashboard.active=true; ui.render();
  assert.equal(ui.node('open-dashboard').hidden,true); // Contact alone is not successful creation.
  ui.fixture.dashboard.setup_error={message:'Dashboard could not be created.',action:'Reconnect in Devices & services.'}; ui.render();
  assert.match(ui.node('connection-message').textContent,/could not be created/);
  assert.match(ui.node('support-text').value,/Reconnect in Devices/);
  ui.fixture.dashboard.ready=true; ui.fixture.dashboard.setup_error=null; ui.render();
  assert.equal(ui.node('open-dashboard').hidden,false);
  assert.equal(ui.node('connection-heading').textContent,'Your dashboard is connected');
  assert.equal(ui.node('connection-steps').hidden,true);
  assert.equal(ui.node('connected-help').hidden,false);
  ui.node('maintenance').open=true; ui.node('check-details').open=true; ui.render();
  assert.equal(ui.node('maintenance').open,true);
  assert.equal(ui.node('check-details').open,true);
  ui.fixture.permissions.protected=true; ui.render();
  assert.equal(ui.node('permission-guide').hidden,true); // Guidance remains on the dashboard when connected.
  ui.fixture.dashboard.active=false; ui.render();
  assert.equal(ui.node('permission-guide').hidden,false);
  assert.equal(ui.node('app-info').href,'/config/app/local_pi5_rtc_wake/info');
  ui.fixture.pending={kind:'schedule'}; ui.render();
  assert.equal(ui.node('reconnect-dashboard').disabled,true);
  assert.equal(ui.node('check').disabled,true);
  ui.fixture.pending=null; ui.fixture.shutdown_requested=true; ui.fixture.recovery_check_allowed=true; ui.render();
  assert.equal(ui.node('check').disabled,false);
  assert.equal(ui.node('reconnect-dashboard').disabled,true);
  assert.equal(/id="(?:schedule-form|recovery-form|messages-form|assist-form|keep-awake|test|prepare|reboot)"/.test(markup),false);
  console.log('Maintenance UI checks passed: first connection, confirmation/CSRF, live connection guidance, persistent dropdowns, protected-mode help, diagnostic boundaries, and no duplicate feature controls. DOM fixture only.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
