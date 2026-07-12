import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { AgGridAngular } from 'ag-grid-angular';
import { ColDef, GridOptions } from 'ag-grid-community';

import { Match, Profile } from '../../core/models/api.models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-matches',
  standalone: true,
  imports: [
    FormsModule,
    AgGridAngular,
    MatCardModule,
    MatFormFieldModule,
    MatSelectModule,
    MatChipsModule,
  ],
  templateUrl: './matches.component.html',
})
export class MatchesComponent implements OnInit {
  private readonly api = inject(ApiService);

  protected readonly profiles = signal<Profile[]>([]);
  protected readonly selectedId = signal<number | null>(null);
  protected readonly matches = signal<Match[]>([]);
  protected readonly loading = signal(false);

  protected readonly columns: ColDef<Match>[] = [
    {
      headerName: 'Score',
      field: 'score',
      width: 100,
      sort: 'desc',
      cellClass: 'font-semibold',
    },
    { headerName: 'Band', field: 'band', width: 130 },
    {
      headerName: 'Eligibility',
      field: 'eligibility_status',
      width: 160,
      // Work-auth is the difference between "apply now" and "ask the recruiter first" (§8).
      valueFormatter: (p) => (p.value === 'actionable' ? 'Actionable' : 'Gated'),
      cellStyle: (p) =>
        p.value === 'eligibility_gated' ? { color: '#b45309' } : { color: 'inherit' },
    },
    { headerName: 'Title', valueGetter: (p) => p.data?.job.title, flex: 2, minWidth: 220 },
    { headerName: 'Company', valueGetter: (p) => p.data?.job.company, flex: 1, minWidth: 140 },
    { headerName: 'Location', valueGetter: (p) => p.data?.job.location, flex: 1, minWidth: 140 },
    { headerName: 'Salary', valueGetter: (p) => p.data?.job.salary_raw, width: 150 },
    {
      headerName: 'Apply',
      width: 110,
      sortable: false,
      filter: false,
      cellRenderer: (p: { data?: Match }) => {
        const job = p.data?.job;
        if (!job) return '';
        const href = job.apply_url ?? job.url;
        return `<a href="${href}" target="_blank" rel="noopener">Open ↗</a>`;
      },
    },
  ];

  protected readonly gridOptions: GridOptions<Match> = {
    defaultColDef: { sortable: true, filter: true, resizable: true },
    rowHeight: 44,
    animateRows: true,
  };

  ngOnInit(): void {
    this.api.listProfiles().subscribe((page) => {
      this.profiles.set(page.items);
      const preferred = page.items.find((p) => p.is_default) ?? page.items[0];
      if (preferred) {
        this.selectedId.set(preferred.id);
        this.load(preferred.id);
      }
    });
  }

  protected onProfileChange(id: number): void {
    this.selectedId.set(id);
    this.load(id);
  }

  private load(profileId: number): void {
    this.loading.set(true);
    this.api.listMatches(profileId, 200).subscribe({
      next: (page) => {
        this.matches.set(page.items);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
