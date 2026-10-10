/* Real proxy lifecycle and D-Bus handlers; mocked sensor I/O and authorization.
 * Only a private test bus is used. GUdev identity/location and sensor I/O
 * are synthetic; actual discovery hardware is not under test.
 */
#include <gio/gio.h>
#include <gudev/gudev.h>
#include <polkit/polkit.h>
static GList *fixture_query(GUdevClient *client, const gchar *subsystem);
static const gchar *fixture_sysfs_path(GUdevDevice *device);
static PolkitAuthorizationResult *fixture_auth(PolkitAuthority *authority,
    PolkitSubject *subject, const gchar *action_id, PolkitDetails *details,
    PolkitCheckAuthorizationFlags flags, GCancellable *cancellable, GError **error);
#define g_udev_client_query_by_subsystem fixture_query
#define g_udev_device_get_sysfs_path fixture_sysfs_path
#define setup_accel_location fixture_accel_location
#define polkit_authority_check_authorization_sync fixture_auth
#define main unused_proxy_main
#include "iio-sensor-proxy.c"
#undef main
#undef polkit_authority_check_authorization_sync
#undef g_udev_client_query_by_subsystem
#undef g_udev_device_get_sysfs_path
#undef setup_accel_location

static SensorData *state;
static GDBusConnection *server, *client;
static const gchar *mode;
static guint starts, stops, opens, availability_events;
static gboolean nested_claim_done;
typedef struct { gboolean done; GError *error; } Reply;

static void reply_done(GObject *object, GAsyncResult *result, gpointer pointer)
{
    Reply *reply = pointer;
    GVariant *value = g_dbus_connection_call_finish(G_DBUS_CONNECTION(object), result, &reply->error);
    if (value) g_variant_unref(value);
    reply->done = TRUE;
}

static void pump_reply(Reply *reply)
{
    gint64 until = g_get_monotonic_time() + 2000000;
    while (!reply->done && g_get_monotonic_time() < until) {
        g_main_context_iteration(NULL, FALSE);
        g_usleep(1000);
    }
    g_assert_true(reply->done);
    g_assert_no_error(reply->error);
}

static void call(GDBusConnection *connection, const gchar *method, Reply *reply)
{
    g_dbus_connection_call(connection, g_dbus_connection_get_unique_name(server),
        SENSOR_PROXY_DBUS_PATH, SENSOR_PROXY_IFACE_NAME, method, NULL, NULL,
        G_DBUS_CALL_FLAGS_NONE, 2000, NULL, reply_done, reply);
}

static GList *fixture_query(GUdevClient *udev, const gchar *subsystem)
{
    GUdevDevice *device;
    if (strcmp(subsystem, "misc")) return NULL;
    device = g_object_new(G_UDEV_TYPE_DEVICE, NULL);
    g_assert_nonnull(device);
    return g_list_append(NULL, device);
}

static const gchar *fixture_sysfs_path(GUdevDevice *device)
{
    return "/synthetic/ssc";
}

AccelLocation fixture_accel_location(GUdevDevice *device)
{
    return ACCEL_LOCATION_DISPLAY;
}

static PolkitAuthorizationResult *fixture_auth(PolkitAuthority *authority,
    PolkitSubject *subject, const gchar *action_id, PolkitDetails *details,
    PolkitCheckAuthorizationFlags flags, GCancellable *cancellable, GError **error)
{
    return polkit_authorization_result_new(TRUE, FALSE, NULL);
}

static gboolean skip(GUdevDevice *device) { return FALSE; }
static gboolean discover(GUdevDevice *device) { return TRUE; }

static void nested_claim(void)
{
    Reply claim = {0}, release = {0};
    if (nested_claim_done) return;
    nested_claim_done = TRUE;
    call(client, "ClaimAccelerometer", &claim);
    pump_reply(&claim);
    g_assert_cmpuint(g_hash_table_size(state->clients[DRIVER_TYPE_ACCEL]), ==, 1);
    if (!strcmp(mode, "release-before-open")) {
        call(client, "ReleaseAccelerometer", &release);
        pump_reply(&release);
        g_assert_cmpuint(g_hash_table_size(state->clients[DRIVER_TYPE_ACCEL]), ==, 0);
    }
    if (!strcmp(mode, "vanish-before-open")) {
        GError *error = NULL;
        gint64 until = g_get_monotonic_time() + 2000000;
        g_dbus_connection_close_sync(client, NULL, &error);
        g_assert_no_error(error);
        while (g_hash_table_size(state->clients[DRIVER_TYPE_ACCEL]) &&
               g_get_monotonic_time() < until) {
            g_main_context_iteration(NULL, FALSE);
            g_usleep(1000);
        }
        g_assert_cmpuint(g_hash_table_size(state->clients[DRIVER_TYPE_ACCEL]), ==, 0);
    }
}

