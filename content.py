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
    r"personal life|rumou?r about|celebrity feud)\b",
    re.I,
)

PREVIEW_PATTERN = re.compile(
    r"\b(live streaming|where to watch|how to watch|schedule|"
    r"fixtures|preview|predicted lineup|probable playing|"
    r"ticket booking|live score)\b",
    re.I,
)

EVENT_PATTERN = re.compile(
    r"\b(won|beat|defeated|qualified|launched|announced|"
    r"discovered|reported|revealed|confirmed|approved|banned|"
    r"signed|elected|resigned|opened|released|achieved|found|"
    r"created|developed|declared|appointed|died|injured|"
    r"scored|increased|decreased|recorded|warned|said|"
    r"began|started|completed|reached|filed|ordered)\b",
    re.I,
)

STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have",
    "has", "was", "were", "are", "will", "into", "over", "after",
    "before", "their", "they", "them", "about", "says", "said",
    "its", "his", "her", "who", "what", "when", "where", "which",
    "while", "than", "under", "between", "more", "most", "also",
    "been", "being", "latest", "news", "update", "updates",
    "here", "there", "today", "report", "reports",
}

BOILERPLATE_PATTERN = re.compile(
    r"\b(subscribe|sign in|log in|cookie policy|advertisement|"
    r"all rights reserved|privacy policy|terms of use|"
    r"read more|click here|follow us|newsletter|"
    r"your browser|enable javascript)\b",
    re.I,
)


