# Security

Report vulnerabilities through
[private vulnerability reporting](https://github.com/adriandlam/notability-mcp/security/advisories/new),
not in a public issue.

The issues that matter most here:

- anything that could leak your `nb-auth-token` or send it somewhere other than notability.com
- a note, PDF or server response that makes `sync` or the server run code or touch files outside
  its index
- the server making network requests, or reading anything other than its index

Only the latest commit on `main` is supported.
