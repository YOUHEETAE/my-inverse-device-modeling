// Chapter id/label pairs only — kept separate from TheoryPage's content JSX
// so the main Sidebar (mounted on every route) can render the chapter list
// as nested navigation without pulling in the page's full content/tool tree.
export const THEORY_CHAPTERS: { id: string; label: string }[] = [
  { id: "overview", label: "개요" },
  { id: "chapter1", label: "1. PN Junction" },
  { id: "chapter2", label: "2. Long-Channel MOSFET" },
  { id: "chapter3", label: "3. Short-Channel MOSFET" },
  { id: "chapter4", label: "4. MOSFET Performance Enhancement" },
  { id: "chapter5", label: "5. Python TCAD" },
];
