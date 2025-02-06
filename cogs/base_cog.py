# base_cog.py
from discord.ext import commands
from playwright.async_api import async_playwright
import requests
from bs4 import BeautifulSoup
import re

class BaseCog(commands.Cog):
    def __init__(self):
        super().__init__()
        # Shared methods here

    async def capture_screenshot(self, char_id: str, name_slug: str) -> str:
        """
        Capture a screenshot from the URL:
        https://jp.tomestone.gg/character/{char_id}/{name_slug}
        """
        pathname = "screenshot.png"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1280, "height": 1800})
            url = f"https://jp.tomestone.gg/character/{char_id}/{name_slug}"
            await page.goto(url)

            # Selector for the <div> you want to keep
            keep_selector = ".flex.flex-row.flex-1.justify-center"  # The <div> you want to keep

            await page.evaluate(f'''
                        (selector) => {{
                            const keep = document.querySelector(selector);
                            if (!keep) return;

                            // 1) Move up the DOM from the 'keep' element to <body>.
                            //    At each level, remove siblings of the current node.
                            let current = keep;
                            while (current && current !== document.body) {{
                                const parent = current.parentElement;
                                if (!parent) break;

                                // 2) Remove all siblings at this level that aren't 'current'
                                //    This effectively removes "brother" tags like nav or script if they share the same parent
                                for (const sibling of parent.children) {{
                                    if (sibling !== current) {{
                                        sibling.remove();
                                    }}
                                }}
                                current = parent;
                            }}

                            // 3) (Optional) Remove all global <nav> or <script> elements anywhere on the page.
                            //    If you only want to remove them outside your keep chain, do it here.
                            document.querySelectorAll('nav, script').forEach(el => el.remove());
                        }}
                    ''', keep_selector)

            # Finally, take the screenshot
            await page.screenshot(path=pathname, clip={"x": 0, "y": 0, "width": 1280, "height": 1585})
            await browser.close()
        return pathname

    def lodestone_search(self, query: str, worldname: str):
        """
        Searches the Lodestone for the given query and worldname.
        Only elements with an exact class of ["entry"] are considered.
        Returns a list of character IDs.
        """
        url = "https://jp.finalfantasyxiv.com/lodestone/character/"
        params = {"q": query, "worldname": worldname}
        response = requests.get(url, params=params)
        soup = BeautifulSoup(response.text, "html.parser")
        # Find all entries with class="entry"
        entries = soup.find_all(lambda tag: tag.has_attr("class") and tag["class"] == ["entry"])
        if not entries:
            return None

        # Take only the first entry
        first_entry = entries[0]

        # Find the element containing the character's displayed name
        name_el = first_entry.find("p", class_="entry__name")
        if not name_el:
            return None

        # Compare the extracted name to our query
        found_name = name_el.get_text(strip=True)
        if found_name != query:
            return None

        # Only select elements whose class attribute is exactly ["entry"]
        entries = soup.find_all(lambda tag: tag.has_attr("class") and tag["class"] == ["entry"])

        character_ids = []
        for entry in entries:
            link = entry.find("a", href=re.compile(r"/lodestone/character/\d+/"))
            if link:
                match = re.search(r"/lodestone/character/(\d+)/", link["href"])
                if match:
                    character_ids.append(match.group(1))
        return character_ids