class ArticleParser(HTMLParser):
    """Collect paragraph text, not arbitrary page fragments."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []
        self.current = []
        self.in_paragraph = False
        self.skip_depth = 0
        self.skip_tags = {
            "script", "style", "nav", "footer", "header",
            "aside", "form", "noscript", "svg",
        }

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip_depth += 1
        if tag == "p" and self.skip_depth == 0:
            self.in_paragraph = True
            self.current = []

    def handle_endtag(self, tag):
        if tag == "p" and self.in_paragraph:
            value = clean_text(" ".join(self.current))
            if value:
                self.paragraphs.append(value)
            self.current = []
            self.in_paragraph = False

        if tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)

    def handle_data(self, data):
        if self.in_paragraph and self.skip_depth == 0:
            value = data.strip()
            if value:
                self.current.append(value)


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
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl(), response.headers.get(
            "Content-Type", ""
        )


def classify_topic(topic):
    value = topic.lower()

    if any(x in value for x in [
        "cricket", "football", "soccer", "tennis", "olympic",
        "sport", "match", "tournament",
    ]):
        return "Sports"

    if any(x in value for x in [
        "technology", "artificial intelligence", " ai ",
        "robot", "smartphone", "google", "apple", "microsoft",
        "software", "cyber",
    ]):
        return "Technology & AI"

    if any(x in value for x in [
        "science", "space", "nasa", "research", "discovery",
        "scientist", "climate",
    ]):
        return "Science & Discoveries"

    if any(x in value for x in [
        "viral", "internet trend", "meme", "social media",
        "instagram", "youtube",
    ]):
        return "Viral Trends"

    if any(x in value for x in [
        "fact", "mystery", "world record", "interesting", "amazing",
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
        data, _, _ = fetch_url(url)
        root = ET.fromstring(data)
    except Exception as error:
        print("RSS error:", topic, error)
        return []

    stories = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        description = clean_text(item.findtext("description", ""))
        link = (item.findtext("link", "") or "").strip()
        pub_date = item.findtext("pubDate", "")

        source_element = item.find("source")
        publisher = (
            clean_text(source_element.text)
            if source_element is not None and source_element.text
            else "Unknown publisher"
        )

        if not title or not link:
            continue
        if SKIP_PATTERN.search(title) or PREVIEW_PATTERN.search(title):
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

    return stories[:10]


def meaningful_words(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {
        word for word in words
        if len(word) > 3 and word not in STOP_WORDS
    }


def title_similarity(title_a, title_b):
    words_a = meaningful_words(title_a)
    words_b = meaningful_words(title_b)

    if not words_a or not words_b:
        return 0.0

    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union else 0.0


def find_story_group(headlines):
    """
    Strict grouping: compare each headline with the first headline
    in a group. This avoids loose, chain-based keyword clustering.
    """
    groups = []

    for story in headlines:
        placed = False
        for group in groups:
            similarity = title_similarity(
                story["title"], group[0]["title"]
            )
            if similarity >= 0.42:
                group.append(story)
                placed = True
                break

        if not placed:
            groups.append([story])

    groups.sort(key=len, reverse=True)
    return groups


def extract_article_text(url):
    try:
        data, final_url, content_type = fetch_url(url, timeout=18)

        if "html" not in content_type.lower():
            return "", final_url

        raw = data.decode("utf-8", errors="ignore")
        if not raw:
            return "", final_url

        parser = ArticleParser()
        parser.feed(raw)

        paragraphs = []
        for paragraph in parser.paragraphs:
            paragraph = clean_text(paragraph)

            if len(paragraph) < 65 or len(paragraph) > 1000:
                continue
            if BOILERPLATE_PATTERN.search(paragraph):
                continue

            paragraphs.append(paragraph)

        # Remove duplicate paragraphs while preserving their order.
        paragraphs = list(dict.fromkeys(paragraphs))
        return " ".join(paragraphs[:45]), final_url

    except Exception as error:
        print("Article extraction failed:", url, error)
        return "", url


def split_sentences(text):
    text = clean_text(text)
    pieces = re.split(r"(?<=[.!?])\s+", text)
    result = []

    for sentence in pieces:
        sentence = sentence.strip()

        # Reject fragments and very long blocks.
        word_count = len(sentence.split())
        if word_count < 11 or word_count > 65:
            continue
        if len(sentence) < 65 or len(sentence) > 450:
            continue
        if not re.search(r"[.!?]$", sentence):
            continue
        if BOILERPLATE_PATTERN.search(sentence):
            continue

        result.append(sentence)

    return result


def is_headline_like(sentence, title):
    sentence_words = meaningful_words(sentence)
    title_words = meaningful_words(title)

    if not sentence_words or not title_words:
        return False

    overlap = len(sentence_words & title_words)
    ratio = overlap / max(1, len(sentence_words))
    return ratio >= 0.72 and len(sentence.split()) < 24


def sentence_score(sentence, topic_words):
    words = meaningful_words(sentence)
    score = len(words & topic_words)

    if re.search(r"\d", sentence):
        score += 1
    if len(sentence.split()) >= 15:
        score += 1

    return score


def collect_facts(group):
    topic_words = set()
    for story in group:
        topic_words |= meaningful_words(story["title"])

    collected = []
    seen_sentences = set()
    publishers_with_facts = set()

    for story in group:
        article_text, final_url = extract_article_text(story["link"])
        story["article_text"] = article_text
        story["article_url"] = final_url

        # No RSS-description fallback: headlines/descriptions alone
        # are not enough to create a narration draft.
        sentences = split_sentences(article_text)

        ranked = sorted(
            sentences,
            key=lambda sentence: sentence_score(sentence, topic_words),
            reverse=True,
        )

        added_for_publisher = 0
        for sentence in ranked:
            if is_headline_like(sentence, story["title"]):
                continue

            key = re.sub(r"[^a-z0-9]", "", sentence.lower())
            if key in seen_sentences:
                continue

            seen_sentences.add(key)
            collected.append({
                "sentence": sentence,
                "publisher": story["publisher"],
                "url": story["article_url"],
            })
            publishers_with_facts.add(story["publisher"])
            added_for_publisher += 1

            if added_for_publisher >= 2:
                break

        time.sleep(1)

    return collected, publishers_with_facts


def make_script(topic, facts):
    selected = []
    used_words = 0

    for fact in facts:
        sentence = fact["sentence"]
        word_count = len(sentence.split())

        if used_words + word_count > 95:
            continue

        selected.append(sentence)
        used_words += word_count

        if len(selected) >= 4:
            break

    if len(selected) < 3 or used_words < 35:
        return None

    script = [
        "HOOK: Here are the key details being reported about "
        + topic + ".",
        "",
        "FACTUAL DETAILS:",
    ]

    script.extend(selected)
    script.extend([
        "",
        "ENDING: Follow InfoRush for more updates.",
    ])

    return "\n".join(script), used_words


def create_draft(category, topic, group, facts, publishers):
    # Demand multiple independent publishers and multiple article facts.
    if len(publishers) < 2 or len(facts) < 3:
        return None

    result = make_script(topic, facts)
    if not result:
        return None

    script, word_count = result
    output = [
        "## " + category + ": " + topic,
        "**Status:** Candidate — human verification required",
        "",
        "### Related reports",
    ]

    for index, story in enumerate(group, start=1):
        output.extend([
            str(index) + ". **" + story["title"] + "**",
            "- Publisher: " + story["publisher"],
            "- Published: " + (story["date"] or "Not provided"),
            "- Article: " + story["article_url"],
            "",
        ])

    output.append("### Article-body sentences extracted")
    for fact in facts:
        output.append("- " + fact["sentence"])
        output.append("  - Publisher: " + fact["publisher"])
        output.append("  - Article: " + fact["url"])

    output.extend([
        "",
        "### Reel script — draft",
        "**Estimated narration:** " + str(word_count) + " words",
        "",
        script,
        "",
        "### Caption",
        "Here are the reported details about " + topic
        + ". Check the original sources for context. "
        + "Follow InfoRush for more.",
        "",
        "### Hashtags",
        "#InfoRush #NewsUpdate #DiscoverMore #LatestUpdates",
        "",
        "### Human verification checklist",
        "- Open each original publisher article.",
        "- Confirm that every article covers the same specific event.",
        "- Verify every name, number, date and quotation.",
        "- Check whether any article has been corrected or updated.",
        "- Remove any detail that cannot be independently confirmed.",
        "- Approve the final narration before publishing.",
        "",
        "---",
        "",
    ])

    return "\n".join(output)


def main():
    topics = read_topics()
    now = datetime.now(timezone.utc)

    report = [
        "# InfoRush Content Drafts",
        "Generated: " + now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "",
        "Free RSS discovery and publisher article-text extraction.",
        "These are research candidates, not independently verified news.",
        "",
    ]

    if not topics:
        report.append("No topics were found in the trend report.")

    category_order = CATEGORIES[:]
    rotation = now.timetuple().tm_yday % len(category_order)
    category_order = category_order[rotation:] + category_order[:rotation]

    selected_count = 0
    skipped_count = 0
    attempted_count = 0

    for category in category_order:
        if selected_count >= 2:
            break

        for topic in topics:
            if classify_topic(topic) != category:
                continue
            if SKIP_PATTERN.search(topic):
                continue

            attempted_count += 1
            headlines = get_headlines(topic)

            if len(headlines) < 2:
                skipped_count += 1
                continue

            groups = find_story_group(headlines)
            usable_groups = [group for group in groups if len(group) >= 2]

            if not usable_groups:
                skipped_count += 1
                continue

            # Try the strongest groups one by one. Do not merge them.
            draft_created = False
            for group in usable_groups[:3]:
                facts, publishers = collect_facts(group)
                draft = create_draft(
                    category, topic, group, facts, publishers
                )

                if draft:
                    report.append(draft)
                    selected_count += 1
                    draft_created = True
                    print("Selected:", topic)
                    break

            if not draft_created:
                skipped_count += 1

            if selected_count >= 2:
                break

    report.extend([
        "",
        "## Run summary",
        "- Drafts created: " + str(selected_count),
        "- Topics attempted: " + str(attempted_count),
        "- Topics skipped for insufficient article information: "
        + str(skipped_count),
        "",
        "Important: This program uses free RSS discovery and basic "
        "publisher-page extraction. It does not independently verify "
        "facts, understand context, or generate AI-written summaries. "
        "Publisher pages may block extraction or provide incomplete text. "
        "If information is insufficient, the topic is skipped.",
    ])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(report))

    print("InfoRush content report created.")
    print("Drafts:", selected_count)
    print("Topics attempted:", attempted_count)
    print("Skipped:", skipped_count)


if __name__ == "__main__":
    main()
