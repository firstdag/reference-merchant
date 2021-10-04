const FIAT_MAX_FRACTION_DIGITS = 6;
const FIAT_SCALING_FACTOR = Math.pow(10, FIAT_MAX_FRACTION_DIGITS);

const FIAT_VISUAL_FORMAT = {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}; 

const DIEM_VISUAL_FORMAT = {
  minimumFractionDigits: 0,
  maximumFractionDigits: 6,
};

export function fiatToFloat(amount: number): number {
  return Math.trunc(amount) / FIAT_SCALING_FACTOR;
}

/**
 * Convert the fiat amount from its internal representation to a human
 * readable decimal fraction.
 *
 * Fiat amounts are handled internally as fixed point scaled numbers and are
 * converted to decimal fraction only for UI presentation.
 *
 * @param amount  Fixed point scaled fiat amount.
 */
export function fiatToHumanFriendly(amount: number): string {
  return fiatToFloat(amount).toLocaleString(undefined, {
    ...FIAT_VISUAL_FORMAT,
    useGrouping: true,
  });
}
