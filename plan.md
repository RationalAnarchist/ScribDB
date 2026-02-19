# Potential Sites for Scrollarr

This document lists potential websites that host stories similar to Archive of Our Own (AO3) or Royal Road. These sites are considered good contenders for future addition to the project due to their popularity and structural similarities.

## High Priority Contenders (Similar Technical Structure)

These sites share the XenForo platform with the existing `QuestionableQuesting` source, making integration potentially easier.

### ~~1. SpaceBattles (spacebattles.com)~~
*   ~~**Description:** A large forum community with a heavy focus on science fiction, fanfiction, and original fiction.~~
*   ~~**Why it's a good fit:** Very similar to Questionable Questing in structure (XenForo). Often cross-posts with Sufficient Velocity and AO3. Has a dedicated Creative Writing section.~~
*   ~~**Technical Feasibility:** High. Can leverage the existing `QuestionableQuestingSource` logic for threadmarks and post extraction.~~

### 2. Sufficient Velocity (sufficientvelocity.com)
*   **Description:** A forum that split from SpaceBattles, sharing a similar community and focus on sci-fi and fanfiction.
*   **Why it's a good fit:** Almost identical structure to SpaceBattles and Questionable Questing (XenForo). Many authors post on both SB and SV.
*   **Technical Feasibility:** High. Same codebase as SB/QQ.

## Strong Contenders (Similar Content/Audience)

These sites are popular among readers of Royal Road and AO3.

### 3. Scribble Hub (scribblehub.com)
*   **Description:** A platform for original web novels, often focusing on LitRPG, Isekai, and Progression Fantasy.
*   **Why it's a good fit:** Structurally and thematically very similar to Royal Road. It was created by the same developer as Royal Road (or is heavily inspired by it).
*   **Technical Feasibility:** High. Standard HTML structure, likely easy to scrape with `BeautifulSoup`.

### 4. Wattpad (wattpad.com)
*   **Description:** One of the largest platforms for original stories and fanfiction, covering a wide range of genres.
*   **Why it's a good fit:** Massive library and user base. Frequently requested.
*   **Technical Feasibility:** Medium/Hard. Uses heavy JavaScript and dynamic loading. May require `playwright` (already in project) or specialized API handling. Login often required for mature content.

### 5. FanFiction.net (fanfiction.net)
*   **Description:** The classic archive for fanfiction. Huge database of stories.
*   **Why it's a good fit:** A staple of the fanfiction community. Many older stories are exclusive here.
*   **Technical Feasibility:** Medium. Known for Cloudflare protection and anti-bot measures. Might require `cloudscraper` or careful `playwright` usage.

### 6. FictionPress (fictionpress.com)
*   **Description:** The original fiction sister site to FanFiction.net.
*   **Why it's a good fit:** Similar to Royal Road but for older original web fiction.
*   **Technical Feasibility:** Medium. Shares the same backend/protection as FanFiction.net.

## Other Potential Sites

### 7. WebNovel (webnovel.com)
*   **Description:** A large platform for translated Chinese/Korean novels and original English works.
*   **Why it's a good fit:** Popular for cultivation and system novels.
*   **Technical Feasibility:** Low/Medium. Heavily monetized with "spirit stones" or coins to unlock chapters. Free chapters might be scrapable, but paywalled content is inaccessible.

### 8. Tapas (tapas.io)
*   **Description:** Hosts both webcomics and novels.
*   **Why it's a good fit:** Growing popularity for original web fiction.
*   **Technical Feasibility:** Medium. Mobile-first design, often has "ink" or wait-to-unlock mechanics.

### 9. Inkitt (inkitt.com)
*   **Description:** A data-driven publisher and reader app.
*   **Why it's a good fit:** Another source of original fiction.
*   **Technical Feasibility:** Unknown. Likely standard web scraping.
