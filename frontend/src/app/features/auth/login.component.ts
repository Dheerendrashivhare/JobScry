import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { Router } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatProgressBarModule,
  ],
  templateUrl: './login.component.html',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly registered = signal(false);

  protected readonly loginForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  protected readonly registerForm = this.fb.nonNullable.group({
    full_name: [''],
    email: ['', [Validators.required, Validators.email]],
    // Backend enforces 8-128; mirror it so the user finds out here, not on submit.
    password: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128)]],
  });

  protected login(): void {
    if (this.loginForm.invalid || this.busy()) return;
    const { email, password } = this.loginForm.getRawValue();

    this.busy.set(true);
    this.error.set(null);
    this.auth.login(email, password).subscribe({
      next: () => void this.router.navigate(['/dashboard']),
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(this.message(err, 'Incorrect email or password.'));
      },
    });
  }

  protected register(): void {
    if (this.registerForm.invalid || this.busy()) return;
    const { email, password, full_name } = this.registerForm.getRawValue();

    this.busy.set(true);
    this.error.set(null);
    this.auth.register(email, password, full_name || null).subscribe({
      next: () => {
        // Sign straight in — the first account created becomes Admin.
        this.auth.login(email, password).subscribe({
          next: () => void this.router.navigate(['/dashboard']),
          error: () => {
            this.busy.set(false);
            this.registered.set(true);
          },
        });
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(this.message(err, 'Could not create the account.'));
      },
    });
  }

  private message(err: unknown, fallback: string): string {
    const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
    return typeof detail === 'string' ? detail : fallback;
  }
}
