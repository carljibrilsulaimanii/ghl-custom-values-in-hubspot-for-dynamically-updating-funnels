#!/usr/bin/env node
/**
 * create-schema.mjs -- create the two custom objects and the contact properties
 * ------------------------------------------------------------------------------
 * Author:  Jibril Sulaiman
 * Created: 2026-10-01 (ET)
 * Deploy:  Run locally once (README Step 1, Route B). Needs Node 20+.
 * What:    Creates Free Class Configuration and Class Registrations (each associated
 *          to Contacts) with every property in schema/schema.mjs, then the contact
 *          properties. Safe to re-run: anything that already exists is skipped,
 *          nothing is changed or deleted.
 * Why:     Building ~55 properties by hand is where typos in internal names creep in,
 *          and the modules and workflows match those names exactly.
 *
 * Usage:   HUBSPOT_TOKEN=<service key> node scripts/create-schema.mjs           (dry run)
 *          HUBSPOT_TOKEN=<service key> node scripts/create-schema.mjs --apply   (creates)
 * Scopes:  crm.schemas.custom.read, crm.schemas.custom.write,
 *          crm.schemas.contacts.write, crm.objects.contacts.read
 */
import { CONFIG_OBJECT, REGISTRATION_OBJECT, CONTACT_PROPERTIES } from '../schema/schema.mjs';

const BASE = 'https://api.hubapi.com';

export async function createSchema({ token, apply = false, fetchImpl = fetch, log = console.log }) {
  if (!token) throw new Error('Set HUBSPOT_TOKEN to a service key (see the Scopes line in this file).');
  const api = async (method, path, body) => {
    const res = await fetchImpl(BASE + path, {
      method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${text.slice(0, 300)}`);
    return text ? JSON.parse(text) : {};
  };

  const summary = { created: [], skipped: [], objectTypeIds: {} };
  const existing = (await api('GET', '/crm/v3/schemas')).results || [];

  for (const def of [CONFIG_OBJECT, REGISTRATION_OBJECT]) {
    const found = existing.find((s) => s.name === def.name);
    if (!found) {
      log(`${apply ? 'CREATE' : 'would create'} object ${def.labels.singular} with ${def.properties.length} properties`);
      if (apply) {
        const made = await api('POST', '/crm/v3/schemas', {
          name: def.name, labels: def.labels,
          primaryDisplayProperty: def.primaryDisplayProperty,
          requiredProperties: def.requiredProperties,
          searchableProperties: [def.primaryDisplayProperty],
          associatedObjects: def.associatedObjects,
          properties: def.properties,
        });
        summary.objectTypeIds[def.name] = made.objectTypeId;
      }
      summary.created.push(`object:${def.name}`);
      continue;
    }
    summary.objectTypeIds[def.name] = found.objectTypeId;
    const have = new Set((found.properties || []).map((p) => p.name));
    const missing = def.properties.filter((p) => !have.has(p.name));
    def.properties.filter((p) => have.has(p.name)).forEach((p) => summary.skipped.push(`${def.name}.${p.name}`));
    // A new property needs a group. Use the object's own first group rather than guess its name.
    let groupName = null;
    if (missing.length) {
      const groups = (await api('GET', `/crm/v3/properties/${found.objectTypeId}/groups`)).results || [];
      groupName = groups.length ? groups[0].name : null;
      if (!groupName) throw new Error(`${def.labels.singular} has no property group; create one in Settings > Properties first.`);
    }
    for (const p of missing) {
      log(`${apply ? 'CREATE' : 'would create'} ${def.name}.${p.name}`);
      if (apply) await api('POST', `/crm/v3/properties/${found.objectTypeId}`, { ...p, groupName });
      summary.created.push(`${def.name}.${p.name}`);
    }
  }

  const contactProps = new Set(((await api('GET', '/crm/v3/properties/contacts')).results || []).map((p) => p.name));
  for (const p of CONTACT_PROPERTIES) {
    if (contactProps.has(p.name)) { summary.skipped.push(`contacts.${p.name}`); continue; }
    log(`${apply ? 'CREATE' : 'would create'} contacts.${p.name}`);
    if (apply) await api('POST', '/crm/v3/properties/contacts', { ...p, groupName: 'contactinformation' });
    summary.created.push(`contacts.${p.name}`);
  }

  log(`\n${apply ? 'Created' : 'Would create'} ${summary.created.length}, already present ${summary.skipped.length}.`);
  for (const [name, id] of Object.entries(summary.objectTypeIds)) if (id) log(`Object type id for ${name}: ${id}`);
  if (!apply) log('Dry run only. Re-run with --apply to create.');
  return summary;
}

const isMain = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop());
if (isMain) {
  createSchema({ token: process.env.HUBSPOT_TOKEN, apply: process.argv.includes('--apply') })
    .catch((e) => { console.error(e.message); process.exit(1); });
}
