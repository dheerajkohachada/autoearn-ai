
import re
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

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
            source_element = item.find("source")

            source = (
                source_element.text.strip()
                if source_element is not None and source_element.text
                else "Publisher not listed"
            )

            if title and link:
                headlines.append({
                    "title": html.unescape(title),
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
    """
    Filter out previews and viewing information.
    Group event headlines with overlapping specific words.
    This does not independently verify facts.
    """

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


def create_draft(category, topic, headlines):
    lines = []

    lines.append("## " + category + ": " + topic)
    lines.append("")
    lines.append("**Status:** Candidate — verify before publishing")
    lines.append("")
    lines.append("### Related event headlines")
    lines.append("")

    for index, item in enumerate(headlines, 1):
        lines.append(f"{index}. **{item['title']}**")
        lines.append(f"   - Publisher: {item['source']}")
        lines.append(f"   - Published: {item['date'] or 'Not listed'}")
        lines.append(f"   - Source: {item['link']}")
        lines.append("")

    lines.append("### Reel script — 30 to 45 seconds")
    lines.append("")
    lines.append(
        "**HOOK:** A major update is attracting attention in "
        + category + "."
    )
    lines.append("")
    lines.append(
        "**WHAT HAPPENED:** [State the specific confirmed event, "
        "including the people or organisations involved.]"
    )
    lines.append("")
    lines.append(
        "**KEY DETAILS:** [Add confirmed figures, dates, location "
        "and important developments.]"
    )
    lines.append("")
    lines.append(
        "**WHY IT MATTERS:** [Explain the verified significance "
        "in simple English.]"
    )
    lines.append("")
    lines.append(
        "**ENDING:** Follow InfoRush for more important updates."
    )
    lines.append("")
    lines.append("### Caption")
    lines.append("")
    lines.append(
        "Here is the latest update on " + topic
        + ". Follow InfoRush for more."
    )
    lines.append("")
    lines.append("### Hashtags")
    lines.append("")
    lines.append(
        "#InfoRush #LatestNews #Trending #DiscoverMore"
    )
    lines.append("")
    lines.append("### Verification checklist")
    lines.append("")
    lines.append("- [ ] Confirm both headlines describe the same event.")
    lines.append("- [ ] Open and read the original articles.")
    lines.append("- [ ] Verify names, dates, numbers and locations.")
    lines.append("- [ ] Check for newer developments or corrections.")
    lines.append("- [ ] Add only facts supported by reliable sources.")
    lines.append("- [ ] Review the final script before publishing.")
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
    used_categories = set()

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

                used_categories.add(category)
                break

    output = [
        "# InfoRush Content Drafts",
        "",
        "Generated: " + datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        ),
        "",
        "Automated research candidates only. Headline similarity "
        "does not establish that reports describe the same event "
        "or prove their accuracy.",
        ""
    ]

    if not selected:
        output.append(
            "No story passed the current headline filters. "
            "No Reel draft was generated. This is preferable "
            "to publishing an unrelated or misleading story."
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
