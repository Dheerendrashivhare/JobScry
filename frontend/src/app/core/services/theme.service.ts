import { Injectable, effect, signal } from '@angular/core';

const KEY = 'ajh.theme';
export type Theme = 'light' | 'dark';

/** Dark mode is required (§2), and it's the default. One class on <html> drives both
 *  Angular Material's system tokens and Tailwind's `dark:` variants. */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<Theme>((localStorage.getItem(KEY) as Theme | null) ?? 'dark');

  constructor() {
    effect(() => {
      const theme = this.theme();
      document.documentElement.classList.toggle('dark', theme === 'dark');
      localStorage.setItem(KEY, theme);
    });
  }

  toggle(): void {
    this.theme.update((t) => (t === 'dark' ? 'light' : 'dark'));
  }
}
