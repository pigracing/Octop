declare const __APP_NAME__: string | undefined;

/**
 * Build-time product name from desktop/branding.json (Vite `define`).
 * Tests and unbranded builds fall back to the upstream name.
 */
export const APP_NAME =
  typeof __APP_NAME__ === "string" && __APP_NAME__.trim()
    ? __APP_NAME__
    : "Octop";
