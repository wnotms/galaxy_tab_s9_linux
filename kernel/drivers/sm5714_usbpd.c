// SPDX-License-Identifier: GPL-2.0-only
/*
 * SM-X710 SM5714 TCPC transport, fixed 5/9 V Sink + Device only.
 *
 * Register provenance: Samsung X710 GPL sm5714_typec.c/.h, and same-model
 * nacht20-de/gts9wifi-fedora-linux ab123e7d, kernel/files/sm5714_usbpd.c.
 * See docs/SM5714_STAGE2_PD_PLAN.md and Test255 SOURCE_AUDIT for each sequence.
 * Stock Linux TCPM owns policy. No private policy, boost, role-swap quirk,
 * alternate-mode, direct-charger or programmable-supply implementation.
 */
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/property.h>
#include <linux/regmap.h>
#include <linux/usb/pd.h>
#include <linux/usb/tcpm.h>
#include <linux/workqueue.h>

#include "sm5714-stage2.h"
#include "sm5714-pd-policy.h"

/* Samsung sm5714_typec.h register map and interrupt bit definitions. */
#define SM5714_REG_INT1		0x01
#define SM5714_REG_MASK1		0x06
#define SM5714_REG_STATUS1	0x0b
#define SM5714_VBUS_POK		BIT(0)
#define SM5714_ATTACH		BIT(3)
#define SM5714_DETACH		BIT(4)
#define SM5714_SRC_ADV		BIT(4)
#define SM5714_VBUS_0V		BIT(5)
#define SM5714_RX_DONE		BIT(0)
#define SM5714_TX_DONE		BIT(1)
#define SM5714_TX_ERR		BIT(2)
#define SM5714_HRST_RX		BIT(5)
#define SM5714_HRST_DONE		BIT(6)
#define SM5714_TX_DISCARD		BIT(7)
#define SM5714_REG_CORR_CNTL4	0x23
#define SM5714_REG_CORR_CNTL5	0x24
#define SM5714_REG_CC_STATUS	0x28
#define SM5714_CC_ATTACH_MASK	GENMASK(2, 0)
#define SM5714_CC_SOURCE		1 /* partner is Source, local port is Sink */
#define SM5714_CC_RP_MASK		GENMASK(4, 3)
#define SM5714_CC_FLIPPED		BIT(5)
#define SM5714_REG_CC_CNTL1	0x29
#define SM5714_REG_CC_CNTL3	0x2b
#define SM5714_REG_CC_CNTL5	0x2d
#define SM5714_REG_PD_CNTL1	0x38
#define SM5714_REG_PD_CNTL2	0x39
#define SM5714_REG_PD_CNTL4	0x3b
#define SM5714_REG_RX_SRC		0x41
#define SM5714_REG_RX_HEADER	0x42
#define SM5714_REG_RX_PAYLOAD	0x44
#define SM5714_REG_RX_BUF		0x5e
#define SM5714_REG_RX_BUF_ST	0x5f
#define SM5714_REG_TX_HEADER	0x60
#define SM5714_REG_TX_PAYLOAD	0x62
#define SM5714_REG_TX_REQ		0x7e
#define SM5714_REG_PD_STATE3	0xd8

struct sm5714_usbpd {
	struct device *dev;
	struct regmap *regmap;
	struct mutex lock;
	struct tcpc_dev tcpc;
	struct tcpm_port *port;
	struct fwnode_handle *connector;
	struct delayed_work cc_resync_work;
	u32 source_pdos[PD_MAX_PAYLOAD];
	unsigned int nr_source_pdos;
	u64 source_generation;
	int irq;
	bool fault;
	bool removing;
};

static const struct regmap_config sm5714_regmap_config = {
	.reg_bits = 8,
	.val_bits = 8,
	.max_register = 0xff,
	.cache_type = REGCACHE_NONE,
};

static struct sm5714_usbpd *tcpc_to_sm5714(struct tcpc_dev *tcpc)
{
	return container_of(tcpc, struct sm5714_usbpd, tcpc);
}

/* Transport lock protects both the cache and its lifetime. No old offer may
 * authorize a Request after reset, fault, detach, or a new source publication.
 */
