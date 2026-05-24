# Chatbot Profiles

Use these profiles when a web chatbot cannot install the native Codex or Claude
Code package.

These files are setup instructions for reusable chatbot personas:

- `chatgpt-gpt-instructions.md`: paste into a Custom GPT's Instructions field.
- `claude-project-instructions.md`: paste into Claude Project instructions.
- `gemini-gem-instructions.md`: paste into Gemini Gem instructions.

For each platform, add this file as knowledge or context when possible:

```text
portable-prompts/code-hygiene-compounder-chat.md
```

Connectors can help the chatbot read a GitHub repo, Google Drive folder, or
uploaded files. They do not automatically install this workflow. The profile
instructions tell the chatbot when and how to use the portable prompt.

Great Code Hygiene may improve names and comments when they affect correctness,
maintainability, reviewability, or user-facing diagnostics. Use a separate
humanize-code pass for broad readability-only renaming or de-jargoning.

## Setup Checklist

1. Create the Custom GPT, Claude Project, or Gemini Gem.
2. Paste the matching instruction file into the platform's instruction field.
3. Upload or attach `portable-prompts/code-hygiene-compounder-chat.md` as
   knowledge/context if the platform supports files.
4. Enable only the connectors needed for the task, such as GitHub or Google
   Drive.
5. Start with a specific request, for example: "Review this repository with Code
   Hygiene Compounder and report verification evidence."

## Limits

Web chatbots may not have shell, test, git, filesystem, or package-install
access. They must not claim local edits or passing checks unless the platform
actually provides tool output or the user supplies it.
