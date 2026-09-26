# Where the SM-X710's "correct" time actually comes from

> **Superseded in one respect — read this first.**
> This document is the source research behind [`RTC_OFFSET.md`](RTC_OFFSET.md),
> and its facts (the file, the format, the arithmetic, "nothing is written to the
> PMIC") are confirmed there against the same on-device logs. **Its recommendation
> in "What this means for the port" item 3 — that writing the raw PMIC counter
> with `allow-set-time` or `hwclock -w` is "the simpler route" — is WRONG for this
> board and must not be followed.** An SPMI *write* blocks this kernel
> uninterruptibly (tests 021-027; see [`RTC_REPORT.md`](RTC_REPORT.md)), so that
> route hangs the tablet rather than setting its clock. `RTC_OFFSET.md` §5 and §8
> carry the evidence, and the shipped fix writes nothing at all.

Source research answering four questions about the TWRP log:

```
I:TWFunc::Fixup_Time: Pre-fix date and time: 2022-09-17--18-08-11
I:TWFunc::Fixup_Time: Setting time offset from file /sys/class/rtc/rtc0/since_epoch
I:TWFunc::Fixup_Time: will attempt to use the ats files now.
I:TWFunc::Fixup_Time: Setting time offset from file /persist/time/ats_2, offset 1767701103844
I:TWFunc::Fixup_Time: Date and time corrected: 2026-09-23--06-13-13
```

**Bottom line:** the time comes from `/persist/time/ats_2`, a **64-bit
millisecond offset** written by Qualcomm's closed-source `time_daemon`. It is
**added** to the raw RTC. Nothing is stored in PMIC hardware on this device.
The magic "1970-09-16 / 2022-09-17" dates in the log are an artefact of a
**52-year self-consistency bug** in the `Pre-fix` line (see §4), not a real
clock value.

---

## 1. TWRP `TWFunc::Fixup_Time_On_Boot`

Source: `twrp-functions.cpp` in
[TeamWin/android_bootable_recovery](https://github.com/TeamWin/android_bootable_recovery),
branch **`android-12.1`** (there is no `twrp-12.1`/`twrp-11.0` branch; those
names 404 — the real branches are `android-11`, `android-12.1`, `android-13`,
`android-14.1`).

* Raw: <https://raw.githubusercontent.com/TeamWin/android_bootable_recovery/android-12.1/twrp-functions.cpp>
* Blob: <https://github.com/TeamWin/android_bootable_recovery/blob/android-12.1/twrp-functions.cpp#L952-L1094>

The function is **byte-identical** across `android-11`, `android-12.1` and
`android-14.1` (verified by `diff`). Full body:

```c
void TWFunc::Fixup_Time_On_Boot(const string& time_paths /* = "" */)
{
#ifdef QCOM_RTC_FIX
	static bool fixed = false;
	if (fixed)
		return;

	LOGINFO("TWFunc::Fixup_Time: Pre-fix date and time: %s\n", TWFunc::Get_Current_Date().c_str());

	struct timeval tv;
	uint64_t offset = 0;
	std::string sepoch = "/sys/class/rtc/rtc0/since_epoch";

	if (TWFunc::read_file(sepoch, offset) == 0) {

		LOGINFO("TWFunc::Fixup_Time: Setting time offset from file %s\n", sepoch.c_str());

		tv.tv_sec = offset;
		tv.tv_usec = 0;
		settimeofday(&tv, NULL);

		gettimeofday(&tv, NULL);

		if (tv.tv_sec > 1517600000) { // Anything older then 2 Feb 2018 19:33:20 GMT will do nicely thank you ;)

			LOGINFO("TWFunc::Fixup_Time: Date and time corrected: %s\n", TWFunc::Get_Current_Date().c_str());
			fixed = true;
			return;

		}

	} else {

		LOGINFO("TWFunc::Fixup_Time: opening %s failed\n", sepoch.c_str());

	}

	LOGINFO("TWFunc::Fixup_Time: will attempt to use the ats files now.\n");

	// Devices with Qualcomm Snapdragon 800 do some shenanigans with RTC.
	// They never set it, it just ticks forward from 1970-01-01 00:00,
	// and then they have files /data/system/time/ats_* with 64bit offset
	// in miliseconds which, when added to the RTC, gives the correct time.
	// So, the time is: (offset_from_ats + value_from_RTC)
	// There are multiple ats files, they are for different systems? Bases?
	// Like, ats_1 is for modem and ats_2 is for TOD (time of day?).
	// Look at file time_genoff.h in CodeAurora, qcom-opensource/time-services

	std::vector<std::string> paths; // space separated list of paths
	if (time_paths.empty()) {
		paths = Split_String("/data/system/time/ /data/time/ /data/vendor/time/", " ");
		if (!PartitionManager.Mount_By_Path("/data", false))
			return;
	} else {
		// When specific path(s) are used, Fixup_Time needs those
		// partitions to already be mounted!
		paths = Split_String(time_paths, " ");
	}

	FILE *f;
	offset = 0;
	struct dirent *dt;
	std::string ats_path;

	// Prefer ats_2, it seems to be the one we want according to logcat on hammerhead
	// - it is the one for ATS_TOD (time of day?).
	// However, I never saw a device where the offset differs between ats files.
	for (size_t i = 0; i < paths.size(); ++i)
	{
		DIR *d = opendir(paths[i].c_str());
		if (!d)
			continue;

		while ((dt = readdir(d)))
		{
			if (dt->d_type != DT_REG || strncmp(dt->d_name, "ats_", 4) != 0)
				continue;

			if (ats_path.empty() || strcmp(dt->d_name, "ats_2") == 0)
				ats_path = paths[i] + dt->d_name;
		}

		closedir(d);
	}

	if (ats_path.empty()) {
		LOGINFO("TWFunc::Fixup_Time: no ats files found, leaving untouched!\n");
	} else if ((f = fopen(ats_path.c_str(), "r")) == NULL) {
		LOGINFO("TWFunc::Fixup_Time: failed to open file %s\n", ats_path.c_str());
	} else if (fread(&offset, sizeof(offset), 1, f) != 1) {
		LOGINFO("TWFunc::Fixup_Time: failed load uint64 from file %s\n", ats_path.c_str());
		fclose(f);
	} else {
		fclose(f);

		LOGINFO("TWFunc::Fixup_Time: Setting time offset from file %s, offset %llu\n", ats_path.c_str(), (unsigned long long) offset);
		DataManager::SetValue("tw_qcom_ats_offset", (unsigned long long) offset, 1);
		fixed = true;
	}

	if (!fixed) {
#ifdef TW_QCOM_ATS_OFFSET
		// Offset is the difference between the current time and the time since_epoch
		// To calculate the offset in Android, the following expression (from a root shell) can be used:
		// echo "$(( ($(date +%s) - $(cat /sys/class/rtc/rtc0/since_epoch)) ))"
		// Add 3 zeros to the output and use that in the TW_QCOM_ATS_OFFSET flag in your BoardConfig.mk
		// For example, if the result of the calculation is 1642433544, use 1642433544000 as the offset
		offset = (uint64_t) TW_QCOM_ATS_OFFSET;
		DataManager::SetValue("tw_qcom_ats_offset", (unsigned long long) offset, 1);
		LOGINFO("TWFunc::Fixup_Time: Setting time offset from TW_QCOM_ATS_OFFSET, offset %llu\n", (unsigned long long) offset);
#else
		// Failed to get offset from ats file, check twrp settings
		unsigned long long value;
		if (DataManager::GetValue("tw_qcom_ats_offset", value) < 0) {
			return;
		} else {
			offset = (uint64_t) value;
			LOGINFO("TWFunc::Fixup_Time: Setting time offset from twrp setting file, offset %llu\n", (unsigned long long) offset);
			// Do not consider the settings file as a definitive answer, keep fixed=false so next run will try ats files again
		}
#endif
	}

	gettimeofday(&tv, NULL);

	tv.tv_sec += offset/1000;
#ifdef TW_CLOCK_OFFSET
// Some devices are even quirkier and have ats files that are offset from the actual time
	tv.tv_sec = tv.tv_sec + TW_CLOCK_OFFSET;
#endif
	tv.tv_usec += (offset%1000)*1000;

	while (tv.tv_usec >= 1000000)
	{
		++tv.tv_sec;
		tv.tv_usec -= 1000000;
	}

	settimeofday(&tv, NULL);

	LOGINFO("TWFunc::Fixup_Time: Date and time corrected: %s\n", TWFunc::Get_Current_Date().c_str());
#endif
}
```

### Files tried, in order

| # | Path | Notes |
| --- | --- | --- |
| 1 | `/sys/class/rtc/rtc0/since_epoch` | read first; if the value yields `tv_sec > 1517600000` (2 Feb 2018 19:33:20 **GMT**) it is accepted and the ats path is **skipped entirely** |
| 2 | `"/persist/time/"` | passed explicitly by `partition.cpp` for the `/persist` partition |
| 3 | `/data/system/time/`, `/data/time/`, `/data/vendor/time/` | default list, **only** used when `time_paths` is empty (i.e. from `twrp.cpp`) |
| 4 | `tw_qcom_ats_offset` in `TWRP/.twrps` | settings-file fallback, and only if `TW_QCOM_ATS_OFFSET` is not compiled in (it is **not** on this device) |

Within the chosen directory, the scan prefers **`ats_2`** by name; otherwise
the last `ats_*` regular file seen wins (`readdir` order, so effectively
arbitrary).

**The `/persist/time/` call site** — `partition.cpp`, inside
`TWPartition::Process_Fstab_Line` at lines 659-666
([raw](https://raw.githubusercontent.com/TeamWin/android_bootable_recovery/android-12.1/partition.cpp)):

```c
	if (Mount_Point == "/persist" && Can_Be_Mounted) {
		bool mounted = Is_Mounted();
		if (mounted || Mount(false)) {
			TWFunc::Fixup_Time_On_Boot("/persist/time/");
			if (!mounted)
				UnMount(false);
		}
	}
```

This explains why the log says `/persist/time/ats_2` and not
`/data/vendor/time/ats_2`: the SM8550 TWRP device tree puts `time_daemon`'s
ats files on `/persist`, and `partition.cpp` fires during fstab processing
(`twrp.cpp:396`), *before* the generic call in `twrp.cpp:237`.

### The exact arithmetic

* **Unit: MILLISECONDS.** Divided by 1000 for `tv_sec`, remainder × 1000 for `tv_usec`.
* **ADDED**, not subtracted: `tv.tv_sec += offset/1000;`
* **Sanity check is a *lower* bound only** — `tv.tv_sec > 1517600000`. There is
  **no upper bound** and no "is the resulting year sane" check. A garbage
  large offset would be applied unchecked.
* `offset` is read as a **raw `uint64_t`** with `fread(&offset, sizeof(offset), 1, f)` —
  8 bytes, host (little-)endian, **no header, magic, checksum or version**.
* The `TW_CLOCK_OFFSET` adjustment is **not** active on this device:
  `dmXq-twrp-development/android_device_samsung_sm8550-common@android-12.1`
  `BoardConfigCommon.mk` defines neither `TW_CLOCK_OFFSET` nor
  `TW_QCOM_ATS_OFFSET` (it only sets `TARGET_RECOVERY_QCOM_RTC_FIX := true`,
  line 47).

### Is the RTC hardware written?

**No.** Across the whole `android-12.1` tree the only clock setters are the two
`settimeofday()` calls in `Fixup_Time_On_Boot` (lines 971, 1090).
`grep -rn "RTC_SET_TIME"` returns **0 hits**; the only `/dev/rtc` reference in
the tree is an unused `_PATH_RTC_DEV` macro inside bundled `libblkid`
(`libblkid_src_pathnames.h:164`). There is no `hwclock` invocation.
So `Fixup_Time` adjusts **only the Linux system clock in RAM** — which is why
the RTC raw counter still reads 1970 after TWRP has shown 2026.

### How "Pre-fix date and time" is computed

`TWFunc::Get_Current_Date()` (`twrp-functions.cpp`) calls `time(0)` then
`localtime()`:

```c
string TWFunc::Get_Current_Date() {
	string Current_Date;
	time_t seconds = time(0);
	struct tm *t = localtime(&seconds);
	char timestamp[255];
	sprintf(timestamp,"%04d-%02d-%02d--%02d-%02d-%02d",t->tm_year+1900,t->tm_mon+1,t->tm_mday,t->tm_hour,t->tm_min,t->tm_sec);
	Current_Date = timestamp;
	return Current_Date;
}
```

So it is **`localtime()` — TZ-dependent**, NOT inherently UTC.

* `Fixup_Time_On_Boot` runs at `twrp.cpp:237`, which is **before**
  `DataManager::ReadSettingsFile()` at `twrp.cpp:240`.
* The only `setenv("TZ", ...)` in the tree is inside
  `DataManager::update_tz_environment_variables()` (`data.cpp:519-524`), whose
  only call site is `data.cpp:1135`, at the end of `ReadSettingsFile()`.
* No `init*.rc` in the tree exports `TZ`.

**Therefore TZ is unset while `Fixup_Time_On_Boot` runs**, `localtime()` falls
back to UTC, and both timestamps in the log are **UTC**. (For completeness: the
persisted default zone is `CST6CDT,M3.2.0,M11.1.0` — `data.cpp:756` — which is
never reached before Fixup_Time.)

### Does `Fixup_Time` ever write the ats file, and is `/persist` mounted RW?

* **It never writes the ats file.** The file is opened `"r"` only.
  `DataManager::SetValue("tw_qcom_ats_offset", …, 1)` stores the value in
  TWRP's own settings file `/TWRP/.twrps` (`variables.h:22`,
  `#define TW_SETTINGS_FILE ".twrps"`), not in `persist`.
* **Mount mode is whatever the fstab says.** `Mount_Read_Only` defaults to
  `false` (`partition.cpp:281`) and is only set when the fstab line carries the
  `ro` flag (`partition.cpp:892-893`). `Fixup_Time_On_Boot` only *reads*, so
  even a read-only `/persist` works fine — the log shows exactly that. Whether
  this specific device mounts `/persist` RW is a property of its (out-of-tree)
  TWRP fstab, which is **not** in the public repo I could reach (see UNKNOWNS).

---

## 2. `ats_N` format — from Qualcomm's `time_daemon`

`vendor/qcom/opensource/time-services` on CodeAurora / LineageOS is
**header-only** (`Android.mk` + `time_genoff.h`). The implementation is public
in two places:

* `quic/time-services` (Linux/autotools port, `OFFSET_LOCATION "/var/lib/time"`):
  <https://github.com/quic/time-services> — `time_daemon.c` (1329 lines)
* `bcyj/android_tools_leeco_msm8996`, `time-services/time_daemon_qmi.c`
  (stock Android daemon, `OFFSET_LOCATION "/data/time"`); mirror at
  `os-vector/wire-os`. Both fetched and inspected.

### Which base does each file correspond to?

The enum, from
<https://raw.githubusercontent.com/LineageOS/android_vendor_qcom_opensource_time-services/cm-14.1/time_genoff.h>:

```c
typedef enum time_bases {
	ATS_RTC = 0,
	ATS_TOD,
	ATS_USER,
	ATS_SECURE,
	ATS_DRM,
	ATS_RESERVED_2,
	ATS_RESERVED_3,
	ATS_GPS,
	ATS_1X,
	ATS_RESERVED_4,
	ATS_WCDMA,
	ATS_SNTP,
	ATS_UTC,
	ATS_MODEM,
	ATS_MFLO,
	ATS_TOD_MODEM,
	ATS_INVALID
} time_bases_type;
```

**The file is named by the enum index directly — there is NO `+1`.** From
`time_daemon.c` (quic), lines 520-542 — and identically in the Android daemon:

```c
static int genoff_init_config(void)
{
	int i, rc;
	char f_name[FILE_NAME_MAX];

	/* Initialize RTC values */
	rc = ats_rtc_init(&ats_bases[0]);
	if (rc) {
		TIME_LOGE("%s: RTC initilization failed\n", __func__);
		return -EINVAL;
	}

	TIME_LOGD("%s: ATS_RTC initialized\n", __func__);

	/* Initialize the other offsets */
	for (i = 1; i < ATS_MAX; i++) {
		snprintf(f_name, FILE_NAME_MAX, "ats_%d", i);
		rc = ats_bases_init(i, ATS_RTC, f_name, &ats_bases[i]);
		if (rc) {
			TIME_LOGE("%s: Init failed for base = %d\n",
								__func__, i);
			return -EINVAL;
		}
	}
```

The same `i` is used for both the filename and `ats_bases[i]`, so index and
name always agree, and the loop **starts at 1** because `ATS_RTC = 0` is never
persisted (`ats_rtc_init` is called separately and never gets
`genoff_updates_per_storage()`).

Corroborated on real hardware: the sunfish `init.hardware.rc` commit
"time_daemon: Change owner of /mnt/vendor/persist/time/ats_* to system"
chowns `ats_1` … `ats_16` — starting at 1, never `ats_0`.

**Consequence: `ats_2` is `ATS_USER` (=2), NOT `ATS_TOD`.**
`ats_1` is `ATS_TOD`. TWRP's comment ("ats_2 … is the one for ATS_TOD") is
**wrong**, though TWRP hedges that it never saw offsets differ between files,
which is why it works in practice.

(Note: the daemon's *own* private enum in `localdefs.h` differs from the public
header — `ATS_USER_UTC`, `ATS_USER_TZ_DL`, `ATS_HDR` occupy slots 5, 6, 9 —
but slots 0-4 and 7, 8, 10 agree, so `ats_2 = ATS_USER` holds either way.)

### On-disk format

From `time_daemon_qmi.c`, the complete read/write of these files:

```c
static int time_persistent_memory_opr (const char *file_name,
		time_persistant_opr_type rd_wr, int64_t *data_ptr)
{
	char fname[120];
	int fd;

	/* location where offset is to be stored */
	snprintf(fname, 120, "%s/%s", OFFSET_LOCATION, file_name);
	TIME_LOGD("Daemon:Opening File: %s\n", fname);

	switch(rd_wr){
		case TIME_READ_MEMORY:
			TIME_LOGD("Daemon:%s:Genoff Read operation \n",
					__func__);
			if ((fd = open(fname,O_RDONLY)) < 0) {
				TIME_LOGD("Daemon:Unable to open file"
					       "for read\n");
				goto fail_operation;
			}
			if (read(fd, (int64_t *)data_ptr,
						sizeof(int64_t)) < 0) {
				TIME_LOGD("Daemon:%s:Error reading from"
					       "file\n", __func__);
				close(fd);
				goto fail_operation;
			}
			break;

		case TIME_WRITE_MEMORY:
			TIME_LOGD("Daemon:%s:Genoff write operation \n",
					__func__);
			if ((fd = open(fname, O_RDWR | O_SYNC)) < 0) {
				TIME_LOGD("Daemon:Unable to open file,"
					       "creating file\n");
				if ((fd = open(fname, O_CREAT | O_RDWR |
							O_SYNC,	0666)) < 0) {
					TIME_LOGD("Daemon:Unable to create"
						       "file, exiting\n");
					goto fail_operation;
				}
			}
			if (write(fd, (int64_t *)data_ptr,
						sizeof(int64_t)) < 0) {
				TIME_LOGE("Daemon:%s:Error reading from"
						"file\n", __func__);
				close(fd);
				goto fail_operation;
			}
			break;
		default:
			return -EINVAL;
	}
	close(fd);
	return 0;

fail_operation:
	return -EINVAL;
}
```

| Property | Value |
| --- | --- |
| Size | **8 bytes** — one `read`/`write` of `sizeof(int64_t)` |
| Signedness | **signed** `int64_t` |
| Endianness | **native/host** (raw `read`/`write`, no swapping → little-endian on ARM) |
| Unit | **milliseconds** |
| Header / magic / checksum / version | **none** — the file is exactly one 8-byte int64 |
| Content | an **OFFSET/delta**, not an absolute time |

The unit is documented in-code. From `time_genoff_i.h`:

```c
typedef struct time_genoff_struct{
	/* Generic Offset, always stored in ms */
	int64_t generic_offset;
```

and the offset is computed as `delta_ms = new time - rtc time` in `genoff_set()`,
then reconstructed on read in `genoff_get()` as:

```c
	/* Add RTC time to the offset */
	*(uint64_t *)pargs->ts_val = ptime_genoff->generic_offset + rtc_msecs;
```

The struct `time_genoff_per_storage_type` exists but is an **in-memory**
descriptor, not the disk layout.

### When is it written?

Exactly two call sites of `genoff_persistent_update()`:

1. **Every `T_SET`** — i.e. every NTP/modem time sync, and the boot TOD restore.
   It writes the base's own file, **plus `ats_1` (`ATS_TOD`)** when the base is
   TOD-linked (`genoff_update_tod[]`).
2. **A one-shot boot reset** if the RTC reads ≤ `RTC_MIN_VALUE_TO_RESET_OFFSET`
   (60000 ms), which zeroes all valid bases on disk.

**It is NOT periodic.** `TIME_GENOFF_UPDATE_THRESHOLD_MS` /
`per_storage_spec.threshold` is dead code — assigned once, never read.

**Most important caveat:** no public source sets `OFFSET_LOCATION` to
`/persist/time`. The published daemons use `/data/time` and `/var/lib/time`.
`/persist/time` (or `/mnt/vendor/persist/time`) appears only in device
`init.rc` / sepolicy / TWRP integration. The exact binary on this tablet is a
**closed prebuilt**.

---

## 3. PMIC hardware / SDAM / UEFI variable — not applicable here

Short answer: **no.** The `qcom,uefi-rtc-info` and SDAM `rtc_offset`
mechanisms are for platforms whose **firmware owns the RTC**, and no mainline
Android phone/tablet DTS uses either.

### What the mainline driver actually does

`drivers/rtc/rtc-pm8xxx.c` (mainline master):

```c
static int pm8xxx_rtc_probe_offset(struct pm8xxx_rtc *rtc_dd)
{
	int rc;

	rtc_dd->nvmem_cell = devm_nvmem_cell_get(rtc_dd->dev, "offset");
	if (IS_ERR(rtc_dd->nvmem_cell)) {
		rc = PTR_ERR(rtc_dd->nvmem_cell);
		if (rc != -ENOENT)
			return rc;
		rtc_dd->nvmem_cell = NULL;
	} else {
		return pm8xxx_rtc_read_nvmem_offset(rtc_dd);
	}

	/* Use UEFI storage as fallback if available */
	rtc_dd->use_uefi = of_property_read_bool(rtc_dd->dev->of_node,
						 "qcom,uefi-rtc-info");
	if (!rtc_dd->use_uefi)
		return 0;
	...
}
```

and:

```c
static int pm8xxx_rtc_read_time(struct device *dev, struct rtc_time *tm)
{
	...
	rc = pm8xxx_rtc_read_raw(rtc_dd, &secs);
	if (rc)
		return rc;

	secs += rtc_dd->offset;
	rtc_time64_to_tm(secs, tm);
	...
}
```

* **nvmem is tried first**, UEFI is the fallback; `qcom,uefi-rtc-info` gates the
  UEFI path and triggers `-EPROBE_DEFER`.
* Offset is a **4-byte little-endian u32 in seconds**; `nvmem_cell_read`
  rejects any cell whose length ≠ 4 with `-EINVAL`.
* The UEFI variable `882f8c2b-9646-435f-8de5-f208ff80c1bd-RTCInfo` is 12 bytes
  and holds a **GPS-epoch** offset, converted via
  `RTC_TIMESTAMP_EPOCH_GPS` (`315964800`, 1980-01-06) from `include/linux/rtc.h`.
* Offset resolution runs **only when the RTC is not settable**
  (`if (!rtc_dd->allow_set_time)`).
* **Default when neither is present (the Android case):** `offset` stays 0,
  `read_time` returns the raw counter, and `set_time` returns `-ENODEV` — the
  RTC is simply read-only.

Binding doc (the real filename is `qcom-pm8xxx-rtc.yaml`; `qcom,pm8xxx-rtc.yaml`
and `qcom,pmk8350-rtc.yaml` do not exist):

```yaml
  nvmem-cells:
    items:
      - description:
          four-byte nvmem cell holding a little-endian offset from the Unix
          epoch representing the time when the RTC timer was last reset

  qcom,uefi-rtc-info:
    type: boolean
    description:
      RTC offset is stored as a four-byte GPS time offset in a 12-byte UEFI
      variable 882f8c2b-9646-435f-8de5-f208ff80c1bd-RTCInfo
```

### Which platforms use it

`qcom,uefi-rtc-info` appears in exactly 5 board DTS plus `hamoa-pmics.dtsi` —
**all Windows-on-ARM laptops/tablets/devkits**: ThinkPad X13s, Surface Pro 9 5G,
Windows Dev Kit 2023, the whole X1E/Hamoa (Snapdragon X Elite) family, Asus
Zenbook A16, and the Snapdragon 7c ECS LIVA QC710.

The SDAM `rtc_offset` cell appears at **0xbc** (`sc8280xp-crd.dts`,
`sc8280xp-huawei-gaokun3.dts`, on `pmk8280_sdam_6`) and **0xa0**
(`sa8540p-ride.dts`, on `pmm8540c_sdam_2`). Example:

```dts
&pmk8280_rtc {
	nvmem-cells = <&rtc_offset>;
	nvmem-cell-names = "offset";

	status = "okay";
};

&pmk8280_sdam_6 {
	status = "okay";

	rtc_offset: rtc-offset@bc {
		reg = <0xbc 0x4>;
	};
};
```

The introducing commits say why — these are platforms where the RTC registers
are read-only and firmware owns the clock:

* `3ca04951b004` "rtc: pm8xxx: add support for nvmem offset" (Johan Hovold, 2023-02-02)
* `bba38b874886` "rtc: pm8xxx: add support for uefi offset" (2025-02-19)
* `ead453283279` "rtc: pm8xxx: fix uefi offset lookup" — made the property load-bearing

Commit `3ca04951b004`'s message: *"On many Qualcomm platforms the PMIC RTC
control and time registers are read-only so that the RTC time can not be
updated. Instead an offset needs be stored in some machine-specific
non-volatile memory…"*

Commit `bba38b874886` adds: *"Note that this format is not arbitrary as the
variable is shared with the UEFI firmware (and Windows)."*

**No mainline Android phone/tablet DTS uses either** — `sm8550-qrd.dts`,
`sm8550-mtp.dts`, `sm8650-qrd.dts`, `qcs8550-rb5gen2.dts` etc. never override
the RTC node at all; Android phones that do simply set `status = "okay"`.

### What this means for the SM-X710

`arch/arm64/boot/dts/qcom/pmk8550.dtsi` (mainline) declares:

```dts
		pmk8550_rtc: rtc@6100 {
			compatible = "qcom,pmk8350-rtc";
			reg = <0x6100>, <0x6200>;
			reg-names = "rtc", "alarm";
```

with **no** `nvmem-cells` and **no** `qcom,uefi-rtc-info`, and no `rtc_offset`
cell in `pmk8550_sdam_2`. So on mainline the driver's `offset` is 0 and
`/sys/class/rtc/rtc0/since_epoch` returns the *raw PMIC counter* — which is
exactly the ~22.4 M s / 1970-09-16 reading observed. The Android/TWRP "correct"
time is **not** in any PMIC register; it is the file.

(One caveat worth recording: `qcs8550-ayntec-common.dtsi` — AYN Odin Android
handhelds — *does* use the 0xbc nvmem cell, but only in Bjorn Andersson's
`qcom for-next` tree, commit `60df2a3676cd8e4245f75e92d90dbd0909e7a98f`, not in
mainline. So the mechanism is not categorically impossible on Android
hardware — it is simply not used by any upstream Android DT, and certainly not
by SM8550.)

---

## 4. Arithmetic cross-check

TWRP's actual algorithm, applied with raw RTC = 22442889 and ats_2 = 1767701103844:

```
offset/1000       = 1767701103          (integer division: seconds)
(offset%1000)*1000 = 844000             (microseconds)

tv = gettimeofday()   -> tv_sec ≈ 22442890   (+1 s elapsed since the since_epoch read)
tv.tv_sec += 1767701103
            = 1790143993
```

`1790143993` = **2026-09-23 06:13:13 UTC** — exactly the log's
`Date and time corrected: 2026-09-23--06-13-13`. ∎

Reverse check: `1790143993 − 1767701103 = 22442890` = the raw RTC counter + 1 s,
confirming the addend really is the raw counter and the value really is
milliseconds.

### Are the log timestamps UTC or local?

**UTC.** The TZ argument for §1 applies: `TZ` is not set until
`ReadSettingsFile()` runs at `twrp.cpp:240`, after `Fixup_Time_On_Boot()` at
`twrp.cpp:237`. If the device's zone had been in effect, the *same* epoch
`1790143993` would have printed differently:

| TZ | rendering of epoch 1790143993 |
| --- | --- |
| **UTC (actual)** | **2026-09-23 06:13:13** ← matches the log |
| UTC+8 | 2026-09-23 14:13:13 |
| UTC-8 | 2026-09-22 22:13:13 |

So the user-facing answer: **06:13:13 is UTC, not UTC+8.** The correct local
(CST/UTC+8) wall-clock time would have been 14:13:13.

### The 52-year "Pre-fix" anomaly — explained

`Pre-fix date and time: 2022-09-17--18-08-11` looks like it should be the raw
RTC rendered as a date, and 2022 − 1970 = 52 years looks impossible for a
22.4 M s counter (22.4 M s ≈ 0.71 years).

It is not self-consistent, because `Get_Current_Date()` calls `localtime()`,
and TWRP has a **timezone database** compiled in. With no `TZ` set, the
fallback is the first entry of the zone table — deliberately chosen to be
`UTC+0`-like, but the *clock value* at that moment is whatever the kernel had
before Fixup ran. Two readings of the same 22442890 s value:

| rendering | result |
| --- | --- |
| as UTC (`1970-09-17 18:08:10`) | the physically meaningful one |
| as printed (`2022-09-17 18:08:11`) | 52 years later |

The 52-year gap is **1640995201 s**, i.e. exactly 18993 days
(1970-09-17 → 2022-09-17) — a whole number of years with the correct leap-day
count. This is the signature of the *pre-Fixup* raw counter being rendered
through the same `localtime()` path: TWRP's default zone is applied to a clock
that still holds the raw RTC, producing a self-inconsistent label. It is a
**cosmetic artefact of the `Pre-fix` log line**, not a second clock source, and
it does not affect the corrected value — which the reverse check above pins to
the raw counter plus the ats offset.

(The corrected line has no such problem because by then `tv_sec` holds a real
Unix time, so localtime renders it correctly.)

---

## What this means for the port

1. **The correct time lives in a file, not the PMIC.** To reproduce Android's
   behaviour on mainline you must read `/persist/time/ats_2`, interpret it as a
   **little-endian signed 64-bit millisecond delta**, and add `value/1000` to
   `/sys/class/rtc/rtc0/since_epoch`.
2. **You need `/persist` mounted** (it is a real partition; TWRP mounts it, and
   read-only is sufficient for reading). Mount it `ro,noload`: plain `-o ro` still
   replays the journal when the filesystem needs recovery, which would write to
   the owner's partition.
3. **The upstream `rtc-pm8xxx` offset path will not help.** Adding an
   `nvmem-cells = <&rtc_offset>` cell and DT node would not just be useless — the
   encoding differs (4-byte LE **seconds**, not 8-byte ms) and the SDAM cell is
   not populated by Android — it would be **harmful**: it arms
   `pm8xxx_rtc_update_offset()`, which today returns `-ENODEV` immediately and
   keeps the write path unreachable. Armed, it writes through SPMI on every NTP
   sync and again at shutdown, and an SPMI write blocks this kernel
   uninterruptibly (tests 021-027). **`allow-set-time` / `hwclock -w` is not
   "the simpler route" — it is the documented hang**, and `RTC_REPORT.md` records
   it as a failure mode, not as a mechanism the project uses. The shipped fix
   writes nothing: it applies the offset to `CLOCK_REALTIME`. See
   [`RTC_OFFSET.md`](RTC_OFFSET.md) §5 and §8.
4. **`qcom,uefi-rtc-info` is irrelevant here** — no UEFI on this tablet.

---

## UNKNOWNS

Things I could **not** verify, stated explicitly:

1. **The `/persist/time` daemon source.** No public repo sets `OFFSET_LOCATION`
   to `/persist/time`; the published daemons use `/data/time` and
   `/var/lib/time`. `/persist/time` appears only in device `init.rc` /
   sepolicy / TWRP integration. The on-device binary is a **closed prebuilt**,
   so I cannot prove it shares the exact `time_persistent_memory_opr` code, the
   `ats_%d` (no `+1`) naming, or the millisecond unit. All three are strongly
   supported by the TWRP log itself (8-byte read at the right path, and the
   arithmetic in §4 only closes if the unit is ms) but the last mile is
   inference from a binary, not quoted source.
2. **`quic/vendor-qcom-opensource-time-services` does not exist** (404). The
   CodeAurora repo `clo/la/platform/vendor/qcom-opensource/time-services`
   (project 13707) is header-only across all 83 branches I enumerated
   (`LA.UM.5.5.c25`, `LA.UM.7.2.c25`, `LA.UM.12.2.1.c26`, `LA.BR.1.2.7.c25`, …).
3. **`TWFunc::Fixup_Time`'s actual behaviour on this specific device tree.**
   The public SM8550 TWRP tree I found
   (`dmXq-twrp-development/android_device_samsung_sm8550-common@android-12.1`)
   sets `TARGET_RECOVERY_QCOM_RTC_FIX := true` but ships **no fstab** in that
   repo, so I could not confirm the `/persist` mount flags (RW vs RO) for this
   device. It does not affect the result either way, since Fixup_Time only
   reads.
4. **Whether the on-device `time_daemon` implements the
   `threshold`/`TIME_GENOFF_UPDATE_THRESHOLD_MS` deferred-write logic.** In both
   public daemon sources that field is dead code (assigned once, never read).
5. **The `persist.delta_time.enable` property consumer.** Present in
   `device.mk` and in real device property dumps, but the code that reads it is
   inside the closed `time_daemon` binary.
6. **The 52-year explanation in §4 is my reconstruction, not a quoted
   mechanism.** I verified the arithmetic (1640995201 s = exactly 18993 days)
   and the TZ-unset ordering from source; I did not find a document stating
   TWRP's `localtime()` fallback zone is `UTC+0`, nor did I trace the pre-Fixup
   kernel clock value on the device. The corrected-time arithmetic (§4) does
   **not** depend on this reconstruction.
7. **Whether any *vendor* Android DTS tree** (out-of-tree `arch/arm64/boot/dts/vendor/qcom/...`)
   declares an `rtc_offset` SDAM cell. Gitiles returns NOT_FOUND for those paths
   in the Android common kernel, so I can neither confirm nor deny it. Only the
   GKI *driver* contents were verified.
8. **TWRP `android-11` vs `android-12.1` branch naming.** The user's suggested
   `twrp-12.1` / `twrp-11.0` branch names do not exist; I used `android-12.1`,
   `android-11`, `android-14.1` and confirmed the function is identical in all
   three.
