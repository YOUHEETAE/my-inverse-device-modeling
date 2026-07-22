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
  onAdd: () => void;
  onUpdateSelected: () => void;
  onRemoveSelected: () => void;
}

export function CurveList({
  curves,
  activeId,
  onSelect,
  onToggleVisible,
  onAdd,
  onUpdateSelected,
  onRemoveSelected,
}: CurveListProps) {
  return (
    <div className="flex flex-col gap-2">
      {/* max-h + overflow-y: caps the list height once many curves are added
          (rows scroll). overflow-x: the 7 columns are wider than the panel
          (columns scroll). Two different problems, both handled here. */}
      <div className="max-h-48 overflow-y-auto overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8"></TableHead>
              <TableHead>Curve</TableHead>
              <TableHead>L</TableHead>
              <TableHead>T</TableHead>
              <TableHead>B</TableHead>
              <TableHead>SD</TableHead>
              <TableHead>LDD</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {curves.map((curve) => (
              <TableRow
                key={curve.id}
                onClick={() => onSelect(curve.id)}
                className={
                  curve.id === activeId
                    ? "cursor-pointer bg-accent"
                    : "cursor-pointer"
                }
              >
                <TableCell onClick={(event) => event.stopPropagation()}>
                  <Checkbox
                    checked={curve.visible}
                    onCheckedChange={() => onToggleVisible(curve.id)}
                  />
                </TableCell>
                <TableCell className="font-medium">{curve.label}</TableCell>
                <TableCell>{curve.parameters.L}</TableCell>
                <TableCell>{curve.parameters.T}</TableCell>
                <TableCell>{curve.parameters.B}</TableCell>
                <TableCell>{curve.parameters.SD}</TableCell>
                <TableCell>{curve.parameters.LDD}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" className="flex-1" onClick={onAdd}>
          Add Curve
        </Button>
        <Button size="sm" variant="secondary" className="flex-1" onClick={onUpdateSelected}>
          Update Selected
        </Button>
        <Button size="sm" variant="secondary" className="flex-1" onClick={onRemoveSelected}>
          Remove Selected
        </Button>
      </div>
    </div>
  );
}
