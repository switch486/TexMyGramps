# Environment Configuration Setup

## Overview
The GrampsBook project uses environment variables for API tokens and configuration. These are automatically loaded through a multi-layer approach to support both interactive development and batch processing.

## Environment Variable Loading Flow

### 1. Shell Script Level (Bash/Zsh)
When you run one of the main orchestration scripts:
- `01_load_complete.sh` (load data from Gramps API)
- `02_generate_subpages.sh` (render LaTeX pages)
- `03_build_complete.sh` (build final PDF)

**Each script automatically loads environment variables from:**
- `token.env` (project root)
- `local.env` (project root)
- `.env` (project root)
- `api_token.env` (project root)
- `src/scripts/gramps_api_token.env` (scripts directory)

The script sources the **first found** `.env` file and exports all variables so they're available to child processes.

**Log output:**
```
[ENV] Loading environment from: /path/to/api_token.env
```

### 2. Python Script Level
When Python scripts (like `render_person_tex.py`) are called from the shell scripts:

**Step 1:** Shell exports environment variables (e.g., `export MAPBOX_TOKEN=...`)
**Step 2:** Python script inherits exported variables via `os.environ`
**Step 3:** Python script also loads `.env` files via `python-dotenv` as a fallback

This dual approach ensures:
- Environment variables from shell scripts take priority
- Direct Python execution also works (via python-dotenv fallback)

**Log output from Python:**
```
[ENV] Loading environment from /path/to/api_token.env
[MAP] Found MAPBOX_TOKEN in environment (length: 128)
```

## Setting Up Your Environment

### Option 1: Use Your Existing `api_token.env`
If you already have `api_token.env` with Gramps API credentials, just add:
```
MAPBOX_TOKEN=pk.your_mapbox_token_here
```

### Option 2: Create a New Token File
Create `token.env` at project root:
```
MAPBOX_TOKEN=pk.your_mapbox_token_here
GRAMPS_API_TOKEN=your_gramps_token
```

### Running the Scripts
No special setup needed - just run normally:
```
./01_load_complete.sh
./02_generate_subpages.sh
./03_build_complete.sh
```

The environment will be automatically loaded.

## Troubleshooting

### MAPBOX_TOKEN not found
Check the logs:
```
[MAP] WARNING: MAPBOX_TOKEN not found in environment
```

**Solution:** Make sure your `.env` file contains `MAPBOX_TOKEN=pk.xxx` and is in one of the supported locations.

### Environment not loaded in shell
Check for `[ENV]` log output when starting scripts:
```
[ENV] Loading environment from: /path/to/api_token.env
```

If missing, the file doesn't exist or isn't named correctly. Verify the filename and location.

### Direct Python script execution
If running `render_person_tex.py` directly (not via shell script), use:
```
python3 src/scripts/render_person_tex.py --page-dir <dir>
```

The script will load `.env` files automatically via python-dotenv.

Or manually:
```
source token.env
python3 src/scripts/render_person_tex.py --page-dir <dir>
```

## Supported Environment Variables

| Variable | Usage | Location |
|----------|-------|----------|
| `MAPBOX_TOKEN` | Static map generation | Used by `render_person_tex.py` |
| `GRAMPS_API_TOKEN` | Gramps API authentication | Used by `gramps_api_loader.py` |
| `GRAMPS_API_KEY` | Alternative Gramps credential | Used by `gramps_api_loader.py` |

## File Search Order

Shell scripts and Python check in this order:
1. `token.env`
2. `local.env`
3. `.env`
4. `api_token.env` (shell) / `gramps_api_token.env` (Python)
5. `gramps_api.local.env` (Python only)

**First found file is used** - so if `token.env` exists, `local.env` won't be checked.

## Best Practices

1. **Use `token.env`** - Clear naming, first in search order
2. **Don't commit `.env` files** - They're in `.gitignore`
3. **Copy from example** - Use `token.env.example` as template
4. **Keep it simple** - One `.env` file per developer/environment

## Security Notes

- **Never commit** your `.env` files with real tokens
- **Use `.gitignore`** to protect these files (already configured)
- **Rotate tokens** if accidentally committed
- **Separate concerns** - Use different tokens for dev/prod if possible
