# Contributing to L3MN05

Thank you for your interest in contributing to L3MN05!  
We're building a local-first, extensible AI-powered software and data engineering consultant. Contributions that improve skills, tools, reliability, or documentation are very welcome.

---

## Code of Conduct

This project follows a simple principle: **be kind, be constructive, and assume good intent**.  
Please treat everyone with respect. We want this to be a welcoming space for developers, consultants, and AI enthusiasts.

---

## How to Contribute

### 1. Reporting Bugs or Requesting Features

- Use the [issue templates](.github/ISSUE_TEMPLATE/) when opening an issue.
- For **security vulnerabilities**, please follow our [Security Policy](SECURITY.md) instead of opening a public issue.

### 2. Setting Up Your Development Environment

```bash
# 1. Clone the repo
git clone https://github.com/nightmoose/l3mn05.git
cd l3mn05

# 2. Install dependencies (if running outside Docker)
pip install -r requirements.txt

# 3. Start the stack
docker compose up -d

# 4. Chat with Horace or run workers directly
```

See [architecture.md](architecture.md) for a full explanation of the v10+ structure.

### 3. Adding a New Skill (Most Common Contribution)

1. Create a new folder: `skills/your_skill_name/`
2. Implement the skill following the emerging `BaseSkill` pattern (see existing skills for reference).
3. Register any new tools it needs in `tools/registry.py`.
4. Add your skill to the `enabled_skills` list in `config.yaml` for testing.
5. Open a Pull Request with a clear description.

**Tip**: Start small. Many skills can be 50–150 lines of well-structured code.

### 4. Improving Existing Skills or Tools

- Focus on reliability, better error handling, and clearer prompts.
- Add unit tests when possible (we're building test coverage).
- Update documentation in `architecture.md` if behavior changes significantly.

### 5. Documentation Improvements

- Fix typos, clarify confusing sections, or add examples.
- The `architecture.md` file is the single source of truth for how the system works — keep it up to date.

---

## Pull Request Guidelines

- Please use the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
- Keep PRs focused (one feature or fix per PR is ideal).
- Update relevant documentation (`README.md`, `architecture.md`, or inline comments).
- Make sure your changes don't break the existing worker flow.

We appreciate small, well-tested contributions over large untested ones.

---

## Development Philosophy

- **Local first** — New features should work offline with Ollama whenever possible.
- **Modular** — Prefer adding a new skill or tool over modifying core workers.
- **Observable** — Use the logging patterns already established in `tools/registry.py`.
- **Client-friendly** — Changes should respect per-client configuration and isolation.

---

## Questions?

- Open a [feature request](.github/ISSUE_TEMPLATE/feature_request.md) or discussion.
- Or just start a conversation in the repo — we're happy to help you get started.

---

**Thank you for helping make L3MN05 better!**  
Every skill you add, bug you fix, or doc you improve makes the system more powerful for everyone.