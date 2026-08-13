import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ELECTRICAL_PARAMETERS, type CurveEntry } from "../types";

export function ElectricalParametersTable({ curves }: { curves: CurveEntry[] }) {
  const withResults = curves.filter((c) => c.result);

  return (
    // Horizontal scroll: one column per curve, so this widens as more
    // curves are compared side by side (matches the original desktop app's
    // horizontal-scrolling electrical parameters panel).
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="px-1.5 py-1">Parameter</TableHead>
            {withResults.map((curve) => (
              <TableHead key={curve.id} className="px-1.5 py-1 text-right">
                {curve.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {ELECTRICAL_PARAMETERS.map(({ key, label, unit, scale }) => (
            <TableRow key={key} className="border-outline-variant hover:bg-surface-container">
              <TableCell className="px-1.5 py-1 text-sm text-on-surface-variant">
                {label}
                {unit ? ` (${unit})` : ""}
              </TableCell>
              {withResults.map((curve) => {
                const raw = curve.result?.electrical_parameters[key];
                return (
                  <TableCell key={curve.id} className="px-1.5 py-1 text-right font-mono text-xs font-bold text-foreground">
                    {raw == null ? "-" : (raw * scale).toPrecision(4)}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
