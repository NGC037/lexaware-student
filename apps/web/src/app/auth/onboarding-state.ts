function keyFor(userId: string) { return `lexaware-onboarding-complete-this-tab:${userId}`; }
const memoryCompleted = new Set<string>();

/** This is a temporary tab-local UX marker, not an authenticated/backend profile field. */
export function isOnboardingCompleteThisTab(userId: string): boolean {
  try { return sessionStorage.getItem(keyFor(userId)) === "true"; }
  catch { return memoryCompleted.has(userId); }
}

export function markOnboardingCompleteThisTab(userId: string): void {
  memoryCompleted.add(userId);
  try { sessionStorage.setItem(keyFor(userId), "true"); } catch { /* Keep completion for this mounted app session. */ }
}
