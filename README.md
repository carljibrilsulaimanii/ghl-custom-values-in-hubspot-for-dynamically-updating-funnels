<!--
  README.md -- GHL custom values in HubSpot for dynamically updating funnels
  Author:  Jibril Sulaiman
  Date:    2026-10-01
  What:    Build guide for a HubSpot custom object that does the job of GoHighLevel
           custom values: one record per event holds the date, time, links, embeds and
           tags, and every page module and workflow reads from it.
  Why:     HubSpot has no account-wide custom values. Without this, moving a webinar
           to a new date means editing every page, form redirect, workflow and email.
-->

# GHL custom values in HubSpot for dynamically updating funnels

**This duplicates GoHighLevel's dynamic funnel functionality.** In GoHighLevel, custom
values like `{{custom_values.free_class_date}}` update data across pages, workflows,
campaigns, emails, SMS and more from one place. Change the value once and the whole
funnel changes. HubSpot has no equivalent, so this repo builds one.

It uses a **configuration object**: a HubSpot custom object with one record per
recurring event (here, a free webinar "class" per topic). The record holds everything
that changes from one session to the next, such as the date, the time, the live and
replay links, the calendar event, the offer links and the tags. Then:

- **Pages** read it through seven custom modules with a **CRM object** field. These show
  the date, a countdown, a replay window, the replay video and an Add to Calendar
  button, and send live registrants to the stream.
- **Workflows** read it through a data source named **Active &lt;Topic&gt; Config**. The
  Registration, Attended and Replay workflows write one Class Registration record per
  person per event, stamped with that session's date and tags.
- **Moving to the next session** ("the flip") is one edit to one record. No page,
  form or workflow changes.

---

## Why it exists

### What GoHighLevel does

GoHighLevel keeps **custom values** in folders under *Settings > Custom values*. Each one
has a name, a key and a value, for example:

| Name | Key | Value |
|---|---|---|
| 4. Free Class Date | `{{custom_values.free_class_date}}` | `Jul 21st, 2026` |
| 6. Free Class Time | `{{custom_values.free_class_time}}` | `7pm EST` |
| 1. Free Class Watch Now Youtube Link | `{{custom_values.free_class_youtube_link}}` | the live link |
| 9b. Tag - Free Class Registration | `{{custom_values.free_class_registration_tag}}` | `… Free Class Registration [Jul 21st 2026]` |

The key works anywhere: page text, buttons, redirects, workflow actions, email and SMS
campaigns, tag names. A webinar funnel built this way runs every session from one
folder. Our folder held 39 values. Flipping to the next class meant editing that folder
and nothing else.

### What HubSpot doesn't have

- **No account-wide custom values.** Personalization tokens belong to the *visitor* or
  *contact*, not to the account. They can't hold "the next class date".
- **Dynamic pages are the wrong shape.** HubSpot can bind a page to a custom object as a
  *dynamic page*, but that makes one page per record. A funnel needs the same page
  (registration, watch, replay) to show whichever session is current. We tried this
  first and moved off it. `dynamic_page_crm_object` also comes back empty on ordinary
  landing pages. The **CRM object** module field (not *CRM object property*) is what
  works.
- **Workflows can't read a value that isn't on the enrolled record**, unless you add a
  data source. The newer *"If a property value is equal to"* data source (marked
  **BETA** in the UI) is what makes this work: it finds a record anywhere in the CRM by
  property value.
- **Forms can't write to a custom object.** A form submission only updates the contact,
  so a workflow has to create the registration record.

### What this repo does instead

| GoHighLevel | HubSpot equivalent here |
|---|---|
| Custom values folder | One **Free Class Configuration** record per topic |
| `{{custom_values.x}}` on a page | A custom module with a **CRM object** field reading `module.crmobject_field.properties.x` |
| `{{custom_values.x}}` in a workflow | A workflow data source **Active &lt;Topic&gt; Config** (*Class Type is equal to &lt;Topic&gt;*), then its tokens |
| A tag per session | A tag string stored on the record (`9. Tag - Free Class Registration`), written into each registration |
| Contact-level registration history | A **Class Registrations** custom object: one record per person per session, with status *Registered*, *Attended* or *Watched Replay* |

### What we tried first

The first version copied the custom values onto **every registration record**:
*1. Free Class Watch Now Youtube Link*, *4. Free Class Date*, *7. Free Class GHL Event
Start Date/Time*, *9. Tag - Free Class Registration* and so on, 19 properties in all,
some duplicated as *- 2*, one set per GHL folder. That repeats the same value on
thousands of records, with nothing that holds the "current" value, and a third topic
would have meant a *- 3* copy of everything. It lasted one day. All 19 were archived
the same night the configuration object went live.

The design approved next was **a new record per class run**: clone last session's
record, update it, set *Cohort Status* to *Active*, keep exactly one Active record per
topic. A separate "linker" automation (custom code or Zapier) would find the Active
record and copy its values onto each new registration.

What shipped is simpler, for two reasons:

- **Workflows can look the record up themselves.** The *"If a property value is equal
  to"* data source finds the record by property value inside the workflow, so no
  linker was needed. No code, no Zapier.
- **History lives on the registrations anyway.** Each Class Registration copies the
  session's date and tag at the moment it's created, so editing one record per topic
  in place loses nothing. Per-session reports group the registrations, not the
  configuration records.

So the final model is **one configuration record per topic, edited in place at every
flip**. Never clone a second record for the same topic (Step 4, Step 13).

**What changed in production:** a flip became one record edit, followed by a
cache-busted look at each page (Step 13). Pages, forms and workflows stay untouched
from one session to the next. They only change when you add a topic (Step 14).

---

## How it works

```
                 Free Class Configuration  (one record per topic)
                 Cohort Name · Class Type · 4. Free Class Date · 6. Free Class Time
                 7. Event Start Date and Time · 4a / Old Class Date (last aired)
                 1. Watch Now link · 3. Replay embed · Add Event ID · 9.x tags · URLs
                          │                                   │
        CRM object field  │                                   │  data source "Active <Topic> Config"
                          ▼                                   ▼
  PAGES                                              WORKFLOWS (contact-based, form triggered)
  Registration page                                  Registration form ─► 2. Registration workflow
    Free Class Date & Time  "Sep 17th, 2026 @ 7pm"     └─ Create record: Class Registration  (Registered)
    Redirect Reg Form  ─ late? go to live stream       └─ Late check (code) ─► submit Attended form
  Watch page                                         Attended form ─────► 4. Attended workflow
    Watch Page Counter  countdown, flips at 7pm        └─ Create record: Class Registration  (Attended)
    Free Class Calendar Button  AddEvent link        Replay form ───────► 5. Replay workflow
  Replay page                                          └─ Create record: Class Registration  (Watched Replay)
    Replay Countdown  open 72h after the class
    Free Class Replay Video  the embed               Class Registration created ─► Class Session label (code)
```

The "upcoming" date pair (`4. Free Class Date` + `7. Event Start Date and Time`) drives
registration and attendance. The "last aired" pair (`4a. Old Free Class Date` +
`Old Class Date`) drives the replay. That way a replay watched after you've already
flipped to next month is still credited to the session the person actually watched.

---

## What's in this repo

| Path | What it is | Where it goes |
|---|---|---|
| [`schema/schema.mjs`](schema/schema.mjs) | Every property on both objects and the contact properties, with exact internal names | Read by the script; the tables in Steps 1-3 |
| [`scripts/create-schema.mjs`](scripts/create-schema.mjs) | Creates both objects and all properties through the API (dry run by default) | Your computer (Step 1, Route B) |
| [`modules/free-class-date.module/`](modules/free-class-date.module/) | "Dates: Sep 17th, 2026" | Design Manager (Step 5) |
| [`modules/free-class-date-and-time.module/`](modules/free-class-date-and-time.module/) | "Sep 17th, 2026 @ 7pm EST" | Design Manager |
| [`modules/free-class-calendar-button.module/`](modules/free-class-calendar-button.module/) | Add To Calendar button from the record's AddEvent id | Design Manager |
| [`modules/free-class-replay-video.module/`](modules/free-class-replay-video.module/) | The record's replay embed, responsive | Design Manager |
| [`modules/watch-page-counter.module/`](modules/watch-page-counter.module/) | Countdown to the class start; hides/shows page parts at zero | Design Manager |
| [`modules/replay-countdown.module/`](modules/replay-countdown.module/) | Countdown to the end of the 72-hour replay window; redirects when it closes | Design Manager |
| [`modules/redirect-reg-form.module/`](modules/redirect-reg-form.module/) | Sends late registrants to the live stream instead of the confirmation page | Design Manager |
| [`workflow-actions/late-registration-check.js`](workflow-actions/late-registration-check.js) | Custom code: did this person register after the class started? | Registration workflow (Step 8) |
| [`workflow-actions/submit-attended-form.js`](workflow-actions/submit-attended-form.js) | Custom code: marks late registrants as attended | Registration workflow (Step 8) |
| [`workflow-actions/class-session-label.js`](workflow-actions/class-session-label.js) | Custom code: one "2026-09-17 - Topic" dropdown value per session, for reports | Class Session workflow (Step 11) |
| [`test/`](test/) | 23 tests: the three actions run unchanged, plus a check that every module only reads properties the schema defines | `npm test` |

