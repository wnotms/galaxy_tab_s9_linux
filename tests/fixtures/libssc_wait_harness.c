/* Exercise the real libssc common implementation with real GLib/GIO.
 * No QMI server, ADSP, firmware, kernel, or tablet is accessed.
 */
#include <gio/gio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libssc-common-private.h"

static SyncContext sync_ctx;
static GThread *poll_owner;
static gint polls, zero_polls, foreign_polls, heartbeats;
static gboolean cancelled;
static GTask *completion_result;

static gint counted_poll(GPollFD *fds, guint n, gint timeout)
{
    g_atomic_int_inc(&polls);
    if (!timeout)
        g_atomic_int_inc(&zero_polls);
    if (g_thread_self() != poll_owner)
        g_atomic_int_inc(&foreign_polls);
    return g_poll(fds, n, timeout);
}

static gboolean heartbeat(gpointer data)
{
    heartbeats++;
    return G_SOURCE_CONTINUE;
}

static void complete(void)
{
    /* Complete the waiter with an already produced GAsyncResult. Creating a
     * new GTask here would itself queue a source/wake the default context and
     * hide a missing wakeup in libssc's completion helper. */
    ssc_common_callback_sync_context(NULL, G_ASYNC_RESULT(completion_result), &sync_ctx);
}

static gboolean completion(gpointer data)
{
    complete();
    return G_SOURCE_REMOVE;
}

static gpointer wait_thread(gpointer data)
{
    ssc_common_wait_sync_context(&sync_ctx);
    return NULL;
}

static gpointer completion_thread(gpointer data)
{
    g_usleep(200000);
    complete();
    return NULL;
}

static void report(void)
{
    printf("{\"polls\":%d,\"zero_polls\":%d,\"foreign_polls\":%d,"
           "\"heartbeats\":%d,\"finished\":%s}\n",
           polls, zero_polls, foreign_polls, heartbeats,
           sync_ctx.finished ? "true" : "false");
    fflush(stdout);
}

static gboolean unanswered_stop(gpointer data)
{
    /* A fixture deadline, not a new timeout in the libssc implementation. */
    report();
    exit(0);
}

int main(int argc, char **argv)
{
    GMainContext *context = g_main_context_default();
    GThread *thread = NULL;
    GError *error = NULL;
    guint tick = 0;
    gboolean okay;
    const char *mode;
    if (argc != 2)
        return 2;
    mode = argv[1];
    poll_owner = g_thread_self();
    g_main_context_set_poll_func(context, counted_poll);
    ssc_common_init_sync_context(&sync_ctx);
    cancelled = !strcmp(mode, "cancelled");
    completion_result = g_task_new(NULL, NULL, NULL, NULL);
    if (cancelled)
        g_task_return_new_error(completion_result, G_IO_ERROR, G_IO_ERROR_CANCELLED, "test cancellation");
    else
        g_task_return_boolean(completion_result, TRUE);

    if (!strcmp(mode, "already")) {
        complete();
        ssc_common_wait_sync_context(&sync_ctx);
    } else if (!strcmp(mode, "foreign-owner")) {
        g_assert_true(g_main_context_acquire(context));
        thread = g_thread_new("waiter", wait_thread, NULL);
        g_timeout_add(200, completion, NULL);
        while (!sync_ctx.finished)
            g_main_context_iteration(context, TRUE);
        g_thread_join(thread);
        g_main_context_release(context);
    } else if (!strcmp(mode, "foreign-completion")) {
        thread = g_thread_new("completion", completion_thread, NULL);
        ssc_common_wait_sync_context(&sync_ctx);
        g_thread_join(thread);
    } else if (!strcmp(mode, "owner") || cancelled || !strcmp(mode, "unanswered")) {
        tick = g_timeout_add(40, heartbeat, NULL);
        g_timeout_add(200, !strcmp(mode, "unanswered") ? unanswered_stop : completion, NULL);
        ssc_common_wait_sync_context(&sync_ctx);
    } else {
        return 2;
    }
    if (tick)
        g_source_remove(tick);
    okay = g_task_propagate_boolean(G_TASK(sync_ctx.result), &error);
    if (cancelled) {
        g_assert_false(okay);
        g_assert_error(error, G_IO_ERROR, G_IO_ERROR_CANCELLED);
        g_clear_error(&error);
    } else {
        g_assert_true(okay);
        g_assert_no_error(error);
    }
    report();
    ssc_common_clear_sync_context(&sync_ctx);
    g_object_unref(completion_result);
    return 0;
}
