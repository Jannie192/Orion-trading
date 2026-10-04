<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ORION // Trading Command Center</title>
<style>
:root{--bg:#05070a;--panel:#0a0f14;--panel2:#0d141b;--line:#182630;--text:#e9f3f7;--muted:#718692;--cyan:#43e8ff;--green:#55f2a0;--red:#ff5f73;--amber:#ffc857}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% -10%,#0e2028 0,#05070a 42%);color:var(--text);font:13px/1.45 Inter,system-ui,sans-serif}body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.18;background-image:linear-gradient(#1a2b33 1px,transparent 1px),linear-gradient(90deg,#1a2b33 1px,transparent 1px);background-size:48px 48px}
.wrap{max-width:1600px;margin:auto;padding:20px;position:relative}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.brand{letter-spacing:.24em;font-weight:800;font-size:18px}.brand span{color:var(--cyan)}.status{display:flex;gap:8px;align-items:center;color:var(--muted)}.dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 14px var(--green)}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}.card{background:linear-gradient(145deg,rgba(13,20,27,.96),rgba(7,11,15,.96));border:1px solid var(--line);border-radius:12px;padding:15px;box-shadow:0 12px 35px #0008}.span3{grid-column:span 3}.span4{grid-column:span 4}.span6{grid-column:span 6}.span8{grid-column:span 8}.span12{grid-column:span 12}.label{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.14em}.value{font-size:25px;font-weight:750;margin-top:4px}.sub{color:var(--muted);font-size:11px}.green{color:var(--green)}.red{color:var(--red)}.cyan{color:var(--cyan)}.amber{color:var(--amber)}h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;margin:0 0 12px}.bar{height:7px;background:#15212a;border-radius:10px;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,var(--cyan),var(--green));border-radius:10px}.table{width:100%;border-collapse:collapse;font-size:11px}.table th{text-align:left;color:var(--muted);font-weight:500;padding:8px;border-bottom:1px solid var(--line)}.table td{padding:8px;border-bottom:1px solid #12202a}.pill{display:inline-block;padding:3px 7px;border-radius:99px;background:#111d24;border:1px solid #20313b}.empty{color:var(--muted);padding:18px;text-align:center}.chart{height:150px;display:flex;align-items:end;gap:3px;padding-top:8px}.barc{flex:1;background:linear-gradient(to top,var(--cyan),#2b7481);min-width:2px;border-radius:2px 2px 0 0;opacity:.8}.gate{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--line)}.gate b{font-size:11px}.small{font-size:10px;color:var(--muted)}@media(max-width:900px){.span3,.span4,.span6,.span8{grid-column:span 12}.wrap{padding:12px}.table{min-width:700px}.scroll{overflow:auto}}
</style></head><body><div class="wrap">
<div class="top"><div><div class="brand">ORION <span>// TRADING COMMAND CENTER</span></div><div class="small">Research → Validation → Paper Trading → Live only when proven</div></div><div class="status"><span class="dot"></span><span id="worker">CONNECTING</span><span>•</span><span id="updated">—</span></div></div>
<div class="grid">
<div class="card span3"><div class="label">Paper equity</div><div class="value" id="equity">—</div><div class="sub" id="equitySub">Starting: —</div></div>
<div class="card span3"><div class="label">Paper trades</div><div class="value" id="tradeCount">—</div><div class="sub" id="tradeSub">Open orders: —</div></div>
<div class="card span3"><div class="label">Research runs</div><div class="value" id="runCount">—</div><div class="sub" id="runSub">Latest: —</div></div>
<div class="card span3"><div class="label">Live trading</div><div class="value red">LOCKED</div><div class="sub">Paper-only until every gate passes</div></div>

<div class="card span8"><h2>Bot performance</h2><div class="chart" id="chart"></div><div class="small">Closed paper-trade P&amp;L history. Empty until the bot actually trades.</div></div>
<div class="card span4"><h2>Hard approval gates</h2><div class="gate"><b>OOS trades</b><strong class="cyan">≥ 500</strong></div><div class="gate"><b>OOS win rate</b><strong class="cyan">≥ 75%</strong></div><div class="gate"><b>Positive expectancy</b><strong class="green">REQUIRED</strong></div><div class="gate"><b>Drawdown / streak</b><strong class="green">CONTROLLED</strong></div><div class="gate"><b>Monte Carlo + WFO</b><strong class="green">REQUIRED</strong></div></div>

<div class="card span6"><h2>Open positions / orders</h2><div class="scroll"><table class="table"><thead><tr><th>Pair</th><th>Side</th><th>Entry</th><th>SL</th><th>TP</th><th>Strategy</th></tr></thead><tbody id="orders"></tbody></table></div></div>
<div class="card span6"><h2>Latest closed trades</h2><div class="scroll"><table class="table"><thead><tr><th>Pair</th><th>Side</th><th>P&amp;L</th><th>Reason</th><th>Closed</th></tr></thead><tbody id="trades"></tbody></table></div></div>

<div class="card span8"><h2>Research / validation</h2><div class="scroll"><table class="table"><thead><tr><th>Pair</th><th>TF</th><th>Return</th><th>DD</th><th>Trades</th><th>Win</th><th>Status</th></tr></thead><tbody id="runs"></tbody></table></div></div>
<div class="card span4"><h2>Worker jobs</h2><div id="jobs"></div></div>

<div class="card span6"><h2>Strategies</h2><div class="scroll"><table class="table"><thead><tr><th>Strategy</th><th>Pair</th><th>TF</th><th>Status</th><th>Updated</th></tr></thead><tbody id="strategies"></tbody></table></div></div>
<div class="card span6"><h2>Datasets</h2><div class="scroll"><table class="table"><thead><tr><th>Pair</th><th>TF</th><th>Rows</th><th>Missing</th><th>Quality</th><th>Provider</th></tr></thead><tbody id="datasets"></tbody></table></div></div>
</div></div>
<script>
const $=id=>document.getElementById(id), fmt=n=>n==null?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:2}), esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function rows(id,html){$(id).innerHTML=html||'<tr><td colspan="8" class="empty">No data yet</td></tr>'}
function time(x){return x?new Date(x).toLocaleString():'—'}
async function load(){
 try{
  const d=await fetch('/api/dashboard-data',{cache:'no-store'}).then(r=>r.json()); if(d.error)throw Error(d.error);
  $('worker').textContent='ONLINE';$('updated').textContent='UPDATED '+new Date().toLocaleTimeString();
  const a=d.account?.[0], t=d.trades||[],o=d.orders||[];
  const pnl=t.reduce((s,x)=>s+Number(x.pnl||0),0), start=Number(a?.initial_equity||10000), eq=start+pnl;
  $('equity').textContent='$'+fmt(eq);$('equitySub').textContent='Starting: $'+fmt(start)+' • P&L: '+(pnl>=0?'+':'')+'$'+fmt(pnl);
  $('tradeCount').textContent=fmt(t.length);$('tradeSub').textContent='Open orders: '+fmt(o.filter(x=>x.status==='open').length);
  $('runCount').textContent=fmt((d.runs||[]).length);$('runSub').textContent='Latest: '+time(d.runs?.[0]?.created_at);
  const vals=t.slice().reverse().map(x=>Number(x.pnl||0)); const mx=Math.max(1,...vals.map(Math.abs)); $('chart').innerHTML=vals.length?vals.map(v=>'<div class="barc" style="height:'+Math.max(5,Math.abs(v)/mx*100)+'%;'+(v<0?'background:linear-gradient(to top,var(--red),#74313b)':'')+'" title="'+fmt(v)+'"></div>').join(''):'<div class="empty" style="width:100%">Bot has not closed any paper trades yet.</div>';
  rows('orders',o.filter(x=>x.status==='open').slice(0,30).map(x=>'<tr><td>'+esc(x.instrument)+'</td><td>'+esc(x.direction)+'</td><td>'+fmt(x.entry)+'</td><td>'+fmt(x.stop)+'</td><td>'+fmt(x.target)+'</td><td>'+esc(x.strategy_name||'—')+'</td></tr>').join(''));
  rows('trades',t.slice(0,30).map(x=>'<tr><td>'+esc(x.instrument)+'</td><td>'+esc(x.direction)+'</td><td class="'+(Number(x.pnl)>=0?'green':'red')+'">'+(Number(x.pnl)>=0?'+':'')+fmt(x.pnl)+'</td><td>'+esc(x.reason)+'</td><td>'+time(x.closed_at)+'</td></tr>').join(''));
  rows('runs',(d.runs||[]).slice(0,30).map(x=>'<tr><td>'+esc(x.instrument)+'</td><td>'+esc(x.timeframe)+'</td><td class="'+(Number(x.total_return_pct)>=0?'green':'red')+'">'+fmt(x.total_return_pct)+'%</td><td>'+fmt(x.max_drawdown_pct)+'%</td><td>'+fmt(x.trade_count)+'</td><td>'+fmt(x.win_rate_pct)+'%</td><td><span class="pill">'+(Number(x.win_rate_pct)>=75&&Number(x.trade_count)>=500?'QUALIFIED':'RESEARCH')+'</span></td></tr>').join(''));
  $('jobs').innerHTML=(d.jobs||[]).slice(0,12).map(x=>'<div class="gate"><div><b>'+esc(x.instrument||'—')+'/'+esc(x.timeframe||'—')+'</b><div class="small">'+esc(x.stage||x.status)+'</div></div><strong>'+fmt(x.progress_pct||x.progress||0)+'%</strong></div>').join('')||'<div class="empty">No queued jobs</div>';
  rows('strategies',(d.strategies||[]).map(x=>'<tr><td>'+esc(x.name)+' '+esc(x.version)+'</td><td>'+esc(x.instrument)+'</td><td>'+esc(x.timeframe)+'</td><td><span class="pill">'+esc(x.status)+'</span></td><td>'+time(x.updated_at)+'</td></tr>').join(''));
  rows('datasets',(d.datasets||[]).slice(0,40).map(x=>'<tr><td>'+esc(x.instrument)+'</td><td>'+esc(x.timeframe)+'</td><td>'+fmt(x.row_count)+'</td><td>'+fmt(x.missing_bars)+'</td><td class="'+(x.quality_passed?'green':'red')+'">'+(x.quality_passed?'PASS':'FAIL')+'</td><td>'+esc(x.provider)+'</td></tr>').join(''));
 }catch(e){$('worker').textContent='DATA ERROR';$('updated').textContent=e.message}
}
load();setInterval(load,10000);
</script></body></html>