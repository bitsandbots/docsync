# Accessibility Testing Checklist

**Use this before every release to maintain WCAG 2.2 AA compliance.**

---

## 🔍 Pre-Release Verification (15 minutes)

### Visual Check

- [ ] **Contrast verified** — Body text ≥4.5:1 on all backgrounds
  - Use: WebAIM Color Contrast Checker or DevTools
- [ ] **No text in color alone** — Symbols, icons, or patterns accompany color states
- [ ] **Touch targets** — All buttons/links are ≥44×44px (DevTools Layout panel)
- [ ] **Focus indicator visible** — 3px dark outline + yellow halo on all interactive elements
- [ ] **Zoom to 200%** — Text reflows, no horizontal scroll, all elements still usable

### Keyboard Navigation

- [ ] **Tab navigation works** — Tab through entire page (no mouse)
- [ ] **Focus order logical** — Top-to-bottom, left-to-right
- [ ] **Skip link visible** — Press Tab immediately after page load
- [ ] **Skip link functional** — Jumps to `#main` element
- [ ] **All buttons activatable** — Enter/Space works on buttons
- [ ] **Form inputs usable** — Can select options with arrow keys
- [ ] **No keyboard traps** — Can always Tab out of any element

### Screen Reader Spot Check

**NVDA (Windows - Free)**
```bash
# Download: https://www.nvaccess.org/download/
# Start: Ctrl+Alt+N
# Navigate: Arrow keys, H=heading, B=button, L=list, etc.
```

- [ ] **Page has `<html lang="en">`**
- [ ] **Headings announced** with level (h1, h2, h3, etc.)
- [ ] **Links have accessible names** (not "click here")
- [ ] **Buttons have accessible names** (`aria-label` if needed)
- [ ] **Form labels associated** with `<label for="id">` or `aria-labelledby`
- [ ] **Decorative elements hidden** (`aria-hidden="true"`)
- [ ] **Reading order sensible** (test with SR roving focus)

### Automated Scanning

- [ ] **Axe DevTools** run without critical/serious issues
  - Install: Chrome extension
  - Scan: Right-click → Inspect → Axe DevTools
  - Review: Any red/orange items must be addressed
- [ ] **Lighthouse accessibility** score ≥90
  - Chrome DevTools → Lighthouse → Accessibility
  - Scan and review any issues

---

## 📋 Component Testing (5 minutes per page)

Test these elements on **every page you change:**

### Navigation

- [ ] **Header links** — All keyboard accessible, focus visible
- [ ] **Sidebar** — Keyboard navigation, focus trap closed on mobile
- [ ] **Breadcrumbs** — Each link focusable, current page announced
- [ ] **Pagination** — Links have accessible names (e.g., "Next page")

### Search

- [ ] **Search input** — Has associated label or `aria-label`
- [ ] **Search button** — Has accessible name
- [ ] **Results** — Announced with `role="region" aria-live="polite"`
- [ ] **No results** — User informed (not just empty list)

### Forms

- [ ] **All inputs have labels** — Associated with `<label for>` or `aria-labelledby`
- [ ] **Required fields marked** — `required` attribute or `aria-required="true"`
- [ ] **Error messages** — Visible, associated with input via `aria-describedby`
- [ ] **Error text color + symbol** — Not color alone
- [ ] **Focus moves to error** — After form submission

### Cards & Content

- [ ] **Headings hierarchy correct** — No skipped levels (h1→h3 bad)
- [ ] **Card interactive areas** — Entire card clickable or just one link?
- [ ] **Image alt text** — All images have meaningful alt text (or decorative)
- [ ] **Code blocks** — Wrapped in `<pre><code>` with proper syntax highlighting

### Modals & Popups

- [ ] **Focus trap** — Focus stays inside modal until closed
- [ ] **Esc closes modal** — Users can escape with keyboard
- [ ] **Focus returns** — After close, focus returns to trigger button
- [ ] **Modal title** — Announced with `role="dialog" aria-labelledby="title"`

---

## 🎨 Accessibility Features Test (5 minutes)

### High-Contrast Mode

1. Click **contrast button** (circle icon) in header
2. [ ] Page becomes white/black
3. [ ] All text readable (≥7:1 contrast)
4. [ ] Navigation and layout intact
5. [ ] Brand structure visible (card gradients, navy elements adjusted)
6. Reload page → [ ] Setting persists

### Dyslexia-Friendly Font

1. Click **font button** (large "A") in header
2. [ ] Body text changes to Atkinson Hyperlegible
3. [ ] Headings remain Exo 2 (brand authority)
4. [ ] All text readable
5. Reload page → [ ] Setting persists

### Reduced Motion

**Windows:** Settings → Ease of Access → Display → Animations OFF  
**Mac:** System Preferences → Accessibility → Display → Reduce motion ON

1. [ ] Animations disabled or instant
2. [ ] Transitions use 0.01ms (effectively instant)
3. [ ] Scroll is not smooth (`scroll-behavior: auto`)
4. [ ] No flashing or rapid blinking

---

## 📱 Mobile/Touch Testing (5 minutes)

