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
            <TableHead>Parameter</TableHead>
            {withResults.map((curve) => (
              <TableHead key={curve.id} className="text-right">
                {curve.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {ELECTRICAL_PARAMETERS.map(({ key, label, unit }) => (
            <TableRow key={key}>
              <TableCell className="text-muted-foreground">
                {label}
                {unit ? ` (${unit})` : ""}
              </TableCell>
              {withResults.map((curve) => (
                <TableCell key={curve.id} className="text-right font-mono text-xs">
                  {curve.result?.electrical_parameters[key]?.toPrecision(4) ?? "-"}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
