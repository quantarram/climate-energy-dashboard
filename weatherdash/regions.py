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
