# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| v10+    | :white_check_mark: |
| < v10   | :x:                |

## Reporting a Vulnerability

We take the security of L3MN05 seriously. If you discover a vulnerability, please follow the responsible disclosure process below.

### How to Report

**Please do NOT open a public issue.**

Instead, email the maintainer directly at: **security@nightmoose.dev** (or open a private security advisory on GitHub if available).

Include the following information:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

### Response Timeline

- **Initial response**: Within 48 hours
- **Status update**: Within 7 days
- **Fix timeline**: Depends on severity (critical issues prioritized)

### Scope

This policy applies to:
- The core L3MN05 codebase
- Docker configuration and deployment scripts
- Integration with Jira, GitHub, Ollama, and Grok/xAI

### Out of Scope

- Issues in third-party dependencies (please report to the upstream project)
- Social engineering or physical attacks
- Issues that require physical access to a developer's machine

## Security Best Practices for Users

When running L3MN05:
- Never commit `.env` or API tokens
- Use the minimum required GitHub token scopes (`repo` write only)
- Keep your Ollama models and Docker images up to date
- Review generated code and PRs before merging
- Use branch protection rules on your own repositories

Thank you for helping keep L3MN05 and its users safe!