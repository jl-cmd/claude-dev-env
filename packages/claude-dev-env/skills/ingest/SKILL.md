---
name: ingest
description: Digest the codebase using gitingest into LLM-friendly text files, one per top-level folder. Use when user wants to create a text digest/summary of their repo for AI consumption.
user_invocable: true
---

# Ingest Codebase with GitIngest

## Steps

1. **Ensure gitingest is installed**: `pip install gitingest`

2. **Clone repo locally** (avoids network drive slowness and enables long paths):
   ```bash
   REMOTE=$(git remote get-url origin)
   TEMP_DIR=$(mktemp -d)/gitingest_repo
   git clone --depth 1 -c core.longpaths=true "$REMOTE" "$TEMP_DIR"
   ```

3. **Identify top-level folders** in the clone to ingest (skip `.git`, `.Codex`, `.planning`, etc.)

4. **Run gitingest Python API on each folder separately** (running separately avoids spaces-in-names breaking CLI glob patterns):
   ```python
   from gitingest import ingest

   summary, tree, content = ingest(
       folder_path,
       include_patterns=["*.py", "*.md", "*.json", "*.yaml", "*.yml", "*.cfg", "*.toml", "*.txt"],
       exclude_patterns=["**/venv/**", "**/logs/**", "**/__pycache__/**", "**/Archive/**",
                         "**/*.png", "**/*.jpg", "**/*.mp4", "**/*.gif", "**/*.pyc",
                         "**/*.rdp", "**/node_modules/**", "**/.git/**"],
       max_file_size=102400,
   )
   ```

5. **Save each digest** as `digest_<folder_name>.txt` in the corresponding source folder on the original working directory (not the temp clone)

6. **Clean up** the temp clone directory

7. **Report** file count, token count, and output paths for each folder
