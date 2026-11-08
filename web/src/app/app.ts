import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { LanguageService } from './core/language.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class App {
  // Created at startup so the saved language is applied before the first page renders.
  private readonly language = inject(LanguageService);
}
