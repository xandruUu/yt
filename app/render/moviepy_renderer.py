from __future__ import annotations


def moviepy_available() -> bool:
    try:
        import moviepy  # noqa: F401
    except ImportError:
        return False
    return True


def render_with_moviepy_placeholder() -> None:
    raise NotImplementedError("MoviePy rendering is reserved for a later visual iteration.")

