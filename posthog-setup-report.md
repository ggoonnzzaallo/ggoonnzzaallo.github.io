<wizard-report>
# PostHog post-wizard report

The wizard has completed a deep integration of PostHog analytics into this static HTML portfolio site. Because the site has no build step or package manager, PostHog is loaded via the official JavaScript snippet pattern. Two files are used: `posthog-config.js` (project key + host; **gitignored**, not committed) and `posthog-analytics.js` (reads `window.POSTHOG_KEY` / `window.POSTHOG_HOST`). Both script tags were added to `index.html` and every page under `pages/`. All event tracking is implemented via a single delegated click listener in `posthog-analytics.js`, keeping page files untouched beyond the two added `<script>` tags.

| Event | Description | File(s) |
|---|---|---|
| `project_card_clicked` | User clicks a project card on the home page | `index.html` |
| `social_link_clicked` | User clicks LinkedIn, X, or YouTube in the header or footer nav | All pages |
| `external_link_clicked` | User follows an external link (GitHub, press, company sites) from a project page | All `pages/*.html` |
| `back_link_clicked` | User clicks the ← back arrow to return to the home page | All `pages/*.html` |
| `image_lightbox_opened` | User clicks an image to open the full-screen lightbox viewer | 14 project pages with lightbox |

## Next steps

We've built some insights and a dashboard for you to keep an eye on user behavior, based on the events we just instrumented:

- **Dashboard — Analytics basics**: https://us.posthog.com/project/408524/dashboard/1540391
- **Most clicked projects**: https://us.posthog.com/project/408524/insights/jIvzhp9t
- **Social link clicks by platform**: https://us.posthog.com/project/408524/insights/HWLXPhiG
- **External link clicks over time**: https://us.posthog.com/project/408524/insights/v2OOWy1A
- **Top external links clicked**: https://us.posthog.com/project/408524/insights/eyAgyaeT
- **Image lightbox opens by page**: https://us.posthog.com/project/408524/insights/toSbcyFe

### Setup notes

- Keep `posthog-config.js` out of git; copy from `posthog-config.example.js` locally. For GitHub Pages, inject this file at deploy (e.g. Actions writing from secrets) or accept that analytics only run where the file exists.
- `posthog-config.example.js` is committed as a template showing the required format.

### Agent skill

We've left an agent skill folder in your project. You can use this context for further agent development when using Claude Code. This will help ensure the model provides the most up-to-date approaches for integrating PostHog.

</wizard-report>
