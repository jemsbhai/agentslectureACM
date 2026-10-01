

Yes. The explanation below is checked against Atlassian's current documentation for the Rovo MCP server (links at the end). I have grouped the controls by who enforces them: Atlassian, CNB's Atlassian organization, and the RBC Assist client itself.

1. How the authorization works

RBC Assist does not use a shared service credential for Atlassian. Each user authorizes individually through OAuth 2.1: the user is sent to Atlassian, signs in, and on the consent screen approves access for a specific Atlassian site. Atlassian issues an access token to RBC Assist for that user and that site. On every tool call the MCP server validates the token, attaches the user and product context, and forwards the request to Jira or Confluence under that user's existing permissions. Nothing is readable through the MCP server that the user could not already read in the product directly.

Two properties of that token matter for your question. First, the token is consented for a specific site, identified by its cloudId, and Atlassian validates that every request is made against the cloudId the token was granted for, so a token for one site is not usable against another. Second, tokens are user-specific and are never shared between users.

Before the consent flow can complete for a given site, Atlassian also runs two organization-level checks on the side of the organization that owns that site: the connecting client's redirect origin must be on that organization's allowed domain list, and, where IP allowlisting is configured, the call must originate from an allowed range. When the domain check fails, the error returned is "Access denied: Your organization admin must authorize access from [redirect URI] to cloudId: [cloudId]".

2. Why a personal Atlassian login cannot reach CNB content

CNB's Jira and Confluence content lives in CNB's Atlassian organization, under CNB's cloudId. A personal Atlassian account (for example an Atlassian ID registered with a Gmail address) is not a member of that organization or site, so it has no project or space permissions there and the CNB site is not available to it on the consent screen. Separately, cnb.com accounts are managed accounts under CNB's verified domain and authentication policy, so a CNB identity can only be asserted through CNB's single sign-on; a personal account cannot present itself as a CNB user. A personal login therefore produces, at most, a token for the user's own personal site, with no reach into CNB data.

3. Why RBC Assist does not read the user's personal Atlassian content

a) Site binding. RBC Assist's Atlassian connection targets CNB's cloudId. A token obtained with a personal account is bound to whatever personal site that account consented for. Every request RBC Assist makes against CNB's cloudId with that token fails validation at the MCP server because the cloudId does not match the token. This is the primary control, and it depends on the client addressing a fixed cloudId rather than discovering sites at runtime (see point c).

b) Domain allowlist, evaluated by the personal organization. The domain check from section 1 is run by the organization that owns the target site. RBC Assist's callback origin would have been added to CNB's organization explicitly; it is not on Atlassian's default list of supported AI client origins (claude.ai, chatgpt.com, vscode.dev, cursor and similar). A personal Atlassian organization therefore refuses the RBC Assist connection at the consent step with the error quoted above. The only way past this is for the user, acting as admin of their own personal organization, to deliberately add RBC's callback origin to that organization's allowlist, which is a multi-step intentional act and not something that happens by choosing the wrong account at login. If the RBC Assist callback is routed through a gateway whose origin is on Atlassian's default list, this layer does not apply and control c) carries the full weight.

c) Client-side enforcement in RBC Assist. Atlassian's client guidance supports pinning the cloudId in the client configuration instead of discovering sites through getAccessibleAtlassianResources. With the cloudId pinned, the only site RBC Assist ever addresses is CNB's, and a personal token fails on every call. On top of that, at the end of the OAuth flow the client should verify, from the identity returned by the authorization, that the account belongs to CNB's managed domain and that CNB's cloudId is among the sites the token was granted for, and discard the token otherwise. I would like the RBC Assist team to confirm that the connection is pinned to CNB's cloudId and whether the identity check is implemented. If it is not, I recommend adding it; it is the control that turns "will not by default" into "cannot".

4. Organization-level controls CNB holds over the MCP server (Atlassian Administration, Rovo > Rovo MCP server, plus data security policies)

- Domain settings: which client origins can complete OAuth connections to CNB's organization. Atlassian's default supported list can be switched off so that only explicitly added origins are accepted.
- Permissions: read, write and search permission groups are granted or revoked per product by organization admins; the delete_jira and manage_jira groups are off by default.
- Authentication method: API token authentication for the MCP server is an organization-level switch. Keeping it off forces per-user OAuth, which is what makes the per-user permission model and the domain allowlist apply (the domain allowlist does not govern API token connections).
- IP allowlisting: tool calls through the MCP server must originate from an allowed range for the relevant product, whichever AI client is used.
- Data security policy "Prevent Atlassian MCP server access" (Atlassian Guard): blocks MCP reads at the organization, site, space or project, or classification level, even where the user has direct access in Jira or Confluence.
- Audit and revocation: every tool call through the MCP server is written to the organization audit log (filter: Rovo MCP User Actions); site and organization admins can review or revoke the MCP app from Connected apps; users can revoke their own authorization from their profile.

5. Two further notes

Atlassian has introduced enterprise-managed authentication (Cross App Access), where the MCP authorization is issued through the organization's identity provider and bound to the organization's cloudId, with IdP app assignment and conditional access deciding who can connect. It is currently documented for Claude as the client with Okta as the IdP. If RBC Assist adds support for it, the Atlassian login prompt disappears from the user flow and the personal-account scenario cannot arise at all.

Also, a correction to my earlier answer on your first question. If user app installs are blocked in CNB's organization (the Connected apps setting), the first OAuth consent for the RBC Assist client on the CNB site must be completed by a CNB site admin; until then other users see "Your site admin must authorize this app". After that first consent, regular users connect normally. It is also advisable that this first user has access to both Jira and Confluence, since the app is registered on the site at that first consent.

Happy to walk through any of this on a call.

References
- Configuring OAuth 2.1 (cloudId binding, user-specific tokens): https://developer.atlassian.com/cloud/rovo-mcp/guides/configuring-oauth-2-1/
- Authentication and authorization (admin controls, permission groups): https://developer.atlassian.com/cloud/rovo-mcp/guides/authentication-and-authorization/
- Understand Atlassian MCP server (domain settings, IP allowlists): https://support.atlassian.com/security-and-access-policies/docs/understand-atlassian-mcp-server/
- Control Atlassian MCP server settings: https://support.atlassian.com/security-and-access-policies/docs/control-atlassian-mcp-server-settings/
- Available Atlassian MCP server domains (default list, how redirect origins are matched): https://support.atlassian.com/security-and-access-policies/docs/available-atlassian-mcp-server-domains/
- Configure Atlassian MCP server permissions (error text for domain and cloudId denial): https://support.atlassian.com/security-and-access-policies/docs/configure-atlassian-mcp-server-permissions/
- Prevent Atlassian MCP server access (data security policy): https://support.atlassian.com/security-and-access-policies/docs/prevent-atlassian-mcp-server-access/
- Configure enterprise-managed authentication: https://support.atlassian.com/security-and-access-policies/docs/configuring-enterprise-managed-authentication/
- "Your site admin must authorize this app" error: https://support.atlassian.com/atlassian-cloud/kb/your-site-admin-must-authorize-this-app-error-in-atlassian-cloud-apps/
- Atlassian MCP Server README (audit logging, pinning cloudId in client configuration): https://github.com/atlassian/atlassian-mcp-server

Thanks,
Syed