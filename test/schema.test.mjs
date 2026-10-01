/**
 * schema.test.mjs -- tests for schema/schema.mjs and scripts/create-schema.mjs
 * ----------------------------------------------------------------------------
 * Author:  Jibril Sulaiman
 * Created: 2026-10-01 (ET)
 * Deploy:  Local only. `npm test`.
 * What:    The schema covers every property the modules and actions read; the
 *          script dry-runs without writing, creates what's missing, skips what exists.
 * Why:     A module that fetches a property the object doesn't have renders blank
 *          with no error, so the names are checked against the code here.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { CONFIG_OBJECT, REGISTRATION_OBJECT, CONTACT_PROPERTIES } from '../schema/schema.mjs';
import { createSchema } from '../scripts/create-schema.mjs';

const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1'), '..');
const configNames = new Set(CONFIG_OBJECT.properties.map((p) => p.name));

test('every module fetches only properties the configuration object defines', () => {
  const dirs = fs.readdirSync(path.join(ROOT, 'modules'));
  assert.equal(dirs.length, 7);
  for (const d of dirs) {
    const fields = JSON.parse(fs.readFileSync(path.join(ROOT, 'modules', d, 'fields.json'), 'utf8'));
    const crm = fields.filter((f) => f.type === 'crmobject');
    assert.equal(crm.length, 1, `${d} has one CRM object field`);
    assert.equal(crm[0].object_type, 'p_' + CONFIG_OBJECT.name, `${d} points at the configuration object`);
    for (const p of [...crm[0].properties_to_fetch, ...crm[0].display_properties]) {
      assert.ok(configNames.has(p), `${d} fetches ${p}, which the schema defines`);
    }
    const html = fs.readFileSync(path.join(ROOT, 'modules', d, 'module.html'), 'utf8');
    for (const [, prop] of html.matchAll(/\.properties\.([a-z_]+)/g)) {
      assert.ok(crm[0].properties_to_fetch.includes(prop), `${d} reads ${prop} and also fetches it`);
    }
  }
});

test('the registration object has every property the code writes', () => {
  const names = new Set(REGISTRATION_OBJECT.properties.map((p) => p.name));
  for (const p of ['class_session', 'class_date', 'class_topic', 'class_status', 'registration_reference', 'reg_redirect']) assert.ok(names.has(p), p);
  const contact = new Set(CONTACT_PROPERTIES.map((p) => p.name));
  for (const p of ['reg_redirect', 'fc_registration_timing', 'fc_current_class_topic']) assert.ok(contact.has(p), p);
  assert.deepEqual(CONTACT_PROPERTIES.find((p) => p.name === 'fc_registration_timing').options.map((o) => o.value), ['Pre-Class', 'Live']);
});

test('date pairs: display strings are text, the real dates are date types', () => {
  const byName = Object.fromEntries(CONFIG_OBJECT.properties.map((p) => [p.name, p]));
  assert.equal(byName.free_class_date.type, 'string');
  assert.equal(byName.old_free_class_date.type, 'string');
  assert.equal(byName.event_start_date_and_time.type, 'datetime');
  assert.equal(byName.old_class_date.type, 'date');
});

function fakeHubSpot(state) {
  const calls = [];
  const fetchImpl = async (url, opts) => {
    const p = new URL(url).pathname; const m = opts.method; const body = opts.body ? JSON.parse(opts.body) : null;
    calls.push({ m, p, body });
    const ok = (j) => ({ ok: true, status: 200, text: async () => JSON.stringify(j) });
    if (m === 'GET' && p === '/crm/v3/schemas') return ok({ results: state.schemas });
    if (m === 'GET' && p === '/crm/v3/properties/contacts') return ok({ results: state.contactProps.map((name) => ({ name })) });
    if (m === 'GET' && /\/groups$/.test(p)) return ok({ results: [{ name: 'registration_info' }] });
    if (m === 'POST' && p === '/crm/v3/schemas') return ok({ objectTypeId: '2-' + (100 + calls.length) });
    if (m === 'POST') return ok({});
    return { ok: false, status: 404, text: async () => 'nope' };
  };
  return { calls, fetchImpl };
}

test('dry run reads but never writes', async () => {
  const { calls, fetchImpl } = fakeHubSpot({ schemas: [], contactProps: [] });
  const s = await createSchema({ token: 't', fetchImpl, log: () => {} });
  assert.ok(calls.every((c) => c.m === 'GET'));
  assert.equal(s.created.length, 2 + CONTACT_PROPERTIES.length);
});

test('apply creates both objects with all properties and the contact properties', async () => {
  const { calls, fetchImpl } = fakeHubSpot({ schemas: [], contactProps: ['reg_redirect'] });
  await createSchema({ token: 't', apply: true, fetchImpl, log: () => {} });
  const made = calls.filter((c) => c.m === 'POST' && c.p === '/crm/v3/schemas').map((c) => c.body);
  assert.deepEqual(made.map((b) => b.name), ['free_class_configurations', 'class_registrations']);
  assert.equal(made[0].properties.length, CONFIG_OBJECT.properties.length);
  assert.deepEqual(made[0].associatedObjects, ['CONTACT']);
  const contactPosts = calls.filter((c) => c.m === 'POST' && c.p === '/crm/v3/properties/contacts');
  assert.equal(contactPosts.length, CONTACT_PROPERTIES.length - 1); // reg_redirect already existed
  assert.ok(contactPosts.every((c) => c.body.groupName === 'contactinformation'));
});

test('existing object: only missing properties are added, into its own group', async () => {
  const have = REGISTRATION_OBJECT.properties.map((p) => ({ name: p.name })).filter((p) => p.name !== 'class_session');
  const { calls, fetchImpl } = fakeHubSpot({ schemas: [{ name: 'class_registrations', objectTypeId: '2-555', properties: have }], contactProps: [] });
  const s = await createSchema({ token: 't', apply: true, fetchImpl, log: () => {} });
  const posts = calls.filter((c) => c.m === 'POST' && c.p === '/crm/v3/properties/2-555');
  assert.deepEqual(posts.map((c) => c.body.name), ['class_session']);
  assert.equal(posts[0].body.groupName, 'registration_info');
  assert.equal(s.objectTypeIds.class_registrations, '2-555');
});

test('no token is a clear error', async () => {
  await assert.rejects(() => createSchema({ token: '' }), /HUBSPOT_TOKEN/);
});
