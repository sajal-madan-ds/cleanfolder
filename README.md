# CleanFolder

LLM-powered folder cleaning agent for macOS. Scans any directory, detects duplicates, categorizes files, flags clutter, and helps you reclaim storage — with intelligent suggestions from your choice of LLM.

## Features

- **Three-tier duplicate detection** — exact hash matches, fuzzy filename matching, and LLM-assisted grouping
- **Smart categorization** — auto-classifies files into Images, Videos, Documents, Archives, Installers, Code, etc.
- **Clutter detection** — flags large files, old files, and temporary/incomplete downloads
- **LLM-powered suggestions** — get AI cleanup recommendations tailored to your folder
- **Multi-provider LLM support** — OpenAI, Anthropic, Ollama (local), vLLM (self-hosted)
- **Safe by default** — dry-run mode, macOS Trash (recoverable), confirmation prompts
- **Rich terminal UI** — colored tables, progress bars, and clean reports via Rich
- **Markdown export** — save analysis reports for later review

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Astral's fast Python package manager)

### Install

```bash
# Clone the repo
git clone <repo-url> && cd Cleaning_Folder_Files_mac

# Install dependencies (uv handles everything)
uv sync
```

### Set up your LLM provider

Copy the example env file and add your API key(s):

```bash
cp .env.example .env
```

Edit `.env` and set at least one:

```
OPENAI_API_KEY=sk-your-key-here
# or
ANTHROPIC_API_KEY=sk-ant-your-key-here
# or use Ollama locally (no key needed)
```

### Run

```bash
# Scan your Downloads folder (dry-run, safe)
uv run cleanfolder scan ~/Downloads

# Use a specific LLM provider
uv run cleanfolder scan ~/Downloads --provider openai

# Skip LLM entirely (offline mode)
uv run cleanfolder scan ~/Downloads --no-llm

# Only look for duplicates
uv run cleanfolder scan ~/Downloads --duplicates-only

# Export report to markdown
uv run cleanfolder scan ~/Downloads --export report.md

# Actually clean up (trash duplicates)
uv run cleanfolder scan ~/Downloads --action trash-duplicates --execute

# Organize files into category folders
uv run cleanfolder scan ~/Downloads --action organize --execute

# View current config
uv run cleanfolder config
```

## CLI Reference

```
Usage: cleanfolder scan [OPTIONS] FOLDER

Options:
  -p, --provider [openai|anthropic|ollama|vllm]
                          LLM provider (auto-detects if omitted)
  --dry-run / --execute   Preview changes (default) or execute them
  --duplicates-only       Only scan for duplicates
  --config FILE           Path to config.yaml
  --export FILE           Export report to markdown
  --max-files INTEGER     Override max file limit (default: 10000)
  --no-llm                Skip all LLM calls
  --action [report|trash-duplicates|trash-temp|organize|archive]
                          Action to perform (default: report)
```

## LLM Provider Setup

### OpenAI

Set `OPENAI_API_KEY` in your `.env`. Uses `gpt-4o-mini` by default (fast and cheap). Change the model in `config.yaml`.

### Anthropic

Set `ANTHROPIC_API_KEY` in your `.env`. Uses `claude-sonnet-4-20250514` by default.

### Ollama (local, free)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3`
3. Run: `uv run cleanfolder scan ~/Downloads --provider ollama`

No API key needed — runs entirely on your machine.

### vLLM (self-hosted)

1. Start your vLLM server with an OpenAI-compatible endpoint
2. Set `base_url` in `config.yaml` under `llm.vllm`
3. Run: `uv run cleanfolder scan ~/Downloads --provider vllm`

## Configuration

Edit `config.yaml` to customize behavior:

```yaml
llm:
  default_provider: openai
  fallback_order: [openai, anthropic, ollama, vllm]
  openai:
    model: gpt-4o-mini
  anthropic:
    model: claude-sonnet-4-20250514
  ollama:
    model: llama3
    base_url: http://localhost:11434
  vllm:
    model: meta-llama/Llama-3-8b
    base_url: http://localhost:8000

scan:
  skip_hidden: true
  skip_patterns: [".DS_Store", "__MACOSX", "Thumbs.db"]
  large_file_threshold_mb: 100
  old_file_days: 90
  max_files: 10000
```

## How It Works

1. **Scan** — Recursively walks the target folder, collecting file metadata (name, size, extension, dates, MIME type)
2. **Hash** — Lazily computes SHA-256 hashes only for files with matching sizes (fast)
3. **Detect duplicates** — Three tiers:
   - Exact: identical file content (same hash)
   - Near: similar filenames (`report.pdf` vs `report (1).pdf`)
   - LLM: AI identifies ambiguous duplicate patterns
4. **Categorize** — Groups files by type, flags large/old/temp files
5. **Report** — Rich terminal output with tables and summaries
6. **Act** — Optionally trash duplicates, remove temp files, organize into folders, or archive old files

## Safety

- **Dry-run by default** — nothing is moved or deleted unless you pass `--execute`
- **Trash, not delete** — uses macOS Trash so files are always recoverable
- **Confirmation prompts** — asks before every destructive action
- **Configurable exclusions** — skip patterns protect important files

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run a quick scan without LLM
uv run cleanfolder scan /tmp --no-llm
```

## License

MIT
