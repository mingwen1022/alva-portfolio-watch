/* L4 · 渲染层判官。把一份产物喂进模板,真的在浏览器里跑一遍,看页面长什么样。
 *
 * 这一层拦的是 L0–L3 结构上抓不到的那类:**数据全对、断言全过、页面上一片空白**。
 * 起因是 2026-08-23 第一次真跑的 BC1 —— `range52w.low` 是 null,
 * `money2(null)` 抛出,renderP2 整个中断,它后面六张卡全没渲染。
 * 而财报数据一直在文件里。任何数据层断言都发现不了这件事。
 *
 * ⚠️ 零安装:Node 22 自带全局 WebSocket,浏览器用 playwright 缓存里的
 *    chrome-headless-shell,退回系统 Chrome。不引入任何 npm 依赖 ——
 *    判官自己要能在任何一台机器上跑起来,否则它会变成「装不上所以没跑」。
 *
 * 用法:
 *     node eval/l4_render.js <产物目录>            # 目录里要有 data/ 与 index.html
 *     node eval/l4_render.js <产物目录> --json
 */
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const ROOT = path.resolve(process.argv[2] || ".");
const JSON_OUT = process.argv.includes("--json");

/* 四个 tab 的静态卡片数。⚠️ 这些卡是**静态 markup**,渲染挂掉时一张都不会少,
   连标题都还在 —— 空的只是挂载点。所以光数卡片是一条永远不会失败的断言。
   数量只当结构护栏(模板被改坏才响),真正抓 BC1 的是下面的「正文非空」。 */
/* ⚠️ tab 按钮上的 `data-panel` 是 `"p2"`，panel 的 id 是 `"panel-p2"` —— **不是同一个串**。
   我第一版拿 id 去比 dataset.panel，四个 tab 一个都点不开，而症状是「三个 panel 的卡片全空」，
   看起来像渲染全挂了。id 与键的对应关系写在这里，不在代码里靠猜。
   tab 本身是 <div class="tab-item">，不是 <button>。 */
const PANELS = { "panel-p1": 3, "panel-p2": 7, "panel-p3": 5, "panel-p4": 6 };
const TAB_KEY = pid => pid.replace(/^panel-/, "");        // panel-p2 → p2

const BIN = [
  `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1228`
    + `/chrome-headless-shell-mac-arm64/chrome-headless-shell`,
  `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1234`
    + `/chrome-mac/Chromium.app/Contents/MacOS/Chromium`,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find(p => { try { fs.accessSync(p, fs.constants.X_OK); return true; } catch { return false; } });

const MIME = { ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
               ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8" };

const FAIL = [], MISS = [];
let RAN = 0;
const A = (name, cond, detail = "") => {
  RAN += 1;
  if (!cond) FAIL.push(`[L4] ${name}` + (detail ? ` ← ${detail}` : ""));
};
const M = what => MISS.push(`[L4] ${what}`);

/* ── 一个只读的本地静态服 ─────────────────────────────────────────── */
function serve(dir) {
  return new Promise(res => {
    const s = http.createServer((rq, rs) => {
      /* 路径遍历在这里不是安全问题（本机、只读、临时端口），但一个走出根目录的
         请求意味着页面在找不该找的东西 —— 静默 404 会把它藏起来。 */
      const rel = decodeURIComponent(rq.url.split("?")[0]);
      const f = path.join(dir, rel === "/" ? "/index.html" : rel);
      if (!f.startsWith(dir)) { rs.writeHead(403).end(); return; }
      fs.readFile(f, (e, b) => {
        if (e) { rs.writeHead(404).end("nope"); return; }
        /* ⚠️ 真跑抓回来的 index.html 里 `alfsRoot` 指着 Alva 远端 FS,那需要鉴权。
           照原样喂进浏览器的话，八个数据文件一个都取不到 → 每张卡都空 →
           判官报「p1 3 张空 p2 7 张空 p3 5 张空」，读起来像渲染全挂了。
           **那是取不到数，不是渲染坏了 —— 症状指向错误的一层。**
           在**内存里**改成 null 走相对 fetch，不动磁盘上的产物。 */
        if (path.extname(f) === ".html") {
          b = Buffer.from(String(b).replace(
            /(id="playbook-config">)\s*\{[^}]*\}/,
            '$1{"alfsRoot": null}'));
        }
        rs.writeHead(200, { "content-type": MIME[path.extname(f)] || "application/octet-stream" });
        rs.end(b);
      });
    });
    s.listen(0, "127.0.0.1", () => res({ srv: s, port: s.address().port }));
  });
}

/* ── 最小 CDP 客户端 ──────────────────────────────────────────────── */
function cdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const waiting = new Map(), handlers = [];
  ws.addEventListener("message", ev => {
    const m = JSON.parse(ev.data);
    if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
    else if (m.method) handlers.forEach(h => h(m));
  });
  return {
    ready: new Promise((ok, no) => {
      ws.addEventListener("open", ok);
      ws.addEventListener("error", () => no(new Error("CDP 连不上")));
    }),
    on: h => handlers.push(h),
    send: (method, params = {}) => new Promise(ok => {
      const n = ++id;
      waiting.set(n, m => ok(m.result === undefined ? m : m.result));
      ws.send(JSON.stringify({ id: n, method, params }));
    }),
    close: () => ws.close(),
  };
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}

