# Privacy Policy

This application includes *opt-in* error reporting powered by
[Sentry](https://sentry.io), an open-source error monitoring service.

## What We Collect

If you choose to opt in to error reporting, we may collect the following
information when an unhandled exception occurs:

- Python tracebacks and exception details
- Application version and Python version
- Operating system name (e.g. "Darwin" or "Windows")
- A randomly generated session identifier
- Whether the application is a development version or installed from a package
- A list of installed Python packages and their versions
- The command used to launch the app, with personal paths removed

> We make every effort to strip potentially sensitive information, such as home
> directory paths and hostnames, before sending.

## What We Don’t Collect

We **do not collect**:

- Names, email addresses, or any personal identifiers
- User input, documents, or data files
- IP addresses (Sentry is configured to avoid storing them)
- Directory paths or filenames (these are stripped before sending)
- Hostnames or computer names, unless you explicitly allow it via the
  `MM_TELEMETRY_SHOW_HOSTNAME` environment variable.

## When We Collect It

Error reporting is **opt-in only**.  No data is sent without your consent.

On program launch, you'll be asked whether you'd like to send crash reports.
Your response is stored locally in a configuration file.  If you answer "Yes",
the application will send error reports to Sentry when an unhandled exception
occurs.

## Opting out

You can change your preference at any time in the Exception Log Window
(restart required).

## Transparency

The complete error reporting logic is open source and viewable at:

<https://github.com/pymmcore-plus/pymmcore-gui/blob/main/src/pymmcore_gui/_sentry_.py>

## Data Retention

Crash data may be stored by Sentry for up to **90 days** for debugging and
quality improvement purposes.

## Legal Basis for Processing (GDPR/UK GDPR)

For users in the EU or UK, the legal basis for collecting crash reports is
**your explicit consent** under Article 6(1)(a) of the GDPR. No data is
collected unless you opt in.

## Your Rights (for EU/UK Users)

Under the GDPR, you have the right to access, delete, or object to the
processing of your personal data.

Note, we **do not collect any data that can be used to identify you**, and
therefore have no way to link error reports to specific individuals. As a
result, we are **unable to fulfill individual access or deletion requests**
because we cannot associate any data with you.

## Third-party Services (Sentry)

Error reports are sent to:

**Sentry**  
Functional Software, Inc.
45 Fremont Street, 8th Floor
San Francisco, CA 94105
Privacy Policy: [https://sentry.io/privacy/](https://sentry.io/privacy/)  
Data Processing Agreement: [https://sentry.io/legal/dpa/](https://sentry.io/legal/dpa/)

## Contact

For any questions or concerns about this policy, feel free to [open an
issue](https://github.com/pymmcore-plus/pymmcore-gui/issues/new) on our GitHub
repository.

---

*Last updated: 2025-04-16*
