# Deck HTML Template

## Slide Structure Template

### HTML Skeleton

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[Deck Title]</title>
  <!-- Red Hat Design Tokens (spacing, typography, borders, shadows) -->
  <link href="https://cdn.jsdelivr.net/npm/@rhds/tokens@3.0.2/css/global.min.css" rel="stylesheet">
  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@400;500;700;900&family=Red+Hat+Text:wght@400;500;700&family=Red+Hat+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    /* === RESET & BASE === */
    :root { color-scheme: dark; } /* Set to 'light' for Core Light mode */
    /* === COLOR VARIABLES (dark or light, based on user choice) === */
    /* === TYPOGRAPHY (uses --rh-font-family-* and --rh-font-size-* tokens with fallbacks) === */
    /* === SPACING (uses --rh-space-* tokens with fallbacks) === */
    /* === LOGO STYLES === */
    /* === ICON STYLES === */
    /* === SLIDE CONTAINER === */
    /* === NAVIGATION === */
    /* === SLIDE TYPES === */
    /* === CONTEXTUAL NOTES PANEL === */
    /* === ANIMATIONS === */
  </style>
</head>
<body>
  <div class="deck">
    <!-- SLIDE 1: TITLE (includes logo in breadcrumb) -->
    <div class="slide">
      <div class="breadcrumb">
        <!-- Inline Red Hat logo SVG (reverse for dark, standard for light) -->
        <svg class="rh-logo small" ...>[appropriate logo paths]</svg>
        <span>› [Team / Group]</span>
      </div>
      <!-- ... rest of title slide ... -->
    </div>

    <!-- CONTENT SLIDES (no logo — brand presence via red accents) -->
    <!-- VIDEO SLIDES use .video-container with iframe or video tag -->
    <!-- MEDIA SLIDES use .media-container with img tag (memes, GIFs, linked images) -->

    <!-- FINAL SLIDE: CTA (includes larger logo) -->
    <div class="slide">
      <!-- ... content ... -->
      <div class="logo-footer">
        <svg class="rh-logo large" ...>[appropriate logo paths]</svg>
      </div>
    </div>
  </div>
  <div class="controls">
    <div class="nav-hint">← → or click to navigate · N for additional context</div>
    <div class="progress"><span class="current">1</span> / <span class="total">10</span></div>
  </div>
  <script>
    // Navigation logic
  </script>
</body>
</html>
```

### Required Slide Types

Every deck should include these slide types (adapt as needed):

#### 1. Title Slide
- Breadcrumb / source label (e.g., "RED HAT › NAPS STP") in small monospace, top-left
- Working group or team label + date in red monospace, left-aligned
- Large bold headline in Red Hat Display Black weight
- Accent word(s) in the headline colored red-50
- Subtitle / description in lighter text below
- Tag pills for key concepts
- Author attribution at bottom: "Name · Role · Organization"

#### 2. Content Slide
- Slide headline as an assertion (not a label)
- Body content: paragraphs, bullet points (use sparingly), or key-value pairs
- Optional: a small icon (`.rh-icon.small`) beside the headline for topical accent
- Optional: icons as feature list markers instead of bullet characters
- Optional: source attribution at bottom

#### 3. Big Number / Stat Slide
- Optional: topic icon (`.rh-icon.xl.accent`) centered above the big number
- One large number (80-120px font size) in red-50 or white
- Brief context line below in gray-30
- Source attribution at bottom

#### 4. Comparison / Before-After Slide
- Two-column layout
- Optional: icons representing each side as column headers (e.g., `padlock-unlocked` vs `padlock-locked`)
- Clear visual distinction between old/new or with/without
- Use red-50 to highlight the preferred side

#### 5. Architecture / Diagram Slide
- CSS-based box diagrams with flexbox/grid (no images required)
- Boxes with borders and labels — use icons (`.rh-icon.small`) inside boxes alongside text labels for visual clarity
- Arrows represented with CSS or Unicode characters (→, ↓)
- Red-50 highlight on the key innovation

#### 6. Quote Slide
- Large pull quote in Red Hat Display, medium weight
- Attribution below
- Red-50 opening quotation mark as decorative element

#### 7. Call-to-Action / Closing Slide
- Clear next steps
- Contact info or resources
- QR code placeholder if relevant (note in contextual notes)

#### 8. Video Slide
- Use when the user provides a video URL or asks to embed a video
- Supports **YouTube**, **Vimeo** (via thumbnail + click-to-embed iframe), and **direct video URLs** (via ` ` tag)
- Headline with optional accent word above the video
- 16:9 responsive container with brand-consistent framing (shadow, rounded corners)
- Optional caption below the video for context
- Source attribution at bottom
- Click the play button to start the video; controls are visible for pause/seek

**⚠ IMPORTANT — When a user adds a video slide, you MUST inform them:**

> **Inline video playback requires serving this deck via HTTP or HTTPS.**
> YouTube and Vimeo embeds do not work when opening the HTML file directly
> from your filesystem (`file://` protocol) — this is a browser security
> restriction that cannot be worked around.
>
> To enable inline video playback:
> - **Quick local server:** Run `python3 -m http.server` in the deck's folder,
> then open `http://localhost:8000/deck-name.html`
> - **Or use:** `npx serve`, VS Code Live Server, or any static file host
> - **Or host it:** Upload to any web server, GitHub Pages, S3, etc.
>
> When opened as a local file, clicking a video will open it on YouTube in a
> new browser tab instead.

