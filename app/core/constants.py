DEFAULT_LANGUAGES = ("en", "es", "hi_hinglish")
DEFAULT_MARKETS = ("global", "spain_latam", "india")
DEFAULT_RESOLUTION = "1080x1920"
DEFAULT_FPS = 30
DEFAULT_TARGET_DURATION_SECONDS = 38

EXPORT_FILE_NAMES = (
    "video.mp4",
    "title.txt",
    "description.txt",
    "hashtags.txt",
    "script.txt",
    "subtitles.srt",
    "voiceover.txt",
    "visual_plan.json",
    "render_plan.json",
    "metadata.json",
    "review_checklist.json",
    "license_manifest.json",
)

SAFE_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
SAFE_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
SAFE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SAFE_FONT_EXTENSIONS = {".ttf", ".otf"}
SAFE_TEXT_EXTENSIONS = {".txt", ".json", ".srt", ".ass", ".md"}
