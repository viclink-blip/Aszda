/**
 * Money formatting for the whole app. Amounts are integer minor units (cents)
 * exactly as the API sends them; this file never does currency conversion.
 * The KES reference amount is calculated by the server from its configured rate.
 *
 * Same rules as the backend (app/billing/money.py): $9, $9.50, KSh 1,197.
 */

export interface MoneyAmount {
  amount_minor: number;
  currency: string;
}

const CURRENCIES: Record<string, { symbol: string; digits: number }> = {
  USD: { symbol: "$", digits: 2 },
  KES: { symbol: "KSh ", digits: 2 },
};

export function formatMoney(money: MoneyAmount): string {
  const { amount_minor: minorUnits, currency } = money;
  const info = CURRENCIES[currency];
  if (!info || !Number.isInteger(minorUnits)) {
    // Unknown currency: show the code rather than guess a symbol.
    return `${currency} ${(minorUnits / 100).toFixed(2)}`;
  }
  const factor = 10 ** info.digits;
  const sign = minorUnits < 0 ? "-" : "";
  const abs = Math.abs(minorUnits);
  const major = Math.floor(abs / factor);
  const minor = abs % factor;
  let text = major.toLocaleString("en-US");
  if (minor) text += `.${String(minor).padStart(info.digits, "0")}`;
  return `${sign}${info.symbol}${text}`;
}

/** "$9/month" for plans, "$5" for one-off purchases. */
export function formatPrice(money: MoneyAmount, interval?: "month" | null): string {
  return interval === "month" ? `${formatMoney(money)}/month` : formatMoney(money);
}
