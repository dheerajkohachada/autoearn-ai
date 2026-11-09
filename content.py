
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

USER_AGENT = (
    "Mozilla/5.0 (compatible; InfoRushBot/1.0; "
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
    r"personal life|rumou?r about|celebrity feud)\b",
    re.I,
)

PREVIEW_PATTERN = re.compile(
    r"\b(live streaming|where to watch|how to watch|"
    r"schedule|fixtures|preview|predicted lineup|"
    r"probable playing|ticket booking|live score)\b",
    re.I,
)

EVENT_PATTERN = re.compile(
    r"\b(won|beat|defeated|qualified|launched|"
    r"announced|discovered|reported|revealed|"
    r"confirmed|approved|banned|signed|"
    r"elected|resigned|opened|released|"
    r"achieved|found|created|developed|"
    r"declared|appointed|died|injured|"
    r"scored|increased|decreased|recorded)\b",
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


def fetch_url(url, timeout=12):
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

        if not EVENT_PATTERN.search(title):
            continue

        stories.append({
            "title": title,
            "description": description,
            "link": link,
            "date": pub_date,
            "publisher": publisher,
            "article_text": "",
            "article_url": link,
        })

    return stories[:8]


def meaningful_words(text):
    words = re.findall(r"[a-z0-9]+", text.lower())

    return {
        word for word in words
        if len(word) > 3 and word not in STOP_WORDS
    }


def find_story_group(headlines):
    groups = []

    for story in headlines:
        words = meaningful_words(story["title"])
        placed = False

        for group in groups:
            group_words = set()

            for existing in group:
                group_words |= meaningful_words(existing["title"])

            overlap = len(words & group_words)

            if overlap >= 2:
                group.append(story)
                placed = True
                break

        if not placed:
            groups.append([story])

    groups.sort(key=len, reverse=True)
    return groups


def extract_article_text(url):
    try:
        data, final_url = fetch_url(url, timeout=15)

        content_type = ""
        # The response may be HTML or another format.
        # HTML extraction is attempted only on readable text.
        raw = data.decode("utf-8", errors="ignore")

        if not raw or "<html" not in raw.lower():
            return "", final_url

        parser = TextExtractor()
        parser.feed(raw)

        paragraphs = []

        for part in parser.parts:
            text = clean_text(part)

            if len(text) < 55:
                continue

            if len(text) > 1200:
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

        # Remove exact duplicate paragraphs.
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

    for story in group:
        article_text, final_url = extract_article_text(story["link"])

        story["article_text"] = article_text
        story["article_url"] = final_url

        sentences = split_sentences(article_text)

        if not sentences:
            # RSS descriptions are used only as a limited fallback.
            fallback = split_sentences(story["description"])
            sentences = fallback

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
            })

            added += 1

            if added >= 3:
                break

        time.sleep(1)

    return collected


def make_script(group, facts):
    lead = group[0]["title"]

    # Use the actual event headline as the hook.
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
        "FACTUAL DETAILS:",
    ]

    for sentence in selected:
        script.append(sentence)

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

    if word_count < 35:
        return None

    if len(facts) < 2:
        return None

    output = []

    output.append("## " + category + ": " + topic)
    output.append("**Status:** Candidate — human verification required")
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

    output.append("### Extracted factual sentences")

    for fact in facts:
        output.append("- " + fact["sentence"])
        output.append(
            "  - Source: " + fact["publisher"]
        )
        output.append(
            "  - Link: " + fact["url"]
        )

    output.append("")
    output.append("### Reel script — draft")
    output.append("**Estimated narration:** " + str(word_count) + " words")
    output.append("")
    output.append(script)
    output.append("")
    output.append("### Caption")
    output.append(
        "What happened in " + topic +
        "? Here are the reported details. Follow InfoRush for more."
    )
    output.append("")
    output.append("### Hashtags")
    output.append(
        "#InfoRush #NewsUpdate #DiscoverMore #LatestUpdates"
    )
    output.append("")
    output.append("### Human verification checklist")
    output.append("- Open the original articles.")
    output.append("- Confirm that all reports describe the same event.")
    output.append("- Verify every name, number, date and quotation.")
    output.append("- Check whether the story has been corrected or updated.")
    output.append("- Remove any sentence that cannot be confirmed.")
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
        "Free RSS and article-text extraction. "
        "These are research candidates, not independently verified news.",
        "",
    ]

    if not topics:
        report.append("No topics were found in the trend report.")

    category_order = CATEGORIES[:]
    rotation = now.timetuple().tm_yday % len(category_order)
    category_order = (
        category_order[rotation:] + category_order[:rotation]
    )

    selected_categories = set()
    selected_count = 0
    skipped_count = 0

    for category in category_order:
        if selected_count >= 2:
            break

        for topic in topics:
            if classify_topic(topic) != category:
                continue

            if SKIP_PATTERN.search(topic):
                continue

            headlines = get_headlines(topic)

            if len(headlines) < 2:
                continue

            groups = find_story_group(headlines)

            if not groups or len(groups[0]) < 2:
                continue

            group = groups[0]

            facts = collect_facts(group)

            draft = create_draft(
                category, topic, group, facts
            )

            if not draft:
                skipped_count += 1
                continue

            report.append(draft)
            selected_categories.add(category)
            selected_count += 1

            print("Selected:", topic)

            break

    report.append("")
    report.append("## Run summary")
    report.append("- Drafts created: " + str(selected_count))
    report.append("- Stories skipped for insufficient information: " + str(skipped_count))
    report.append("")
    report.append(
        "Important: Similar headlines do not prove accuracy. "
        "Article extraction can fail, RSS descriptions may be incomplete, "
        "and all scripts require human verification."
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(report))

    print("InfoRush content report created.")
    print("Drafts:", selected_count)
    print("Skipped:", skipped_count)


if __name__ == "__main__":
    main()
