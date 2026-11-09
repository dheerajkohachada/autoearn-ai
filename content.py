import re
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from collections import Counter

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

STOP_WORDS = set("""
the a an and or but of to in on at for from by with is are was were
be been being this that these those as it its after before over under
about into than then who what when where why how says said report
reports according latest update updates news today live watch
schedule result results team teams match tournament asia cup
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
        "https://news.google.com/rss/search?q=" + query
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
    Find headlines with overlapping specific details.
    This is only an automated similarity check, not fact verification.
    """

    scored = []

    for headline in headlines:
        headline["keywords"] = meaningful_words(
            headline["title"], topic
        )

    for first in headlines:
        group = [first]

        for second in headlines:
            if first is second:
                continue

            overlap = first["keywords"] & second["keywords"]

            if len(overlap) >= 1:
                group.append(second)

        if len(group) > len(scored):
            scored = group

    # Require at least two headlines with some specific overlap.
    if len(scored) < 2:
        return []

    unique = []
    seen = set()

    for item in scored:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique.append(item)

    return unique[:4]


def create_draft(category, topic, headlines):
    lines = []

    lines.append("# " + category + ": " + topic)
    lines.append("")
    lines.append("**Story status:** Candidate — manual verification required")
    lines.append("")
    lines.append("## Related research headlines")
    lines.append("")

    for index, item in enumerate(headlines, 1):
        lines.append(
            f"{index}. **{item['title']}**"
        )
        lines.append(f"   - Publisher: {item['source']}")
        lines.append(f"   - Date: {item['date'] or 'Not listed'}")
        lines.append(f"   - Link: {item['link']}")
        lines.append("")

    lines.append("## 30–45 second Reel script draft")
    lines.append("")
    lines.append(
        "**HOOK:** A developing story in " + category
        + " is attracting attention."
    )
    lines.append("")
    lines.append(
        "**INTRODUCTION:** The story concerns: [Insert the exact "
        "event after checking the sources]."
    )
    lines.append("")
    lines.append(
        "**MAIN UPDATE:** [Explain what happened, who is involved, "
        "where it happened and when. Use only confirmed details.]"
    )
    lines.append("")
    lines.append(
        "**WHY IT MATTERS:** [Explain the confirmed significance "
        "in one or two simple sentences.]"
    )
    lines.append("")
    lines.append(
        "**ENDING:** Follow InfoRush for more updates, technology "
        "and interesting discoveries."
    )
    lines.append("")
    lines.append("## Caption")
    lines.append("")
    lines.append(
        "A closer look at this developing story: "
        + topic + ". Follow InfoRush for more."
    )
    lines.append("")
    lines.append("## Hashtags")
    lines.append("")
    tag = re.sub(r"[^a-zA-Z0-9]", "", category.title().replace("&", ""))
    lines.append(
        "#InfoRush #" + tag + " #LatestNews #Trending "
        "#DiscoverMore"
    )
    lines.append("")
    lines.append("## Before publishing")
    lines.append("")
    lines.append("- [ ] Confirm that all headlines describe the same event.")
    lines.append("- [ ] Read the original source articles.")
    lines.append("- [ ] Confirm names, dates, locations and numbers.")
    lines.append("- [ ] Check for corrections or newer updates.")
    lines.append("- [ ] Add only facts supported by reliable sources.")
    lines.append("- [ ] Review the final script before recording.")
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def main():
    topics = read_topics()

    if not topics:
        print("No suitable categorized topics found.")
        return

    # Rotate category priority each day.
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
                headlines, candidate["topic"]
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
        "These are candidate stories. Similarity matching does not "
        "prove that reports describe the same event. Verify every "
        "story manually before publishing.",
        ""
    ]

    if not selected:
        output.append(
            "No story had enough related headlines today. "
            "No Reel draft was generated. Try again later."
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
