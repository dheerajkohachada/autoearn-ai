
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

USER_AGENT = "Mozilla/5.0 (compatible; InfoRush/3.0)"

MAX_DRAFTS = 2
MAX_HEADLINES_PER_TOPIC = 8
MAX_ARTICLES_PER_GROUP = 5

SKIP_PATTERN = re.compile(
    r"\b(divorce|breakup|affair|dating|relationship gossip|"
    r"personal life|celebrity feud)\b", re.I
)

PREVIEW_PATTERN = re.compile(
    r"\b(live streaming|where to watch|how to watch|schedule|"
    r"fixtures|preview|predicted lineup|ticket booking|live score)\b",
    re.I
)

STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have",
    "has", "was", "were", "are", "will", "into", "over", "after",
    "before", "their", "they", "them", "about", "said", "its",
    "his", "her", "who", "what", "when", "where", "which",
    "while", "than", "under", "between", "more", "most", "also",
    "been", "being", "latest", "news", "update", "updates",
    "today", "report", "reports", "says"
}

BOILERPLATE = re.compile(
    r"\b(subscribe|sign in|log in|cookie policy|advertisement|"
    r"all rights reserved|privacy policy|terms of use|read more|"
    r"click here|follow us|newsletter|enable javascript)\b", re.I
)


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []
        self.current = []
        self.in_p = False
        self.skip_depth = 0
        self.skip_tags = {
            "script", "style", "nav", "footer", "header",
            "aside", "form", "noscript", "svg"
        }

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip_depth += 1

        if tag == "p" and self.skip_depth == 0:
            self.in_p = True
            self.current = []

    def handle_endtag(self, tag):
        if tag == "p" and self.in_p:
            value = clean_text(" ".join(self.current))
            if value:
                self.paragraphs.append(value)
            self.current = []
            self.in_p = False

        if tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)

    def handle_data(self, data):
        if self.in_p and self.skip_depth == 0:
            value = data.strip()
            if value:
                self.current.append(value)


def fetch_url(url, timeout=15):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*"
        }
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return (
            response.read(),
            response.geturl(),
            response.headers.get("Content-Type", "")
        )


def read_topics():
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        return []

    topics = []

    for line in lines:
        match = re.match(r"^\s*\d+[\.\)]\s+(.+)", line)

        if match:
            topic = clean_text(match.group(1))

            if len(topic) >= 3 and topic.lower() not in {
                "no trends retrieved"
            }:
                topics.append(topic)

    return list(dict.fromkeys(topics))


def classify_topic(topic):
    value = topic.lower()

    if any(x in value for x in [
        "cricket", "football", "soccer", "tennis",
        "olympic", "sport", "match", "tournament"
    ]):
        return "Sports"

    if any(x in value for x in [
        "technology", "artificial intelligence", " ai ",
        "robot", "smartphone", "google", "apple",
        "microsoft", "software", "cyber"
    ]):
        return "Technology & AI"

    if any(x in value for x in [
        "science", "space", "nasa", "research",
        "discovery", "scientist", "climate"
    ]):
        return "Science & Discoveries"

    if any(x in value for x in [
        "viral", "internet trend", "meme",
        "social media", "instagram", "youtube"
    ]):
        return "Viral Trends"

    if any(x in value for x in [
        "fact", "mystery", "world record",
        "interesting", "amazing"
    ]):
        return "Interesting Facts"

    return "World News"


def get_headlines(topic):
    query = urllib.parse.quote(topic)

    url = (
        "https://news.google.com/rss/search?q="
        + query
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    try:
        data, _, _ = fetch_url(url)
        root = ET.fromstring(data)
    except Exception as error:
        print("RSS error:", topic, error)
        return []

    stories = []

    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        description = clean_text(
            item.findtext("description", "")
        )
        link = (item.findtext("link", "") or "").strip()
        pub_date = item.findtext("pubDate", "")

        source = item.find("source")

        publisher = (
            clean_text(source.text)
            if source is not None and source.text
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
            "article_text": "",
            "article_url": link
        })

    return stories[:MAX_HEADLINES_PER_TOPIC]