This message should be delivered **every time** a video slide is added to a deck. Do not skip it.

**URL conversion rules:**
- YouTube `https://www.youtube.com/watch?v=VIDEO_ID` → `https://www.youtube-nocookie.com/embed/VIDEO_ID?enablejsapi=1&mute=1`
- YouTube `https://youtu.be/VIDEO_ID` → `https://www.youtube-nocookie.com/embed/VIDEO_ID?enablejsapi=1&mute=1`
- Vimeo `https://vimeo.com/VIDEO_ID` → `https://player.vimeo.com/video/VIDEO_ID?muted=1`
- Direct `.mp4`, `.webm`, `.ogg` URLs → use ` ` tag with `muted` attribute

**YouTube/Vimeo implementation — thumbnail + open-in-new-tab pattern:**

YouTube iframes have multiple failure modes: `file://` protocol blocks them (Error 153), ad blockers
block YouTube's tracking requests (`ERR_BLOCKED_BY_CLIENT`), and CSP policies can prevent embedding.
To ensure decks work reliably everywhere, **always use the thumbnail + new-tab pattern**:

1. Show the YouTube thumbnail as an image with a branded red play button overlay
2. On click, open the video on youtube.com in a new browser tab
3. The presenter's slide stays visible — they can return to it after watching

This approach has zero dependencies on iframes, works from any protocol, and is immune to ad blockers.