static void sm5714_forget_source(struct sm5714_usbpd *sm)
{
	lockdep_assert_held(&sm->lock);
	memset(sm->source_pdos, 0, sizeof(sm->source_pdos));
	sm->nr_source_pdos = 0;
	sm->source_generation++;
}

/* No bus retry/reset loop: first transport failure latches charger off. */
static int sm5714_result(struct sm5714_usbpd *sm, int ret)
{
	bool first;

	if (ret < 0) {
		mutex_lock(&sm->lock);
		first = !sm->fault;
		sm->fault = true;
		sm5714_forget_source(sm);
		mutex_unlock(&sm->lock);
		if (first) {
			sm5714_battery_typec_fault();
			dev_err(sm->dev, "TCPC fault %d; switching charge inhibited\n", ret);
		}
	}
	return ret;
}

static int sm5714_usbpd_init(struct tcpc_dev *tcpc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	/* Fedora same-model masks; read INT1..5 clears edge latches (Samsung). */
	static const u8 masks[5] = { 0xe6, 0xcf, 0xff, 0x08, 0xff };
	unsigned int state;
	u8 pending[5];
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	mutex_lock(&sm->lock);
	sm5714_forget_source(sm);
	/* Fedora/Samsung normal (non water-detection) CORR initialization. */
	ret = regmap_write(sm->regmap, SM5714_REG_CORR_CNTL5, 0x00);
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CORR_CNTL4, 0x00);
	if (!ret)
		ret = regmap_read(sm->regmap, SM5714_REG_PD_STATE3, &state);
	/* Samsung protocol-layer RX flush; Fedora/Samsung retained ResetDone ack. */
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_RX_BUF_ST, 0x10);
	if (!ret && (state & 0x06))
		ret = regmap_write(sm->regmap, SM5714_REG_PD_CNTL4, 0x01);
	/* Samsung set_vconn_source(OFF) and set_snk/set_ufp: preserve other bits. */
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL5, 0x18);
	if (!ret)
		ret = regmap_update_bits(sm->regmap, SM5714_REG_PD_CNTL2,
					 GENMASK(1, 0), 0);
	/* Force Rd, not autonomous DRP; Samsung sm5714_set_attach(UFP). */
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL1, 0x45);
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL3, 0x82);
	if (!ret)
		ret = regmap_bulk_read(sm->regmap, SM5714_REG_INT1,
				       pending, sizeof(pending));
	if (!ret)
		ret = regmap_bulk_write(sm->regmap, SM5714_REG_MASK1,
					masks, sizeof(masks));
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_get_vbus(struct tcpc_dev *tcpc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	unsigned int status;
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	ret = regmap_read(sm->regmap, SM5714_REG_STATUS1, &status);
	return ret ? sm5714_result(sm, ret) : !!(status & SM5714_VBUS_POK);
}

static int sm5714_usbpd_get_current_limit(struct tcpc_dev *tcpc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	/* TCPM calls this for default Rp; retain Stage1 BC1.2 SDP/CDP/DCP. */
	ret = sm5714_battery_get_bc12_limit();
	return ret < 0 ? sm5714_result(sm, ret) : ret;
}

static int sm5714_usbpd_get_cc(struct tcpc_dev *tcpc,
			      enum typec_cc_status *cc1, enum typec_cc_status *cc2)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	enum typec_cc_status active = TYPEC_CC_OPEN;
	unsigned int cc;
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	ret = regmap_read(sm->regmap, SM5714_REG_CC_STATUS, &cc);
	if (ret)
		return sm5714_result(sm, ret);
	/* Samsung CC_STATUS: only a Source partner is accepted by this Sink. */
	if ((cc & SM5714_CC_ATTACH_MASK) == SM5714_CC_SOURCE) {
		switch (cc & SM5714_CC_RP_MASK) {
		case 0x08: active = TYPEC_CC_RP_1_5; break;
		case 0x10:
		case 0x18: active = TYPEC_CC_RP_3_0; break;
		default: active = TYPEC_CC_RP_DEF; break;
		}
	}
	*cc1 = cc & SM5714_CC_FLIPPED ? TYPEC_CC_OPEN : active;
	*cc2 = cc & SM5714_CC_FLIPPED ? active : TYPEC_CC_OPEN;
	return 0;
}

