// Run with: npm test  (Node's built-in test runner; no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { formatMoney, formatPrice } from "./money.ts";

test("USD amounts", () => {
  assert.equal(formatMoney({ amount_minor: 0, currency: "USD" }), "$0");
  assert.equal(formatMoney({ amount_minor: 900, currency: "USD" }), "$9");
  assert.equal(formatMoney({ amount_minor: 950, currency: "USD" }), "$9.50");
  assert.equal(formatMoney({ amount_minor: 905, currency: "USD" }), "$9.05");
  assert.equal(formatMoney({ amount_minor: 1234567, currency: "USD" }), "$12,345.67");
  assert.equal(formatMoney({ amount_minor: -500, currency: "USD" }), "-$5");
});

test("KES reference amounts as sent by the API (133 KES per USD)", () => {
  // $9 x 133 = KSh 1,197 ... the server sends these minor-unit values.
  assert.equal(formatMoney({ amount_minor: 119700, currency: "KES" }), "KSh 1,197");
  assert.equal(formatMoney({ amount_minor: 252700, currency: "KES" }), "KSh 2,527");
  assert.equal(formatMoney({ amount_minor: 651700, currency: "KES" }), "KSh 6,517");
  assert.equal(formatMoney({ amount_minor: 1316700, currency: "KES" }), "KSh 13,167");
  assert.equal(formatMoney({ amount_minor: 66500, currency: "KES" }), "KSh 665");
});

test("plan prices are labelled per month", () => {
  assert.equal(formatPrice({ amount_minor: 1900, currency: "USD" }, "month"), "$19/month");
  assert.equal(formatPrice({ amount_minor: 2500, currency: "USD" }), "$25");
});

test("unknown currency shows its code", () => {
  assert.equal(formatMoney({ amount_minor: 1000, currency: "EUR" }), "EUR 10.00");
});
