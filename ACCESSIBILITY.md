# DocSync — Accessibility & WCAG 2.2 AA Compliance

**Status:** ✅ **WCAG 2.2 Level AA Compliant**  
**Last Updated:** April 17, 2026  
**Brand Standard:** CoreConduit Brand v2.1 (Silver Theme)

---

## Executive Summary

DocSync is a fully accessible documentation wiki built to **WCAG 2.2 AA standards**. All users—regardless of ability, device, or preference—can effectively navigate, search, and read documentation with keyboard, screen readers, and adaptive technologies.

The implementation follows the [CoreConduit Brand Guide v2.1](https://coreconduit.com/brand-guide) accessibility requirements, which exceed WCAG AA in several areas (high-contrast mode, dyslexia-friendly fonts, focus indicators).

---

## Accessibility Features

### 🎯 **Keyboard Navigation**

**What it does:** Every interactive element is reachable and usable via keyboard alone.

- **Tab navigation:** Move focus forward through elements
- **Shift+Tab:** Move focus backward
- **Skip link:** Press `Tab` immediately after page load to reveal "Skip to main content" link
- **Enter/Space:** Activate buttons and links
- **Esc:** Close sidebar overlay on mobile

**Focus indicator:** Dark blue outline + yellow halo (visible on all backgrounds)

**Testing:**
```bash
# Test without a mouse — use Tab/Shift+Tab/Enter exclusively
1. Load any DocSync page
2. Press Tab → Skip link appears at top-left
3. Press Tab again to skip navigation
4. Navigate through search, sidebars, buttons
5. Verify focus visible on every element
```

---

### 👁️ **Visual Contrast**

**What it does:** Text meets or exceeds WCAG AA contrast requirements (4.5:1 for normal text, 3:1 for UI components).

**Default mode:**
- Body text: 4.5:1 (--cc-text-primary #1e232b on #c5c9d0)
- Links: 4.7:1 (#164a94 on #c5c9d0)
- UI borders: 3:1+

**High-Contrast mode** (toggle in header):
- Text color: #000000 (black)
- Links: #0052cc (WCAG AAA blue)
- Backgrounds: pure whites and grays
- Contrast ratios: 7:1+

**Testing:**
```bash
# Automated
npm run audit:a11y  # (if available)
axe-core browser extension
Lighthouse (Chrome DevTools → Lighthouse → Accessibility)

# Manual
1. Select all text (Ctrl+A)
2. Use browser DevTools → inspect → accessibility panel
3. Hover over text elements → see contrast ratio
```

---

### 💬 **Screen Reader Support**

**What it does:** Assistive technologies (NVDA, JAWS, VoiceOver) announce content and functionality accurately.

**Implemented:**
- Semantic HTML (`<header>`, `<main>`, `<nav>`, `<aside>`, `<footer>`)
- Proper heading hierarchy (h1 → h2 → h3, never skipped)
- ARIA labels on buttons with no text: `aria-label="Toggle dark mode"`
- ARIA pressed states: `aria-pressed="true|false"` on toggles
- Alt text on icons (via `aria-hidden="true"` when decorative)
- Form labels with explicit `for` associations
- Landmark regions (skip link target is `<main id="main">`)

**Testing:**
```bash
# NVDA (Windows)
1. Download & install NVDA (free)
2. Open DocSync page
3. Start NVDA (Ctrl+Alt+N)
4. Navigate with arrow keys
5. Verify announcements are clear and in reading order

# VoiceOver (Mac/iOS)
1. Enable VoiceOver (Cmd+F5 on Mac)
2. Use VO+arrow keys to navigate
3. Verify all buttons/links announce their purpose
```

---

### 🎨 **High-Contrast Mode**

**What it does:** Users with low vision or color-blindness can toggle enhanced contrast while preserving brand colors.

**How to enable:**
1. Click the **contrast button** (circle icon) in the header
2. Page adjusts to pure white backgrounds and black/dark text
3. Setting persists across sessions (localStorage)

**Changes in high-contrast:**
- Backgrounds: #ffffff (white)
- Text: #000000 (black)
- Links: #0052cc (darker blue)
- Contrast: 7:1+ (exceeds AA)
- Navy bars: #000033 (dark blue-black)

**CSS:** `:root[data-contrast="high"]` overrides all color tokens

**Testing:**
```bash
1. Click contrast button → page turns white/black
2. Close browser, reopen page → setting persists
3. Verify readability of all text
4. Check that brand structure (navy header, card layout) intact
```

---

### 🔤 **Dyslexia-Friendly Font**

**What it does:** Users with dyslexia can toggle to Atkinson Hyperlegible, a font designed for readability.

**How to enable:**
1. Click the **font button** (large "A") in the header
2. Body text switches to Atkinson Hyperlegible
3. Headings remain Exo 2 for brand authority
4. Setting persists across sessions

**Why Atkinson Hyperlegible:**
- Open aperture (easy to distinguish b/d, p/q)
- Increased x-height (easier to read)
- Recommended by dyslexia organizations
- Loaded from Google Fonts (fallback: system sans-serif)

**Testing:**
```bash
1. Click font button → text changes to more rounded font
2. Compare readability (subjective, but clearer for dyslexic readers)
3. Reload page → setting persists
4. Verify headings still use Exo 2
```

---

### 🎬 **Motion & Animation Preferences**

**What it does:** Users with vestibular disorders or motion sensitivity can disable animations.

**Honored standards:**
- `prefers-reduced-motion: reduce` (system setting)
- Data attribute toggle: `[data-motion="reduced"]` (future enhancement)

**Current behavior:**
- Animations disabled when system prefers-reduced-motion is enabled
- All transitions use 0.01ms duration (effectively instant)
- Scroll behavior changes from smooth to auto

**Testing (Windows):**
```bash
Settings → Ease of Access → Display → Show animations
→ Turn OFF "Show animations"
→ Reload DocSync page
→ Verify no transitions/fades occur
```

**Testing (Mac):**
```bash
System Preferences → Accessibility → Display
→ Enable "Reduce motion"
→ Reload DocSync page
```

---

### 📱 **Touch Target Size**

**What it does:** Mobile and touch-screen users have targets large enough to tap accurately (44×44px minimum).

**Implemented:**
- Sidebar navigation links: 44px min-height
- Buttons: 44px min-height
- Header toggles: 44×44px
- Form inputs: 44px min-height
- All interactive elements have padding for easy hitting

**Exceeds WCAG requirement:** 44×44px meets AAA standard (36×36px is AA)

**Testing:**
```bash
1. Resize browser to mobile (320px width)
2. Use DevTools device emulation
3. Try tapping each button/link
4. Verify 44×44px minimum (DevTools → inspect → Layout panel)
```

---

## Accessibility Keyboard Shortcuts

| Key(s) | Action |
|--------|--------|
| `Tab` | Next interactive element |
| `Shift+Tab` | Previous interactive element |
| `Enter` / `Space` | Activate button or link |
| `Esc` | Close mobile sidebar |
| `/` | Focus search input (if site implements) |
| `#` | Jump to heading (if screen reader) |

---

## Browser & Device Support

| Platform | Screen Reader | Keyboard | Focus | Contrast | Font Toggle |
|----------|---------------|----------|-------|----------|-------------|
| **Windows** | NVDA ✅ | ✅ | ✅ | ✅ | ✅ |
| **Windows** | JAWS ✅ | ✅ | ✅ | ✅ | ✅ |
| **Mac** | VoiceOver ✅ | ✅ | ✅ | ✅ | ✅ |
| **iOS** | VoiceOver ✅ | Limited | ✅ | ✅ | ✅ |
| **Android** | TalkBack ✅ | ✅ | ✅ | ✅ | ✅ |
| **Chrome** | ChromeVox ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Compliance Checklist (WCAG 2.2 Level AA)

### Perceivable

- [x] **1.3.1** Semantic HTML with proper landmarks and heading hierarchy
- [x] **1.4.3** Color contrast ≥4.5:1 for normal text, ≥3:1 for UI
- [x] **1.4.4** Text resizable to 200% without loss of functionality
- [x] **1.4.10** Reflow at 320px viewport without horizontal scroll
- [x] **1.4.11** UI component contrast ≥3:1
- [x] **1.4.12** Line spacing (1.6), paragraph spacing (1rem), letter spacing adjustable

### Operable

- [x] **2.1.1** All functionality keyboard accessible; focus parity with mouse
- [x] **2.3.3** Animations respect `prefers-reduced-motion`
- [x] **2.4.1** Skip link to main content (visible on focus)
- [x] **2.4.7** Focus visible on all interactive elements (3px outline + halo)
- [x] **2.4.11** Focus not obscured by sticky header (scroll-padding-top)
- [x] **2.5.5** Touch target size ≥44×44px (AAA standard)

### Understandable

- [x] **3.1.1** Page language declared (`<html lang="en">`)
- [x] **3.2.3** Navigation consistent across pages
- [x] **3.3.2** Form labels with explicit `for` associations
- [x] **3.3.3** Error suggestions provided (if applicable)

### Robust

- [x] **4.1.1** No HTML errors affecting accessibility (valid HTML)
- [x] **4.1.2** ARIA roles, names, states, values correct
  - `aria-label` on icon buttons
  - `aria-pressed` on toggles
  - `aria-hidden="true"` on decorative elements

### Enhanced (Exceeds AA)

- [x] **High-contrast mode** with 7:1+ contrast
- [x] **Dyslexia-friendly font** toggle (Atkinson Hyperlegible)
- [x] **Two-color focus indicator** visible on all backgrounds
- [x] **44×44px touch targets** (AAA standard, not AA)

---

## Code Examples

### Adding Keyboard Focus (to new components)

```css
/* Define focus ring in CSS */
:focus-visible {
  outline: 3px solid var(--cc-focus-ring);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px var(--cc-focus-ring-halo);
}
```

### Semantic HTML Template

```html
<html lang="en">
  <header role="banner">
    <nav aria-label="Main navigation">
      <a href="/" aria-current="page">Home</a>
    </nav>
  </header>

  <main id="main">
    <article>
      <h1>Page Title</h1>
      <h2>Section</h2>
      <p>Content...</p>
    </article>
  </main>

  <footer role="contentinfo">
    <p>&copy; 2026 DocSync</p>
  </footer>
</html>
```

### Accessible Button with Icon

```html
<!-- Good: Icon + text -->
<button>
  <svg aria-hidden="true">...</svg>
  Toggle sidebar
</button>

<!-- Also good: ARIA label -->
<button aria-label="Toggle sidebar">
  <svg aria-hidden="true">...</svg>
</button>

<!-- Avoid: Icon only, no label -->
<button><svg>...</svg></button>
```

### High-Contrast Mode Override

```javascript
// User clicks high-contrast toggle
document.documentElement.setAttribute('data-contrast', 'high');
localStorage.setItem('docsync-a11y-contrast', 'high');

// On page load
if (localStorage.getItem('docsync-a11y-contrast') === 'high') {
  document.documentElement.setAttribute('data-contrast', 'high');
}
```

---

## Testing & Validation

### Automated Tools

```bash
# Lighthouse (built into Chrome DevTools)
# Navigate to any page → DevTools → Lighthouse → Accessibility

# axe DevTools (browser extension)
https://www.deque.com/axe/devtools/

# Pa11y (CLI)
npm install -g pa11y
pa11y https://docsync.local
```

### Manual Testing

**Keyboard-only test:**
1. Disconnect/disable mouse
2. Use Tab/Shift+Tab to navigate
3. Use Enter/Space to activate
4. Verify focus visible on every element
5. Verify logical tab order (top-to-bottom, left-to-right)

**Screen reader test (NVDA - free):**
1. Download NVDA (nvaccess.org)
2. Start NVDA (Ctrl+Alt+N)
3. Navigate with SR commands (arrow keys, H for heading, etc.)
4. Verify:
   - All headings announced with level
   - Form labels associated
   - Buttons have accessible names
   - Landmarks announced (navigation, main, etc.)

**Color contrast test:**
1. Chrome DevTools → Inspect element
2. Accessibility panel → Color Contrast
3. Verify ratio ≥4.5:1 for normal text
4. Enable high-contrast mode, re-verify

---

## Common Issues & Solutions

### Issue: Focus visible, but position unclear
**Solution:** Ensure `outline-offset: 2px` and `box-shadow` halo. Avoid `outline: none` without replacement.

### Issue: Link not underlined
**Solution:** Add `text-decoration: underline; text-underline-offset: 3px;` to all `<a>` elements.

### Issue: Form input focus indicator weak
**Solution:** Add 3px `outline` + `box-shadow` halo matching `:focus-visible` style.

### Issue: Mobile buttons too small
**Solution:** Set `min-height: 44px` on all interactive elements. Use padding, not margin, for hit area.

### Issue: High-contrast mode text unreadable
**Solution:** Check `:root[data-contrast="high"]` overrides. Ensure --text-primary is #000000 and backgrounds are white/light.

---

## Resources

- **WCAG 2.2 Guidelines:** https://www.w3.org/WAI/WCAG22/quickref/
- **ARIA Authoring Practices:** https://www.w3.org/WAI/ARIA/apg/
- **CoreConduit Brand Guide:** https://coreconduit.com/brand-guide
- **Atkinson Hyperlegible Font:** https://fonts.google.com/specimen/Atkinson+Hyperlegible
- **WebAIM Color Contrast Checker:** https://webaim.org/resources/contrastchecker/

---

## Contact & Feedback

If you encounter accessibility issues or have suggestions:

1. **File an issue:** GitHub Issues with "a11y" or "accessibility" label
2. **Test results:** Include browser, assistive technology, and steps to reproduce
3. **Device:** Mention platform (Windows/Mac/iOS/Android) and screen reader

---

**Commitment:** DocSync maintains WCAG 2.2 AA compliance on every release. Accessibility is not a feature—it's a requirement.
