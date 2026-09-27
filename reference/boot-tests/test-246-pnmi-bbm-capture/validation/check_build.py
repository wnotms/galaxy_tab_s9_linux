from pathlib import Path
import hashlib,json,tarfile,struct,re

p=Path('reference/boot-tests/test-246-pnmi-bbm-capture/validation')
out=Path('out/test246');newroot=Path('out/kernel-pnmi-bbm')
def cfg(path):
 values={}
 for l in path.read_text().splitlines():
  if l.startswith('CONFIG_'):k,v=l.split('=',1);values[k]=v
  elif l.startswith('# CONFIG_') and l.endswith(' is not set'):values[l.split()[1]]='n'
 return values
old=cfg(Path('out/kernel-bbm-range/config'));new=cfg(newroot/'config')
diffs={k:[old.get(k,'n'),new.get(k,'n')] for k in sorted(old.keys()|new.keys()) if old.get(k,'n')!=new.get(k,'n')}
expected=['CONFIG_ARM64_PSEUDO_NMI','CONFIG_HAVE_HARDLOCKUP_DETECTOR_PERF','CONFIG_HAVE_PERF_EVENTS_NMI']
assert diffs=={k:['n','y'] for k in expected},diffs
assert old['CONFIG_HARDLOCKUP_DETECTOR']==new['CONFIG_HARDLOCKUP_DETECTOR']=='n'
assert (newroot/'sm8550-samsung-gts9wifi.dtb').read_bytes()==Path('out/kernel-bbm-range/sm8550-samsung-gts9wifi.dtb').read_bytes()
assert (newroot/'kernel.release').read_bytes()==Path('out/kernel-bbm-range/kernel.release').read_bytes()
source=Path('.work/build/linux-src-gts9wifi/arch/arm64/mm/mmu.c').read_text()
assert '__flush_tlb_range(vma, addr, addr + nr * PAGE_SIZE,' in source
assert not Path('.work/build/linux-src-gts9wifi/arch/arm64/kernel/gts9_pnmi_test.c').exists()
def sections(raw):
 assert raw[:6]==b'\x7fELF\x02\x01'
 shoff=struct.unpack_from('<Q',raw,40)[0];size,num,idx=struct.unpack_from('<HHH',raw,58)
 rows=[struct.unpack_from('<IIQQQQIIQQ',raw,shoff+i*size) for i in range(num)]
 st=rows[idx];strings=raw[st[4]:st[4]+st[5]]
 return {strings[r[0]:].split(b'\0',1)[0].decode():(r,raw[r[4]:r[4]+r[5]] if r[1]!=8 else b'') for r in rows}
capfile=Path('.work/build/linux-out/arch/arm64/include/generated/asm/cpucap-defs.h')
cap=int(re.search(r'#define ARM64_HAS_GIC_PRIO_MASKING\s+(\d+)',capfile.read_text()).group(1))
mods=[]
with tarfile.open(out/'original-modules.tar') as tar:
 for member in tar:
  if not member.isfile() or not member.name.endswith('.ko'):continue
  oldraw=tar.extractfile(member).read();candidate=newroot/'modules-root/lib/modules'/member.name
  assert candidate.exists(),member.name
  newraw=candidate.read_bytes();a=sections(oldraw);b=sections(newraw)
  def versions(s):
   data=s['__versions'][1];assert len(data)%64==0
   return {data[i+8:i+64].split(b'\0',1)[0].decode():hex(struct.unpack_from('<Q',data,i)[0])
           for i in range(0,len(data),64)}
  va,vb=versions(a),versions(b)
  mismatches={k:[va[k],vb[k]] for k in va.keys()&vb.keys() if va[k]!=vb[k]}
  assert not mismatches,(member.name,mismatches)
  alloc_different=[n for n in sorted(a.keys()|b.keys())
   if (n in a and a[n][0][2]&2 or n in b and b[n][0][2]&2) and
   (n not in a or n not in b or (a[n][0][1:3],a[n][0][5],a[n][1])!=(b[n][0][1:3],b[n][0][5],b[n][1]))]
  def counts(s):
   raw=s.get('.altinstructions',(None,b''))[1];assert len(raw)%12==0
   return sum(struct.unpack_from('<iiHBB',raw,i)[2]==cap for i in range(0,len(raw),12))
  mods.append({'path':member.name,'original_sha256':hashlib.sha256(oldraw).hexdigest(),
   'candidate_sha256':hashlib.sha256(newraw).hexdigest(),'identical_bytes':oldraw==newraw,
   'allocated_sections_different':alloc_different,'old_gic_priority_alternatives':counts(a),
   'new_gic_priority_alternatives':counts(b),
   'versions_equal':a.get('__versions',(None,None))[1]==b.get('__versions',(None,None))[1],
   'import_crc_mismatches':mismatches,'new_imports':sorted(vb.keys()-va.keys()),
   'removed_imports':sorted(va.keys()-vb.keys())})
(p/'module-comparison.json').write_text(json.dumps({'scope':'All installed .ko files in verified backup compared with candidate. Differences are not automatically defects or proof of IRQ-mask incompatibility.','modules':mods},indent=2)+'\n')
files=[newroot/'Image.gz',newroot/'config',newroot/'sm8550-samsung-gts9wifi.dtb',newroot/'kernel.release',out/'vmlinux',out/'System.map',out/'Module.symvers']
artifacts={str(f):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files}
(p/'build-check.json').write_text(json.dumps({'config_differences':diffs,
 'config_explanation':'arm64 Kconfig selects the two HAVE_* capabilities when PSEUDO_NMI=y; HARDLOCKUP_DETECTOR remains unset in both',
 'dtb_equal_test245':True,'release_equal_test245':True,'bbm_patch_present':True,
 'calibration_helper_absent':True,'artifacts':artifacts},indent=2)+'\n')
print('config',diffs,'modules',len(mods),'identical bytes',sum(r['identical_bytes'] for r in mods),
 'allocated differences',sum(bool(r['allocated_sections_different']) for r in mods),
 'version table byte differences',sum(not r['versions_equal'] for r in mods),
 'shared import CRC mismatches',sum(bool(r['import_crc_mismatches']) for r in mods))
print('priority alternatives changed',[(Path(r['path']).name,r['old_gic_priority_alternatives'],r['new_gic_priority_alternatives']) for r in mods if r['old_gic_priority_alternatives']!=r['new_gic_priority_alternatives']])
