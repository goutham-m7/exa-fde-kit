# Two retrieval tools over stdio

Point the host's local MCP server command at `uv --directory /absolute/path/to/exa-fde-kit run python -m exa_fde_kit.mcp_server --offline`. Use a question from `exa-fde-kit ask --help`'s case set (the tool takes the question text, not its ID). Remove `--offline` and pass a restricted EXA_API_KEY via the host's secret environment for paid calls. No inbound port, dynamic endpoints, disk cache or customer credentials in tool arguments.

| Tool | Returns | Network in live mode |
|---|---|---|
| search_with_citations | Up to three distinct HTTP(S) source links with ranks, not a relevance judgment | One [Search](https://docs.exa.ai/reference/search.md) before retries |
| answer_with_evidence | Source passages with URLs, or an explicit abstention | Search plus at most one batch of [Contents](https://docs.exa.ai/reference/get-contents.md) before retries |

This small server implements the [2025-11-25 MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle), newline-delimited JSON-RPC, ping and [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools). Calls execute serially. It does not advertise prompts, resources, tasks, or an HTTP transport. Provider failures are tool errors, not JSON-RPC framing errors. Parsed tool results identify synthetic versus live mode. The two-tool subset avoids installing a web server and schema stack just to use stdio. Use the official SDK for a broader server.

## How an FDE would use this with a customer

Give a support agent only the evidence tool initially. Try a known question and a missing one, verify attribution and abstention, then let the host display sources. Do not execute instructions found in retrieved text. Use [Exa's hosted MCP](https://docs.exa.ai/get-started/exa-mcp.md) for general Exa functionality. This local adapter exists for this kit's replay, extraction and test contract; it does not wrap the hosted MCP or Exa's generative [/answer](https://docs.exa.ai/reference/answer.md) endpoint.
