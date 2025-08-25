#!/usr/bin/env bash
set -Eeuo pipefail

parse_args() {
  if (($# != 6)); then
    printf "Usage: %s <dep_type_var> <update_type_var> <pr_url_var> <dep_type> <update_type> <pr_url>\n" "$0" >&2
    return 1
  fi

  local -n dep_type_ref="$1"
  local -n update_type_ref="$2"
  local -n pr_url_ref="$3"

  # Shift past the destination names and assign values
  shift 3
  dep_type_ref="$1"
  update_type_ref="$2"
  pr_url_ref="$3"
}

should_automerge() {
  local dep_type="$1"
  local update_type="$2"

  case "$dep_type" in
    direct:development* | indirect) return 0 ;;
    direct:production)
      case "$update_type" in
        version-update:semver-minor | version-update:semver-patch) return 0 ;;
      esac
      ;;
  esac
  return 1
}

main() {
  local dep_type update_type pr_url

  parse_args dep_type update_type pr_url "$@"

  printf "Dependency type: %s\n" "$dep_type"
  printf "Update type: %s\n" "$update_type"

  if [[ -z ${pr_url// /} ]]; then
    printf "Error: pr_url is empty\n" >&2
    return 2
  fi

  if ! command -v gh &> /dev/null; then
    printf "Error: gh CLI not found in PATH\n" >&2
    return 2
  fi

  if should_automerge "$dep_type" "$update_type"; then
    printf "Enabling auto-merge...\n"
    gh pr merge --auto --squash --delete-branch -- "$pr_url"
  else
    printf "Not eligible for auto-merge.\n"
  fi
}

if ! (return 0 2> /dev/null); then
  main "$@"
fi
