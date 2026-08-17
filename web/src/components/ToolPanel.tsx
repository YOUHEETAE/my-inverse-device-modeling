import { useEffect, useState, type ReactNode } from "react";
import { FlaskConical } from "lucide-react";
import { Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetBody } from "@/components/ui/sheet";

interface ToolPanelProps {
  label?: string;
  // Whether this panel's chapter/case is the one currently selected. The
  // caller is expected to keep every ToolPanel mounted at all times (not
  // just the active one) so switching chapters and coming back doesn't lose
  // the tool's state — this prop just hides the trigger and force-closes
  // the panel while its chapter isn't selected.
  active: boolean;
  children: ReactNode;
}

// A floating button (fixed to the viewport, so it stays reachable no matter
// how far down the reader has scrolled a long chapter) that slides the
// simulator in from the right, instead of the simulator sitting inline at
// the bottom of the article where it's easy to miss.
//
// The Sheet's portal keeps its content mounted even while closed (see
// components/ui/sheet.tsx's keepMounted default), and this component only
// renders `children` once the panel has been opened at least once — so a
// tool's fetched data and selections survive being closed, reopened, or the
// reader navigating to a different chapter and back, without eagerly
// firing every tool's data fetch just because its chapter was selected.
export function ToolPanel({ label = "시뮬레이션", active, children }: ToolPanelProps) {
  const [open, setOpen] = useState(false);
  const [hasOpenedOnce, setHasOpenedOnce] = useState(false);

  // Switching away from this chapter closes the panel (rather than leaving
  // it open in the background) so returning to the chapter later shows the
  // collapsed trigger, not an already-open panel — but hasOpenedOnce stays
  // true, so the tool itself stays mounted and keeps its state.
  useEffect(() => {
    if (!active) setOpen(false);
  }, [active]);

  return (
    <Sheet
      open={active && open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setHasOpenedOnce(true);
      }}
    >
      {active && (
        <SheetTrigger
          render={
            <button
              type="button"
              className="fixed bottom-6 right-6 z-30 flex items-center gap-2 rounded-full border border-primary/20 bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-lg transition-transform hover:scale-105"
            />
          }
        >
          <FlaskConical className="h-4 w-4" />
          {label}
        </SheetTrigger>
      )}
      <SheetContent>
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            {label}
          </SheetTitle>
        </SheetHeader>
        <SheetBody>{hasOpenedOnce && children}</SheetBody>
      </SheetContent>
    </Sheet>
  );
}
