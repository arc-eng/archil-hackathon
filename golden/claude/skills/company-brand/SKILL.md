---
name: company-brand
description: The company's brand for every app page. Use it whenever you build or change an app's page (public/index.html and its styles).
---

# Company brand: Arcane Engineering

Every app the company's people build looks like it comes from the same company.

- **Header:** a top bar on every page with "Arcane Engineering" on the left in bold, and the app's name after a thin
  divider (`Arcane Engineering | Stock Tracker`). White background, a 1 px bottom border `#E3E5E8`.
- **Colour:** the brand green `#007A33` for primary buttons, links and positive values (gains, "done", "live").
  Red `#B42318` only for errors and negative values. Text `#15171A`, secondary text `#4B5057`, borders `#E3E5E8`,
  page background `#FFFFFF`. No other accent colours.
- **Font:** Inter for everything. Add
  `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">`
  and set `font-family: Inter, system-ui, sans-serif` on `body`. Keep Pico CSS, and override its primary colour:
  `:root { --pico-primary: #007A33; --pico-primary-hover: #00652a; --pico-font-family: Inter, system-ui, sans-serif; }`.
- **Footer:** one small line, "Built with the Arcane Engineering golden sandbox", in secondary text.
- Light mode only. Rounded corners 8 px. No gradients, no emoji icons.

When you change an existing app, bring its page in line with this brand, and keep everything it does.
