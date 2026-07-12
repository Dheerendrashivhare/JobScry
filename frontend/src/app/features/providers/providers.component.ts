import { Component, OnInit, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';

import { Provider } from '../../core/models/api.models';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-providers',
  standalone: true,
  imports: [MatCardModule, MatSlideToggleModule, MatIconModule, MatChipsModule],
  templateUrl: './providers.component.html',
})
export class ProvidersComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly snack = inject(MatSnackBar);

  protected readonly providers = signal<Provider[]>([]);
  protected readonly isAdmin = this.auth.isAdmin;

  ngOnInit(): void {
    this.api.listProviders().subscribe((rows) => this.providers.set(rows));
  }

  protected toggle(provider: Provider, active: boolean): void {
    this.api.setProviderActive(provider.slug, active).subscribe({
      next: () =>
        this.api.listProviders().subscribe((rows) => this.providers.set(rows)),
      error: () => this.snack.open('Only an Admin can change providers', 'OK', { duration: 4000 }),
    });
  }
}
