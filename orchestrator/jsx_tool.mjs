// Deterministic JSX class editing (the "edit" branch's tool).
//
//   node jsx_tool.mjs tag    < {"code": "..."}                 -> {"code": tagged, "elements": [{id, tag, class, text}]}
//   node jsx_tool.mjs apply  < {"code": tagged, "edits": [...]} -> {"code": new, "applied": n, "skipped": [...]}
//
// tag: adds data-pc="N" to every intrinsic JSX element (document order), so a model can name elements.
// apply: each edit {id, add?: "classes", remove?: "classes"} rewrites ONLY that element's className
// string literal; every other byte of the file is unchanged. Tailwind conflicts are resolved by
// removing classes with the same variant+property prefix before adding (e.g. add "md:mt-8" removes "md:mt-4").
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "../sandbox/package.json"));
const { parse } = require("@babel/parser");

function walk(node, fn) {
  if (!node || typeof node.type !== "string") return;
  fn(node);
  for (const k of Object.keys(node)) {
    if (k === "loc" || k === "start" || k === "end") continue;
    const c = node[k];
    if (Array.isArray(c)) c.forEach((x) => walk(x, fn));
    else if (c && typeof c.type === "string") walk(c, fn);
  }
}

function openings(code) {
  const ast = parse(code, { sourceType: "module", plugins: ["jsx"] });
  const out = [];
  walk(ast.program, (n) => {
    if (n.type === "JSXElement" && n.openingElement.name.type === "JSXIdentifier" && /^[a-z]/.test(n.openingElement.name.name)) {
      out.push(n);
    }
  });
  return out.sort((a, b) => a.start - b.start);
}

function attr(op, name) {
  return op.attributes.find((a) => a.type === "JSXAttribute" && a.name?.name === name);
}

function classLiteral(op) {
  const a = attr(op, "className");
  if (!a || !a.value) return null;
  if (a.value.type === "StringLiteral") return { start: a.value.start + 1, end: a.value.end - 1, value: a.value.value };
  const e = a.value.type === "JSXExpressionContainer" ? a.value.expression : null;
  if (e?.type === "StringLiteral") return { start: e.start + 1, end: e.end - 1, value: e.value };
  if (e?.type === "TemplateLiteral" && e.expressions.length === 0) {
    const q = e.quasis[0];
    return { start: q.start, end: q.end, value: q.value.cooked };
  }
  return { dynamic: true };
}

function textOf(el) {
  const parts = [];
  walk(el, (n) => { if (n.type === "JSXText" && n.value.trim()) parts.push(n.value.trim()); });
  return parts.join(" ").slice(0, 60);
}

function tag(code) {
  const els = openings(code);
  let out = code, shift = 0;
  const list = [];
  els.forEach((el, i) => {
    const op = el.openingElement;
    const existing = attr(op, "data-pc");
    const cls = classLiteral(op);
    list.push({ id: i, tag: op.name.name, class: cls?.value ?? (cls?.dynamic ? "(dynamic)" : ""), text: textOf(el) });
    if (existing) return;
    const at = op.name.end + shift;
    const ins = ` data-pc="${i}"`;
    out = out.slice(0, at) + ins + out.slice(at);
    shift += ins.length;
  });
  return { code: out, elements: list };
}

