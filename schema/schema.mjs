/**
 * schema.mjs -- the two custom objects and the contact properties this guide uses
 * --------------------------------------------------------------------------------
 * Author:  Jibril Sulaiman
 * Created: 2026-10-01 (ET)
 * Deploy:  Read by scripts/create-schema.mjs, and the source of the property tables
 *          in README Steps 1-3. Edit labels here if you rename things.
 * What:    Free Class Configuration (one record per class topic: the "custom values"),
 *          Class Registrations (one record per person per class event), and the
 *          contact properties the workflows write.
 * Why:     Internal names are what the modules' HubL and the workflow tokens read.
 *          Keep them exactly; labels are free to change.
 */

const text = (name, label, extra = {}) => ({ name, label, type: 'string', fieldType: 'text', ...extra });
const area = (name, label) => ({ name, label, type: 'string', fieldType: 'textarea' });
const pick = (name, label, values) => ({
  name, label, type: 'enumeration', fieldType: 'select',
  options: values.map((v, i) => ({ label: v, value: v, displayOrder: i })),
});

// ---------- Free Class Configuration: the "custom values" ----------
export const CONFIG_OBJECT = {
  name: 'free_class_configurations',            // gives modules object_type "p_free_class_configurations"
  labels: { singular: 'Free Class Configuration', plural: 'Free Class Configurations' },
  primaryDisplayProperty: 'cohort_name',
  requiredProperties: ['cohort_name'],
  associatedObjects: ['CONTACT'],
  properties: [
    text('cohort_name', 'Cohort Name'),
    pick('class_type', 'Class Type', ['Topic A', 'Topic B']),             // one option per topic you run
    pick('cohort_status', 'Cohort Status', ['Planning', 'Active', 'Completed', 'Archived']),
    text('class_title', 'Class Title'),
    text('watch_now_youtube_link', '1. Watch Now YouTube Link'),
    text('next_day_restream_yt_link', '2. Next Day Restream YT Link'),
    area('replay_video_embed_code', '3. Replay Video Embed Code'),
    text('free_class_date', '4. Free Class Date'),                       // display string: "Sep 17th, 2026"
    text('old_free_class_date', '4a. Old Free Class Date'),              // display string of the class that aired
    text('day_of_class', '5. Day of Class'),                             // "Thursday"
    text('class_time', '6. Free Class Time'),                            // "7pm EST"
    { name: 'event_start_date_and_time', label: '7. Event Start Date and Time', type: 'datetime', fieldType: 'date' },
    { name: 'old_class_date', label: 'Old Class Date', type: 'date', fieldType: 'date' },
    text('add_event_id', 'Add Event ID'),
    text('registration_page_url', 'Registration Page URL'),
    text('preview_link', 'Preview Link'),
    text('offer_link', 'Offer Link'),
    text('upsell_url', 'Upsell URL'),
    text('offer_paywall_url', 'Offer Paywall URL'),
    text('fc_status_tag', 'FC Status Tag'),
    text('tag__free_class_registration', '9. Tag - Free Class Registration'),
    text('tag__free_class__attended', '9a. Tag - Free Class - Attended'),
    text('tag__free_class_replay', '9b. Tag - Free Class Replay'),
    text('tag__free_class__did_not_attend', '9c. Tag - Free Class - Did Not Attend'),
    text('slicktext_list_code__registration', 'SMS List Code - Registration'),     // optional: campaign values
    text('slicktext_list_code___attendees', 'SMS List Code - Attendees'),
    text('slicktext_list_code___watched_replay', 'SMS List Code - Watched Replay'),
    text('slicktext_list_code___did_not_attend', 'SMS List Code - Did Not Attend'),
  ],
};

// ---------- Class Registrations: one record per person per class event ----------
export const REGISTRATION_OBJECT = {
  name: 'class_registrations',
  labels: { singular: 'Class Registration', plural: 'Class Registrations' },
  primaryDisplayProperty: 'class_registration_name',
  requiredProperties: ['class_registration_name'],
  associatedObjects: ['CONTACT'],
  properties: [
    text('class_registration_name', 'Class Name/Topic'),
    pick('class_status', 'Class Status', ['Registered', 'Attended', 'Watched Replay']),
    pick('class_topic', 'Class Topic', ['Topic A', 'Topic B']),
    pick('free_class_type', 'Free Class Type', ['Topic A free class', 'Topic B free class']),
    { name: 'class_date', label: 'Class Date', type: 'date', fieldType: 'date' },
    text('free_class_date', 'Free Class Date'),
    text('fc_status_tag', 'FC Status Tag'),
    text('free_class_source', 'Free Class Source'),
    { name: 'registered_at', label: 'Registered At', type: 'datetime', fieldType: 'date' },
    { name: 'enrolled_date', label: 'Enrolled Date', type: 'date', fieldType: 'date' },
    text('email', 'Email'),
    text('phone_number', 'Phone number'),
    text('registration_reference', 'Registration Reference'),
    pick('reg_redirect', 'Reg Redirect', ['Yes', 'No']),
    { name: 'class_session', label: 'Class Session', type: 'enumeration', fieldType: 'select', options: [] },
    text('utm_source__f', 'UTM Source - F'), text('utm_source__l', 'UTM Source - L'),
    text('utm_medium__f', 'UTM Medium - F'), text('utm_medium__l', 'UTM Medium - L'),
    text('utm_campaign__f', 'UTM Campaign - F'), text('utm_campaign__l', 'UTM Campaign - L'),
  ],
};

// ---------- Contact properties the workflows and the router write ----------
export const CONTACT_PROPERTIES = [
  pick('fc_current_class_topic', 'FC Current Class Topic', ['Topic A', 'Topic B']),
  pick('reg_redirect', 'Reg Redirect', ['Yes', 'No']),
  pick('fc_registration_timing', 'FC Registration Timing', ['Pre-Class', 'Live']),
  text('class_reg_utm_source', 'Class Reg UTM Source'),
  text('class_reg_utm_medium', 'Class Reg UTM Medium'),
  text('class_reg_utm_campaign', 'Class Reg UTM Campaign'),
];

export const CONTACT_GROUP = { name: 'free_class', label: 'Free Class' };
