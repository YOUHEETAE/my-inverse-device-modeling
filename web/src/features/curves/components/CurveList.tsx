import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CurveEntry } from "../types";

interface CurveListProps {
  curves: CurveEntry[];
  activeId: number;
  onSelect: (id: number) => void;
  onToggleVisible: (id: number) => void;
  onUpdateSelected: () => void;
  onRemoveSelected: () => void;
}

export function CurveList({
  curves,
  activeId,
  onSelect,
  onToggleVisible,
  onUpdateSelected,
  onRemoveSelected,
}: CurveListProps) {
  return (
    <div className="flex flex-col gap-2">
      {/* Fixed height (not max-h): keeps this area a constant size regardless
          of curve count, so sections below don't shift as curves are
          added/removed. Sized for header + 3 rows; overflow-y scrolls once a
          4th curve is added. Height + both overflow axes live on the same
          element (Table's own container) — splitting them across nested
          divs breaks position:sticky on the header cells (mismatched
          overflow-x/overflow-y on different ancestors defeats the sticky
          containing block). */}
      <Table containerClassName="h-[175px] overflow-y-auto">
        <TableHeader>
          <TableRow className="border-outline-variant hover:bg-transparent">
            <TableHead className="sticky top-0 z-10 w-8 bg-surface-container"></TableHead>
            <TableHead className="sticky top-0 z-10 bg-surface-container font-mono text-[10px] uppercase text-on-surface-variant">Curve</TableHead>
            <TableHead className="sticky top-0 z-10 bg-surface-container font-mono text-[10px] uppercase text-on-surface-variant">L</TableHead>
            <TableHead className="sticky top-0 z-10 bg-surface-container font-mono text-[10px] uppercase text-on-surface-variant">T</TableHead>
            <TableHead className="sticky top-0 z-10 bg-surface-container font-mono text-[10px] uppercase text-on-surface-variant">B</TableHead>
            <TableHead className="sticky top-0 z-10 bg-surface-container font-mono text-[10px] uppercase text-on-surface-variant">SD</TableHead>
            <TableHead className="sticky top-0 z-10 bg-surface-container font-mono text-[10px] uppercase text-on-surface-variant">LDD</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {curves.map((curve) => (
            <TableRow
              key={curve.id}
              onClick={() => onSelect(curve.id)}
              className={
                curve.id === activeId
                  ? "cursor-pointer border-outline-variant bg-surface-container-highest"
                  : "cursor-pointer border-outline-variant hover:bg-surface-container-highest"
              }
            >
              <TableCell onClick={(event) => event.stopPropagation()}>
                <Checkbox
                  checked={curve.visible}
                  onCheckedChange={() => {
                    onToggleVisible(curve.id);
                    onSelect(curve.id);
                  }}
                />
              </TableCell>
              <TableCell className="font-medium">{curve.label}</TableCell>
              <TableCell className="font-mono text-xs">{curve.parameters.L}</TableCell>
              <TableCell className="font-mono text-xs">{curve.parameters.T}</TableCell>
              <TableCell className="font-mono text-xs">{curve.parameters.B}</TableCell>
              <TableCell className="font-mono text-xs">{curve.parameters.SD}</TableCell>
              <TableCell className="font-mono text-xs">{curve.parameters.LDD}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex gap-2 border-t border-outline-variant p-2">
        <Button size="sm" variant="ghost" className="flex-1 text-xs" onClick={onUpdateSelected}>
          Update Selected
        </Button>
        <Button size="sm" variant="ghost" className="flex-1 text-xs" onClick={onRemoveSelected}>
          Remove Selected
        </Button>
      </div>
    </div>
  );
}
