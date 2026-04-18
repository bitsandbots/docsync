# Accessibility Developer Guide

**For:** DocSync contributors and developers  
**Purpose:** Maintain WCAG 2.2 AA compliance in all code changes  
**Brand:** CoreConduit Brand v2.1

---

## Quick Start: 5 Rules for Accessible Code

1. **Always use `:focus-visible`** — Never set `outline: none` without replacement
2. **Semantic HTML first** — Use `<button>`, `<a>`, `<nav>`, `<header>`, `<main>`, `<footer>`
3. **Color + symbol** — Don't communicate state with color alone
4. **Test with keyboard** — Tab through every page you change
5. **Ask "Can a screen reader announce this?"** — If unsure, add `aria-label`

---

## Checklist for Every Change

### Before Committing

- [ ] **Keyboard navigation** — Tab through all new interactive elements
- [ ] **Focus visible** — Is focus indicator visible on every element?
- [ ] **Semantic HTML** — Did I use `<button>` instead of `<div onclick>`?
- [ ] **Color contrast** — Is text ≥4.5:1 on all backgrounds?
- [ ] **Touch targets** — Are buttons/links ≥44×44px?
- [ ] **ARIA labels** — Do icon-only buttons have `aria-label`?
- [ ] **Tests passing** — `pytest` and `npm test` (if applicable)

### For HTML Templates

```html
<!-- ✅ GOOD: Semantic, labeled, focusable -->
<nav aria-label="Documentation">
  <a href="#main" class="skip-link">Skip to main content</a>
  <ul>
    <li><a href="/docs">Documentation</a></li>
    <li><a href="/api">API Reference</a></li>
  </ul>
</nav>

<main id="main">
  <h1>Page Title</h1>
  <section aria-labelledby="search-heading">
    <h2 id="search-heading">Search</h2>
    <input type="search" placeholder="Search docs..." aria-label="Search documentation">
    <button>Search</button>
  </section>
</main>

<!-- ❌ BAD: Not semantic, no labels, hard to focus -->
<div>
  <div onclick="search()">🔍</div>
  <div class="result">Page</div>
</div>
```

### For CSS / Styling

```css
/* ✅ GOOD: Always define focus indicator */
button:focus-visible {
  outline: 3px solid var(--cc-focus-ring);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px var(--cc-focus-ring-halo);
}

/* ✅ GOOD: Respect prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}

/* ✅ GOOD: Ensure text contrast */
.card { background: var(--cc-bg-card); color: var(--cc-text-primary); }
/* var(--cc-text-primary) #1e232b is 4.5:1 on #c5c9d0 */

/* ❌ BAD: No focus indicator */
button:focus { border: 1px solid blue; }
/* Not visible on all backgrounds; too thin */

/* ❌ BAD: Color only */
.error { color: red; }
/* Color-blind users won't see it */

/* ❌ BAD: No motion preference */
.slide-in { animation: slideIn 0.3s ease; }
/* Motion-sensitive users affected */
```

### For JavaScript

```javascript
// ✅ GOOD: Update ARIA state when toggle changes
function toggleMode(dark) {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  const btn = document.getElementById('theme-toggle');
  btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
  localStorage.setItem('docsync-theme', dark ? 'dark' : 'light');
}

// ✅ GOOD: Announce status changes to screen readers
function showMessage(text) {
  const alert = document.createElement('div');
  alert.setAttribute('role', 'alert');
  alert.setAttribute('aria-live', 'polite');
  alert.textContent = text;
  document.body.appendChild(alert);
}

// ❌ BAD: No ARIA feedback
function toggleMode(dark) {
  document.documentElement.style.background = dark ? '#000' : '#fff';
  // Screen reader user has no idea what changed
}

// ❌ BAD: Event handler on non-interactive element
document.getElementById('title').onclick = () => { openMenu(); };
/* Keyboard users can't activate this; not in tab order */
```

---

## Color Tokens & Contrast

### Approved Text Colors

