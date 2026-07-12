import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { Router, UrlTree } from '@angular/router';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { AuthService } from '../services/auth.service';
import { adminGuard, authGuard, guestGuard } from './auth.guard';

const run = (guard: typeof authGuard, url = '/matches') =>
  TestBed.runInInjectionContext(() =>
    guard({} as never, { url } as never),
  );

describe('route guards', () => {
  let auth: AuthService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideRouter([])],
    });
    auth = TestBed.inject(AuthService);
  });

  it('authGuard redirects a signed-out user to /login and remembers where they were going', () => {
    const result = run(authGuard, '/matches');

    expect(result).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toContain('redirect=%2Fmatches');
  });

  it('authGuard lets a signed-in user through', () => {
    localStorage.setItem('ajh.access', 'token');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter([])] });

    expect(run(authGuard)).toBe(true);
  });

  it('adminGuard blocks a non-admin', () => {
    auth.currentUser.set({ id: 2, role: 'user' } as never);

    expect(run(adminGuard)).toBeInstanceOf(UrlTree);
  });

  it('adminGuard admits an admin', () => {
    auth.currentUser.set({ id: 1, role: 'admin' } as never);

    expect(run(adminGuard)).toBe(true);
  });

  it('guestGuard keeps a signed-out user on the login page', () => {
    expect(run(guestGuard)).toBe(true);
  });
});
