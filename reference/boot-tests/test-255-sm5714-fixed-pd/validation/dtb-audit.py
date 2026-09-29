import importlib.util,json,re,subprocess,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('dt','scripts/lib/dtb-idle-states.py');dt=importlib.util.module_from_spec(spec);spec.loader.exec_module(dt)
p=Path('reference/boot-tests/test-255-sm5714-fixed-pd/validation')
base=Path('out/kernel-container-candidate/sm8550-samsung-gts9wifi.dtb')
new=Path(sys.argv[1]) if len(sys.argv)>1 else Path('out/kernel-sm5714-stage2/sm8550-samsung-gts9wifi.dtb')
a,aph=dt.parse_tree(dt.decompile(str(base)));b,bph=dt.parse_tree(dt.decompile(str(new)))
cell_props={'clocks':'#clock-cells','assigned-clocks':'#clock-cells','assigned-clock-parents':'#clock-cells','resets':'#reset-cells','power-domains':'#power-domain-cells','phys':'#phy-cells','dmas':'#dma-cells','iommus':'#iommu-cells','interrupts-extended':'#interrupt-cells','io-channels':'#io-channel-cells','interconnects':'#interconnect-cells','mboxes':'#mbox-cells','thermal-sensors':'#thermal-sensor-cells','sound-dai':'#sound-dai-cells','qcom,smem-states':'#qcom,smem-state-cells'}
plain={'remote-endpoint','interrupt-parent','memory-region','nvmem-cells','cpu-idle-states','domain-idle-states','msi-parent','tcpm-power-supply','usb-role-switch','monitored-battery','operating-points-v2','required-opps','lens-focus','qcom,qmp','qcom,gmu','qcom,ice','sram','trip','wakeup-parent'}
def normalize(nodes,ph,prop,v):
 if v is None:return None
 if prop=='phandle':return '<local identifier>'
 cprop=cell_props.get(prop)
 if prop.endswith('-gpios') or prop in {'gpios','gpio'}:cprop='#gpio-cells'
 if prop=='cooling-device':cprop='#cooling-cells'
 if prop in {'gpio-ranges','msi-map'}:
  values=v.split();idx=0 if prop=='gpio-ranges' else 1
  for i in range(idx,len(values),4):values[i]=ph[int(values[i],0)]
  return values
 single=prop in plain or prop.endswith('-supply') or re.fullmatch(r'pinctrl-\d+',prop)
 if not single and not cprop:return v
 try:cells=[int(x,0) for x in v.split()]
 except ValueError:return v
 result=[];i=0
 while i<len(cells):
  key=cells[i];i+=1
  if key==0:result.append(0);continue
  if key not in ph:return v
  node=ph[key];result.append(node)
  n=int(nodes[node].get(cprop,'0'),0) if cprop else 0
  result.extend(cells[i:i+n]);i+=n
 return result
changes=[]
for node in sorted(a.keys()|b.keys()):
 if node not in a or node not in b:
  changes.append({'node':node,'property':'<node>','before':'present' if node in a else 'absent','after':'present' if node in b else 'absent'});continue
 for prop in sorted(a[node].keys()|b[node].keys()):
  x=normalize(a,aph,prop,a[node].get(prop));y=normalize(b,bph,prop,b[node].get(prop))
  if x!=y:changes.append({'node':node,'property':prop,'before':x,'after':y})
usbpd=b['/__symbols__']['sm5714_usbpd'];conn=b['/__symbols__']['sm5714_connector'];dwc=b['/__symbols__']['usb_1'];charger=b['/__symbols__']['sm5440_direct']
cap=[int(x,0) for x in b[conn]['sink-pdos'].split()]
pdos=[{'type':x>>30,'mv':((x>>10)&1023)*50,'ma':(x&1023)*10,'flags':x&0x3ff00000} for x in cap]
assert pdos==[{'type':0,'mv':5000,'ma':1800,'flags':0x04000000},{'type':0,'mv':9000,'ma':1500,'flags':0x04000000}],pdos
assert b[conn]['power-role']=='sink' and b[conn]['data-role']=='device'
assert 'source-pdos' not in b[conn] and b[dwc]['dr_mode']=='peripheral' and 'usb-role-switch' not in b[dwc]
assert b[charger]['status']=='disabled' and 'tcpm-power-supply' not in b[charger]
assert b[usbpd]['reg']=='0x33' and b[usbpd.rsplit('/',1)[0]]['clock-frequency']=='0x61a80'
assert normalize(b,bph,'interrupts-extended',b[usbpd]['interrupts-extended'])[1:]==[133,8]
hs=b['/__symbols__']['sm5714_hs_in'];dwchs=b['/__symbols__']['usb_1_dwc3_hs']
assert normalize(b,bph,'remote-endpoint',b[hs]['remote-endpoint'])==[dwchs]
assert normalize(b,bph,'remote-endpoint',b[dwchs]['remote-endpoint'])==[hs]
assert normalize(a,aph,'remote-endpoint',a[dwchs]['remote-endpoint'])==[a['/__symbols__']['sm5714_hs_in']]
approved=json.loads((p/'approved-dtb-changes.json').read_text())['changes']
key=lambda c:json.dumps(c,sort_keys=True)
actual_keys={key(c) for c in changes}
approved_keys={key(c) for c in approved}
unexpected=[c for c in changes if key(c) not in approved_keys]
missing=[c for c in approved if key(c) not in actual_keys]
obj={'valid':not unexpected and not missing,'phandle_identifiers_normalized':True,'changes':changes,'unexpected_changes':unexpected,'missing_approved_changes':missing,'sink_pdos':pdos,'DWC3_peripheral_unchanged':True,'SM5440_child_disabled':True,'other_hub3_GPI_properties_unchanged':not any(c['node']==charger.rsplit('/',1)[0] for c in changes),'USB2_graph_retained':True,'actual_VBUS_measured':False}
(p/'dtb-semantic-diff.json').write_text(json.dumps(obj,indent=2)+'\n')
import difflib
(p/'dtb.diff').write_text(''.join(difflib.unified_diff(dt.decompile(str(base)).splitlines(True),dt.decompile(str(new)).splitlines(True),fromfile=str(base),tofile=str(new))))
print(json.dumps({'changes':len(changes),'unexpected':unexpected,'missing':missing,'pdo':pdos},indent=2))
assert not unexpected and not missing,(unexpected,missing)
