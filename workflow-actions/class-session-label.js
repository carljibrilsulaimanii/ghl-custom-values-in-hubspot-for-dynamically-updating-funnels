/*
 Class Session — auto-populate from Class Date + Class Topic
 Author: Jibril Sulaiman · 2026-08-24 (published 2026-10-01)

 Deploy: its own workflow on the Class Registrations object (Step 11).
 Custom code action · Node.js 20.x · secret CLASS_SESSION_WRITE_TOKEN
 (a service key with read + write on the Class Registrations object and its
 property definitions).

 WHAT IT DOES
 Builds one label per class, "<YYYY-MM-DD> - <Topic>" (e.g.
 "2026-09-17 - Dividend Stocks"), writes it to the Class Session dropdown on
 the registration, and adds the dropdown option first if it doesn't exist yet.

 WHY A DROPDOWN, AND WHY CODE
 Reports group cleanly on a dropdown and not on free text, but HubSpot can't
 add dropdown options from a workflow. This action creates the option on the
 fly, so a new class never needs a property edit.

 TIMEZONE FIX
 class_date is a date property (midnight UTC). For an evening class in
 US Eastern, the date taken naively from the timestamp can be the next day.
 When the associated configuration record's event start is available, the
 Eastern calendar date is used instead, and class_date is corrected.

 EDIT FOR YOUR TOPICS
 The topic rules below match on words in class_topic. Add one line per topic
 you run, or the label stays empty and nothing is written for that topic.

 INPUTS   class_date, class_topic          (the enrolled Class Registration)
          event_start_date_and_time        (associated configuration record)
 OUTPUTS  class_session (String)
*/
const hubspot = require('@hubspot/api-client');
const OBJECT_TYPE = '2-12345678';               // your Class Registrations object type id
const SECRET = 'CLASS_SESSION_WRITE_TOKEN';

exports.main = async (event, callback) => {
  // --- PARSE class_date (may arrive as epoch ms OR ISO string) ---
  var rawDate = String(event.inputFields['class_date'] || '');
  var iso = '';
  if (/^\d+$/.test(rawDate)) {
    var d = new Date(Number(rawDate));
    iso = d.toISOString().slice(0, 10);
    console.log('class_date was epoch ms: ' + rawDate + ' -> ' + iso);
  } else {
    iso = rawDate.slice(0, 10);
  }

  var t = String(event.inputFields['class_topic'] || '').toLowerCase();
  var topic = '';
  if (t.indexOf('reit') > -1) topic = 'REITs';
  else if (t.indexOf('dividend') > -1) topic = 'Dividend Stocks';
  else if (t.indexOf('etf') > -1 || t.indexOf('stock') > -1) topic = 'Stocks & ETFs';

  // --- TIMEZONE FIX ---
  var fixedIso = iso;
  try {
    var eventTs = event.inputFields['event_start_date_and_time'];
    if (eventTs) {
      var ms = Number(eventTs);
      var dt = isNaN(ms) ? new Date(String(eventTs)) : new Date(ms);
      if (!isNaN(dt.getTime())) {
        var parts = new Intl.DateTimeFormat('en-US', {
          timeZone: 'America/New_York',
          year: 'numeric', month: '2-digit', day: '2-digit'
        }).formatToParts(dt);
        var y = parts.find(function(p) { return p.type === 'year'; }).value;
        var m = parts.find(function(p) { return p.type === 'month'; }).value;
        var dd = parts.find(function(p) { return p.type === 'day'; }).value;
        fixedIso = y + '-' + m + '-' + dd;
        console.log('TZ fix: raw=' + iso + ' corrected=' + fixedIso);
      }
    }
  } catch (tzErr) {
    console.log('TZ fix skipped: ' + String(tzErr.message || tzErr).slice(0, 200));
  }

  // --- BUILD LABEL (YYYY-MM-DD format to match existing enum options) ---
  var label = (fixedIso && topic) ? fixedIso + ' - ' + topic : '';
  console.log('iso=' + fixedIso + ' topic=' + topic + ' label=' + label);
  if (!label) {
    callback({ outputFields: { class_session: '' } });
    return;
  }

  var token = process.env[SECRET];
  if (!token) {
    console.log('SECRET MISSING: ' + SECRET);
    callback({ outputFields: { class_session: label } });
    return;
  }

  try {
    var client = new hubspot.Client({ accessToken: token });

    // --- ENSURE ENUM OPTION EXISTS before setting value ---
    try {
      var prop = await client.crm.properties.coreApi.getByName(OBJECT_TYPE, 'class_session');
      var exists = (prop.options || []).some(function(o) { return o.value === label; });
      if (!exists) {
        var newOptions = (prop.options || []).concat([{
          label: label,
          value: label,
          displayOrder: -1,
          hidden: false
        }]);
        await client.crm.properties.coreApi.update(OBJECT_TYPE, 'class_session', {
          options: newOptions
        });
        console.log('CREATED enum option: ' + label);
      } else {
        console.log('Enum option already exists: ' + label);
      }
    } catch (enumErr) {
      console.log('Enum option check failed (will try update anyway): ' + String(enumErr.message || enumErr).slice(0, 300));
    }

    // --- UPDATE RECORD ---
    var props = { class_session: label };
    if (fixedIso !== iso) {
      var pArr = fixedIso.split('-');
      var correctedMs = Date.UTC(parseInt(pArr[0]), parseInt(pArr[1]) - 1, parseInt(pArr[2]));
      props.class_date = String(correctedMs);
      console.log('FIXING class_date: ' + iso + ' -> ' + fixedIso + ' (ms: ' + correctedMs + ')');
    }

    await client.crm.objects.basicApi.update(OBJECT_TYPE, String(event.object.objectId), {
      properties: props
    });
    console.log('WROTE label=' + label + (props.class_date ? ' + fixed date' : ''));
  } catch (e) {
    console.log('FAILED: ' + String(e.message || e).slice(0, 400));
  }

  callback({ outputFields: { class_session: label } });
};
