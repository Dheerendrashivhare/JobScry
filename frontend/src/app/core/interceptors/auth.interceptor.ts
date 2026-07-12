import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { BehaviorSubject, catchError, filter, switchMap, take, throwError } from 'rxjs';

import { AuthService } from '../services/auth.service';

let refreshing = false;
const refreshed$ = new BehaviorSubject<string | null>(null);

/**
 * Attaches the JWT and transparently recovers from an expired access token by
 * refreshing once. Concurrent 401s queue on the single in-flight refresh rather than
 * each firing their own (which would race and invalidate each other).
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.token();

  const authorized = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authorized).pipe(
    catchError((error: unknown) => {
      const is401 = error instanceof HttpErrorResponse && error.status === 401;
      const isAuthCall = req.url.includes('/auth/login') || req.url.includes('/auth/refresh');

      if (!is401 || isAuthCall || !auth.refreshToken()) {
        if (is401 && isAuthCall) auth.logout();
        return throwError(() => error);
      }

      if (refreshing) {
        return refreshed$.pipe(
          filter((t): t is string => t !== null),
          take(1),
          switchMap((fresh) =>
            next(req.clone({ setHeaders: { Authorization: `Bearer ${fresh}` } })),
          ),
        );
      }

      refreshing = true;
      refreshed$.next(null);

      return auth.refresh().pipe(
        switchMap((fresh) => {
          refreshing = false;
          refreshed$.next(fresh.access_token);
          return next(
            req.clone({ setHeaders: { Authorization: `Bearer ${fresh.access_token}` } }),
          );
        }),
        catchError((refreshError: unknown) => {
          refreshing = false;
          auth.logout();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
