import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Token, User } from '../models/api.models';

const ACCESS_KEY = 'ajh.access';
const REFRESH_KEY = 'ajh.refresh';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly accessToken = signal<string | null>(localStorage.getItem(ACCESS_KEY));
  readonly currentUser = signal<User | null>(null);

  readonly isAuthenticated = computed(() => this.accessToken() !== null);
  readonly isAdmin = computed(() => this.currentUser()?.role === 'admin');

  token(): string | null {
    return this.accessToken();
  }

  refreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  }

  /** The very first account to register becomes Admin (backend policy). */
  register(email: string, password: string, fullName: string | null): Observable<User> {
    return this.http.post<User>(`${environment.apiUrl}/auth/register`, {
      email,
      password,
      full_name: fullName,
    });
  }

  login(email: string, password: string): Observable<Token> {
    return this.http
      .post<Token>(`${environment.apiUrl}/auth/login`, { email, password })
      .pipe(tap((token) => this.store(token)));
  }

  refresh(): Observable<Token> {
    return this.http
      .post<Token>(`${environment.apiUrl}/auth/refresh`, { refresh_token: this.refreshToken() })
      .pipe(tap((token) => this.store(token)));
  }

  loadCurrentUser(): Observable<User> {
    return this.http
      .get<User>(`${environment.apiUrl}/auth/me`)
      .pipe(tap((user) => this.currentUser.set(user)));
  }

  logout(): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    this.accessToken.set(null);
    this.currentUser.set(null);
    void this.router.navigate(['/login']);
  }

  private store(token: Token): void {
    localStorage.setItem(ACCESS_KEY, token.access_token);
    localStorage.setItem(REFRESH_KEY, token.refresh_token);
    this.accessToken.set(token.access_token);
  }
}
