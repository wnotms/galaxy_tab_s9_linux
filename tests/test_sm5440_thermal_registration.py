"""Run actual descriptor + pinned mainline thermal registration, no device."""
from pathlib import Path
import ctypes
import subprocess
import tempfile
import unittest
from test_sm5714_policy import function
ROOT=Path(__file__).resolve().parents[1]

class PassiveThermalRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        driver=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        core=(ROOT/'reference/boot-tests/test-299-thermal-read-incident/mainline-thermal-functions.c').read_text()
        code=r'''
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#define ARRAY_SIZE(x) (sizeof(x)/sizeof(*(x)))
#define CONFIG_POWER_SUPPLY_HWMON 0
#define IS_ENABLED(x) (x)
#define IS_ERR(p) ((p)==NULL)
#define PTR_ERR(p) (-ENOMEM)
#define WARN_ON(x) ((void)(x))
enum power_supply_property {POWER_SUPPLY_PROP_STATUS,POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_ONLINE,POWER_SUPPLY_PROP_VOLTAGE_NOW,
 POWER_SUPPLY_PROP_CURRENT_NOW,POWER_SUPPLY_PROP_TEMP};
#define POWER_SUPPLY_TYPE_MAINS 1
union power_supply_propval {int intval;};
struct power_supply;struct thermal_zone_device {struct power_supply *psy;};
struct thermal_zone_device_ops {int (*get_temp)(struct thermal_zone_device *,int *);};
struct thermal_zone_params {bool no_hwmon;};
struct power_supply_desc {const char *name;int type;bool no_thermal;
 const enum power_supply_property *properties;unsigned int num_properties;
 int (*get_property)(struct power_supply *,enum power_supply_property,union power_supply_propval *);};
struct power_supply {const struct power_supply_desc *desc;struct thermal_zone_device *tzd;};
static int registered,enabled,reads,property_error;static struct thermal_zone_device zone;
static void *thermal_zone_device_priv(struct thermal_zone_device *t){return t->psy;}
static int sm5440_get_property(struct power_supply *p,enum power_supply_property prop,union power_supply_propval *v){(void)p;(void)prop;reads++;if(property_error)return property_error;v->intval=318;return 0;}
static int power_supply_get_property(struct power_supply *p,enum power_supply_property prop,union power_supply_propval *v){return p->desc->get_property(p,prop,v);}
static bool psy_desc_has_property(const struct power_supply_desc *p,enum power_supply_property prop){for(unsigned int i=0;i<p->num_properties;i++)if(p->properties[i]==prop)return true;return false;}
static struct thermal_zone_device *thermal_tripless_zone_device_register(const char *name,void *data,const struct thermal_zone_device_ops *ops,const struct thermal_zone_params *params){(void)name;(void)ops;(void)params;registered++;zone.psy=data;return &zone;}
static int thermal_zone_device_enable(struct thermal_zone_device *t){(void)t;enabled++;return 0;}
static void thermal_zone_device_unregister(struct thermal_zone_device *t){(void)t;}
'''
        start=driver.index('static enum power_supply_property sm5440_props[]')
        end=driver.index('static int sm5440_quiesce(',start)
        code+=driver[start:end]+core.split('*/',1)[1]
        code+=r'''
int exercise(int mode,int *out){
 registered=enabled=reads=property_error=0;struct power_supply_desc desc=sm5440_desc;
 if(mode) {desc.no_thermal=false;desc.name="sm5714-battery";}
 struct power_supply psy={.desc=&desc};int ret=psy_register_thermal(&psy),temperature=0;
 if(mode==2)ret=power_supply_read_temp(psy.tzd,&temperature);
 if(mode==3){property_error=-ENODATA;ret=power_supply_read_temp(psy.tzd,&temperature);}
 out[0]=registered;out[1]=enabled;out[2]=reads;out[3]=temperature;
 out[4]=psy_desc_has_property(&desc,POWER_SUPPLY_PROP_TEMP);return ret;}
'''
        c=Path(cls.temp.name)/'thermal.c';so=c.with_suffix('.so');c.write_text(code)
        result=subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror','-o',str(so),str(c)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        cls.lib=ctypes.CDLL(str(so))
    def run_case(self,mode):
        out=(ctypes.c_int*5)();ret=self.lib.exercise(mode,out);return ret,list(out)
    def test_passive_cache_never_creates_thermal_zone(self):self.assertEqual(self.run_case(0),(0,[0,0,0,0,1]))
    def test_standard_battery_zone_still_registers(self):self.assertEqual(self.run_case(1),(0,[1,1,0,0,1]))
    def test_standard_temperature_units_are_unchanged(self):self.assertEqual(self.run_case(2),(0,[1,1,1,31800,1]))
    def test_missing_temperature_still_propagates(self):self.assertEqual(self.run_case(3),(-61,[1,1,1,0,1]))
    def test_real_passive_error_guards_and_pack_sensor_retained(self):
        driver=(ROOT/'kernel/drivers/sm5440-direct.c').read_text();get=function(driver,'static int sm5440_get_property(')
        self.assertIn('startup_pending || !sample.valid',get);self.assertIn('return -ENODATA',get);self.assertIn('sample.stamp + msecs_to_jiffies(2500)',get)
        battery=(ROOT/'kernel/drivers/sm5714-battery.c').read_text();self.assertNotIn('.no_thermal = true',battery)
        self.assertIn('iio_read_channel_processed',function(battery,'static int sm5714_get_temp(struct sm5714_battery *sm, int *val)\n{'))
        self.assertIn('sm5714_disable_charging',function(battery,'static int sm5714_configure_charging_locked('))
