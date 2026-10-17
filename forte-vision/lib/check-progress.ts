import type { StoredCheck } from "@/lib/checks";
/** Keep absent progress absent, including after a reply drops its percentage. */
export function checkProgress(check: StoredCheck): number | undefined {
  const value = check.status === "uploading" ? check.uploadProgress : check.progress;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100 ? value : undefined;
}
