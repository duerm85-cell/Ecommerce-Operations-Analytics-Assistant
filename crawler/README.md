# Public collector boundary

V1.0 does **not** claim live Shopee collection. `public_product_collector.py` is a deliberately conservative framework for a documented public JSON endpoint after manual terms review. It checks `robots.txt`, identifies itself, sleeps between requests, retries at most twice, logs failures, and stops on access restrictions. It does not implement login, CAPTCHA solving, browser fingerprinting, proxy rotation, cookies, or anti-bot bypasses.

The repository's product rows are synthetic compliant samples and use `example.com` placeholder URLs. This choice keeps the portfolio reproducible and avoids misrepresenting generated data as observed market facts.

