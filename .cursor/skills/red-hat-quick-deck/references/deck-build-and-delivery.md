# Deck Build and Delivery

## Building the Narrative

When the user gives you a topic, follow this process:

### Step 1: Research (if web search available)
Search for current statistics, quotes, and developments related to the topic. Look for:
- Recent industry reports or surveys with quotable numbers
- Expert quotes that support the thesis
- Competitive landscape data
- Adoption metrics or trends

### Step 2: Choose a Story Arc
Read `references/story-arcs.md` and select the best arc for the content:
- **Problem → Tension → Resolution**: Best for introducing a new tool, approach, or technology
- **Myth-Busting**: Best for challenging conventional thinking
- **Journey**: Best for case studies or retrospectives

### Step 3: Outline the Deck
Write the slide headlines FIRST. The headlines alone should tell the complete story. Show the user
the outline before generating the full HTML if the topic is complex.

### Step 4: Write Each Slide
For each slide:
- Write the headline as an assertion
- Write concise supporting content (fewer words = more impact)
- Choose the appropriate slide type
- Add source attributions where data is cited
- Add contextual notes with references, links, deeper explanations, and related resources that let viewers dive deeper into the slide's topic

### Step 5: Note Video & Media Opportunities
As you build the narrative, identify slides where a video or meme could strengthen the story —
a demo video after an architecture slide, a reaction meme to break tension after a dense section,
etc. **Do not insert Video or Media slides during initial generation.** Instead, note opportunities
in the contextual notes like:

```
[VIDEO OPPORTUNITY] A short demo of [feature] here would reinforce the architecture on the previous slide.
[MEME OPPORTUNITY] A well-placed meme here could break the tension after the dense comparison slide.
```

After delivering the deck, the post-generation prompt (see "Post-Generation: Video & Media Placement")
will guide the user to add these if they choose.

### Step 6: AI Image Opportunities
As you build slides, identify moments where a custom AI-generated image would elevate the deck.
For each opportunity, add a note in the contextual notes like:

```
[IMAGE OPPORTUNITY] Prompt for Nano Banana Pro 2:
"[detailed image generation prompt describing the desired visual,
style, composition, colors, and mood — incorporating Red Hat brand
colors where appropriate]"
```

Good candidates for AI images:
- Title slide hero visuals (abstract, on-brand)
- Concept illustrations (e.g., "air gap" as a visual metaphor)
- Background textures or atmospheric elements
- Infographic-style data visualizations
- Metaphorical illustrations for complex concepts

When writing prompts, specify:
- Dark background compatible (for Core Dark decks)
- Red Hat color palette (reds, dark grays, subtle teals/purples)
- No text in the image (text will be overlaid in HTML)
- Aspect ratio suited for the slide layout (usually 16:9 or specific region)

## Navigation JavaScript

Include this navigation system in every deck:

```javascript
(function() {
  const slides = document.querySelectorAll('.slide');
  const currentEl = document.querySelector('.current');
  const totalEl = document.querySelector('.total');
  const notesPanel = document.querySelector('.notes-panel');
  let idx = 0;
  let notesVisible = false;

  totalEl.textContent = slides.length;

  function pauseAllMedia() {
    // Pause HTML5 video elements on inactive slides
    document.querySelectorAll('.slide:not(.active) video').forEach(v => v.pause());
    // Pause YouTube/Vimeo iframes on inactive slides
    document.querySelectorAll('.slide:not(.active) iframe').forEach(f => {
      f.contentWindow.postMessage('{"event":"command","func":"pauseVideo","args":""}', '*');
      f.contentWindow.postMessage('{"method":"pause"}', '*');
    });
  }

  function playActiveMedia() {
    // Autoplay HTML5 video on the active slide
    document.querySelectorAll('.slide.active video').forEach(v => v.play());
    // Autoplay YouTube/Vimeo iframes on the active slide
    document.querySelectorAll('.slide.active iframe').forEach(f => {
      f.contentWindow.postMessage('{"event":"command","func":"playVideo","args":""}', '*');
      f.contentWindow.postMessage('{"method":"play"}', '*');
    });
  }

  function show(i) {
    slides.forEach((s, j) => {
      s.classList.toggle('active', j === i);
      s.style.display = j === i ? 'flex' : 'none';
    });
    currentEl.textContent = i + 1;
    pauseAllMedia();
    playActiveMedia();
    // Update contextual notes if visible
    if (notesVisible && notesPanel) {
      const note = slides[i].dataset.notes || '';
      notesPanel.innerHTML = note;
    }
  }

  function next() { if (idx < slides.length - 1) { idx++; show(idx); } }
  function prev() { if (idx > 0) { idx--; show(idx); } }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); next(); }
    if (e.key === 'ArrowLeft') { prev(); }
    if (e.key === 'n' || e.key === 'N') {
      notesVisible = !notesVisible;
      if (notesPanel) notesPanel.classList.toggle('visible', notesVisible);
      show(idx);
    }
  });

  document.addEventListener('click', (e) => {
    if (e.target.closest('.controls') || e.target.closest('.notes-panel') || e.target.closest('.video-container') || e.target.closest('.media-container')) return;
    const x = e.clientX / window.innerWidth;
    x > 0.5 ? next() : prev();
  });

  // Touch support
  let touchStartX = 0;
  document.addEventListener('touchstart', (e) => { touchStartX = e.touches[0].clientX; });
  document.addEventListener('touchend', (e) => {
    const diff = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(diff) > 50) { diff < 0 ? next() : prev(); }
  });

  show(0);
})();
```