def meaningful_words(text):
    words = re.findall(r"[a-z0-9]+", text.lower())

    return {
        word for word in words
        if len(word) > 3 and word not in STOP_WORDS
    }


def title_similarity(a, b):
    words_a = meaningful_words(a)
    words_b = meaningful_words(b)

    if not words_a or not words_b:
        return 0

    return len(words_a & words_b) / len(words_a | words_b)


def find_story_groups(headlines):
    groups = []

    for story in headlines:
        placed = False

        for group in groups:
            similarity = title_similarity(
                story["title"], group[0]["title"]
            )

            if similarity >= 0.30:
                group.append(story)
                placed = True
                break

        if not placed:
            groups.append([story])

    groups.sort(key=len, reverse=True)
    return groups


def extract_article_text(url):
    try:
        data, final_url, content_type = fetch_url(
            url, timeout=15
        )

        if "html" not in content_type.lower():
            return "", final_url

        raw = data.decode("utf-8", errors="ignore")

        parser = ArticleParser()
        parser.feed(raw)

        paragraphs = []

        for paragraph in parser.paragraphs:
            paragraph = clean_text(paragraph)

            if len(paragraph) < 45:
                continue

            if len(paragraph) > 1000:
                continue

            if BOILERPLATE.search(paragraph):
                continue

            paragraphs.append(paragraph)

        paragraphs = list(dict.fromkeys(paragraphs))

        return " ".join(paragraphs[:25]), final_url

    except Exception as error:
        print("Article extraction failed:", error)
        return "", url


def split_sentences(text):
    text = clean_text(text)
    pieces = re.split(r"(?<=[.!?])\s+", text)

    result = []

    for sentence in pieces:
        sentence = sentence.strip()
        count = len(sentence.split())

        if count < 8 or count > 55:
            continue

        if len(sentence) < 45 or len(sentence) > 400:
            continue

        if not re.search(r"[.!?]$", sentence):
            continue

        if BOILERPLATE.search(sentence):
            continue

        result.append(sentence)

    return result


def collect_facts(group):
    facts = []
    seen = set()
    publishers = set()

    for story in group[:MAX_ARTICLES_PER_GROUP]:
        article_text, final_url = extract_article_text(
            story["link"]
        )

        story["article_text"] = article_text
        story["article_url"] = final_url

        # Use article text first. If blocked, use the RSS description.
        source_text = article_text

        if not source_text:
            source_text = story["description"]

        sentences = split_sentences(source_text)

        added = 0

        for sentence in sentences:
            key = re.sub(
                r"[^a-z0-9]", "", sentence.lower()
            )

            if key in seen:
                continue

            seen.add(key)

            facts.append({
                "sentence": sentence,
                "publisher": story["publisher"],
                "url": story["article_url"]
            })

            publishers.add(story["publisher"])
            added += 1

            if added >= 3:
                break

        time.sleep(0.5)

    return facts, publishers


def make_script(topic, facts):
    selected = []
    used_words = 0

    for fact in facts:
        sentence = fact["sentence"]
        count = len(sentence.split())

        if used_words + count > 95:
            continue

        selected.append(sentence)
        used_words += count

        if len(selected) >= 4:
            break

    if len(selected) < 3 or used_words < 35:
        return None

    script = [
        "HOOK: Here are the reported details about "
        + topic + ".",
        "",
        "FACTUAL DETAILS:"
    ]

    script.extend(selected)

    script.extend([
        "",
        "ENDING: Follow InfoRush for more updates."
    ])

    return "\n".join(script), used_words


