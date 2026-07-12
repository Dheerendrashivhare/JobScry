import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Router, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let httpMock: HttpTestingController;
  let router: Router;

  beforeEach(async () => {
    localStorage.clear();

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        provideNoopAnimations(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    httpMock = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  const form = () => fixture.componentInstance['loginForm'];

  it('rejects an invalid email before anything is sent', () => {
    form().setValue({ email: 'not-an-email', password: 'supersecret' });

    expect(form().invalid).toBe(true);
    httpMock.verify(); // nothing left the app
  });

  it('signs in, stores the tokens, and lands on the dashboard', async () => {
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    form().setValue({ email: 'owner@e.com', password: 'supersecret' });

    fixture.componentInstance['login']();

    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.body).toEqual({ email: 'owner@e.com', password: 'supersecret' });
    req.flush({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' });

    expect(localStorage.getItem('ajh.access')).toBe('a');
    expect(navigate).toHaveBeenCalledWith(['/dashboard']);
    httpMock.verify();
  });

  it('surfaces the backend message on bad credentials rather than a generic failure', () => {
    form().setValue({ email: 'owner@e.com', password: 'wrong' });

    fixture.componentInstance['login']();

    httpMock.expectOne('/api/v1/auth/login').flush(
      { detail: 'Incorrect email or password', code: 'invalid_credentials' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(fixture.componentInstance['error']()).toBe('Incorrect email or password');
    expect(fixture.componentInstance['busy']()).toBe(false);
    httpMock.verify();
  });

  it('registering signs you straight in (the first account becomes Admin)', async () => {
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    fixture.componentInstance['registerForm'].setValue({
      full_name: 'Owner',
      email: 'owner@e.com',
      password: 'supersecret',
    });

    fixture.componentInstance['register']();

    httpMock.expectOne('/api/v1/auth/register').flush({ id: 1, email: 'owner@e.com', role: 'admin' });
    httpMock
      .expectOne('/api/v1/auth/login')
      .flush({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' });

    expect(navigate).toHaveBeenCalledWith(['/dashboard']);
    httpMock.verify();
  });
});
