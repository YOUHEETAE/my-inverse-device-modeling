import type { PlotParams } from "react-plotly.js";
import type { ComponentType } from "react";
import Plotly from "plotly.js-dist-min";
import * as PlotlyFactoryModule from "react-plotly.js/factory";

// plotly.js-dist-min is a bundler-friendly build; plain "plotly.js" (used by
// the default react-plotly.js export) breaks Vite's dependency pre-bundling.
//
// react-plotly.js/factory's pre-bundled CJS output ends up double-wrapped
// under `.default` (once from the original module's `exports.default = fn`,
// once more from importing it as a namespace here), so unwrap `.default`
// repeatedly until we land on the actual function instead of assuming a
// fixed nesting depth.
function unwrapDefault(value: unknown): unknown {
  let current = value;
  while (
    current &&
    typeof current !== "function" &&
    typeof current === "object" &&
    "default" in current
  ) {
    current = (current as { default: unknown }).default;
  }
  return current;
}

type PlotlyFactory = (plotly: object) => ComponentType<PlotParams>;
const createPlotlyComponent = unwrapDefault(PlotlyFactoryModule) as PlotlyFactory;

export const Plot = createPlotlyComponent(Plotly);
