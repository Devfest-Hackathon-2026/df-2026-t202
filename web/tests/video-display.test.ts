import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { PlanPanel } from '../components/plan/plan-panel';
import { SpotPanel } from '../components/plan/spot-panel';
import type { Plan } from '../lib/types';

vi.mock('../components/plan/place-photo', () => ({ PlacePhoto: () => null }));

function planWith(videoIds: string[]): Plan {
  return {
    title: 'Test trip',
    subtitle: '',
    language: 'en',
    currency: 'MYR',
    checks: [],
    days: [
      {
        day: 1,
        theme: '',
        stay: '',
        stops: [
          {
            id: 's-1',
            time: '10:00',
            stayMinutes: 60,
            name: 'Merdeka Square',
            nameLocal: 'Dataran Merdeka',
            kind: 'sight',
            note: '',
            videoIds,
          },
        ],
      },
    ],
  };
}

function itinerary(plan: Plan) {
  return renderToStaticMarkup(
    createElement(PlanPanel, {
      trip: null,
      plan,
      loading: false,
      error: null,
      activeDay: null,
      onDayChange: () => {},
      onSelectStop: () => {},
      onOpenShorts: () => {},
    }),
  );
}

function spot(plan: Plan) {
  return renderToStaticMarkup(
    createElement(SpotPanel, {
      days: plan.days,
      selected: { day: 1, index: 0 },
      onSelect: () => {},
      onClose: () => {},
    }),
  );
}

test('a plan without videos loads normally without YouTube links or players', () => {
  const plan = planWith([]);
  expect(itinerary(plan)).toContain('Merdeka Square');
  expect(spot(plan)).toContain('Merdeka Square');
  for (const html of [itinerary(plan), spot(plan)]) {
    expect(html).not.toContain('Search on YouTube');
    expect(html).not.toContain('youtube.com');
  }
});

test('stops with videos keep their thumbnail and embedded player', () => {
  const plan = planWith(['test-video']);
  expect(itinerary(plan)).toContain('https://i.ytimg.com/vi/test-video/mqdefault.jpg');
  expect(spot(plan)).toContain('https://www.youtube.com/embed/test-video?');
  expect(spot(plan)).not.toContain('No video for this spot.');
});
