# Pokecrack design system

## Direction

Pokecrack is a quiet research instrument: white and soft-grey surfaces, precise typography, restrained colour and data graphics that carry the visual interest. The regional map is the signature element. Interface chrome should support it rather than compete with it.

## Hierarchy

1. Scope and product promise.
2. Regional evidence map and metric control.
3. Snapshot provenance and aggregate totals.
4. Trend, ranked evidence and recent activity.
5. Methodology and disclaimers.

## Visual rules

- Prefer dividers, aligned rows and grouped surfaces over cards inside cards.
- Use one dominant surface per section; reserve tinted backgrounds for status or caution.
- Keep the type scale compact and consistent. Display text is sentence case; metadata may use uppercase mono labels.
- Use the blue–violet–pink scale only for data intensity. Neutral controls stay ink, white and grey.
- Outer radius should equal the inner radius plus the surrounding inset wherever shapes nest.
- Icons are Lucide outlines and should match the visual weight of adjacent labels.

## Motion rules

- Motion explains a state change or establishes the page hierarchy; it is never ambient decoration.
- Use `cubic-bezier(0.16, 1, 0.3, 1)` for entrances and `cubic-bezier(0.77, 0, 0.175, 1)` for shared-position changes.
- Micro-interactions run for 150–280 ms and animate only `transform` or `opacity` where possible.
- The map metric selector uses a shared sliding indicator adapted from the BeUI Tabs pattern.
- Pressed controls scale to 0.98; hover treatments run only on devices that actually support hover.
- `prefers-reduced-motion: reduce` removes non-essential movement and makes state changes immediate.

## Responsive rules

- Preserve a 44 px minimum target size.
- The map and regional list stack below 900 px.
- Summary metrics move from six columns to three and then two without horizontal overflow.
- Tables remain horizontally scrollable inside labelled, keyboard-focusable regions.
