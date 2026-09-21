"""Execute panel commands and pinned DRM DSC code on the host against stock data.

Only transport/kernel environment is stubbed. No device is accessed. Requires
clang and the pinned kernel checkout used by scripts/build-kernel.sh.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STOCK = json.loads((ROOT / 'tests/fixtures/x710-panel-commands.json').read_text())


def function(source, name):
    start = source.index(name + '(')
    start = source.rfind('\n', 0, start) + 1
    body = source.index('{', start)
    # These functions have no braces inside string literals.
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def commands(name):
    """Read unconditional vendor commands, including wrapped WT payloads."""
    text = re.sub(r'/\*.*?\*/', '', STOCK['blocks'][name], flags=re.S)
    text = re.sub(r'\n\s+(?=0x)', ' ', text)
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


class PanelX710(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        kernel = Path(os.environ.get('KERNEL_SRC', ROOT / '.work/linux-mainline'))
        if not (kernel / 'include/drm/display/drm_dsc.h').is_file() or not shutil.which('clang'):
            raise unittest.SkipTest('requires pinned kernel checkout and clang')
        pin = subprocess.check_output(['git', '-C', str(kernel), 'rev-parse', 'HEAD'], text=True).strip()
        if pin != 'a13c140cc289c0b7b3770bce5b3ad42ab35074aa':
            raise RuntimeError('DSC comparison requires the pinned upstream kernel')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        header = (kernel / 'include/drm/display/drm_dsc.h').read_text()
        header = header.replace('#include <drm/display/drm_dp.h>', '')
        helper = (kernel / 'drivers/gpu/drm/display/drm_dsc_helper.c').read_text()
        helper = helper[helper.index('void drm_dsc_pps_payload_pack('):helper.index('static void drm_dsc_dump_config_main_params(')]
        host = (kernel / 'drivers/gpu/drm/msm/dsi/dsi_host.c').read_text()
        # The first occurrence is the forward declaration, not the definition.
        host = host[host.index('static int dsi_populate_dsc_params(', host.index('static int dsi_populate_dsc_params(') + 1):]
        panel = (ROOT / 'kernel/drivers/panel-samsung-ana38407.c').read_text()
        template = re.search(r'static const struct drm_dsc_config ana38407_dsc_template = \{.*?\n\};', panel, re.S).group()
        prefix = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <endian.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint16_t __be16;
#define __packed __attribute__((packed))
struct dp_sdp_header { u8 data[4]; };
#define DP_SDP_PPS_HEADER_PAYLOAD_BYTES_MINUS_1 127
#define BUILD_BUG_ON(x) _Static_assert(!(x), "build assertion")
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define DIV_ROUND_UP(n,d) (((n) + (d) - 1) / (d))
#define cpu_to_be16(x) htobe16(x)
#define EXPORT_SYMBOL(x)
static bool host_warn(bool value) { return value; }
#define WARN_ON_ONCE(x) host_warn(x)
#define DRM_DEBUG_KMS(...)
#define DRM_DEV_ERROR(...)
#define DSC_BPG_OFFSET(x) ((u8)((x) & 0x3f))
enum drm_dsc_params_type { DRM_DSC_1_2_444, DRM_DSC_1_1_PRE_SCR,
                         DRM_DSC_1_2_422, DRM_DSC_1_2_420 };
struct msm_dsi_host { int unused; };
'''
        transport = r'''
#define MIPI_DSI_MODE_LPM 1
struct mipi_dsi_device { int dev; unsigned long mode_flags; struct drm_dsc_config *dsc; };
struct mipi_dsi_multi_context { struct mipi_dsi_device *dsi; int accum_err; };
struct ana38407 { struct mipi_dsi_device *dsi; u8 id[3]; char cell_id[23]; u16 user_brightness; };
#define dev_info(...)
#define dev_warn(...)
static int fail_at, writes;
static void emit(struct mipi_dsi_multi_context *ctx, const char *type, const u8 *p, size_t n) {
    if (ctx->accum_err) return;
    if (++writes == fail_at) { ctx->accum_err = -EIO; return; }
    printf("%s", type);
    for (size_t i = 0; i < n; i++) printf(" 0x%02x", p[i]);
    putchar('\n');
}
#define mipi_dsi_dcs_write_seq_multi(ctx, ...) do { \
    static const u8 data[] = { __VA_ARGS__ }; emit(ctx, "w", data, sizeof(data)); \
} while (0)
#define mipi_dsi_dcs_write_var_seq_multi(ctx, ...) do { \
    const u8 data[] = { __VA_ARGS__ }; emit(ctx, "w", data, sizeof(data)); \
} while (0)
static void mipi_dsi_msleep(struct mipi_dsi_multi_context *ctx, unsigned ms) {
    if (!ctx->accum_err) printf("delay %ums\n", ms);
}
static int mipi_dsi_dcs_read(struct mipi_dsi_device *dsi, u8 cmd, void *buf, size_t n) {
    memset(buf, 0, n); if (cmd == 0xda) *(u8 *)buf = 0x80;
    if (cmd == 0xdc) *(u8 *)buf = 0x04;
    return n;
}
static void mipi_dsi_compression_mode_multi(struct mipi_dsi_multi_context *ctx, bool enable) {
    u8 data[] = { enable }; emit(ctx, "wt 0x07", data, sizeof(data));
}
static void mipi_dsi_picture_parameter_set_multi(struct mipi_dsi_multi_context *ctx,
                                               struct drm_dsc_picture_parameter_set *pps) {
    emit(ctx, "wt 0x0a", (const u8 *)pps, sizeof(*pps));
}
'''
        source = prefix + header + helper + function(host, 'dsi_populate_dsc_params') + template + transport
        for name in ('ana38407_slew_boost', 'ana38407_set_120hz', 'ana38407_on'):
            source += function(panel, name) + '\n'
        source += r'''
int main(int argc, char **argv) {
    struct drm_dsc_config dsc = ana38407_dsc_template;
    struct mipi_dsi_device dsi = { .dsc = &dsc };
    struct ana38407 panel = { .dsi = &dsi, .user_brightness = 2047 };
    if (dsi_populate_dsc_params(NULL, &dsc)) return 2;
    fail_at = argc > 1 ? atoi(argv[1]) : 0;
    int ret = ana38407_on(&panel);
    fprintf(stderr, "ret=%d writes=%d\n", ret, writes);
    return ret ? 1 : 0;
}
'''
        c = Path(cls.tmp.name) / 'panel.c'
        cls.exe = Path(cls.tmp.name) / 'panel'
        c.write_text(source)
        subprocess.run(['clang', '-std=gnu11', '-Werror', str(c), '-o', str(cls.exe)],
                       check=True, text=True)
        cls.run_ok = subprocess.run([str(cls.exe)], check=True, capture_output=True, text=True)
        cls.lines = cls.run_ok.stdout.splitlines()

    def test_official_power_and_sync_sequence(self):
        prefix = commands('SLEW_BOOSTING_OFF') + commands('PM_EN_DISP_ON_DELAY') + ['w 0x11', 'delay 50ms']
        self.assertEqual(self.lines[:len(prefix)], prefix)
        sync = sum((commands(n) for n in ('MX_IP_ENABLE', 'TCON_INTR_SETTING', 'TE_ON', 'TSP_SYNC_SETTING')), [])
        self.assertIn('\n'.join(sync), '\n'.join(self.lines))
        suffix = commands('SP_SETTING') + ['delay 20ms'] + commands('SLEW_BOOSTING_ON')
        # Resolve the stock VRR conditions for revision D, 120HS explicitly.
        vrr = ['w 0xf0 0x5a 0x5a', 'w 0xf1 0x5a 0x5a', 'w 0x60 0x00',
               'w 0xb0 0x13 0xdd', 'w 0xdd 0x00', 'w 0xb0 0x10 0xb9',
               'w 0xb9 0x80 0x00 0x00 0x00', 'w 0xf0 0xa5 0xa5', 'w 0xf1 0xa5 0xa5']
        self.assertEqual(self.lines[-len(suffix + vrr):], suffix + vrr)

    def test_pps_matches_official_payload(self):
        stock = next(s for s in commands('DSC_SETTING') if s.startswith('wt 0x0a'))
        expected = bytes(int(x, 16) for x in stock.split()[2:])
        actual = next(s for s in self.lines if s.startswith('wt 0x0a'))
        actual = bytes(int(x, 16) for x in actual.split()[2:])
        self.assertEqual(len(expected), 88)
        self.assertEqual(actual[:len(expected)], expected)
        self.assertEqual(actual[len(expected):], bytes(128 - len(expected)))
        self.assertIn('wt 0x07 0x01', self.lines)

    def test_write_errors_stop_initialisation(self):
        total = int(re.search(r'writes=(\d+)', self.run_ok.stderr)[1])
        for fail_at in (1, total // 2, total):
            with self.subTest(fail_at=fail_at):
                result = subprocess.run([str(self.exe), str(fail_at)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f'ret=-5 writes={fail_at}', result.stderr)
                self.assertEqual(sum(s.startswith(('w ', 'wt ')) for s in result.stdout.splitlines()), fail_at - 1)


if __name__ == '__main__':
    unittest.main()