## Animations

Use subtle entrance animations for slide content. Stagger child elements for a cinematic reveal:

```css
.slide.active .animate-in {
  animation: fadeSlideUp 0.6s ease-out forwards;
}
.slide.active .animate-in:nth-child(2) { animation-delay: 0.1s; }
.slide.active .animate-in:nth-child(3) { animation-delay: 0.2s; }
.slide.active .animate-in:nth-child(4) { animation-delay: 0.3s; }

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

## Quality Checklist

Before delivering the HTML file, verify:

- [ ] **User was asked** about dark or light mode preference before generation
- [ ] All text uses Red Hat font family (Display, Text, or Mono)
- [ ] Red-50 (#ee0000) appears on every slide (even if just in the nav or a small accent)
- [ ] **Red Hat logo** appears on the title slide (breadcrumb area, small) and closing slide (larger)
- [ ] Logo uses the correct variant: reverse (white wordmark) for dark, standard (black wordmark) for light
- [ ] Logo is inline SVG (no external image dependencies)
- [ ] Color palette matches the chosen mode (Core Dark or Core Light or Expressive Dark)
- [ ] Color contrast meets WCAG AA (4.5:1 for body text, 3:1 for large headlines)
- [ ] Headlines tell a complete story when read in sequence
- [ ] Keyboard navigation works (← → Space N)
- [ ] Click/tap navigation works
- [ ] Contextual notes are present with references, links, and additional context for deeper exploration
- [ ] Sources are attributed on data slides
- [ ] At least one AI image opportunity is noted in contextual notes
- [ ] Icons (if used) load from jsDelivr CDN and display correctly in chosen mode
- [ ] Icons are used sparingly (2-3 per slide max) and enhance rather than clutter
- [ ] Red Hat Design Tokens CSS is loaded via jsDelivr CDN (`@rhds/tokens@3.0.2/css/global.min.css`)
- [ ] `color-scheme` is set correctly on `:root` (`dark` for Core Dark / Expressive Dark, `light` for Core Light)
- [ ] Spacing uses `--rh-space-*` tokens with px fallbacks (e.g., `var(--rh-space-lg, 24px)`)
- [ ] Typography sizing uses `--rh-font-size-*` tokens with fallbacks where appropriate
- [ ] Tags use `--rh-border-radius-pill` and `--rh-space-*` for padding
- [ ] Video slides (if any) use the thumbnail + click-to-embed pattern with `data-video-id` attributes
- [ ] Video slides (if any) include the protocol-aware JS handler (inline iframe on HTTP, new tab on file://)
- [ ] **User was informed** that inline video requires serving via HTTP/HTTPS (mandatory notification)
- [ ] Media slides (if any) have descriptive alt text on ` ` tags
- [ ] Media/video containers are excluded from click-to-navigate (click guard in JS)
- [ ] File is self-contained (no external dependencies besides Google Fonts, jsDelivr icons, jsDelivr design tokens, and user-provided video/image URLs)
- [ ] Progress indicator shows current/total slides
- [ ] The narrative follows a clear story arc with emotional rhythm
- [ ] **Thank You slide** is present as the final slide with author name, role, and Red Hat logo
- [ ] The accent word(s) in the title slide headline are colored red-50 for emphasis
- [ ] Video/media opportunities are noted in contextual notes (not inserted during initial generation)
- [ ] **Post-generation prompt** was shown to the user after delivering the deck, offering to add videos or memes

## Example: Mapping the OpenCode Screenshot to This System

The reference screenshot ("Your AI Assistant Should Live Where You Work") demonstrates:

```
Breadcrumb:    [RH Logo SVG] › NAPS STP               [logo small + font-mono, small, muted]
Label:         —— NAPS STP WORKING GROUP · FEB 27, 2026   [font-mono, red-50, small, tracking-wide]
Headline:      Your AI Assistant                       [Red Hat Display, Black, white, ~64px]
               Should Live Where You Work              ["Live Where You Work" in red-50, italic]
