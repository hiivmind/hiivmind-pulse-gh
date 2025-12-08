# GitHub Documentation Skill

Claude Code plugin providing always-current access to official GitHub documentation.

## Coverage

This plugin indexes the complete GitHub documentation including:

- **GitHub Actions** - Workflows, CI/CD, actions syntax
- **GitHub Copilot** - AI pair programming features
- **REST API & GraphQL** - API reference and guides
- **Repositories** - Branches, commits, pull requests
- **Authentication** - SSH, tokens, SSO, 2FA
- **Security** - Code scanning, Dependabot, secrets
- **Codespaces** - Cloud development environments
- **Pages** - Static site hosting
- **Issues & Projects** - Project management
- **Organizations** - Team and enterprise administration
- **GitHub CLI** - Command-line interface

## Source

- Documentation: https://docs.github.com
- Repository: https://github.com/github/docs
- Docs path: `content/`

## Usage

The skill is automatically available when the plugin is installed. Ask questions about GitHub features and the index will be consulted.

## Maintenance

To update the index after upstream changes:

```
docs-refresh
```

To add depth to specific topics:

```
docs-enhance
```

## Structure

```
github-docs/
├── .claude-plugin/plugin.json  # Plugin metadata
├── data/
│   ├── config.yaml             # Source configuration
│   └── index.md                # Documentation index
├── skills/
│   └── navigate/SKILL.md       # Navigation skill
└── README.md
```
