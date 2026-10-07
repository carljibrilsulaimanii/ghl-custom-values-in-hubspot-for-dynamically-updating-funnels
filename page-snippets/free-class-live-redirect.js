(function () {
  "use strict";

  /*
    Free Class Live Redirect
    Author: Jibril Sulaiman · 2026-09-10 (published 2026-10-07)
    Deploy: Design Manager > New file > JavaScript file, named exactly
            "Free Class Live Redirect.js" (README Step 6f). Paste this whole file.
            Only the cookie name and comments differ from the running copy.

    Paired with a HubL block in the confirmation page's Head HTML, which sets
    window.liveClassConfig from the Free Class Configuration record selected by
    subdomain. This file holds no class data — updating the record is the only
    per-class step.

    Someone who registers after the class has begun lands on the confirmation
    page, reads that they should come back later, and leaves. This sends them
    to the class instead, starting the video at 3:00 so it feels like they
    caught the opening rather than joined late. Before the start time it does
    nothing.

    CONFIRMATION PAGES ONLY. It redirects on load, so on a registration page it
    would throw people out before they register.

    Unlike a redirect meant for registration pages, this does NOT skip hs_preview. Testing requires
    setting `offset` high, and doing that on a published page would redirect
    real visitors — so previews have to be usable. The iframe guard still keeps
    the page editor safe.
  */

  // The Meta and TikTok pixels fire from Head HTML above this script.
  // Navigating immediately can abort their in-flight requests, which would
  // silently stop counting conversions for late registrants — the exact
  // cohort this redirect creates. Give them a moment to flush.
  var PIXEL_FLUSH_MS = 400;

  var cfg = window.liveClassConfig;

  if (!cfg || typeof cfg.watch !== "string" || !/^https?:\/\//i.test(cfg.watch)) {
    console.error("Free Class Live Redirect: destination URL is missing or invalid.");
    return;
  }

  // crm_object returns the datetime as either epoch milliseconds or an ISO
  // string depending on the property; accept both rather than guess.
  var start = /^\d+$/.test(String(cfg.start))
    ? parseInt(cfg.start, 10)
    : Date.parse(cfg.start);

  if (!start) {
    console.error("Free Class Live Redirect: start time is missing or unparseable.");
    return;
  }

  try {
    if (window.self !== window.top) return;   // page editor preview
  } catch (err) {
    return;
  }

  var offset = (parseFloat(cfg.offset) || 0) * 60000;
  if (Date.now() < start - offset) return;    // class has not started

  var COOKIE = "site_attr";
  var CLICK_IDS = [
    "gclid", "wbraid", "gbraid", "fbclid", "msclkid", "ttclid",
    "twclid", "li_fat_id", "irclickid", "epik", "sccid", "rdt_cid"
  ];

  function isTracking(key) {
    var k = String(key).toLowerCase();
    return /^utm_/.test(k) || /^hsa_/.test(k) || CLICK_IDS.indexOf(k) !== -1;
  }

  var u;
  try {
    u = new URL(cfg.watch, window.location.href);
  } catch (err) {
    return;
  }

  // YouTube reads the offset as `t` on watch/live/youtu.be URLs and as `start`
  // on /embed/ URLs. The wrong one is silently ignored, which reads as "the
  // parameter did not work" rather than "wrong parameter".
  var seconds = parseInt(cfg.seconds, 10) || 0;
  if (seconds) {
    if (/\/embed\//.test(u.pathname)) u.searchParams.set("start", seconds);
    else u.searchParams.set("t", seconds);
  }

  // HubSpot's form redirect builds its own query string and drops every utm_*,
  // so the site_attr cookie written by the attribution snippet is the only
  // surviving source. Read only — that snippet owns every write. (The snippet is
  // in the hubspot-stripe-utm-attribution repo; without it this step is skipped.)
  try {
    var m = document.cookie.match(new RegExp("(?:^|;\\s*)" + COOKIE + "=([^;]*)"));
    if (m) {
      var stash = JSON.parse(decodeURIComponent(m[1])) || {};
      Object.keys(stash).forEach(function (k) {
        if (k !== "_t" && stash[k]) u.searchParams.set(k, stash[k]);
      });
    }
  } catch (err) {}

  try {
    new URL(window.location.href).searchParams.forEach(function (value, key) {
      if (value && isTracking(key)) u.searchParams.set(key, value);
    });
  } catch (err) {}

  var target = u.toString();
  window.setTimeout(function () {
    window.location.replace(target);
  }, PIXEL_FLUSH_MS);
})();
