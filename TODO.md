# Aster acceptance outcomes

## Open sign-in and registration
“Anyone with the link can register and chat.” Require Manus sign-in before chat. On a visitor's first successful sign-in, register the account automatically; do not impose an Aster invite list. Resolve the user by the stable Manus account identity so the same account works across browsers and devices.

## Account-wide daily message limit
“Count 100/day per account across devices.” Permit each signed-in account to submit at most 100 user messages during each UTC day. Enforce the count server-side and across concurrent requests; show the remaining daily messages and explain when the account has reached its limit. Reset the allowance at the next UTC day.

## Persistent account and quota records
“Enable the database for accounts and counters.” Use the managed database to persist Manus-linked account identifiers and per-account UTC daily message counts. Do not persist chat prompt or response text in these account/quota tables.

## Live AI chat
Allow an authenticated visitor to send a prompt from the public Aster page and receive a streamed AI response. Keep provider credentials on the server, enforce the account quota before sending the message to the AI service, and show clear authentication, limit, loading, and service-error states. Visitors must not be able to call the chat API without an authenticated session.
