# Public crawler runtime

The crawler checks each destination's registered hostname and public DNS answers,
then checks robots.txt before fetching. Redirect targets undergo the same checks.
Direct requests resolve again at the transport boundary and pin a public address
while preserving TLS SNI and the Host header.

Inherited HTTP_PROXY / HTTPS_PROXY / ALL_PROXY and NO_PROXY settings are honored.
For proxy requests, destination domain/DNS checks still run locally; the session
proxy performs the final remote DNS resolution and applies its own egress policy.
The crawler does not replace proxy hostnames with pinned destination IPs or bypass
the proxy. A trusted proxy must prevent private destination resolution itself.

Set CRAWLER_INFO_URL to this deployment's public /crawler page to include the
contact/opt-out URL in the bot's User-Agent. No example domain is advertised.

Backend workers call run_school(..., commit_state=False) and acknowledge_result
only after their document/exam database transaction commits. Unacknowledged pages
stay queued and are re-extracted after a failed ingestion. The standalone CLI
acknowledges its output automatically; it does not publish into the backend.

The HTTP MVP has no JS browser fallback or search-engine integration. Rules only
extract unambiguous, single-grade documents naming the expected school. Every
rule extraction requires human review; there are no automatically generated
confidence claims above the publication threshold. PDF scan images require OCR,
which is not enabled in this version.
