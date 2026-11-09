import type { Metadata, Viewport } from 'next';
import { Inter, Noto_Sans_JP } from 'next/font/google';
import { cookies, headers } from 'next/headers';
import { I18nProvider } from '@/lib/i18n';
import { LANGUAGE_COOKIE, languageFromHeader, toLanguage } from '@/lib/language';
import './globals.css';

// Inter for Latin, Noto Sans JP for Japanese, as in the design mock.
const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-inter',
});
const notoSansJp = Noto_Sans_JP({
  subsets: ['latin'],
  weight: ['400', '500', '700'],
  display: 'swap',
  variable: '--font-noto-sans-jp',
});

export const metadata: Metadata = { title: 'AI Trip Planner' };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, viewportFit: 'cover' };

/** The language comes from the cookie, so the server renders the right text with no flash (PLAN.md 10.3). */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [cookieStore, headerStore] = await Promise.all([cookies(), headers()]);
  const lang =
    toLanguage(cookieStore.get(LANGUAGE_COOKIE)?.value) ??
    languageFromHeader(headerStore.get('accept-language'));

  return (
    <html lang={lang} className={`${inter.variable} ${notoSansJp.variable}`}>
      <body>
        <I18nProvider lang={lang}>{children}</I18nProvider>
      </body>
    </html>
  );
}
