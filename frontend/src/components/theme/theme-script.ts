// Shared by the server layout (inline script) and the client theme store.
// No "use client" here: the server must import the real string value.

export const THEME_STORAGE_KEY = "aszda-theme";

/**
 * Runs before the page paints (inlined in <head>) so there is no flash of the
 * wrong theme. Keep the logic identical to applyTheme in theme-store.ts.
 */
export const THEME_SCRIPT = `(function(){try{var p=localStorage.getItem("${THEME_STORAGE_KEY}");var d=p==="dark"||(p!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.dataset.theme=d?"dark":"light";}catch(e){document.documentElement.dataset.theme="light";}})();`;
