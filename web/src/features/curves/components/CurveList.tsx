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
      {/* max-h + overflow-y: caps the list height once many curves are added
          (rows scroll). overflow-x: the 7 columns are wider than the panel
          (columns scroll). Two different problems, both handled here. */}
      <div className="max-h-48 overflow-y-auto overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-outline-variant hover:bg-transparent">
              <TableHead className="w-8"></TableHead>
              <TableHead className="font-mono text-[10px] uppercase text-on-surface-variant">Curve</TableHead>
              <TableHead className="font-mono text-[10px] uppercase text-on-surface-variant">L</TableHead>
              <TableHead className="font-mono text-[10px] uppercase text-on-surface-variant">T</TableHead>
              <TableHead className="font-mono text-[10px] uppercase text-on-surface-variant">B</TableHead>
              <TableHead className="font-mono text-[10px] uppercase text-on-surface-variant">SD</TableHead>
              <TableHead className="font-mono text-[10px] uppercase text-on-surface-variant">LDD</TableHead>
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
                    onCheckedChange={() => onToggleVisible(curve.id)}
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
      </div>
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
