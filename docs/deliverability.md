# Deliverability

If the newsletter lands in spam the product is dead, so these are hard
constraints rather than nice-to-haves.

## Zoho Mail setup

Delivery goes over plain SMTP, so any provider works. The defaults target Zoho.

### 1. Match the data centre

Zoho runs regional data centres and the SMTP host must match the one your
account was created in. Check the domain you log in to:

| Login at | `SMTP_HOST` |
|----------|-------------|
| mail.zoho.com | `smtp.zoho.com` |
| mail.zoho.eu | `smtp.zoho.eu` |
| mail.zoho.in | `smtp.zoho.in` |
| mail.zoho.com.au | `smtp.zoho.com.au` |
| mail.zoho.jp | `smtp.zoho.jp` |
| mail.zohocloud.ca | `smtp.zohocloud.ca` |

Using the wrong one fails authentication with correct credentials, which is the
single most common Zoho setup mistake.

### 2. App-specific password

If two-factor authentication is on, your normal password will be rejected.
Create an app password under **Zoho Mail > My Account > Security > App
passwords** and put that in `SMTP_PASSWORD`.

### 3. Check that your plan allows SMTP

Zoho's free Mail tier does not include IMAP/SMTP access. If authentication keeps
failing on credentials you know are right, confirm your plan in the Zoho admin
console before debugging anything else.

### 4. Sender address must be owned

Zoho only accepts a `From` address the authenticated account owns: the mailbox
itself, a verified alias, or an address on a domain you have verified. Set
`SENDER_EMAIL` accordingly, or the server refuses the envelope sender.

### 5. Verify before sending

```bash
oykos check-smtp
```

Connects, authenticates and probes the `From` address without delivering
anything. It reports the specific failure and what to change.

### Sending limits

Zoho Mail is a mailbox product, not a bulk sender, and enforces per-hour and
per-day limits that vary by plan. The engine sends one message per subscriber
over a shared connection, paced by `SMTP_THROTTLE_SECONDS` and recycling the
connection every `SMTP_MAX_PER_CONNECTION` messages.

Check your plan's actual limit in the Zoho admin console and size the list
against it. Once the list outgrows what Zoho Mail allows, move to a bulk sender
(Zoho Campaigns, Postmark, SendGrid, SES). Only `smtp_*` settings and
`email_sender.py` would need to change.

---

## DNS records (do this before the first send)

All three must exist on the sending domain. Google requires them for bulk
senders and Yahoo enforces the same expectations. Zoho shows the exact values
for your domain under **Admin Console > Domains > Email Configuration**.

| Record | Type | Notes |
|--------|------|-------|
| SPF | TXT on the root domain | Zoho's include is `include:zoho.eu` (or the equivalent for your data centre). Keep a single SPF record. |
| DKIM | TXT on the selector Zoho gives you | Generate and enable it in the Zoho admin console, then verify. |
| DMARC | TXT on `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.it; pct=100; adkim=s; aspf=s` |

Start DMARC at `p=none` while you read the aggregate reports, then move to
`p=quarantine` once SPF and DKIM align on every stream.

## Headers the engine sets

`oykos.delivery.email_sender.build_message` sets these on every message,
newsletters and trigger alerts alike:

* `List-Unsubscribe` with the HTTPS one-click URL and, when
  `UNSUBSCRIBE_MAILTO` is configured, a `mailto:` fallback.
* `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058). Only emitted
  alongside an HTTPS target, because a one-click POST to a mailto is meaningless.
* `List-Id`, `Date` and `Message-ID`.

`POST /unsubscribe/{token}` handles the one-click request without a confirmation
step, which is what RFC 8058 requires.

## Recipient privacy

Recipients are never disclosed to each other. A single recipient goes in `To`;
a batch goes in `Bcc` with the sender in `To`. The weekly pipeline sends one
message per subscriber anyway, so each reader gets their own unsubscribe token.

## Links in the body

Every issue carries three outbound links beyond the sources: the closing call to
action (`CTA_URL`, default `https://oykomed.it`), the preferences and
unsubscribe links, and - when WordPress publishing is enabled - a "Leggi online"
link to the published post.

Two things follow from that:

* **Publish before you send.** `deliver_and_finalize` POSTs the issue to
  WordPress first, so the "Leggi online" link resolves the moment the mail
  arrives. A link that 404s on the day of send is a spam signal and a support
  ticket. If publishing fails the link is omitted rather than sent broken. See
  [wordpress.md](wordpress.md).
* **Keep the link domains stable and aligned.** `CTA_URL`, `BASE_URL` and
  `WORDPRESS_URL` should all sit on domains you control and that resolve over
  HTTPS. Filters weigh the reputation of the domains you link to, not just the
  one you send from.

## Thresholds to watch

| Metric | Target | Hard limit |
|--------|--------|-----------|
| Spam complaint rate | < 0.10% | never reach 0.30% |
| Bounce rate | < 2% | |
| Weekly engaged rate | tracked per issue | |

Monitor these in Google Postmaster Tools for the sending domain.

## What not to do

* Do not make unsubscribing hard, or hide the link.
* Do not change the sending domain or From name frequently.
* Do not send to cold or unengaged lists. Every address in the database went
  through double opt-in; keep it that way.
* Do not increase frequency to drive engagement. For this audience it is the
  fastest way to lose both trust and inbox placement.

## Warm-up

Use a dedicated sending domain and ramp volume over the first few weeks rather
than sending to the whole list on day one. Reputation is per-domain and per-IP,
and a cold domain sending a large first batch is the classic way to start in the
spam folder.

## Switching provider

Nothing outside `smtp_*` in `config.py` and `delivery/email_sender.py` is
provider-specific. To move to Gmail, Postmark or SES, change the host, port and
credentials; the legacy `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` variables still
resolve to `SMTP_USERNAME` / `SMTP_PASSWORD` for existing deployments.
