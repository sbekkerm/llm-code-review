import os
import click
import time
import random
from typing import Optional, List

import requests
from requests.exceptions import RequestException, Timeout

# Reasonable defaults for transient-server errors
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
SYSTEM_FALLBACK = (
    'You are a senior code reviewer. Explain intent, behavior changes, risks, testing impact, '
    'and rollout/rollback guidance in concise, actionable bullets.'
)

USER_INSTRUCTIONS = (
    'Explain intent of the following git diff. Summarize per-file themes when possible. Highlight: '
    '(1) high-level intent, (2) notable APIs/functions touched, (3) risky areas, '
    '(4) testing implications, (5) migration or rollback notes.'
)


def _load_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def chunk_text(text: str, max_chars: int, max_chunks: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    chunks, start = [], 0
    while start < len(text) and len(chunks) < max_chunks:
        end = min(start + max_chars, len(text))
        cut = text.rfind('\n@@', start, end)
        if cut == -1 or cut <= start + max_chars // 2:
            cut = end
        chunks.append(text[start:cut])
        start = cut
    if start < len(text):
        chunks.append(text[start:start + max_chars])
    return chunks


def call_llm(
    url: str,
    api_key: str,
    model: str,
    messages: list,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    timeout: float | tuple[float, float] = (10, 30),  # (connect, read)
    max_attempts: int = 5,
    base_backoff: float = 1.0,
    max_backoff: float = 10.0,
) -> str:
    """
    Call an LLM endpoint with simple exponential backoff + jitter.
    - Retries on transient errors (429, 5xx, etc).
    - Returns the assistant's message if available, otherwise JSON.
    """
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, max_attempts + 1):
        print(f"Request the {model} model to review")
        try:
            resp = requests.post(
                url + '/chat/completions',
                headers=headers,
                json=payload,
                timeout=timeout,
                allow_redirects=True,
            )
        except (Timeout, RequestException) as e:
            if attempt < max_attempts:
                sleep_s = min(max_backoff, base_backoff * (2 ** (attempt - 1)))
                sleep_s *= 0.7 + 0.6 * random.random()  # jitter
                time.sleep(sleep_s)
                continue
            raise RuntimeError(f"LLM request failed after {attempt} attempts: {e}") from e

        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                raise ValueError(f"Invalid JSON response: {resp.text[:500]}")
            content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content")
                    )
            return content.strip() if isinstance(content, str) else ""

        if resp.status_code in RETRY_STATUS and attempt < max_attempts:
            sleep_s = min(max_backoff, base_backoff * (2 ** (attempt - 1)))
            sleep_s *= 0.7 + 0.6 * random.random()
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    sleep_s = max(float(retry_after), sleep_s)
                except ValueError:
                    pass
            time.sleep(sleep_s)
            continue

        raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:500]}")

    raise RuntimeError("Failed to get response from LLM after retries.")


def load_agent_instructions(explicit_path: Optional[str]) -> str:
    candidates = [explicit_path] if explicit_path else ['.github/AGENTS.md', 'AGENTS.md']
    for p in candidates:
        if p and os.path.exists(p):
            return _load_text(p)
    return SYSTEM_FALLBACK


def llm_once(diff_fragment: str, system_text: str, url: str, key: str, model: str,
             temperature: float, max_tokens: int, timeout: int) -> str:
    messages = [
        {'role': 'system', 'content': system_text},
        {'role': 'user', 'content': f"{USER_INSTRUCTIONS}\n\n```diff\n{diff_fragment}\n```"},
    ]
    return call_llm(url, key, model, messages, temperature, max_tokens, timeout)


def multiple_pass(diff_text: str, system_text: str, url: str, key: str, model: str,
                  temperature: float, max_tokens: int, timeout: int,
                  max_chars: int, max_chunks: int) -> str:
    parts = chunk_text(diff_text, max_chars, max_chunks)
    if len(parts) == 1:
        return llm_once(parts[0], system_text, url, key, model, temperature, max_tokens, timeout)

    summaries: List[str] = []
    for i, ch in enumerate(parts, 1):
        summaries.append(f"### Part {i}\n" + llm_once(ch, system_text, url, key, model, temperature,
                                                      max_tokens, timeout))
    synthesis = (
        'Combine the following chunk summaries into a single coherent review. Avoid repetition, '
        'call out cross-file risks, and propose concrete tests.\n\n' + '\n\n'.join(summaries)
    )
    return llm_once(synthesis, system_text, url, key, model, temperature, max_tokens, timeout)


@click.command()
@click.option('--diff', 'diff_path', required=True,
              help='Path to a unified diff file')
@click.option('--out', 'out_path', type=click.Path(dir_okay=False), default='code-review.md',
              help='Where to write the Markdown PR review')
@click.option('--agents-path', type=click.Path(exists=True, dir_okay=False), default=None,
              help='Optional path to AGENTS.md. Defaults to .github/AGENTS.md or AGENTS.md')
def main(diff_path: str, out_path: str, agents_path: Optional[str]):
    url = os.environ.get('LLM_API_URL')
    key = os.environ.get('LLM_API_KEY')
    model = os.environ.get('LLM_MODEL_NAME')
    timeout = int(os.environ.get('LLM_TIMEOUT_SECONDS', 60))
    temperature = float(os.environ.get('LLM_TEMPERATURE', 0.2))
    max_tokens = int(os.environ.get('LLM_MAX_TOKENS', 700))
    max_chars = int(os.environ.get('LLM_MAX_CHARS_PER_CHUNK', 12000))
    max_chunks = int(os.environ.get('LLM_MAX_CHUNKS', 12))

    if not url or not key or not model:
        click.echo('Missing required env vars: LLM_API_URL, LLM_API_KEY, LLM_MODEL_NAME', err=True)
        raise SystemExit(1)

    diff_text = _load_text(diff_path)

    if not diff_text.strip():
        print('Error: No changes detected')
        raise SystemExit(1)

    system_text = load_agent_instructions(agents_path)

    review = multiple_pass(
        diff_text=diff_text,
        system_text=system_text,
        url=url,
        key=key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_chars=max_chars,
        max_chunks=max_chunks,
    )

    md = '# AI PR Review\n\n' + review.strip() + '\n'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)

    click.echo(out_path)


if __name__ == "__main__":
    main()
