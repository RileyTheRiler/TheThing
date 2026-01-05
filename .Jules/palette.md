## 2024-05-23 - Accessibility of Icon-only Buttons
**Learning:** This application heavily uses icon-only buttons (navigation arrows, close 'X', etc.) without `aria-label` attributes. While some use `title` for mouse users, screen readers are left with unhelpful announcements like "multiplication sign" for '✕' or generic button announcements.
**Action:** Always couple visual icons with `aria-label` for action descriptions. For purely decorative elements (like the center nav dot), use `aria-hidden="true"` to remove noise.
