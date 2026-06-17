# Odysseus-Inspired Design Proposal for Job Raider

## Design Analysis

Based on Pewdiepie's Odysseus project, here are the key design elements to implement:

### 1. Typography System
- **Primary font**: Fira Code (monospaced) for UI text
- **Font sizes**: px-based sizing (no type-scale variables)
- **Hierarchy**: Clear distinction between headings, body, and small text

### 2. Color Palette (Dual Theme Support)

#### Light Theme
```
--bg: #fafafa (near-white background)
--fg: #1a1a1a (near-black text)
--panel: #ffffff (pure white cards)
--border: #e0e0e0 (subtle borders)
--red: #e63946 (primary accent/CTA)
--border-subtle: #f0f0f0 (very subtle dividers)
```

#### Dark Theme
```
--bg: #0f0f0f (near-black background)
--fg: #f0f0f0 (near-white text)
--panel: #1a1a1a (dark cards)
--border: #333333 (visible borders)
--red: #ff6b6b (bright accent/CTA)
--border-subtle: #2a2a2a (subtle dividers)
```

### 3. Card Styling
- **Border**: 1px solid var(--border)
- **Shadow**: Subtle box-shadow for depth
- **Padding**: 16px standard spacing
- **Border-radius**: 4px (minimal rounding)
- **Background**: var(--panel)

### 4. Button Patterns
- **Primary CTA**: var(--red) background, white text
- **Borders**: 1px solid transparent normally, var(--border) for secondary
- **Hover**: Darken/lighten by 10%
- **Focus ring**: 2px solid var(--red) with offset

### 5. Layout Structure
- **Sidebar**: Left navigation with icons + labels
- **Main content**: Right panel with cards organized in grids
- **Responsive**: Collapsible sidebar on mobile
- **Grid patterns**: 2-column and 3-column layouts

### 6. Interactive Elements
- **Focus states**: Visible focus rings (accessibility)
- **Hover states**: Clear visual feedback
- **Active states**: Inverted colors for active items
- **Transitions**: 150ms ease-in-out

## Implementation Priority

1. **Typography** - Add Fira Code font, set up font sizes
2. **Color system** - Implement CSS variables for both themes
3. **Card redesign** - Update card borders, shadows, spacing
4. **Button styling** - Red CTA buttons, proper focus states
5. **Layout updates** - Sidebar navigation pattern, grid layouts
6. **Accessibility** - Focus rings, ARIA labels, keyboard nav

## Benefits

- **Professional appearance**: Monospaced font gives a technical, clean look
- **Strong accessibility**: Meets WCAG AA contrast ratios
- **Clear CTAs**: Red accent color draws attention to key actions
- **Responsive**: Works well on desktop and mobile
- **Maintainable**: CSS variables make theme switching easy
