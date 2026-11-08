import { provideHttpClient, withFetch } from '@angular/common/http';
import { ApplicationConfig, isDevMode, provideBrowserGlobalErrorListeners } from '@angular/core';
import { initializeApp, provideFirebaseApp } from '@angular/fire/app';
import { ReCaptchaEnterpriseProvider, initializeAppCheck, provideAppCheck } from '@angular/fire/app-check';
import { connectAuthEmulator, getAuth, provideAuth } from '@angular/fire/auth';
import { connectFirestoreEmulator, getFirestore, provideFirestore } from '@angular/fire/firestore';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideTransloco } from '@jsverse/transloco';

import { routes } from './app.routes';
import { env } from './core/env';
import { TranslocoHttpLoader } from './core/transloco-loader';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withFetch()),
    provideFirebaseApp(() => initializeApp({ ...env.firebase, apiKey: env.firebase.apiKey || 'demo-key' })),
    provideAuth(() => {
      const auth = getAuth();
      if (env.useEmulators) connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
      return auth;
    }),
    provideFirestore(() => {
      const db = getFirestore();
      if (env.useEmulators) connectFirestoreEmulator(db, '127.0.0.1', 8081);
      return db;
    }),
    ...(env.recaptchaSiteKey
      ? [
          provideAppCheck(() =>
            initializeAppCheck(undefined, {
              provider: new ReCaptchaEnterpriseProvider(env.recaptchaSiteKey),
              isTokenAutoRefreshEnabled: true,
            }),
          ),
        ]
      : []),
    provideTransloco({
      config: {
        availableLangs: ['en', 'ja'],
        defaultLang: 'en',
        fallbackLang: 'en',
        reRenderOnLangChange: true,
        prodMode: !isDevMode(),
      },
      loader: TranslocoHttpLoader,
    }),
  ],
};