static int sm5714_usbpd_set_cc(struct tcpc_dev *tcpc, enum typec_cc_status cc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	if (cc != TYPEC_CC_OPEN && cc != TYPEC_CC_RD)
		return -EOPNOTSUPP;
	mutex_lock(&sm->lock);
	/* Samsung force-detach=0x88, force UFP=0x45/0x82; no Rp writes. */
	if (cc == TYPEC_CC_OPEN) {
		sm5714_forget_source(sm);
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL3, 0x88);
	} else {
		ret = regmap_update_bits(sm->regmap, SM5714_REG_CC_CNTL1,
					 0xff, 0x45);
		if (!ret)
			ret = regmap_update_bits(sm->regmap, SM5714_REG_CC_CNTL3,
						 0xff, 0x82);
	}
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_set_polarity(struct tcpc_dev *tcpc,
				    enum typec_cc_polarity polarity)
{
	/* Fedora: CC_STATUS selects hardware PD lane; no external mux required. */
	return READ_ONCE(tcpc_to_sm5714(tcpc)->fault) ? -EIO : 0;
}

static int sm5714_usbpd_set_vconn(struct tcpc_dev *tcpc, bool on)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);

	if (on)
		return -EOPNOTSUPP;
	if (READ_ONCE(sm->fault))
		return -EIO;
	/* Samsung OFF=0x18; no source VCONN or cable discovery is implemented. */
	return sm5714_result(sm, regmap_write(sm->regmap,
					    SM5714_REG_CC_CNTL5, 0x18));
}

static int sm5714_usbpd_set_vbus(struct tcpc_dev *tcpc, bool on, bool charge)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);

	if (on)
		return -EOPNOTSUPP;
	if (READ_ONCE(sm->removing))
		return charge ? -ESHUTDOWN : 0;
	if (READ_ONCE(sm->fault) && charge)
		return -EIO;
	/* Required by TCPM: apply Sink charge gate, never generate VBUS. */
	return sm5714_result(sm, sm5714_battery_set_typec_charge(charge));
}

static int sm5714_usbpd_set_current_limit(struct tcpc_dev *tcpc, u32 ma, u32 mv)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	ret = sm5714_battery_set_pd_contract(mv, ma);
	if (!ret)
		dev_info(sm->dev, "TCPM Sink budget: %u mV %u mA (not measured VBUS)\n",
			 mv, ma);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_set_pd_rx(struct tcpc_dev *tcpc, bool on)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	/* Samsung set_pd_control(): ordinary SOP receive=0x08, off=0x00. */
	mutex_lock(&sm->lock);
	if (!on)
		sm5714_forget_source(sm);
	ret = regmap_write(sm->regmap, SM5714_REG_PD_CNTL1, on ? 0x08 : 0x00);
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_set_roles(struct tcpc_dev *tcpc, bool attached,
				 enum typec_role role, enum typec_data_role data)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);

	if (role != TYPEC_SINK || data != TYPEC_DEVICE)
		return -EOPNOTSUPP;
	if (READ_ONCE(sm->fault))
		return -EIO;
	/* Samsung set_snk/set_ufp: role bits1:0; DWC3 stays peripheral. */
	return sm5714_result(sm, regmap_update_bits(sm->regmap,
						 SM5714_REG_PD_CNTL2, GENMASK(1, 0), 0));
}

/* Guard the actual Request frame without choosing a PDO or changing policy. */
static bool sm5714_request_allowed(struct sm5714_usbpd *sm, u32 rdo)
{
	/* PPS validator is host-tested separately. Until a reviewed live handoff
	 * gate exists the actual transport accepts fixed offers only.
	 */
	return sm5714_validate_request(sm->source_pdos, sm->nr_source_pdos, rdo, false);
}

