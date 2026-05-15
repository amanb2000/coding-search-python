#!/usr/bin/env bash
# One-shot installer for the `coding-search` CLI.
#
#   curl -fsSL https://raw.githubusercontent.com/andre-fu/coding-search-python/main/install.sh | bash
#
# What it does:
#   1. Installs `uv` (Astral's Python toolchain manager) if it's not already on $PATH.
#   2. Uses `uv tool install` to put `coding-search` in an isolated venv under ~/.local.
#   3. Wires ~/.local/bin into your shell's $PATH so the CLI just works in new shells.
#
# Safe to re-run. No sudo. Lands entirely in $HOME.

set -euo pipefail

REPO_URL="${CODING_SEARCH_REPO_URL:-git+https://github.com/andre-fu/coding-search-python.git}"

# ---- pretty output ----------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD=$(printf '\033[1m')
    DIM=$(printf '\033[2m')
    GREEN=$(printf '\033[32m')
    YELLOW=$(printf '\033[33m')
    RED=$(printf '\033[31m')
    RESET=$(printf '\033[0m')
else
    BOLD=""; DIM=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

info()  { printf '%s==>%s %s\n' "${BOLD}${GREEN}" "${RESET}" "$*"; }
warn()  { printf '%s==>%s %s\n' "${BOLD}${YELLOW}" "${RESET}" "$*" >&2; }
error() { printf '%serror:%s %s\n' "${BOLD}${RED}" "${RESET}" "$*" >&2; }
step()  { printf '   %s%s%s\n' "${DIM}" "$*" "${RESET}"; }

# ---- preflight --------------------------------------------------------------
case "$(uname -s)" in
    Linux|Darwin) ;;
    *)
        error "Unsupported OS: $(uname -s). This installer supports macOS and Linux."
        error "On Windows, use WSL or install manually: pipx install ${REPO_URL}"
        exit 1
        ;;
esac

for cmd in curl uname; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        error "Required command '$cmd' is not installed."
        exit 1
    fi
done

# ---- 1. uv ------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    info "Installing uv (Python toolchain manager)..."
    # Astral's official installer — drops uv into ~/.local/bin or ~/.cargo/bin.
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # The uv installer adds its bin dir to the *user's shell config* but
    # doesn't export it into the current shell, so source the env file it
    # writes — or fall back to the conventional locations.
    if [ -f "${HOME}/.local/bin/env" ]; then
        # shellcheck disable=SC1091
        . "${HOME}/.local/bin/env"
    fi
    for candidate in "${HOME}/.local/bin" "${HOME}/.cargo/bin"; do
        case ":${PATH}:" in
            *":${candidate}:"*) ;;
            *) [ -d "$candidate" ] && PATH="${candidate}:${PATH}" ;;
        esac
    done
    export PATH

    if ! command -v uv >/dev/null 2>&1; then
        error "uv installation completed but 'uv' is still not on PATH."
        error "Try opening a new shell and re-running this installer."
        exit 1
    fi
    step "uv $(uv --version 2>/dev/null | awk '{print $2}') installed"
else
    step "uv already present: $(uv --version 2>/dev/null)"
fi

# ---- 2. coding-search -------------------------------------------------------
info "Installing coding-search from ${REPO_URL}..."
# --force makes the script idempotent: re-running upgrades to latest main.
uv tool install --force "${REPO_URL}"

# ---- 3. PATH wiring ---------------------------------------------------------
info "Wiring uv's tool bin directory into your shell PATH..."
# `uv tool update-shell` appends the right line to each detected rc file
# (.bashrc, .zshrc, fish config, etc.) and is a no-op if already wired.
uv tool update-shell || warn "uv tool update-shell reported an issue — your PATH may already be set."

# Also export for the current shell in case the user is sourcing this script
# rather than piping it.
UV_TOOL_BIN="$(uv tool dir --bin 2>/dev/null || echo "${HOME}/.local/bin")"
case ":${PATH}:" in
    *":${UV_TOOL_BIN}:"*) ;;
    *) export PATH="${UV_TOOL_BIN}:${PATH}" ;;
esac

# ---- 4. verify --------------------------------------------------------------
if command -v coding-search >/dev/null 2>&1; then
    VERSION=$(coding-search --version 2>/dev/null || echo "installed")
    info "${GREEN}${BOLD}coding-search is installed:${RESET} ${VERSION}"
    step "Try it:  coding-search \"python asyncio gather\""
else
    warn "Install completed, but 'coding-search' isn't on PATH in this shell."
    warn "Open a new terminal, or run:  export PATH=\"${UV_TOOL_BIN}:\$PATH\""
fi
