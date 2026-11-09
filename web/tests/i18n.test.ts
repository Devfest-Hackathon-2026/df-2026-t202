import en from '../public/i18n/en.json';
import ja from '../public/i18n/ja.json';

/** Every UI string must exist in both languages (PLAN.md 10.3). */
function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe('i18n', () => {
  it('en.json and ja.json have the same keys', () => {
    expect(keys(ja).sort()).toEqual(keys(en).sort());
  });
});
