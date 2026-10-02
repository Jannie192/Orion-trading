const state={view:"overview",assets:["BTCUSDT","ETHUSDT"],timeframe:"1H",mode:"paper",autoExecution:false,api:"/api/paper-state",scanApi:"/api/paper-scan",panels:JSON.parse(localStorage.getItem("orion-panels")||'{"equity":true,"signals":true,"research":true,"risk":true,"markets":true,"activity":true}')};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const panelNames={equity:"Equity & performance",signals:"Active signals",research:"Research status",risk:"Risk controls",markets:"Market watch",activity:"Recent activity"};
const paper={initial_equity:10000,equity:10000,open_orders:0,closed_trades:0,realized_pnl:0};
let apiOnline=false,scanOnline=false,scanData={results:[],scanned_at:null};

function save(){localStorage.setItem("orion-panels",JSON.stringify(state.panels))}
function chips(){
  $("#asset-filters").innerHTML=["BTCUSDT","ETHUSDT","EURUSD","GBPUSD","NAS100","US30"].map(x=>'<button class="chip '+(state.assets.includes(x)?"active":"")+'" data-asset="'+x+'">'+x+"</button>").join("");
  $("#tf-filters").innerHTML=["15M","1H","4H","1D"].map(x=>'<button class="chip '+(state.timeframe===x?"active":"")+'" data-tf="'+x+'">'+x+"</button>").join("");
  $$("[data-asset]").forEach(b=>b.onclick=()=>{const x=b.dataset.asset;state.assets=state.assets.includes(x)?state.assets.filter(a=>a!==x):[...state.assets,x];chips();render()});
  $$("[data-tf]").forEach(b=>b.onclick=()=>{state.timeframe=b.dataset.tf;chips();render()});
}
function stat(title,value,sub,cls=""){return '<div class="card stat"><div class="card-title"><h3>'+title+"</h3></div><div class="big "+cls+'">'+value+'</div><div class="sub">'+sub+"</div></div>"}
function activeSignals(){return scanData.results.flatMap(r=>r.candidates.map(c=>({...c,timeframe:r.timeframe}))).filter(c=>c.valid)}
function renderOverview(){let c='<div class="grid">';
if(state.panels.equity)c+=stat("Paper equity","$"+paper.equity.toLocaleString(),"Initial: $"+paper.initial_equity.toLocaleString());
if(state.panels.signals){const n=activeSignals().length;c+=stat("Signals",String(n),scanOnline?"Validated scanner candidates":"Scanner unavailable",n?"":"neutral");}
if(state.panels.research)c+=stat("Research","VALIDATION","Live capital remains disconnected","neutral");
if(state.panels.risk)c+=stat("Risk / trade","0.50%","Hard risk veto enabled");
if(state.panels.equity)c+='<section class="card wide"><div class="card-title"><h3>Equity curve</h3><span class="muted">Paper account</span></div><div class="chart"><div class="empty">Equity data will populate automatically as paper trades close.</div></div></section>';
if(state.panels.risk)c+='<section class="card side"><div class="card-title"><h3>Risk guardrails</h3><span class="pill">ARMED</span></div>'+[["Mode","PAPER"],["Auto execution","DISABLED"],["Risk / trade","0.50%"],["Daily loss limit","1.50%"],["Consecutive losses","3"],["Correlated exposure","2"]].map(r=>'<div class="metric-row"><span class="muted">'+r[0]+"</span><strong>"+r[1]+"</strong></div>").join("")+"</section>";
if(state.panels.markets)c+='<section class="card full"><div class="card-title"><h3>Market watch</h3><span class="muted">'+state.timeframe+" • "+state.assets.length+' selected</span></div><table class="table"><thead><tr><th>Instrument</th><th>Regime</th><th>Signal</th><th>State</th></tr></thead><tbody>'+state.assets.map(x=>'<tr><td><strong>'+x+"</strong></td><td class="muted">Awaiting scan</td><td>—</td><td><span class="pill">PAPER</span></td></tr>").join("")+"</tbody></table></section>";
if(state.panels.activity)c+='<section class="card full"><div class="card-title"><h3>Scanner activity</h3><span class="muted">'+(scanData.scanned_at?new Date(scanData.scanned_at).toLocaleString():"Not scanned")+'</span></div><div class="empty">'+(scanOnline?"Market scan completed. Valid candidates are persisted as paper orders only.":"Scanner unavailable; retrying automatically.")+'</div></section>';
return c+"</div>"}
function renderBacktests(){
  return '<div class="grid"><section class="card full"><div class="card-title"><h3>Backtest engine</h3><span class="pill">RESEARCH ONLY</span></div><div class="sub">Walk-forward simulation using ORION signals, ATR stops, 2R targets and 0.50% risk per trade. No live orders.</div><div style="display:flex;gap:10px;margin-top:18px;flex-wrap:wrap"><select id="bt-asset"><option>BTCUSDT</option><option>ETHUSDT</option><option>EURUSD</option><option>GBPUSD</option><option>NAS100</option><option>US30</option></select><select id="bt-tf"><option>H1</option><option>H4</option><option>M15</option><option>D1</option></select><select id="bt-days"><option value="30">30 days</option><option value="90" selected>90 days</option><option value="180">180 days</option><option value="365">365 days</option></select><button class="primary" id="run-backtest">Run backtest</button></div><div id="bt-results" class="empty" style="margin-top:18px">Choose a market and run a historical simulation.</div></section></div>'
}
let btReplayTimer=null,btReplayState=null;
function renderReplay(data){
  const box=$("#bt-results");
  const trades=data.trade_log||[], curve=data.equity_curve||[];
  box.innerHTML='<div class="grid" style="margin:0"><div class="card stat"><div class="card-title"><h3>Replay</h3><span id="bt-replay-status" class="pill">READY</span></div><div class="big" id="bt-replay-equity">
  const box=$("#bt-results"); box.textContent="Running historical simulation…";
  try{
    const a=$("#bt-asset").value,t=$("#bt-tf").value,d=$("#bt-days").value;
    const r=await fetch("/api/backtest?instrument="+encodeURIComponent(a)+"&timeframe="+encodeURIComponent(t)+"&days="+d,{cache:"no-store"});
    const data=await r.json(); if(!r.ok) throw new Error(data.error||"Backtest failed");
    box.innerHTML='<div class="grid" style="margin:0">'+[
      ["Final equity","$"+Number(data.final_equity).toLocaleString(undefined,{maximumFractionDigits:2})],
      ["Return",Number(data.total_return_pct).toFixed(2)+"%"],
      ["Trades",data.trades_count],
      ["Win rate",Number(data.win_rate_pct).toFixed(1)+"%"],
      ["Profit factor",Number(data.profit_factor).toFixed(2)],
      ["Max drawdown",Number(data.max_drawdown_pct).toFixed(2)+"%"]
    ].map(x=>'<div class="card stat"><div class="card-title"><h3>'+x[0]+'</h3></div><div class="big">'+x[1]+'</div></div>').join("")+'</div><div class="sub" style="margin-top:14px">Historical simulation only. Results can change with data, costs, slippage and execution assumptions.</div><div class="card" style="margin-top:14px"><div class="card-title"><h3>Trade-by-trade replay</h3><span class="pill">'+data.trades_count+' trades</span></div><div id="bt-trades"></div></div>';
    renderReplay(data); const rows=(data.trade_log||[]).map((t,i)=>'<div class="activity-row"><span>#'+(i+1)+' '+t.direction+'</span><span>'+t.reason+'</span><strong>'+Number(t.pnl).toFixed(2)+'</strong></div>').join("");
    $("#bt-trades").innerHTML=rows||'<div class="empty">No trades in this test window.</div>'; $("#bt-play").onclick=()=>{if(btReplayTimer)return;btReplayTimer=setInterval(()=>{if(!btReplayState||btReplayState.index>=btReplayState.trades.length){clearInterval(btReplayTimer);btReplayTimer=null;return}replayStep()},700)}; $("#bt-step").onclick=replayStep; $("#bt-reset").onclick=()=>{if(btReplayTimer){clearInterval(btReplayTimer);btReplayTimer=null}btReplayState.index=0;btReplayState.equity=Number(data.initial_equity||10000);drawReplay()};
  }catch(e){box.textContent="Backtest error: "+e.message}
}
function render(){
  const title=state.view[0].toUpperCase()+state.view.slice(1);
  $("#page-title").textContent=title;
  $("#mode-badge").textContent=state.mode.toUpperCase();
  $(".live-state").innerHTML='<i class="dot '+(apiOnline?"green":"amber")+'"></i> '+(apiOnline?"Paper API online":"Paper API unavailable");
  $("#view").innerHTML=state.view==="overview"?renderOverview():state.view==="backtests"?renderBacktests():'<div class="card full"><div class="card-title"><h3>'+title+'</h3><span class="pill">CONNECTED</span></div><div class="empty">Dashboard module ready for its ORION data adapter.</div></div>'
}
function customize(){
  $("#panel-toggles").innerHTML=Object.entries(panelNames).map(([k,v])=>'<div class="toggle-row"><span>'+v+'</span><button class="switch '+(state.panels[k]?"on":"")+'" data-panel="'+k+'"><i></i></button></div>').join("");
  $$("[data-panel]").forEach(b=>b.onclick=()=>{const k=b.dataset.panel;state.panels[k]=!state.panels[k];b.classList.toggle("on",state.panels[k])});
  $("#customize-dialog").showModal()
}
async function refreshScan(){
  try{
    const response=await fetch(state.scanApi,{cache:"no-store",headers:{"Accept":"application/json"}});
    if(!response.ok)throw new Error("HTTP "+response.status);
    const data=await response.json();
    if(data.mode!=="paper"||data.live_trading_enabled!==false)throw new Error("Unsafe scanner response");
    scanData=data; scanOnline=true;
  }catch(error){scanOnline=false;console.warn("ORION scanner unavailable:",error)}
  render();
}
async function refreshPaperState(){
  try{
    const response=await fetch(state.api,{cache:"no-store",headers:{"Accept":"application/json"}});
    if(!response.ok)throw new Error("HTTP "+response.status);
    const data=await response.json();
    if(data.mode!=="paper"||data.live_trading_enabled!==false)throw new Error("Unsafe paper-state response");
    Object.assign(paper,data.account||{});
    apiOnline=true;
  }catch(error){
    apiOnline=false;
    console.warn("ORION paper state unavailable:",error);
  }
  render();
}
$(".nav-item").forEach(b=>b.onclick=()=>{$(".nav-item").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.view=b.dataset.view;render();if(state.view==="backtests"){$("#run-backtest").onclick=runBacktest}});
$("#customize").onclick=customize;
$("#refresh").onclick=async()=>{await refreshPaperState();$("#refresh").textContent="✓";setTimeout(()=>$("#refresh").textContent="↻",700)};
$("#customize-dialog").addEventListener("close",()=>{save();render()});
chips();
render();
refreshPaperState();
refreshScan();
setInterval(refreshPaperState,10000);
setInterval(refreshScan,60000);
+Number(data.initial_equity||10000).toLocaleString(undefined,{maximumFractionDigits:2})+'</div><div class="sub">Equity</div></div><div class="card stat"><div class="card-title"><h3>Progress</h3></div><div class="big" id="bt-replay-progress">0 / '+trades.length+'</div><div class="sub">Trades replayed</div></div></div><div class="card" style="margin-top:14px"><div class="card-title"><h3>Market replay</h3><div style="display:flex;gap:8px"><button class="primary" id="bt-play">▶ Play</button><button id="bt-step">Step</button><button id="bt-reset">Reset</button></div></div><div id="bt-replay-log" class="activity"></div></div><div class="card" style="margin-top:14px"><div class="card-title"><h3>Equity curve</h3></div><div style="height:180px;overflow:hidden"><svg id="bt-equity-chart" viewBox="0 0 800 180" preserveAspectRatio="none" style="width:100%;height:100%"></svg></div></div>';
  btReplayState={data,trades,curve,index:0,equity:Number(data.initial_equity||10000)};
  drawReplay();
}
function drawReplay(){
  if(!btReplayState)return;
  const s=btReplayState,t=s.trades[s.index-1],n=s.trades.length;
  $("#bt-replay-progress").textContent=s.index+" / "+n;
  $("#bt-replay-equity").textContent="$"+s.equity.toLocaleString(undefined,{maximumFractionDigits:2});
  $("#bt-replay-status").textContent=s.index>=n?"COMPLETE":"REPLAYING";
  $("#bt-replay-log").innerHTML=s.trades.slice(0,s.index).slice(-8).reverse().map((x,i)=>'<div class="activity-row"><span>#'+(s.index-i)+' '+x.direction+'</span><span>'+x.reason+'</span><strong>'+Number(x.pnl).toFixed(2)+'</strong></div>').join("")||'<div class="empty">Press Play to begin the historical replay.</div>';
  const vals=[Number(s.data.initial_equity||10000),...s.curve.slice(0,s.index).map(x=>Number(x.equity))];
  const min=Math.min(...vals),max=Math.max(...vals),range=max-min||1;
  const pts=vals.map((v,i)=>((i/(vals.length-1||1))*790+5)+","+(170-((v-min)/range)*150)).join(" ");
  $("#bt-equity-chart").innerHTML='<polyline fill="none" stroke="currentColor" stroke-width="3" points="'+pts+'"/>';
}
function replayStep(){
  const s=btReplayState;if(!s||s.index>=s.trades.length)return;
  s.equity+=Number(s.trades[s.index].pnl||0);s.index++;drawReplay();
}
async function runBacktest(){
  const box=$("#bt-results"); box.textContent="Running historical simulation…";
  try{
    const a=$("#bt-asset").value,t=$("#bt-tf").value,d=$("#bt-days").value;
    const r=await fetch("/api/backtest?instrument="+encodeURIComponent(a)+"&timeframe="+encodeURIComponent(t)+"&days="+d,{cache:"no-store"});
    const data=await r.json(); if(!r.ok) throw new Error(data.error||"Backtest failed");
    box.innerHTML='<div class="grid" style="margin:0">'+[
      ["Final equity","$"+Number(data.final_equity).toLocaleString(undefined,{maximumFractionDigits:2})],
      ["Return",Number(data.total_return_pct).toFixed(2)+"%"],
      ["Trades",data.trades_count],
      ["Win rate",Number(data.win_rate_pct).toFixed(1)+"%"],
      ["Profit factor",Number(data.profit_factor).toFixed(2)],
      ["Max drawdown",Number(data.max_drawdown_pct).toFixed(2)+"%"]
    ].map(x=>'<div class="card stat"><div class="card-title"><h3>'+x[0]+'</h3></div><div class="big">'+x[1]+'</div></div>').join("")+'</div><div class="sub" style="margin-top:14px">Historical simulation only. Results can change with data, costs, slippage and execution assumptions.</div><div class="card" style="margin-top:14px"><div class="card-title"><h3>Trade-by-trade replay</h3><span class="pill">'+data.trades_count+' trades</span></div><div id="bt-trades"></div></div>';
    const rows=(data.trade_log||[]).map((t,i)=>'<div class="activity-row"><span>#'+(i+1)+' '+t.direction+'</span><span>'+t.reason+'</span><strong>'+Number(t.pnl).toFixed(2)+'</strong></div>').join("");
    $("#bt-trades").innerHTML=rows||'<div class="empty">No trades in this test window.</div>';
  }catch(e){box.textContent="Backtest error: "+e.message}
}
function render(){
  const title=state.view[0].toUpperCase()+state.view.slice(1);
  $("#page-title").textContent=title;
  $("#mode-badge").textContent=state.mode.toUpperCase();
  $(".live-state").innerHTML='<i class="dot '+(apiOnline?"green":"amber")+'"></i> '+(apiOnline?"Paper API online":"Paper API unavailable");
  $("#view").innerHTML=state.view==="overview"?renderOverview():state.view==="backtests"?renderBacktests():'<div class="card full"><div class="card-title"><h3>'+title+'</h3><span class="pill">CONNECTED</span></div><div class="empty">Dashboard module ready for its ORION data adapter.</div></div>'
}
function customize(){
  $("#panel-toggles").innerHTML=Object.entries(panelNames).map(([k,v])=>'<div class="toggle-row"><span>'+v+'</span><button class="switch '+(state.panels[k]?"on":"")+'" data-panel="'+k+'"><i></i></button></div>').join("");
  $$("[data-panel]").forEach(b=>b.onclick=()=>{const k=b.dataset.panel;state.panels[k]=!state.panels[k];b.classList.toggle("on",state.panels[k])});
  $("#customize-dialog").showModal()
}
async function refreshScan(){
  try{
    const response=await fetch(state.scanApi,{cache:"no-store",headers:{"Accept":"application/json"}});
    if(!response.ok)throw new Error("HTTP "+response.status);
    const data=await response.json();
    if(data.mode!=="paper"||data.live_trading_enabled!==false)throw new Error("Unsafe scanner response");
    scanData=data; scanOnline=true;
  }catch(error){scanOnline=false;console.warn("ORION scanner unavailable:",error)}
  render();
}
async function refreshPaperState(){
  try{
    const response=await fetch(state.api,{cache:"no-store",headers:{"Accept":"application/json"}});
    if(!response.ok)throw new Error("HTTP "+response.status);
    const data=await response.json();
    if(data.mode!=="paper"||data.live_trading_enabled!==false)throw new Error("Unsafe paper-state response");
    Object.assign(paper,data.account||{});
    apiOnline=true;
  }catch(error){
    apiOnline=false;
    console.warn("ORION paper state unavailable:",error);
  }
  render();
}
$(".nav-item").forEach(b=>b.onclick=()=>{$(".nav-item").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.view=b.dataset.view;render();if(state.view==="backtests"){$("#run-backtest").onclick=runBacktest}});
$("#customize").onclick=customize;
$("#refresh").onclick=async()=>{await refreshPaperState();$("#refresh").textContent="✓";setTimeout(()=>$("#refresh").textContent="↻",700)};
$("#customize-dialog").addEventListener("close",()=>{save();render()});
chips();
render();
refreshPaperState();
refreshScan();
setInterval(refreshPaperState,10000);
setInterval(refreshScan,60000);
