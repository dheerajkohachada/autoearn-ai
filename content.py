
import os
import re
import xml.etree.ElementTree as ET
import urllib.request
from datetime import datetime

INPUT_FILE = "trend_report.md"
OUTPUT_FILE = "content_drafts.md"

def get_headlines(topic):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(topic) + "&hl=en-US&gl=US&ceid=US:en"

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            root = ET.fromstring(response.read())

        headlines = []
        for item in root.findall(".//item")[:3]:
            title = item.findtext("title", "").strip()
            if title:
                headlines.append(title)

        return headlines

    except Exception:
        return []

def main():
    if not os.path.exists(INPUT_FILE):
        print("Trend report not found.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        lines = file.readlines()

    topics = []
    for line in lines:
        match = re.match(r"\d+\.\s+(.+)", line.strip())
        if match:
            topics.append(match.group(1))

    drafts = [
        "# InfoRush Content Drafts",
        f"Generated: {datetime.utcnow()} UTC",
        "",
        "Review and verify every story before publishing.",
        ""
    ]

    used = set()

    for topic in topics:
        if topic in used:
            continue
        used.add(topic)

        headlines = get_headlines(topic)

        if not headlines:
            continue

        drafts.extend([
            f"## Topic: {topic}",
            "",
            "**Research headlines:**"
        ])

        for headline in headlines:
            drafts.append(f"- {headline}")

        drafts.extend([
            "",
            "**Reel script draft:**",
            f"Here's what people are talking about: {topic}.",
            "Recent headlines are drawing attention to this topic.",
            "Check the latest verified details before sharing.",
            "",
            "**Caption:**",
            f"What's your take on {topic}? Follow InfoRush for more updates.",
            "",
            "**Hashtags:**",
            "#InfoRush #Trending #News #Technology #DiscoverMore",
            "",
            "---",
            ""
        ])

        if len(used) >= 2:
            break

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(drafts))

    print("Content drafts created!")

if __name__ == "__main__":
    main()
