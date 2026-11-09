'use client';

import { setLanguage, useLanguage, useT } from '@/lib/i18n';
import type { Language } from '@/lib/language';

const LANGUAGES: Language[] = ['en', 'ja'];

export function LanguageSwitch() {
  const current = useLanguage();
  const t = useT();

  return (
    <div className="frost inline-flex gap-1 rounded-full p-1">
      {LANGUAGES.map((lang) => (
        <button
          key={lang}
          type="button"
          aria-pressed={lang === current}
          className={[
            'min-h-11 rounded-full border-0 px-4 font-inherit',
            lang === current ? 'bg-accent text-on-accent' : 'text-muted bg-transparent',
          ].join(' ')}
          onClick={() => lang !== current && setLanguage(lang)}
        >
          {t(`language.${lang}`)}
        </button>
      ))}
    </div>
  );
}
