import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatTableModule } from '@angular/material/table';

import { environment } from '../../../environments/environment';
import { User } from '../../core/models/api.models';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [MatCardModule, MatTableModule, MatChipsModule],
  templateUrl: './admin.component.html',
})
export class AdminComponent implements OnInit {
  private readonly http = inject(HttpClient);

  protected readonly users = signal<User[]>([]);
  protected readonly columns = ['id', 'email', 'full_name', 'role', 'is_active'];

  ngOnInit(): void {
    this.http
      .get<User[]>(`${environment.apiUrl}/auth/users`)
      .subscribe((rows) => this.users.set(rows));
  }
}
