import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { AppCheck, getToken } from '@angular/fire/app-check';
import { Auth } from '@angular/fire/auth';
import { firstValueFrom } from 'rxjs';
import { env } from './env';

/**
 * The only way to call the Cloud Run API. Attaches the Firebase ID token and App Check token (PLAN.md 9.1).
 * Reads go to Firestore directly; the API only writes and runs AI work.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(Auth);
  private readonly appCheck = inject(AppCheck, { optional: true });

  async post<T>(path: string, body: unknown = {}): Promise<T> {
    const user = this.auth.currentUser;
    if (!user) throw new Error('not_signed_in');
    let headers = new HttpHeaders({ Authorization: `Bearer ${await user.getIdToken()}` });
    if (this.appCheck) {
      const { token } = await getToken(this.appCheck);
      headers = headers.set('X-Firebase-AppCheck', token);
    }
    return firstValueFrom(this.http.post<T>(`${env.apiBaseUrl}${path}`, body, { headers }));
  }
}
