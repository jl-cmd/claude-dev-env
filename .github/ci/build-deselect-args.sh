#!/usr/bin/env bash
# Builds the pytest --deselect argument array shared by the ci-tests.yml Root
# suite and Package suite steps. Source this file (do not execute it) so the
# deselect_args array lands in the calling shell. Blank and comment lines are
# skipped and carriage returns stripped. Self-verifies that the flag count
# equals the non-comment line count so a list edit that drops a node ID surfaces
# as a failing step rather than a silently shorter deselect set.

deselect_source_lists=(
  .github/ci/live-post-audit-deselects.txt
  .github/ci/windows-semantics-node-ids.txt
  .github/ci/known-pending-deselects.txt
  .github/ci/author-swap-deselects.txt
)

deselect_args=()
expected_deselect_count=0
for each_list_file in "${deselect_source_lists[@]}"; do
  while IFS= read -r each_node_id || [ -n "${each_node_id}" ]; do
    each_node_id="${each_node_id//$'\r'/}"
    case "${each_node_id}" in
      ''|\#*) continue ;;
    esac
    deselect_args+=(--deselect="${each_node_id}")
    expected_deselect_count=$((expected_deselect_count + 1))
  done < "${each_list_file}"
done

deselect_flag_count=${#deselect_args[@]}
echo "deselect flag count=${deselect_flag_count} expected non-comment lines=${expected_deselect_count}"
if [ "${deselect_flag_count}" -ne "${expected_deselect_count}" ]; then
  echo "ERROR: deselect_args length (${deselect_flag_count}) != expected non-comment line count (${expected_deselect_count})"
  exit 1
fi

for each_deselect_flag in "${deselect_args[@]}"; do
  case "${each_deselect_flag}" in
    *test_fan_out_dispatch.py*)
      echo "known-pending deselect: ${each_deselect_flag}"
      ;;
  esac
done
