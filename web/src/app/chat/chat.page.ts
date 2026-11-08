import { ChangeDetectionStrategy, Component } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

/** S1 Chat + S2 Plan summary (PLAN.md 10.1). Placeholder: replace with the real screen. */
@Component({
  selector: 'app-chat-page',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<main class="page"><h1>{{ 'chat.title' | transloco }}</h1></main>`,
})
export class ChatPage {}
