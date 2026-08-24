// 最小探针：确认 ask() 可用 · 返回结构 · 是否裹 markdown fence。1 次调用。
const { ask } = require("@alva/alvaask");
(async () => {
  const t0 = Date.now();
  let out = {};
  try {
    const r = ask(
      'Classify this policy post. Reply with ONLY a JSON array, no prose.\n' +
      '[{"id":"t1","specificity":"factual|rhetorical","specificity_evidence":"<verbatim substring>"}]\n\n' +
      'id=t1 text="""We are imposing a 25% tariff on imported semiconductors, effective October 1."""',
      { system: "You are a strict JSON extraction engine. Output JSON only.", model: "claude-haiku-4-5", effort: "low" }
    );
    out = { keys: Object.keys(r || {}), text: (r && r.text) ? String(r.text).slice(0, 800) : null,
            raw: (r && !r.text) ? String(JSON.stringify(r)).slice(0, 800) : null };
  } catch (e) {
    out = { err: String(e).slice(0, 500) };
  }
  out.ms = Date.now() - t0;
  return out;
})();
