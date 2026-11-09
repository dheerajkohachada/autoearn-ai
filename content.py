
import os
import re
import html
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
from datetime import datetime, timezone

INPUT_FILE = "trend_report.md"
OUTPUT_FILE = "content_drafts.md"

# Topics to avoid: private-life gossip and rumours
SKIP_PATTERN = re.compile(
    r"\b(divorce|ex-wife|ex-husband|dating|breakup|"
    r"relationship|gossip|rumou?r)\b",
    re.IGNORECASE
)

CATEGORIES = {
    "World News": [
        "world", "election", "government", "parliament",
        "president", "prime minister", "minister", "policy",
        "war", "conflict", "summit", "protest", "economy",
        "inflation", "oil price", "trade", "border",
        "earthquake", "cyclone", "flood", "disaster",
        "climate", "nato"
    ],
    "Technology & AI": [
        "technology", "tech", "artificial intelligence",
        "AI", "chatgpt", "openai", "google", "apple",
        "microsoft", "samsung", "iphone", "android",
        "oppo", "smartphone", "chip", "robot", "cyber",
        "app", "software", "gaming", "cloud gaming"
    ],
    "Sports": [
        "cricket", "league", "tournament", "match",
        "football", "soccer", "tennis", "basketball",
        "NBA", "FIFA", "olympic", "championship",
        "player", "team", "score", "world cup",
        "U19", "T10", "IPL"
    ],
    "Science & Discoveries": [
        "science", "scientist", "research", "discovery",
        "NASA", "space", "moon", "mars", "satellite",
        "planet", "astronomy", "physics", "biology",
        "fossil", "dinosaur", "experiment", "mission"
    ],
    "Viral Trends": [
        "viral", "meme", "internet", "social media",
        "trending", "trend", "tiktok", "instagram",
        "youtube", "reddit", "challenge", "online"
    ],
    "Interesting Facts": [
        "fact", "facts", "history", "mystery",
        "record", "world record", "unusual",
        "amazing", "interesting", "did you know",
        "invention", "ancient", "archaeology"
    ]
}

HASHTAGS = {
    "World News": "#WorldNews #CurrentAffairs #GlobalNews",
    "Technology & AI": "#Technology #AI #TechNews",
    "Sports": "#Sports #Cricket #SportsNews",
    "Science & Discoveries": "#Science #Discoveries #Space",
    "Viral Trends": "#ViralTrends #InternetTrends #Trending",
    "Interesting Facts": "#AmazingFacts #DidYouKnow #Facts"
}


def classify_topic(topic):
    text = topic.lower()

    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword.lower()) + r"\b"

            if re.search(pattern, text):
                return category

    return None


def read_topics():
    if not os.path.exists(INPUT_FILE):
        print("Trend report not found.")
        return []

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        lines = file.readlines()

    topics = []
    seen = set()

    for line in lines:
        match = re.match(r"^\s*\d+\.\s+(.+?)\s*$", line)

        if not match:
            continue

        topic = match.group(1).strip()
        key = topic.lower()

        if key in seen or SKIP_PATTERN.search(topic):
            continue

        seen.add(key)

        category = classify_topic(topic)

        if category:
            topics.append((category, topic))

    return topics


def get_headlines(topic):
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(topic)
        + "&hl=en-US&gl=US&ceid=US:en"
    )

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(request, timeout=12) as response:
            root = ET.fromstring(response.read())

        headlines = []
        seen = set()

        for item in root.findall(".//item")[:5]:
            title = html.unescape(
                item.findtext("title", "").strip()
            )

            source_element = item.find("source")
            source = (
                source_element.text.strip()
                if source_element is not None and source_element.text
                else "News source not identified"
            )

            link = item.findtext("link", "").strip()
            published = item.findtext("pubDate", "").strip()

            if title and title.lower() not in seen:
                seen.add(title.lower())

                headlines.append({
                    "title": title,
                    "source": source,
                    "link": link,
                    "published": published
                })

        return headlines

    except Exception as error:
        print("Research error for", topic, ":", error)
        return []


def create_draft(category, topic, headlines):
    lines = [
        f"## {category}: {topic}",
        "",
        "**Research headlines and sources:**",
        ""
    ]

    for item in headlines:
        title = item["title"]
        source = item["source"]
        link = item["link"]
        published = item["published"]

        if link:
            lines.append(
                f"- **{source}** — [{title}]({link})"
            )
        else:
            lines.append(f"- **{source}** — {title}")

        if published:
            lines.append(f"  - Published: {published}")

    first = headlines[0]

    lines.extend([
        "",
        "**30–45 second Reel script draft:**",
        "",
        "**HOOK:**",
        f"Here's a story gaining attention in {category}: {topic}.",
        "",
        "**WHAT THE REPORTS SAY:**",
        f"According to {first['source']}: {first['title']}"
    ])

    for item in headlines[1:3]:
        lines.append(
            f"Another report from {item['source']}: {item['title']}"
        )

    lines.extend([
        "",
        "**VERIFIED CONTEXT:**",
        "[Read the linked articles and add the confirmed details: who, what, when and where.]",
        "",
        "**ENDING:**",
        "Follow InfoRush for more world updates, technology and interesting discoveries.",
        "",
        "**Caption:**",
        f"Today's update: {topic}. What would you like to know about this story? Follow InfoRush for more.",
        "",
        "**Hashtags:**",
        f"#InfoRush {HASHTAGS[category]} #DiscoverMore",
        "",
        "**Before publishing:**",
        "- [ ] Open and verify the source articles.",
        "- [ ] Confirm the date and important facts.",
        "- [ ] Check whether the story has been updated.",
        "- [ ] Add verified context to the script.",
        "- [ ] Check names, numbers and pronunciations.",
        "",
        "---",
        ""
    ])

    return lines


def main():
    topics = read_topics()

    drafts = [
        "# InfoRush Content Drafts",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "Two research-based content candidates selected using rotating categories.",
        "All stories require source verification before publishing.",
        ""
    ]

    # Rotate category priority every day
    category_names = list(CATEGORIES.keys())
    day_number = datetime.now(timezone.utc).timetuple().tm_yday
    start = day_number % len(category_names)

    rotated_categories = (
        category_names[start:] + category_names[:start]
    )

    selected = []

    for category in rotated_categories:
        candidates = [
            topic for cat, topic in topics
            if cat == category
        ]

        # Try up to two topics from each category
        for topic in candidates[:2]:
            headlines = get_headlines(topic)

            if headlines:
                selected.append((category, topic, headlines))
                break

        if len(selected) == 2:
            break

    if not selected:
        drafts.extend([
            "No suitable topics with research headlines were found today.",
            "Check the trend report and try again."
        ])

    for category, topic, headlines in selected:
        drafts.extend(create_draft(category, topic, headlines))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(drafts))

    print("Content drafts created!")
    print("Number of selected stories:", len(selected))

    for category, topic, headlines in selected:
        print(category, "-", topic, "-", len(headlines), "headlines")


if __name__ == "__main__":
    main()
