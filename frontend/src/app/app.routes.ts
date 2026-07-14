import { Routes } from '@angular/router';

import { adminGuard, authGuard, guestGuard } from './core/guards/auth.guard';

/** Every feature is lazy-loaded (§3). The shell owns the chrome; features own the content. */
export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'matches',
        loadComponent: () =>
          import('./features/matches/matches.component').then((m) => m.MatchesComponent),
      },
      {
        path: 'searches',
        loadComponent: () =>
          import('./features/searches/searches.component').then((m) => m.SearchesComponent),
      },
      {
        path: 'profiles',
        loadComponent: () =>
          import('./features/profiles/profiles.component').then((m) => m.ProfilesComponent),
      },
      {
        path: 'providers',
        loadComponent: () =>
          import('./features/providers/providers.component').then((m) => m.ProvidersComponent),
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./features/settings/settings.component').then((m) => m.SettingsComponent),
      },
      {
        path: 'admin',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/admin/admin.component').then((m) => m.AdminComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
