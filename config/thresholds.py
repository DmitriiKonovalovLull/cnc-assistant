RPM_LIMITS = {
    "steel": lambda d: (50, 6000 / d),
    "aluminum": lambda d: (100, 12000 / d),
    "titanium": lambda d: (30, 3000 / d),
}