---

## Table of contents

1. [Requirements](#1-requirements)
2. [Setup, step by step](#2-setup-step-by-step)
   - [Step 1: Create the Free Class Configuration object](#step-1-create-the-free-class-configuration-object)
   - [Step 2: Create the Class Registrations object](#step-2-create-the-class-registrations-object)
   - [Step 3: Create the contact properties](#step-3-create-the-contact-properties)
   - [Step 4: Create one configuration record per topic](#step-4-create-one-configuration-record-per-topic)
   - [Step 5: Build the seven modules in Design Manager](#step-5-build-the-seven-modules-in-design-manager)
   - [Step 6: Put the modules on your pages](#step-6-put-the-modules-on-your-pages)
   - [Step 7: Set up the forms](#step-7-set-up-the-forms)
   - [Step 8: Build the Registration workflow](#step-8-build-the-registration-workflow)
   - [Step 9: Build the Attended workflow](#step-9-build-the-attended-workflow)
   - [Step 10: Build the Replay workflow](#step-10-build-the-replay-workflow)
   - [Step 11: Label each session for reporting](#step-11-label-each-session-for-reporting)
   - [Step 12: Test one full session](#step-12-test-one-full-session)
   - [Step 13: Flip to the next session](#step-13-flip-to-the-next-session)
   - [Step 14: Add a new topic](#step-14-add-a-new-topic)
3. [Create record mappings, side by side](#3-create-record-mappings-side-by-side)
4. [Troubleshooting](#4-troubleshooting)
5. [Limits](#5-limits)
6. [Testing](#6-testing)
7. [Security](#7-security)

---

## 1. Requirements

| You need | Why |
|---|---|
| HubSpot **Enterprise** on any hub (Marketing, Sales, Service, Content or Data) | Custom objects are Enterprise-only. |
| **Content Hub Professional** or above, or Marketing Hub Professional with landing pages | Custom modules in Design Manager, and the **CRM object** module field. |
| **Data Hub Professional** (formerly Operations Hub) or above | **Custom code** workflow actions (Steps 8 and 11). Without it, skip the late-registration path and the session label; the rest still works. |
| Workflows with the **"If a property value is equal to"** data source | The *Active &lt;Topic&gt; Config* source. It was marked **BETA** when this was built. |
| Super Admin, or permission to create objects, properties, workflows and modules | Every step |
| Optional: Node.js 20+ | Only for the schema script (Step 1, Route B) and `npm test` |

---

## 2. Setup, step by step

Do the steps in order. Each ends with a ✅ **Check**; don't go on until it passes. Most
failures in this build are silent: a token that points at the wrong record, a selector
that matches nothing, a branch that copied another topic's values. The checks are the
only place you'll see them.

> **About the labels:** names in **bold** or *"quotes"* were checked against
> screenshots of HubSpot from August and September 2026. HubSpot moves these menus
> often (object settings moved from *Settings > Objects* into the *Data Model Builder*
> during this build). Where a screen wasn't captured, the step says *(wording may
> differ)*.

> **Naming used in this guide:** the event is a "free class", run on several *topics*.
> Each topic has one configuration record. Replace "Topic A" with your own topics.
> Property **labels** can be anything; **internal names** must match this guide,
> because the modules and actions read them.

### Step 1: Create the Free Class Configuration object

About 30 minutes by hand, or 2 minutes with the script.

**Route A, by hand:**

**1a.** Go to **Settings** (gear icon) **> Data Management > Objects** and click
**Create Object** (an older UI labels it **Create Custom Object**). If HubSpot opens the
**Data Model Builder** instead, use **Create object** there.

**1b.** On the object details screen. We used the wizard's **Create with AI** option,
which opens a *"Review AI recommended object"* panel ("Always check AI-generated content
for inaccuracies before saving.") with the AI's suggested names and properties. You can
type the values yourself instead. Either way, end up with:

| Field | Value |
|---|---|
| **Object name (Singular) \*** | `Free Class Configuration` |
| **Object name (Plural) \*** | `Free Class Configurations` |
| **Internal name** | `free_class_configurations`. **Exactly this.** The modules point at `p_free_class_configurations`. |
| **Primary display property** | `Cohort Name`, *Single-line text* |
| **Associations** | **Contacts** |

> 💡 **Number the labels the way your GHL custom values were numbered.** We
> relabelled the properties *1. Watch Now YouTube Link* … *7. Event Start Date and
> Time*, *9. Tag - …*, matching the old custom-value names, so everyone who ran the
> GHL funnel could find "number 4, the date" straight away. Labels can change any
> time; internal names can't.

> 💡 **Don't copy the custom values onto the registration object.** That was our first
> attempt (see *What we tried first*). The values belong on one configuration record.
> Registrations only keep what was true for that person: the date and the tag at the
> moment they registered.

**1c.** Open the object's **Properties** (**Manage Free Class Configuration properties**)
and click **Create property** for each row below. For each one fill **Property label \***,
check that **Internal name** matches the table, pick the **Field type**, and choose a
**Group \***. We made three groups so the record reads like the old custom-values
folder: *Cohort Setup* (name, type, status, dates, time, title, calendar),
*Cohort Links* (every URL and the embed) and *Cohort SMS* (the list codes). Groups
only organize the sidebar; they don't change behavior.

| Label | Internal name | Field type | Holds |
|---|---|---|---|
| Cohort Name | `cohort_name` | Single-line text | The topic's display name, e.g. `Topic A`. Shown in the module picker. |
| Class Type | `class_type` | Dropdown select | **One option per topic.** The workflows find the record by this value. |
| Cohort Status | `cohort_status` | Dropdown select | `Planning`, `Active`, `Completed`, `Archived` |
| Class Title | `class_title` | Single-line text | The public title of the class |
| 1. Watch Now YouTube Link | `watch_now_youtube_link` | Single-line text | The live stream link |
| 2. Next Day Restream YT Link | `next_day_restream_yt_link` | Single-line text | Optional encore stream |
| 3. Replay Video Embed Code | `replay_video_embed_code` | Multi-line text | The full `<iframe>` embed for the replay |
| 4. Free Class Date | `free_class_date` | Single-line text | **Display** date of the upcoming session: `Sep 17th, 2026` |
| 4a. Old Free Class Date | `old_free_class_date` | Single-line text | **Display** date of the session that last aired |
| 5. Day of Class | `day_of_class` | Single-line text | `Thursday` |
| 6. Free Class Time | `class_time` | Single-line text | `7pm EST`. The Replay Countdown reads the hour from this. |
| 7. Event Start Date and Time | `event_start_date_and_time` | **Date and time picker** | The real start moment. Countdowns and the late check use it. |
| Old Class Date | `old_class_date` | **Date picker** | The real date of the session that last aired. The replay uses it. |
| Add Event ID | `add_event_id` | Single-line text | Your AddEvent event id |
| Registration Page URL | `registration_page_url` | Single-line text | Where the replay page sends people once the replay closes |
| Preview Link / Offer Link / Upsell URL / Offer Paywall URL | `preview_link`, `offer_link`, `upsell_url`, `offer_paywall_url` | Single-line text | Funnel links that change per session |
| FC Status Tag | `fc_status_tag` | Single-line text | Optional status label |
| 9. Tag - Free Class Registration | `tag__free_class_registration` | Single-line text | `Topic A Free Class Registration [Sep 17th 2026]` |
| 9a. Tag - Free Class - Attended | `tag__free_class__attended` | Single-line text | `Topic A Free Class Attendees [Sep 17th 2026]` |
| 9b. Tag - Free Class Replay | `tag__free_class_replay` | Single-line text | `Topic A Free Class Watched Replay [Sep 17th 2026]` |
| 9c. Tag - Free Class - Did Not Attend | `tag__free_class__did_not_attend` | Single-line text | `Topic A Free Class Did Not Attend [Sep 17th 2026]` |
| SMS List Code - Registration / Attendees / Watched Replay / Did Not Attend | `slicktext_list_code__registration`, `slicktext_list_code___attendees`, `slicktext_list_code___watched_replay`, `slicktext_list_code___did_not_attend` | Single-line text | Optional: per-session list codes for an SMS tool, so SMS campaigns follow the record too |

> ⚠️ **Each date exists twice on purpose.** The *display* strings (`4.`, `4a.`, `5.`,
> `6.`) are text, so pages show them exactly as typed, ordinal and comma included.
> Nothing validates them. The real dates (`7.` and `Old Class Date`) are what code and
> workflows do arithmetic on. If you fill only the string, the countdown is blank and
> the registration record gets an empty **Class Date**. Always fill both halves of a
> pair, and make them agree.

> ⚠️ **`Old Class Date` is a date, not a date-time.** HubSpot stores it as midnight
> UTC. For a 7pm Eastern class that's ~19 hours before the class. The Replay Countdown
> corrects for this by reading the hour from `6. Free Class Time`. Anything else you
> build on it must do the same.

**Route B, with the script** (creates exactly the same thing):

1. Create a service key: **Settings > Integrations > Service Keys** *(wording may
   differ)* **> Create service key**. Give it the scopes `crm.schemas.custom.read`,
   `crm.schemas.custom.write`, `crm.schemas.contacts.write` and `crm.objects.contacts.read`.
2. Edit [`schema/schema.mjs`](schema/schema.mjs): replace the `Topic A` / `Topic B` options in `class_type`,
   `class_topic`, `free_class_type` and `fc_current_class_topic` with your topics.
3. Dry run, then apply (PowerShell):

```powershell
$env:HUBSPOT_TOKEN = "<your service key>"
node scripts/create-schema.mjs
node scripts/create-schema.mjs --apply
```

Runs [`scripts/create-schema.mjs`](scripts/create-schema.mjs).

The dry run prints `would create object Free Class Configuration with 28 properties` and
the same for Class Registrations. After `--apply` it prints each object's **object type
id** (`2-12345678`). Write both down: Step 11 needs the Class Registrations one.

✅ **Check:** **Settings > Data Management > Objects** lists *Free Class Configurations*,
and its property list shows every internal name above. Click one or two and confirm the
internal name, since that's the part you can't change later.

### Step 2: Create the Class Registrations object

About 25 minutes by hand (skip if you used the script).

**2a.** **Create Object** again: **Singular** `Class Registration`, **Plural**
`Class Registrations`, internal name `class_registrations`, primary display property
`Class Name/Topic` (Single-line text, internal `class_registration_name`), associated to
**Contacts**.

**2b.** Add these properties:

| Label | Internal name | Field type | Options / notes |
|---|---|---|---|
| Class Name/Topic | `class_registration_name` | Single-line text | Built by the workflow: `First Last - <tag>` |
| Class Status | `class_status` | Dropdown select | `Registered`, `Attended`, `Watched Replay` |
| Class Topic | `class_topic` | Dropdown select | One option per topic |
| Free Class Type | `free_class_type` | Dropdown select | One option per topic, e.g. `Topic A free class` |
| Class Date | `class_date` | Date picker | From the config's real date |
| Free Class Date | `free_class_date` | Single-line text | From the config's display date |
| FC Status Tag | `fc_status_tag` | Single-line text | The session tag |
| Free Class Source | `free_class_source` | Single-line text | The contact's latest traffic source |
| Registered At | `registered_at` | Date and time picker | The form submission time |
| Enrolled Date | `enrolled_date` | Date picker | The day the workflow ran |
| Email | `email` | Single-line text | **Always map it.** Matching and dedupe depend on it. |
| Phone number | `phone_number` | Single-line text | |
| Registration Reference | `registration_reference` | Single-line text | Dedupe key: `email-<tag>` |
| Reg Redirect | `reg_redirect` | Dropdown select | `Yes`, `No` |
| Class Session | `class_session` | Dropdown select | **No options.** Step 11 adds them automatically. |
| UTM Source/Medium/Campaign - F and - L | `utm_source__f`, `utm_source__l`, `utm_medium__f`, `utm_medium__l`, `utm_campaign__f`, `utm_campaign__l` | Single-line text | **F** = the touch that registered them, **L** = the latest touch |

**2c.** In the Free Class Configuration object's **Associations** tab, add an
association to **Class Registrations** (**+ Create association**, *1-to-many*).
Optional, but it lets you open a topic and see its registrations.

✅ **Check:** a test **Class Registration** created by hand shows all the fields above
in its sidebar, and **Associations** on it offers *Contacts*.

### Step 3: Create the contact properties

About 10 minutes (skip if you used the script).

**Settings > Properties > Contact properties > Create property**:

| Label | Internal name | Field type | Options | Written by |
|---|---|---|---|---|
| FC Current Class Topic | `fc_current_class_topic` | Dropdown select | One per topic | Registration workflow |
| Reg Redirect | `reg_redirect` | Dropdown select | `Yes`, `No` | Registration workflow; the Attended form |
| FC Registration Timing | `fc_registration_timing` | Dropdown select | `Pre-Class`, `Live` | The Redirect Reg Form module, via a hidden form field |
| Class Reg UTM Source / Medium / Campaign | `class_reg_utm_source`, `class_reg_utm_medium`, `class_reg_utm_campaign` | Single-line text | | Registration workflow: a snapshot of the UTMs at registration |

> ⚠️ **Snapshot the UTMs at registration.** The contact's own `utm_*` properties change
> every time they come back through a different link. By attendance night they describe
> the reminder email, not the ad that registered them. The Registration workflow copies
> them into `class_reg_utm_*`, and the Attended workflow reads the copies for **- F**.

✅ **Check:** all six properties appear under **Contact properties** with the internal
names above.

### Step 4: Create one configuration record per topic

About 10 minutes per topic.

**4a.** Open **Contacts > Free Class Configurations** (or the object switcher on any
index) and click **Add free class configurations > Create**.

**4b.** Fill every property from Step 1. For the first session of a topic:

| Property | Example | Rule |
|---|---|---|
| Cohort Name | `Topic A` | Shown in every module picker. Keep it short. |
| Class Type | `Topic A` | Must be the option the workflows filter on |
| Cohort Status | `Active` | |
| 4. Free Class Date | `Sep 17th, 2026` | Pick one format and keep it, character for character |
| 5. Day of Class / 6. Free Class Time | `Thursday` / `7pm EST` | |
| 7. Event Start Date and Time | `09/17/2026 7:00 PM` (your time zone) | The same moment as 4 + 6 |
| 4a. Old Free Class Date / Old Class Date | *(blank)* | Filled the night the first session airs (Step 13) |
| 1. Watch Now YouTube Link | the live link | |
| 3. Replay Video Embed Code | the `<iframe>` embed | Can be added after the class |
| Add Event ID | your AddEvent id | |
| Registration Page URL | `https://www.example.com/topic-a/register` | Full URL |
| 9. / 9a. / 9b. / 9c. tags | `Topic A Free Class Registration [Sep 17th 2026]` … | Same prefix and date in all four |

> ⚠️ **A new record can arrive pre-filled with another topic's values.** In
> production, both *Create* and *Clone* produced records already carrying the previous
> topic's Class Type, dates, title, status tag, all four tags, the restream link and the
> replay embed. Usually only Cohort Name was right. Nothing downstream complains about a
> stale tag or date. Treat every property as wrong until you've set it, and clear any
> that don't apply. Don't just leave them.

> ⚠️ **Tag strings must be identical every time.** Reports and lists match tags as
> text. `[Sep 8th 2026]`, `[Sep 8 2026]` and a double space before the bracket are three
> different tags. Copy the pattern from the previous session and change only the date.

✅ **Check:** the record's sidebar shows *7. Event Start Date and Time* in your time
zone at the right hour, and *4. Free Class Date* reads exactly how you want it on the
page.

### Step 5: Build the seven modules in Design Manager

About 10 minutes per module (the small ones take 3).

Every module has one **CRM object** field, named `crmobject_field` (`class_config` in
Redirect Reg Form), pointed at Free Class Configuration. The editor picks a record once,
and every value in the module comes from it.

**5a. How every module is built** (do this once per module, in 5b-5h):

1. Go to **Marketing > Files and Templates > Design Tools** (Design Manager). Click
   **File > New file**, choose **Module**, tick **Landing pages** and **Site pages**
   under *"Where would you like to use this module?"*, choose **Local module**, set
   **File name**, and click **Create**.
2. **Add the CRM object field.** In the right sidebar click **Add field**, type `cr`,
   and pick **CRM object** under *Selectors*:

   | Setting | Value |
   |---|---|
   | **HubL variable name** | as given in the module's step |
   | **CRM object type** | `Free Class Configuration` |
   | **Properties to fetch** | as given in the module's step. **A property that isn't listed here comes back empty**, even if the HubL asks for it. |
   | **Properties for choice label** | `Class Type` (optionally the date as well). Without it the picker lists raw values, such as AddEvent ids or epoch numbers. |
   | **Format of choice label** | `%0` (or `%0 %1` with the date) |
   | **Default CRM object instance** | leave empty |

3. **Add the other fields** the module's step lists, with the **HubL variable name**
   exactly as given. Instead of clicking them in, you can open **Actions > Edit JSON**
   *(wording may differ)* on the fields list and paste the module's whole
   `fields.json`.
4. **Paste the code.** In each pane, select all, delete the sample code, and paste in
   **all** of the file the module's step links for that pane.
5. Turn on **Make available in templates and pages** and click **Publish changes**.
   To preview, temporarily pick a record in **Default CRM object instance**, then
   clear it again before publishing.

**5b. Free Class Date.** Prints `Dates: Sep 17th, 2026`.

1. **File > New file > Module**, File name `Free Class Date`, as in 5a.
2. **Add field > CRM object**: HubL variable name `crmobject_field`, CRM object type *Free Class Configuration*, **Properties to fetch**: *4. Free Class Date*.
3. Delete the sample code and paste: **module.html (HTML + HubL)** ← all of [`module.html`](modules/free-class-date.module/module.html). Leave **module.css** and **module.js** empty.
4. Check the fields against [`fields.json`](modules/free-class-date.module/fields.json) (or paste it with **Edit JSON**, 5a), then **Publish changes**.

✅ **Check:** pick a record and the preview shows `Dates:` and its 4. Free Class Date.

**5c. Free Class Date & Time.** Prints `Sep 17th, 2026 @ 7pm EST`.

1. **File > New file > Module**, File name `Free Class Date & Time`, as in 5a.
2. **Add field > CRM object**: HubL variable name `crmobject_field`, CRM object type *Free Class Configuration*, **Properties to fetch**: *6. Free Class Time*, *4. Free Class Date*.
3. Delete the sample code and paste: **module.html (HTML + HubL)** ← all of [`module.html`](modules/free-class-date-and-time.module/module.html). Leave **module.css** and **module.js** empty.
4. Check the fields against [`fields.json`](modules/free-class-date-and-time.module/fields.json) (or paste it with **Edit JSON**, 5a), then **Publish changes**.

✅ **Check:** the preview shows the record's date, `@`, and its time.

**5d. Free Class Calendar Button.** An *Add To Calendar* button that opens `addevent.com/event/<Add Event ID>`.

1. **File > New file > Module**, File name `Free Class Calendar Button`, as in 5a.
2. **Add field > CRM object**: HubL variable name `crmobject_field`, CRM object type *Free Class Configuration*, **Properties to fetch**: *Add Event ID*.
3. Delete the sample code and paste: **module.html (HTML + HubL)** ← all of [`module.html`](modules/free-class-calendar-button.module/module.html); **module.css** ← all of [`module.css`](modules/free-class-calendar-button.module/module.css). Leave **module.js** empty.
4. Check the fields against [`fields.json`](modules/free-class-calendar-button.module/fields.json) (or paste it with **Edit JSON**, 5a), then **Publish changes**.

✅ **Check:** the preview shows the button, and its link ends in the record's Add Event ID.

**5e. Free Class Replay Video.** Renders the record's replay embed at 16:9.

1. **File > New file > Module**, File name `Free Class Replay Video`, as in 5a.
2. **Add field > CRM object**: HubL variable name `crmobject_field`, CRM object type *Free Class Configuration*, **Properties to fetch**: *3. Replay Video Embed Code*.
3. Delete the sample code and paste: **module.html (HTML + HubL)** ← all of [`module.html`](modules/free-class-replay-video.module/module.html); **module.css** ← all of [`module.css`](modules/free-class-replay-video.module/module.css). Leave **module.js** empty.
4. Check the fields against [`fields.json`](modules/free-class-replay-video.module/fields.json) (or paste it with **Edit JSON**, 5a), then **Publish changes**.

✅ **Check:** the preview shows the video player from the record's embed code.

**5f. Watch Page Counter.** Days / Hours / Minutes / Seconds to the class start; at zero it hides and reveals page parts (wired in Step 6).

1. **File > New file > Module**, File name `Watch Page Counter`, as in 5a.
2. **Add field > CRM object**: HubL variable name `crmobject_field`, CRM object type *Free Class Configuration*, **Properties to fetch**: *7. Event Start Date and Time*.
3. Add these fields (**Add field**, then set the label and HubL variable name exactly):

   | Type | Label | HubL variable name | Default |
   |---|---|---|---|
   | Text | Selector - Hide While Active / Unhide at 0 | `form_selector` | empty |
   | Text | Selector - Unhide While Active / Hide at 0 | `hide_selector` | empty |
   | Number | Offset minutes | `offset_minutes` | empty |

4. Delete the sample code and paste: **module.html (HTML + HubL)** ← all of [`module.html`](modules/watch-page-counter.module/module.html); **module.css** ← all of [`module.css`](modules/watch-page-counter.module/module.css). Leave **module.js** empty.
5. Check the fields against [`fields.json`](modules/watch-page-counter.module/fields.json) (or paste it with **Edit JSON**, 5a), then **Publish changes**.

✅ **Check:** the preview shows the four-unit clock counting down to the record's 7. Event Start Date and Time.

**5g. Replay Countdown.** Time left in the 72-hour replay window after Old Class Date + class time; at zero it closes the replay and redirects to Registration Page URL. 

1. Create it as in 5a with File name `Replay Countdown`, or clone **Watch Page Counter** (right-click it in the file tree, **Clone** *(wording may differ)*) and rename the clone. Either way, the fields and code below replace everything in it.
2. **Add field > CRM object**: HubL variable name `crmobject_field`, CRM object type *Free Class Configuration*, **Properties to fetch**: *Old Class Date*, *6. Free Class Time*, *7. Event Start Date and Time*, *Registration Page URL*.
3. Add these fields (**Add field**, then set the label and HubL variable name exactly):

   | Type | Label | HubL variable name | Default |
   |---|---|---|---|
   | Text | Selector - Hide While Active / Unhide at 0 | `form_selector` | empty |
   | Text | Selector - Unhide While Active / Hide at 0 | `hide_selector` | empty |
   | Number | Offset minutes | `offset_minutes` | empty |
   | Boolean | Ignore countdown - keep replay open | `force_open` | `false` |
   | Text | Selector - Hide when toggle is on | `forced_hide_selector` | empty |

4. Delete the sample code and paste: **module.html (HTML + HubL)** ← all of [`module.html`](modules/replay-countdown.module/module.html); **module.css** ← all of [`module.css`](modules/replay-countdown.module/module.css). Leave **module.js** empty.
5. Check the fields against [`fields.json`](modules/replay-countdown.module/fields.json) (or paste it with **Edit JSON**, 5a), then **Publish changes**.

✅ **Check:** the preview shows a clock counting down to 72 hours after the record's Old Class Date at its class time.

**5h. Redirect Reg Form.** Shows nothing on the page. After the class has started it sends a registrant straight to the live link instead of `confirmation_url`.

1. **File > New file > Module**, File name `Redirect Reg Form`, as in 5a.
2. **Add field > CRM object**: HubL variable name `class_config`, CRM object type *Free Class Configuration*, **Properties to fetch**: *7. Event Start Date and Time*, *1. Watch Now YouTube Link*.
3. Add these fields (**Add field**, then set the label and HubL variable name exactly):

   | Type | Label | HubL variable name | Default |
   |---|---|---|---|
   | Text | Button Label | `button_label` | `continue to payment` |
   | Text | confirmation_url | `confirmation_url` | empty |
   | Number | start_seconds | `start_seconds` | `180` |
   | Number | offset_minutes | `offset_minutes` | empty |
   | Text | form_guid | `form_guid` | empty |

4. Delete the sample code and paste: **module.html (HTML + HubL)** ← all of [`module.html`](modules/redirect-reg-form.module/module.html); **module.css** ← all of [`module.css`](modules/redirect-reg-form.module/module.css); **module.js** ← all of [`module.js`](modules/redirect-reg-form.module/module.js).
5. Check the fields against [`fields.json`](modules/redirect-reg-form.module/fields.json) (or paste it with **Edit JSON**, 5a), then **Publish changes**.

✅ **Check:** with a record picked the preview is blank; with no record it shows *"Free Class Live Router is not configured."*

> ⚠️ **After you add a property to *Properties to fetch*, re-select the record** in
> every page that already uses the module. Pages keep the old fetch list until you do.

> ⚠️ **Tick *Landing pages* in the module's content types.** A module created for
> *Site pages* only doesn't appear in the landing-page editor's module list.

> ⚠️ **"Properties to fetch" is the trap that cost the most time.** The Replay
> Countdown first fetched only `event_start_date_and_time`, so `old_class_date` came
> back empty and the clock never rendered. The editor shows *"Replay Countdown is not
> rendering: pick a CRM object that has an Old Class Date value"* even when the record
> does have one. Check the fetch list before checking the record.

> ⚠️ **The Free Class modules reference `extra_classes`, `separator` and `link_text`**,
> but none of them ship those fields. They fall back to defaults (`@`, *Add To
> Calendar*). Add a text field with that name if you want to set them per page.

✅ **Check:** the module's preview in Design Manager shows a placeholder, and after you
pick a record in the field's **Default CRM object instance** (temporarily) it shows the
record's date. Clear the default again before publishing.

### Step 6: Put the modules on your pages

About 5 minutes per page.

**6a.** Open the page in the page editor, drag the module in, and in the left sidebar
pick the record in **CRM object** (it lists *Select a free class configuration*, then
one row per record, e.g. *Topic A Sep 17th, 2026*).

**6b.** Typical placement:

| Page | Modules |
|---|---|
| Registration (opt-in) | Free Class Date & Time; Redirect Reg Form (set **confirmation_url** to your confirmation page's full URL, **form_guid** to the registration form) |
| Confirmation | Free Class Date & Time; Free Class Calendar Button |
| Watch / live | Watch Page Counter; Free Class Date & Time |
| Replay sign-in | Replay Countdown; Free Class Replay Video |

**6c.** Wire the countdown selectors. Both countdowns take HubSpot element ids, comma
separated, pasted exactly as HubSpot prints them (no `#` needed):

| Field | On the watch page | On the replay page |
|---|---|---|
| **Selector - Unhide While Active / Hide at 0** (`hide_selector`) | The waiting copy (*"Join Link Available In:"*) | The replay form |
| **Selector - Hide While Active / Unhide at 0** (`form_selector`) | The join form or button | The *"replay has ended"* copy |

To find an id, right-click the element in the published page, choose **Inspect**, and
copy the `id` of the nearest `hs_cos_wrapper_widget_…` (a module) or
`hs_form_target_widget_…` (a form) element.

> ⚠️ **HubSpot ids pasted straight into CSS match nothing.** An earlier version of the
> countdown wrote the fields into CSS as typed, so `hs_cos_wrapper_widget_123` became a
> *type* selector (an element named `hs_cos_wrapper_widget_123`) and the form never hid.
> These modules add the `#` for you, so paste the bare id.

> ⚠️ **Many templates duplicate the whole hero for mobile.** If the page has separate
> desktop and mobile sections, every module and form exists twice with different ids.
> List **both** ids in each selector field, and put a countdown in each section. A reveal
> can't cross sections: the hidden section's `display:none` wins.

> ⚠️ **To hide a form's fields but keep its card**, use
> `#hs_form_target_widget_<id> .hsfc-Step` rather than the `…-100` id. The numeric
> suffixes inside a form can change when the form is edited.

**6d. Offset minutes is how early the page flips.** On the watch page, `60` opens the
join link an hour before the start. On the replay page leave it at `0`. A blank field
counts as `0`, so clearing it by accident silently moves the flip by the whole offset.

> ⚠️ **The two selector fields read alike and do opposite things.** Putting the form
> in *Unhide While Active / Hide at 0* instead of *Hide While Active / Unhide at 0*
> inverts the page: the join form shows during the countdown and vanishes at the start.
> Check by the field's wording, not its position.

**6e.** For **Replay Countdown**, set **Ignore countdown - keep replay open** on every
instance if you want the replay open indefinitely (for example, an evergreen replay).

✅ **Check:** preview the page and see the record's date. For the countdowns, open the
published page once with `?v=1` added (to skip the CDN cache). Then temporarily set
**Offset minutes** to a large number so the clock hits zero, confirm the right parts hide
and show, and set it back to `0`.

### Step 7: Set up the forms

About 10 minutes per topic.

You need three forms per topic, all writing to the contact:

| Form | Example name | Hidden fields | Used by |
|---|---|---|---|
| Registration | `Topic A Free Class Registration - Popup` | `fc_registration_timing` (hidden; the module fills it) | Step 8 trigger |
| Attended | `Topic A Attended Form (Watch Now Page)` | `reg_redirect` (hidden, default `No`) | Step 9 trigger; Step 8 submits it for late registrants |
| Replay | `Topic A Replay Form` | none | Step 10 trigger |

> ⚠️ **The hidden field must be on the form *and* published.** If `Reg Redirect` is
> missing from the Attended form, or the form has unpublished changes, HubSpot accepts
> the late-registration submission, returns 200, and silently drops the value. The log
> looks clean and the contact stays `No`.

> ⚠️ **Keep the three kinds of form apart.** In production a registration popup was
> added to the Attended workflow's trigger list, so everyone who registered was also
> recorded as having attended. Name forms so their kind is obvious, and check every
> trigger list against this table.

> ⚠️ **If your registration form opens in a pop-up CTA that renders in an iframe**,
> the Redirect Reg Form module can't reach it: page scripts can't fill hidden fields or
> catch submissions inside the iframe. That's why the late-registration decision also
> lives server-side in the Registration workflow (Step 8i). Use an inline form, or rely
> on Step 8i alone.

Copy each form's GUID from its editor URL (`app.hubspot.com/forms/<portal>/editor/<GUID>`).
Step 8 needs the Attended forms' GUIDs.

✅ **Check:** a test submission of each form shows the hidden field's value on the
contact.

### Step 8: Build the Registration workflow

About 45 minutes for the first topic, 15 for each one after.

#### Before you start: how data tokens work in these workflows

Steps 8-11 fill fields with **data tokens**: values that HubSpot fills in for each
enrollment, like a GHL custom value. You'll do this dozens of times, so here's the
whole interaction once.

**Insert a token into a field.** Click into the field (for example *Class Name/Topic*
in a Create record action). The **All data tokens** panel opens beside the action.

| Panel section | What's in it | Use it for |
|---|---|---|
| **Search all data** (top) + **Filter by data source(s)** | Searches every source at once, e.g. type `source` | Finding a property when you know its name |
| **Popular** | Email, First Name and Last Name of the **Enrolled contact** | The commonest three |
| **Trigger & event data** > **Enrolled contact** | Every contact property | Name, email, phone, `utm_*`, *Latest Traffic Source* |
| **Trigger & event data** > **Form submission** | The submission that enrolled them | *Processed at timestamp* for *Registered At* |
| **Action data** | Outputs of earlier actions, e.g. *1. Custom code*, *2. Branch* | `registeredLate`, `regRedirect` |
| **Recommended & recent** | Your data sources, e.g. **Active Topic A Config** (pencil icon to manage the list) | Every configuration value: dates, tags, links |
| **More data sources** / **+ Add data** (bottom) | Adds a new data source | Step 8f |

Click a group (the **>** arrow), then click the property. It drops into the field as a
grey chip labelled *Property (Source)*, e.g. `9. Tag - Free Class Registrati… (Active
Topic A Config)`.

**Combine tokens and text.** A field can hold several chips with typed text between
them. *Class Name/Topic* is three chips with ` - ` typed between them:
`First Name (Enrolled contact)` `Last Name (Enrolled contact)` ` - `
`9. Tag - Free Class Registration (Active Topic A Config)`.

**Check where a chip reads from.** Hover the chip's **ⓘ**. The tooltip names the
property and the source: *"This is the 9b. Tag - Free Class Replay property of the
Active Dividends Config."* This tooltip is the only place a wrong source shows up.

**Remove a chip.** Click it and choose **Remove data token**, or use the field's bin
icon to clear the whole field.

**Date fields work differently.** A date property such as *Class Date* first asks
**Calendar date** or **Days after action running**:

- **Calendar date**, then click the box below it and pick a date token (e.g.
  `7. Event Start Date and Time (Active Topic A Config)`).
- **Days after action running**, then type `0` for "the day the action runs". HubSpot
  shows the hint *"Enrolled Date will be set to the day the action runs"*.

**Dropdown fields take a fixed choice**, not a token. For *Class Status* and
*Class Topic*, pick the option.

**Custom code inputs** use the same panel. Under **Property to include in code**,
type the **Key** (the name the code reads, e.g. `event_start_date_and_time`), click
**Select a property**, and pick the token. **Add property** adds another row.

> ⚠️ **A typed property name is not a token.** Typing `utm_source` into a field saves
> the literal word `utm_source` on every record. Always pick from the panel, and check
> for the grey chip.

> ⚠️ **Nothing may be typed in front of a token unless you mean it.** In production
> an *Email* field held the text `email` followed by the Email chip, and every
> address was saved as `emailname@example.com`. Click into each mapped field after
> cloning to look for stray text.

**8a. Create it.** **Automation > Workflows > Create workflow > From scratch**, choose
**Contact-based**, name it `2. Class Registration Record Creation`.

> 💡 **HubSpot's AI workflow builder (Breeze) helps only partly.** It can draft a
> contact-based skeleton (trigger, branches) but it can't generate workflows on custom
> objects (Step 11). It also drops token mappings and invents values it doesn't know,
> and bracketed placeholders like `[FORM NAME]` are read literally. If you use it,
> treat the result as a skeleton and do 8c-8k by hand.

**8b. Trigger.** **Set up triggers > When an event occurs > Form submission**:
*"Form submission has been completed any number of times anytime"* and *"Form name is
any of"* every topic's **Registration** form. Under **Settings**, turn **re-enrollment
on** for this trigger, so a person who registers for next month's session is recorded
again.

**8c. Branch: does the contact have an email?** **+ > Branch > Based on filters**
*(wording may differ)*. Branch name `Contact is Known`, filter **Email is known**. Leave
*None met* to end. Everything below goes on the *Contact is Known* path.

**8d. Snapshot the UTMs.** There is no "copy property value" action, so add three
**Edit record** actions (**Record type**
*Contact (Current object)*, **Change type** *Replace*), each set from the enrolled
contact's own value:

| Property to edit | Value (token) |
|---|---|
| Class Reg UTM Source | `utm_source` (Enrolled contact) |
| Class Reg UTM Medium | `utm_medium` (Enrolled contact) |
| Class Reg UTM Campaign | `utm_campaign` (Enrolled contact) |

Insert each value as a **data token** from the token panel. Typed text such as
`utm_source` is saved as that literal word.

> ⚠️ **Don't use *Traffic Source Drill-Down 1 / 2* as UTMs.** Drill-down 1 holds a
> referring domain, campaign or `IMPORT`, and drill-down 2 holds `source / medium`.
> One production branch mapped *UTM Source - F* to a drill-down and reported nonsense
> sources. Map the `utm_*` properties.

Optional: before these, an **Edit record** that clears **Reg Redirect** (leave the value
empty), so the late check below always starts fresh.

**8e. Branch on the form.** **+ > Branch > Based on one property** *(wording may
differ)*: *"Branch on the value "Form name" of Form submission"*. Add one branch per
topic, **is equal to** that topic's Registration form.

> ⚠️ **Every form in the trigger needs a branch, and every branch needs its form in
> the trigger.** Trigger only: the contact enrolls, falls through to *None met*, and no
> record is written. Branch only: nobody ever enrolls. Also add forms to the trigger
> **by name**. A form GUID typed into the list enrolls the contact, but the branch
> matches on form name and never fires.

**8f. Add one data source per topic.** This is the step that turns the configuration
record into "custom values" the workflow can read. The topic must already exist as a
**Class Type** option, or there's nothing to pick. Data sources belong to one workflow,
so you'll repeat this in Steps 9 and 10.

Open any action that takes tokens (the Create record in 8g is the natural place),
click into a field, and at the bottom of **All data tokens** click **+ Add data** (or
**More data sources**). HubSpot offers one of two screens, depending on your portal's
editor version:

*Route 1, the **Add records** panel* (seen in August 2026):

| Field | Value |
|---|---|
| **Name your data source** | `Active Topic A Config` |
| **Choose a record type \*** | `Free Class Configuration` |
| **Choose a condition to filter free class configurations \*** | **If a property value is equal to** (BETA). Helper text: *"All records in your CRM are reviewed to find a matching property"* |
| property / **is equal to** / value | `Class Type` / is equal to / `Topic A` |
| **Choose a condition to filter free class configurations down to one \*** | **Most recently created** (other choices: *None*, *Most recently updated*, *First created*) |

Click **Add**.

*Route 2, inside the token panel* (seen in September 2026). The breadcrumb reads
**All data > Add data > Object > Value equals**:

1. **Add data**, under *"Choose how to find records"*, click **By property criteria >
   Property value is equal to**. *(Not **By association > Associated to enrolled
   contact**; see the warning below.)*
2. **Object**: search for and click **Free Class Configuration**.
3. **Value equals**, under *"Select a value to match"*: pick **Class Type**, then
   **is equal to**, then **Enter a value** > `Topic A`.
4. If asked how to filter down to one record, choose **Most recently created**. If
   asked for a name, use `Active Topic A Config` *(wording may differ: this route's
   last screen wasn't captured)*. A source created this way may appear as
   *"Free Class Configuration: Class Type …"*. That works the same, but rename it if
   you can, because you'll be telling five of these apart by name.

Either way, the source now appears under **Recommended & recent** in every token panel
in this workflow. Its properties are the topic's "custom values": click
**Active Topic A Config >** to see *4. Free Class Date*, *7. Event Start Date and
Time*, *9. Tag - Free Class Registration* and the rest.

✅ **Check:** pick any token from the new source and hover its ⓘ. It should read
*"This is the … property of the Active Topic A Config."*

> ⚠️ **Filter on Class Type, not Cohort Status.** Our first source was
> *Cohort Status is equal to Active*. With one record per topic, every topic's record
> is Active, so "down to one" just picks the most recent and every branch reads the
> same topic. The panel allows one condition, so make it the one that identifies the
> topic.

> ⚠️ **Don't use "If associated to the enrolled contact".** That was the first version,
> and it reads whichever configuration record the contact happens to be associated with.
> A brand-new contact has none, so every token came back empty and the action failed
> with *"Required properties were missing or empty"*. Property-equals finds the record
> regardless of the contact.

> ⚠️ **Use the same "down to one" choice in every workflow.** Production ended up with
> *Most recently created* in some sources, *Most recently updated* in others, and *First
> created* in one. With one record per Class Type they agree. The day someone clones a
> record, they don't. Pick one and keep exactly one record per Class Type.

**8g. Create the registration record.** On the topic's branch, click **+**, then
**Create record**.

*Why copy config values onto the registration at all?* Three reasons:

- **History.** The record is edited in place, so tomorrow it holds next month's date.
- **Email tokens.** Personalization tokens can't reach the configuration record from a
  contact or a registration (two hops).
- **Delays.** A *"Delay until"* step in a registration-based workflow can only anchor
  on the registration's own *Class Date*.

The copy is the snapshot.

1. **Type of record to create**: `Class Registration`. HubSpot shows the required field,
   **Class Name/Topic \***, first.
2. For every other property, click **Add more properties**, search for the property
   (e.g. `class`), and tick it. *(An older editor first asks **Set another class
   registration property** or **Copy a property to a class registration property**;
   choose **Set another…**.)*
3. Fill each one: a token from the panel, a dropdown choice, or for dates **Calendar
   date** plus a date token. Use the table below. "Config" means a token from this
   branch's **Active Topic A Config**.

| Property | Value |
|---|---|
| **Class Name/Topic \*** | `First Name` (Enrolled contact), space, `Last Name` (Enrolled contact), ` - `, `9. Tag - Free Class Registration` (Active Topic A Config) |
| Class Date | **Calendar date**, then token `7. Event Start Date and Time` (Active Topic A Config) |
| Class Status | `Registered` |
| Class Topic | `Topic A` |
| Free Class Type | `Topic A free class` |
| Email | `Email` (Enrolled contact) |
| Phone number | `Phone Number` (Enrolled contact) |
| Enrolled Date | **Days after action running**, `0` *(hint: "Enrolled Date will be set to the day the action runs")* |
| FC Status Tag | `9. Tag - Free Class Registration` (Active Topic A Config) |
| Free Class Date | `4. Free Class Date` (Active Topic A Config) |
| Free Class Source | `Latest Traffic Source` (Enrolled contact) |
| Registered At | **Calendar date**, then `Processed at timestamp` (Form submission) |
| Registration Reference | `Email` (Enrolled contact), `-`, `9. Tag - Free Class Registration` (Active Topic A Config) |
| UTM Source - F / - L | `utm_source` (Enrolled contact) |
| UTM Medium - F / - L | `utm_medium` (Enrolled contact) |
| UTM Campaign - F / - L | `utm_campaign` (Enrolled contact) |

**Associate new class registration with:** *The contact enrolled in this workflow*.
Optionally tick **Add timeline activity from the enrolled contact to the class
registration**.

**8h. Remember the topic on the contact.** **Edit record**: **FC Current Class Topic**
= `Topic A`.

**8i. Late registration check** (needs Data Hub Pro; skip 8i-8k without it).
**+ > Custom code**:

1. **Language**: `Node.js 20.x`. **Description**: `Determines if registration is after
   the class has started.`
2. **Secrets**: none.
3. **Property to include in code**:

   | Key | Value |
   |---|---|
   | `event_start_date_and_time` | `7. Event Start Date and Time` (**Active Topic A Config**) |

4. Delete the sample code and paste in **all** of [`workflow-actions/late-registration-check.js`](workflow-actions/late-registration-check.js).
5. **Data outputs** (*"Outputs must be defined in both the code and the data outputs form"*):

   | Output | Type |
   |---|---|
   | `regRedirect` | String |
   | `registeredLate` | Boolean |
   | `classStartIso` | String |
   | `reason` | String |

6. **Test action.** The tester does **not** resolve data-source tokens. Run it as-is
   and you'll get `reason` **no_start_time** and the log *"No event_start_date_and_time
   on the input. Check the Active Config mapping on this branch."* even when the mapping
   is right. Type a test value instead: the session start in epoch milliseconds (e.g.
   `1789686000000`) in the **Enter test value** box. Before that time you should see
   *Status* **Success**, `registeredLate` **false**, `reason` **before_start**, and a
   log line like `Class starts Sep 17, 2026, 7:00 PM ET; now Sep 17, 2026, 2:10 PM ET;
   regRedirect=No`. Confirm the real mapping later in a live enrollment's log.

| `reason` | Means | Fix |
|---|---|---|
| `before_start` / `after_start` | Working | none |
| `no_start_time` | The input is empty. The log says *"Check the Active Config mapping on this branch."* | Map the token from **this branch's** data source, or fill 7. on the record |
| `unparseable_start_time` | The input is a display string (`Sep 17th, 2026`) | Map `7. Event Start Date and Time`, not `4. Free Class Date` |

**8j. Branch on the result.** **+ > Branch > Based on one property**: *"Branch on
registeredLate of &lt;the custom code action&gt;"*. One branch **is equal to** `true`; name
the default `Not Registered Late`.

**8k. Mark late registrants as attended.** On the `true` branch, **+ > Custom code**:

1. **Language** `Node.js 20.x`, **Secrets** none.
2. **Property to include in code**:

   | Key | Value |
   |---|---|
   | `email` | `Email` (Enrolled contact) |
   | `firstname` | `First Name` (Enrolled contact) |
   | `lastname` | `Last Name` (Enrolled contact) |
   | `phone` | `Phone Number` (Enrolled contact) |

3. Paste in **all** of [`workflow-actions/submit-attended-form.js`](workflow-actions/submit-attended-form.js), then set
   `PORTAL_ID` (your Hub ID) and `FORM_GUID` (**this topic's Attended form**).
4. **Data outputs**: `submitted` Boolean, `reason` String.
5. Don't **Test** this one on a real contact unless you want them recorded as attended.

> ⚠️ **One copy of 8i-8k per topic branch.** A workflow data source resolves to one
> fixed record, so each branch's code reads its own *Active &lt;Topic&gt; Config*. Only
> `FORM_GUID` differs between the copies of the second action.

**8l. Optional nurture.** End the **Not Registered Late** path with **Go to workflow**
pointing at your nurture workflow for that topic. Leave the late path without it,
because someone who joined a class already in progress shouldn't get "see you
tonight" reminders.

**8m.** Click **Review and publish** *(wording may differ)*, choose **No, only enroll
contacts who meet the trigger criteria after the workflow is turned on**, and turn it on.

✅ **Check:** submit the Registration form with a test email. Within a minute the
contact has a **Class Registration** with **Class Status** *Registered*, **Class Date**
on the session date, and **Class Name/Topic** `Test User - Topic A Free Class
Registration [Sep 17th 2026]`. The workflow's **Enrollment history** shows every action
as *Success*.

### Step 9: Build the Attended workflow

About 30 minutes for the first topic, 10 after.

**9a.** Create a **Contact-based** workflow named `4. Class Attended Workflow (Watch Now Page)`.

**9b. Trigger:** *Form submission* · *"Form name is any of"* every topic's **Attended**
form, **and nothing else**. Re-enrollment on.

**9c. Branch on the form** (as 8e), one branch per topic's Attended form.

> ⚠️ **A cloned branch keeps the old topic's data source.** The field labels look
> right. Only the token's tooltip (*"This is the 9a. Tag - Free Class - Attended
> property of the Active Topic B Config"*) shows that it reads another topic. Hover
> every token after cloning.

**9d. Create record** on each branch, using the topic's **Active Topic A Config** data
source (create it here as in 8f; data sources belong to one workflow):

| Property | Value |
|---|---|
| **Class Name/Topic \*** | `Email` (Enrolled contact), `-`, `First Name`, `-`, `Last Name`, `-`, `9a. Tag - Free Class - Attended` (Active Topic A Config) |
| Class Date | **Calendar date**, `7. Event Start Date and Time` (Active Topic A Config) |
| Class Status | `Attended` |
| Class Topic / Free Class Type | `Topic A` / `Topic A free class` |
| Email | `Email` (Enrolled contact) |
| Phone number | `Phone Number` (Enrolled contact) |
| FC Status Tag | `9a. Tag - Free Class - Attended` (Active Topic A Config) |
| Free Class Date | `4. Free Class Date` (Active Topic A Config) |
| Free Class Source | `Latest Traffic Source` (Enrolled contact) |
| Registered At | **Calendar date**, `Processed at timestamp` (Form submission) |
| Registration Reference | `Email` (Enrolled contact), `-`, `9a. Tag - Free Class - Attended` (Active Topic A Config) |
| UTM Source/Medium/Campaign - **F** | `Class Reg UTM Source / Medium / Campaign` (Enrolled contact) *(UTM at last class registration)* |
| UTM Source/Medium/Campaign - **L** | `utm_source / utm_medium / utm_campaign` (Enrolled contact) |

Associate with *The contact enrolled in this workflow*.

> ⚠️ **Attendance reads the *upcoming* pair, not `4a`.** On class night the session in
> `4.` / `7.` is the one airing; `4a` / `Old Class Date` still hold the previous
> session until you update them after the class (Step 13). Mapping an Attended branch to
> `4a` stamps attendees with last month's date. That happened on one topic in production.

> ⚠️ **Every branch must use its own tag.** Use `9a` (Attended) here. A branch that
> keeps `9. Tag - Free Class Registration` from a cloned Registration action writes
> attendance records labelled as registrations.

> ⚠️ **Re-submitting the watch page writes another record.** The trigger fires on *any
> number of* submissions, so a viewer who reloads and submits twice gets two Attended
> records. In production about one in four attended records was a repeat. Count unique
> **Registration Reference** values, not records. Or add a filter *(Only enroll
> contacts that meet these conditions)* that skips contacts whose
> **FC Current Class Topic** session is already marked attended, if you'd rather prevent
> it.

✅ **Check:** submit the Attended form for your test contact. A second Class
Registration appears with **Class Status** *Attended*, the same **Class Date** as the
registration, and **UTM Source - F** equal to the registration's **UTM Source - F**.

### Step 10: Build the Replay workflow

About 30 minutes for the first topic, 10 after.

**10a.** Create a **Contact-based** workflow named `5. Free Class Watched Replay Workflow`.
Trigger: every topic's **Replay** form. Re-enrollment on.

**10b.** Branch on the form, one branch per Replay form. Every form in the trigger needs
a branch, because a form with no branch runs straight to *None met* and records nothing.

**10c. Create record** on each branch, with that topic's **Active Topic A Config**:

| Property | Value |
|---|---|
| **Class Name/Topic \*** | `First Name`, `Last Name` (Enrolled contact), ` - `, `9b. Tag - Free Class Replay` (Active Topic A Config) |
| Class Date | **Calendar date**, **`Old Class Date`** (Active Topic A Config) |
| Class Status | `Watched Replay` |
| Class Topic / Free Class Type | `Topic A` / `Topic A free class` |
| Email | `Email` (Enrolled contact). The token alone, nothing typed in front of it. |
| Phone number | `Phone Number` (Enrolled contact) |
| FC Status Tag | `9b. Tag - Free Class Replay` (Active Topic A Config) |
| Free Class Date | **`4a. Old Free Class Date`** (Active Topic A Config) |
| Free Class Source | `Latest Traffic Source` (Enrolled contact) |
| Registered At | **Calendar date**, `Processed at timestamp` (Form submission) |
| Registration Reference | `Email` (Enrolled contact), `-`, `9b. Tag - Free Class Replay` |
| UTM - F / - L | as Step 9 |

> ⚠️ **Don't publish the replay page before the first session airs.** Until then
> `4a` and `Old Class Date` are blank, so every replay record is written with no date.

> ⚠️ **The replay reads the *last aired* pair.** People watch the replay in the days
> after the class, often after you've already moved `4.` / `7.` to the next session.
> `4a` and `Old Class Date` still point at the session they watched, so the record is
> credited to the right session.

> ⚠️ **Read every value after cloning a branch.** In production, the newest topic's
> Replay branch was cloned from another topic and kept that topic's **Class Topic** and
> **Free Class Type**. Its **Email** field also had the word `email` typed in front of
> the token, so every address was stored as `emailname@example.com`. Two branches had
> no **Class Date** at all. Open each mapped field after you clone.

✅ **Check:** submit the Replay form. A third Class Registration appears with
**Class Status** *Watched Replay*, **Class Date** on the session that aired, and a clean
**Email**.

### Step 11: Label each session for reporting

About 15 minutes. Needs Data Hub Pro.

`class_session` gives each session one dropdown value (`2026-09-17 - Topic A`), so
reports can group by session. HubSpot can't add dropdown options from a workflow, so
this action adds them itself.

**11a.** Create a service key with read and write on the Class Registrations object and
on property definitions *(scopes: `crm.objects.custom.read`, `crm.objects.custom.write`,
`crm.schemas.custom.read`, `crm.schemas.custom.write`)*. Add it as a workflow secret
named `CLASS_SESSION_WRITE_TOKEN`.

**11b.** Create a workflow on the **Class Registrations** object: name
`Class Session - auto-populate from Class Date + Class Topic`, trigger
*"Class Date is known"*, re-enrollment on when **Class Date** changes.

**11c.** **+ > Custom code**: **Language** `Node.js 20.x`, **Description** `Build Class
Session label from Class Date + Class Topic`, **Secrets** `CLASS_SESSION_WRITE_TOKEN`.

| Key | Value |
|---|---|
| `class_date` | `Class Date` (Enrolled class registration) |
| `class_topic` | `Class Topic` (Enrolled class registration) |
| `event_start_date_and_time` | Optional: `7. Event Start Date and Time` from an associated configuration record, if you associate them (Step 2c) |

Paste in **all** of [`workflow-actions/class-session-label.js`](workflow-actions/class-session-label.js), set `OBJECT_TYPE` to your
Class Registrations object type id, and **edit the topic rules** (the three `if` lines)
to match your topics. **Data outputs**: `class_session` String.

> ⚠️ **A topic with no rule writes nothing.** The label needs both a date and a matched
> topic. In production two newer topics were added to the workflows but not to these
> rules, so their registrations never got a session label. Any report grouped by
> Class Session silently leaves them out.

**11d. Test action** on a test registration: *Status* **Success**, `class_session` =
`2026-09-17 - Topic A`, and the log shows `CREATED enum option` the first time,
`Enum option already exists` after.

✅ **Check:** the test registration's **Class Session** shows the label, and
**Settings > Properties > Class Session** lists it as an option.

### Step 12: Test one full session

About 20 minutes, ideally an hour before a real session.

1. Set a test topic's record to start 15 minutes from now (7. and the display strings).
2. Register on the registration page. **Check:** the confirmation page shows the date,
   and a *Registered* record appears.
3. Open the watch page. **Check:** the countdown runs; at zero the waiting copy hides
   and the join form appears.
4. After the start time, register a second test contact. **Check:** they land on the
   live link (with `?t=180`), their contact shows **Reg Redirect** *Yes*, and they have
   both a *Registered* and an *Attended* record.
5. Submit the Attended form for the first contact. **Check:** *Attended* record, same
   **Class Date**.
6. Fill `4a` and `Old Class Date` with today, and submit the Replay form. **Check:**
   *Watched Replay* record dated today.
7. Put the record back, and **delete the test registrations**. In one production
   class, test records were counted as real attendance.

### Step 13: Flip to the next session

About 10 minutes. This is the whole point: nothing but the record changes.

**The night the session airs, after it ends:**

| Property | Set to |
|---|---|
| 4a. Old Free Class Date | the session that just aired (copy `4.`) |
| Old Class Date | the same date |
| 3. Replay Video Embed Code | the replay embed |

**When you open registration for the next session:**

| Property | Set to |
|---|---|
| 4. Free Class Date, 5. Day of Class, 6. Free Class Time | the next session |
| 7. Event Start Date and Time | the next session's start |
| 1. Watch Now YouTube Link | the next stream's link |
| Add Event ID | the next calendar event |
| 9. / 9a. / 9b. / 9c. tags | same prefix, new date |
| SMS list codes, offer links | if they change per session |

`4a` is always one session behind `4`. `4a == 4` means "this session has aired and
hasn't been flipped yet". `4a` earlier than `4` means "`4` is upcoming and `4a` is the
last one that aired". Both are normal.

Also check `5. Day of Class`, which nothing validates, and every tag's date.

✅ **Check:** open each funnel page with a fresh query string (`?v=flip2`). HubSpot's
CDN can serve a cached page for up to about 10 hours, so a page without one may still
show last session's date. Confirm the date, the countdown target and the calendar
button. The day after the flip, filter Class Registrations on the new **Class Date**
and group by **FC Status Tag**. Any old-session tag there means a branch still reads a
stale value.

### Step 14: Add a new topic

About 30 minutes.

1. Add the topic as an option to **Class Type** (config), **Class Topic** and
   **Free Class Type** (registrations), and **FC Current Class Topic** (contact).
2. Create its configuration record (Step 4). Watch for pre-filled values.
3. Create its three forms (Step 7).
4. In each of the three workflows: add the new forms to the trigger, add a branch, add
   an **Active &lt;Topic&gt; Config** data source, and add a **Create record** mapped as in
   Section 3. In Registration, also add a copy of 8i-8k with the new Attended form's GUID.
5. Add the topic's rule to [`class-session-label.js`](workflow-actions/class-session-label.js) (Step 11).
6. Build the pages from an existing topic's pages and re-pick the record in every
   module's **CRM object** field.

✅ **Check:** Step 12, on the new topic.

---

## 3. Create record mappings, side by side

| Class Registration property | Registration (Step 8) | Attended (Step 9) | Replay (Step 10) |
|---|---|---|---|
| Class Status | `Registered` | `Attended` | `Watched Replay` |
| Class Date | `7. Event Start Date and Time` | `7. Event Start Date and Time` | **`Old Class Date`** |
| Free Class Date | `4. Free Class Date` | `4. Free Class Date` | **`4a. Old Free Class Date`** |
| FC Status Tag | `9.` registration tag | `9a.` attended tag | `9b.` replay tag |
| Class Name/Topic | First Last - `9.` | Email-First-Last-`9a.` | First Last - `9b.` |
| Registration Reference | Email-`9.` | Email-`9a.` | Email-`9b.` |
| Email / Phone | contact | contact | contact |
| Registered At | form processed-at | form processed-at | form processed-at |
| UTM - F | contact `utm_*` | contact `class_reg_utm_*` | contact `utm_*` |
| UTM - L | contact `utm_*` | contact `utm_*` | contact `utm_*` |

All config tokens come from that branch's **Active &lt;Topic&gt; Config**.

---

## 4. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| A module shows nothing on the live page | No record picked in its **CRM object** field, or the property is empty on the record | Step 6a; check the record |
| The editor says *"Countdown is not rendering: pick a CRM object that has an Event Start Date and Time value"* | The record's 7. is empty, or the module doesn't fetch it | Step 4; Step 5a *Properties to fetch* (and the module's own step, 5f or 5g) |
| The countdown runs but nothing hides at zero | The selector fields hold ids from the other (desktop/mobile) section, or a stale form id | Step 6c, list both copies |
| The page still shows last session's date | CDN cache | Reload with `?v=<anything>` (Step 13) |
| Create record fails: *"Required properties were missing or empty"* | Class Name/Topic built from a token that's empty: the data source didn't find a record | Step 8f: property-equals source, Class Type set on the record |
| Every token from the config is empty | The data source is *"If associated to the enrolled contact"* | Step 8f |
| Registrations carry another topic's date | The branch uses another topic's data source | Re-pick each token from **this** branch's source |
| Late registrants not marked attended; `reason` = `no_start_time` | The late check's input isn't mapped on this branch | Step 8i |
| `submitted` = true but Reg Redirect stays No | `reg_redirect` isn't on the Attended form, or the form has unpublished changes | Step 7 |
| Registrants recorded as attendees | A registration form is in the Attended trigger | Step 9b |
| Attended records dated last month | The Attended branch maps `4a` / Old Class Date | Step 9d |
| Replay records with no Class Date, or another topic's topic | Branch cloned and not re-mapped | Step 10c |
| Twice as many attended records as people | Re-submissions; trigger runs on every submission | Count unique Registration Reference (Step 9) |
| Class Session empty for one topic | No topic rule in `class-session-label.js` | Step 11c |
| Replay page never closes | `Old Class Date` empty, or *force_open* on | Step 13; Step 6d |
| Late registrant lands on the confirmation page | Redirect Reg Form missing, or its record has no 1. or 7. (the editor shows *"Free Class Live Router is not configured"*) | Step 6b; Step 4 |

---

## 5. Limits

- **One record per Class Type.** The data sources pick one record by Class Type. Two
  records with the same Class Type means the "down to one" rule decides which one wins,
  and different workflows may decide differently.
- **Workflows can't loop over topics.** Each topic needs its own branch, data source and
  Create record in each workflow. Adding a topic means editing three workflows (Step 14).
- **The late check uses execution time.** HubSpot doesn't expose the form submission
  time to custom code, so a backed-up workflow queue could mark an on-time registrant
  as late.
- **The Replay Countdown assumes US Eastern** (`America/New_York`) for the class time,
  and reads only the hour from `6. Free Class Time` (minutes are ignored). Change the
  zone in `module.html` for other regions.
- **Display dates aren't validated.** Nothing checks that `4.` matches `7.`. Step 4's
  check is the only safeguard.
- **Calculated contact properties lag.** If you build "latest class attended" style
  calculated properties on top of this, they can take many hours to update, so never
  use them as a dedupe key in a workflow that runs on class night.
- **The CRM object module field and the property-equals data source were both BETA**
  when this was built, and their labels may have changed.

## 6. Testing

```bash
npm test
```

23 tests, Node 20+, nothing leaves your machine:

- **The three custom code actions run unchanged** in a sandbox with a frozen clock and
  a fake `fetch` and HubSpot client. They cover:
  - late vs on time, at the exact start second
  - epoch vs ISO input
  - a missing or unreadable start time always returning `No`
  - the form submission's fields, and skipping empty ones
  - failed and offline submissions
  - session labels and new dropdown options
  - the Eastern-date fix
  - topics with no rule
  - a missing secret
  - an API failure
- **Every module's CRM object field** points at the configuration object and only
  fetches properties the schema defines. Every property its HubL reads is in its fetch
  list.
- **The schema script** dry-runs without writing, creates what's missing, skips what
  exists, and uses each object's own property group.

## 7. Security

- **No secrets in code.** The only secret is `CLASS_SESSION_WRITE_TOKEN`, stored as a
  workflow secret. The late check and form submission use none.
- **The form submission action posts to HubSpot's public Forms API**, the same endpoint
  your website forms use. It can only submit the form named in `FORM_GUID`.
- **The configuration record is not secret, but it is public in effect.** Anything a
  module renders, such as links or embeds, is in the page source. Don't put private
  links on the record that you wouldn't put on the page.
- **The replay embed is rendered unescaped** (`|safe`), so anyone who can edit a
  configuration record can put HTML or script on the replay page. Limit who can edit
  the object.
- **Service keys:** give the schema key only the scopes listed in Step 1, and revoke it
  after the objects exist.

---

Built by [Jibril Sulaiman](https://github.com/jbrillionaire).
