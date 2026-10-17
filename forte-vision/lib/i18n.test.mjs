import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function readModule(path, parent = import.meta.url) {
  const url = new URL(path, parent);
  const source = readFileSync(url, "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => readModule(`${name}.ts`, url) });
  return exports;
}
const { parseLocale, serializeLocaleCookie, createTranslator, LOCALE_COOKIE, LOCALE_TAGS } = readModule("./i18n.ts");
const { commonMessages } = readModule("./messages/common.ts");

test("only the three supported languages are selected, including regional locale tags", () => {
  for (const value of ["kk", "kk-KZ", " KK_kz "]) assert.equal(parseLocale(value), "kk");
  for (const value of ["en", "en-US", " EN_gb "]) assert.equal(parseLocale(value), "en");
  for (const value of ["ru", "ru-RU", "kz", "fr", "en<script>", null, undefined, {}, 1]) assert.equal(parseLocale(value), "ru");
  assert.equal(LOCALE_TAGS.kk, "kk-KZ");
  assert.equal(new Intl.DateTimeFormat(LOCALE_TAGS.en).resolvedOptions().locale, "en-GB");
});

test("language cookies persist the canonical preference with same-site and HTTPS protection", () => {
  assert.equal(LOCALE_COOKIE, "forte-locale");
  assert.equal(serializeLocaleCookie("kk", true), "forte-locale=kk; Path=/; Max-Age=31536000; SameSite=Lax; Secure");
  assert.equal(serializeLocaleCookie("en", false), "forte-locale=en; Path=/; Max-Age=31536000; SameSite=Lax");
  assert.equal(serializeLocaleCookie("en; Domain=example.org", true), "forte-locale=ru; Path=/; Max-Age=31536000; SameSite=Lax; Secure");
});

test("feature translations take precedence, then common phrases, while backend text is preserved", () => {
  const feature = { "Войти": { kk: "Аккаунтқа кіру", en: "Sign in to account" }, "Видео": { kk: "Бейне", en: "Video" } };
  const en = createTranslator("en", feature, commonMessages);
  assert.equal(en("Войти"), "Sign in to account");
  assert.equal(en("Закрыть"), "Close");
  assert.equal(en("Название_записи_из_API.mov"), "Название_записи_из_API.mov");
  assert.equal(createTranslator("kk", feature, commonMessages)("Видео"), "Бейне");
  assert.equal(createTranslator("ru", feature, commonMessages)("Войти"), "Войти");
});

test("interpolation accepts zero and literal replacement symbols and retains missing values", () => {
  const source = "Проверка {name}: {count}, {missing}";
  const t = createTranslator("en", { [source]: { kk: "Тексеру {name}: {count}, {missing}", en: "Check {name}: {count}, {missing}" } });
  assert.equal(t(source, { name: "$&.mov", count: 0 }), "Check $&.mov: 0, {missing}");
  assert.equal(createTranslator("ru")("Запись {id}", { id: 12 }), "Запись 12");
  assert.equal(t(source), "Check {name}: {count}, {missing}");
});

test("all shared control labels contain both translations and work without feature dictionaries", () => {
  for (const [source, translations] of Object.entries(commonMessages)) {
    for (const locale of ["kk", "en"]) {
      assert.ok(translations[locale]?.trim(), `${source} is missing ${locale}`);
      assert.equal(createTranslator(locale, {}, commonMessages)(source), translations[locale]);
    }
  }
});

test("every feature dictionary has complete translations and matching interpolation placeholders", () => {
  const placeholders = value => [...value.matchAll(/\{([^{}]+)\}/g)].map(match => match[1]).sort();
  for (const file of readdirSync(new URL("./messages/", import.meta.url)).filter(name => name.endsWith(".ts"))) {
    for (const messages of Object.values(readModule(`./messages/${file}`))) {
      for (const [source, translations] of Object.entries(messages)) {
        for (const locale of ["kk", "en"]) {
          assert.ok(translations[locale]?.trim(), `${file}: ${source} is missing ${locale}`);
          assert.deepEqual(placeholders(translations[locale]), placeholders(source), `${file}: ${source} (${locale})`);
        }
      }
    }
  }
});

test("literal interface messages resolve in the dictionary actually imported by each component", () => {
  const missing = [];
  function walk(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const file = new URL(entry.name + (entry.isDirectory() ? "/" : ""), directory);
      if (entry.isDirectory()) { walk(file); continue; }
      if (!/\.tsx?$/.test(entry.name)) continue;
      const source = readFileSync(file, "utf8");
      const dictionaries = [...source.matchAll(/import\s*\{\s*(\w+Messages)\s*\}\s*from\s*["']@\/lib\/messages\/([^"']+)/g)]
        .map(match => readModule(`./messages/${match[2]}.ts`)[match[1]]);
      const messages = Object.assign({}, commonMessages, ...dictionaries);
      const ast = ts.createSourceFile(file.pathname, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      function inspectArgument(node) {
        if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
          if (/[А-Яа-яЁё]/.test(node.text) && !messages[node.text]) missing.push(`${file.pathname}: ${node.text}`);
        } else if (ts.isConditionalExpression(node)) { inspectArgument(node.whenTrue); inspectArgument(node.whenFalse); }
      }
      function visit(node) {
        if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "t" && node.arguments[0]) inspectArgument(node.arguments[0]);
        ts.forEachChild(node, visit);
      }
      visit(ast);
    }
  }
  walk(new URL("../components/", import.meta.url));
  walk(new URL("../hooks/", import.meta.url));
  assert.deepEqual(missing, []);
});
