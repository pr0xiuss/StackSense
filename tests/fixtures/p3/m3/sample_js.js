/**
 * Sample JavaScript module for M3 IR normalization fixtures.
 */
import { formatCurrency } from './utils';

export function calculateTotal(items) {
  return items.reduce((acc, item) => acc + item.price, 0);
}

export const TAX_RATE = 0.08;

module.exports = {
  calculateTotal,
  TAX_RATE,
};
