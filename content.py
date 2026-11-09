
import re
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser

INPUT_FILE = "trend_report.md"
OUTPUT_FILE = "content_drafts.md"

CATEGORIES = {
    "World News": [
        "world", "election", "government", "parliament", "president",
        "minister", "policy", "war", "conflict", "summit", "protest",
        "economy", "inflation", "trade", "earthquake", "cyclone",
        "flood", "disaster", "climate"
    ],
    "Technology & AI": [
        "technology", "tech", "artificial intelligence", "AI",
        "chatgpt", "openai", "google", "apple", "microsoft",
        "samsung", "iphone", "android", "smartphone", "robot",
        "cyber", "software", "gaming"
    ],
    "Sports": [
        "cricket", "league", "tournament", "match", "football",
        "soccer", "tennis", "basketball", "NBA", "FIFA",
        "olympic", "championship", "player", "team", "world cup"
    ],
    "Science & Discoveries": [
        "science", "scientist", "research", "discovery", "NASA",
        "space", "moon", "mars", "satellite", "planet",
        "astronomy", "physics", "biology", "fossil", "dinosaur"
    ],
    "Viral Trends": [
        "viral", "meme", "internet", "social media", "trending",
        "tiktok", "instagram", "youtube", "reddit", "online"
    ],
    "Interesting Facts": [
        "fact", "facts", "history", "mystery", "record",
        "unusual", "amazing", "interesting", "invention",
        "ancient", "archaeology"
    ]
}

SKIP_PATTERN = re.compile(
    r"divorce|ex-wife|ex-husband|dating|breakup|relationship|gossip|rumou?r",
    re.IGNORECASE
)

PREVIEW_PATTERN = re.compile(
    r"live streaming|where to watch|when and where|live telecast|"
    r"schedule|fixtures|how to watch|tv channel|broadcast|"
    r"match preview|live coverage",
    re.IGNORECASE
)

EVENT_PATTERN = re.compile(
    r"\b(won|wins|win|beat|beats|defeated|defeats|lost|loses|loss|"
    r"qualified|qualifies|advanced|advances|eliminated|scored|"
    r"announced|launched|discovered|approved|signed|resigned|"
    r"arrested|acquired|released|appointed|elected|died|"
    r"injured|opened|closed|reported|revealed|confirmed|"
    r"banned|selected|reached|surpassed|breaks|broke)\b",
    re.IGNORECASE
)

STOP_WORDS = set("""
the a an and or but of to in on at for from by with is are was were
be been being this that these those as it its after before over under
about into than then who what when where why how says said report
reports according latest update updates news today live watch
""".split())


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self):
        return " ".join(self.parts)


def clean_text(value):
    parser = TextExtractor()
    parser.feed(html.unescape(value or ""))
    text = parser.get_text()
    return re.sub(r"\s+", " ", text).strip()


def classify_topic(topic):
    text = topic.lower()

    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text):
                return category

    return None


