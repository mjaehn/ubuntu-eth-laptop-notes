# ETH VPN in KDE Plasma

Date: 2026-11-13

## Summary

ETH uses a Cisco AnyConnect compatible VPN. On Linux, the open-source client
`openconnect` works through its NetworkManager plugin, so the VPN can be
switched on and off from the KDE network applet in the system tray.

## Installation

```sh
sudo apt install network-manager-openconnect network-manager-openconnect-gnome
```

The `-gnome` package provides the authentication dialog and is also needed
under KDE.

## Connection settings

In KDE: System Settings, Wi-Fi & Networking, add a new connection of type
"Cisco AnyConnect compatible VPN (openconnect)".

| Setting | Value |
| --- | --- |
| Connection name | `ETH VPN` |
| Gateway | `sslvpn.ethz.ch/staff-net` |
| Protocol | Cisco AnyConnect |

The realm after the slash in the gateway (`staff-net`) depends on the user
group; see the ETH IT Services documentation for the right one.

When connecting, the dialog asks for the username, the ETH network password
and a one-time code from the authenticator app (multi-factor
authentication). The credentials are entered at each connection and not
stored in the connection profile.

## Usage

System tray, network icon, click `ETH VPN`. From the terminal:

```sh
nmcli connection up "ETH VPN"
nmcli connection down "ETH VPN"
```
