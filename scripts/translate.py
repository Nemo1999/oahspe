#!/usr/bin/env python3
"""Translate Oahspe verse JSON into zh_hant, zh_hans, ja via OpenAI."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content" / "books"
BOOKS_JSON = ROOT / "content" / "meta" / "books.json"

LANG_KEYS = ("zh_hant", "zh_hans", "ja")

SYSTEM_PROMPT = (
    "You are translating the Oahspe Bible (1882), a spiritual text with archaic English. "
    "Preserve the formal, reverent register. "
    "Special terms like Jehovih, Corpor, Es, Ethe, Atmospherea, I'hin, I'huan, Se'muan, "
    "Kosmon, Oahspe must be transliterated consistently, not translated. "
    "Return ONLY a JSON array of translated strings in the same order as the input. "
    "Do not add any explanation or markdown fences."
)

LANG_NAMES = {
    "zh_hant": "Traditional Chinese",
    "zh_hans": "Simplified Chinese",
    "ja": "Japanese",
}

BATCH_SIZE = 20


def load_chapters(book_slug: str | None) -> list[tuple[Path, dict]]:
    chapters = []
    if book_slug and book_slug != "all":
        dirs = [CONTENT_DIR / book_slug]
    else:
        dirs = sorted(CONTENT_DIR.iterdir())
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("chapter-*.json")):
            chapters.append((p, json.loads(p.read_text())))
    return chapters


def translate_batch(client, verses_en: list[str], lang: str, model: str) -> list[str]:
    """Call OpenAI to translate a batch of verses. Returns translated strings."""
    from openai import OpenAI  # lazy import — not available at module load time in non-translate runs

    user_msg = json.dumps(verses_en, ensure_ascii=False)
    lang_name = LANG_NAMES[lang]

    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Translate the following verses into {lang_name}:\n{user_msg}",
                    },
                ],
                temperature=0.2,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            raw = raw.strip("` \n")
            if raw.startswith("json"):
                raw = raw[4:].strip()
            translations = json.loads(raw)
            if isinstance(translations, list) and len(translations) == len(verses_en):
                return translations, response.usage
            raise ValueError(f"Unexpected response shape: {translations!r}")
        except Exception as e:
            if attempt == 4:
                raise
            wait = 2 ** attempt
            tqdm.write(f"  Retry {attempt+1}/5 after {wait}s: {e}")
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description="Translate Oahspe verses with OpenAI")
    parser.add_argument("--book", default="all", help="Book slug or 'all'")
    parser.add_argument("--lang", default="all", choices=[*LANG_KEYS, "all"])
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--force", action="store_true", help="Re-translate already translated verses")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Lazy import so the module is importable without openai installed
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed. pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    target_langs = LANG_KEYS if args.lang == "all" else (args.lang,)

    chapters = load_chapters(args.book)
    if not chapters:
        print(f"No chapters found for book={args.book!r}")
        sys.exit(1)

    total_prompt_tokens = 0
    total_completion_tokens = 0

    for lang in target_langs:
        print(f"\n=== Translating → {LANG_NAMES[lang]} ===")
        for path, chapter in tqdm(chapters, desc=lang, unit="ch"):
            verses = chapter["verses"]
            to_translate = [
                (i, v) for i, v in enumerate(verses)
                if (v[lang] is None or args.force) and v["en"]
            ]
            if not to_translate:
                continue

            changed = False
            for batch_start in range(0, len(to_translate), BATCH_SIZE):
                batch = to_translate[batch_start : batch_start + BATCH_SIZE]
                indices = [i for i, _ in batch]
                texts = [v["en"] for _, v in batch]

                translations, usage = translate_batch(client, texts, lang, args.model)
                total_prompt_tokens += usage.prompt_tokens
                total_completion_tokens += usage.completion_tokens

                for idx, trans in zip(indices, translations):
                    verses[idx][lang] = trans
                changed = True
                time.sleep(0.1)  # gentle rate limiting

            if changed:
                chapter["verses"] = verses
                path.write_text(json.dumps(chapter, indent=2, ensure_ascii=False))

    print(f"\n=== Token summary ===")
    print(f"  Prompt tokens:     {total_prompt_tokens:,}")
    print(f"  Completion tokens: {total_completion_tokens:,}")
    total = total_prompt_tokens + total_completion_tokens
    print(f"  Total tokens:      {total:,}")
    # gpt-4o-mini pricing (as of 2024): ~$0.15/1M input, $0.60/1M output
    cost = (total_prompt_tokens * 0.15 + total_completion_tokens * 0.60) / 1_000_000
    print(f"  Estimated cost:    ${cost:.4f} (gpt-4o-mini rates)")


if __name__ == "__main__":
    main()
