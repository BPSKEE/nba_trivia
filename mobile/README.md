# NBA Trivia website

This is a standalone static website. It does not use ChatGPT hosting or services.

Edit the source files in `dist/`, then run `make website` from the parent project folder. This builds the deployable `docs/` folder with enriched roster and All-Star data, and creates `dist/NBA Trivia Website.zip` in the parent project.

Push the parent project’s `docs/` folder to GitHub. In repository **Settings → Pages**, choose **Deploy from a branch**, **main**, **/docs**, then **Save**. No build action or server is required. See the parent README for the clickable game link and complete instructions.

For a local preview, run `make website-serve` from the parent folder and open http://localhost:8080. Visitors use the GitHub Pages address instead. On iPhone, Safari’s Share menu can add the site to the Home Screen.

Run logic tests with `node --test mobile/tests/engine.test.mjs` from the parent folder. The four modes use the same eligibility rules as the desktop game. Physical iPhone testing remains necessary to confirm installation and offline behavior on that device.