static int sm5714_usbpd_transmit(struct tcpc_dev *tcpc,
			       enum tcpm_transmit_type type, const struct pd_message *msg,
			       unsigned int negotiated_rev)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	unsigned int count;
	int ret = 0;

	if (READ_ONCE(sm->fault))
		return -EIO;
	if (type != TCPC_TX_SOP && type != TCPC_TX_HARD_RESET)
		return -EOPNOTSUPP;
	mutex_lock(&sm->lock);
	if (type == TCPC_TX_HARD_RESET) {
		/* Samsung hard_reset(): PD_CNTL4 bit2; IRQ HCRST_DONE completes TX. */
		sm5714_forget_source(sm);
		ret = regmap_update_bits(sm->regmap, SM5714_REG_PD_CNTL4, BIT(2), BIT(2));
		goto out;
	}
	if (!msg) {
		ret = -EINVAL;
		goto out;
	}
	count = pd_header_cnt_le(msg->header);
	/* This driver has no extended-message transport or EPR implementation.
	 * Type2/count0 is Get_Source_Cap control, not a malformed Request.
	 */
	if (le16_to_cpu(msg->header) & PD_HEADER_EXT_HDR) {
		ret = -EOPNOTSUPP;
		goto out;
	}
	if (!count && pd_header_type_le(msg->header) == PD_CTRL_SOFT_RESET)
		sm5714_forget_source(sm);
	if (pd_header_type_le(msg->header) == PD_DATA_REQUEST && count &&
	    (count != 1 || !sm5714_request_allowed(sm, le32_to_cpu(msg->payload[0])))) {
		ret = -ERANGE;
		goto out;
	}
	/* Samsung write_msg_header/obj/send_msg: little-endian header/payload. */
	ret = regmap_bulk_write(sm->regmap, SM5714_REG_TX_HEADER,
				&msg->header, sizeof(msg->header));
	if (!ret && count)
		ret = regmap_bulk_write(sm->regmap, SM5714_REG_TX_PAYLOAD,
					msg->payload, count * sizeof(msg->payload[0]));
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_TX_REQ, 0x07); /* SOP only */
out:
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

/* Called under transport lock. Deliver only a completely read SOP frame. */
static int sm5714_usbpd_receive(struct sm5714_usbpd *sm)
{
	struct pd_message msg = {};
	unsigned int count, origin, i;
	int ret, ack;

	ret = regmap_bulk_read(sm->regmap, SM5714_REG_RX_HEADER,
			       &msg.header, sizeof(msg.header));
	if (ret)
		goto acknowledge;
	count = pd_header_cnt_le(msg.header);
	if (count) {
		ret = regmap_bulk_read(sm->regmap, SM5714_REG_RX_PAYLOAD,
				       msg.payload, count * sizeof(msg.payload[0]));
		if (ret)
			goto acknowledge;
	}
	ret = regmap_read(sm->regmap, SM5714_REG_RX_SRC, &origin);
	if (ret)
		goto acknowledge;
	/* Samsung RX_SRC low nibble0=SOP; no cable/alternate-mode transport. */
	if (!(origin & 0x0f)) {
		if (!count && pd_header_type_le(msg.header) == PD_CTRL_SOFT_RESET)
			sm5714_forget_source(sm);
		if (count && !(le16_to_cpu(msg.header) & PD_HEADER_EXT_HDR) &&
		    pd_header_type_le(msg.header) == PD_DATA_SOURCE_CAP) {
			sm5714_forget_source(sm);
			sm->nr_source_pdos = count;
			for (i = 0; i < count; i++)
				sm->source_pdos[i] = le32_to_cpu(msg.payload[i]);
		}
		tcpm_pd_receive(sm->port, &msg, TCPC_TX_SOP);
	}
acknowledge:
	/* Samsung receive_message(): RX_BUF=0x80 marks message consumed. */
	ack = regmap_write(sm->regmap, SM5714_REG_RX_BUF, 0x80);
	return ret ? ret : ack;
}

