
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

COUNTRIES = {
    "India": "IN",
    "United States": "US",
    "United Kingdom": "GB",
    "Canada": "CA"
}

def get_trends(country, code):
    url = f"https://trends.google.com/trending/rss?geo={code}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())

        items = root.findall(".//item")
        trends = []

        for item in items[:15]:
            title = item.findtext("title", default="").strip()
            if title:
                trends.append(title)

        return trends

    except Exception as error:
        print(f"Could not fetch {country}: {error}")
        return []

def main():
    report = [
        "# InfoRush Trending Topics",
        f"Updated: {datetime.utcnow()} UTC",
        "",
        "These are trend candidates, not verified news.",
        ""
    ]

    for country, code in COUNTRIES.items():
        print(f"Checking {country}...")
        trends = get_trends(country, code)

        report.append(f"## {country}")
        if trends:
            for number, trend in enumerate(trends, 1):
                report.append(f"{number}. {trend}")
        else:
            report.append("No trends retrieved.")

        report.append("")

    with open("trend_report.md", "w", encoding="utf-8") as file:
        file.write("\n".join(report))

    print("InfoRush trend report created!")

if __name__ == "__main__":
    main()
