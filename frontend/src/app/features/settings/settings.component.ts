import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';

import { AppSettings, Credential } from '../../core/models/api.models';
import { ApiService } from '../../core/services/api.service';

/** Every key the backend accepts (CredentialKey). Values are Fernet-encrypted server-side
 *  and only ever come back masked. */
const CREDENTIAL_KEYS = [
  'apify_token',
  'llm_api_key',
  'serpapi_key',
  'rapidapi_key',
  'adzuna_app_id',
  'adzuna_app_key',
  'jooble_key',
  'telegram_bot_token',
  'smtp_password',
] as const;

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    MatButtonModule,
    MatIconModule,
  ],
  templateUrl: './settings.component.html',
})
export class SettingsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snack = inject(MatSnackBar);

  protected readonly credentialKeys = CREDENTIAL_KEYS;
  protected readonly credentials = signal<Credential[]>([]);
  protected readonly saving = signal(false);

  protected readonly form = this.fb.nonNullable.group({
    llm_provider: [null as string | null],
    llm_model: [''],
    telegram_enabled: [false],
    telegram_chat_id: [''],
    email_enabled: [false],
    notify_email: [''],
    smtp_host: [''],
    smtp_port: [587],
    smtp_username: [''],
    notify_cap: [20],
  });

  protected readonly credentialForm = this.fb.nonNullable.group({
    key: ['apify_token'],
    value: [''],
  });

  ngOnInit(): void {
    this.api.getSettings().subscribe((s) => this.form.patchValue(s as never));
    this.reloadCredentials();
  }

  protected save(): void {
    this.saving.set(true);
    const v = this.form.getRawValue();
    const body: Partial<AppSettings> = {
      ...v,
      llm_provider: (v.llm_provider as AppSettings['llm_provider']) || null,
      llm_model: v.llm_model || null,
      telegram_chat_id: v.telegram_chat_id || null,
      notify_email: v.notify_email || null,
      smtp_host: v.smtp_host || null,
      smtp_username: v.smtp_username || null,
    };

    this.api.updateSettings(body).subscribe({
      next: () => {
        this.saving.set(false);
        this.snack.open('Settings saved', 'OK', { duration: 3000 });
      },
      error: () => {
        this.saving.set(false);
        this.snack.open('Could not save settings', 'Dismiss', { duration: 4000 });
      },
    });
  }

  protected saveCredential(): void {
    const { key, value } = this.credentialForm.getRawValue();
    if (!value) return;

    this.api.setCredential(key, value).subscribe({
      next: () => {
        this.credentialForm.patchValue({ value: '' });
        this.reloadCredentials();
        this.snack.open('Key stored (encrypted)', 'OK', { duration: 3000 });
      },
      error: () => this.snack.open('Could not store the key', 'Dismiss', { duration: 4000 }),
    });
  }

  protected deleteCredential(key: string): void {
    this.api.deleteCredential(key).subscribe(() => this.reloadCredentials());
  }

  private reloadCredentials(): void {
    this.api.listCredentials().subscribe((rows) => this.credentials.set(rows));
  }
}