static gboolean after_discovery(GUdevDevice *device)
{
    if (!strcmp(mode, "during-discovery") || !strcmp(mode, "release-before-open") ||
        !strcmp(mode, "vanish-before-open")) nested_claim();
    return FALSE;
}

static SensorDevice *open_sensor(GUdevDevice *device)
{
    SensorDevice *sensor;
    opens++;
    if (!strcmp(mode, "during-open")) nested_claim();
    if (!strcmp(mode, "open-failure")) return NULL;
    sensor = g_new0(SensorDevice, 1);
    sensor->name = g_strdup("synthetic-accelerometer");
    return sensor;
}

static void polling(SensorDevice *sensor, gboolean enabled)
{
    g_assert_nonnull(sensor);
    if (enabled) starts++; else stops++;
}

static void close_sensor(SensorDevice *sensor) { g_free(sensor); }
#define IGNORE_DRIVER(symbol, kind) SensorDriver symbol = { .driver_name = #symbol, .type = kind, .discover = skip }
IGNORE_DRIVER(iio_buffer_accel, DRIVER_TYPE_ACCEL);
IGNORE_DRIVER(iio_poll_accel, DRIVER_TYPE_ACCEL);
IGNORE_DRIVER(input_accel, DRIVER_TYPE_ACCEL);
IGNORE_DRIVER(iio_buffer_light, DRIVER_TYPE_LIGHT);
IGNORE_DRIVER(iio_poll_light, DRIVER_TYPE_LIGHT);
IGNORE_DRIVER(hwmon_light, DRIVER_TYPE_LIGHT);
IGNORE_DRIVER(fake_compass, DRIVER_TYPE_COMPASS);
IGNORE_DRIVER(fake_light, DRIVER_TYPE_LIGHT);
IGNORE_DRIVER(iio_buffer_compass, DRIVER_TYPE_COMPASS);
IGNORE_DRIVER(iio_poll_proximity, DRIVER_TYPE_PROXIMITY);
IGNORE_DRIVER(input_proximity, DRIVER_TYPE_PROXIMITY);
IGNORE_DRIVER(ssc_proximity, DRIVER_TYPE_PROXIMITY);
IGNORE_DRIVER(ssc_light, DRIVER_TYPE_LIGHT);
SensorDriver ssc_accel = { "synthetic-accel", DRIVER_TYPE_ACCEL, discover, open_sensor, polling, close_sensor };
SensorDriver ssc_compass = { .driver_name = "after-discovery-hook", .type = DRIVER_TYPE_COMPASS, .discover = after_discovery };

static void properties_changed(GDBusConnection *connection, const gchar *sender,
    const gchar *path, const gchar *interface, const gchar *signal,
    GVariant *parameters, gpointer data)
{
    GVariant *changed, *invalidated;
    gboolean has_accel = FALSE;
    g_variant_get(parameters, "(&s@a{sv}@as)", &interface, &changed, &invalidated);
    if (g_variant_lookup(changed, "HasAccelerometer", "b", &has_accel) && has_accel)
        availability_events++;
    g_variant_unref(changed);
    g_variant_unref(invalidated);
}

static GDBusConnection *connect_bus(const gchar *address)
{
    GError *error = NULL;
    GDBusConnection *connection = g_dbus_connection_new_for_address_sync(address,
        G_DBUS_CONNECTION_FLAGS_AUTHENTICATION_CLIENT | G_DBUS_CONNECTION_FLAGS_MESSAGE_BUS_CONNECTION,
        NULL, NULL, &error);
    g_assert_no_error(error);
    g_assert_nonnull(connection);
    return connection;
}

