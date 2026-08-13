// Re-exports the `katex` global set by the plain <script> tag injected into
// the production build's index.html (see vite.config.ts) as this module's
// default export, matching what `import katex from "katex"` normally
// provides. This exists only so the production build never has to parse or
// transform katex's own source: Rolldown's transform step corrupts katex's
// \uD800-\uDBFF Unicode escapes, and Rollup's usual external+output.globals
// escape hatch doesn't apply the same way in Rolldown, so this alias
// (resolve.alias, build-only — see vite.config.ts) is the fix instead.
export default (globalThis as unknown as { katex: unknown }).katex
