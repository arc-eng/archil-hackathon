---
name: company-brand
description: The company's brand for every app page. Use it whenever you build or change an app's page (public/index.html and its styles).
---

# Company brand: Quillfeather Ventures

Every app the company's people build looks like it comes from the same company.

- **Header:** a top bar on every page with "Quillfeather Ventures" on the left in bold, and the app's name after a thin
  divider (`Quillfeather Ventures | Stock Tracker`). White background, a 1 px bottom border `#E3E5E8`.
- **Colour:** the brand green `#007A33` for primary buttons, links and positive values (gains, "done", "live").
  Red `#B42318` only for errors and negative values. Text `#15171A`, secondary text `#4B5057`, borders `#E3E5E8`,
  page background `#FFFFFF`. No other accent colours.
- **Font:** Inter for everything. Add
  `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">`
  and set `font-family: Inter, system-ui, sans-serif` on `body`.
- **Pico CSS stays, in brand green.** Pico sets its colours on `:root:not([data-theme=dark]), [data-theme=light]`,
  which beats a plain `:root`, and its buttons use the `-background` and `-border` variables. So copy this block
  exactly, after Pico's stylesheet:

  ```css
  :root:not([data-theme=dark]), [data-theme=light] {
    --pico-font-family: Inter, system-ui, sans-serif;
    --pico-primary: #007A33;
    --pico-primary-background: #007A33;
    --pico-primary-border: #007A33;
    --pico-primary-underline: rgba(0, 122, 51, 0.5);
    --pico-primary-hover: #00652a;
    --pico-primary-hover-background: #00652a;
    --pico-primary-hover-border: #00652a;
    --pico-primary-hover-underline: #00652a;
    --pico-primary-focus: rgba(0, 122, 51, 0.25);
    --pico-primary-inverse: #FFFFFF;
    --pico-border-radius: 8px;
  }
  ```

  Buttons must come out green: no Pico blue anywhere on the page.
- **Footer:** one small line, "Built with the Quillfeather Ventures golden sandbox", in secondary text.
- Light mode only. Rounded corners 8 px. No gradients, no emoji icons.

When you change an existing app, bring its page in line with this brand, and keep everything it does.