static void measurement(void)
{
    AccelReadings reading = { .accel_x = 0, .accel_y = -981, .accel_z = 0,
        .scale = { .x = 0.01, .y = 0.01, .z = 0.01 } };
    SensorDevice *sensor = state->devices[DRIVER_TYPE_ACCEL];
    g_assert_nonnull(sensor);
    sensor->callback_func(sensor, &reading, sensor->user_data);
}

int main(int argc, char **argv)
{
    GBytes *xml;
    GError *error = NULL;
    guint subscription;
    gint64 until;
    if (argc != 3) return 2;
    mode = argv[2];
    server = connect_bus(argv[1]); client = connect_bus(argv[1]);
    state = g_new0(SensorData, 1);
    state->loop = g_main_loop_new(NULL, FALSE);
    xml = g_resources_lookup_data("/net/hadess/SensorProxy/net.hadess.SensorProxy.xml", 0, &error);
    g_assert_no_error(error);
    state->introspection_data = g_dbus_node_info_new_for_xml(g_bytes_get_data(xml, NULL), &error);
    g_assert_no_error(error); g_bytes_unref(xml);
    subscription = g_dbus_connection_signal_subscribe(client, g_dbus_connection_get_unique_name(server),
        "org.freedesktop.DBus.Properties", "PropertiesChanged", SENSOR_PROXY_DBUS_PATH,
        NULL, 0, properties_changed, NULL, NULL);
    /* Barrier on the same client connection: AddMatch is processed before the
     * server publishes availability, even when no client claims the device. */
    {
        GVariant *id = g_dbus_connection_call_sync(client, "org.freedesktop.DBus",
            "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetId", NULL, NULL,
            0, 2000, NULL, &error);
        g_assert_no_error(error); g_assert_nonnull(id); g_variant_unref(id);
    }
    bus_acquired_handler(server, SENSOR_PROXY_DBUS_NAME, state);
    if (!strcmp(mode, "before-discovery")) nested_claim();
    name_acquired_handler(server, SENSOR_PROXY_DBUS_NAME, state);
    g_assert_cmpuint(opens, ==, 1);
    if (!strcmp(mode, "open-failure")) {
        g_assert_null(state->devices[0]); g_assert_null(state->drivers[0]);
        g_assert_cmpuint(starts, ==, 0);
    } else if (!strcmp(mode, "no-clients") || !strcmp(mode, "release-before-open") ||
               !strcmp(mode, "vanish-before-open")) {
        g_assert_cmpuint(starts, ==, 0);
        g_assert_cmpuint(stops, ==, 0);
    } else if (!strcmp(mode, "after-open")) {
        Reply claim = {0};
        call(client, "ClaimAccelerometer", &claim);
        until = g_get_monotonic_time() + 2000000;
        while (!state->sensor_startup_dbus_invocations_delayed[0]->len &&
               g_get_monotonic_time() < until) {
            g_main_context_iteration(NULL, FALSE); g_usleep(1000);
        }
        g_assert_false(claim.done);
        g_assert_cmpuint(starts, ==, 1);
        measurement(); pump_reply(&claim);
    } else {
        Reply duplicate = {0};
        g_assert_true(nested_claim_done);
        g_assert_cmpuint(starts, ==, 1);
        call(client, "ClaimAccelerometer", &duplicate); pump_reply(&duplicate);
        g_assert_cmpuint(starts, ==, 1);
        measurement();
        g_assert_false(state->sensor_startup_dbus_event_delayed[0]);
    }
    if (strcmp(mode, "open-failure") && strcmp(mode, "vanish-before-open")) {
        until = g_get_monotonic_time() + 2000000;
        while (!availability_events && g_get_monotonic_time() < until) {
            g_main_context_iteration(NULL, FALSE); g_usleep(1000);
        }
        g_assert_cmpuint(availability_events, >, 0);
    }
    printf("{\"case\":\"%s\",\"starts\":%u,\"stops\":%u,\"opens\":%u,\"availability_events\":%u}\n",
        mode, starts, stops, opens, availability_events);
    g_dbus_connection_signal_unsubscribe(client, subscription);
    free_sensor_data(state);
    g_object_unref(client); g_object_unref(server);
    return 0;
}
