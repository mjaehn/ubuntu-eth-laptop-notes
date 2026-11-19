# Ubuntu laptop at ETH Zurich: setup notes

Notes on what was needed to make a Linux laptop work in the ETH Zurich
environment, written down so that others with a similar setup can reuse them.
Each topic has its own page with the symptoms, the cause and the fix.

## System

| Component | Value |
| --- | --- |
| Laptop | Dell Pro 14 Premium PA14250 (Intel Core Ultra 7 268V) |
| OS | Ubuntu 26.04.1 LTS, kernel 7.0.0-43-generic |
| Desktop | KDE Plasma 6 on Wayland, NetworkManager |
| Department | IAC / C2SM, ETH Zurich |

## Topics

| Page | Problem solved |
| --- | --- |
| [Printing](printing.md) | ETH SMB printers via `ethz-cups-config-app`: jobs held for authentication, Kerberos setup |
| [Thunderbird mail](thunderbird-mail.md) | ETH Microsoft 365 mail: SMTP refuses the login when the mail alias is used |
| [Touchpad](touchpad/README.md) | Collaboration Touchpad Zoom/Teams icons stay dark (under investigation) |
| [VPN](vpn.md) | ETH VPN (Cisco AnyConnect protocol) in KDE with openconnect |
| [Webcam](webcam/README.md) | Integrated IPU7 webcam shows black or crashes PipeWire; includes install scripts |

## Official IAC documentation

The IAC IT wiki covers the officially supported setup and is the first place
to look:

- [Linux on IAC laptops](https://wiki.iac.ethz.ch/bin/viewauth/IT/LinuxIACLaptop)
  (login required)
- [Linux on Dell laptops](https://wiki.iac.ethz.ch/IT/LinuxLaptopDell)
- [Printing under Linux](https://wiki.iac.ethz.ch/IT/LinuxPrinting)

## Disclaimer

These are personal notes, not official ETH documentation. Usernames, printer
names and paths are the real values from one machine; replace them with your
own. For official instructions see the
[ETH IT Services knowledge base](https://ethz.ch/staffnet/en/it-services.html).