// "md:mt-[18px]" -> variant "md:", property key "mt"
function key(cls) {
  const i = cls.lastIndexOf(":");
  const variant = i >= 0 ? cls.slice(0, i + 1) : "";
  let base = i >= 0 ? cls.slice(i + 1) : cls;
  base = base.replace(/^!/, "").replace(/^-/, "");
  const groups = [
    /^(m[trblxy]?)-/, /^(p[trblxy]?)-/, /^(w)-/, /^(h)-/, /^(min-w)-/, /^(min-h)-/, /^(max-w)-/, /^(max-h)-/,
    /^(gap(-[xy])?)-/, /^(space-[xy])-/, /^(top|left|right|bottom|inset(-[xy])?)-/, /^(rounded(-[trbl]{1,2})?)(-|$)/,
    /^(leading)-/, /^(tracking)-/, /^(grid-cols)-/, /^(grid-rows)-/, /^(col-span)-/, /^(order)-/, /^(z)-/, /^(basis)-/,
    /^(opacity)-/, /^(font)-(thin|extralight|light|normal|medium|semibold|bold|extrabold|black|\[)/,
  ];
  for (const g of groups) { const m = base.match(g); if (m) return variant + m[1]; }
  if (/^text-(xs|sm|base|lg|[0-9]?xl|\[\d)/.test(base)) return variant + "text-size";
  if (/^text-/.test(base)) return variant + "text-color";
  if (/^bg-/.test(base)) return variant + "bg";
  if (/^border(-[trblxy])?-(\[#|#|[a-z]+-\d|white|black|transparent)/.test(base)) return variant + "border-color";
  if (/^(block|inline|inline-block|flex|inline-flex|grid|inline-grid|hidden|contents|table)$/.test(base)) return variant + "display";
  if (/^flex-(row|col)(-reverse)?$/.test(base)) return variant + "flex-dir";
  if (/^(items|justify|self|content|place)-/.test(base)) return variant + base.split("-")[0];
  if (/^text-(left|center|right|justify)$/.test(base)) return variant + "text-align";
  if (/^(static|relative|absolute|fixed|sticky)$/.test(base)) return variant + "position";
  return variant + base;  // exact-match only
}

// ---- breakpoint-scoped edits -------------------------------------------------------------------
// Levels by viewport: mobile 390 (no prefix), tablet 768 (sm:, md:), desktop 1280 (sm:, md:, lg:, xl:).
const RESP = /^(sm|md|lg|xl|2xl):/;
const CHAIN = { mobile: [""], tablet: ["md:", "sm:", ""], desktop: ["xl:", "lg:", "md:", "sm:", ""] };
const PREFIX = { mobile: "", tablet: "md:", desktop: "xl:" };
// value to pin when a breakpoint previously had NO class for a property (Tailwind/browser default)
const DEFAULTS = { m: "m-0", mt: "mt-0", mb: "mb-0", ml: "ml-0", mr: "mr-0", mx: "mx-0", my: "my-0",
  p: "p-0", pt: "pt-0", pb: "pb-0", pl: "pl-0", pr: "pr-0", px: "px-0", py: "py-0", gap: "gap-0", "gap-x": "gap-x-0",
  "gap-y": "gap-y-0", w: "w-auto", h: "h-auto", "max-w": "max-w-none", "min-h": "min-h-0", "text-align": "text-left",
  "flex-dir": "flex-row", "grid-cols": "grid-cols-none", order: "order-none", rounded: "rounded-none",
  "text-size": "text-base", "space-y": "space-y-0", "space-x": "space-x-0", leading: "leading-normal", font: "font-normal",
  tracking: "tracking-normal", "min-w": "min-w-0", "max-h": "max-h-none" };

function bare(c) { return c.replace(RESP, ""); }   // keeps a leading "!" (important) — key() ignores it

function effective(classes, bp, k) {
  for (const pre of CHAIN[bp]) {
    const hit = classes.find((c) => (c.match(RESP)?.[0] ?? "") === pre && key(bare(c)) === k);
    if (hit) return bare(hit);
  }
  return null;
}

function scopedEdit(classes, bp, addList, pins) {
  const notes = [];
  let out = [...classes];
  for (const raw of addList) {
    const b = bare(raw), k = key(b), pre = PREFIX[bp];
    const before = { tablet: effective(out, "tablet", k), desktop: effective(out, "desktop", k) };
    out = out.filter((c) => !((c.match(RESP)?.[0] ?? "") === pre && key(bare(c)) === k));
    if (b.startsWith("!")) {
      // an important class beats every non-important class of the property at ANY breakpoint: promote the
      // others to important (same values; Tailwind orders md:/xl: after base, so they still win where they apply)
      out = out.map((c) => {
        const p = c.match(RESP)?.[0] ?? "";
        return p !== pre && key(bare(c)) === k && !bare(c).startsWith("!") ? p + "!" + bare(c) : c;
      });
    }
    out.push(pre + b);
    const pin = (level, lvlPre) => {
      const has = out.some((c) => CHAIN[level].slice(0, CHAIN[level].indexOf(pre) >= 0 ? CHAIN[level].indexOf(pre) : undefined)
        .includes(c.match(RESP)?.[0] ?? "") && (c.match(RESP)?.[0] ?? "") !== pre && key(bare(c)) === k);
      if (has && !(pins || {})[level]) return;   // that breakpoint has its own, more specific value: unaffected
      // explicit pins (computed values from the render) beat class-derived guesses: inherited properties and
      // parent-set margins (space-y) don't appear in the element's own classes (a leak found in a live run)
      const explicit = (pins || {})[level];
      const pinned = explicit ? [].concat(explicit).find((c) => key(bare(c)) === k) : null;
      if (pinned) { out = out.filter((c) => !((c.match(RESP)?.[0] ?? "") === lvlPre && key(bare(c)) === k)); out.push(lvlPre + pinned); notes.push(`pinned ${lvlPre}${pinned} (computed)`); return; }
      const old = before[level] ?? DEFAULTS[k.replace(/^.*:/, "")] ?? null;
      // an important (!) class beats non-important md:/xl: classes, so the pin must be important too
      const imp = b.startsWith("!") && old && !old.startsWith("!") ? "!" : "";
      if (old && old !== b) { out.push(lvlPre + imp + old); notes.push(`pinned ${lvlPre}${imp}${old}`); }
      else if (!old) notes.push(`could not pin ${level} for ${k}`);
    };
    if (bp === "mobile") pin("tablet", "md:");
    if (bp === "mobile" && (pins || {}).desktop) pin("desktop", "xl:");
    if (bp === "tablet") pin("desktop", "xl:");
  }
  return { classes: out, notes };
}

// Tailwind spacing class → px ("mt-4" 16, "mt-[13px]" 13, "-mt-2" -8, "mt-px" 1); null if not a px length
function spacingPx(cls) {
  if (!cls) return 0;
  const neg = cls.startsWith("-") ? -1 : 1;
  const v = cls.replace(/^-/, "").replace(/^[a-z-]+?-(?=\[|\d|px$)/, "");
  if (v === "px") return neg;
  let m = v.match(/^\[(-?\d+(?:\.\d+)?)px\]$/);
  if (m) return neg * Number(m[1]);
  m = v.match(/^(\d+(?:\.\d+)?)$/);
  if (m) return neg * Number(m[1]) * 4;
  return null;
}

// delta edit: {id, bp, delta: {mt: +14}} → read the current value of that property at bp, write current+Δ
function deltaToAdd(classes, bp, delta) {
  const adds = [], notes = [];
  for (const [prop, d] of Object.entries(delta || {})) {
    const cur = effective(classes, bp, prop);
    const px = cur ? spacingPx(cur) : 0;
    if (px === null) { notes.push(`${prop}: current ${cur} is not a px length`); continue; }
    const v = Math.round(px + Number(d));
    adds.push(v < 0 ? `-${prop}-[${-v}px]` : `${prop}-[${v}px]`);
  }
  return { adds, notes };
}

function apply(code, edits) {
  const els = openings(code);
  const byId = new Map();
  els.forEach((el) => {
    const a = attr(el.openingElement, "data-pc");
    if (a?.value?.type === "StringLiteral") byId.set(Number(a.value.value), el);
  });
  const patches = [], skipped = [];
  // group by element: several edits to one element (e.g. mobile + tablet + desktop) must compose into ONE
  // patch of its class list — separate patches over the same range corrupted the file (found in a live run)
  const groups = new Map();
  for (const e of edits || []) {
    const id = Number(e.id);
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(e);
  }
  for (const [id, group] of groups) {
    const el = byId.get(id);
    if (!el) { skipped.push({ id, why: "no such element" }); continue; }
    const op = el.openingElement;
    const lit = classLiteral(op);
    if (lit?.dynamic) { skipped.push({ id, why: "className is dynamic" }); continue; }
    let classes = (lit?.value || "").split(/\s+/).filter(Boolean);
    for (const e of group) {
      let add = String(e.add || "").split(/\s+/).filter(Boolean);
      const remove = new Set(String(e.remove || "").split(/\s+/).filter(Boolean));
      if (e.delta && e.bp && PREFIX[e.bp] !== undefined) {
        const d = deltaToAdd(classes, e.bp, e.delta);
        add = add.concat(d.adds);
        if (d.notes.length) skipped.push({ id, why: d.notes.join("; "), partial: true });
      }
      if (e.bp && e.bp !== "all" && PREFIX[e.bp] !== undefined) {
        const pre = PREFIX[e.bp];
        const addKeys = new Set(add.map((c) => key(bare(c))));
        const resets = [...remove].filter((c) => (c.match(RESP)?.[0] ?? "") === pre && !addKeys.has(key(bare(c))))
          .map((c) => DEFAULTS[key(bare(c)).replace(/^.*:/, "")]).filter(Boolean);
        const r = scopedEdit(classes, e.bp, [...add, ...resets], e.pins);
        classes = r.classes;
        if (r.notes.some((n) => n.startsWith("could not"))) skipped.push({ id, why: r.notes.join("; "), partial: true });
      } else {
        classes = classes.filter((c) => !remove.has(c));
        const addKeys = new Set(add.map(key));
        classes = classes.filter((c) => !addKeys.has(key(c)));
        for (const c of add) if (!classes.includes(c)) classes.push(c);
      }
    }
    const value = classes.join(" ");
    if (/["`\\{}]/.test(value)) { skipped.push({ id, why: "unsafe characters" }); continue; }
    if (lit) patches.push({ id, start: lit.start, end: lit.end, text: value });
    else patches.push({ id, start: op.name.end, end: op.name.end, text: ` className="${value}"` });
  }
  patches.sort((a, b) => b.start - a.start);   // back to front: earlier offsets stay valid
  let out = code, applied = 0;
  for (const p of patches) {
    const next = out.slice(0, p.start) + p.text + out.slice(p.end);
    try {
      parse(next, { sourceType: "module", plugins: ["jsx"] });
      out = next; applied++;
    } catch (err) {
      skipped.push({ id: p.id, why: `edit would break parsing: ${String(err.message).slice(0, 120)}` });
    }
  }
  return { code: out, applied, skipped };
}

// ---- structural tools (Nemotron's tool calls) ----------------------------------------------------
// Each op is applied to the source by AST ranges; elements are addressed by data-pc ids. Inserted JSX must
// contain NO text (only text-free elements such as rules, icon boxes, wrappers) so tools can't fake content.
function elementsById(code) {
  const map = new Map();
  for (const el of openings(code)) {
    const a = attr(el.openingElement, "data-pc");
    if (a?.value?.type === "StringLiteral") map.set(Number(a.value.value), el);
  }
  return map;
}

function parentOf(code, el) {
  const ast = parse(code, { sourceType: "module", plugins: ["jsx"] });
  let found = null;
  walk(ast.program, (n) => {
    if (n.type === "JSXElement" && n.children?.some((c) => c.start === el.start && c.end === el.end)) found = n;
  });
  return found;
}

function textFree(jsx) {
  const ast = parse(`const x = (${jsx});`, { sourceType: "module", plugins: ["jsx"] });
  let ok = true, count = 0;
  walk(ast.program, (n) => {
    if (n.type === "JSXText" && n.value.trim()) ok = false;
    if (n.type === "StringLiteral" && n.extra?.parenthesized) ok = false;
    if (n.type === "JSXExpressionContainer" && n.expression.type !== "JSXEmptyExpression" &&
        !(n.expression.type === "StringLiteral" || n.expression.type === "TemplateLiteral")) ok = false;
    if (n.type === "JSXElement") count++;
  });
  return ok && count >= 1 && count <= 8;
}

function structural(code, ops) {
  const done = [], skipped = [];
  let out = code;
  for (const op of ops || []) {
    try {
      const els = elementsById(out);
      let next = null;
      if (op.op === "set_layout") {
        const lay = { grid: `grid grid-cols-${Math.max(1, Math.min(12, op.cols || 2))}`, "flex-row": "flex flex-row flex-wrap",
          "flex-col": "flex flex-col", block: "block" }[op.layout];
        if (!lay) throw new Error("unknown layout");
        const add = [lay, op.gap_x != null ? `gap-x-[${op.gap_x}px]` : "", op.gap_y != null ? `gap-y-[${op.gap_y}px]` : ""].join(" ").trim();
        const r = apply(out, [{ id: op.id, bp: op.bp || "all", add }]);
        if (!r.applied) throw new Error(r.skipped?.[0]?.why || "not applied");
        next = r.code;
      } else if (op.op === "wrap") {
        const ids = (op.ids || []).map(Number);
        const nodes = ids.map((i) => els.get(i));
        if (nodes.some((n) => !n) || !nodes.length) throw new Error("unknown id");
        const par = parentOf(out, nodes[0]);
        if (!par || nodes.some((n) => parentOf(out, n)?.start !== par.start)) throw new Error("ids must be siblings");
        nodes.sort((a, b) => a.start - b.start);
        const cls = String(op.classes || "").replace(/["`{}\\]/g, "");
        next = out.slice(0, nodes[0].start) + `<div className="${cls}">` + out.slice(nodes[0].start, nodes.at(-1).end) +
          "</div>" + out.slice(nodes.at(-1).end);
      } else if (op.op === "move") {
        const el = els.get(Number(op.id)), ref = els.get(Number(op.before ?? op.after));
        if (!el || !ref || el === ref) throw new Error("unknown id");
        if (ref.start >= el.start && ref.end <= el.end) throw new Error("cannot move into itself");
        const chunk = out.slice(el.start, el.end);
        const without = out.slice(0, el.start) + out.slice(el.end);
        const shift = ref.start > el.start ? el.end - el.start : 0;
        const at = op.before != null ? ref.start - shift : ref.end - shift;
        next = without.slice(0, at) + chunk + without.slice(at);
      } else if (op.op === "insert") {
        const jsx = String(op.jsx || "");
        if (!textFree(jsx)) throw new Error("inserted JSX must be text-free elements only");
        const ref = els.get(Number(op.after ?? op.before ?? op.into));
        if (!ref) throw new Error("unknown id");
        if (op.into != null) {
          const close = ref.closingElement;
          if (!close) throw new Error("into: self-closing element");
          next = out.slice(0, close.start) + jsx + out.slice(close.start);
        } else {
          const at = op.after != null ? ref.end : ref.start;
          next = out.slice(0, at) + jsx + out.slice(at);
        }
      } else if (op.op === "remove") {
        const el = els.get(Number(op.id));
        if (!el) throw new Error("unknown id");
        next = out.slice(0, el.start) + out.slice(el.end);
      } else if (op.op === "set_tag") {
        const el = els.get(Number(op.id));
        const tag = String(op.tag || "");
        if (!el || !/^(div|section|header|footer|nav|main|button|a|h1|h2|h3|p|span|ul|li|label)$/.test(tag)) throw new Error("bad id/tag");
        const o = el.openingElement, c = el.closingElement;
        next = out;
        if (c) next = next.slice(0, c.name.start) + tag + next.slice(c.name.end);
        next = next.slice(0, o.name.start) + tag + next.slice(o.name.end);
      } else {
        throw new Error(`unknown op ${op.op}`);
      }
      parse(next, { sourceType: "module", plugins: ["jsx"] });
      out = next;
      done.push(op);
    } catch (err) {
      skipped.push({ op, why: String(err.message).slice(0, 160) });
    }
  }
  return { code: out, applied: done.length, skipped };
}

const cmd = process.argv[2];
const input = JSON.parse(fs.readFileSync(0, "utf8"));
try {
  const res = cmd === "tag" ? tag(input.code) : cmd === "apply" ? apply(input.code, input.edits)
    : cmd === "structural" ? structural(input.code, input.ops) : { error: "unknown command" };
  process.stdout.write(JSON.stringify(res));
} catch (err) {
  process.stdout.write(JSON.stringify({ error: String(err.message).slice(0, 300) }));
  process.exit(4);
}
