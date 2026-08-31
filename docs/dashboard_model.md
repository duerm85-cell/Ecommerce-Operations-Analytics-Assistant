# Power BI star model

```text
products (1) ───────< orders >─────── (1) users
                         ^
                         |
calendar (1) ────────────+───────────< ads
```

`orders` and `ads` are facts at order-line-like and daily-campaign grains. `products`, `users`, and `calendar` are dimensions. Relationships are one-to-many, active and single-direction. Advertising is not joined to orders because campaign attribution is already represented at aggregate daily campaign grain; joining the two facts would multiply rows.

