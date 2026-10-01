/**
 * harness.mjs -- runs a workflow-actions/*.js file the way HubSpot does
 * ----------------------------------------------------------------------
 * Author:  Jibril Sulaiman
 * Created: 2026-10-01 (ET)
 * Deploy:  Local only.
 * What:    Loads an action unchanged in a vm sandbox with a frozen clock, a fake
 *          fetch, fake secrets and a fake @hubspot/api-client, then calls
 *          exports.main and returns its outputFields, logs and calls.
 * Why:     Custom code actions can only be tested one record at a time in the
 *          HubSpot UI. These checks pin the edge cases (late by one second, ISO vs
 *          epoch input, missing fields) before a live class does.
 */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';

const DIR = path.join(path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1'), '..', 'workflow-actions');

export async function run(file, { inputFields = {}, objectId = '9001', now = Date.parse('2026-09-17T22:00:00Z'), env = {}, fetchImpl, hubspot } = {}) {
  const logs = [];
  const calls = { fetch: [], hubspot: [] };
  const RealDate = Date;
  class FrozenDate extends RealDate {
    constructor(...a) { super(...(a.length ? a : [now])); }
    static now() { return now; }
  }
  const fakeFetch = async (url, opts) => {
    calls.fetch.push({ url, opts, body: opts && opts.body ? JSON.parse(opts.body) : null });
    if (fetchImpl) return fetchImpl(url, opts);
    return { ok: true, status: 200, text: async () => '' };
  };
  const fakeRequire = (name) => {
    if (name !== '@hubspot/api-client') throw new Error('unexpected require ' + name);
    return { Client: class { constructor(o) { calls.hubspot.push({ op: 'client', token: o.accessToken }); return hubspot ? hubspot(calls) : defaultHubspot(calls); } } };
  };
  const module = { exports: {} };
  const ctx = {
    module, exports: module.exports, require: fakeRequire, fetch: fakeFetch,
    process: { env }, Date: FrozenDate, Intl, JSON, Math, String, Number, parseInt, isNaN, Promise,
    console: { log: (...a) => logs.push(a.join(' ')), error: (...a) => logs.push('ERROR ' + a.join(' ')) },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(DIR, file), 'utf8'), ctx, { filename: file });
  const result = await new Promise((resolve, reject) => {
    Promise.resolve(module.exports.main({ inputFields, object: { objectId } }, resolve)).catch(reject);
  });
  // Objects built inside the sandbox have its own prototypes; round-trip them so
  // deepStrictEqual compares content, not realms.
  const plain = (v) => JSON.parse(JSON.stringify(v));
  return { out: plain(result.outputFields), logs, calls: plain(calls) };
}

// A minimal stand-in for the HubSpot client: one enum property, record updates recorded.
export function defaultHubspot(calls, options = ['2026-09-10 - REITs']) {
  return {
    crm: {
      properties: { coreApi: {
        getByName: async (ot, name) => { calls.hubspot.push({ op: 'getProperty', ot, name }); return { options: options.map((v) => ({ label: v, value: v })) }; },
        update: async (ot, name, body) => { calls.hubspot.push({ op: 'updateProperty', ot, name, body }); return {}; },
      } },
      objects: { basicApi: {
        update: async (ot, id, body) => { calls.hubspot.push({ op: 'updateRecord', ot, id, body }); return {}; },
      } },
    },
  };
}
