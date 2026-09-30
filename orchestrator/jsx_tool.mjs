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
  base = base.replace(/^-/, "");
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
  "flex-dir": "flex-row", "grid-cols": "grid-cols-none", order: "order-none", rounded: "rounded-none" };

function bare(c) { return c.replace(RESP, ""); }

function effective(classes, bp, k) {
  for (const pre of CHAIN[bp]) {
    const hit = classes.find((c) => (c.match(RESP)?.[0] ?? "") === pre && key(bare(c)) === k);
    if (hit) return bare(hit);
  }
  return null;
}

function scopedEdit(classes, bp, addList) {
  const notes = [];
  let out = [...classes];
  for (const raw of addList) {
    const b = bare(raw), k = key(b), pre = PREFIX[bp];
    const before = { tablet: effective(out, "tablet", k), desktop: effective(out, "desktop", k) };
    out = out.filter((c) => !((c.match(RESP)?.[0] ?? "") === pre && key(bare(c)) === k));
    out.push(pre + b);
    const pin = (level, lvlPre) => {
      const has = out.some((c) => CHAIN[level].slice(0, CHAIN[level].indexOf(pre) >= 0 ? CHAIN[level].indexOf(pre) : undefined)
        .includes(c.match(RESP)?.[0] ?? "") && (c.match(RESP)?.[0] ?? "") !== pre && key(bare(c)) === k);
      if (has) return;   // that breakpoint has its own, more specific value: unaffected
      const old = before[level] ?? DEFAULTS[k.replace(/^.*:/, "")] ?? null;
      if (old && old !== b) { out.push(lvlPre + old); notes.push(`pinned ${lvlPre}${old}`); }
      else if (!old) notes.push(`could not pin ${level} for ${k}`);
    };
    if (bp === "mobile") pin("tablet", "md:");
    if (bp === "tablet") pin("desktop", "xl:");
  }
  return { classes: out, notes };
}

function apply(code, edits) {
  const els = openings(code);
  const byId = new Map();
  els.forEach((el) => {
    const a = attr(el.openingElement, "data-pc");
    if (a?.value?.type === "StringLiteral") byId.set(Number(a.value.value), el);
  });
  const patches = [], skipped = [];
  for (const e of edits || []) {
    const el = byId.get(Number(e.id));
    if (!el) { skipped.push({ id: e.id, why: "no such element" }); continue; }
    const op = el.openingElement;
    const lit = classLiteral(op);
    const add = String(e.add || "").split(/\s+/).filter(Boolean);
    const remove = new Set(String(e.remove || "").split(/\s+/).filter(Boolean));
    if (lit?.dynamic) { skipped.push({ id: e.id, why: "className is dynamic" }); continue; }
    let classes = (lit?.value || "").split(/\s+/).filter(Boolean).filter((c) => !remove.has(c));
    if (e.bp && e.bp !== "all" && PREFIX[e.bp] !== undefined) {
      const r = scopedEdit(classes, e.bp, add);
      classes = r.classes;
      if (r.notes.some((n) => n.startsWith("could not"))) skipped.push({ id: e.id, why: r.notes.join("; "), partial: true });
    } else {
      const addKeys = new Set(add.map(key));
      classes = classes.filter((c) => !addKeys.has(key(c)));
      for (const c of add) if (!classes.includes(c)) classes.push(c);
    }
    const value = classes.join(" ");
    if (/["`\\{}]/.test(value)) { skipped.push({ id: e.id, why: "unsafe characters" }); continue; }
    if (lit) patches.push({ id: e.id, start: lit.start, end: lit.end, text: value });
    else patches.push({ id: e.id, start: op.name.end, end: op.name.end, text: ` className="${value}"` });
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

const cmd = process.argv[2];
const input = JSON.parse(fs.readFileSync(0, "utf8"));
try {
  const res = cmd === "tag" ? tag(input.code) : cmd === "apply" ? apply(input.code, input.edits) : { error: "unknown command" };
  process.stdout.write(JSON.stringify(res));
} catch (err) {
  process.stdout.write(JSON.stringify({ error: String(err.message).slice(0, 300) }));
  process.exit(4);
}
