import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';

import { Profile, Provider, ProviderSlug, SavedSearch, SearchMode } from '../../core/models/api.models';
import { ApiService } from '../../core/services/api.service';

/**
 * A saved search is the piece that tells the pipeline WHERE to look. A profile without
 * one produces `searches_run: 0` and finds nothing — which is exactly the trap this
 * screen exists to remove.
 *
 * The presets are the recipes that actually work (CLAUDE.md §5), not blank boxes.
 */
interface Preset {
  label: string;
  provider: ProviderSlug;
  hint: string;
  needsKey: string | null;
  params: Record<string, unknown>;
}

const PRESETS: Preset[] = [
  {
    label: 'Remotive — remote jobs (no key needed)',
    provider: 'remotive',
    hint: 'Works instantly. But their API ignores the search term and exposes only ~39 jobs — good for a smoke test, weak as a real source.',
    needsKey: null,
    params: { keywords: ['Backend Engineer'], limit: 100 },
  },
  {
    label: 'Company ATS boards — Greenhouse (no key needed)',
    provider: 'greenhouse_lever',
    hint: 'Hundreds of real jobs straight from company boards. Highest source-quality score. Put the company board tokens below.',
    needsKey: null,
    params: {
      greenhouse_boards: ['stripe', 'databricks', 'cloudflare'],
      lever_boards: [],
      limit: 1000,
    },
  },
  {
    label: 'LinkedIn via Apify — the proven recipe',
    provider: 'apify_linkedin',
    hint: 'Where the real volume is. Broad titles + tech-in-description massively out-performs narrow queries.',
    needsKey: 'apify_token',
    params: {
      titleSearch: [
        'Backend Engineer',
        'Backend Developer',
        'Python Developer',
        'Software Engineer',
      ],
      descriptionSearch: ['Python', 'FastAPI'],
      locationSearch: ['India'],
      aiExperienceLevelFilter: ['2-5'],
      removeAgency: true,
      populateExternalApplyURL: true,
      limit: 100,
    },
  },
  {
    label: 'Naukri via Apify',
    provider: 'apify_naukri',
    hint: 'Search "FastAPI Backend Developer" — NEVER bare "Python", that floods you with AI/ML-trainer roles.',
    needsKey: 'apify_token',
    params: { keyword: 'FastAPI Backend Developer', freshness: 7, sortBy: 'date', maxJobs: 100 },
  },
];

@Component({
  selector: 'app-searches',
  standalone: true,
  imports: [
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
  ],
  templateUrl: './searches.component.html',
})
export class SearchesComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly snack = inject(MatSnackBar);

  protected readonly profiles = signal<Profile[]>([]);
  protected readonly providers = signal<Provider[]>([]);
  protected readonly searches = signal<SavedSearch[]>([]);
  protected readonly selectedProfile = signal<number | null>(null);
  protected readonly saving = signal(false);

  protected readonly presets = PRESETS;
  protected name = '';
  protected provider: ProviderSlug = 'remotive';
  protected mode: SearchMode = 'daily';
  protected paramsJson = JSON.stringify(PRESETS[0].params, null, 2);
  protected jsonError = signal<string | null>(null);

  /** Which stored keys the chosen provider still needs — the usual reason a run finds nothing. */
  protected readonly missingKeys = computed(() => {
    const p = this.providers().find((x) => x.slug === this.provider);
    return p ? p.requires_credentials : [];
  });

  ngOnInit(): void {
    this.api.listProviders().subscribe((rows) => this.providers.set(rows));
    this.api.listProfiles().subscribe((page) => {
      this.profiles.set(page.items);
      const preferred = page.items.find((p) => p.is_default) ?? page.items[0];
      if (preferred) {
        this.selectedProfile.set(preferred.id);
        this.load(preferred.id);
      }
    });
  }

  protected onProfileChange(id: number): void {
    this.selectedProfile.set(id);
    this.load(id);
  }

  protected applyPreset(preset: Preset): void {
    this.name = preset.label.split(' — ')[0];
    this.provider = preset.provider;
    this.paramsJson = JSON.stringify(preset.params, null, 2);
    this.jsonError.set(null);
  }

  protected create(): void {
    const profileId = this.selectedProfile();
    if (profileId === null || this.saving()) return;

    let params: Record<string, unknown>;
    try {
      params = JSON.parse(this.paramsJson);
    } catch {
      this.jsonError.set('That is not valid JSON.');
      return;
    }
    this.jsonError.set(null);

    this.saving.set(true);
    this.api
      .createSearch(profileId, {
        name: this.name || `${this.provider} search`,
        provider_slug: this.provider,
        mode: this.mode,
        is_active: true,
        params,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.name = '';
          this.load(profileId);
          this.snack.open('Search saved — now run the pipeline from the Dashboard', 'OK', {
            duration: 6000,
          });
        },
        error: () => {
          this.saving.set(false);
          this.snack.open('Could not save the search', 'Dismiss', { duration: 4000 });
        },
      });
  }

  protected remove(searchId: number): void {
    const profileId = this.selectedProfile();
    if (profileId === null) return;
    this.api.deleteSearch(profileId, searchId).subscribe(() => this.load(profileId));
  }

  protected pretty(params: Record<string, unknown>): string {
    return JSON.stringify(params);
  }

  private load(profileId: number): void {
    this.api.listSearches(profileId).subscribe((page) => this.searches.set(page.items));
  }
}
