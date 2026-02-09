# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | Yes       |
| < 0.2   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in UniFi Monitor, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email the maintainer or open a [private security advisory](https://github.com/Matt-Bloise/unifi-monitor/security/advisories/new) on GitHub.
3. Include steps to reproduce, affected versions, and potential impact.

You should receive an acknowledgment within 48 hours. A fix will be prioritized based on severity.

## Security Considerations

- **No built-in authentication.** The dashboard exposes network data (client MACs, IPs, device names). Bind to `localhost` or place behind a reverse proxy with authentication.
- **UniFi credentials** are stored in `.env` (gitignored). Never commit credentials to version control.
- **Self-signed SSL** is expected when connecting to UniFi gateways (`verify=False`). This is standard for local UniFi OS API access.
- **Webhook URLs** may contain secrets (e.g., Discord webhook tokens). Treat `ALERT_WEBHOOK_URL` as sensitive.
