import { describe, expect, it } from 'vitest';
import { ApiError, errorKey } from '../lib/api';
import { safeCurrency } from '../lib/currency';

describe('errorKey', () => {
  it('gives a specific message for known API limits', () => {
    expect(errorKey(new ApiError('plan_limit_reached'))).toBe('error.plan_limit_reached');
    expect(errorKey(new ApiError('place_not_found'))).toBe('error.place_not_found');
  });
  it('falls back to the generic retry message', () => {
    expect(errorKey(new ApiError('http_500'))).toBe('state.sendFailed');
    expect(errorKey(new Error('network'))).toBe('state.sendFailed');
  });
});

describe('safeCurrency', () => {
  it('keeps ISO codes and replaces anything Intl would throw on', () => {
    expect(safeCurrency('JPY')).toBe('JPY');
    expect(safeCurrency('円')).toBe('XXX');
    expect(safeCurrency('Japanese yen')).toBe('XXX');
    expect(safeCurrency(undefined)).toBe('XXX');
  });
});