static irqreturn_t sm5714_usbpd_irq(int irq, void *data)
{
	struct sm5714_usbpd *sm = data;
	u8 intr[5];
	int ret;

	if (READ_ONCE(sm->removing))
		return IRQ_HANDLED;
	mutex_lock(&sm->lock);
	ret = regmap_bulk_read(sm->regmap, SM5714_REG_INT1, intr, sizeof(intr));
	if (!ret && (intr[0] & (SM5714_ATTACH | SM5714_DETACH) ||
		     intr[3] & (SM5714_HRST_RX | SM5714_HRST_DONE)))
		sm5714_forget_source(sm);
	if (!ret && (intr[3] & SM5714_RX_DONE)) {
		/* Detach/reset may share an IRQ with a buffered old frame. Drain it
		 * without publishing capabilities or delivering it to the new epoch.
		 */
		if (intr[0] & SM5714_DETACH ||
		    intr[3] & (SM5714_HRST_RX | SM5714_HRST_DONE))
			ret = regmap_write(sm->regmap, SM5714_REG_RX_BUF, 0x80);
		else
			ret = sm5714_usbpd_receive(sm);
	}
	if (!ret) {
		/* Hard-reset completion is also a TX completion, not a timeout. */
		if (intr[3] & SM5714_TX_ERR)
			tcpm_pd_transmit_complete(sm->port, TCPC_TX_FAILED);
		else if (intr[3] & SM5714_TX_DISCARD)
			tcpm_pd_transmit_complete(sm->port, TCPC_TX_DISCARDED);
		else if (intr[3] & (SM5714_TX_DONE | SM5714_HRST_DONE))
			tcpm_pd_transmit_complete(sm->port, TCPC_TX_SUCCESS);
		if (intr[3] & SM5714_HRST_RX) {
			tcpm_pd_hard_reset(sm->port);
		}
	}
	mutex_unlock(&sm->lock);
	if (ret) {
		/* Level-low IRQ plus failed clear must not form an interrupt storm. */
		disable_irq_nosync(irq);
		sm5714_result(sm, ret);
		return IRQ_HANDLED;
	}
	if (intr[0] & (SM5714_ATTACH | SM5714_DETACH) || intr[1] & SM5714_SRC_ADV)
		tcpm_cc_change(sm->port);
	if (intr[0] & SM5714_VBUS_POK || intr[1] & SM5714_VBUS_0V)
		tcpm_vbus_change(sm->port);
	return IRQ_HANDLED;
}

static void sm5714_usbpd_resync(struct work_struct *work)
{
	struct sm5714_usbpd *sm = container_of(to_delayed_work(work),
						     struct sm5714_usbpd, cc_resync_work);

	/* Fedora one-shot1.5s resync covers a pre-registration attach edge. */
	if (!READ_ONCE(sm->fault) && !READ_ONCE(sm->removing)) {
		tcpm_cc_change(sm->port);
		tcpm_vbus_change(sm->port);
	}
}

