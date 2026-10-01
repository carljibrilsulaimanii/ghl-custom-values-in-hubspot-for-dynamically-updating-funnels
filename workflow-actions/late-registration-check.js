/*
 Free Class — Late Registration Check
 Author: Jibril Sulaiman · 2026-09-22 (published 2026-10-01)

 Deploy: Registration workflow (Step 8), one copy inside each topic branch,
 mapped to that topic's "Active <Topic> Config" data source.
 Custom code action · Node.js 20.x · no secrets.

 WHAT IT DOES
 Decides whether this registration arrived after the class had already begun,
 and outputs the value for Reg Redirect. It writes nothing itself — the Edit
 record action after it sets the contact property from `regRedirect`, which
 keeps this action free of secrets and API calls.

 WHY BOTH VALUES, NEVER JUST Yes
 Class Registration syncs Reg Redirect from the contact. Writing only Yes
 would leave it saying Yes forever after one late registration, and the next
 class's organic attendance record would inherit it and report a redirect that
 never happened. Always writing one value or the other is the reset.

 WHERE THE START TIME COMES FROM
 The `event_start_date_and_time` input is mapped from that branch's Active
 Config data source, not hardcoded. Updating the config record for next
 month's class is the only per-class step — this action never changes. Each
 topic branch needs its own copy, because a workflow data source resolves to
 one fixed record.

 ON ERROR IT RETURNS No
 A crash or an unparseable date must not leave the output empty, or the Edit
 record action writes nothing and the previous class's value survives. No is
 the safe direction: a missing late-flag is recoverable from the timestamps, a
 false one quietly corrupts attendance reporting.

 TIMING ASSUMPTION
 Lateness is judged at execution time — HubSpot does not expose the form
 submission timestamp here. The workflow fires within seconds of the form, so
 the two differ only if the queue is backed up.

 INPUTS   event_start_date_and_time  (Active Config → 7. Event Start Date and Time)
 OUTPUTS  regRedirect (String), registeredLate (Boolean), classStartIso (String),
          reason (String)
*/

const GRACE_MINUTES = 0; // minutes before the start to count as live
const ZONE = 'America/New_York';

function eastern(ms) {
  try {
    return new Date(ms).toLocaleString('en-US', {
      timeZone: ZONE,
      dateStyle: 'medium',
      timeStyle: 'short'
    }) + ' ET';
  } catch (err) {
    return new Date(ms).toISOString() + ' UTC';
  }
}

exports.main = async (event, callback) => {
  const out = {
    regRedirect: 'No',
    registeredLate: false,
    classStartIso: '',
    reason: ''
  };

  try {
    const raw = String(event.inputFields['event_start_date_and_time'] || '').trim();

    if (!raw) {
      out.reason = 'no_start_time';
      console.log('No event_start_date_and_time on the input. Check the Active Config mapping on this branch.');
      return callback({ outputFields: out });
    }

    // HubSpot passes datetimes as epoch milliseconds, but a mapped property can
    // arrive as an ISO string. Accept both rather than guess.
    const start = /^\d+$/.test(raw) ? parseInt(raw, 10) : Date.parse(raw);

    if (!start || isNaN(start)) {
      out.reason = 'unparseable_start_time';
      console.log(`Could not parse start time "${raw}".`);
      return callback({ outputFields: out });
    }

    out.classStartIso = new Date(start).toISOString();

    const now = Date.now();
    out.registeredLate = now >= (start - (GRACE_MINUTES * 60000));
    out.regRedirect = out.registeredLate ? 'Yes' : 'No';
    out.reason = out.registeredLate ? 'after_start' : 'before_start';

    console.log(
      `Class starts ${eastern(start)}; now ${eastern(now)}; ` +
      `regRedirect=${out.regRedirect}`
    );
  } catch (err) {
    out.regRedirect = 'No';
    out.registeredLate = false;
    out.reason = 'error';
    console.error('Late registration check failed:', err.message);
  }

  callback({ outputFields: out });
};
