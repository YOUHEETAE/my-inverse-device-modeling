import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FIELD_DISPLAYS, RANGE_MODES, SCALE_MODES, type FieldDisplay, type RangeMode, type ScaleMode } from "../types";

interface DisplayControlsProps {
  display: FieldDisplay;
  onDisplayChange: (display: FieldDisplay) => void;
  scaleMode: ScaleMode;
  onScaleModeChange: (mode: ScaleMode) => void;
  rangeMode: RangeMode;
  onRangeModeChange: (mode: RangeMode) => void;
}

export function DisplayControls({
  display,
  onDisplayChange,
  scaleMode,
  onScaleModeChange,
  rangeMode,
  onRangeModeChange,
}: DisplayControlsProps) {
  return (
    <div className="flex gap-2">
      <Select value={display} onValueChange={(value) => onDisplayChange(value as FieldDisplay)}>
        <SelectTrigger size="sm" className="w-44 border-outline-variant bg-surface-container-highest text-xs">
          <SelectValue>{display}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {FIELD_DISPLAYS.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={scaleMode}
        onValueChange={(value) => onScaleModeChange(value as ScaleMode)}
        disabled={display === "Mesh"}
      >
        <SelectTrigger size="sm" className="w-32 border-outline-variant bg-surface-container-highest text-xs">
          <SelectValue>{scaleMode}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {SCALE_MODES.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={rangeMode}
        onValueChange={(value) => onRangeModeChange(value as RangeMode)}
        disabled={display === "Mesh"}
      >
        <SelectTrigger size="sm" className="w-32 border-outline-variant bg-surface-container-highest text-xs">
          <SelectValue>{rangeMode}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {RANGE_MODES.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
