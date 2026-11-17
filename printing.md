# Printing on ETH SMB printers

Date: 2026-11-17

## Summary

The ETH printers are shared over SMB from the print server `pia01.d.ethz.ch`.
The ETH tool `ethz-cups-config-app` creates a CUPS queue for a printer, but on
this machine every job ended up "held for authentication" and nothing printed.
Two problems had to be fixed:

1. The CUPS SMB backend (`smbspool`) does not understand `D\username` as
   domain plus username, so the domain has to go into the printer URI.
2. KDE/Qt print dialogs never ask for SMB credentials, so jobs from most
   applications stay held. Kerberos authentication solves this for all
   applications.

The final setup uses Kerberos: run `kinit` once before printing, and every
application prints without a password prompt.

## Initial setup

The app is available from the ETH repository on the openSUSE Build Service
(`home:ethz`, here the `xUbuntu_24.04` packages, which also work on 26.04):

```text
ethz-cups-config-app 1.1.0-1
```

It downloads the ETH "Multibrand" PPD driver from `pia01.ethz.ch` and creates
a queue such as:

```text
device for p-chn-hp008: smb://pia01.d.ethz.ch/p-chn-hp008
auth-info-required=username,password
```

## Diagnosis

`lpstat -t` only shows `SMB connection failed!`. The useful information is in
`/var/log/cups/error_log` (readable by the `adm` group):

```sh
grep -E 'NT_STATUS|held' /var/log/cups/error_log | tail
```

| Error | Meaning |
| --- | --- |
| `NT_STATUS_LOGON_FAILURE` | The server rejected the username or password |
| `NT_STATUS_INVALID_ACCOUNT_NAME` | No or malformed username was sent (for example, a job submitted with `lp`, which cannot prompt) |
| `Job held for authentication` | The job waits for credentials; it is not lost |

To check that the credentials themselves are valid, independent of CUPS:

```sh
smbclient -L //pia01.d.ethz.ch -U 'D\mjaehn'
```

If this lists the printers, the account and password are fine and the problem
is on the CUPS side.

## Fix 1: domain in the printer URI

`smbclient` accepts `D\mjaehn`, but `smbspool` passes it unchanged as the
username. Put the domain (workgroup) into the URI instead and use the plain
username:

```sh
sudo lpadmin -p p-chn-hp008 -v smb://D/pia01.d.ethz.ch/p-chn-hp008
```

With username/password authentication, a held job can then be released from
the terminal (the password is read interactively and not stored):

```sh
python3 -c "import cups,getpass; cups.Connection().authenticateJob(<job-id>, ['mjaehn', getpass.getpass('ETH password: ')])"
```

This works, but it is impractical: only applications with the GTK print
dialog (Firefox, Thunderbird, GIMP, GNOME applications) ask for the password.
KDE applications (Okular, Kate, Dolphin) and the KDE printer settings never
do, so their jobs stay held.

## Fix 2: Kerberos authentication (final setup)

The ETH Active Directory domain `d.ethz.ch` is also the Kerberos realm
`D.ETHZ.CH`. Its domain controllers are published in DNS
(`_kerberos._tcp.d.ethz.ch`), so no KDC has to be configured by hand.

Run as root:

```sh
DEBIAN_FRONTEND=noninteractive apt-get install -y krb5-user

cat > /etc/krb5.conf <<'EOF'
[libdefaults]
    default_realm = D.ETHZ.CH
    dns_lookup_kdc = true
    dns_lookup_realm = false
    rdns = false
    default_ccache_name = FILE:/tmp/krb5cc_%{uid}

[domain_realm]
    .d.ethz.ch = D.ETHZ.CH
    d.ethz.ch = D.ETHZ.CH
EOF

# CUPS runs a backend as root only if it is not world-executable;
# root is needed so that smbspool can read the user's ticket.
dpkg-statoverride --update --add root root 0700 /usr/bin/smbspool

lpadmin -p p-chn-hp008 -o auth-info-required=negotiate
systemctl restart cups
```

Notes:

- `default_ccache_name` must be a `FILE:` cache in `/tmp`; `smbspool` looks
  for the ticket of the job owner there. A kernel keyring cache does not work.
- `dpkg-statoverride` keeps the 0700 mode across package updates. The only
  side effect is that normal users can no longer run `smbspool` directly.
- Keep the domain in the URI from Fix 1.

Test the ticket without CUPS:

```sh
kinit mjaehn@D.ETHZ.CH
smbclient -L //pia01.d.ethz.ch --use-kerberos=required
```

## Daily use

Get a ticket before printing (valid for about 10 hours):

```sh
kinit mjaehn@D.ETHZ.CH
klist          # shows the ticket and its expiry
```

An alias `ethkinit` for this command is defined in the dotfiles.

If a job was sent without a valid ticket, it is held, not lost. Get a ticket
and release it:

```sh
lpstat -o                 # shows the job id, e.g. p-chn-hp008-7
lp -i 7 -H resume
```

Off campus, connect the [ETH VPN](vpn.md) first if `kinit` cannot reach the
domain controllers.

## Options that were considered and rejected

- **Saving the password in the GTK dialog or in KWallet**: only helps GTK
  applications, and the stored password becomes wrong after the regular ETH
  password change. Repeated failed logins can lock the ETH account.
- **A keytab for password-free `kinit`**: stores a password-equivalent key on
  disk and breaks on every password change, with the same lockout risk.
- **Running `kinit` automatically at login** (KDE autostart with a `kdialog`
  password prompt): works, but must wait for the network (`nm-online`), and
  for occasional printing a manual `kinit` is simpler.
