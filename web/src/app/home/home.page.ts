import { ChangeDetectionStrategy, Component } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

/** S7 My trips (PLAN.md 10.1). Placeholder: replace with the real screen. */
@Component({
  selector: 'app-home-page',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<main class="page"><h1>{{ 'home.title' | transloco }}</h1></main>`,
})
export class HomePage {}
