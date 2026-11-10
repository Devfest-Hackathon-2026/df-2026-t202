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

/**
 * A currency code Intl.NumberFormat can format. It throws a RangeError on codes that aren't 3 letters ("円"), which
 * would crash the page, so an unknown code becomes "XXX" (ISO 4217 "no currency", shown as "¤").
 */
export function safeCurrency(code: string | null | undefined): string {
  if (!code) return 'XXX';
  try {
    new Intl.NumberFormat('en', { style: 'currency', currency: code });
    return code;
  } catch {
    return 'XXX';
  }
}
