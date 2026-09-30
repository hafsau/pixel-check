// Pixel-Check static lint: anything here makes a candidate's score 0.
//
//   node lint.mjs /work/App.jsx        -> {"ok": bool, "violations": [{rule, detail, line}]} on stdout
//
// Why each rule exists:
//   media tags / url( / data: / base64      — embedding the target (or any picture) instead of building it
//   svg                                      — vector paths can trace a design; targets use solid blocks only
//   width detection in JS                    — switching layouts in JS is fake responsive, and it would
//                                              also defeat the runtime duplicate-layout check in render.mjs
//   non-react imports                        — nothing else exists in the sandbox; also blocks sneaky loaders
//   dangerouslySetInnerHTML / <style>        — hides markup and CSS from these checks
// Runtime checks (render.mjs → checks.json.integrity): positioned-element ratio, duplicated layouts.
import fs from "node:fs";
import { parse } from "@babel/parser";

const BANNED_TAGS = new Set(["img", "image", "picture", "video", "audio", "canvas", "iframe", "object",
  "embed", "svg", "source", "track", "style", "link", "script", "base", "frame", "frameset"]);
const BANNED_TEXT = [
  [/url\s*\(/i, "url("],
  [/\bdata\s*:/i, "data: URI"],
  [/background-image/i, "background-image"],
  [/backgroundImage/, "backgroundImage"],
  [/\bbg-\[url/i, "Tailwind arbitrary bg url"],
  [/\bbg-gradient-to-|\bfrom-\[|\bconic|\bradial-gradient|\blinear-gradient/i, null], // allowed; listed for clarity
  [/matchMedia|innerWidth|outerWidth|clientWidth|screen\.width|visualViewport|ResizeObserver|addEventListener\(\s*['"]resize/,
    "JS width detection"],
  [/dangerouslySetInnerHTML/, "dangerouslySetInnerHTML"],
  [/\b(fetch|XMLHttpRequest|WebSocket|EventSource|importScripts)\b/, "network API"],
  [/\beval\s*\(|new\s+Function\s*\(/, "dynamic code"],
];
const BASE64_RUN = /[A-Za-z0-9+/=]{200,}/;

export function lint(src) {
  const v = [];
  const lineOf = (idx) => src.slice(0, idx).split("\n").length;
  for (const [re, name] of BANNED_TEXT) {
    if (!name) continue;
    const m = re.exec(src);
    if (m) v.push({ rule: "banned-text", detail: name, line: lineOf(m.index) });
  }
  const b = BASE64_RUN.exec(src);
  if (b) v.push({ rule: "base64", detail: `${b[0].length}-char run`, line: lineOf(b.index) });

  let ast;
  try {
    ast = parse(src, { sourceType: "module", plugins: ["jsx"], errorRecovery: false });
  } catch (e) {
    v.push({ rule: "parse-error", detail: String(e.message).slice(0, 200), line: e.loc?.line ?? null });
    return { ok: false, violations: v };
  }
  let exportsDefault = false;
  const walk = (node) => {
    if (!node || typeof node.type !== "string") return;
    if (node.type === "ImportDeclaration" && !["react", "react/jsx-runtime"].includes(node.source.value)) {
      v.push({ rule: "import", detail: node.source.value, line: node.loc.start.line });
    }
    if (node.type === "ImportExpression" || (node.type === "CallExpression" && node.callee.type === "Import")) {
      v.push({ rule: "import", detail: "dynamic import()", line: node.loc.start.line });
    }
    if (node.type === "CallExpression" && node.callee.type === "Identifier" && node.callee.name === "require") {
      v.push({ rule: "import", detail: "require()", line: node.loc.start.line });
    }
    if (node.type === "ExportDefaultDeclaration") exportsDefault = true;
    if (node.type === "JSXOpeningElement") {
      const n = node.name;
      const tag = n.type === "JSXIdentifier" ? n.name : n.type === "JSXNamespacedName" ? `${n.namespace.name}:${n.name.name}` : null;
      if (tag && BANNED_TAGS.has(tag.toLowerCase())) {
        v.push({ rule: "banned-tag", detail: `<${tag}>`, line: node.loc.start.line });
      }
      if (tag && /^[a-z]/.test(tag) && tag.includes("-")) {
        v.push({ rule: "banned-tag", detail: `custom element <${tag}>`, line: node.loc.start.line });
      }
      // React.createElement("img") style dodges are caught below.
    }
    if (node.type === "CallExpression") {
      const c = node.callee;
      const isCreate = (c.type === "MemberExpression" && c.property?.name === "createElement") ||
        (c.type === "Identifier" && ["createElement", "jsx", "jsxs", "_jsx", "_jsxs"].includes(c.name));
      const first = node.arguments[0];
      if (isCreate && first?.type === "StringLiteral" && BANNED_TAGS.has(first.value.toLowerCase())) {
        v.push({ rule: "banned-tag", detail: `createElement("${first.value}")`, line: node.loc.start.line });
      }
      if (isCreate && first && first.type !== "StringLiteral" && first.type !== "Identifier" && first.type !== "MemberExpression") {
        v.push({ rule: "banned-tag", detail: "computed element type", line: node.loc.start.line });
      }
    }
    for (const key of Object.keys(node)) {
      if (key === "loc" || key === "start" || key === "end") continue;
      const child = node[key];
      if (Array.isArray(child)) child.forEach(walk);
      else if (child && typeof child.type === "string") walk(child);
    }
  };
  walk(ast.program);
  if (!exportsDefault) v.push({ rule: "no-default-export", detail: "App must be the default export", line: null });
  return { ok: v.length === 0, violations: v };
}

if (process.argv[1] && process.argv[1].endsWith("lint.mjs")) {
  const res = lint(fs.readFileSync(process.argv[2] ?? "/work/App.jsx", "utf8"));
  process.stdout.write(JSON.stringify(res));
  process.exit(res.ok ? 0 : 3);
}
