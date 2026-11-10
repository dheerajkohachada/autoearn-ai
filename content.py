
import re
import html
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from html.parser import HTMLParser


INPUT_FILE = "trend_report.md"
OUTPUT_FILE = "content_drafts.md"

MAX_DRAFTS = 2
MAX_HEADLINES_PER_TOPIC = 8
MAX_ARTICLES_PER_GROUP = 5

USER_AGENT = (
    "Mozilla/5.0 (compatible; InfoRushBot/2.0; "
    "+https://github.com/dheerajkohachada/autoearn-ai)"
)

CATEGORIES = [
    "World News",
    "Technology & AI",
    "Sports",
    "Science & Discoveries",
    "Viral Trends",
    "Interesting Facts",
]

SKIP_PATTERN = re.compile(
    r"\b(divorce|breakup|affair|dating|relationship gossip|"
    r"personal life|celebrity feud)\b",
    re.I,
)

PREVIEW_PATTERN = re.compile(
    r"\b(live streaming|where to watch|how to watch|"
    r"schedule|fixtures|preview|predicted lineup|"
    r"probable playing|ticket booking|live score)\b",
    re.I,
)

STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this",
    "have", "has", "was", "were", "are", "will", "into",
    "over", "after", "before", "their", "they", "them",
    "about", "says", "said", "its", "his", "her", "who",
    "what", "when", "where", "which", "while", "than",
    "under", "between", "more", "most", "also", "been",
    "being", "latest", "news", "update", "updates",
}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.skip_depth = max(0, self.skip_depth - 1)

    def handle_data(self, data):
        if self.skip_depth == 0:
            value = data.strip()
            if value:
                self.parts.append(value)


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def fetch_url(url, timeout=15):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/rss+xml,*/*",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl()


def classify_topic(topic):
    value = topic.lower()

    if any(x in value for x in [
        "cricket", "football", "soccer", "tennis",
        "olympic", "sport", "match", "tournament",
        "blue jays", "championship",
    ]):
        return "Sports"

    if any(x in value for x in [
        "technology", "artificial intelligence", " ai ",
        "robot", "smartphone", "google", "apple",
        "microsoft", "software", "cyber",
    ]):
        return "Technology & AI"

    if any(x in value for x in [
        "science", "space", "nasa", "research",
        "discovery", "scientist", "climate",
    ]):
        return "Science & Discoveries"

    if any(x in value for x in [
        "viral", "internet trend", "meme",
        "social media", "instagram", "youtube",
    ]):
        return "Viral Trends"

    if any(x in value for x in [
        "fact", "mystery", "world record",
        "interesting", "amazing",
    ]):
        return "Interesting Facts"

    return "World News"


def read_topics():
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        print("Trend report not found.")
        return []

    topics = []

    for line in lines:
        match = re.match(r"^\s*\d+[\.\)]\s+(.+)", line)

        if match:
            topic = clean_text(match.group(1))
            if len(topic) >= 3:
                topics.append(topic)

    return list(dict.fromkeys(topics))


def get_headlines(topic):
    query = urllib.parse.quote(topic)

    url = (
        "https://news.google.com/rss/search?q="
        + query
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    try:
        data, _ = fetch_url(url)
        root = ET.fromstring(data)
    except Exception as error:
        print("RSS error:", topic, error)
        return []

    stories = []

    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        description = clean_text(item.findtext("description", ""))
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")

        source_element = item.find("source")

        publisher = (
            clean_text(source_element.text)
            if source_element is not None and source_element.text
            else "Unknown publisher"
        )

        if not title or not link:
            continue

        if SKIP_PATTERN.search(title):
            continue

        if PREVIEW_PATTERN.search(title):
            continue

        stories.append({
            "title": title,
            "description": description,
            "link": link,
            "date": pub_date,
            "publisher": publisher,
            "article_url": link,
        })

    # Do not require an event verb in the headline.
    # Many valid news headlines do not contain one.
    return stories[:MAX_HEADLINES_PER_TOPIC]


def meaningful_words(text):
    words = re.findall(r"[a-z0-9]+", text.lower())

    return {
        word for word in words
        if len(word) > 3 and word not in STOP_WORDS
    }


def find_story_groups(headlines):
    groups = []

    for story in headlines:
        words = meaningful_words(story["title"])
        placed = False

        for group in groups:
            group_words = set()

            for existing in group:
                group_words |= meaningful_words(existing["title"])

            overlap = len(words & group_words)

            # Require at least two shared meaningful words.
            # Otherwise keep stories separate.
            if overlap >= 2:
                group.append(story)
                placed = True
                break

        if not placed:
            groups.append([story])

    # Prefer groups with more distinct publishers.
    groups.sort(
        key=lambda group: (
            len({
                story["publisher"].lower()
                for story in group
                if story["publisher"] != "Unknown publisher"
            }),
            len(group),
        ),
        reverse=True,
    )

    return groups


def extract_article_text(url):
    try:
        data, final_url = fetch_url(url, timeout=15)
        raw = data.decode("utf-8", errors="ignore")

        if not raw or "<html" not in raw.lower():
            return "", final_url

        parser = TextExtractor()
        parser.feed(raw)

        paragraphs = []

        for part in parser.parts:
            text = clean_text(part)

            if len(text) < 55 or len(text) > 1200:
                continue

            if re.search(
                r"(subscribe|sign in|log in|cookie policy|"
                r"advertisement|all rights reserved|"
                r"privacy policy|terms of use)",
                text,
                re.I,
            ):
                continue

            paragraphs.append(text)

        paragraphs = list(dict.fromkeys(paragraphs))

        return " ".join(paragraphs[:35]), final_url

    except Exception as error:
        print("Article extraction failed:", error)
        return "", url


def split_sentences(text):
    text = clean_text(text)
    pieces = re.split(r"(?<=[.!?])\s+", text)

    result = []

    for sentence in pieces:
        sentence = sentence.strip()

        if len(sentence.split()) < 8:
            continue

        if len(sentence) > 450:
            continue

        if re.search(
            r"(subscribe|click here|read more|"
            r"sign up|follow us|advertisement)",
            sentence,
            re.I,
        ):
            continue

        result.append(sentence)

    return result


def sentence_score(sentence, topic_words):
    words = meaningful_words(sentence)
    score = len(words & topic_words)

    if re.search(r"\d", sentence):
        score += 1

    if len(sentence.split()) > 12:
        score += 1

    return score


def collect_facts(group):
    topic_words = set()

    for story in group:
        topic_words |= meaningful_words(story["title"])

    collected = []
    seen = set()

    for story in group[:MAX_ARTICLES_PER_GROUP]:
        article_text, final_url = extract_article_text(story["link"])
        story["article_url"] = final_url

        sentences = split_sentences(article_text)
        source_type = "Article text"

        if not sentences:
            # Limited fallback when the article page blocks access.
            sentences = split_sentences(story["description"])
            source_type = "RSS description"

        ranked = sorted(
            sentences,
            key=lambda sentence: sentence_score(
                sentence, topic_words
            ),
            reverse=True,
        )

        added = 0

        for sentence in ranked:
            key = re.sub(r"[^a-z0-9]", "", sentence.lower())

            if key in seen:
                continue

            seen.add(key)

            collected.append({
                "sentence": sentence,
                "publisher": story["publisher"],
                "url": story["article_url"],
                "source_type": source_type,
            })

            added += 1

            if added >= 2:
                break

        time.sleep(1)

    return collected


def make_script(group, facts):
    lead = group[0]["title"]
    hook = "Here's what happened: " + lead + "."

    selected = []
    used_words = len(hook.split())

    for fact in facts:
        sentence = fact["sentence"]
        word_count = len(sentence.split())

        if sentence in selected:
            continue

        if used_words + word_count > 105:
            continue

        selected.append(sentence)
        used_words += word_count

        if len(selected) >= 4:
            break

    if not selected:
        return None

    script = [
        "HOOK: " + hook,
        "",
        "REPORTED DETAILS:",
    ]

    script.extend(selected)

    script.extend([
        "",
        "ENDING: Follow InfoRush for more important updates.",
    ])

    return "\n".join(script), used_words


def create_draft(category, topic, group, facts):
    result = make_script(group, facts)

    if not result:
        return None

    script, word_count = result

    # At least one usable sentence is now enough.
    if not facts:
        return None

    publishers = {
        fact["publisher"].lower()
        for fact in facts
        if fact["publisher"] != "Unknown publisher"
    }

    if len(publishers) >= 2:
        status = (
            "MULTI-SOURCE CANDIDATE — "
            "VERIFY BEFORE PUBLISHING"
        )
    else:
        status = (
            "SINGLE-SOURCE CANDIDATE — "
            "VERIFY BEFORE PUBLISHING"
        )

    output = []

    output.append("## " + category + ": " + topic)
    output.append("**Status:** " + status)
    output.append("")
    output.append(
        "**Important:** This is an automated research draft, "
        "not confirmed news."
    )
    output.append("")

    output.append("### Related reports")

    for index, story in enumerate(group, start=1):
        output.append(
            str(index) + ". **" + story["title"] + "**"
        )
        output.append("- Publisher: " + story["publisher"])
        output.append("- Published: " + (story["date"] or "Not provided"))
        output.append("- Article: " + story["article_url"])
        output.append("")

    output.append("### Extracted information")

    for fact in facts:
        output.append("- " + fact["sentence"])
        output.append("  - Publisher: " + fact["publisher"])
        output.append("  - Extraction: " + fact["source_type"])
        output.append("  - Link: " + fact["url"])

    output.append("")
    output.append("### Reel script — draft")
    output.append("**Estimated narration:** " + str(word_count) + " words")
    output.append("")
    output.append(script)
    output.append("")

    output.append("### Caption")
    output.append(
        "What happened in " + topic +
        "? Here are the reported details. "
        "Follow InfoRush for more."
    )
    output.append("")

    output.append("### Hashtags")
    output.append(
        "#InfoRush #NewsUpdate #DiscoverMore #LatestUpdates"
    )
    output.append("")

    output.append("### Human verification checklist")
    output.append("- Open every original article.")
    output.append("- Confirm that reports describe the same event.")
    output.append("- Check the event date and publication date.")
    output.append("- Verify every name, number and claim.")
    output.append("- Look for corrections or newer developments.")
    output.append("- For single-source drafts, find another reliable source.")
    output.append("- Remove anything that cannot be confirmed.")
    output.append("- Approve the final narration before publishing.")
    output.append("")
    output.append("---")
    output.append("")

    return "\n".join(output)


def main():
    topics = read_topics()
    now = datetime.now(timezone.utc)

    report = [
        "# InfoRush Content Drafts",
        "Generated: " + now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "",
        "Free RSS research and article extraction.",
        "All drafts are candidates, not verified news.",
        "",
    ]

    if not topics:
        report.append("No topics were found in the trend report.")

    category_order = CATEGORIES[:]
    rotation = now.timetuple().tm_yday % len(category_order)

    category_order = (
        category_order[rotation:] + category_order[:rotation]
    )

    selected_count = 0
    attempted_count = 0
    skipped = []

    for category in category_order:
        if selected_count >= MAX_DRAFTS:
            break

        for topic in topics:
            if selected_count >= MAX_DRAFTS:
                break

            if classify_topic(topic) != category:
                continue

            if SKIP_PATTERN.search(topic):
                skipped.append((topic, "Filtered by topic safety rule"))
                continue

            attempted_count += 1
            headlines = get_headlines(topic)

            if not headlines:
                skipped.append((topic, "No usable RSS headlines"))
                continue

            groups = find_story_groups(headlines)

            if not groups:
                skipped.append((topic, "No headline groups found"))
                continue

            draft_created = False
            best_reason = "No sufficiently relevant article information"

            for group in groups:
                facts = collect_facts(group)

                if not facts:
                    best_reason = "No usable article sentences or RSS descriptions"
                    continue

                draft = create_draft(category, topic, group, facts)

                if draft:
                    report.append(draft)
                    selected_count += 1
                    draft_created = True
                    print("Selected:", topic)
                    break

            if not draft_created:
                skipped.append((topic, best_reason))

    report.append("")
    report.append("## Run summary")
    report.append("- Drafts created: " + str(selected_count))
    report.append("- Topics found: " + str(len(topics)))
    report.append("- Topics attempted: " + str(attempted_count))
    report.append("- Topics skipped: " + str(len(skipped)))
    report.append("")

    report.append("## Skipped topic details")

    if skipped:
        for topic, reason in skipped:
            report.append("- " + topic + " — " + reason)
    else:
        report.append("No topics were skipped.")

    report.append("")
    report.append("## Important limitations")
    report.append(
        "- RSS descriptions may be incomplete or shortened."
    )
    report.append(
        "- Similar headlines do not prove independent confirmation."
    )
    report.append(
        "- Multiple publishers do not automatically prove accuracy."
    )
    report.append(
        "- Single-source drafts need another reliable source before publishing."
    )
    report.append(
        "- This program does not independently verify facts."
    )
    report.append(
        "- It does not generate AI-written narration."
    )
    report.append(
        "- Human review is required before publishing."
    )
    report.append(
        "- It may create fewer than two drafts when evidence is weak."
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(report))

    print("InfoRush content report created.")
    print("Drafts:", selected_count)
    print("Topics attempted:", attempted_count)
    print("Topics skipped:", len(skipped))


if __name__ == "__main__":
    main()
