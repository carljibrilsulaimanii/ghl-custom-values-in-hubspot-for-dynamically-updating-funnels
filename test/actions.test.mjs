/**
 * actions.test.mjs -- tests for the three custom code actions
 * -----------------------------------------------------------
 * Author:  Jibril Sulaiman
 * Created: 2026-10-01 (ET)
 * Deploy:  Local only. `npm test` (Node 20+).
 * What:    Late Registration Check, Submit Attended Form, Class Session label.
 * Why:     Each one fails quietly in production: an empty output leaves the last
 *          class's value in place, a dropped field reads as success.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { run, defaultHubspot } from './harness.mjs';

const START = Date.parse('2026-09-17T23:00:00Z'); // 7:00 PM EDT

// ---------- late-registration-check.js ----------

test('late check: before the start is No / not late', async () => {
  const { out } = await run('late-registration-check.js', { inputFields: { event_start_date_and_time: String(START) }, now: START - 1000 });
  assert.deepEqual(out, { regRedirect: 'No', registeredLate: false, classStartIso: '2026-09-17T23:00:00.000Z', reason: 'before_start' });
});

test('late check: at or after the start is Yes / late', async () => {
  for (const now of [START, START + 60_000]) {
    const { out } = await run('late-registration-check.js', { inputFields: { event_start_date_and_time: String(START) }, now });
    assert.equal(out.regRedirect, 'Yes');
    assert.equal(out.registeredLate, true);
    assert.equal(out.reason, 'after_start');
  }
});

test('late check: accepts an ISO string as well as epoch ms', async () => {
  const { out } = await run('late-registration-check.js', { inputFields: { event_start_date_and_time: '2026-09-17T23:00:00Z' }, now: START + 1 });
  assert.equal(out.regRedirect, 'Yes');
});

test('late check: missing or unparseable start always outputs No, never blank', async () => {
  let r = await run('late-registration-check.js', { inputFields: {} });
  assert.equal(r.out.regRedirect, 'No');
  assert.equal(r.out.reason, 'no_start_time');
  assert.match(r.logs.join('\n'), /Active Config mapping/);
  r = await run('late-registration-check.js', { inputFields: { event_start_date_and_time: 'Sep 17th, 2026' } });
  assert.equal(r.out.regRedirect, 'No');
  assert.equal(r.out.reason, 'unparseable_start_time');
});

test('late check: logs both times in Eastern', async () => {
  const { logs } = await run('late-registration-check.js', { inputFields: { event_start_date_and_time: String(START) }, now: START - 3_600_000 });
  assert.match(logs.join('\n'), /Class starts Sep 17, 2026, 7:00 PM ET; now Sep 17, 2026, 6:00 PM ET; regRedirect=No/);
});

// ---------- submit-attended-form.js ----------

test('submit: posts email + reg_redirect=Yes to the form, skipping empty identity fields', async () => {
  const { out, calls } = await run('submit-attended-form.js', { inputFields: { email: ' ann@example.com ', firstname: 'Ann', lastname: '', phone: '' } });
  assert.deepEqual(out, { submitted: true, reason: 'submitted' });
  const c = calls.fetch[0];
  assert.equal(c.url, 'https://api.hsforms.com/submissions/v3/integration/submit/REPLACE_WITH_PORTAL_ID/REPLACE_WITH_FORM_GUID');
  assert.equal(c.opts.method, 'POST');
  assert.deepEqual(c.body.fields, [
    { objectTypeId: '0-1', name: 'email', value: 'ann@example.com' },
    { objectTypeId: '0-1', name: 'reg_redirect', value: 'Yes' },
    { objectTypeId: '0-1', name: 'firstname', value: 'Ann' },
  ]);
  assert.equal(c.body.context.pageUri, 'workflow://late-registration');
});

test('submit: no email means no request', async () => {
  const { out, calls } = await run('submit-attended-form.js', { inputFields: {} });
  assert.deepEqual(out, { submitted: false, reason: 'no_email' });
  assert.equal(calls.fetch.length, 0);
});

test('submit: a rejected submission reports the status and does not throw', async () => {
  const { out, logs } = await run('submit-attended-form.js', {
    inputFields: { email: 'ann@example.com' },
    fetchImpl: async () => ({ ok: false, status: 400, text: async () => '{"status":"error"}' }),
  });
  assert.deepEqual(out, { submitted: false, reason: 'submit_failed_400' });
  assert.match(logs.join('\n'), /failed: 400/);
});

test('submit: a network error is caught', async () => {
  const { out } = await run('submit-attended-form.js', { inputFields: { email: 'ann@example.com' }, fetchImpl: async () => { throw new Error('offline'); } });
  assert.deepEqual(out, { submitted: false, reason: 'error' });
});

// ---------- class-session-label.js ----------

const env = { CLASS_SESSION_WRITE_TOKEN: 'test-token' };

test('session: builds "<date> - <topic>" and adds the dropdown option when new', async () => {
  const { out, calls } = await run('class-session-label.js', { env, inputFields: { class_date: String(Date.UTC(2026, 8, 17)), class_topic: 'Dividend Stocks' } });
  assert.equal(out.class_session, '2026-09-17 - Dividend Stocks');
  const add = calls.hubspot.find((c) => c.op === 'updateProperty');
  assert.equal(add.body.options.at(-1).value, '2026-09-17 - Dividend Stocks');
  assert.equal(add.body.options.length, 2); // kept the existing option
  const upd = calls.hubspot.find((c) => c.op === 'updateRecord');
  assert.deepEqual(upd.body, { properties: { class_session: '2026-09-17 - Dividend Stocks' } });
  assert.equal(upd.id, '9001');
});

test('session: an existing option is not added twice', async () => {
  const { calls } = await run('class-session-label.js', { env, inputFields: { class_date: '2026-09-10', class_topic: "REIT's" } });
  assert.equal(calls.hubspot.some((c) => c.op === 'updateProperty'), false);
  assert.equal(calls.hubspot.find((c) => c.op === 'updateRecord').body.properties.class_session, '2026-09-10 - REITs');
});

test('session: the Eastern date from the event start corrects class_date', async () => {
  // Stored as the next UTC day; the class was 7pm Eastern on the 17th.
  const { out, calls } = await run('class-session-label.js', { env, inputFields: {
    class_date: String(Date.UTC(2026, 8, 18)), class_topic: "Stocks & ETF's", event_start_date_and_time: String(START) } });
  assert.equal(out.class_session, '2026-09-17 - Stocks & ETFs');
  const upd = calls.hubspot.find((c) => c.op === 'updateRecord');
  assert.equal(upd.body.properties.class_date, String(Date.UTC(2026, 8, 17)));
});

test('session: a topic with no rule writes nothing', async () => {
  const { out, calls } = await run('class-session-label.js', { env, inputFields: { class_date: '2026-10-27', class_topic: 'Retirement' } });
  assert.equal(out.class_session, '');
  assert.equal(calls.hubspot.length, 0);
});

test('session: missing secret still returns the label but writes nothing', async () => {
  const { out, calls, logs } = await run('class-session-label.js', { inputFields: { class_date: '2026-09-10', class_topic: 'REITs' } });
  assert.equal(out.class_session, '2026-09-10 - REITs');
  assert.equal(calls.hubspot.length, 0);
  assert.match(logs.join('\n'), /SECRET MISSING: CLASS_SESSION_WRITE_TOKEN/);
});

test('session: an API failure is logged, not thrown', async () => {
  const { out, logs } = await run('class-session-label.js', { env, inputFields: { class_date: '2026-09-10', class_topic: 'REITs' },
    hubspot: (calls) => { const c = defaultHubspot(calls); c.crm.objects.basicApi.update = async () => { throw new Error('403 Forbidden'); }; return c; } });
  assert.equal(out.class_session, '2026-09-10 - REITs');
  assert.match(logs.join('\n'), /FAILED: 403 Forbidden/);
});