Subtitle:      A fully local, air-gap-ready AI...      [font-body, gray-40, ~18px]
Tags:          [Local-First] [Air-Gap Ready] ...       [pill style, monospace, outlined]
Attribution:   Todd Wardzinski · Architect · Red Hat    [font-body, gray-40, small]
Background:    Black with subtle red radial glow       [upper-right corner, very low opacity]
```

This is the target aesthetic. Every title slide should feel this cinematic and intentional.

## File Delivery

Save the generated HTML to `/mnt/user-data/outputs/[deck-name].html` and present it to the user.
The filename should be kebab-case derived from the deck title.

## Post-Generation: Video & Media Placement

Video and media slides are **not** part of the initial deck generation. They are added in a second
pass after the user has reviewed the generated deck structure. This keeps the initial creation
focused on narrative flow, and lets the user make informed decisions about where media fits.

### Workflow

After delivering the initial deck, **always prompt the user** with:

> "Would you like to add any **videos** or **memes / images** to the deck? If so, tell me:
> 1. The **URL** of the video or image — or a **local file path** / `@file` reference for images on your machine
> 2. **Where** it should go — **in** an existing slide, **before/after** a specific slide, or **replacing** a slide
>
> You can add as many as you'd like, one at a time or all at once."

### Placement Rules

When the user provides a URL and placement:

1. **Identify the media type** from the source:
 - YouTube / Vimeo links → Video embed (thumbnail-first pattern)
 - Direct `.mp4` / `.webm` / `.ogg` → Video embed
 - Giphy links (`giphy.com`, `gph.is`, `media.giphy.com`) → Media embed (convert to direct GIF URL)
 - Image URLs (`.jpg`, `.png`, `.gif`, `.webp`, `.svg`) or meme links → Media embed
 - Imgflip links → Media embed (convert to full-size template URL)
 - **Local file path or `@file` reference** → Media embed (base64-encode and inline as data URI)
 - If ambiguous, ask the user

2. **Placement modes** (default to "in" for content-rich slides, "after" for standalone media):

 - **"In slide 3"** → embed the video/media directly into the existing slide, below the headline
 and body text. Keep the slide's existing content and add a `.video-container` or
 `.media-container` after the body content. Reduce body text if needed to prevent overflow.
 Best for: adding a demo video to an architecture slide, a supporting image to a content slide,
 or a reaction meme alongside a quote.

 - **"After slide 3"** → insert a new dedicated Video/Media slide between current slides 3 and 4.
 Best for: standalone videos or memes that deserve their own moment in the narrative.

 - **"Before slide 5"** → insert a new dedicated slide before slide 5.

 - **"Replace slide 4"** → swap slide 4's content with a Video/Media slide, keeping the
 narrative position.

3. **For new standalone slides**, write a headline that fits the surrounding narrative context. Use
 the headlines of the adjacent slides to maintain story flow. Ask the user if you're unsure what
 headline to use.

4. **For in-slide embeds**, keep the existing headline and body content. Add the media below the
 body text. If the slide becomes too crowded, offer to move some body text into contextual notes
 or split into two slides.

5. **Preserve the navigation JS** — no changes needed; the `show()` function already handles
 autoplay/pause for any Video or Media slides in the deck.

6. **Update the slide count** in the progress indicator if slides were added (the JS handles this
 automatically via `slides.length`).

7. **Re-deliver the updated file** and ask if the user wants to add more or adjust placement.

### Iterative Refinement

The user may want to:
- Add multiple videos/memes in one pass — process all of them
- Move a video/meme to a different position — remove from old spot, insert at new spot
- Remove a video/meme they added — delete that slide
- Change the caption or headline on a media slide

Support all of these as natural follow-up edits after the initial placement.

## Tips for Viewers

Include these tips in the first contextual note:
- Arrow keys or click to navigate
- Press 'N' to toggle contextual notes — references, links, and additional context for each slide
- Works in any modern browser — share the HTML file directly
- For best results, use fullscreen (F11) or present in a browser tab

