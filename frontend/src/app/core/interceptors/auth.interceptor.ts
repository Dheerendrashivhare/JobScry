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
      if (!(error instanceof HttpErrorResponse) || error.status !== 401) {
        return throwError(() => error);
      }

      // A 401 from /auth/login or /auth/refresh IS the answer — not a signal to refresh.
      // Don't log out here: on a failed login it would navigate away and wipe the error the
      // user needs to read, and on a failed refresh it would double up with the handler below.
      if (req.url.includes('/auth/login') || req.url.includes('/auth/refresh')) {
        return throwError(() => error);
      }

      // A stale access token with nothing to refresh with would 401 forever.
      if (!auth.refreshToken()) {
        auth.logout();
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
