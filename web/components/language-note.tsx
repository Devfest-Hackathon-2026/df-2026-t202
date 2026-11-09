'use client';

import { Languages } from 'lucide-react';
import { useLanguage, useT } from '@/lib/i18n';
import type { Lang } from '@/lib/types';

/**
 * A trip's AI text stays in the language it was created in (PLAN.md 7.1), while the interface
 * follows the reader's own setting. When the two differ, say so — otherwise an English plan
 * inside a Japanese interface just looks broken.
 */
export function LanguageNote({ tripLanguage }: { tripLanguage: Lang }) {
  const t = useT();
  const language = useLanguage();
  if (tripLanguage === language) return null;

  return (
    <p className="m-0 flex w-fit items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-[11px] text-white/75">
      <Languages size={13} strokeWidth={1.8} aria-hidden="true" />
      {t('trip.otherLanguage').replace('{lang}', t(`language.${tripLanguage}`))}
    </p>
  );
}