| Token | Value | On bg-base | Use |
|-------|-------|-----------|-----|
| `--cc-text-primary` | #1e232b | 4.5:1 ✅ | Body text, headings |
| `--cc-text-secondary` | #3a404a | 6.1:1 ✅ | UI text, labels |
| `--cc-text-muted` | #636a76 | 3.1:1 ❌ | **Don't use for info** |
| `--cc-link-color` | #164a94 | 4.7:1 ✅ | Links (always underlined) |
| `--cc-blue-600` | #1b6ad4 | 3.5:1 ⚠️ | Large text only |

### Avoid These

```css
/* ❌ FAIL — insufficient contrast on light backgrounds */
color: var(--cc-blue-500);     /* 2.5:1 on bg-base */
color: var(--cc-orange-500);   /* 2.2:1 on bg-base */
color: var(--cc-text-faint);   /* 2.2:1 on bg-base */

/* ✅ PASS — good contrast, brand-compliant */
color: var(--cc-text-primary); /* 4.5:1 */
color: var(--cc-link-color);   /* 4.7:1 */
color: var(--cc-blue-600);     /* 3.5:1 (large text only) */
```

---

## Focus Indicator Guidelines

Every interactive element **must** have a visible focus indicator.

### Default (use this everywhere):

```css
:focus-visible {
  outline: 3px solid var(--cc-focus-ring);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px var(--cc-focus-ring-halo);
}
```

### Custom (if needed for specific element):

```css
.my-button:focus-visible {
  outline: 3px solid var(--cc-focus-ring);
  outline-offset: 2px;
  border-radius: 4px;
  box-shadow: 0 0 0 5px var(--cc-focus-ring-halo);
}
```

### ❌ Never do this:

```css
button:focus { outline: none; }  /* Removes focus indicator */
button:focus { border: 1px solid blue; }  /* Too subtle */
```

---

## Keyboard Navigation Rules

### Tab Order

Ensure tab order follows visual order (top-to-bottom, left-to-right):

```html
<!-- ✅ GOOD: Natural reading order -->
<header>...</header>
<nav>...</nav>
<main>...</main>
<footer>...</footer>

<!-- ❌ BAD: Footer in tab order before main content -->
<footer tabindex="0">...</footer>
<main>...</main>
```

### When to use `tabindex`

- `tabindex="0"` — Make element keyboard-focusable (use sparingly)
- `tabindex="-1"` — Remove from tab order but allow focus via script
- ❌ **Avoid:** `tabindex="1"` or `tabindex="2"` (breaks natural order)

---

## Mobile & Touch Accessibility

### Minimum Touch Target Sizes

```css
/* All interactive elements */
button, a, input, select, textarea {
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem;  /* Add padding for visual breathing room */
}

/* Mobile optimization */
@media (max-width: 768px) {
  button, a { min-height: 48px; min-width: 48px; }
}
```

### Testing on Mobile

```bash
# DevTools device emulation
Chrome DevTools → Device Emulation → Pixel 4a / iPhone SE

# Real devices
1. Use real iPhone or Android device
2. Test touch accuracy (can you tap without hitting adjacent elements?)
3. Test orientation (portrait & landscape)
4. Test zoom to 200% (text should reflow)
```

---

## Testing Workflow

### Daily Development

```bash
# Before pushing code
1. Tab through your changes (no mouse)
2. Open DevTools → Accessibility panel
3. Check color contrast on new text
4. Verify focus visible on all buttons/links
```

### Before Pull Request

```bash
# Run automated checks
pytest              # Backend tests
npm run lint        # Linting
axe-core (browser)  # Automated a11y scan

# Manual screen reader test
# If you have NVDA/JAWS on Windows:
nvda --start
# Navigate page with arrow keys, H for headings, B for buttons
```

### Example: Adding a Search Feature

