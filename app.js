const state={view:"overview",assets:["BTCUSDT","ETHUSDT"],timeframe:"1H",mode:"research",api:"/api/paper-state",scanApi:"/api/paper-scan",panels:JSON.parse(localStorage.getItem("orion-panels")||'{"equity":true,"signals":true,"research":true,"risk":true,"markets":true,"activity":true}')};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const paper={initial_equity:10000,equity:10000,closed_trades:0,realized_pnl:0};
let apiOnline=false,scanOnline=false,scanData={results:[],scanned_at:null},btReplayTimer=null,btReplayState=null,strategyHistory={versions:[],experiments:[]},researchIterations=[],lastLabRun=null;

function save(){localStorage.setItem("orion-panels",JSON.stringify(state.panels))}
function chips(){
  $("#asset-filters").innerHTML=["BTCUSDT","ETHUSDT","EURUSD","GBPUSD","NAS100","US30"].map(x=>'<button class="chip '+(state.assets.includes(x)?"active":"")+'" data-asset="'+x+'">'+x+"</button>").join("");
  $("#tf-filters").innerHTML=["15M","1H","4H","1D"].map(x=>'<button class="chip '+(state.timeframe===x?"active":"")+'" data-tf="'+x+'">'+x+"</button>").join("");
  $$("[data-asset]").forEach(b=>b.onclick=()=>{const x=b.dataset.asset;state.assets=state.assets.includes(x)?state.assets.filter(a=>a!==x):[...state.assets,x];chips();render()});
  $$("[data-tf]").forEach(b=>b.onclick=()=>{state.timeframe=b.dataset.tf;chips();render()});
}
function stat(title,value,sub,cls=""){return '<div class="card stat"><div class="card-title"><h3>'+title+"</h3></div><div class="big "+cls+'">'+value+'</div><div class="sub">'+sub+"</div></div>"}
function activeSignals(){return (scanData.results||[]).flatMap(r=>(r.candidates||[]).map(c=>({...c,timeframe:r.timeframe}))).filter(c=>c.valid)}
function renderOverview(){
  let c='<div class="grid">';
  if(state.panels.equity)c+=stat("Paper equity","$"+Number(paper.equity).toLocaleString(),"Initial: $"+Number(paper.initial_equity).toLocaleString());
  if(state.panels.signals)c+=stat("Signals",String(activeSignals().length),scanOnline?"Validated scanner candidates":"Scanner unavailable");
  if(state.panels.research)c+=stat("Research","ACTIVE","Historical backtests + replay","neutral");
  if(state.panels.risk)c+=stat("Risk / trade","0.50%","Hard risk veto enabled");
  if(state.panels.equity)c+='<section class="card wide"><div class="card-title"><h3>Equity curve</h3><span class="muted">Paper account</span></div><div class="chart"><div class="empty">Equity data will populate as paper trades close.</div></div></section>';
  if(state.panels.risk)c+='<section class="card side"><div class="card-title"><h3>Risk guardrails</h3><span class="pill">ARMED</span></div>'+[["Mode","PAPER"],["Auto execution","DISABLED"],["Risk / trade","0.50%"],["Daily loss limit","1.50%"],["Consecutive losses","3"],["Correlated exposure","2"]].map(r=>'<div class="metric-row"><span class="muted">'+r[0]+"</span><strong>"+r[1]+"</strong></div>").join("")+"</section>";
  if(state.panels.markets)c+='<section class="card full"><div class="card-title"><h3>Market watch</h3><span class="muted">'+state.timeframe+" • "+state.assets.length+' selected</span></div><table class="table"><thead><tr><th>Instrument</th><th>Regime</th><th>Signal</th><th>State</th></tr></thead><tbody>'+state.assets.map(x=>'<tr><td><strong>'+x+"</strong></td><td class="muted">"+(scanData.results.find(r=>r.instrument===x)?.regime||"Awaiting scan")+"</td><td>—</td><td><span class="pill">PAPER</span></td></tr>").join("")+"</tbody></table></section>";
  if(state.panels.activity)c+='<section class="card full"><div class="card-title"><h3>Scanner activity</h3><span class="muted">'+(scanData.scanned_at?new Date(scanData.scanned_at).toLocaleString():"Not scanned")+'</span></div><div class="empty">'+(scanOnline?"Market scan completed. Valid candidates are paper-only.":"Scanner unavailable; retrying automatically.")+"</div></section>";
  return c+"</div>";
}
function renderBacktests(){
  return '<div class="grid"><section class="card full"><div class="card-title"><h3>Backtest Lab</h3><span class="pill">RESEARCH ONLY</span></div><div class="sub">Run a historical simulation, then replay it candle-by-candle. No live orders are possible from this module.</div><div style="display:flex;gap:10px;margin-top:18px;flex-wrap:wrap"><select id="bt-asset"><option>BTCUSDT</option><option>ETHUSDT</option><option>EURUSD</option><option>GBPUSD</option><option>NAS100</option><option>US30</option></select><select id="bt-tf"><option>H1</option><option>H4</option><option>M15</option><option>D1</option></select><select id="bt-days"><option value="30">30 days</option><option value="90" selected>90 days</option><option value="180">180 days</option><option value="365">365 days</option></select><button class="primary" id="run-backtest">Run backtest</button></div><div id="bt-results" class="empty" style="margin-top:18px">Choose a market and run a historical simulation.</div></section></div>';
}
function renderStrategyLab(){
  const latestIteration=researchIterations[0];
  const iterationHtml=latestIteration ? '<div class="metric-row"><span><strong>Generation '+latestIteration.generation+' • '+latestIteration.status+'</strong><small> '+latestIteration.strategy_name+' v'+latestIteration.strategy_version+' • '+latestIteration.instrument+' • '+latestIteration.timeframe+'</small></span><div style="display:flex;gap:8px;flex-wrap:wrap"><button id="run-proposed-research" '+(latestIteration.status!=="PROPOSED"?"disabled":"")+'>Run Proposed</button><button id="reject-proposed-research" '+(latestIteration.status!=="PROPOSED"?"disabled":"")+'>Reject</button></div></div><div class="sub" style="margin-top:10px">Proposed grid: risk '+latestIteration.proposed_grid.risks.join(', ')+'% • stop '+latestIteration.proposed_grid.stops.join(', ')+' ATR • reward '+latestIteration.proposed_grid.rewards.join(', ')+'R</div><div class="sub" style="margin-top:6px">'+latestIteration.rationale+'</div>' : '<div class="empty">No next experiment proposed yet.</div>';
  const versions=strategyHistory.versions||[], experiments=strategyHistory.experiments||[];
  const vh=versions.length?versions.map(v=>'<div class="metric-row"><span><strong>'+v.name+' v'+v.version+'</strong><small> '+v.instrument+' • '+v.timeframe+' • '+v.status+'</small></span><button data-promote="'+v.strategy_id+'">Paper Candidate</button></div>').join(""):'<div class="empty">No saved versions.</div>';
  const eh=experiments.length?experiments.slice(0,10).map(e=>'<div class="metric-row"><span><strong>'+e.strategy_name+' v'+e.strategy_version+'</strong><small> '+e.instrument+' • '+e.timeframe+'</small></span><strong>'+((e.results||[]).length)+' runs</strong><button data-exp="'+e.experiment_id+'">Open Replay</button></div>').join(""):'<div class="empty">No experiment history.</div>';
  return '<div class="grid"><section class="card full"><div class="card-title"><h3>Strategy Lab</h3><span class="pill">EXPERIMENTS</span></div><div class="sub">Versioned strategy research with chronological validation. Results are persisted for later comparison.</div><div style="display:flex;gap:10px;margin-top:18px;flex-wrap:wrap"><input id="lab-name" value="ORION Trend"><input id="lab-version" value="1.0"><select id="lab-asset"><option>BTCUSDT</option><option>ETHUSDT</option></select><select id="lab-tf"><option>H1</option><option>H4</option><option>M15</option></select><select id="lab-days"><option value="30">30 days</option><option value="90" selected>90 days</option><option value="180">180 days</option></select><input id="lab-risks" value="0.25,0.5,0.75"><input id="lab-stops" value="1,1.5,2"><input id="lab-rewards" value="1.5,2,3"><button class="primary" id="run-lab">Run + Validate</button><button id="auto-research">Run ORION Research Engine</button><button id="analyze-research">Analyze Latest Experiment</button><button id="save-strategy">Save version</button></div><div id="lab-results" class="empty" style="margin-top:18px">The grid uses a 70/30 chronological split.</div><div id="research-engine-status" class="sub" style="margin-top:10px">Auto Research runs controlled parameter experiments, records them, and never promotes them automatically.</div></section><section class="card full"><div class="card-title"><h3>Next Research Iteration</h3><span class="pill">HUMAN APPROVAL</span></div><div class="sub">ORION proposes the next controlled grid from observed experiment data. It does not run the proposal until you explicitly approve it.</div><div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap"><button class="primary" id="generate-next-research">Generate Next Experiment</button></div><div id="research-iteration-panel" style="margin-top:14px">'+iterationHtml+'</div></section><section class="card full"><div class="card-title"><h3>Research Lineage</h3><span class="pill">HISTORY</span></div><div id="research-iteration-history" class="sub">Loading iteration history…</div></section><section class="card full"><div class="card-title"><h3>Cross-Experiment Intelligence</h3><span class="pill">MULTI-CONTEXT</span></div><div id="cross-research-intelligence" class="sub">Loading cross-experiment diagnostics…</div></section><section class="card full"><div class="card-title"><h3>Strategy Versions</h3><span class="pill">PERSISTENT</span></div><div id="strategy-versions">'+vh+'</div></section><section class="card full"><div class="card-title"><h3>Experiment History</h3><span class="pill">RESEARCH RECORD</span></div><div id="strategy-experiments">'+eh+'</div></section><section class="card full"><div class="card-title"><h3>Compare Experiments</h3><span class="pill">FACTUAL COMPARISON</span></div><div style="display:flex;gap:10px;flex-wrap:wrap"><select id="compare-a"></select><select id="compare-b"></select><button id="compare-run">Compare</button></div><div id="compare-results" class="empty" style="margin-top:14px">Select two recorded experiments.</div></section></div>';
}
function renderReplay(data){
  const box=$("#bt-results"),trades=data.trade_log||[],bars=data.replay||[];
  box.innerHTML='<div class="card" style="margin-bottom:14px"><div class="card-title"><h3>Market Replay</h3><span id="bt-candle-status" class="pill">CANDLE 0 / '+bars.length+'</span></div><div class="sub" id="bt-replay-time">HISTORICAL REPLAY — NOT LIVE MARKET</div><svg id="bt-market-chart" viewBox="0 0 900 320" preserveAspectRatio="none" style="width:100%;height:320px"></svg></div><div class="grid" style="margin:0"><div class="card stat"><div class="card-title"><h3>Equity</h3></div><div class="big" id="bt-replay-equity">$10,000</div><div class="sub" id="bt-replay-pnl">P&L $0.00</div></div><div class="card stat"><div class="card-title"><h3>Replay</h3><span id="bt-replay-status" class="pill">READY</span></div><div class="big" id="bt-replay-progress">0 / '+bars.length+'</div><div class="sub">Candles processed</div></div><div class="card stat"><div class="card-title"><h3>Drawdown</h3></div><div class="big" id="bt-replay-dd">0.00%</div><div class="sub" id="bt-replay-action">WAIT</div></div></div><div class="card" style="margin-top:14px"><div class="card-title"><h3>Replay controls</h3><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="primary" id="bt-play">▶ Play</button><button id="bt-step">Step</button><button id="bt-reset">Reset</button><select id="bt-speed"><option value="1600">0.25×</option><option value="700" selected>1×</option><option value="350">2×</option><option value="140">5×</option><option value="70">10×</option></select></div></div><div class="sub">Step advances exactly one historical candle. Entry/exit events and equity are synchronized to the replay.</div></div><div class="card" style="margin-top:14px"><div class="card-title"><h3>Equity curve</h3></div><div style="height:180px;overflow:hidden"><svg id="bt-equity-chart" viewBox="0 0 800 180" preserveAspectRatio="none" style="width:100%;height:100%"></svg></div></div><div class="card" style="margin-top:14px"><div class="card-title"><h3>Trade log</h3><span class="pill">'+trades.length+' trades</span></div><div id="bt-replay-log" class="activity"></div></div>';
  btReplayState={data,index:0,barIndex:0,equity:Number(data.initial_equity||10000),peak:Number(data.initial_equity||10000),position:null};
  drawReplay();
  $("#bt-play").onclick=()=>{if(btReplayTimer){clearInterval(btReplayTimer);btReplayTimer=null;$("#bt-play").textContent="▶ Play";return}$("#bt-play").textContent="Ⅱ Pause";btReplayTimer=setInterval(replayStep,Number($("#bt-speed").value));};
  $("#bt-speed").onchange=()=>{if(btReplayTimer){clearInterval(btReplayTimer);btReplayTimer=setInterval(replayStep,Number($("#bt-speed").value))}};
  $("#bt-step").onclick=replayStep;
  $("#bt-reset").onclick=()=>{if(btReplayTimer){clearInterval(btReplayTimer);btReplayTimer=null}btReplayState.index=0;btReplayState.barIndex=0;btReplayState.equity=Number(data.initial_equity||10000);btReplayState.peak=btReplayState.equity;btReplayState.position=null;drawReplay();$("#bt-play").textContent="▶ Play"};
}
function drawReplay(){
  const s=btReplayState;if(!s)return;const bars=s.data.replay||[],bar=bars[s.barIndex]||bars[0],n=bars.length;
  const chart=$("#bt-market-chart");
  if(bar&&chart){const slice=bars.slice(Math.max(0,s.barIndex-70),s.barIndex+1),lo=Math.min(...slice.map(x=>x.low)),hi=Math.max(...slice.map(x=>x.high)),span=hi-lo||1,w=900,h=320,p=22,step=(w-p*2)/Math.max(slice.length,1),bw=Math.max(3,step*.62);
    let svg=""; slice.forEach((x,i)=>{const xx=p+i*step+step/2,oy=h-p-(x.open-lo)/span*(h-p*2),cy=h-p-(x.close-lo)/span*(h-p*2),hy=h-p-(x.high-lo)/span*(h-p*2),ly=h-p-(x.low-lo)/span*(h-p*2);svg+='<line x1="'+xx+'" x2="'+xx+'" y1="'+hy+'" y2="'+ly+'" stroke="currentColor" opacity=".7"/><rect x="'+(xx-bw/2)+'" y="'+Math.min(oy,cy)+'" width="'+bw+'" height="'+Math.max(1,Math.abs(cy-oy))+'" fill="'+(x.close>=x.open?"currentColor":"transparent")+'" stroke="currentColor" opacity=".9"/>';if(x.action==="ENTER")svg+='<circle cx="'+xx+'" cy="'+cy+'" r="5" fill="currentColor"/>';if(x.action==="EXIT")svg+='<circle cx="'+xx+'" cy="'+cy+'" r="5" fill="transparent" stroke="currentColor" stroke-width="2"/>';});chart.innerHTML=svg}
  if(!bar)return;
  const dd=Number(bar.drawdown_pct||0),eq=Number(bar.equity||s.equity);s.equity=eq;s.peak=Math.max(s.peak,eq);
  $("#bt-candle-status").textContent="CANDLE "+(s.barIndex+1)+" / "+n;
  $("#bt-replay-time").textContent=new Date(bar.time).toLocaleString()+" • "+(bar.action||"WAIT")+" • HISTORICAL REPLAY";
  $("#bt-replay-equity").textContent="$"+eq.toLocaleString(undefined,{maximumFractionDigits:2});
  $("#bt-replay-pnl").textContent="P&L $"+(eq-Number(s.data.initial_equity||10000)).toFixed(2);
  $("#bt-replay-dd").textContent=dd.toFixed(2)+"%";
  $("#bt-replay-action").textContent=(bar.action||"WAIT")+(bar.position_status?" • "+bar.position_status:"");
  const entered=bar.action==="ENTER"; if(entered&&bar.trade)s.position=bar.trade; if(bar.action==="EXIT")s.position=null;
  const done=s.barIndex>=n-1;$("#bt-replay-status").textContent=done?"COMPLETE":s.barIndex===0?"READY":"REPLAYING";$("#bt-replay-progress").textContent=(s.barIndex+1)+" / "+n;
  const seen=(s.data.trade_log||[]).filter(t=>new Date(t.entry_time)<=new Date(bar.time));$("#bt-replay-log").innerHTML=seen.slice(-8).reverse().map((t,i)=>'<div class="activity-row"><span>#'+(seen.length-i)+' '+t.direction+'</span><span>'+t.reason+'</span><strong>'+Number(t.pnl).toFixed(2)+'</strong></div>').join("")||'<div class="empty">Press Play to begin.</div>';
  const curve=[Number(s.data.initial_equity||10000),...bars.slice(0,s.barIndex+1).map(x=>Number(x.equity||s.data.initial_equity||10000))];const min=Math.min(...curve),max=Math.max(...curve),range=max-min||1;const pts=curve.map((v,i)=>i/(curve.length-1||1)*790+5+","+((170-(v-min)/range*150))).join(" ");$("#bt-equity-chart").innerHTML='<polyline fill="none" stroke="currentColor" stroke-width="3" points="'+pts+'"/>';
}
function replayStep(){const s=btReplayState;if(!s)return;if(s.barIndex>=s.data.replay.length-1){if(btReplayTimer){clearInterval(btReplayTimer);btReplayTimer=null}drawReplay();return}s.barIndex++;drawReplay()}
async function runBacktest(){
  const box=$("#bt-results");box.textContent="Running historical simulation…";
  try{const a=$("#bt-asset").value,t=$("#bt-tf").value,d=$("#bt-days").value,r=await fetch("/api/backtest?instrument="+a+"&timeframe="+t+"&days="+d,{cache:"no-store"}),data=await r.json();if(!r.ok)throw new Error(data.error||"Backtest failed");renderReplay(data)}
  catch(e){box.textContent="Backtest error: "+e.message}
}
async function runLab(){
  const box=$("#lab-results");box.textContent="Running experiment grid…";
  try{const p=new URLSearchParams({instrument:$("#lab-asset").value,timeframe:$("#lab-tf").value,days:$("#lab-days").value,risks:$("#lab-risks").value,stops:$("#lab-stops").value,rewards:$("#lab-rewards").value});const r=await fetch("/api/backtest-batch?"+p.toString(),{cache:"no-store"}),d=await r.json();if(!r.ok)throw new Error(d.error||"Batch failed");lastLabRun=d;const rows=(d.results||[]).map((x,i)=>'<tr><td>'+(i+1)+'</td><td>'+x.risk_per_trade_pct+'%</td><td>'+x.atr_stop_multiple+' ATR</td><td>'+x.reward_multiple+'R</td><td>'+x.train.trades_count+' / '+x.test.trades_count+'</td><td>'+Number(x.train.total_return_pct).toFixed(2)+'% / '+Number(x.test.total_return_pct).toFixed(2)+'%</td><td>'+Number(x.test.max_drawdown_pct).toFixed(2)+'%</td><td>'+Number(x.test.win_rate_pct).toFixed(1)+'%</td><td>'+((x.test.profit_factor==null)?"∞":Number(x.test.profit_factor).toFixed(2))+'</td><td>'+Number(x.return_delta_pct).toFixed(2)+'%</td><td><button data-lab-replay data-result-index="'+i+'">Replay</button></td></tr>').join("");box.innerHTML='<div class="card-title"><h3>Validated experiments</h3><span class="pill">'+d.count+' runs</span></div><div class="sub">Validation: '+d.validation.method+' • '+d.validation.train_bars+' train bars / '+d.validation.test_bars+' unseen test bars</div><div style="overflow:auto"><table class="table"><thead><tr><th>#</th><th>Risk</th><th>Stop</th><th>Reward</th><th>Trades T/V</th><th>Return T/V</th><th>Test DD</th><th>Test WR</th><th>Test PF</th><th>Δ Return</th><th>Replay</th></tr></thead><tbody>'+rows+'</tbody></table></div><div class="sub" style="margin-top:12px">Training results are historical fit data; test results are out-of-sample for this run. No configuration is automatically promoted to paper trading.</div>'; const saved=await persistExperiment(d); await refreshStrategyHistory(); if(saved&&saved.experiment_id){$("[data-lab-replay]").forEach(b=>b.onclick=()=>openExperimentReplay(saved.experiment_id,Number(b.dataset.resultIndex)||0));}}
  catch(e){box.textContent="Experiment error: "+e.message}
}
async function runResearchEngine(){
  const box=$("#research-engine-status");
  const button=$("#auto-research");
  if(button)button.disabled=true;
  if(box)box.textContent="ORION Research Engine is running a controlled 27-run experiment…";
  try{
    const p=new URLSearchParams({
      instrument:$("#lab-asset").value,
      timeframe:$("#lab-tf").value,
      days:$("#lab-days").value,
      strategy_name:$("#lab-name").value,
      strategy_version:$("#lab-version").value
    });
    const r=await fetch("/api/research-engine",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(p)),cache:"no-store"});
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||"Research Engine failed");
    lastLabRun=d;
    if(box)box.textContent="Research complete: "+d.count+" controlled runs recorded. Validation used "+d.validation.train_bars+" train bars and "+d.validation.test_bars+" unseen test bars. No automatic promotion.";
    await refreshStrategyHistory();
  }catch(e){if(box)box.textContent="Research Engine error: "+e.message}
  finally{if(button)button.disabled=false}
}
async function refreshCrossResearch(){
  const el=$("#cross-research-intelligence"); if(!el)return;
  try{
    const r=await fetch("/api/research-cross?limit=100",{cache:"no-store"}),d=await r.json();
    if(!r.ok)throw new Error(d.error||"cross research unavailable");
    const contexts=d.contexts||[], cross=d.cross_context_strategies||[];
    const rows=contexts.slice(0,12).map(x=>'<tr><td>'+x.instrument+'</td><td>'+x.timeframe+'</td><td>'+x.experiments+'</td><td>'+Number(x.positive_experiment_pct).toFixed(0)+'%</td><td>'+Number(x.average_experiment_test_return_pct).toFixed(2)+'%</td><td>'+Number(x.test_return_spread_pct).toFixed(2)+'%</td></tr>').join("");
    el.innerHTML='<div>'+((d.facts||[]).join(" "))+'</div><div style="overflow:auto;margin-top:10px"><table class="table"><thead><tr><th>Asset</th><th>TF</th><th>Experiments</th><th>Positive contexts</th><th>Avg test return</th><th>Return spread</th></tr></thead><tbody>'+rows+'</tbody></table></div><div class="sub" style="margin-top:10px">'+(cross.length?cross.length+" strategy/version groups have multi-context observations.":"No strategy/version has yet been tested across multiple contexts.")+'</div>';
  }catch(e){el.textContent="Cross-experiment diagnostics unavailable: "+e.message}
}
async function refreshResearchIterations(){
  try{const r=await fetch("/api/research-iteration?limit=20",{cache:"no-store"}),d=await r.json();if(!r.ok)throw new Error(d.error||"iteration history unavailable");researchIterations=d.iterations||[];if(state.view==="research"){render();populateComparison();$("[data-exp]").forEach(b=>b.onclick=()=>openExperimentReplay(b.dataset.exp));bindResearchControls();renderIterationHistory()}}catch(e){}
}
async function generateNextResearch(){
  const ex=(strategyHistory.experiments||[])[0],box=$("#research-iteration-panel");if(!ex){if(box)box.textContent="Run or record an experiment first.";return}
  const b=$("#generate-next-research");if(b)b.disabled=true;if(box)box.textContent="Generating a controlled next-experiment proposal…";
  try{const r=await fetch("/api/research-iteration",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"generate",experiment_id:ex.experiment_id}),cache:"no-store"}),d=await r.json();if(!r.ok)throw new Error(d.error||"Proposal generation failed");await refreshResearchIterations()}catch(e){if(box)box.textContent="Proposal error: "+e.message}finally{if(b)b.disabled=false}
}
async function runProposedResearch(){
  const it=researchIterations.find(x=>x.status==="PROPOSED")||researchIterations[0],box=$("#research-iteration-panel");if(!it||it.status!=="PROPOSED"){if(box)box.textContent="No proposed iteration is ready to run.";return}
  const b=$("#run-proposed-research");if(b)b.disabled=true;if(box)box.textContent="Running the approved proposal…";
  try{const r=await fetch("/api/research-iteration",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"run",iteration_id:it.iteration_id}),cache:"no-store"}),d=await r.json();if(!r.ok)throw new Error(d.error||"Proposed experiment failed");await refreshStrategyHistory();await refreshResearchIterations()}catch(e){if(box)box.textContent="Iteration error: "+e.message}finally{if(b)b.disabled=false}
}
async function rejectProposedResearch(){
  const it=researchIterations.find(x=>x.status==="PROPOSED")||researchIterations[0];if(!it||it.status!=="PROPOSED")return;
  await fetch("/api/research-iteration",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"reject",iteration_id:it.iteration_id}),cache:"no-store"});await refreshResearchIterations(); await refreshCrossResearch();
}
function renderIterationHistory(){
  const el=$("#research-iteration-history");if(!el)return;
  if(!researchIterations.length){el.textContent="No research iterations recorded yet.";return}
  el.innerHTML=researchIterations.slice(0,10).map(it=>'<div class="metric-row"><span><strong>Gen '+it.generation+' • '+it.status+'</strong><small>'+it.instrument+' • '+it.timeframe+' • '+(it.strategy_name||"ORION")+' v'+(it.strategy_version||"?")+'</small></span><span><small>'+(it.child_experiment_id?"Experiment linked":"Proposal")+'</small></span></div>').join("");
}
function bindResearchControls(){
  if(state.view!=="research")return;
  $("#run-lab").onclick=runLab;$("#auto-research").onclick=runResearchEngine;$("#analyze-research").onclick=analyzeLatestResearch;$("#save-strategy").onclick=()=>saveStrategyVersion().catch(e=>alert(e.message));$("#generate-next-research").onclick=generateNextResearch;
  const run=$("#run-proposed-research");if(run)run.onclick=runProposedResearch;const reject=$("#reject-proposed-research");if(reject)reject.onclick=rejectProposedResearch;$("[data-promote]").forEach(b=>b.onclick=()=>promoteStrategy(b.dataset.promote).catch(e=>alert(e.message)));
}
async function analyzeLatestResearch(){
  const box=$("#research-engine-status"); const ex=(strategyHistory.experiments||[])[0];
  if(!ex){if(box)box.textContent="No recorded experiment is available to analyze.";return;}
  const button=$("#analyze-research"); if(button)button.disabled=true;
  if(box)box.textContent="ORION is analyzing parameter sensitivity, train/test stability, and grid behavior…";
  try{
    const r=await fetch("/api/research-insights?experiment_id="+encodeURIComponent(ex.experiment_id),{cache:"no-store"});
    const d=await r.json(); if(!r.ok)throw new Error(d.error||"Analysis failed");
    const s=(d.observed&&d.observed.sensitivity)||{};
    const fmt=(m)=>Object.entries(m||{}).map(x=>x[0]+": "+Number(x[1]).toFixed(2)+"%").join(" • ")||"—";
    const rows='<tr><td>Risk</td><td>'+fmt(s.risk_test_return_by_value)+'</td></tr><tr><td>ATR stop</td><td>'+fmt(s.stop_test_return_by_value)+'</td></tr><tr><td>Reward</td><td>'+fmt(s.reward_test_return_by_value)+'</td></tr>';
    box.innerHTML='<strong>Research Intelligence</strong><div style="margin-top:8px">'+(d.facts||[]).join(" ")+'</div><div style="overflow:auto;margin-top:10px"><table class="table"><thead><tr><th>Parameter</th><th>Average observed test return by grid value</th></tr></thead><tbody>'+rows+'</tbody></table></div><div class="sub" style="margin-top:10px">Diagnostics are descriptive. ORION does not infer future performance, rank configurations, or promote a strategy automatically.</div>';
  }catch(e){if(box)box.textContent="Research analysis error: "+e.message}
  finally{if(button)button.disabled=false}
}
async function persistExperiment(d){
  const payload={action:"experiment",strategy_name:$("#lab-name").value,strategy_version:$("#lab-version").value,instrument:d.instrument,timeframe:d.timeframe,days:d.days,grid:{risks:$("#lab-risks").value,stops:$("#lab-stops").value,rewards:$("#lab-rewards").value},validation:d.validation,results:d.results};
  const r=await fetch("/api/strategy-history",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const out=await r.json();if(!r.ok)throw new Error(out.error||"history save failed");return out.experiment;
}
async function openExperimentReplay(id,index=0){try{const r=await fetch('/api/experiment-replay?experiment_id='+encodeURIComponent(id)+'&result_index='+index,{cache:'no-store'}),d=await r.json();if(!r.ok)throw new Error(d.error||'Replay failed');state.view='backtests';render();renderReplay(d);window.scrollTo({top:0,behavior:'smooth'});}catch(e){alert(e.message)}}
function populateComparison(){
  const es=strategyHistory.experiments||[], a=$("#compare-a"), b=$("#compare-b"); if(!a||!b)return;
  const opts=es.map((e,i)=>'<option value="'+i+'">'+e.strategy_name+' v'+e.strategy_version+' • '+e.instrument+' '+e.timeframe+' • '+new Date(e.created_at).toLocaleString()+'</option>').join("");
  a.innerHTML=opts;b.innerHTML=opts;if(es.length>1)b.selectedIndex=1;
  $("#compare-run").onclick=()=>{const x=es[Number(a.value)],y=es[Number(b.value)],xm=(x.results||[])[0]||{},ym=(y.results||[])[0]||{},xt=xm.test||{},yt=ym.test||{};$("#compare-results").innerHTML='<div style="overflow:auto"><table class="table"><thead><tr><th>Metric</th><th>'+x.strategy_name+' v'+x.strategy_version+'</th><th>'+y.strategy_name+' v'+y.strategy_version+'</th></tr></thead><tbody>'+[['Instrument',x.instrument,y.instrument],['Timeframe',x.timeframe,y.timeframe],['Runs',(x.results||[]).length,(y.results||[]).length],['Test return',Number(xt.total_return_pct||0).toFixed(2)+'%',Number(yt.total_return_pct||0).toFixed(2)+'%'],['Test drawdown',Number(xt.max_drawdown_pct||0).toFixed(2)+'%',Number(yt.max_drawdown_pct||0).toFixed(2)+'%'],['Test win rate',Number(xt.win_rate_pct||0).toFixed(1)+'%',Number(yt.win_rate_pct||0).toFixed(1)+'%'],['Test profit factor',xt.profit_factor==null?'∞':Number(xt.profit_factor).toFixed(2),yt.profit_factor==null?'∞':Number(yt.profit_factor).toFixed(2)]].map(r=>'<tr><td>'+r[0]+'</td><td>'+r[1]+'</td><td>'+r[2]+'</td></tr>').join("")+'</tbody></table></div><div class="sub" style="margin-top:10px">This is a side-by-side factual comparison of the first recorded configuration in each experiment; it does not automatically select or promote a strategy.</div>'};
}
async function refreshStrategyHistory(){
  try{const r=await fetch("/api/strategy-history?limit=50",{cache:"no-store"}),d=await r.json();if(!r.ok)throw new Error(d.error||"history unavailable");strategyHistory={versions:d.versions||[],experiments:d.experiments||[]};if(state.view==="research"){render();populateComparison();$("[data-exp]").forEach(b=>b.onclick=()=>openExperimentReplay(b.dataset.exp));bindResearchControls()}}catch(e){}
}
async function saveStrategyVersion(){
  const payload={action:"version",name:$("#lab-name").value,version:$("#lab-version").value,instrument:$("#lab-asset").value,timeframe:$("#lab-tf").value,days:Number($("#lab-days").value),risks:$("#lab-risks").value,stops:$("#lab-stops").value,rewards:$("#lab-rewards").value,status:lastLabRun?"VALIDATED":"DRAFT"};
  const r=await fetch("/api/strategy-history",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw new Error(d.error||"save failed");await refreshStrategyHistory();
}
async function promoteStrategy(id){
  const r=await fetch("/api/strategy-history",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"promote",strategy_id:id,status:"PAPER_CANDIDATE"})}),d=await r.json();if(!r.ok)throw new Error(d.error||"promotion failed");await refreshStrategyHistory();
}
function render(){
  $("#page-title").textContent=state.view[0].toUpperCase()+state.view.slice(1);$("#mode-badge").textContent="RESEARCH";$(".live-state").innerHTML='<i class="dot '+(apiOnline?"green":"amber")+'"></i> '+(apiOnline?"Paper API online":"Paper API unavailable");
  $("#view").innerHTML=state.view==="overview"?renderOverview():state.view==="backtests"?renderBacktests():state.view==="research"?renderStrategyLab():'<div class="card full"><div class="card-title"><h3>'+state.view[0].toUpperCase()+state.view.slice(1)+'</h3><span class="pill">CONNECTED</span></div><div class="empty">Dashboard module ready for its ORION data adapter.</div></div>';
  if(state.view==="backtests")$("#run-backtest").onclick=runBacktest;
  if(state.view==="research"){ $("#run-lab").onclick=runLab; $("#auto-research").onclick=runResearchEngine; $("#analyze-research").onclick=analyzeLatestResearch; $("#save-strategy").onclick=()=>saveStrategyVersion().catch(e=>alert(e.message)); $("[data-promote]").forEach(b=>b.onclick=()=>promoteStrategy(b.dataset.promote).catch(e=>alert(e.message))); /*const arr=JSON.parse(localStorage.getItem("orion-strategies")||"[]");arr.unshift({name:$("#lab-name").value,version:$("#lab-version").value,asset:$("#lab-asset").value,timeframe:$("#lab-tf").value,days:$("#lab-days").value,risks:$("#lab-risks").value,stops:$("#lab-stops").value,rewards:$("#lab-rewards").value,saved_at:new Date().toLocaleString()});localStorage.setItem("orion-strategies",JSON.stringify(arr.slice(0,20)));render()}; */ }
}
function customize(){$("#panel-toggles").innerHTML=Object.entries({equity:"Equity & performance",signals:"Active signals",research:"Research status",risk:"Risk controls",markets:"Market watch",activity:"Recent activity"}).map(([k,v])=>'<div class="toggle-row"><span>'+v+'</span><button class="switch '+(state.panels[k]?"on":"")+'" data-panel="'+k+'"><i></i></button></div>').join("");$$("[data-panel]").forEach(b=>b.onclick=()=>{state.panels[b.dataset.panel]=!state.panels[b.dataset.panel];b.classList.toggle("on",state.panels[b.dataset.panel])});$("#customize-dialog").showModal()}
async function refreshPaperState(){try{const r=await fetch(state.api,{cache:"no-store"}),d=await r.json();if(!r.ok||d.mode!=="paper"||d.live_trading_enabled!==false)throw new Error("unsafe paper response");Object.assign(paper,d.account||{});apiOnline=true}catch(e){apiOnline=false}render()}
async function refreshScan(){try{const r=await fetch(state.scanApi,{cache:"no-store"}),d=await r.json();if(!r.ok||d.mode!=="paper"||d.live_trading_enabled!==false)throw new Error("unsafe scan response");scanData=d;scanOnline=true}catch(e){scanOnline=false}render()}
$$(".nav-item").forEach(b=>b.onclick=()=>{$$(".nav-item").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.view=b.dataset.view;render()});
$("#customize").onclick=customize;$("#refresh").onclick=refreshPaperState;$("#customize-dialog").addEventListener("close",()=>{save();render()});
chips();render();refreshPaperState();refreshScan();refreshStrategyHistory();refreshResearchIterations();refreshCrossResearch();setInterval(refreshPaperState,10000);setInterval(refreshScan,60000);
