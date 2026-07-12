import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    TestBed.configureTestingModule({});
  });

  it('defaults to dark (required by the spec)', () => {
    const service = TestBed.inject(ThemeService);
    TestBed.flushEffects();

    expect(service.theme()).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('toggles the class on <html> so Material and Tailwind flip together', () => {
    const service = TestBed.inject(ThemeService);
    TestBed.flushEffects();

    service.toggle();
    TestBed.flushEffects();

    expect(service.theme()).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('ajh.theme')).toBe('light');
  });

  it('restores the persisted choice', () => {
    localStorage.setItem('ajh.theme', 'light');
    const service = TestBed.inject(ThemeService);

    expect(service.theme()).toBe('light');
  });
});
