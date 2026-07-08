# Setup

## 1. Create the environment

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## 2. Create local config

```bash
copy .env.example .env
```

Edit `.env` only if you want custom folders or dimensions.

## 3. Install FFmpeg

Rendering requires `ffmpeg` in PATH. The app can still manage topics, hooks, scripts, assets, music, reviews, and exports without it.

## 4. Start the dashboard

```bash
streamlit run app/main.py
```

## 5. Run tests

```bash
pytest
```
