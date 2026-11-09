'use client';

import { useEffect, useState } from 'react';

/**
 * The currency for budgets and costs, picked in the account menu. Saved on this device and sent
 * when a trip is created; the trip keeps it whatever the destination is. Yen by default.
 * These are the currencies the budget card has sensible amounts for (api/app/flow.py BUDGET_CHIPS).
 */
export const CURRENCIES = ['JPY', 'USD', 'EUR', 'GBP', 'KRW', 'TWD', 'THB', 'INR'] as const;
export type Currency = (typeof CURRENCIES)[number];

const KEY = 'currency';
const DEFAULT: Currency = 'JPY';
const EVENT = 'currencychange';

export function getCurrency(): Currency {
  try {
    const saved = localStorage.getItem(KEY);
    return (CURRENCIES as readonly string[]).includes(saved ?? '') ? (saved as Currency) : DEFAULT;
  } catch {
    return DEFAULT;
  }
}

export function setCurrency(currency: Currency) {
  try {
    localStorage.setItem(KEY, currency);
  } catch {
    // Storage blocked: the choice lasts until the page reloads.
  }
  window.dispatchEvent(new Event(EVENT));
}

export function useCurrency(): Currency {
  const [currency, set] = useState<Currency>(DEFAULT);
  useEffect(() => {
    const update = () => set(getCurrency());
    update();
    window.addEventListener(EVENT, update);
    return () => window.removeEventListener(EVENT, update);
  }, []);
  return currency;
}
