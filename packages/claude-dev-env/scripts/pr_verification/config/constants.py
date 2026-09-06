import re

SUCCESS_EXIT_CODE = 0
INCOMPLETE_EXIT_CODE = 3
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
GITHUB_API_URL = "https://api.github.com"
GITHUB_PAGE_SIZE = 100
UTF8_ENCODING = "utf-8"
JSON_CONTENT_TYPE = "application/json"
GITHUB_ACCEPT_TYPE = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"
AUTHORIZATION_HEADER = "Authorization"
ACCEPT_HEADER = "Accept"
CONTENT_TYPE_HEADER = "Content-Type"
API_VERSION_HEADER = "X-GitHub-Api-Version"
BEARER_PREFIX = "Bearer "
APP_JWT_ALGORITHM = "RS256"
APP_ISSUER_CLAIM = "iss"
APP_ISSUED_AT_CLAIM = "iat"
APP_EXPIRATION_CLAIM = "exp"
PULL_NUMBER_KEY = "number"
PULL_DRAFT_KEY = "draft"
PULL_MERGE_SHA_KEY = "merge_commit_sha"
PULL_BASE_KEY = "base"
PULL_HEAD_KEY = "head"
PULL_REF_KEY = "ref"
PULL_SHA_KEY = "sha"
COMMIT_PARENTS_KEY = "parents"
TOKEN_KEY = "token"
REPOSITORIES_KEY = "repositories"
PERMISSIONS_KEY = "permissions"
CONTENTS_PERMISSION_KEY = "contents"
PULL_REQUESTS_PERMISSION_KEY = "pull_requests"
STATUSES_PERMISSION_KEY = "statuses"
ISSUES_PERMISSION_KEY = "issues"
READ_PERMISSION = "read"
WRITE_PERMISSION = "write"
STATUS_STATE_KEY = "state"
STATUS_CONTEXT_KEY = "context"
STATUS_DESCRIPTION_KEY = "description"
STATUS_PENDING = "pending"
STATUS_ERROR = "error"
STATUS_FAILURE = "failure"
STATUS_SUCCESS = "success"
LOCAL_CHECKS_CONTEXT = "local-checks"
LOCAL_CHECKS_PASSED_LABEL = "local-checks:passed"
PULLS_ENDPOINT_TEMPLATE = (
    "/repos/{repository}/pulls?state=open&per_page={page_size}&page={page}"
)
PULL_ENDPOINT_TEMPLATE = "/repos/{repository}/pulls/{pull_number}"
GIT_BRANCH_REFERENCE_ENDPOINT_TEMPLATE = "/repos/{repository}/git/ref/heads/{base_ref}"
GIT_BRANCH_REF_SAFE_CHARACTERS = "/"
GIT_REFERENCE_OBJECT_KEY = "object"
GIT_REFERENCE_RESOURCE_NAME = "git reference"
COMMIT_ENDPOINT_TEMPLATE = "/repos/{repository}/git/commits/{commit_sha}"
STATUS_ENDPOINT_TEMPLATE = "/repos/{repository}/statuses/{commit_sha}"
ISSUE_LABELS_ENDPOINT_TEMPLATE = "/repos/{repository}/issues/{pull_number}/labels"
ISSUE_LABELS_PAGE_ENDPOINT_TEMPLATE = (
    "/repos/{repository}/issues/{pull_number}/labels?per_page={page_size}&page={page}"
)
ISSUE_LABEL_ENDPOINT_TEMPLATE = (
    "/repos/{repository}/issues/{pull_number}/labels/{label}"
)
ISSUE_LABELS_KEY = "labels"
INSTALLATION_TOKEN_ENDPOINT_TEMPLATE = (
    "/app/installations/{installation_id}/access_tokens"
)
GITHUB_REQUEST_ERROR_TEMPLATE = "GitHub {method} {url} returned {status_code}"
GITHUB_JSON_ERROR_TEMPLATE = "GitHub returned invalid JSON from {url}"
GITHUB_SHAPE_ERROR_TEMPLATE = "GitHub returned an invalid {resource} payload"
PULL_RESOURCE_NAME = "pull request"
PULL_LIST_RESOURCE_NAME = "pull request list"
TOKEN_RESOURCE_NAME = "installation token"
PENDING_DESCRIPTION = "Local verification is running"
FAILURE_DESCRIPTION = "A required local check failed"
ERROR_DESCRIPTION = "Local verification did not complete"
GIT_BARE_SUFFIX = ".git"
SUPERVISOR_LOCK_FILENAME = "supervisor.lock"
SUPERVISOR_LOCK_ERROR = "Another verification supervisor owns this cache root"
SUPERVISOR_LOCK_IO_ERROR = "Verification supervisor lock file is unavailable"
SUPERVISOR_LOCK_FILE_MODE = 0o600
REPOSITORY_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
