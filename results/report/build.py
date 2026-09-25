"""Build the Tickmark one-page report: an Artifact page and a print/PDF twin.

Every figure below was computed from run d849113d369c (results/scored) and
checked against results/REPORT.md. Charts are generated to scale here rather
than drawn by hand.
"""
import html, pathlib

OUT = pathlib.Path(__file__).parent
REPO = "https://github.com/LBB2005/tickmark"

# ---- data -------------------------------------------------------------------
# (display name, maker, confident-wrong %, 90% low, 90% high, k, n, numeric accuracy %)
CW = [
    ("GPT-5.6 Luna", "OpenAI · budget tier", 20.8, 18.8, 22.9, 223, 1074, 2.5),
    ("GPT-5.6 Sol", "OpenAI · flagship", 5.5, 4.5, 6.8, 59, 1074, 11.5),
    ("Claude Opus 5", "Anthropic · flagship", 0.3, 0.1, 0.7, 3, 1074, 9.2),
    ("Gemini 3.1 Pro", "Google · flagship", 0.2, 0.1, 0.6, 2, 1074, 2.5),
    ("Grok 4.6", "xAI · flagship", 0.1, 0.0, 0.4, 1, 1074, 4.4),
]
# mean stated confidence (0-100) on answered numeric questions: (name, right, n_right, wrong, n_wrong, answered)
CONF = [
    ("GPT-5.6 Luna", 97.8, 17, 86.9, 199, 216),
    ("GPT-5.6 Sol", 75.6, 77, 50.5, 285, 362),
    ("Claude Opus 5", 62.7, 63, 44.3, 294, 357),
    ("Gemini 3.1 Pro", 71.8, 17, 64.3, 7, 24),
    ("Grok 4.6", 60.5, 30, 53.2, 38, 68),
]
FEW = {"Gemini 3.1 Pro", "Grok 4.6"}
# confident-wrong by question type: (label, sub, {model: (k, n)})
CATS = [
    ("Restated figures", "a number the company later revised", "restatement",
     {"GPT-5.6 Luna": (94, 231), "GPT-5.6 Sol": (9, 231), "Claude Opus 5": (0, 231),
      "Gemini 3.1 Pro": (2, 231), "Grok 4.6": (1, 231)}),
    ("Just before the cutoff", "a period near the model's training cutoff", "post_cutoff_boundary",
     {"GPT-5.6 Luna": (129, 294), "GPT-5.6 Sol": (50, 294), "Claude Opus 5": (3, 294),
      "Gemini 3.1 Pro": (0, 294), "Grok 4.6": (0, 294)}),
    ("Obscure segment figures", "real but rarely quoted numbers", "buried",
     {m: (0, 291) for m in ["GPT-5.6 Luna", "GPT-5.6 Sol", "Claude Opus 5", "Gemini 3.1 Pro", "Grok 4.6"]}),
    ("After the cutoff", "periods the model cannot have seen", "post_cutoff",
     {m: (0, 144) for m in ["GPT-5.6 Luna", "GPT-5.6 Sol", "Claude Opus 5", "Gemini 3.1 Pro", "Grok 4.6"]}),
    ("Segments that don't exist", "a false premise the model must reject", "false_premise",
     {m: (0, 114) for m in ["GPT-5.6 Luna", "GPT-5.6 Sol", "Claude Opus 5", "Gemini 3.1 Pro", "Grok 4.6"]}),
]
MODELS = [c[0] for c in CW]
e = html.escape


