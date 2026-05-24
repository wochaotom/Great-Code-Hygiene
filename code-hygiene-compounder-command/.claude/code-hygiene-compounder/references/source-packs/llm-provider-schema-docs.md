# Source Pack: LLM Provider Tool and Structured Output Documentation

- Source ID: `llm-provider-schema-docs`
- Activation: llm_tool_schema
- Official links:
  - https://developers.openai.com/api/docs/guides/function-calling
  - https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
  - https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
  - https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use
  - https://ai.google.dev/gemini-api/docs/function-calling
  - https://ai.google.dev/gemini-api/docs/structured-output
  - https://developers.google.cn/terms/site-policies?hl=en
- License note: Provider docs are official compatibility references. Google AI/Developers documentation uses the standard Google site policy for CC BY 4.0 content and Apache 2.0 code samples where that notice applies. OpenAI and Anthropic documentation pages are treated as attribution-required, link-backed operational references; do not copy their prose or code into package text unless reuse terms are explicitly accepted.

## Distilled Checks

- Treat LLM tool and structured-output schemas as provider-facing interface contracts, not as generic JSON Schema that every model/API mode accepts unchanged.
- Keep the canonical local schema separate from provider adapters; compile or normalize only at the boundary where the target provider, model, and API mode are known.
- Validate the provider-supported subset explicitly: tool/function names, descriptions, required fields, enums, object nesting, unsupported keywords, `$ref` handling, strictness flags, and additional-property behavior.
- Fail closed on adapter or provider validation errors with diagnostics that name the provider, model/API mode, schema hash or version, and rejected field without leaking secrets or prompt data.
- Add local canaries for positive schemas and deliberately unsupported schemas before relying on remote API behavior; provider calls may support audit evidence but should not be the only promotion oracle.
- Preserve ordinary correctness, security, compatibility, and local integration controls when changing AI SDK, MCP, or provider bridge schema code.
- Document the adapter contract so future maintainers can see which provider subset is supported and when the mapping should be revisited.

## PASS-100 Focus

`correctness`, `tests`, `local_integration`, `security`, `documentation`, `maintainability`
