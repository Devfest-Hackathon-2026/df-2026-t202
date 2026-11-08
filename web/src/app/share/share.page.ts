import { ChangeDetectionStrategy, Component } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

/** S6 Shared page (read-only, anonymous auth) (PLAN.md 10.1). Placeholder: replace with the real screen. */
@Component({
  selector: 'app-share-page',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<main class="page"><h1>{{ 'share.title' | transloco }}</h1></main>`,
})
export class SharePage {}
