# Power BI star model

```text
products (1) ───────< orders >─────── (1) users
                         ^
                         |
calendar (1) ────────────+───────────< ads
```

`orders` and `ads` are facts at order-line-like and daily-campaign grains. `products`, `users`, and `calendar` are dimensions. The Power BI export enriches `users` with one-to-one RFM attributes calculated from completed 2025 orders; no extra relationship is required. Relationships are one-to-many, active and single-direction. Advertising is not joined to orders because campaign attribution is already represented at aggregate daily campaign grain; joining the two facts would multiply rows.
