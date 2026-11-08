import { Routes } from '@angular/router';

// Screens from PLAN.md 10.1. Each area owns its folder (home/, chat/, plan/, share/).
export const routes: Routes = [
  { path: '', loadComponent: () => import('./home/home.page').then((m) => m.HomePage) }, // S7
  { path: 'trips/:tripId', loadComponent: () => import('./chat/chat.page').then((m) => m.ChatPage) }, // S1 + S2
  { path: 'trips/:tripId/plan', loadComponent: () => import('./plan/plan.page').then((m) => m.PlanPage) }, // S3-S5
  { path: 's/:shareId', loadComponent: () => import('./share/share.page').then((m) => m.SharePage) }, // S6
  { path: '**', redirectTo: '' },
];