### Device Emulation (Chrome DevTools)

1. DevTools → Device Emulation → Select device (Pixel 4a, iPhone SE, etc.)
2. [ ] Touch targets ≥44×44px
3. [ ] No horizontal scroll at 320px width
4. [ ] Zoom to 200% → text reflows, readable
5. [ ] Touch buttons without missing adjacent elements
6. [ ] Sidebar accessible (no overflow)

### Real Device (if possible)

1. [ ] Navigate with touch only (no mouse)
2. [ ] Use device zoom (pinch) — scales properly
3. [ ] Test with device screen reader (VoiceOver on iOS, TalkBack on Android)
4. [ ] Verify landscape & portrait orientations

---

## 🔧 Browser & OS Combinations

Test on at least **one from each group:**

### Windows
- [ ] Chrome + NVDA (free)
- [ ] Edge + Narrator (built-in)
- [ ] Firefox + NVDA

### Mac
- [ ] Safari + VoiceOver (built-in)
- [ ] Chrome + VoiceOver

### Mobile
- [ ] iOS Safari + VoiceOver
- [ ] Android Chrome + TalkBack

---

## 🚀 Pre-Commit Checklist

```bash
# Run before git push
pytest                          # All tests pass
npm run lint                    # No linting errors
python -m pytest tests/ -v      # Verbose output for review

# Manual verification (5 minutes)
1. Open site locally
2. Tab through new changes
3. Verify focus visible everywhere
4. Test high-contrast + font toggles
5. Check contrast on new text
```

---

## 📊 Automated Scanning Script

Create `scripts/a11y-check.sh`:

```bash
#!/bin/bash
# Quick accessibility check before commit

echo "🔍 Running accessibility checks..."
echo ""

# Check for common violations
echo "1. Checking for 'onclick' on non-buttons..."
grep -r 'onclick' docsync/templates/ | grep -v '<button' && echo "❌ FAIL" || echo "✅ PASS"

echo ""
echo "2. Checking for images without alt text..."
grep -r '<img' docsync/templates/ | grep -v 'alt=' && echo "⚠️  Review needed" || echo "✅ PASS"

echo ""
echo "3. Checking for unlabeled form inputs..."
grep -r '<input' docsync/templates/ | grep -v 'aria-label' | grep -v 'id=' && echo "⚠️  Review needed" || echo "✅ PASS"

echo ""
echo "4. Checking for outline: none without replacement..."
grep 'outline: none' docsync/static/style.css && echo "❌ FAIL: outline: none found" || echo "✅ PASS"

echo ""
echo "✅ Manual testing recommended before push"
```

Run with:
```bash
chmod +x scripts/a11y-check.sh
./scripts/a11y-check.sh
```

---

## 🐛 Accessibility Issues: Reporting & Fixing

### When Finding an Issue

**Report with:**
1. Component/page name
2. Browser & screen reader (if applicable)
3. Steps to reproduce
4. Expected behavior
5. Actual behavior
6. WCAG criterion violated (if known)

**Example:**
> **Title:** Search button not focusable  
> **Component:** Search (header)  
> **Steps:** 1. Load page 2. Press Tab multiple times 3. Search button never focused  
> **Expected:** Button should be in tab order  
> **Actual:** Tab order skips search button  
> **WCAG:** 2.1.1 Keyboard

### When Fixing an Issue

1. **Make minimal change** — Don't refactor surrounding code
2. **Test fix locally** — Verify keyboard, screen reader, contrast
3. **Run automated checks** — `axe` and `pytest`
4. **Document in commit** — Reference issue, WCAG criterion
5. **Add test case** (if applicable)

---

## 📚 Quick Reference

| WCAG Criterion | Test Method | Pass = |
|---|---|---|
| **1.4.3** Contrast | WebAIM checker or DevTools | ≥4.5:1 normal, ≥3:1 UI |
| **2.1.1** Keyboard | Tab through entire page | All functions reachable |
| **2.4.1** Skip link | Press Tab on page load | Skip link visible & works |
| **2.4.7** Focus visible | Tab to element | 3px outline visible |
| **2.5.5** Touch targets | DevTools Layout panel | ≥44×44px all buttons |
| **3.3.2** Form labels | Inspect input | `<label for>` associated |
| **4.1.2** ARIA | Inspect source | Roles, names, states correct |

---

## ✅ Sign-Off

**Completed by:** `______________________`  
**Date:** `______________________`  
**Notes:** `_____________________________________________________`

Before merging to main:
- [ ] All items above checked
- [ ] No WCAG AA violations found
- [ ] Automated tests pass
- [ ] Manual keyboard test passed
- [ ] Screen reader spot check passed (if changed interactive elements)

---

## Resources

- **WCAG 2.2 Quick Ref:** https://www.w3.org/WAI/WCAG22/quickref/
- **WebAIM Contrast:** https://webaim.org/resources/contrastchecker/
- **NVDA Download:** https://www.nvaccess.org/download/
- **Axe DevTools:** https://www.deque.com/axe/devtools/
- **DocSync ACCESSIBILITY.md:** See ../ACCESSIBILITY.md
