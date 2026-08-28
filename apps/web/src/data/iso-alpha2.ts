import codes from "./iso-alpha2.json";

export type IsoAlpha2 = string & { readonly __isoAlpha2: unique symbol };

export const ISO_ALPHA2_CODES = codes as readonly string[];
const ISO_ALPHA2_CODE_SET = new Set(ISO_ALPHA2_CODES);

export function isIsoAlpha2(value: string): value is IsoAlpha2 {
  return ISO_ALPHA2_CODE_SET.has(value);
}
