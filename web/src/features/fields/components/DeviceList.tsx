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
import type { DeviceEntry } from "../types";

interface DeviceListProps {
  devices: DeviceEntry[];
  activeId: number;
  onSelect: (id: number) => void;
  onToggleVisible: (id: number) => void;
  onUpdateSelected: () => void;
  onRemoveSelected: () => void;
}

const HEAD_CLASS = "sticky top-0 z-10 bg-surface-container px-1 py-1 font-mono text-[9px] uppercase text-on-surface-variant";
const CELL_CLASS = "px-1 py-1 font-mono text-[9px]";

export function DeviceList({
  devices,
  activeId,
  onSelect,
  onToggleVisible,
  onUpdateSelected,
  onRemoveSelected,
}: DeviceListProps) {
  return (
    <div className="flex flex-col gap-2">
      <Table containerClassName="h-[175px] overflow-y-auto">
        <TableHeader>
          <TableRow className="border-outline-variant hover:bg-transparent">
            <TableHead className={`${HEAD_CLASS} w-5`}></TableHead>
            <TableHead className={HEAD_CLASS}>Device</TableHead>
            <TableHead className={HEAD_CLASS}>L</TableHead>
            <TableHead className={HEAD_CLASS}>T</TableHead>
            <TableHead className={HEAD_CLASS}>B</TableHead>
            <TableHead className={HEAD_CLASS}>SD</TableHead>
            <TableHead className={HEAD_CLASS}>LDD</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {devices.map((device) => (
            <TableRow
              key={device.id}
              onClick={() => onSelect(device.id)}
              className={
                device.id === activeId
                  ? "cursor-pointer border-outline-variant bg-surface-container-highest"
                  : "cursor-pointer border-outline-variant hover:bg-surface-container-highest"
              }
            >
              <TableCell className={CELL_CLASS} onClick={(event) => event.stopPropagation()}>
                <Checkbox
                  className="size-3"
                  checked={device.visible}
                  onCheckedChange={() => {
                    onToggleVisible(device.id);
                    onSelect(device.id);
                  }}
                />
              </TableCell>
              <TableCell className={`${CELL_CLASS} font-sans font-medium`}>{device.label}</TableCell>
              <TableCell className={CELL_CLASS}>{device.parameters.L}</TableCell>
              <TableCell className={CELL_CLASS}>{device.parameters.T}</TableCell>
              <TableCell className={CELL_CLASS}>{device.parameters.B}</TableCell>
              <TableCell className={CELL_CLASS}>{device.parameters.SD}</TableCell>
              <TableCell className={CELL_CLASS}>{device.parameters.LDD}</TableCell>
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
