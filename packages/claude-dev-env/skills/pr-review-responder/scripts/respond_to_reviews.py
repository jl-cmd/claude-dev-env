#!/usr/bin/env python3
"""
Standalone script to respond to GitHub PR review comments.

Usage:
    python respond_to_reviews.py [--pr PR_NUMBER] [--auto-approve]

Requirements:
    - gh CLI installed and authenticated
    - Git repository with GitHub remote
    - Python 3.8+
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class ReviewComment:
    id: int
    path: str
    line: int
    body: str
    user: str
    created_at: str
    in_reply_to: Optional[int]


@dataclass
class FileChange:
    path: str
    lines_changed: Set[int]
    diff: str


def run_command(cmd: List[str]) -> str:
    """Run shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        print(f"Error: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def get_current_pr() -> Optional[Dict]:
    """Get PR number for current branch."""
    output = run_command(['gh', 'pr', 'view', '--json', 'number,title,url'])
    if not output:
        return None
    return json.loads(output)


def get_review_comments(pr_number: int, repo: str) -> List[ReviewComment]:
    """Fetch all review comments from PR."""
    cmd = [
        'gh', 'api',
        f'repos/{repo}/pulls/{pr_number}/comments',
        '--jq',
        '.[] | {id, path, line, body, user: .user.login, created_at, in_reply_to}'
    ]
    output = run_command(cmd)

    comments = []
    for line in output.split('\n'):
        if not line:
            continue
        data = json.loads(line)
        comments.append(ReviewComment(
            id=data['id'],
            path=data['path'],
            line=data['line'],
            body=data['body'],
            user=data['user'],
            created_at=data['created_at'],
            in_reply_to=data.get('in_reply_to')
        ))

    return comments


def get_current_user() -> str:
    """Get current GitHub username."""
    return run_command(['gh', 'api', 'user', '--jq', '.login'])


def filter_unresponded_comments(
    comments: List[ReviewComment],
    current_user: str
) -> List[ReviewComment]:
    """Filter for comments that haven't been responded to."""
    # Group comments by thread (in_reply_to chain)
    threads: Dict[int, List[ReviewComment]] = {}

    for comment in comments:
        if comment.in_reply_to is None:
            # Top-level comment
            thread_id = comment.id
        else:
            # Reply to another comment
            thread_id = comment.in_reply_to

        if thread_id not in threads:
            threads[thread_id] = []
        threads[thread_id].append(comment)

    # Find threads where we haven't replied
    unresponded = []
    for thread_id, thread_comments in threads.items():
        # Check if current user has replied in this thread
        user_replied = any(c.user == current_user for c in thread_comments)

        if not user_replied:
            # Find the original comment (first in thread)
            original = min(thread_comments, key=lambda c: c.created_at)
            if original.user != current_user:
                unresponded.append(original)

    return unresponded


def get_changed_files() -> List[FileChange]:
    """Get files changed in the last commit."""
    # Get list of changed files
    files_output = run_command(['git', 'diff', '--name-only', 'HEAD~1..HEAD'])

    changes = []
    for file_path in files_output.split('\n'):
        if not file_path:
            continue

        # Get diff for this file
        diff = run_command(['git', 'diff', 'HEAD~1..HEAD', '--', file_path])

        # Parse changed line numbers from diff
        lines_changed = set()
        for line in diff.split('\n'):
            if line.startswith('@@'):
                # Parse @@ -old_start,old_count +new_start,new_count @@
                parts = line.split(' ')
                if len(parts) >= 3:
                    new_range = parts[2]  # +new_start,new_count
                    if ',' in new_range:
                        start, count = new_range[1:].split(',')
                        start_line = int(start)
                        count_lines = int(count)
                        lines_changed.update(range(start_line, start_line + count_lines))

        changes.append(FileChange(
            path=file_path,
            lines_changed=lines_changed,
            diff=diff
        ))

    return changes


def match_comments_to_changes(
    comments: List[ReviewComment],
    changes: List[FileChange]
) -> List[tuple[ReviewComment, FileChange]]:
    """Match review comments to file changes."""
    matches = []

    changes_by_path = {c.path: c for c in changes}

    for comment in comments:
        if comment.path in changes_by_path:
            change = changes_by_path[comment.path]
            # Check if the commented line was changed
            if comment.line in change.lines_changed or not change.lines_changed:
                # Either the exact line changed, or we changed the file (good enough)
                matches.append((comment, change))

    return matches


def draft_response(comment: ReviewComment, change: FileChange) -> str:
    """Draft a concise response to a review comment."""
    # Analyze the diff to understand what changed
    diff_lines = change.diff.split('\n')

    # Look for common patterns
    if 'class ' in change.diff and '- class ' in change.diff:
        return "Removed wrapper class, using direct approach"

    if 'def ' in change.diff:
        if '+ def ' in change.diff:
            return "Extracted to shared function"
        if 'Type[' in change.diff or ': ' in change.diff:
            return "Added type hints"

    if 'import ' in change.diff:
        return "Updated imports"

    if '.css' in comment.path or 'style' in change.diff:
        return "Moved CSS values to stylesheet"

    if 'select_related' in change.diff or 'prefetch_related' in change.diff:
        return "Added query optimization to eliminate N+1"

    if comment.path.endswith('.py'):
        # Generic Python change
        return f"Updated {Path(comment.path).name}"

    # Generic fallback
    return f"Addressed feedback in {comment.path}"


def post_response(comment_id: int, response: str, repo: str) -> bool:
    """Post response to GitHub review comment."""
    formatted_response = f"✅ **Fixed**: {response}"

    try:
        run_command([
            'gh', 'api',
            f'repos/{repo}/pulls/comments/{comment_id}/replies',
            '-X', 'POST',
            '-f', f'body={formatted_response}'
        ])
        return True
    except Exception as e:
        print(f"Failed to post response: {e}", file=sys.stderr)
        return False


def get_repo_name() -> str:
    """Get owner/repo from git remote."""
    remote_url = run_command(['git', 'remote', 'get-url', 'origin'])

    # Parse GitHub URL
    # SSH: git@github.com:owner/repo.git
    # HTTPS: https://github.com/owner/repo.git

    if 'github.com' not in remote_url:
        print("Error: Not a GitHub repository", file=sys.stderr)
        sys.exit(1)

    if remote_url.startswith('git@'):
        # SSH format
        repo_part = remote_url.split(':')[1]
    else:
        # HTTPS format
        repo_part = '/'.join(remote_url.split('/')[-2:])

    # Remove .git suffix
    return repo_part.replace('.git', '')


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Respond to GitHub PR review comments'
    )
    parser.add_argument(
        '--pr',
        type=int,
        help='PR number (auto-detected if not provided)'
    )
    parser.add_argument(
        '--auto-approve',
        action='store_true',
        help='Auto-approve all responses without confirmation'
    )

    args = parser.parse_args()

    # Get PR number
    if args.pr:
        pr_number = args.pr
        pr_title = f"PR #{pr_number}"
        pr_url = ""
    else:
        pr = get_current_pr()
        if not pr:
            print("Error: No PR found for current branch", file=sys.stderr)
            print("Create a PR first or specify --pr NUMBER", file=sys.stderr)
            sys.exit(1)
        pr_number = pr['number']
        pr_title = pr['title']
        pr_url = pr['url']

    print(f"Checking PR #{pr_number}: {pr_title}")
    if pr_url:
        print(f"URL: {pr_url}")
    print()

    # Get repository name
    repo = get_repo_name()

    # Get current user
    current_user = get_current_user()

    # Fetch review comments
    print("Fetching review comments...")
    all_comments = get_review_comments(pr_number, repo)
    print(f"Found {len(all_comments)} total review comments")

    # Filter for unresponded comments
    unresponded = filter_unresponded_comments(all_comments, current_user)
    print(f"Found {len(unresponded)} unresponded comments")

    if not unresponded:
        print("\nNo unresponded comments found!")
        return

    # Get changed files
    print("\nAnalyzing recent changes...")
    changes = get_changed_files()
    print(f"Found {len(changes)} changed files in last commit")

    # Match comments to changes
    matches = match_comments_to_changes(unresponded, changes)

    if not matches:
        print("\nNo review comments match your recent changes.")
        print(f"\nReview comments are about:")
        for comment in unresponded:
            print(f"  - {comment.path}:{comment.line}")
        print(f"\nBut you changed:")
        for change in changes:
            print(f"  - {change.path}")
        return

    # Draft responses
    print(f"\nFound {len(matches)} review comments addressed:\n")

    responses = []
    for i, (comment, change) in enumerate(matches, 1):
        response = draft_response(comment, change)
        responses.append((comment, response))

        print(f"{i}. @{comment.user} on {comment.path}:{comment.line}")
        print(f"   Comment: {comment.body[:80]}...")
        print(f"   Response: ✅ **Fixed**: {response}")
        print()

    # Get approval
    if not args.auto_approve:
        answer = input(f"Post these {len(responses)} responses to the PR? (y/n) ")
        if answer.lower() != 'y':
            print("Cancelled.")
            return

    # Post responses
    print("\nPosting responses...")
    success_count = 0

    for comment, response in responses:
        if post_response(comment.id, response, repo):
            print(f"  ✓ {comment.path}:{comment.line}")
            success_count += 1
        else:
            print(f"  ✗ {comment.path}:{comment.line}")

    print(f"\nPosted {success_count}/{len(responses)} responses to PR #{pr_number}")

    if pr_url:
        print(f"View PR: {pr_url}")

    print("\nReady to push!")


if __name__ == '__main__':
    main()
