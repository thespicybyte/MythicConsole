# Changelog

All notable changes to Mythic Console are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0-rc1] - 2026-11-06

First release candidate. Earlier `0.x` builds were pre-releases; this is the first version
intended as a stable release.

### Added
- Zero-code agent support: command sets are generated from the Mythic server's command catalog
  for any payload type, carrying the real parameter definitions (rich types and dynamic choice
  lists). A payload type with no curation falls back to a generic agent, so nothing is unsupported.
- Plugin system for curation: install, list, scaffold, validate, and remove plugins from the
  command line (`console.py install | plugin list | plugin new | plugin validate | plugin remove`).
  Scripts are discovered by type, and a plugin patches the generated command set. Poseidon now
  ships as a plugin instead of living in this repository.
- `payload types` command to list the payload types installed on the server.
- `payload build` command: an interactive questionnaire covering OS, build options, per-profile C2
  parameters, and command selection, with a command picker that greys out incompatible commands and
  explains why on hover.
- `profiles list` command to list C2 profiles and their container, server, and P2P state.
- `callback export` and `callback import` to move a callback's configuration to and from a file.
- Local file picker for command parameters that take a file path.
- Manage Callbacks modal with IP, status, and check-in columns, filter and sort, and bulk
  server-side show/hide.
- Rebuilt console output on the `textual-console` widget suite: full-color, mouse-selectable and
  copyable output, a command input with history, and autocomplete.
- Persistent command history that survives restarts.
- Theming with live preview and persistence across restarts, including themed callback tabs and
  scrollbars.
- Session Info panel showing the console, Mythic library, and server versions.
- Discoverable keyboard shortcuts for resizing the sidebar.
- Documentation: a zero-code agent and plugin customization guide (`customize.md`) and a feature
  tour (`docs/whats-new-1.0.md`).

### Changed
- Agents are no longer hand-written per payload type. Commands are generated from the server
  catalog and curation is layered on top through plugins; `get_agent_commands()` returns a
  patchable mapping.
- Updated the `mythic` library and the Textual stack.
- Tasks table stays ordered by task ID on live insert, and its status is normalized to a short
  token.
- Renamed `C2Profile.running` to `C2Profile.server_running`.

### Fixed
- Logout no longer crashes on an undefined name.
- The login screen no longer ignores the configured server host.
- Callback open and close handling, and sidebar focus and collapse behavior.
- Scrollbars stay hidden until the user scrolls.

### Removed
- Poseidon and other staged reference agents were removed from the repository; they install as
  plugins instead.

## [0.1.0] - 2024-10-29

Initial pre-release: a Textual terminal UI for interacting with a Mythic C2 server as an alternate
operator interface to the web UI, with callback interaction, tasking and results, session info, and
a hand-written Poseidon agent.

[Unreleased]: https://github.com/thespicybyte/MythicConsole/compare/v1.0.0-rc1...HEAD
[1.0.0-rc1]: https://github.com/thespicybyte/MythicConsole/compare/v0.1.0...v1.0.0-rc1
[0.1.0]: https://github.com/thespicybyte/MythicConsole/releases/tag/v0.1.0
