/* Linux7.2-rc3 a13c140cc289c0b7b3770bce5b3ad42ab35074aa;
 * drivers/power/supply/power_supply_core.c, unchanged upstream functions. */
static int power_supply_read_temp(struct thermal_zone_device *tzd,
		int *temp)
{
	struct power_supply *psy;
	union power_supply_propval val;
	int ret;

	WARN_ON(tzd == NULL);
	psy = thermal_zone_device_priv(tzd);
	ret = power_supply_get_property(psy, POWER_SUPPLY_PROP_TEMP, &val);
	if (ret)
		return ret;

	/* Convert tenths of degree Celsius to milli degree Celsius. */
	*temp = val.intval * 100;

	return ret;
}
static const struct thermal_zone_device_ops psy_tzd_ops = {
	.get_temp = power_supply_read_temp,
};

static int psy_register_thermal(struct power_supply *psy)
{
	int ret;

	if (psy->desc->no_thermal)
		return 0;

	/* Register battery zone device psy reports temperature */
	if (psy_desc_has_property(psy->desc, POWER_SUPPLY_PROP_TEMP)) {
		/* Prefer our hwmon device and avoid duplicates */
		struct thermal_zone_params tzp = {
			.no_hwmon = IS_ENABLED(CONFIG_POWER_SUPPLY_HWMON)
		};
		psy->tzd = thermal_tripless_zone_device_register(psy->desc->name,
				psy, &psy_tzd_ops, &tzp);
		if (IS_ERR(psy->tzd))
			return PTR_ERR(psy->tzd);
		ret = thermal_zone_device_enable(psy->tzd);
		if (ret)
			thermal_zone_device_unregister(psy->tzd);
		return ret;
	}

	return 0;
}
