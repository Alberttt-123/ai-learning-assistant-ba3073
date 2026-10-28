# ADR 012 Student mail and HTTPS proxy authentication

Status: Accepted
Date: 2026-10-28

The assignment owner supplied a BNBU student address at `mail.bnbu.edu.cn`.
Accept that exact domain in addition to `bnbu.edu.cn`; arbitrary subdomains
and lookalike suffixes remain rejected. Roles, passwords, and token semantics
are unchanged. This is an additive accepted-domain change under the auth contract.

The public teaching deployment needs a reverse-proxy access layer separate from
the application's opaque bearer session. HTTP Basic Authentication and the app
otherwise compete for the `Authorization` header. The optional Nginx deployment
injects a meta tag into the UI HTML to select `X-App-Authorization` for the app's
session header. Nginx validates Basic credentials first, then replaces the
upstream `Authorization` header with the app session header. The backend still
accepts only its existing Bearer authorization contract. Direct/local deployment
without the meta tag continues to use `Authorization: Bearer`.

The backend must bind to loopback behind this proxy. A client-supplied app header
does not bypass Nginx Basic Authentication. Proxy credentials are never sent to
the backend, and the metadata tag contains no credentials. The deployed proxy
must be tested for both unauthenticated rejection and authenticated API access.