def read_topics():
    topics = []

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as file:
            for line in file:
                match = re.match(r"^\s*\d+[.)]\s*(.+?)\s*$", line)

                if not match:
                    continue

                topic = match.group(1).strip()

                if not topic or SKIP_PATTERN.search(topic):
                    continue

                category = classify_topic(topic)

                if category:
                    topics.append({
                        "topic": topic,
                        "category": category
                    })

    except FileNotFoundError:
        print("Trend report not found.")
        return []

    unique = []
    seen = set()

    for item in topics:
        key = item["topic"].lower()

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def get_headlines(topic):
    query = urllib.parse.quote(topic)

    url = (
        "https://news.google.com/rss/search?q="
        + query
        + "&hl=en-US&gl=US&ceid=US:en"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            root = ET.fromstring(response.read())

        headlines = []

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            date = item.findtext("pubDate", "").strip()
            description = item.findtext("description", "")

            source_element = item.find("source")

            source = (
                source_element.text.strip()
                if source_element is not None and source_element.text
                else "Publisher not listed"
            )

            if title and link:
                headlines.append({
                    "title": clean_text(title),
                    "description": clean_text(description),
                    "link": link,
                    "date": date,
                    "source": source
                })

        return headlines

    except Exception as error:
        print("Could not fetch:", topic, "-", error)
        return []


def meaningful_words(title, topic):
    words = re.findall(r"[a-zA-Z0-9]+", title.lower())
    topic_words = set(re.findall(r"[a-zA-Z0-9]+", topic.lower()))

    return {
        word for word in words
        if len(word) > 2
        and word not in STOP_WORDS
        and word not in topic_words
    }


def find_story_group(headlines, topic):
    candidates = []

    for headline in headlines:
        title = headline["title"]

        if PREVIEW_PATTERN.search(title):
            continue

        if not EVENT_PATTERN.search(title):
            continue

        headline["keywords"] = meaningful_words(title, topic)
        candidates.append(headline)

    best_group = []

    for first in candidates:
        group = [first]

        for second in candidates:
            if first is second:
                continue

            overlap = first["keywords"] & second["keywords"]

            if len(overlap) >= 2:
                group.append(second)

        if len(group) > len(best_group):
            best_group = group

    unique = []
    seen = set()

    for item in best_group:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique.append(item)

    return unique[:4] if len(unique) >= 2 else []


def make_script(category, topic, headlines):
    primary = headlines[0]
    title = primary["title"]
    summary = primary["description"]

    # Remove publisher suffix sometimes added to titles.
    title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()

    script = []

    script.append(
        "Here's an important update from " + category + "."
    )

    script.append(title + ".")

    if summary:
        sentences = re.split(r"(?<=[.!?])\s+", summary)

        useful = [
            sentence.strip()
            for sentence in sentences
            if len(sentence.strip()) > 20
        ]

        for sentence in useful[:3]:
            script.append(sentence)

    else:
        script.append(
            "The available news feed did not provide a detailed "
            "summary. More reporting is needed before adding details."
        )

    script.append(
        "Follow InfoRush for more updates and important stories."
    )

    narration = " ".join(script)

    return narration


def create_draft(category, topic, headlines):
    lines = []

    narration = make_script(category, topic, headlines)

    lines.append("## " + category + ": " + topic)
    lines.append("")
    lines.append("**Status:** Candidate — manual verification required")
    lines.append("")

    lines.append("### Sources")
    lines.append("")

    for index, item in enumerate(headlines, 1):
        lines.append(f"{index}. **{item['title']}**")
        lines.append(f"   - Publisher: {item['source']}")
        lines.append(f"   - Published: {item['date'] or 'Not listed'}")
        lines.append(f"   - Link: {item['link']}")

        if item["description"]:
            lines.append(
                "   - Available summary: " + item["description"]
            )

        lines.append("")

    lines.append("### Automatic Reel narration")
    lines.append("")
    lines.append(narration)
    lines.append("")

    word_count = len(narration.split())
    lines.append(f"**Word count:** {word_count}")
    lines.append("**Estimated duration:** Depends on speaking speed.")
    lines.append("")

    lines.append("### Caption")
    lines.append("")
    lines.append(
        "A closer look at " + topic
        + ". Read the latest reports and follow InfoRush for more."
    )
    lines.append("")

    lines.append("### Hashtags")
    lines.append("")
    lines.append(
        "#InfoRush #LatestNews #Trending #DiscoverMore"
    )
    lines.append("")

    lines.append("### Important verification checklist")
    lines.append("")
    lines.append("- [ ] Open the original source articles.")
    lines.append("- [ ] Confirm the reports describe the same event.")
    lines.append("- [ ] Verify all names, dates, figures and locations.")
    lines.append("- [ ] Compare the summaries with the original articles.")
    lines.append("- [ ] Check for newer developments or corrections.")
    lines.append("- [ ] Remove any unsupported or misleading statement.")
    lines.append("- [ ] Review the final narration before publishing.")
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def main():
    topics = read_topics()

    if not topics:
        print("No suitable categorized topics found.")
        return

    categories = list(CATEGORIES.keys())

    day_number = datetime.now(timezone.utc).timetuple().tm_yday
    shift = day_number % len(categories)
    categories = categories[shift:] + categories[:shift]

    selected = []

    for category in categories:
        if len(selected) >= 2:
            break

        candidates = [
            item for item in topics
            if item["category"] == category
        ]

        for candidate in candidates[:3]:
            headlines = get_headlines(candidate["topic"])

            story_group = find_story_group(
                headlines,
                candidate["topic"]
            )

            if len(story_group) >= 2:
                selected.append({
                    "category": category,
                    "topic": candidate["topic"],
                    "headlines": story_group
                })
                break

    output = [
        "# InfoRush Content Drafts",
        "",
        "Generated: " + datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        ),
        "",
        "Automatic drafts generated from Google News RSS headlines "
        "and available feed summaries. These are not independently "
        "fact-checked. Verify all details before publishing.",
        ""
    ]

    if not selected:
        output.append(
            "No story passed the current filters. No Reel draft "
            "was generated."
        )
    else:
        output.append(
            f"{len(selected)} candidate story draft(s) selected."
        )
        output.append("")

        for story in selected:
            output.append(
                create_draft(
                    story["category"],
                    story["topic"],
                    story["headlines"]
                )
            )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(output))

    print("Content drafts created!")
    print("Stories selected:", len(selected))


if __name__ == "__main__":
    main()
