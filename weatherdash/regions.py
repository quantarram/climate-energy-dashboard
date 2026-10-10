"""
Pilot regions: US balancing authorities (EIA-930 codes), each represented by its main load
centres. Weights are approximate metro populations in thousands (rounded 2020-census scale) --
a population-weighted point sample, the way degree-day products are built. To be replaced by
gridded population (GPW / WorldPop) once the pipeline is proven.
"""
# name: (lat, lon, weight_thousands, tz)
REGIONS = {
    "ERCO": {"label": "ERCOT (Texas)", "tz": "America/Chicago", "cities": {
        "Houston": (29.76, -95.37, 7300), "Dallas-Fort Worth": (32.78, -96.80, 8100),
        "San Antonio": (29.42, -98.49, 2700), "Austin": (30.27, -97.74, 2500)}},
    "PJM": {"label": "PJM (Mid-Atlantic / Midwest)", "tz": "America/New_York", "cities": {
        "Philadelphia": (39.95, -75.17, 6200), "Washington DC": (38.90, -77.04, 6300),
        "Chicago": (41.88, -87.63, 9400), "Pittsburgh": (40.44, -79.99, 2400),
        "Columbus": (39.96, -83.00, 2200), "Baltimore": (39.29, -76.61, 2800),
        "Cleveland": (41.50, -81.69, 2100), "Richmond": (37.54, -77.44, 1300),
        "Newark": (40.74, -74.17, 2000)}},
    "CISO": {"label": "CAISO (California)", "tz": "America/Los_Angeles", "cities": {
        "Los Angeles": (34.05, -118.24, 13200), "San Francisco Bay": (37.77, -122.42, 4700),
        "San Diego": (32.72, -117.16, 3300), "Sacramento": (38.58, -121.49, 2400)}},
    "NYIS": {"label": "NYISO (New York)", "tz": "America/New_York", "cities": {
        "New York City": (40.71, -74.01, 8300), "Long Island": (40.79, -73.13, 2900),
        "Buffalo": (42.89, -78.88, 1200), "Rochester": (43.16, -77.61, 1100),
        "Albany": (42.65, -73.76, 900), "Syracuse": (43.05, -76.15, 650)}},
    "ISNE": {"label": "ISO-NE (New England)", "tz": "America/New_York", "cities": {
        "Boston": (42.36, -71.06, 4900), "Hartford": (41.76, -72.69, 1200),
        "Providence": (41.82, -71.41, 1600), "Manchester NH": (42.99, -71.46, 410),
        "Portland ME": (43.66, -70.26, 550)}},
    "MISO": {"label": "MISO (Midcontinent)", "tz": "America/Chicago", "cities": {
        "Minneapolis": (44.98, -93.27, 3700), "Detroit": (42.33, -83.05, 4300),
        "Indianapolis": (39.77, -86.16, 2100), "St. Louis": (38.63, -90.20, 2800),
        "New Orleans": (29.95, -90.07, 1300), "Milwaukee": (43.04, -87.91, 1600),
        "Little Rock": (34.75, -92.29, 750)}},
}

CITY_TZ = {  # a city's own civil day defines its daily mean temperature
    "Chicago": "America/Chicago", "Dallas-Fort Worth": "America/Chicago", "Houston": "America/Chicago",
    "San Antonio": "America/Chicago", "Austin": "America/Chicago", "Minneapolis": "America/Chicago",
    "Indianapolis": "America/Indiana/Indianapolis", "St. Louis": "America/Chicago",
    "New Orleans": "America/Chicago", "Milwaukee": "America/Chicago", "Little Rock": "America/Chicago",
    "Detroit": "America/Detroit", "Los Angeles": "America/Los_Angeles",
    "San Francisco Bay": "America/Los_Angeles", "San Diego": "America/Los_Angeles",
    "Sacramento": "America/Los_Angeles",
}


def city_tz(region, city):
    return CITY_TZ.get(city, REGIONS[region]["tz"])


def all_points():
    """[(region, city, lat, lon, weight)] in a stable order."""
    return [(r, c, v[0], v[1], v[2]) for r, d in REGIONS.items() for c, v in d["cities"].items()]


# ---------------------------------------------------------------------------
# Wind and solar: candidate generation areas per balancing authority. Capacity at each site is not
# known here, so the weights are *learned* from observed EIA-930 generation (see renewables.py);
# the candidates only need to cover where the plants are. (lat, lon)
# ---------------------------------------------------------------------------
SITES = {
    "ERCO": {
        "wind": {"Panhandle": (35.2, -101.8), "Roscoe": (32.45, -100.54), "Abilene": (32.4, -99.7),
                 "Midland-Pecos": (31.4, -103.5), "Kenedy": (27.8, -97.6), "Raymondville": (26.5, -97.8),
                 "Lubbock": (33.6, -101.9)},
        "solar": {"Pecos": (31.4, -103.5), "Fort Stockton": (30.9, -102.9), "Van Horn": (31.0, -104.8),
                  "Del Rio-Uvalde": (29.2, -99.8), "Corpus Christi": (27.8, -97.6), "Abilene": (32.4, -99.7),
                  "Austin": (30.3, -97.7)}},
    "CISO": {
        "wind": {"Tehachapi": (35.1, -118.3), "Altamont": (37.75, -121.65), "Solano": (38.15, -121.85),
                 "San Gorgonio": (33.9, -116.6)},
        "solar": {"Mojave": (35.0, -117.5), "Blythe": (33.6, -114.6), "Imperial Valley": (32.9, -115.6),
                  "Westlands": (36.4, -120.1), "Bakersfield": (35.4, -119.0), "Riverside": (33.9, -117.4)}},
    "MISO": {
        "wind": {"Iowa": (42.4, -93.6), "SW Minnesota": (44.0, -96.0), "North Dakota": (46.9, -98.7),
                 "Illinois": (40.5, -88.9), "Indiana": (40.6, -87.4), "Michigan Thumb": (43.7, -83.0)},
        "solar": {"Illinois": (39.9, -88.0), "Indiana": (39.8, -86.2), "Minnesota": (45.0, -93.5),
                  "Michigan": (42.6, -84.5), "Louisiana": (30.5, -91.5)}},
    "PJM": {
        "wind": {"Illinois": (41.0, -89.0), "Indiana": (40.6, -87.4), "NW Ohio": (41.1, -84.2),
                 "Pennsylvania ridges": (40.0, -79.0), "Maryland West": (39.6, -79.1)},
        "solar": {"Virginia": (37.0, -77.5), "New Jersey": (39.7, -74.8), "Illinois": (40.0, -88.5),
                  "Ohio": (40.0, -83.0), "North Carolina": (36.2, -77.0)}},
    "NYIS": {
        "wind": {"Lowville": (43.8, -75.5), "Western NY": (42.7, -78.3), "Clinton County": (44.9, -73.8)}},
    "ISNE": {
        "wind": {"Aroostook": (46.5, -68.0), "Kibby": (45.4, -70.5), "Western MA": (42.5, -72.8)}},
}


def site_list():
    """[(region, resource, site, lat, lon)] in a stable order."""
    return [(r, res, n, v[0], v[1]) for r, d in SITES.items() for res, sites in d.items() for n, v in sites.items()]
