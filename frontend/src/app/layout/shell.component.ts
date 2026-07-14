import { Component, OnInit, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';

import { AuthService } from '../core/services/auth.service';
import { ThemeService } from '../core/services/theme.service';

interface NavItem {
  path: string;
  /** i18n key resolved through ngx-translate. */
  label: string;
  icon: string;
  adminOnly?: boolean;
}

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
    MatTooltipModule,
    TranslateModule,
  ],
  templateUrl: './shell.component.html',
})
export class ShellComponent implements OnInit {
  private readonly auth = inject(AuthService);
  protected readonly themeService = inject(ThemeService);

  protected readonly user = this.auth.currentUser;
  protected readonly isAdmin = this.auth.isAdmin;

  protected readonly nav: NavItem[] = [
    { path: '/dashboard', label: 'nav.dashboard', icon: 'dashboard' },
    { path: '/matches', label: 'nav.matches', icon: 'work' },
    { path: '/profiles', label: 'nav.profiles', icon: 'person' },
    { path: '/searches', label: 'nav.searches', icon: 'travel_explore' },
    { path: '/providers', label: 'nav.providers', icon: 'hub' },
    { path: '/settings', label: 'nav.settings', icon: 'settings' },
    { path: '/admin', label: 'nav.admin', icon: 'admin_panel_settings', adminOnly: true },
  ];

  ngOnInit(): void {
    // The guard only checks for a token; this resolves who that token belongs to
    // (needed before the Admin link can be shown).
    this.auth.loadCurrentUser().subscribe({ error: () => this.auth.logout() });
  }

  protected visible(item: NavItem): boolean {
    return !item.adminOnly || this.isAdmin();
  }

  protected logout(): void {
    this.auth.logout();
  }
}