```html
<!-- 1. Use semantic HTML -->
<form role="search" aria-label="Documentation search">
  <!-- 2. Associate label with input -->
  <label for="search-input">Search:</label>
  <input
    id="search-input"
    type="search"
    placeholder="Type to search..."
    aria-describedby="search-help"
  >
  <button type="submit">Search</button>
  <!-- 3. Help text for context -->
  <small id="search-help">Use quotes for exact match: "api reference"</small>
</form>

<style>
  /* 4. Ensure contrast */
  #search-input {
    background: var(--cc-bg-card);
    color: var(--cc-text-primary);
    border: 1px solid var(--cc-border);
  }

  /* 5. Define focus indicator */
  #search-input:focus-visible {
    outline: 3px solid var(--cc-focus-ring);
    outline-offset: 2px;
    box-shadow: 0 0 0 5px var(--cc-focus-ring-halo);
  }

  /* 6. Support high-contrast mode */
  :root[data-contrast="high"] #search-input {
    border: 2px solid var(--cc-border-strong);
    background: white;
  }

  /* 7. Respect motion preferences */
  @media (prefers-reduced-motion: reduce) {
    #search-input { transition: none; }
  }
}
</style>

<script>
// 8. Announce search results to screen readers
function displayResults(items) {
  const resultsDiv = document.getElementById('results');
  resultsDiv.setAttribute('role', 'status');
  resultsDiv.setAttribute('aria-live', 'polite');
  resultsDiv.textContent = `Found ${items.length} results`;
  // Show results...
}
</script>
```

---

## Common Patterns

### Icon Button

```html
<!-- ✅ GOOD -->
<button aria-label="Open menu">
  <svg aria-hidden="true" viewBox="0 0 24 24">...</svg>
</button>

<!-- ❌ BAD — no accessible name -->
<button><svg viewBox="0 0 24 24">...</svg></button>
```

### Link vs Button

```html
<!-- Use <a> for navigation -->
<a href="/docs">Documentation</a>

<!-- Use <button> for actions -->
<button onclick="save()">Save</button>

<!-- ❌ DON'T use <div> for either -->
<div onclick="navigate('/docs')">Documentation</div>
```

### Toggle Button

```html
<button
  id="dark-mode"
  aria-pressed="false"
  aria-label="Toggle dark mode"
>
  🌙 Dark
</button>

<script>
  button.addEventListener('click', () => {
    const isDark = button.getAttribute('aria-pressed') === 'true';
    button.setAttribute('aria-pressed', !isDark);
  });
</script>
```

### Form with Errors

```html
<form>
  <div class="form-group">
    <label for="email">Email:</label>
    <input id="email" type="email" aria-describedby="email-error">
    <!-- Error visible to all users + announced to screen readers -->
    <span id="email-error" role="alert">
      ❌ Please enter a valid email
    </span>
  </div>
</form>

<style>
  #email-error {
    color: var(--cc-error);       /* Red, but see below */
    font-size: 0.875rem;
  }

  /* ✅ Color + symbol, not color alone */
  #email-error::before {
    content: "✕ ";
  }
}
</style>
```

---

## Merging Accessibility Into Design Reviews

When reviewing designs:

- [ ] **Contrast:** Can text be read on all backgrounds? (test with WebAIM checker)
- [ ] **Focus:** Is there a visible focus indicator on interactive elements?
- [ ] **Spacing:** Are buttons/links at least 44×44px?
- [ ] **Typography:** Readable font size (16px+ for body text)?
- [ ] **Layout:** Logical reading order? Sidebar before main content?
- [ ] **Icons:** Do icon-only buttons have labels?
- [ ] **Color:** Is information conveyed without color alone?
- [ ] **Motion:** Are animations essential, or should they be optional?

---

## Resources

- **WCAG 2.2 Quick Reference:** https://www.w3.org/WAI/WCAG22/quickref/
- **ARIA Practices Guide:** https://www.w3.org/WAI/ARIA/apg/
- **WebAIM Contrast Checker:** https://webaim.org/resources/contrastchecker/
- **HTML Spec (Semantic):** https://html.spec.whatwg.org/
- **MDN Web Docs:** https://developer.mozilla.org/en-US/docs/Web/Accessibility

---

## Questions?

Refer to [ACCESSIBILITY.md](../ACCESSIBILITY.md) for user-facing documentation and comprehensive compliance details.

For issues: File a GitHub issue with the `a11y` label.
