import type { Plugin } from "vite";

/** Extend the library's own dictionaries without patching node_modules or global browser state. */
export function addKazakhTableLocale(code: string, id: string, dictionaryModule: string) {
  const match = id.replaceAll("\\", "/").match(/\/react-aria\/dist\/private\/(grid|table)\/intlStrings\.(?:m?js)(?:\?.*)?$/);
  if (!match) return null;
  const exported = code.match(/export\s*\{\s*([\w$]+)\s+as\s+default\s*\}/);
  if (!exported) throw new Error("React Aria locale module changed: review the Kazakh table dictionary integration.");
  const name = match[1] === "grid" ? "kazakhGridStrings" : "kazakhTableStrings";
  return `import { ${name} as forteKazakhStrings } from ${JSON.stringify(dictionaryModule)};\n${code.slice(0, exported.index)}\n${exported[1]}["kk-KZ"] = forteKazakhStrings;\n${code.slice(exported.index)}`;
}

export function reactAriaKazakh(dictionaryModule: string): Plugin {
  return {
    name: "forte:react-aria-kazakh", enforce: "pre",
    transform(code, id) { return addKazakhTableLocale(code, id, dictionaryModule); },
  };
}