# ---- Exhibit 1: confident-wrong by model, bars with 90% intervals -------------
def exhibit1():
    W, L, R, top, row = 640, 168, 590, 30, 46
    xmax = 25.0
    x = lambda v: L + v / xmax * (R - L)
    H = top + row * len(CW) + 34
    g = []
    for t in (0, 5, 10, 15, 20, 25):
        g.append(f'<line x1="{x(t):.1f}" y1="{top-8}" x2="{x(t):.1f}" y2="{top+row*len(CW)}" class="grid"/>')
        g.append(f'<text x="{x(t):.1f}" y="{top+row*len(CW)+20}" class="tick" text-anchor="middle">{t}%</text>')
    for i, (name, maker, v, lo, hi, k, n, acc) in enumerate(CW):
        cy = top + i * row + row / 2
        bh = 18
        w = max(x(v) - x(0), 3)
        cls = "bar hot" if i == 0 else "bar"
        tip = (f"{name}: {v}% confidently wrong ({k} of {n:,} answers). "
               f"90% interval {lo}–{hi}%. Numeric accuracy {acc}%.")
        # bar with 4px rounded data-end, square at the baseline
        r = min(4, w / 2)
        path = (f"M{x(0):.1f},{cy-bh/2:.1f} H{x(0)+w-r:.1f} "
                f"Q{x(0)+w:.1f},{cy-bh/2:.1f} {x(0)+w:.1f},{cy-bh/2+r:.1f} "
                f"V{cy+bh/2-r:.1f} Q{x(0)+w:.1f},{cy+bh/2:.1f} {x(0)+w-r:.1f},{cy+bh/2:.1f} "
                f"H{x(0):.1f} Z")
        g.append(f'<g class="mark" tabindex="0" data-tip="{e(tip)}">'
                 f'<rect x="{L-4}" y="{cy-row/2+2:.1f}" width="{R-L+8}" height="{row-4}" class="hit"/>'
                 f'<path d="{path}" class="{cls}"/>'
                 f'<line x1="{x(lo):.1f}" y1="{cy:.1f}" x2="{x(hi):.1f}" y2="{cy:.1f}" class="ci"/>'
                 f'<line x1="{x(lo):.1f}" y1="{cy-5:.1f}" x2="{x(lo):.1f}" y2="{cy+5:.1f}" class="ci"/>'
                 f'<line x1="{x(hi):.1f}" y1="{cy-5:.1f}" x2="{x(hi):.1f}" y2="{cy+5:.1f}" class="ci"/></g>')
        g.append(f'<text x="{L-14}" y="{cy-2:.1f}" class="lab" text-anchor="end">{e(name)}</text>')
        g.append(f'<text x="{L-14}" y="{cy+13:.1f}" class="sub" text-anchor="end">{e(maker)}</text>')
        g.append(f'<text x="{x(hi)+9:.1f}" y="{cy+4.5:.1f}" class="val{" valhot" if i == 0 else ""}">{v}%</text>')
    g.append(f'<line x1="{x(0):.1f}" y1="{top-8}" x2="{x(0):.1f}" y2="{top+row*len(CW)}" class="axis"/>')
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="ex1t" class="chart">'
           + "".join(g) + "</svg>")
    table = "".join(
        f"<tr><td>{e(n)}</td><td>{v}%</td><td>{lo}–{hi}%</td><td>{k} / {nn:,}</td><td>{a}%</td></tr>"
        for n, _, v, lo, hi, k, nn, a in CW)
    return svg, (
        "<table><thead><tr><th>Model</th><th>Confident-wrong</th><th>90% interval</th>"
        "<th>Answers</th><th>Numeric accuracy</th></tr></thead><tbody>" + table + "</tbody></table>")


