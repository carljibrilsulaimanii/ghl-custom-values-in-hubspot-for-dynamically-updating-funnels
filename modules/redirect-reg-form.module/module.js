/*
  Redirect Reg Form (Free Class Live Router) -- module.js
  Author:  Jibril Sulaiman
  Date:    2026-09 (published 2026-10-01)
  Deploy:  Design Manager > your module "Redirect Reg Form" > JS pane
  What:    1. Stamps the contact property fc_registration_timing ("Live" or
              "Pre-Class") into a hidden field on the registration form.
           2. On submit, sends the visitor to the live watch link if the class has
              started (with ?t=<start_seconds>), otherwise to confirmation_url,
              carrying UTMs and click ids.
           3. Optionally relabels the submit button.
  Why:     HubSpot's form "redirect to another page" setting is fixed per form, so
           it cannot change at 7pm. This decides at submit time instead.
  Needs:   A contact property fc_registration_timing (dropdown: Live, Pre-Class) added
           to the form as a hidden field. The cookie read below is written by the
           sitewide UTM header script from the companion order-form repo; without it,
           only the current URL's UTMs are carried.
*/
(function () {
  // Contact property the module stamps on every submission. The attendance
  // workflow filters on it, so changing these strings means changing the
  // workflow's enrolment criteria too.
  //
  // Both values are written, always. Writing only LIVE would leave the field
  // saying "Live" forever after one late registration, and the next class's
  // early registrants would inherit it and get a false attendance record.
  var TIMING_FIELD = 'fc_registration_timing';
  var LIVE_VALUE = 'Live';
  var EARLY_VALUE = 'Pre-Class';

  // HubSpot's newer forms namespace every input with the object type prefix —
  // the field renders as name="0-1/fc_registration_timing", not the bare
  // property name, and NOT as type="hidden". Match both shapes so this works
  // on legacy embeds too.
  var FIELD_SELECTOR =
    'input[name="' + TIMING_FIELD + '"], input[name$="/' + TIMING_FIELD + '"], ' +
    'select[name="' + TIMING_FIELD + '"], select[name$="/' + TIMING_FIELD + '"]';

  // Campaign stash written by the sitewide header snippet. Read only here —
  // that snippet owns every write, and a second writer with its own rules would
  // eventually disagree with it about which touch counts.
  var COOKIE = 'site_attr';

  var CLICK_IDS = [
    'gclid', 'wbraid', 'gbraid', 'fbclid', 'msclkid', 'ttclid',
    'twclid', 'li_fat_id', 'irclickid', 'epik', 'sccid', 'rdt_cid'
  ];

  function isTracking(key) {
    var k = String(key).toLowerCase();
    return /^utm_/.test(k) || /^hsa_/.test(k) || CLICK_IDS.indexOf(k) !== -1;
  }

  // Cookie first so the campaign survives a landing page that is not this one,
  // then anything on the current URL layered over it.
  function trackingParams() {
    var out = {};
    try {
      var m = document.cookie.match(new RegExp('(?:^|;\\s*)' + COOKIE + '=([^;]*)'));
      if (m) {
        var stash = JSON.parse(decodeURIComponent(m[1])) || {};
        Object.keys(stash).forEach(function (k) {
          if (k !== '_t' && stash[k]) out[k] = stash[k]; // _t is capture time
        });
      }
    } catch (e) {}

    try {
      new URL(window.location.href).searchParams.forEach(function (value, key) {
        if (value && isTracking(key)) out[key] = value;
      });
    } catch (e) {}

    return out;
  }

  function withParams(url, params) {
    if (!url) return '';
    var u;
    try {
      u = new URL(url, window.location.href);
    } catch (e) {
      return url;
    }
    Object.keys(params).forEach(function (k) {
      if (params[k]) u.searchParams.set(k, params[k]);
    });
    return u.toString();
  }

  // YouTube reads the offset as `t` on watch/live/youtu.be URLs and as `start`
  // on /embed/ URLs. The wrong one is silently ignored, which reads as "the
  // parameter did not work" rather than "wrong parameter".
  function withStart(url, seconds) {
    if (!url) return '';
    var u;
    try {
      u = new URL(url, window.location.href);
    } catch (e) {
      return url;
    }
    if (!seconds) return u.toString();
    if (/\/embed\//.test(u.pathname)) u.searchParams.set('start', seconds);
    else u.searchParams.set('t', seconds);
    return u.toString();
  }

  // HubSpot's newer forms are React-controlled: assigning .value directly is
  // reverted on the next render. Going through the native setter and firing the
  // events React listens for is what makes the value stick and get submitted.
  function setValue(el, value) {
    try {
      var proto = window.HTMLInputElement.prototype;
      if (el.tagName === 'TEXTAREA') proto = window.HTMLTextAreaElement.prototype;
      else if (el.tagName === 'SELECT') proto = window.HTMLSelectElement.prototype;
      var desc = Object.getOwnPropertyDescriptor(proto, 'value');
      if (desc && desc.set) desc.set.call(el, value);
      else el.value = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) {}
  }

  function setup(root) {
    var start = parseInt(root.getAttribute('data-start'), 10);
    var watch = root.getAttribute('data-watch') || '';
    var seconds = parseInt(root.getAttribute('data-seconds'), 10) || 0;
    var offset = (parseFloat(root.getAttribute('data-offset')) || 0) * 60000;
    var confirm = root.getAttribute('data-confirm') || '';
    var label = root.getAttribute('data-button-label') || '';
    var formId = root.getAttribute('data-form') || '';

    if (!start) return; // nothing to compare against; leave the form alone

    var labelTimer = null;

    function isLive() {
      return Date.now() >= (start - offset);
    }

    // Resolved at submit time, not page load. The button is a form submit, not
    // a link, so there is no href to keep in sync — the clock is read once, at
    // the moment it matters. Someone who sits on the page through 7pm still
    // routes live without reloading.
    function destination() {
      var base = (isLive() && watch) ? withStart(watch, seconds) : confirm;
      if (!base) return '';
      return withParams(base, trackingParams());
    }

    // Scoped to the form that carries our timing field, so a second form on the
    // page never gets relabelled. Falls back to a lone form only when there is
    // exactly one, which cannot be the wrong one.
    function targetForm() {
      var f = document.querySelector(FIELD_SELECTOR);
      if (f && f.form) return f.form;
      var forms = document.querySelectorAll('form');
      return forms.length === 1 ? forms[0] : null;
    }

    function applyButtonLabel() {
      if (!label) return;
      var f = targetForm();
      if (!f) return;
      var b = f.querySelector('input[type="submit"], button[type="submit"], .hs-button.primary');
      if (!b) return;
      if (b.tagName === 'INPUT') {
        if (b.value !== label) b.value = label;
      } else if (b.textContent.trim() !== label) {
        b.textContent = label;
      }
    }

    // HubSpot resets the button text when submission starts, and does it by
    // property write — which fires no mutation record. Re-apply on a timer.
    function holdLabel() {
      if (!label) return;
      clearInterval(labelTimer);
      var until = Date.now() + 3000;
      labelTimer = setInterval(function () {
        if (Date.now() > until) { clearInterval(labelTimer); return; }
        try { applyButtonLabel(); } catch (e) {}
      }, 50);
    }

    // The CTA injects its form when the popup opens, which can be long after
    // load — so keep looking rather than acting once at init. Re-stamping on an
    // interval also means a popup opened at 6:59 and submitted at 7:01 is
    // correctly recorded as Live.
    function tick() {
      var value = isLive() ? LIVE_VALUE : EARLY_VALUE;
      var fields = document.querySelectorAll(FIELD_SELECTOR);
      for (var i = 0; i < fields.length; i++) {
        if (fields[i].value !== value) setValue(fields[i], value);
      }
      try { applyButtonLabel(); } catch (e) {}
    }

    if (window.MutationObserver) {
      new MutationObserver(tick).observe(document.documentElement, {
        childList: true,
        subtree: true
      });
    }
    setInterval(tick, 500);
    tick();

    document.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest('input[type="submit"], button[type="submit"], .hs-button.primary')) holdLabel();
    }, true);
    document.addEventListener('submit', holdLabel, true);

    // Best effort only: when the event exposes a form id and a guid is
    // configured, require a match. Events that carry no id are acted on, since
    // refusing them would break the common single-form page.
    function wrongForm(id) {
      return !!(formId && id && id !== formId);
    }

    var done = false;
    function route(id) {
      if (done || wrongForm(id)) return;
      var url = destination();
      if (!url) return; // no confirmation_url set; nothing to route to
      done = true;
      window.location.replace(url);
    }

    document.addEventListener('hs-form-event:on-submitted', function (e) {
      route((e.detail && (e.detail.formId || e.detail.id)) || '');
    }, true);

    window.addEventListener('message', function (e) {
      if (e.data && e.data.type === 'hsFormCallback' && e.data.eventName === 'onFormSubmitted') {
        route(e.data.id || '');
      }
    });
  }

  function init() { document.querySelectorAll('.fclr').forEach(setup); }
  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
})();
