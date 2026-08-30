# Design System

## Design thesis
The product should feel like an engineering evidence tool, not an AI marketing site. Inspiration: scientific benchmark, consumer-comparison guide, and developer console.

## Palette
- Navy shell: `#07192D`
- Navy secondary: `#0A2039`
- Main ink: `#172033`
- Muted text: `#667085`
- Canvas: `#F7F8FB`
- Surface: `#FFFFFF`
- Border: `#E6E9EF`
- Product blue: `#2457F5`
- Rules green: `#15966B`
- Traditional ML blue: `#2457F5`
- Small model purple: `#7756D8`
- Frontier LLM red: `#E24A4A`
- Warning amber: `#B96A08`

## Typography
- UI/body: system sans stack; target Inter when available.
- Hero display: Georgia/serif to distinguish the thesis from the application chrome.
- Dense data: 10–12 px labels, 12–14 px table body.
- No body text below 10 px on desktop; mobile body 12 px minimum.

## Layout
- Fixed desktop sidebar, mobile drawer.
- Dominant evidence viewport, not equal KPI tiles.
- Maximum content width roughly 1,420 px.
- 16–22 px card/panel radius only where a framed analytical region helps.
- Open whitespace elsewhere.

## Interaction
- Requirement sliders update results instantly.
- Chart points can be hovered, focused, or clicked.
- Table always exposes the same data as the chart.
- Avoid hover-only information.

## Responsive standard
- Desktop: 1440 px reference.
- Tablet: 860–1180 px.
- Mobile: 390 px reference.
- On mobile, navigation becomes a drawer; comparison tables scroll horizontally; evidence remains before explanatory content.
