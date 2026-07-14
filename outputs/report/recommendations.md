# Facility Placement Recommendations

Greedy farthest-point placement of K = 3 new facilities per service. Each new site is the worst-served location at the time it is added; figures below quantify the before/after change in access.

## Metro station (`metro_station`)

- Underserved threshold: **2.0 km** nearest-facility distance.
- Max access distance: **10.16 km -> 7.00 km** (cut by 3.16 km).
- Mean access distance: 3.56 km -> 2.75 km.
- Underserved grid points: 4949 -> 4681.
- Proposed new sites (worst-served first):
  1. near **Dhanmondi** — lat 23.6617, lon 90.3324
  2. near **Bashundhara** — lat 23.8766, lon 90.4998
  3. near **Bashundhara** — lat 23.7864, lon 90.4991

## Hospital (`hospital`)

- Underserved threshold: **2.0 km** nearest-facility distance.
- Max access distance: **8.19 km -> 4.97 km** (cut by 3.22 km).
- Mean access distance: 1.70 km -> 1.45 km.
- Underserved grid points: 2411 -> 2188.
- Proposed new sites (worst-served first):
  1. near **Uttara** — lat 23.8992, lon 90.4994
  2. near **Motijheel** — lat 23.6622, lon 90.4990
  3. near **Bashundhara** — lat 23.7954, lon 90.4989

## Water pump / source (`water_pump`)

- Underserved threshold: **1.0 km** nearest-facility distance.
- Max access distance: **10.87 km -> 6.88 km** (cut by 3.99 km).
- Mean access distance: 2.80 km -> 2.21 km.
- Underserved grid points: 5399 -> 5336.
- Proposed new sites (worst-served first):
  1. near **Uttara** — lat 23.8992, lon 90.4994
  2. near **Dhanmondi** — lat 23.6617, lon 90.3324
  3. near **Bashundhara** — lat 23.8247, lon 90.4983

## Fuel station (`fuel`)

- Underserved threshold: **1.5 km** nearest-facility distance.
- Max access distance: **10.11 km -> 5.48 km** (cut by 4.63 km).
- Mean access distance: 2.17 km -> 1.69 km.
- Underserved grid points: 3488 -> 3327.
- Proposed new sites (worst-served first):
  1. near **Uttara** — lat 23.8992, lon 90.4994
  2. near **Bashundhara** — lat 23.8270, lon 90.4983
  3. near **Dhanmondi** — lat 23.6888, lon 90.3319

## Bus stop (`bus_stop`)

- Underserved threshold: **0.8 km** nearest-facility distance.
- Max access distance: **9.84 km -> 5.03 km** (cut by 4.81 km).
- Mean access distance: 1.71 km -> 1.25 km.
- Underserved grid points: 4211 -> 4130.
- Proposed new sites (worst-served first):
  1. near **Bashundhara** — lat 23.8857, lon 90.4996
  2. near **Bashundhara** — lat 23.8292, lon 90.4983
  3. near **Uttara** — lat 23.8758, lon 90.4507

## Fire station (`fire_station`)

- Underserved threshold: **3.0 km** nearest-facility distance.
- Max access distance: **7.43 km -> 6.79 km** (cut by 0.64 km).
- Mean access distance: 2.80 km -> 2.39 km.
- Underserved grid points: 3054 -> 2361.
- Proposed new sites (worst-served first):
  1. near **Uttara** — lat 23.8760, lon 90.3305
  2. near **Motijheel** — lat 23.6616, lon 90.4574
  3. near **Bashundhara** — lat 23.7773, lon 90.4993
