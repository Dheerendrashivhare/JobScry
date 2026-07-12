import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AppSettings,
  Credential,
  Match,
  NotificationResult,
  Page,
  PipelineResult,
  Profile,
  Provider,
  Resume,
  SavedSearch,
  SearchMode,
} from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;

  // --- profiles -------------------------------------------------------------
  listProfiles(): Observable<Page<Profile>> {
    return this.http.get<Page<Profile>>(`${this.base}/profiles`);
  }

  getProfile(id: number): Observable<Profile> {
    return this.http.get<Profile>(`${this.base}/profiles/${id}`);
  }

  createProfile(body: Partial<Profile> & { name: string }): Observable<Profile> {
    return this.http.post<Profile>(`${this.base}/profiles`, body);
  }

  updateProfile(id: number, body: Partial<Profile>): Observable<Profile> {
    return this.http.patch<Profile>(`${this.base}/profiles/${id}`, body);
  }

  deleteProfile(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/profiles/${id}`);
  }

  addSkill(
    profileId: number,
    body: { name: string; weight?: number; is_required?: boolean },
  ): Observable<Profile> {
    return this.http.post<Profile>(`${this.base}/profiles/${profileId}/skills`, body);
  }

  removeSkill(profileId: number, skillId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/profiles/${profileId}/skills/${skillId}`);
  }

  // --- matches --------------------------------------------------------------
  listMatches(profileId: number, limit = 50, offset = 0): Observable<Page<Match>> {
    const params = new HttpParams().set('limit', limit).set('offset', offset);
    return this.http.get<Page<Match>>(`${this.base}/profiles/${profileId}/matches`, { params });
  }

  // --- pipeline -------------------------------------------------------------
  runPipeline(profileId: number, mode: SearchMode = 'daily'): Observable<PipelineResult> {
    const params = new HttpParams().set('mode', mode);
    return this.http.post<PipelineResult>(`${this.base}/profiles/${profileId}/run`, null, {
      params,
    });
  }

  notify(profileId: number): Observable<NotificationResult> {
    return this.http.post<NotificationResult>(`${this.base}/profiles/${profileId}/notify`, null);
  }

  // --- searches -------------------------------------------------------------
  listSearches(profileId: number): Observable<Page<SavedSearch>> {
    return this.http.get<Page<SavedSearch>>(`${this.base}/profiles/${profileId}/searches`);
  }

  createSearch(profileId: number, body: Partial<SavedSearch>): Observable<SavedSearch> {
    return this.http.post<SavedSearch>(`${this.base}/profiles/${profileId}/searches`, body);
  }

  deleteSearch(profileId: number, searchId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/profiles/${profileId}/searches/${searchId}`);
  }

  // --- resumes --------------------------------------------------------------
  listResumes(profileId: number): Observable<Page<Resume>> {
    return this.http.get<Page<Resume>>(`${this.base}/profiles/${profileId}/resumes`);
  }

  uploadResume(profileId: number, file: File): Observable<Resume> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<Resume>(`${this.base}/profiles/${profileId}/resumes`, form);
  }

  deleteResume(profileId: number, resumeId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/profiles/${profileId}/resumes/${resumeId}`);
  }

  // --- providers ------------------------------------------------------------
  listProviders(): Observable<Provider[]> {
    return this.http.get<Provider[]>(`${this.base}/providers`);
  }

  setProviderActive(slug: string, isActive: boolean): Observable<Provider> {
    return this.http.patch<Provider>(`${this.base}/providers/${slug}`, { is_active: isActive });
  }

  // --- settings + credentials ----------------------------------------------
  getSettings(): Observable<AppSettings> {
    return this.http.get<AppSettings>(`${this.base}/settings`);
  }

  updateSettings(body: Partial<AppSettings>): Observable<AppSettings> {
    return this.http.patch<AppSettings>(`${this.base}/settings`, body);
  }

  listCredentials(): Observable<Credential[]> {
    return this.http.get<Credential[]>(`${this.base}/credentials`);
  }

  setCredential(key: string, value: string): Observable<Credential> {
    return this.http.put<Credential>(`${this.base}/credentials`, { key, value });
  }

  deleteCredential(key: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/credentials/${key}`);
  }
}
