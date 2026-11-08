import { Injectable, inject, signal } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';

export type Language = 'en' | 'ja';
const STORAGE_KEY = 'language';

/**
 * Holds the UI language (PLAN.md 10.3). Also save it to users/{uid}.language through the API/user service.
 * The Maps JavaScript API language is fixed when its script loads, so the page reloads after a change.
 */
@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly transloco = inject(TranslocoService);
  readonly language = signal<Language>(this.initial());

  constructor() {
    this.transloco.setActiveLang(this.language());
    document.documentElement.lang = this.language();
  }

  set(lang: Language, { reload = true } = {}): void {
    if (lang === this.language()) return;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // Storage can be blocked (private mode). The setting then lasts for this page only.
    }
    if (reload) {
      location.reload();
      return;
    }
    this.language.set(lang);
    this.transloco.setActiveLang(lang);
    document.documentElement.lang = lang;
  }

  private initial(): Language {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'en' || saved === 'ja') return saved;
    } catch {
      // ignore
    }
    return navigator.language.toLowerCase().startsWith('ja') ? 'ja' : 'en';
  }
}
