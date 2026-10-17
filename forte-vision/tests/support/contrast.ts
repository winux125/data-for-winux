/** WCAG sRGB contrast calculation. QA-only: never imported by the application. */
export function contrastRatio(foreground: string, background: string) {
  const luminance = (hex: string) => {
    const rgb = hex.replace(/^#/, "").match(/../g)!.map(value => Number.parseInt(value, 16) / 255);
    return rgb.map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
      .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
  };
  const first = luminance(foreground), second = luminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

/** Evaluated in the browser. Image/gradient and translucent groups require a separate check. */
export function auditTextContrast() {
  const rgba = (value: string) => {
    const values = value.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0];
    const scale = value.startsWith("color(srgb") ? 255 : 1;
    return [values[0] * scale, values[1] * scale, values[2] * scale, values[3] ?? 1];
  };
  const composite = (front: number[], back: number[]) => [0, 1, 2].map(index => front[index] * front[3] + back[index] * (1 - front[3]));
  const luminance = (rgb: number[]) => rgb.slice(0, 3).map(value => {
    value /= 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
  const failures: { text: string; selector: string; ratio: number }[] = [];
  const skipped: { text: string; reason: string }[] = [];
  let checked = 0, minimum = 21;
  for (const element of document.querySelectorAll<HTMLElement>("body *")) {
    const text = Array.from(element.childNodes).filter(node => node.nodeType === 3).map(node => node.textContent?.trim()).join(" ").trim();
    const placeholder = element.matches("input[placeholder],textarea[placeholder]") ? element.getAttribute("placeholder") : null;
    if (!text && !placeholder) continue;
    const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
    if (rect.width < 2 || rect.height < 2 || style.visibility !== "visible" || element.closest('[aria-hidden="true"],[hidden],[inert],:disabled,[aria-disabled="true"]') || ["STYLE", "SCRIPT", "NOSCRIPT"].includes(element.tagName)) continue;
    const layers: CSSStyleDeclaration[] = [];
    let current: HTMLElement | null = element, complex = false, opacity = 1;
    while (current) {
      const layer = getComputedStyle(current);
      complex ||= layer.backgroundImage !== "none";
      opacity *= Number(layer.opacity);
      layers.unshift(layer); current = current.parentElement;
    }
    if (complex || opacity < 0.99) { skipped.push({ text: (text || placeholder || "").slice(0, 80), reason: complex ? "image/gradient" : "opacity" }); continue; }
    let background = [255, 255, 255];
    for (const layer of layers) background = composite(rgba(layer.backgroundColor), background);
    const samples = [{ text, color: style.color }];
    if (placeholder) samples.push({ text: placeholder, color: getComputedStyle(element, "::placeholder").color });
    for (const sample of samples) {
      if (!sample.text) continue;
      const first = luminance(composite(rgba(sample.color), background)), second = luminance(background);
      const ratio = (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
      checked++; minimum = Math.min(minimum, ratio);
      if (ratio < 4.5) failures.push({ text: sample.text.slice(0, 90), selector: element.className, ratio });
    }
  }
  return { checked, minimum, failures, skipped };
}
