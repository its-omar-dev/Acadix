"""YouTube and course-platform search helpers."""
import urllib.parse

from youtubesearchpython import VideosSearch


def search_learning_links(topic):
    courses = []
    try:
        search = VideosSearch(topic, limit=6)
        result = search.result()
        if result and "result" in result:
            for video in result.get("result", []):
                if isinstance(video, dict) and video.get("title") and video.get("link"):
                    courses.append(
                        {
                            "platform": "يوتيوب (YouTube)",
                            "title": str(video["title"]),
                            "link": str(video["link"]),
                        }
                    )
    except Exception:
        pass

    encoded = urllib.parse.quote(topic)
    if not courses:
        courses.append(
            {
                "platform": "يوتيوب (YouTube)",
                "title": f"عرض أفضل الفيديوهات والروابط التعليمية لـ '{topic}' على يوتيوب",
                "link": f"https://www.youtube.com/results?search_query={encoded}",
            }
        )

    courses.extend(
        [
            {
                "platform": "منصة مَعارف (M3aarf)",
                "title": f"مسارات ودورات '{topic}' المتوفرة",
                "link": f"https://www.m3aarf.com/?search_for={encoded}",
            },
            {
                "platform": "منصة إدراك (Edraak)",
                "title": f"مساقات وبرامج '{topic}' المجانية",
                "link": f"https://www.edraak.org/explore/?query={encoded}",
            },
            {
                "platform": "كورسيرا (Coursera)",
                "title": f"شهادات وبرامج أكاديمية لـ '{topic}'",
                "link": f"https://www.coursera.org/search?query={encoded}",
            },
            {
                "platform": "يوديمي (Udemy)",
                "title": f"أبرز الدورات التدريبية لـ '{topic}'",
                "link": f"https://www.udemy.com/courses/search/?q={encoded}",
            },
        ]
    )
    return courses