# ---- Exhibit 2: stated confidence when right vs when wrong (dumbbell) --------
def exhibit2():
    W, L, R, top, row = 640, 168, 610, 34, 44
    x = lambda v: L + v / 100 * (R - L)
    H = top + row * len(CONF) + 34
    g = []
    for t in (0, 25, 50, 75, 100):
        g.append(f'<line x1="{x(t):.1f}" y1="{top-8}" x2="{x(t):.1f}" y2="{top+row*len(CONF)}" class="grid"/>')
        g.append(f'<text x="{x(t):.1f}" y="{top+row*len(CONF)+20}" class="tick" text-anchor="middle">{t}</text>')
    # the frozen confident-wrong threshold
    g.append(f'<line x1="{x(75):.1f}" y1="{top-8}" x2="{x(75):.1f}" y2="{top+row*len(CONF)}" class="thresh"/>')
    g.append(f'<text x="{x(75)+5:.1f}" y="{top-12}" class="sub">75 = "confident"</text>')
    for i, (name, right, nr, wrong, nw, ans) in enumerate(CONF):
        cy = top + i * row + row / 2
        few = name in FEW
        tip = (f"{name}: mean stated confidence {right:.0f} when right (n={nr}), "
               f"{wrong:.0f} when wrong (n={nw}); {ans} numeric answers given.")
        g.append(f'<g class="mark{" few" if few else ""}" tabindex="0" data-tip="{e(tip)}">'
                 f'<rect x="{L-4}" y="{cy-row/2+2:.1f}" width="{R-L+8}" height="{row-4}" class="hit"/>'
                 f'<line x1="{x(wrong):.1f}" y1="{cy:.1f}" x2="{x(right):.1f}" y2="{cy:.1f}" class="stem"/>'
                 f'<circle cx="{x(wrong):.1f}" cy="{cy:.1f}" r="6" class="dot wrong"/>'
                 f'<circle cx="{x(right):.1f}" cy="{cy:.1f}" r="6" class="dot right"/></g>')
        g.append(f'<text x="{L-14}" y="{cy-2:.1f}" class="lab{" fewt" if few else ""}" text-anchor="end">{e(name)}</text>')
        g.append(f'<text x="{L-14}" y="{cy+13:.1f}" class="sub" text-anchor="end">'
                 f'{"only " if few else ""}{ans} answers</text>')
        if not few:  # label the story rows; the few-answer rows stay in the tooltip and table
            g.append(f'<text x="{x(wrong)-11:.1f}" y="{cy+4.5:.1f}" class="val" text-anchor="end">{wrong:.0f}</text>')
            g.append(f'<text x="{x(right)+11:.1f}" y="{cy+4.5:.1f}" class="val">{right:.0f}</text>')
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="ex2t" class="chart">'
           + "".join(g) + "</svg>")
    table = "".join(
        f"<tr><td>{e(n)}</td><td>{r:.0f} <span class=n>(n={nr})</span></td>"
        f"<td>{w:.0f} <span class=n>(n={nw})</span></td><td>{a}</td></tr>"
        for n, r, nr, w, nw, a in CONF)
    return svg, (
        "<table><thead><tr><th>Model</th><th>When right</th><th>When wrong</th>"
        "<th>Numeric answers</th></tr></thead><tbody>" + table + "</tbody></table>")


