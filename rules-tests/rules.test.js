// Firestore security rules tests (PLAN.md 11.1). Run: npm test
import { readFileSync } from 'node:fs';
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from '@firebase/rules-unit-testing';
import { collection, doc, getDoc, getDocs, query, setDoc, updateDoc, where } from 'firebase/firestore';
import { afterAll, beforeAll, beforeEach, describe, it } from 'vitest';

let env;
const OWNER = 'owner';
const VIEWER = 'viewer';
const STRANGER = 'stranger';

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: 'demo-trip-planner',
    firestore: { rules: readFileSync('../firestore.rules', 'utf8') },
  });
});
afterAll(() => env.cleanup());

beforeEach(async () => {
  await env.clearFirestore();
  // Seed data the way the API writes it (rules disabled).
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await setDoc(doc(db, 'trips/t1'), { ownerUid: OWNER, members: { [OWNER]: 'owner', [VIEWER]: 'viewer' } });
    await setDoc(doc(db, 'trips/t1/messages/m1'), { role: 'ai', text: 'hi' });
    await setDoc(doc(db, 'trips/t1/plans/p1'), { version: 1 });
    await setDoc(doc(db, 'trips/t2'), { ownerUid: STRANGER, members: { [STRANGER]: 'owner' } });
    await setDoc(doc(db, 'shares/active1'), { tripId: 't1', active: true });
    await setDoc(doc(db, 'shares/off1'), { tripId: 't1', active: false });
    await setDoc(doc(db, 'cache_places/k'), { placeId: 'x' });
    await setDoc(doc(db, `users/${OWNER}/limits/2026-11-08`), { plans: 1 });
  });
});

const as = (uid) => env.authenticatedContext(uid).firestore();
const anon = () => env.unauthenticatedContext().firestore();

describe('trips', () => {
  it('members can read the trip, messages and plans', async () => {
    for (const uid of [OWNER, VIEWER]) {
      await assertSucceeds(getDoc(doc(as(uid), 'trips/t1')));
      await assertSucceeds(getDoc(doc(as(uid), 'trips/t1/messages/m1')));
      await assertSucceeds(getDoc(doc(as(uid), 'trips/t1/plans/p1')));
    }
  });

  it('non-members and signed-out users cannot read', async () => {
    await assertFails(getDoc(doc(as(STRANGER), 'trips/t1')));
    await assertFails(getDoc(doc(as(STRANGER), 'trips/t1/messages/m1')));
    await assertFails(getDoc(doc(anon(), 'trips/t1')));
  });

  it('nobody can write trips, messages or plans from the client', async () => {
    await assertFails(updateDoc(doc(as(OWNER), 'trips/t1'), { status: 'ready' }));
    await assertFails(setDoc(doc(as(OWNER), 'trips/new'), { members: { [OWNER]: 'owner' } }));
    await assertFails(setDoc(doc(as(OWNER), 'trips/t1/messages/m2'), { role: 'user', text: 'x' }));
    await assertFails(setDoc(doc(as(OWNER), 'trips/t1/plans/p2'), { version: 2 }));
  });

  it('the "My trips" query works for the signed-in user only', async () => {
    const q = (uid) => query(collection(as(uid), 'trips'), where(`members.${uid}`, 'in', ['owner', 'viewer']));
    await assertSucceeds(getDocs(q(OWNER)));
    await assertFails(getDocs(collection(as(OWNER), 'trips'))); // listing everything is denied
  });
});

describe('shares', () => {
  it('any signed-in user can read an active share', async () => {
    await assertSucceeds(getDoc(doc(as(STRANGER), 'shares/active1')));
  });
  it('inactive shares, listing and writes are denied', async () => {
    await assertFails(getDoc(doc(as(STRANGER), 'shares/off1')));
    await assertFails(getDocs(collection(as(OWNER), 'shares')));
    await assertFails(setDoc(doc(as(OWNER), 'shares/x'), { tripId: 't1', active: true }));
    await assertFails(getDoc(doc(anon(), 'shares/active1')));
  });
});

describe('users', () => {
  it('a user reads and writes only their own profile', async () => {
    await assertSucceeds(setDoc(doc(as(OWNER), `users/${OWNER}`), { displayName: 'A', language: 'ja' }));
    await assertSucceeds(getDoc(doc(as(OWNER), `users/${OWNER}`)));
    await assertFails(getDoc(doc(as(STRANGER), `users/${OWNER}`)));
    await assertFails(setDoc(doc(as(STRANGER), `users/${OWNER}`), { displayName: 'B' }));
  });
  it('rejects unknown fields and bad languages', async () => {
    await assertFails(setDoc(doc(as(OWNER), `users/${OWNER}`), { role: 'admin' }));
    await assertFails(setDoc(doc(as(OWNER), `users/${OWNER}`), { language: 'fr' }));
  });
  it('the daily plan counter is server-only', async () => {
    await assertFails(getDoc(doc(as(OWNER), `users/${OWNER}/limits/2026-11-08`)));
    await assertFails(setDoc(doc(as(OWNER), `users/${OWNER}/limits/2026-11-08`), { plans: 0 }));
  });
});

describe('caches', () => {
  it('no client access', async () => {
    await assertFails(getDoc(doc(as(OWNER), 'cache_places/k')));
    await assertFails(setDoc(doc(as(OWNER), 'cache_videos/k'), { videoIds: [] }));
  });
});
