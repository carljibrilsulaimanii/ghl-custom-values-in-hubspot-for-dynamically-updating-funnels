/*
 Free Class — Submit Attended Form for Late Registrations
 Author: Jibril Sulaiman · 2026-09-22 (published 2026-10-01)

 Deploy: Registration workflow (Step 8), on the "true" leaf of the
 registeredLate branch, one copy per topic branch.
 Custom code action · Node.js 20.x · no secrets (the Forms submission API
 is public).

 WHAT IT DOES
 Submits that topic's Attended form on the contact's behalf, carrying
 reg_redirect = Yes. The Attended workflow already enrols on those forms, so it
 builds the Attended record using the mappings it has always used.

 WHY SUBMIT A FORM RATHER THAN CREATE THE RECORD HERE
 Creating it here would mean a second Create record action per topic — eight
 places to keep in step instead of four. Submitting the form routes the
 contact into the attendance workflow that already exists, so the definition
 of an Attended record stays in exactly one place.

 NO TIME CHECK HERE
 The Late Registration Check already decided. Reaching this action means
 registeredLate was true, so this one only submits. Do not re-check the clock
 — two places deciding the same thing is how they end up disagreeing.

 reg_redirect = Yes
 Reaching this line means the contact was routed into a class already in
 progress. Every other submission of that form — someone on the watch page,
 or a manual entry — leaves the field on its default of No, so the property
 always describes the submission that just happened. Class Registration syncs
 it from the contact, so a stale value would follow someone into next month.

 THE FIELD MUST BE ON THE FORM AND PUBLISHED
 If Reg Redirect is missing from the Attended form, or the form has unpublished
 changes, HubSpot accepts the submission and silently drops the value. The API
 returns 200, the log looks clean, and the contact stays No.

 PER BRANCH
 Only FORM_GUID changes between copies. Take it from the Attended form's editor
 URL: app.hubspot.com/forms/<PORTAL_ID>/new-editor/<GUID>

 ON ERROR IT DOES NOT THROW
 A failed submission returns submitted = false and logs the response body. The
 registration record already exists by this point, so a crash here would lose
 only the attendance half — better seen in the log than as a red action.

 INPUTS   email, firstname, lastname, phone  (the enrolled contact)
 OUTPUTS  submitted (Boolean), reason (String)
*/

const PORTAL_ID = 'REPLACE_WITH_PORTAL_ID';   // Settings > Account Defaults > Hub ID
const FORM_GUID = 'REPLACE_WITH_FORM_GUID';   // this branch's Attended form

exports.main = async (event, callback) => {
  const out = { submitted: false, reason: '' };

  try {
    if (!FORM_GUID) {
      out.reason = 'no_form_guid';
      console.error("FORM_GUID is empty. Set it to this branch's Attended form.");
      return callback({ outputFields: out });
    }

    const email = String(event.inputFields['email'] || '').trim();
    if (!email) {
      out.reason = 'no_email';
      console.log('Contact has no email; the Forms API cannot identify them.');
      return callback({ outputFields: out });
    }

    const fields = [
      { objectTypeId: '0-1', name: 'email', value: email },
      { objectTypeId: '0-1', name: 'reg_redirect', value: 'Yes' }
    ];

    // Only send the optional identity fields when we actually have them — an
    // empty value would overwrite a good one on the contact.
    ['firstname', 'lastname', 'phone'].forEach((key) => {
      const value = String(event.inputFields[key] || '').trim();
      if (value) fields.push({ objectTypeId: '0-1', name: key, value });
    });

    const url =
      `https://api.hsforms.com/submissions/v3/integration/submit/${PORTAL_ID}/${FORM_GUID}`;

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fields,
        context: {
          pageUri: 'workflow://late-registration',
          pageName: 'Late registration (workflow 2)'
        }
      })
    });

    const body = await res.text();

    if (!res.ok) {
      out.reason = `submit_failed_${res.status}`;
      console.error(`Attended form submission failed: ${res.status} ${body}`);
      return callback({ outputFields: out });
    }

    out.submitted = true;
    out.reason = 'submitted';
    console.log(`Submitted Attended form ${FORM_GUID} for ${email}.`);
  } catch (err) {
    out.reason = 'error';
    console.error('Attended form submission errored:', err.message);
  }

  callback({ outputFields: out });
};
