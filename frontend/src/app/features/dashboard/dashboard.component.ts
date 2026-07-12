import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  ApexAxisChartSeries,
  ApexChart,
  ApexDataLabels,
  ApexLegend,
  ApexPlotOptions,
  ApexTheme,
  ApexXAxis,
  NgApexchartsModule,
} from 'ng-apexcharts';

import { PipelineResult, Profile, SearchMode } from '../../core/models/api.models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatButtonToggleModule,
    MatSelectModule,
    MatFormFieldModule,
    MatIconModule,
    MatProgressBarModule,
    NgApexchartsModule,
  ],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly snack = inject(MatSnackBar);

  protected readonly profiles = signal<Profile[]>([]);
  protected readonly selectedId = signal<number | null>(null);
  protected readonly running = signal(false);
  protected readonly result = signal<PipelineResult | null>(null);
  protected mode: SearchMode = 'daily';

  // ng-apexcharts v1.15 uses signal inputs, so each option is bound as its own typed
  // field rather than one Partial<ChartComponent> blob.
  protected series = signal<ApexAxisChartSeries>([{ name: 'Jobs', data: [] }]);
  protected readonly chart: ApexChart = {
    type: 'bar',
    height: 260,
    toolbar: { show: false },
    background: 'transparent',
  };
  protected readonly plotOptions: ApexPlotOptions = {
    bar: { borderRadius: 4, distributed: true },
  };
  protected readonly dataLabels: ApexDataLabels = { enabled: true };
  protected readonly legend: ApexLegend = { show: false };
  protected readonly xaxis: ApexXAxis = {
    categories: ['Qualified', 'Below gate', 'Eligibility-gated'],
  };
  protected readonly theme: ApexTheme = { mode: 'dark' };

  ngOnInit(): void {
    this.api.listProfiles().subscribe((page) => {
      this.profiles.set(page.items);
      const preferred = page.items.find((p) => p.is_default) ?? page.items[0];
      if (preferred) this.selectedId.set(preferred.id);
    });
  }

  protected run(): void {
    const id = this.selectedId();
    if (id === null || this.running()) return;

    this.running.set(true);
    this.result.set(null);
    this.api.runPipeline(id, this.mode).subscribe({
      next: (res) => {
        this.running.set(false);
        this.result.set(res);
        this.series.set([
          {
            name: 'Jobs',
            data: [
              res.matching.qualified,
              res.matching.below_gate,
              res.matching.eligibility_gated,
            ],
          },
        ]);
        // Honest reporting (§7): show the real count, even when it's zero.
        this.snack.open(
          `${res.matching.qualified} qualified · ${res.notification.selected} notified`,
          'OK',
          { duration: 5000 },
        );
      },
      error: () => {
        this.running.set(false);
        this.snack.open('Pipeline run failed', 'Dismiss', { duration: 5000 });
      },
    });
  }
}