def create_draft(category, topic, group, facts, publishers):
    if len(publishers) < 2:
        return None, "Fewer than two distinct publishers supplied facts"

    if len(facts) < 3:
        return None, "Fewer than three usable article sentences"

    result = make_script(topic, facts)

    if not result:
        return None, "Not enough usable sentences for a script"

    script, word_count = result

    output = [
        "## " + category + ": " + topic,
        "**Status:** Research candidate — human verification required",
        "",
        "### Related reports"
    ]

    for index, story in enumerate(group, 1):
        output.extend([
            str(index) + ". **" + story["title"] + "**",
            "- Publisher: " + story["publisher"],
            "- Published: " + (
                story["date"] or "Not provided"
            ),
            "- Article: " + story["article_url"],
            ""
        ])

    output.append("### Source information")

    for fact in facts:
        output.extend([
            "- " + fact["sentence"],
            "  - Publisher: " + fact["publisher"],
            "  - Source: " + fact["url"]
        ])

    output.extend([
        "",
        "### Reel script — draft",
        "**Estimated narration:** " + str(word_count) + " words",
        "",
        script,
        "",
        "### Caption",
        "Here are the reported details about " + topic
        + ". Read the original reports and check the context. "
        + "Follow InfoRush for more updates.",
        "",
        "### Hashtags",
        "#InfoRush #NewsUpdate #DiscoverMore #LatestUpdates",
        "",
        "### Human verification checklist",
        "- Confirm that the reports cover the same specific event.",
        "- Open and read the original publisher articles.",
        "- Verify names, dates, numbers and quotations.",
        "- Check for corrections or later updates.",
        "- Do not publish unconfirmed claims.",
        "- Approve the final script before publishing.",
        "",
        "---",
        ""
    ])

    return "\n".join(output), None


def main():
    topics = read_topics()
    now = datetime.now(timezone.utc)

    report = [
        "# InfoRush Content Drafts",
        "Generated: " + now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "",
        "Free RSS research and article extraction.",
        "These drafts are candidates, not verified news.",
        ""
    ]

    if not topics:
        report.append(
            "No numbered topics found in trend_report.md."
        )

    selected_count = 0
    attempted_count = 0
    skipped = []

    for topic in topics:
        if selected_count >= MAX_DRAFTS:
            break

        if SKIP_PATTERN.search(topic):
            skipped.append((topic, "Filtered by topic safety rule"))
            continue

        attempted_count += 1
        category = classify_topic(topic)

        headlines = get_headlines(topic)

        if len(headlines) < 2:
            skipped.append((
                topic,
                "Fewer than two usable RSS headlines"
            ))
            continue

        groups = find_story_groups(headlines)
        usable_groups = [
            group for group in groups if len(group) >= 2
        ]

        if not usable_groups:
            skipped.append((
                topic,
                "No sufficiently similar headline group"
            ))
            continue

        draft_created = False
        reasons = []

        for group in usable_groups[:2]:
            facts, publishers = collect_facts(group)

            draft, reason = create_draft(
                category, topic, group, facts, publishers
            )

            if draft:
                report.append(draft)
                selected_count += 1
                draft_created = True
                print("Draft created:", topic)
                break

            reasons.append(reason)

        if not draft_created:
            skipped.append((
                topic,
                "; ".join(dict.fromkeys(reasons))
                or "Insufficient information"
            ))

    report.extend([
        "",
        "## Run summary",
        "- Drafts created: " + str(selected_count),
        "- Topics found: " + str(len(topics)),
        "- Topics attempted: " + str(attempted_count),
        "- Topics skipped: " + str(len(skipped)),
        "",
        "## Skipped topic details"
    ])

    if skipped:
        for topic, reason in skipped:
            report.append("- **" + topic + "** — " + reason)
    else:
        report.append("No topics were skipped.")

    report.extend([
        "",
        "## Important limitations",
        "- RSS descriptions are used when article pages block access.",
        "- Similar headlines do not prove independent confirmation.",
        "- This program does not independently verify facts.",
        "- It does not generate AI-written narration.",
        "- Human review is required before publishing.",
        "- It may create fewer than two drafts when evidence is weak."
    ])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(report))

    print("InfoRush content report created.")
    print("Drafts:", selected_count)
    print("Topics attempted:", attempted_count)
    print("Skipped:", len(skipped))


if __name__ == "__main__":
    main()
