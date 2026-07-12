import {
  HttpClient,
  HttpErrorResponse,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthService } from '../services/auth.service';
import { authInterceptor } from './auth.interceptor';

/** The interceptor is the piece most likely to fail in a way users actually feel
 *  (silent logouts, lost error messages), so it gets the most coverage. */
describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let auth: AuthService;

  /** AuthService reads the token in its constructor, so tokens must be in storage
   *  BEFORE the TestBed injects it. */
  const setup = (tokens: { access?: string; refresh?: string } = {}) => {
    localStorage.clear();
    if (tokens.access) localStorage.setItem('ajh.access', tokens.access);
    if (tokens.refresh) localStorage.setItem('ajh.refresh', tokens.refresh);

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  };

  beforeEach(() => setup());

  it('sends no Authorization header when signed out', () => {
    http.get('/api/v1/providers').subscribe();

    const req = httpMock.expectOne('/api/v1/providers');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
    httpMock.verify();
  });

  it('attaches the bearer token when signed in', () => {
    setup({ access: 'token-abc' });

    http.get('/api/v1/providers').subscribe();

    const req = httpMock.expectOne('/api/v1/providers');
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-abc');
    req.flush({});
    httpMock.verify();
  });

  it('refreshes once on a 401 and replays the original request with the new token', () => {
    setup({ access: 'stale', refresh: 'refresh-1' });

    let body: unknown;
    http.get('/api/v1/auth/me').subscribe((r) => (body = r));

    // 1. original request goes out with the stale token and is rejected
    const first = httpMock.expectOne('/api/v1/auth/me');
    expect(first.request.headers.get('Authorization')).toBe('Bearer stale');
    first.flush({ detail: 'expired' }, { status: 401, statusText: 'Unauthorized' });

    // 2. the interceptor refreshes
    const refresh = httpMock.expectOne('/api/v1/auth/refresh');
    expect(refresh.request.body).toEqual({ refresh_token: 'refresh-1' });
    refresh.flush({ access_token: 'fresh', refresh_token: 'refresh-2', token_type: 'bearer' });

    // 3. the original request is replayed with the fresh token
    const retried = httpMock.expectOne('/api/v1/auth/me');
    expect(retried.request.headers.get('Authorization')).toBe('Bearer fresh');
    retried.flush({ id: 1, email: 'o@e.com' });

    expect(body).toEqual({ id: 1, email: 'o@e.com' });
    expect(localStorage.getItem('ajh.access')).toBe('fresh');
    httpMock.verify();
  });

  it('logs out exactly once (and does not loop) when the refresh itself fails', () => {
    setup({ access: 'stale', refresh: 'dead' });
    const logout = vi.spyOn(auth, 'logout');

    http.get('/api/v1/auth/me').subscribe({ error: () => undefined });

    httpMock.expectOne('/api/v1/auth/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    httpMock
      .expectOne('/api/v1/auth/refresh')
      .flush({}, { status: 401, statusText: 'Unauthorized' });

    // Regression guard: the /auth/refresh 401 also passes back through this interceptor,
    // which used to trigger a second logout (and a second router navigation).
    expect(logout).toHaveBeenCalledOnce();
    httpMock.verify(); // and the original request was not retried forever
  });

  it('leaves a failed login alone: no refresh, and no logout that would wipe the error', () => {
    const logout = vi.spyOn(auth, 'logout');
    let status: number | undefined;

    http.post('/api/v1/auth/login', {}).subscribe({
      error: (e: HttpErrorResponse) => (status = e.status),
    });

    httpMock.expectOne('/api/v1/auth/login').flush({}, { status: 401, statusText: 'Unauthorized' });

    // The 401 must reach the component so it can show "Incorrect email or password".
    expect(status).toBe(401);
    expect(logout).not.toHaveBeenCalled();
    httpMock.verify(); // and no /auth/refresh was attempted
  });

  it('logs out when a 401 arrives and there is no refresh token to recover with', () => {
    setup({ access: 'stale' }); // no refresh token
    const logout = vi.spyOn(auth, 'logout');

    http.get('/api/v1/auth/me').subscribe({ error: () => undefined });

    httpMock.expectOne('/api/v1/auth/me').flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(logout).toHaveBeenCalledOnce();
    httpMock.verify();
  });

  it('passes non-401 errors straight through', () => {
    setup({ access: 'token', refresh: 'r' });
    const logout = vi.spyOn(auth, 'logout');
    let status: number | undefined;

    http.get('/api/v1/profiles/999').subscribe({
      error: (e: HttpErrorResponse) => (status = e.status),
    });

    httpMock
      .expectOne('/api/v1/profiles/999')
      .flush({ detail: 'Profile not found' }, { status: 404, statusText: 'Not Found' });

    expect(status).toBe(404);
    expect(logout).not.toHaveBeenCalled();
    httpMock.verify();
  });
});
