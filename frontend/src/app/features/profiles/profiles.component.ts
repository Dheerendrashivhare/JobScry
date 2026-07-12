import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';

import { Profile } from '../../core/models/api.models';
import { ApiService } from '../../core/services/api.service';

const csv = (value: string): string[] =>
  value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

@Component({
  selector: 'app-profiles',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
  ],
  templateUrl: './profiles.component.html',
})
export class ProfilesComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snack = inject(MatSnackBar);

  protected readonly profiles = signal<Profile[]>([]);
  protected readonly saving = signal(false);

  protected readonly form = this.fb.nonNullable.group({
    name: ['', Validators.required],
    target_roles: ['Backend Engineer, Python Developer'],
    locations: ['India'],
    skills: ['Python, FastAPI, PostgreSQL'],
    experience_min_years: [2, [Validators.min(0), Validators.max(60)]],
    experience_max_years: [5, [Validators.min(0), Validators.max(60)]],
    min_score: [90, [Validators.min(0), Validators.max(100)]],
  });

  ngOnInit(): void {
    this.load();
  }

  protected create(): void {
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();

    this.saving.set(true);
    this.api
      .createProfile({
        name: v.name,
        target_roles: csv(v.target_roles),
        locations: csv(v.locations),
        experience_min_years: v.experience_min_years,
        experience_max_years: v.experience_max_years,
        min_score: v.min_score,
        // Skill names are normalized server-side, so casing here doesn't matter.
        skills: csv(v.skills).map((name) => ({ name })),
      } as never)
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.form.reset({
            name: '',
            target_roles: '',
            locations: '',
            skills: '',
            experience_min_years: 2,
            experience_max_years: 5,
            min_score: 90,
          });
          this.load();
          this.snack.open('Profile created', 'OK', { duration: 3000 });
        },
        error: () => {
          this.saving.set(false);
          this.snack.open('Could not create the profile', 'Dismiss', { duration: 4000 });
        },
      });
  }

  protected remove(id: number): void {
    this.api.deleteProfile(id).subscribe(() => this.load());
  }

  private load(): void {
    this.api.listProfiles().subscribe((page) => this.profiles.set(page.items));
  }
}