(async () => {
  if (!BIN) { console.error("❌ 找不到无头浏览器"); process.exit(3); }
  if (!fs.existsSync(path.join(ROOT, "index.html"))) {
    console.error(`❌ ${ROOT} 里没有 index.html —— L4 无从跑起`); process.exit(3);
  }

  const { srv, port } = await serve(ROOT);
  const profile = fs.mkdtempSync("/tmp/l4-");
  const chrome = spawn(BIN, [
    "--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
    "--no-first-run", "--no-default-browser-check", "--disable-gpu",
    "--window-size=1440,1000", "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  /* 端口从 stderr 的 "DevTools listening on ws://..." 里读 —— 写死端口会在
     并发跑两个案例时互相抢。 */
  const devtools = await new Promise((ok, no) => {
    let buf = "";
    const t = setTimeout(() => no(new Error("浏览器 10 秒没起来")), 10000);
    chrome.stderr.on("data", d => {
      buf += d;
      const m = buf.match(/ws:\/\/([^\s]+)/);
      if (m) { clearTimeout(t); ok(`http://${m[1].split("/")[0]}`); }
    });
  });

  const cleanup = () => { try { chrome.kill(); } catch {} srv.close();
                          try { fs.rmSync(profile, { recursive: true, force: true }); } catch {} };

  try {
    /* ⚠️ 不用 /json/new —— 新版 Chrome 要求 PUT，GET 会返回一段非 JSON 的说明文字，
       而 JSON.parse 报出来的是「Unexpected token U」，指向完全错误的方向。
       启动时已经带了 about:blank，直接用那个 page target。 */
    const list = await getJSON(`${devtools}/json/list`);
    const tgt = list.find(t => t.type === "page");
    if (!tgt) throw new Error("没有 page target:" + JSON.stringify(list).slice(0, 200));
    const c = cdp(tgt.webSocketDebuggerUrl);
    await c.ready;

    /* ⚠️ 只收 console.error 抓不到 BC1 —— 那是 Uncaught TypeError,
       走的是 Runtime.exceptionThrown。两条都要挂。 */
    const errs = [], net404 = [];
    c.on(m => {
      if (m.method === "Runtime.exceptionThrown") {
        const d = m.params.exceptionDetails;
        const stack = (d.stackTrace?.callFrames || []).slice(0, 6)
          .map(f => f.functionName || "(anon)").join(" ← ");
        errs.push(`${d.exception?.description?.split("\n")[0] || d.text}${stack ? "  @ " + stack : ""}`);
      }
      if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
        errs.push("console.error: " + m.params.args.map(a => a.value ?? a.description).join(" "));
      }
      if (m.method === "Network.responseReceived" && m.params.response.status === 404) {
        net404.push(m.params.response.url.replace(`http://127.0.0.1:${port}`, ""));
      }
    });
    await c.send("Runtime.enable");
    await c.send("Network.enable");
    await c.send("Page.enable");
    await c.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
    await sleep(2500);

    const evalJs = async expr => {
      const r = await c.send("Runtime.evaluate",
        { expression: expr, returnByValue: true, awaitPromise: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + " " +
        (r.exceptionDetails.exception?.description || ""));
      return r.result.value;
    };

    /* 先把四个 tab 都点一遍 —— 只为**触发异常**:p2/p3/p4 初始 hidden,不点不渲染,
       BC1 那条 Uncaught 只在点开 tab 2 的瞬间抛。卡片正文的判定在下面第 4 条里
       逐个 panel 重新切过去做,不依赖这一轮。 */
    const tabs = await evalJs(`(() => {
      const t = [...document.querySelectorAll('[role=tab], .tabs button, nav button')];
      return t.length;
    })()`);
    const clicked = await evalJs(`(async () => {
      const out = [];
      for (const k of ['p1','p2','p3','p4']) {
        const btn = document.querySelector('.tab-item[data-panel="' + k + '"]')
                 || document.querySelector('[data-panel="' + k + '"]');
        if (btn) { btn.click(); out.push(k); await new Promise(r => setTimeout(r, 600)); }
      }
      return out;
    })()`);

    /* 上面那套选择器可能对不上模板 —— 对不上就退回按顺序点 tab 条,
       但要**说出来**:静默退回等于把「没点到」显示成「点过了」。 */
    let how = "data-panel";
    if (!clicked || clicked.length < 4) {
      how = "按顺序点 tab 条";
      await evalJs(`(async () => {
        const bar = document.querySelector('[role=tablist]') || document.querySelector('.tabs');
        const bs = bar ? [...bar.querySelectorAll('button,[role=tab],a')] : [];
        for (const b of bs) { b.click(); await new Promise(r => setTimeout(r, 600)); }
        return bs.length;
      })()`);
    }
    await sleep(1200);

    /* ── 1 · 控制台零异常 ── */
    A("页面加载与四个 tab 全部点过之后,零未捕获异常", errs.length === 0,
      errs.slice(0, 4).join(" ‖ "));
    A("没有 404", net404.length === 0, net404.slice(0, 5).join(" "));

    /* ── 2 · 禁词。⚠️ 排除 pre/code —— 方法页里有示例代码 ── */
    const banned = await evalJs(`(() => {
      /* ⚠️ script/style 也要排除 —— TreeWalker(SHOW_TEXT) 会走进 <script>，
         把内联 JS 的注释当成「页面文本」。第一次跑就把一行 ═══ 注释报成了禁词，
         而那行根本不在页面上。pre/code 是方法页里的示例代码。 */
      const skip = new Set();
      document.querySelectorAll('pre, code, script, style, noscript, template')
        .forEach(e => skip.add(e));
      const bad = [];
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        let p = n.parentElement, inCode = false;
        while (p) { if (skip.has(p)) { inCode = true; break; } p = p.parentElement; }
        if (inCode) continue;
        /* ⚠️ null 原本不在这张表里。实测 2026-08-25：线上 DOGE 那张归因卡上
           并排两行写着「null」—— 模型自搜的来源只回 URL，title 落盘是 null，
           而页面把它原样印了出来。三个词挡住了 undefined 却没挡住 null，
           而两者是同一件事：页面在渲染一个它没有的值。
           ⚠️ 本段在模板字符串里，不能用反引号 —— 会当场截断这个字符串。
           边界要求两侧非字母，否则 annulled、nullable 这类词会误报。 */
        let m = n.nodeValue.match(/NaN|undefined|\\[object Object\\]/);
        /* ⚠️ null 单独一条判据，比另外三个窄。要抓的是**值槽印出了 null**，
           而 null 在散文里是正当用词 —— 本页方法 tab 就写着 an empirical null（经验零）。
           判据因此是「这个文本节点短，且 null 独立成词」：值槽都很短，句子不会。
           第一版用了和另外三词一样的宽判据，当场把那句统计说明报成缺陷。 */
        if (!m) { const t = n.nodeValue.trim();
          if (t.length <= 40 && /(^|[^A-Za-z])null([^A-Za-z]|$)/.test(t)) m = ["null"]; }
        if (!m) continue;
        /* ⚠️ 只报匹配到的那个词等于没报 —— 「NaN」三个字母哪里都可能出现，
           拿着它回去找要翻一万一千行模板。把**位置**一起带出来：
           最近带 id 的祖先 + 所在卡片的标题 + 整段文本。 */
        let id = "", card = "";
        for (let e = n.parentElement; e; e = e.parentElement) {
          if (!id && e.id) id = "#" + e.id;
          if (!card && e.classList && e.classList.contains("widget-card")) {
            const hh = e.querySelector(".sec-title, .p2-head, .widget-title");
            card = hh ? hh.innerText.trim().split(String.fromCharCode(10))[0].slice(0, 22) : "(无标题卡)";
          }
        }
        bad.push((card || "?") + " " + id + " 「" + n.nodeValue.trim().slice(0, 60) + "」");
      }
      return [...new Set(bad)];
    })()`);
    A("页面文本里没有 NaN / null / undefined / [object Object]", banned.length === 0,
      banned.slice(0, 3).join(" ‖ "));

    /* ── 2b · 弹窗里的禁词 ───────────────────────────────────────────
       ⚠️ 上面那一遍只扫四个面板。而告警详情弹窗是**另一整片渲染**：
          归因与来源、围绕触发那根 bar 的 K 线、幅度分位、你的持仓 ——
          它们全都不在 document.body 的默认可见树里被扫到。
          实测 2026-08-25：线上 DOGE 卡上并排两行写着「null」，
          而 L4 全绿 —— 不是判错，是**从来没打开过那扇窗**。
          做过一次破坏性测试确认这一点：把页面的兜底去掉，上面那一遍照样通过。
       每张卡都开一次，逐张扫完再关。 */
    const mdlBanned = await evalJs(`(async () => {
      if (typeof ACTIVE === 'undefined' || !ACTIVE.length) return [];
      const skip = new Set();
      const bad = [];
      for (let i = 0; i < ACTIVE.length; i++) {
        openDetail(i);
        await new Promise(r => setTimeout(r, 120));
        const body = document.getElementById('mdl-body');
        if (!body) continue;
        skip.clear();
        body.querySelectorAll('pre, code, script, style, noscript, template')
            .forEach(e => skip.add(e));
        const walk = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
        for (let n = walk.nextNode(); n; n = walk.nextNode()) {
          let p2 = n.parentElement, inCode = false;
          while (p2) { if (skip.has(p2)) { inCode = true; break; } p2 = p2.parentElement; }
          if (inCode) continue;
          let m = n.nodeValue.match(/NaN|undefined|\\[object Object\\]/);
          if (!m) { const t = n.nodeValue.trim();
            if (t.length <= 40 && /(^|[^A-Za-z])null([^A-Za-z]|$)/.test(t)) m = ["null"]; }
          if (!m) continue;
          bad.push(ACTIVE[i].symbol + " " + ACTIVE[i].signalId
                   + " 「" + n.nodeValue.trim().slice(0, 60) + "」");
        }
      }
      const x = document.getElementById('mdl-x'); if (x) x.click();
      return [...new Set(bad)];
    })()`);
    A("告警弹窗里没有 NaN / null / undefined / [object Object]", mdlBanned.length === 0,
      mdlBanned.slice(0, 3).join(" ‖ "));

    /* ── 3 · 基线天数。要页面在元素上挂 data-base="<SYMBOL>" ──
       ⚠️ 不按下标配对两个列表 —— 两边打同一个键,按键配对。 */
    /* ⚠️ 我原本要的是 `data-base="<SYMBOL>"`，前端实现成
       `data-base="<baselineDays>"` + `data-sym="<SYMBOL>"` —— **值和键分开，比我要的好**。
       但我的断言照旧读 data-base 当 symbol，于是拿 "3000" 去 baselines 里查，
       查不到就报「没有对应条目」。看起来像页面标错了标的，其实是判官读错了属性。
       ⚠️ 这一条正是「不按下标配对」的同类:键要显式指定，不能靠位置或习惯假定。 */
    const shown = await evalJs(`[...document.querySelectorAll('[data-base]')]
      .map(e => [e.dataset.sym || e.dataset.base, e.dataset.base])`);
    const baselines = JSON.parse(fs.readFileSync(path.join(ROOT, "data/baselines.json")));
    if (!shown.length) {
      M("页面上没有 data-base 锚点,基线天数断言未跑（需要前端在该元素上加 data-base=\"<SYMBOL>\"）");
    } else {
      for (const [sym, txt] of shown) {
        const want = (baselines[sym] || {}).baselineDays;
        if (want == null) { M(`data-base="${sym}" 在 baselines 里没有对应条目`); continue; }
        A(`${sym} 页面上印的基线天数 == baselines 里的值`, Number(txt) === want,
          `页面 ${txt} vs 契约 ${want}`);
      }
    }

    /* ── 4 · 卡片:结构与正文分开报 ──
       ⚠️ 合成一条的话「卡数对但全空」会被算作通过 —— 那恰好就是 BC1 的症状。

       ⚠️ **必须逐个 panel 切过去、确认它可见之后再量。**
          隐藏元素的 `innerText` 恒为空串 —— 一次性扫四个 panel 的话，
          三个隐藏的会全部报「卡片正文为空」。那不是在量「渲染出来没有」，
          是在量「现在看得见没有」，而两者长得一模一样。
          第一次跑就是这样报出 p2/p3/p4 共 18 张空卡的，一张都不是真的。 */
    const cards = {};
    for (const pid of Object.keys(PANELS)) {
      const r = await evalJs(`(async () => {
        const panel = document.getElementById(${JSON.stringify(pid)});
        if (!panel) return { missing: true };
        const btn = document.querySelector('.tab-item[data-panel=${JSON.stringify(TAB_KEY(pid))}]')
                 || document.querySelector('[data-panel=${JSON.stringify(TAB_KEY(pid))}]')
                 || document.querySelector('[aria-controls=${JSON.stringify(pid)}]');
        if (btn) { btn.click(); await new Promise(r => setTimeout(r, 700)); }
        const panelVisible = panel.offsetParent !== null && !panel.hidden;
        const cs = [...panel.querySelectorAll('.widget-card')];
        /* ⚠️ **藏起来的卡不是空的卡。** 隐藏元素的 innerText 恒为空串，
           于是「这本账用不到这张卡、所以藏了」被数成「这张卡没渲染出来」。
           契约明写「不适用就整个省掉这个键」，页面据此隐藏（p2Scope）——
           那是正确行为，而我的判官把它报成了缺陷（BC14 因此是一条误报）。
           我在 panel 那一层修过同一个坑，没想到卡片这一层还有一次。
           ⚠️ 判据用 offsetParent / hidden，不用 style.display —— 卡可能是被
              **祖先**藏的，问它自己的 display 得到的是「我没被藏」。 */
        const visible = c => c.offsetParent !== null && !c.hidden
                             && !(c.parentElement && c.parentElement.hidden);
        const hiddenN = cs.filter(c => !visible(c)).length;
        const empty = [];
        cs.filter(visible).forEach((c, i) => {
          const head = c.querySelector('.p2-head, .widget-title, .sec-title');
          let body = c.innerText || '';
          if (head) body = body.replace(head.innerText, '');
          if (!body.trim()) empty.push(String(c.dataset.cardKind || c.id || ('#' + i)));
        });
        return { visible: panelVisible, n: cs.length, hidden: hiddenN, empty, clicked: !!btn };
      })()`);
      cards[pid] = r;
      if (r.missing) { M(`${pid} 这个 panel 不存在,该 tab 的卡片断言未跑`); continue; }
      /* (a) 结构护栏 —— 只有模板被改坏了才会响。与可见性无关,隐藏也数得到 */
      A(`${pid} 卡片数 == ${PANELS[pid]}`, r.n === PANELS[pid],
        `实际 ${r.n}（模板被改过?）`);
      /* (b) 渲染护栏 —— BC1 在这里响。但 panel 打不开时**不判**,
             报「未跑」。把「切不过去」算成「渲染挂了」是在冤枉另一层。 */
      if (!r.visible) {
        M(`${pid} 切不过去（clicked=${r.clicked}）,正文断言未跑 —— 不是通过`);
        continue;
      }
      /* 空态也必须有文字。这样「合法的空」（未连账户没有净值曲线）与
         「渲染挂了」被强制分开 —— 想让断言过,就得写那句文案。 */
      A(`${pid} 每张可见的卡都有正文`, r.empty.length === 0,
        `${r.empty.length} 张空:${r.empty.slice(0, 6).join(" ")}`);
      /* 藏了几张要说出来:「这本账用不到」与「这张卡没了」在计数上长得一样 */
      if (r.hidden) M(`${pid} 有 ${r.hidden} 张卡按适用范围隐藏（不计入正文断言）`);
    }

    const out = { ran: RAN, fail: FAIL, miss: MISS, exceptions: errs,
                  tabsClicked: how, tabsFound: tabs, cards };
    c.close();
    cleanup();

    if (JSON_OUT) { console.log(JSON.stringify(out, null, 1)); process.exit(FAIL.length ? 1 : 0); }
    console.log(`L4 渲染层 · 求值 ${RAN} 条 · tab 点法「${how}」`);
    for (const [pid, v] of Object.entries(cards)) {
      console.log(`  ${pid}  ${v.n} 张卡,空 ${v.empty.length} 张`);
    }
    if (MISS.length) { console.log(`\n—  ${MISS.length} 处对象不存在:`); MISS.forEach(x => console.log("  ", x)); }
    if (FAIL.length) {
      console.log(`\n❌ ${FAIL.length} 条未过:`);
      FAIL.forEach(x => console.log("  ", x));
      process.exit(1);
    }
    if (RAN === 0) { console.log("⚠️ 一条都没求值 —— 这不是通过,是没查"); process.exit(2); }
    console.log(`\n✅ L4 全过（求值 ${RAN} 条）`);
  } catch (e) {
    cleanup();
    console.error("❌ L4 自己挂了:", e.message);
    process.exit(3);
  }
})();
