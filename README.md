# LLM Code Review

An intelligent CI/CD tool that leverages Large Language Models (LLMs) to automatically review pull/merge requests. This tool analyzes git diffs and provides comprehensive code reviews with insights, suggestions, and risk assessments.

## Features

- 🤖 **AI-Powered Reviews**: Uses any OpenAI-compatible LLM API for intelligent code analysis
- 📊 **Smart Chunking**: Automatically splits large diffs into manageable chunks for review
- 🔄 **Retry Logic**: Built-in exponential backoff and error handling for reliable API calls
- 📝 **Markdown Output**: Generates clean, readable review reports
- ⚙️ **Configurable**: Extensive customization via environment variables
- 🎯 **Custom Instructions**: Support for project-specific review guidelines via AGENTS.md
- 🚀 **CI/CD Ready**: Designed for seamless integration into automated workflows

## Installation

### Using pip

```bash
pip install git+https://github.com/yourusername/llm-code-review.git
```

### From source

```bash
git clone https://github.com/yourusername/llm-code-review.git
cd llm-code-review
pip install .
```

## Quick Start

1. **Set up your environment variables:**

```bash
export LLM_API_URL="https://api.openai.com/v1"
export LLM_API_KEY="your-api-key-here"
export LLM_MODEL_NAME="gpt-4"
```

2. **Generate a git diff:**

```bash
git diff main..feature-branch > changes.diff
```

3. **Run the code review:**

```bash
llm-code-review --diff changes.diff --out review.md
```

## Usage

### Basic Usage

```bash
llm-code-review --diff <path-to-diff-file> [OPTIONS]
```

### Command Line Options

- `--diff` (required): Path to the unified diff file to review
- `--out`: Output path for the markdown review (default: `code-review.md`)
- `--agents-path`: Path to custom AGENTS.md file with review instructions

### Examples

**Basic review:**
```bash
llm-code-review --diff changes.diff
```

**Custom output file:**
```bash
llm-code-review --diff changes.diff --out my-review.md
```

**With custom agent instructions:**
```bash
llm-code-review --diff changes.diff --agents-path .github/AGENTS.md
```

## Configuration

Configure the tool using environment variables:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_URL` | Base URL for the LLM API | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API key for authentication | `sk-...` |
| `LLM_MODEL_NAME` | Model to use for reviews | `gpt-4`, `claude-3-opus-20240229` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_TIMEOUT_SECONDS` | `60` | API request timeout |
| `LLM_TEMPERATURE` | `0.2` | Model temperature (0.0-2.0) |
| `LLM_MAX_TOKENS` | `700` | Maximum tokens per response |
| `LLM_MAX_CHARS_PER_CHUNK` | `12000` | Characters per diff chunk |
| `LLM_MAX_CHUNKS` | `12` | Maximum number of chunks |

## Custom Review Instructions

Create an `AGENTS.md` file in your repository root or `.github/` directory to provide custom review instructions:

```markdown
# Custom Review Guidelines

You are a senior code reviewer for our team. Focus on:

1. **Security**: Flag potential security vulnerabilities
2. **Performance**: Identify performance bottlenecks
3. **Maintainability**: Ensure code follows our standards
4. **Testing**: Verify adequate test coverage

## Specific Guidelines

- Always check for proper error handling
- Ensure database queries are optimized
- Verify API endpoints follow our naming conventions
```

## CI/CD Integration

### GitHub Actions

```yaml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Generate diff
        run: |
          git diff origin/${{ github.base_ref }}..HEAD > changes.diff
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install llm-code-review
        run: pip install git+https://github.com/yourusername/llm-code-review.git
      
      - name: Run AI Review
        env:
          LLM_API_URL: ${{ secrets.LLM_API_URL }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_MODEL_NAME: "gpt-4"
        run: llm-code-review --diff changes.diff --out ai-review.md
      
      - name: Comment PR
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('ai-review.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: review
            });
```

### GitLab CI

```yaml
ai_review:
  stage: review
  image: python:3.12
  script:
    - pip install git+https://github.com/yourusername/llm-code-review.git
    - git diff origin/main..HEAD > changes.diff
    - llm-code-review --diff changes.diff --out ai-review.md
    - cat ai-review.md
  artifacts:
    reports:
      junit: ai-review.md
  only:
    - merge_requests
```

## Requirements

- Python 3.12+
- Git
- Access to an OpenAI-compatible LLM API

## Dependencies

- `click`: Command-line interface
- `requests`: HTTP client for API calls

## How It Works

1. **Diff Analysis**: Reads the provided git diff file
2. **Smart Chunking**: Splits large diffs into manageable pieces at logical boundaries
3. **LLM Review**: Sends each chunk to the configured LLM for analysis
4. **Synthesis**: Combines multiple chunk reviews into a cohesive final report
5. **Output**: Generates a markdown file with the complete review

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the terms specified in the LICENSE file.