# ---- Exhibit 3: where confident errors happen (heat table) -------------------
def exhibit3():
    head = "".join(f'<th scope="col">{e(m)}</th>' for m in MODELS)
    rows = []
    for label, sub, _, vals in CATS:
        cells = []
        for m in MODELS:
            k, n = vals[m]
            pct = 100 * k / n
            a = 0 if k == 0 else 0.10 + min(pct, 45) / 45 * 0.78
            txt = "0" if k == 0 else (f"{pct:.0f}%" if pct >= 1 else f"{pct:.1f}%")
            cls = "hc" + (" z" if k == 0 else "") + (" ink" if a > 0.5 else "")
            cells.append(f'<td class="{cls}" style="--a:{a:.2f}" title="{e(m)}: {k} of {n} answers">{txt}</td>')
        rows.append(f'<tr><th scope="row"><span class="cl">{e(label)}</span>'
                    f'<span class="cs">{e(sub)}</span></th>{"".join(cells)}</tr>')
    return ('<div class="scroll"><table class="heat"><thead><tr><th></th>' + head +
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


ex1, ex1t = exhibit1()
ex2, ex2t = exhibit2()
ex3 = exhibit3()

STYLE = r"""
:root{
  --paper:#F6F7F8; --card:#FFFFFF; --ink:#141A23; --ink2:#46505F; --muted:#737D8C;
  --rule:#DCE0E6; --grid:#E6E9EE; --blue:#2F6DB5; --brick:#C2412D; --brick-rgb:194,65,45;
  --bar:#B7C0CC; --tipbg:#141A23; --tipfg:#FFFFFF; --focus:#2F6DB5;
  --serif:"Newsreader","Iowan Old Style","Georgia",serif;
  --sans:"Public Sans","Helvetica Neue",Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Menlo,monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  color-scheme:dark; --paper:#12161C; --card:#1A1F27; --ink:#E9EDF2; --ink2:#B6BFCB;
  --muted:#8C96A4; --rule:#2C333D; --grid:#262C35; --blue:#5C93DB; --brick:#E0654F;
  --brick-rgb:224,101,79; --bar:#566172; --tipbg:#E9EDF2; --tipfg:#12161C; --focus:#5C93DB;}}
:root[data-theme="dark"]{
  color-scheme:dark; --paper:#12161C; --card:#1A1F27; --ink:#E9EDF2; --ink2:#B6BFCB;
  --muted:#8C96A4; --rule:#2C333D; --grid:#262C35; --blue:#5C93DB; --brick:#E0654F;
  --brick-rgb:224,101,79; --bar:#566172; --tipbg:#E9EDF2; --tipfg:#12161C; --focus:#5C93DB;}
body{background:var(--paper);color:var(--ink);font:16px/1.6 var(--sans);-webkit-font-smoothing:antialiased}
.note{max-width:760px;margin:0 auto;padding-inline:20px;padding-block:40px 64px}
a{color:var(--blue);text-underline-offset:3px}
a:focus-visible,.mark:focus-visible,summary:focus-visible{outline:2px solid var(--focus);outline-offset:3px;border-radius:3px}

.meta{display:flex;flex-wrap:wrap;gap:6px 18px;font:500 12px/1.4 var(--mono);letter-spacing:.04em;
  text-transform:uppercase;color:var(--muted);padding-bottom:14px;border-bottom:1px solid var(--rule)}
.meta b{color:var(--brick);font-weight:600}
h1{font:600 clamp(44px,8vw,68px)/1 var(--serif);letter-spacing:-.02em;margin:26px 0 10px;text-wrap:balance}
.dek{font:400 clamp(20px,3.2vw,24px)/1.35 var(--serif);color:var(--ink2);margin:0 0 20px;max-width:34ch;text-wrap:balance}
.byline{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;font-size:14px;color:var(--ink2)}
.byline strong{color:var(--ink);font-weight:600}
.byline .sep{width:1px;height:14px;background:var(--rule)}
.why{font-size:13.5px;color:var(--muted);margin:14px 0 0;max-width:60ch;font-style:italic}

.lede{font-size:18px;line-height:1.65;margin:36px 0 26px;max-width:62ch}
.tiles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}
.tile{background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:18px 18px 16px;display:flex;flex-direction:column;gap:6px}
.tile .v{font:650 40px/1 var(--sans);letter-spacing:-.02em}
.tile.hot .v{color:var(--brick)}
.tile .l{font-size:14px;line-height:1.45;color:var(--ink2)}
.def{font-size:13px;color:var(--muted);margin:0 0 8px}

section{margin-top:52px}
h2{font:600 clamp(24px,4vw,30px)/1.2 var(--serif);letter-spacing:-.01em;margin:0 0 12px;text-wrap:balance}
p{margin:0 0 14px;max-width:64ch}
.exhibit{margin:22px 0 16px;background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:18px 18px 12px}
.exh{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 16px;align-items:baseline;margin-bottom:6px}
.exh .t{font:600 14px/1.4 var(--sans)}
.exh .t span{font:500 11px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-right:8px}
.legend{display:flex;gap:14px;font-size:13px;color:var(--ink2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.src{font:400 12px/1.5 var(--sans);color:var(--muted);margin:10px 0 0;padding-top:8px;border-top:1px solid var(--grid)}
details{margin-top:8px;font-size:13px}
summary{cursor:pointer;color:var(--ink2);width:max-content}

.chart{width:100%;height:auto;display:block;font-family:var(--sans);overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}
.axis{stroke:var(--muted);stroke-width:1}
.thresh{stroke:var(--muted);stroke-width:1}
.tick{fill:var(--muted);font:500 11px var(--mono)}
.lab{fill:var(--ink);font:600 13.5px var(--sans)}
.fewt{fill:var(--ink2)}
.sub{fill:var(--muted);font:400 11.5px var(--sans)}
.val{fill:var(--ink);font:600 12.5px var(--mono)}
.valhot{fill:var(--ink)}
.bar{fill:var(--bar)}
.bar.hot{fill:var(--brick)}
.ci{stroke:var(--ink2);stroke-width:1.25}
.hit{fill:transparent}
.stem{stroke:var(--bar);stroke-width:2}
.dot{stroke:var(--card);stroke-width:2}
.dot.right{fill:var(--blue)} .dot.wrong{fill:var(--brick)}
.mark.few{opacity:.55}
.mark{cursor:default;outline:none}
.mark:hover .hit,.mark:focus .hit{fill:var(--grid);opacity:.6}

.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
thead th{font:600 12px/1.3 var(--sans);color:var(--ink2)}
td{font-variant-numeric:tabular-nums}
.n{color:var(--muted)}
.heat{min-width:560px}
.heat thead th{text-align:center;font-size:12px;padding-bottom:10px}
.heat th[scope=row]{padding-right:14px;min-width:170px}
.cl{display:block;font-weight:600;font-size:13.5px}
.cs{display:block;font-weight:400;font-size:12px;color:var(--muted);line-height:1.35}
.hc{text-align:center;vertical-align:middle;font:600 13px var(--mono);font-variant-numeric:tabular-nums;
  background:rgba(var(--brick-rgb),var(--a));border:2px solid var(--card);border-radius:4px}
.hc.z{color:var(--muted);font-weight:400;background:transparent}
.hc.ink{color:#FFFFFF}

.rules{list-style:none;padding:0;margin:18px 0 0;display:grid;gap:14px}
.rules li{display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:start;max-width:66ch}
.rules li::before{content:"";width:8px;height:8px;margin-top:9px;background:var(--brick);border-radius:2px}
.rules b{font-weight:600}

.checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 28px;margin-top:18px}
.checks div{border-top:1px solid var(--rule);padding-top:12px}
.checks h3{font:600 15px/1.35 var(--sans);margin:0 0 4px}
.checks p{font-size:14px;color:var(--ink2);margin:0;line-height:1.55}

footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--rule);font-size:13px;color:var(--muted);line-height:1.6}
footer p{max-width:none;margin:0 0 8px}
footer .links{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:10px;font-size:14px}

#tip{position:fixed;z-index:10;max-width:280px;padding:8px 10px;border-radius:6px;background:var(--tipbg);color:var(--tipfg);
  font:400 12.5px/1.45 var(--sans);pointer-events:none;box-shadow:0 4px 14px rgba(0,0,0,.18)}
@media (max-width:640px){
  .tiles{grid-template-columns:1fr} .checks{grid-template-columns:1fr}
  .tile .v{font-size:34px} .exhibit{padding:14px 12px 10px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media print{
  body{background:#fff} .note{padding-block:0}
  .exhibit,.tile,.checks div,.rules li{break-inside:avoid}
  section{break-inside:auto} h2{break-after:avoid}
  details,#tip{display:none!important}
  a{color:var(--ink);text-decoration:none}
}
"""

SCRIPT = r"""
(function(){
  var tip=document.getElementById('tip');
  function show(el,x,y){tip.textContent=el.getAttribute('data-tip');tip.hidden=false;
    var r=tip.getBoundingClientRect(),px=Math.min(x+14,innerWidth-r.width-8),py=y+14;
    if(py+r.height>innerHeight-8)py=y-r.height-12;tip.style.left=px+'px';tip.style.top=py+'px';}
  document.querySelectorAll('.mark').forEach(function(el){
    el.addEventListener('mousemove',function(ev){show(el,ev.clientX,ev.clientY)});
    el.addEventListener('mouseleave',function(){tip.hidden=true});
    el.addEventListener('focus',function(){var b=el.getBoundingClientRect();show(el,b.left+b.width/2,b.top+b.height/2)});
    el.addEventListener('blur',function(){tip.hidden=true});
  });
})();
"""

BODY = f"""
<main class="note">
<header>
  <div class="meta"><span>Research note</span><span>25 September 2026</span><span>Closed-book</span><span><b>6,444</b> graded answers</span></div>
  <h1>Tickmark</h1>
  <p class="dek">How often AI models give confidently wrong financial figures, checked against SEC filings.</p>
  <div class="byline"><strong>Liam Blackshaw-Brown</strong><span class="sep"></span><a href="{REPO}">Code and data on GitHub</a></div>
  <p class="why">A tick mark is what an auditor writes beside a figure once it has been checked against the source document. Tickmark does the same to AI answers.</p>
</header>

<p class="lede">Five leading AI models were each asked 358 questions whose answers sit in SEC filings, three times each, with no documents and no web access: the way an analyst types a question into a chat window. The main measure is how often a model gives a <strong>wrong figure while saying it is at least 75% sure</strong>. That is the answer most likely to be copied into a model or a memo unchecked.</p>

<div class="tiles">
  <div class="tile hot"><div class="v">20.8%</div><div class="l">of the budget model's answers were wrong and stated with high confidence</div></div>
  <div class="tile"><div class="v">0.1–5.5%</div><div class="l">for the four flagship models on the same questions</div></div>
  <div class="tile"><div class="v">0</div><div class="l">figures invented across 570 answers about business segments that don't exist</div></div>
</div>
<p class="def">Confident-wrong: a figure the filing contradicts, given with stated confidence of 75 or more. Accuracy is graded at the precision the model stated.</p>

<section>
  <h2>The budget model is confidently wrong about one time in five</h2>
  <p>GPT-5.6 Luna, OpenAI's low-cost model, gave a confident wrong figure on 223 of its 1,074 answers. The flagship from the same generation, GPT-5.6 Sol, did so on 59. The other three flagships each did so fewer than four times.</p>
  <figure class="exhibit" aria-labelledby="ex1t">
    <div class="exh"><div class="t" id="ex1t"><span>Exhibit 1</span>Share of answers that were confidently wrong</div></div>
    {ex1}
    <p class="src">Bars show the rate; lines show the 90% Wilson interval. n = 1,074 answers per model (358 questions × 3). Source: Tickmark run d849113d369c; ground truth from SEC 10-K and 10-Q filings.</p>
    <details><summary>View as table</summary>{ex1t}</details>
  </figure>
</section>

<section>
  <h2>The gap is in the confidence, not the knowledge</h2>
  <p>None of these models reliably recalls exact figures from filings. What separates them is what they say when they don't know. When Luna gave a wrong number it still reported a mean confidence of 87, barely below the 98 it reported when right. Sol drops to 50 when wrong, and Claude Opus 5 to 44. Their stated confidence carries a warning; Luna's does not.</p>
  <figure class="exhibit" aria-labelledby="ex2t">
    <div class="exh"><div class="t" id="ex2t"><span>Exhibit 2</span>Mean stated confidence on numeric answers</div>
      <div class="legend"><span><i style="background:var(--blue)"></i>When right</span><span><i style="background:var(--brick)"></i>When wrong</span></div></div>
    {ex2}
    <p class="src">Confidence is the 0–100 figure each model reported alongside its answer. Gemini and Grok declined most numeric questions, so their averages rest on few answers and are shown faded. Source: Tickmark run d849113d369c.</p>
    <details><summary>View as table</summary>{ex2t}</details>
  </figure>
</section>

<section>
  <h2>Mistakes cluster where a plausible old number exists</h2>
  <p>Every closed-book model handled the traps: made-up segments, obscure figures and periods after its training data all drew zero confident errors. The errors come from two kinds of question. One is a <strong>restated figure</strong>, where the model remembers the number as originally reported. The other is a period <strong>just before its training cutoff</strong>, where it fills the gap with a guess.</p>
  <figure class="exhibit" aria-labelledby="ex3t">
    <div class="exh"><div class="t" id="ex3t"><span>Exhibit 3</span>Confidently wrong, by type of question</div></div>
    {ex3}
    <p class="src">Share of each model's answers in that category, darker = higher. n per model: restated 231, near cutoff 294, obscure 291, after cutoff 144, non-existent segment 114. Source: Tickmark run d849113d369c.</p>
  </figure>
</section>

<section>
  <h2>What this means for an analyst</h2>
  <ul class="rules">
    <li><span><b>Check any figure for a period near the model's training cutoff</b>, whatever confidence it states. That is where confident errors peak, reaching 44% of answers for the budget model.</span></li>
    <li><span><b>Expect restated numbers to come back as originally reported.</b> After a spin-off or an accounting change, a model will often give the old figure and be sure of it.</span></li>
    <li><span><b>Read the confidence field only on models that use it.</b> A flagship's stated confidence falls sharply when it is wrong. The budget model's barely moves, so a cheaper model saves money at the cost of that warning.</span></li>
  </ul>
</section>

<section>
  <h2>How the results were checked</h2>
  <div class="checks">
    <div><h3>Answers come from the filings</h3><p>358 questions built from XBRL data in 10-K and 10-Q filings across 50 companies, chosen for messy structures (spin-offs, 52-week fiscal years, share classes) rather than size.</p></div>
    <div><h3>Rules fixed before any model ran</h3><p>Grading rules were committed before the first model call, and the git history shows the order. The rules were never changed after results came in.</p></div>
    <div><h3>Answer key verified by hand</h3><p>A seeded sample of 78 answer-key records was checked against the primary filings: 78 of 78 confirmed. An automated review beforehand found 13 questions asking for figures that companies later revised; that question type was reworded before the final run.</p></div>
    <div><h3>Results reproduce</h3><p>260 unchanged questions were run a week apart, and no model's results moved beyond noise (|z| ≤ 1.4). The same check flagged a web-search reference model whose provider changed its behaviour under an unchanged name, so it is reported separately and not compared here.</p></div>
  </div>
</section>

<footer>
  <p>Models were called through OpenRouter with provider fallbacks disabled and any substituted model quarantined; 3 samples per question; all 6,444 answers graded. Rates carry 90% Wilson intervals. Limitations: 280 of the 358 answer-key records are verified by the automated pipeline only, per-category samples are 114–294 answers per model, and this is the closed-book track only, with no documents provided.</p>
  <div class="links"><a href="{REPO}/blob/main/results/REPORT.md">Full technical report</a><a href="{REPO}/blob/main/METHODOLOGY.md">Methodology</a><a href="{REPO}">Code and data</a></div>
</footer>
</main>
<div id="tip" role="tooltip" hidden></div>
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600'
         '&family=Newsreader:opsz,wght@6..72,400;6..72,600&family=Public+Sans:wght@400;500;600;650&display=swap">')

page = f"<title>Tickmark</title>\n{FONTS}\n<style>{STYLE}</style>\n{BODY}\n<script>{SCRIPT}</script>\n"
(OUT / "tickmark.html").write_text(page)

# Print twin: a full document (the Artifact skeleton is added only at publish),
# pinned to the light theme for paper.
PRINT_CSS = "@page{size:Letter;margin:0.5in 0.55in} body{zoom:.8} section{margin-top:34px} html{-webkit-print-color-adjust:exact;print-color-adjust:exact}"
doc = (f'<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8">'
       f'<meta name="viewport" content="width=device-width,initial-scale=1">'
       f"<title>Tickmark</title>{FONTS}<style>{STYLE}{PRINT_CSS}</style></head>"
       f"<body>{BODY}<script>{SCRIPT}</script></body></html>")
(OUT / "tickmark_print.html").write_text(doc)
print("wrote", OUT / "tickmark.html", "and tickmark_print.html")


# ---- Standalone SVGs for the GitHub README -----------------------------------
# GitHub renders an SVG as an <img>: no page CSS, no web fonts. So each figure
# carries its own literal light palette on a white card with a system font stack.
SVG_CSS = """
text{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.grid{stroke:#E6E9EE;stroke-width:1}.axis,.thresh{stroke:#737D8C;stroke-width:1}
.tick{fill:#737D8C;font-size:11px}.lab{fill:#141A23;font-size:13.5px;font-weight:600}
.fewt{fill:#46505F}.sub{fill:#737D8C;font-size:11.5px}.val,.valhot{fill:#141A23;font-size:12.5px;font-weight:600}
.bar{fill:#B7C0CC}.bar.hot{fill:#C2412D}.ci{stroke:#46505F;stroke-width:1.25}.hit{fill:none}
.stem{stroke:#B7C0CC;stroke-width:2}.dot{stroke:#FFFFFF;stroke-width:2}.dot.right{fill:#2F6DB5}.dot.wrong{fill:#C2412D}
.few{opacity:.55}.ttl{fill:#141A23;font-size:16px;font-weight:700}.cap{fill:#737D8C;font-size:11.5px}
"""


def standalone(svg, title, caption, legend=False):
    import re
    inner = re.sub(r"^<svg[^>]*>|</svg>$", "", svg)
    vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    w, h = int(vb.group(1)), int(vb.group(2))
    W, H = w + 40, h + 96
    leg = ""
    if legend:
        leg = (f'<circle cx="{W-196}" cy="30" r="5" class="dot right"/><text x="{W-186}" y="34" class="sub">When right</text>'
               f'<circle cx="{W-104}" cy="30" r="5" class="dot wrong"/><text x="{W-94}" y="34" class="sub">When wrong</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f"<style>{SVG_CSS}</style>"
            f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="8" fill="#FFFFFF" stroke="#DCE0E6"/>'
            f'<text x="20" y="34" class="ttl">{e(title)}</text>{leg}'
            f'<g transform="translate(20,52)">{inner}</g>'
            f'<text x="20" y="{H-16}" class="cap">{e(caption)}</text></svg>')


FIG = OUT.parent / "figures"
FIG.mkdir(exist_ok=True)
(FIG / "confident_wrong_by_model.svg").write_text(standalone(
    ex1, "Share of answers that were confidently wrong",
    "Bars: rate. Lines: 90% Wilson interval. n = 1,074 answers per model. Tickmark run d849113d369c."))
(FIG / "confidence_right_vs_wrong.svg").write_text(standalone(
    ex2, "Mean stated confidence on numeric answers",
    "Gemini and Grok declined most numeric questions (faded: few answers). Tickmark run d849113d369c.",
    legend=True))
print("wrote figures to", FIG)
