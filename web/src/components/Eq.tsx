import { BlockMath } from "react-katex";

// Wraps react-katex's BlockMath with the spacing/overflow handling this
// codebase's theory content needs (long piecewise equations can exceed the
// text column width on narrow viewports).
export function Eq({ tex }: { tex: string }) {
  return (
    <div className="my-1 overflow-x-auto py-1 text-[15px]">
      <BlockMath math={tex} />
    </div>
  );
}
