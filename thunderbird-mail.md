# Thunderbird with ETH Microsoft 365 mail

Date: 2026-11-16

## Symptom

Receiving mail works, but sending fails with:

```text
Unable to authenticate to Outgoing server (SMTP)
```

## Cause

ETH mail runs on Microsoft 365. The IMAP server accepts a mail alias (here
`michael.jaehn@c2sm.ethz.ch`) as username, but the SMTP server only accepts
the Microsoft login name, which is `<eth-username>@ethz.ch`.

## Settings

| Setting | Incoming (IMAP) | Outgoing (SMTP) |
| --- | --- | --- |
| Server | `outlook.office365.com` | `smtp.office365.com` |
| Port | 993 | 587 |
| Connection security | SSL/TLS | STARTTLS |
| Authentication | OAuth2 | OAuth2 |
| Username | `mjaehn@ethz.ch` (an alias also works) | `mjaehn@ethz.ch` (an alias fails) |

## Fix

In Thunderbird: Account Settings, Outgoing Server (SMTP), select the server,
Edit, and set the username to `mjaehn@ethz.ch`. The sender address of the
account can still be the alias.

## Notes

Thunderbird is installed as a snap here. Its profile is under:

```text
~/snap/thunderbird/current/.config/thunderbird/<profile>.default/
```
