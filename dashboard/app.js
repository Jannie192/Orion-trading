const state={view:"overview",assets:["BTCUSDT","ETHUSDT"],timeframe:"1H",mode:"paper",autoExecution:false,panels:JSON.parse(localStorage.getItem("orion-panels")||'{"equity":true,"signals":true,"research":true,"risk":true,"markets":true,"activity":true}')};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const panelNames={equity:"Equity & performance",signals:"Active signals",research:"Research status",risk:"Risk controls",markets:"Market watch",activity:"Recent activity"};
const paper={initial_equity:10000,equity:10000,open_orders:0,closed_trades:0,realized_pnl:0};
function save(){localStorage.setItem("orion-panels",JSON.stringify(state.panels))}
function chips(){
  $("#asset-filters").innerHTML=["BTCUSDT","ETHUSDT","EURUSD","GBPUSD","NAS100","US30"].map(x=>'<button class="chip '+(state.assets.includes(x)?"active":"")+'" data-asset="'+x+'">'+x+"</button>").join("");
  $("#tf-filters").innerHTML=["15M","1H","4H","1D"].map(x=>'<button class="chip '+(state.timeframe===x?"active":"")+'" data-tf="'+x+'">'+x+"</button>").join("");
  $$("[data-asset]").forEach(b=>b.onclick=()=>{const x=b.dataset.asset;state.assets=state.assets.includes(x)?state.assets.filter(a=>a!==x):[...state.assets,x];chips();render()});
  $$("[data-tf]").forEach(b=>b.onclick=()=>{state.timeframe=b.dataset.tf;chips();render()});
}
function stat(title,value,sub,cls=""){return '<div class="card stat"><div class="card-title"><h3>'+title+"</h3></div><div class="big "+cls+">"+value+'</div><div class="sub">'+sub+"</div></div>"}
function renderOverview(){let c='<div class="grid">';
if(state.panels.equity)c+=stat("Paper equity","$"+paper.equity.toLocaleString(),"Initial: $"+paper.initial_equity.toLocaleString());
if(state.panels.signals)c+=stat("Signals","—","Awaiting validated market scan","neutral");
if(state.panels.research)c+=stat("Research","VALIDATION","Live capital remains disconnected","neutral");
if(state.panels.risk)c+=stat("Risk / trade","0.50%","Hard risk veto enabled");
if(state.panels.equity)c+='<section class="card wide"><div class="card-title"><h3>Equity curve</h3><span class="muted">Paper account</span></div><div class="chart"><div class="empty">Equity data will populate automatically as paper trades close.</div></div></section>';
if(state.panels.risk)c+='<section class="card side"><div class="card-title"><h3>Risk guardrails</h3><span class="pill">ARMED</span></div>'+[["Mode","PAPER"],["Auto execution","DISABLED"],["Risk / trade","0.50%"],["Daily loss limit","1.50%"],["Consecutive losses","3"],["Correlated exposure","2"]].map(r=>'<div class="metric-row"><span class="muted">'+r[0]+"</span><strong>"+r[1]+"</strong></div>").join("")+"</section>";
if(state.panels.markets)c+='<section class="card full"><div class="card-title"><h3>Market watch</h3><span class="muted">'+state.timeframe+" • "+state.assets.length+' selected</span></div><table class="table"><thead><tr><th>Instrument</th><th>Regime</th><th>Signal</th><th>State</th></tr></thead><tbody>'+state.assets.map(x=>'<tr><td><strong>'+x+"</strong></td><td class="muted">Awaiting scan</td><td>—</td><td><span class="pill">PAPER</span></td></tr>").join("")+"</tbody></table></section>";
if(state.panels.activity)c+='<section class="card full"><div class="card-title"><h3>Activity</h3><span class="muted">'+paper.closed_trades+' closed trades</span></div><div class="empty">Paper fills, risk decisions, journal events and system errors will appear here.</div></section>';
return c+"</div>"}
function render(){const title=state.view[0].toUpperCase()+state.view.slice(1);$("#page-title").textContent=title;$("#mode-badge").textContent=state.mode.toUpperCase();$("#view").innerHTML=state.view==="overview"?renderOverview():'<div class="card full"><div class="card-title"><h3>'+title+'</h3><span class="pill">CONNECTED</span></div><div class="empty">Dashboard module ready for its ORION data adapter.</div></div>'}
function customize(){$("#panel-toggles").innerHTML=Object.entries(panelNames).map(([k,v])=>'<div class="toggle-row"><span>'+v+'</span><button class="switch '+(state.panels[k]?"on":"")+'" data-panel="'+k+'"><i></i></button></div>').join("");$$("[data-panel]").forEach(b=>b.onclick=()=>{const k=b.dataset.panel;state.panels[k]=!state.panels[k];b.classList.toggle("on",state.panels[k])});$("#customize-dialog").showModal()}
$$(".nav-item").forEach(b=>b.onclick=()=>{$$(".nav-item").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.view=b.dataset.view;render()});$("#customize").onclick=customize;$("#refresh").onclick=()=>{render();$("#refresh").textContent="✓";setTimeout(()=>$("#refresh").textContent="↻",700)};$("#customize-dialog").addEventListener("close",()=>{save();render()});chips();render();