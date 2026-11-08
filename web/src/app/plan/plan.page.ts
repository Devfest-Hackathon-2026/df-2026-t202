import { ChangeDetectionStrategy, Component } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

/** S3 Trip page, S4 Shorts viewer, S5 Share sheet (PLAN.md 10.1). Placeholder: replace with the real screen. */
@Component({
  selector: 'app-plan-page',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<main class="page"><h1>{{ 'plan.title' | transloco }}</h1></main>`,
})
export class PlanPage {}