static int sm5714_usbpd_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct sm5714_usbpd *sm;
	const u8 masked[5] = { 0xff, 0xff, 0xff, 0xff, 0xff };
	int ret;

	if (client->irq <= 0)
		return -EINVAL;
	sm = devm_kzalloc(dev, sizeof(*sm), GFP_KERNEL);
	if (!sm)
		return -ENOMEM;
	sm->dev = dev;
	sm->irq = client->irq;
	sm->regmap = devm_regmap_init_i2c(client, &sm5714_regmap_config);
	if (IS_ERR(sm->regmap))
		return PTR_ERR(sm->regmap);
	mutex_init(&sm->lock);
	INIT_DELAYED_WORK(&sm->cc_resync_work, sm5714_usbpd_resync);
	i2c_set_clientdata(client, sm);
	sm->connector = device_get_named_child_node(dev, "connector");
	if (!sm->connector)
		return -EINVAL;
	ret = sm5714_battery_typec_claim();
	if (ret)
		goto put_connector;
	ret = regmap_bulk_write(sm->regmap, SM5714_REG_MASK1, masked, sizeof(masked));
	if (ret)
		goto fault;
	/* Request before unmask, but enable only after a live TCPM port exists. */
	ret = devm_request_threaded_irq(dev, client->irq, NULL, sm5714_usbpd_irq,
				       IRQF_ONESHOT | IRQF_TRIGGER_LOW | IRQF_NO_AUTOEN,
				       dev_name(dev), sm);
	if (ret)
		goto fault;
	sm->tcpc.fwnode = sm->connector;
	sm->tcpc.init = sm5714_usbpd_init;
	sm->tcpc.get_vbus = sm5714_usbpd_get_vbus;
	sm->tcpc.get_current_limit = sm5714_usbpd_get_current_limit;
	sm->tcpc.get_cc = sm5714_usbpd_get_cc;
	sm->tcpc.set_cc = sm5714_usbpd_set_cc;
	sm->tcpc.set_polarity = sm5714_usbpd_set_polarity;
	sm->tcpc.set_vconn = sm5714_usbpd_set_vconn;
	sm->tcpc.set_vbus = sm5714_usbpd_set_vbus;
	sm->tcpc.set_current_limit = sm5714_usbpd_set_current_limit;
	sm->tcpc.set_pd_rx = sm5714_usbpd_set_pd_rx;
	sm->tcpc.set_roles = sm5714_usbpd_set_roles;
	sm->tcpc.pd_transmit = sm5714_usbpd_transmit;
	/* TCPM7.2 ignores init's return: check explicitly before registering. */
	ret = sm5714_usbpd_init(&sm->tcpc);
	if (ret)
		goto fault;
	sm->port = tcpm_register_port(dev, &sm->tcpc);
	if (IS_ERR(sm->port)) {
		ret = PTR_ERR(sm->port);
		goto fault;
	}
	if (READ_ONCE(sm->fault)) {
		ret = -EIO;
		tcpm_unregister_port(sm->port);
		goto fault;
	}
	enable_irq(client->irq);
	mod_delayed_work(system_dfl_wq, &sm->cc_resync_work, msecs_to_jiffies(1500));
	dev_info(dev, "SM-X710 fixed5/9V Sink/Device TCPC registered\n");
	return 0;
fault:
	sm5714_result(sm, ret);
put_connector:
	fwnode_handle_put(sm->connector);
	return dev_err_probe(dev, ret, "cannot register fixed-PD Sink\n");
}

static void sm5714_usbpd_remove(struct i2c_client *client)
{
	struct sm5714_usbpd *sm = i2c_get_clientdata(client);

	WRITE_ONCE(sm->removing, true);
	disable_irq(client->irq);
	cancel_delayed_work_sync(&sm->cc_resync_work);
	WRITE_ONCE(sm->fault, true);
	mutex_lock(&sm->lock);
	sm5714_forget_source(sm);
	mutex_unlock(&sm->lock);
	sm5714_battery_typec_fault();
	tcpm_unregister_port(sm->port);
	fwnode_handle_put(sm->connector);
}

static void sm5714_usbpd_shutdown(struct i2c_client *client)
{
	struct sm5714_usbpd *sm = i2c_get_clientdata(client);

	WRITE_ONCE(sm->removing, true);
	disable_irq(client->irq);
	cancel_delayed_work_sync(&sm->cc_resync_work);
	WRITE_ONCE(sm->fault, true);
	mutex_lock(&sm->lock);
	sm5714_forget_source(sm);
	mutex_unlock(&sm->lock);
	sm5714_battery_typec_fault();
	/* Stop TCPM timers/worker before the I2C controllers shut down. */
	tcpm_unregister_port(sm->port);
}

static const struct of_device_id sm5714_usbpd_of_match[] = {
	{ .compatible = "siliconmitus,sm5714-usbpd" },
	{ }
};
MODULE_DEVICE_TABLE(of, sm5714_usbpd_of_match);

static struct i2c_driver sm5714_usbpd_driver = {
	.driver = {
		.name = "sm5714-usbpd",
		.of_match_table = sm5714_usbpd_of_match,
	},
	.probe = sm5714_usbpd_probe,
	.remove = sm5714_usbpd_remove,
	.shutdown = sm5714_usbpd_shutdown,
};
module_i2c_driver(sm5714_usbpd_driver);
MODULE_DESCRIPTION("SM-X710 SM5714 fixed-PD Sink TCPC transport");
MODULE_LICENSE("GPL");