The thumbnail URL pattern: `https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg`
(falls back to `hqdefault.jpg` if maxres isn't available)

**Required CSS for video slides:**
```css
.video-thumbnail {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover;
}
.video-play-btn {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 80px; height: 80px; background: rgba(238,0,0,0.9); border-radius: 50%;
  display: flex; align-items: center; justify-content: center; z-index: 2;
  transition: background 0.2s ease;
}
.video-play-btn::after {
  content: ''; display: block; width: 0; height: 0;
  border-style: solid; border-width: 14px 0 14px 24px;
  border-color: transparent transparent transparent #fff; margin-left: 4px;
}
.video-container:hover .video-play-btn { background: rgba(238,0,0,1); }
```

**Required JavaScript** (inside the navigation IIFE, BEFORE the navigation click handler):
```javascript
// Click-to-play for video thumbnails
// HTTP/HTTPS: embed iframe inline for seamless playback
// file://: open in new tab (YouTube blocks iframe embeds from file:// protocol)
document.addEventListener('click', (e) => {
  const vc = e.target.closest('.video-container[data-video-id]');
  if (vc) {
    e.stopImmediatePropagation(); // prevent navigation handler from firing
    const vid = vc.dataset.videoId;
    if (window.location.protocol === 'file:') {
      window.open('https://www.youtube.com/watch?v=' + vid, '_blank');
    } else {
      const iframe = document.createElement('iframe');
      iframe.src = 'https://www.youtube-nocookie.com/embed/' + vid + '?autoplay=1';
      iframe.setAttribute('frameborder', '0');
      iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
      iframe.setAttribute('allowfullscreen', '');
      vc.innerHTML = '';
      vc.appendChild(iframe);
    }
    return;
  }
});
```

**Why `e.stopImmediatePropagation()`**: When the click handler replaces the video container's
innerHTML, the clicked element (play button) becomes detached from the DOM. Without stopping
propagation, the navigation click handler can't find `.video-container` via `closest()` on the
detached target and accidentally advances the slide.

**Inline video playback note**: Include in the first slide's contextual notes and the nav hint
that videos play inline when served via HTTP (`python3 -m http.server`). When opened as a local
file, videos open on YouTube in a new tab instead.

```html
<!-- YouTube video (thumbnail + new-tab pattern) -->
<div class="slide" data-notes="[notes]">
  <div class="slide-label animate-in">—— LABEL</div>
  <h2 class="animate-in">Headline <span class="accent">with accent</span></h2>
  <div class="video-container animate-in" data-video-id="VIDEO_ID">
    <img class="video-thumbnail" src="https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg" alt="Video description">
    <div class="video-play-btn"></div>
  </div>
  <div class="media-caption animate-in">Optional context about the video</div>
  <div class="source animate-in">Source attribution</div>
</div>

<!-- Direct video file (works from file:// natively) -->
<div class="slide" data-notes="[notes]">
  <div class="slide-label animate-in">—— LABEL</div>
  <h2 class="animate-in">Headline <span class="accent">with accent</span></h2>
  <div class="video-container animate-in">
    <video controls muted preload="metadata">
      <source src="https://example.com/video.mp4" type="video/mp4">
    </video>
  </div>
  <div class="media-caption animate-in">Optional context</div>
  <div class="source animate-in">Source attribution</div>
</div>
```

#### 9. Media Slide (Memes, GIFs, Linked Images, Giphy)
- Use when the user provides an image/meme/GIF URL or asks to include visual media
- Supports any image format: JPG, PNG, GIF (including animated), WebP, SVG
- Supports **Giphy** GIFs (see URL conversion rules below)
- Responsive container that preserves the original aspect ratio
- Optional caption below for humor, context, or commentary — use a lighter tone for memes
- Source / credit line at bottom
- Works for memes, reaction GIFs, diagrams, screenshots, photos — any linked image
- **Important**: Use full-resolution image URLs, not thumbnails. For imgflip templates, use the
 `https://imgflip.com/s/meme/Template-Name.jpg` pattern (full-size) instead of
 `https://i.imgflip.com/2/xxxxx.jpg` (150x150 thumbnails)

**Media URL conversion rules:**
- Giphy page `https://giphy.com/gifs/SLUG-ID` → `https://media.giphy.com/media/ID/giphy.gif`
- Giphy short `https://gph.is/SHORTCODE` → resolve to full URL, then extract ID for `https://media.giphy.com/media/ID/giphy.gif`
- Giphy direct links (`media.giphy.com`, `media0-4.giphy.com`) → use as-is
- Imgflip templates → use `https://imgflip.com/s/meme/Template-Name.jpg` (full-size)
- Direct image URLs (`.jpg`, `.png`, `.gif`, `.webp`, `.svg`) → use as-is
- **Local files** (via `@file`, file path, or "use this image") → embed as base64 data URI (see below)

#### Local File / @file Image Support

When the user provides a local file path or references an image via `@file`, embed the image
directly into the HTML as a **base64 data URI**. This keeps the deck fully self-contained and
portable — the image travels with the HTML file.

**Encoding workflow:**

1. Determine the MIME type from the file extension:
 - `.png` → `image/png`
 - `.jpg` / `.jpeg` → `image/jpeg`
 - `.gif` → `image/gif`
 - `.webp` → `image/webp`
 - `.svg` → `image/svg+xml`

2. Base64-encode the file using a shell command:
   ```bash
   base64 -i /path/to/image.png | tr -d '\n'
   ```

3. Construct the data URI and use it as the `src`:
   ```html
   <img src="data:image/png;base64,iVBORw0KGgo..." alt="Description" class="slide-media">
   ```

**Important notes:**
- This works for any image the user can reference — screenshots, diagrams, downloaded memes,
 photos, exported charts, etc.
- Base64 increases file size by ~33%, so very large images (>5MB) may make the HTML file unwieldy.
 For large images, suggest the user resize or compress first.
- Animated GIFs can be embedded as base64 but will be large. For animated content, prefer Giphy
 links when possible.
- The user may provide images by:
 - Using `@file` syntax: `@screenshot.png` or `@/Users/name/Desktop/diagram.png`
 - Pasting a file path: `/tmp/my-meme.jpg`
 - Saying "use this image" with a file reference in context
 - Dragging an image into the conversation

```html
<!-- Standard image/meme -->
<div class="slide" data-notes="[notes]">
  <div class="slide-label animate-in">—— LABEL</div>
  <h2 class="animate-in">Headline <span class="accent">with accent</span></h2>
  <div class="media-container animate-in">
    <img src="https://example.com/meme.gif" alt="Descriptive alt text" class="slide-media">
  </div>
  <div class="media-caption animate-in">Optional witty caption or context</div>
  <div class="source animate-in">Source / credit</div>
</div>

<!-- Giphy GIF example -->
<div class="slide" data-notes="[notes]">
  <div class="slide-label animate-in">—— LABEL</div>
  <h2 class="animate-in">Headline <span class="accent">with accent</span></h2>
  <div class="media-container animate-in">
    <img src="https://media.giphy.com/media/GIPHY_ID/giphy.gif" alt="Descriptive alt text" class="slide-media">
  </div>
  <div class="media-caption animate-in">Caption</div>
  <div class="source animate-in">via Giphy</div>
</div>
```

#### 10. Thank You Slide (Required — always the final slide)
- Large "Thank You" headline in Red Hat Display, Black weight
- Accent word ("You") in red-50
- Author name, role, and organization centered below
- Red Hat logo (large) centered beneath attribution
- Optionally include contact email, social handle, or team URL in small muted text
- Keep it clean — no tags, no body text, generous whitespace
- The ambient glow effect should be prominent on this slide for a strong visual close

