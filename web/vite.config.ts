import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The production build's Rolldown-based bundler corrupts katex's own
// \uD800-\uDBFF surrogate-pair Unicode escapes when it transforms katex's
// source (turning `\uD800` into a literal replacement character + "d800",
// which breaks the tokenizer regex and renders every equation as garbled raw
// LaTeX) — this reproduces even with minification off, so it's a bug in
// Rolldown's own transform step, not the minifier. optimizeDeps.exclude
// (below) only affects the dev server's esbuild pre-bundling and has no
// effect on `vite build` at all, so it can't fix this path.
//
// The fix is to keep Rolldown from ever parsing katex's source: emit
// katex's own prebuilt, already-correct UMD file as a static asset and load
// it via a plain <script> tag (which sets `window.katex`), then alias the
// `katex` import specifier (see resolve.alias below, build-only) to a tiny
// local module that just re-exports that global. Rollup's usual
// external + output.globals escape hatch for this exact scenario does NOT
// carry over to Rolldown — it throws "Calling require for katex in an
// environment that doesn't expose the require function" at runtime, since
// Rolldown needs its own `inject` mechanism instead — so an alias to a real
// (if trivial) ESM module is used here rather than fighting that.
function katexGlobalScriptPlugin(): Plugin {
  const katexMinPath = path.resolve(__dirname, 'node_modules/katex/dist/katex.min.js')
  return {
    name: 'katex-global-script',
    apply: 'build',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'katex.min.js',
        source: fs.readFileSync(katexMinPath, 'utf8'),
      })
    },
    transformIndexHtml: {
      // Must run before Vite's own html plugin rewrites the module script's
      // src from /src/main.tsx to its hashed build output path — 'pre' runs
      // ahead of that, so matching the original source-relative tag is safe.
      // The plain (non-module) script tag runs synchronously before any
      // module script on the page, so `window.katex` is guaranteed to exist
      // by the time the app's module code (and the katex-global.ts alias
      // below) runs.
      order: 'pre',
      handler(html) {
        return html.replace('</head>', '    <script src="/katex.min.js"></script>\n  </head>')
      },
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss(), katexGlobalScriptPlugin()],
  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, './src') },
      // Only during production build — see katexGlobalScriptPlugin above.
      // The dev server keeps resolving 'katex' normally (via
      // optimizeDeps.exclude). Exact-match regex, not a plain string key:
      // a plain 'katex' key also matches 'katex/dist/katex.min.css' (the
      // CSS import in index.css), which would break that resolution too.
      ...(command === 'build'
        ? [{ find: /^katex$/, replacement: path.resolve(__dirname, './src/katex-global.ts') }]
        : []),
    ],
  },
  server: {
    port: 5174,
    strictPort: true,
  },
  optimizeDeps: {
    include: ['react-plotly.js/factory', 'plotly.js-dist-min'],
    exclude: ['katex'],
  },
}))
