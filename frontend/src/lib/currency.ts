/**
 * Currency formatting utility.
 * 
 * Uses a configurable currency code that can be changed from settings.
 * Default is NGN (Nigerian Naira).
 */

const STORAGE_KEY = 'app_currency';
const DEFAULT_CURRENCY = 'NGN';
const DEFAULT_LOCALE = 'en-NG';

// Currency options available in settings
export const CURRENCY_OPTIONS = [
  { value: 'NGN', label: '₦ Nigerian Naira (NGN)', locale: 'en-NG' },
  { value: 'USD', label: '$ US Dollar (USD)', locale: 'en-US' },
  { value: 'GBP', label: '£ British Pound (GBP)', locale: 'en-GB' },
  { value: 'EUR', label: '€ Euro (EUR)', locale: 'de-DE' },
  { value: 'GHS', label: '₵ Ghanaian Cedi (GHS)', locale: 'en-GH' },
  { value: 'KES', label: 'KSh Kenyan Shilling (KES)', locale: 'en-KE' },
  { value: 'ZAR', label: 'R South African Rand (ZAR)', locale: 'en-ZA' },
];

export function getCurrency(): string {
  if (typeof window === 'undefined') return DEFAULT_CURRENCY;
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_CURRENCY;
}

export function setCurrency(currency: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, currency);
  }
}

export function getLocale(): string {
  const currency = getCurrency();
  const opt = CURRENCY_OPTIONS.find((o) => o.value === currency);
  return opt?.locale || DEFAULT_LOCALE;
}

export function formatCurrency(amount: number | string): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '—';
  return new Intl.NumberFormat(getLocale(), {
    style: 'currency',
    currency: getCurrency(),
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(num);
}
