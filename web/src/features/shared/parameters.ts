import type { DeviceParameters } from "../curves/types";

export function parametersEqual(a: DeviceParameters, b: DeviceParameters): boolean {
  return a.L === b.L && a.T === b.T && a.B === b.B && a.SD === b.SD && a.LDD === b.LDD;
}
