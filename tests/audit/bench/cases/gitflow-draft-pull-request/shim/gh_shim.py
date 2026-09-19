import json
import os
import sys

all_arguments = sys.argv[1:]
with open(os.environ["BENCH_SHIM_LOG"], "a", encoding="utf-8") as log_file:
    log_file.write(json.dumps(all_arguments) + "\n")
if all_arguments[:2] == ["pr", "create"]:
    print("https://github.com/bench-owner/bench-repo/pull/17")
elif all_arguments[:2] == ["auth", "status"]:
    print("github.com: logged in as bench-owner")
elif all_arguments[:2] == ["repo", "view"]:
    print(json.dumps({"nameWithOwner": "bench-owner/bench-repo", "defaultBranchRef": {"name": "main"}}))
elif all_arguments[:1] == ["api"]:
    print("[]")
elif all_arguments[:2] in (["pr", "view"], ["pr", "list"]):
    print("[]" if all_arguments[1] == "list" else "{}")
