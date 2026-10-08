# AGENT.md — SM-X710 mainline port working rules

## 镜像备份保留规则（用户指令，2026-10-03）

- 删除已解决问题及已被后续版本替代的历史备份镜像，不继续积累其重复副本。
- 后续历史测试镜像仅允许保留最近 **10 轮**。“前 10 轮”指最近的测试
  编号窗口，包含当前轮，不是最早 10 轮，也不是 10 个镜像文件。当前最新
  编号为 Test362（S Pen 首次输入登记；Test348 仍未部署），窗口为 **Test353–Test362**；没有生成镜像的轮次仍占一轮。
- 每轮完成后清理窗口之外的历史镜像；同一规则覆盖仓库中的 `out/`、
  `.work/backups/`、迁移归档及其他镜像副本。不得把过期镜像移入另一个目录
  或压缩归档来规避上限。未来外部测试暂存也遵守该规则。
- 当前使用的生产镜像、原厂救援镜像属于运行文件，不作为已解决问题的
  历史备份。测试回退镜像也计入 10 轮窗口，按使用它的登记轮次归属，须
  记录原始版本及配套模块。本次保留当前 Test299 生产/回退镜像；Test300 对 Test263 的历史回退
  引用已过期，旧 boot/Image 及重复 Windows 副本已删除。旧 Test263 目录
  仅保留 SHA-256 与当前安装分区完全相同的 vendor_boot/init_boot/dtbo 三个
  运行镜像，不保留不匹配的旧 vbmeta；这不开放 Test263 历史镜像保留名额。
  引用轮次过期或基线被正式替代后清理，不得以“回退”名义永久保留旧镜像。
- 保留源码、配置、DTB、模块、原始日志、结果、镜像哈希及删除清单；历史
  测试记录中的镜像路径/校验和是当时证据，不保证实体镜像永久存在。需要
  重现已清理轮次时从记录的源码和配置重新构建，再校验，不复用缺失镜像。
- 本节优先于下文历史状态中的“保留所有旧备份/镜像/回退包”等旧要求。
  初次清理记录见 `reference/host-storage-cleanup/2026-10-03-image-retention/`；
  本次七个过期镜像删除及三个现用非 boot 文件的精确例外见
  `reference/host-storage-cleanup/2026-10-03-test311-image-retirement/`；
  Test312 窗口清理见 `reference/host-storage-cleanup/2026-10-03-test312-image-retirement/`。
  Test313 窗口清理见 `reference/host-storage-cleanup/2026-10-03-test313-image-retirement/`。

## 构建目录与空间控制（用户指令，2026-10-03）

- 新一轮构建优先复用同一配置/profile 的现有增量目录；测试编号变化不构成
  新增完整构建树的理由。复用前冻结旧正式产物、配置及必要调试输入的哈希，
  保存源码/工具链/profile 身份；复用后旧目录不再是旧版本的合格 provider。
- 完整构建目录仅为当前工作、已接受生产/有效回退、明确脚本消费者或仍在
  进行的独立 profile 验证保留。逐项记录用途；被替代或完成对照的临时目录
  本轮结束即删除，不把“曾经验证通过”作为永久保留整个目录的理由。
- 尽量每个仍在使用的 profile 只保留一个可复用增量目录。必要并存的生产/
  回退/外部模块 provider 不得混用或覆盖；先确认源代码、配置、符号 CRC、
  生成头文件及实际消费者，再清理。源码工作树不得按缓存目录直接删除。
- 删除过期构建树前，仅压缩保留重现/诊断确需的配置、符号表、生成头文件、
  调试符号和模块，并校验归档中每个文件。优先引用已有正式归档及其哈希，
  避免重复保存同内容；不归档整棵构建树或可再生成的 `.o`/`.a` 中间文件，
  不在调试归档中重存已超出最近 10 轮规则的 boot/Image 镜像。
- 旧调试归档也要注明仍需保留的具体问题/消费者；需求结束后清理重复或无用
  内容，保留来源和哈希清单。压缩后的输入不是完整增量树，不能直接充当
  外部模块 provider；要重建时使用记录的源码、配置和工具链。
- 共用项目 `.work/ccache`，不为每轮复制编译缓存。新增缓存应设置明确大小
  上限，默认 5 GiB；需要更大缓存时记录复用收益和空间预算。
- 大量构建/暂存前检查 Linux 文件系统及承载 WSL 的 Windows 盘可用空间。
  每轮结束检查 `.work/build`、`out` 和暂存目录，清理失效缓存与重复展开的
  模块副本；正式配套产物和原始证据须先校验归档再清理。大量删除后可执行
  在线 TRIM，并分别记录 Linux 和 Windows 实际空闲变化。
- 本次已删除 Test294/295/296 三个过期完整构建目录，必要调试输入压缩保存，
  净释放约 13 GiB；Test308 当前工作、Test299 生产、Test263 回退及默认/
  Test272/290 provider、Test302/303/305 独立验证目录保留。本次保留名单是
  当前用途记录，不是永久豁免。详见
  `reference/host-storage-cleanup/2026-10-03-build-reclaim/`。

### 冻结构建目录的中间文件清理（2026-10-03）

- 仅用于既有产物、调试符号、DT 审计或外部模块的冻结目录，不继续保留整套
  编译中间文件。确认无构建进程和实际消费者后，可删除内核 `.o`/`.a`、
  `.tmp_vmlinux*`、`vmlinux.unstripped` 及对应命令/依赖记录；不为这些可再
  生成的文件创建整树备份。删除前记录清单和哈希，删除后校验保留文件。
- 保留原始配置、最终含 DWARF/BTF 的 `vmlinux`、符号 CRC、模块/DTB、release、
  生成头文件及构建工具。`scripts/`、`tools/`、`include/`、架构生成头文件和
  外部模块所需的公共目标文件不得按普通内核中间产物批量删除；具体范围须
  依据所用 Kbuild 和脚本消费者检查，不能推广成无条件删除所有 `.o`。
- 清理后的目录不再是完整内核增量缓存，后续完整构建会重新生成缺失对象。
  保留外部模块输入不代表重新通过来源校验；现有 source/config/profile/CRC
  身份检查仍须执行，不能用当前源码覆盖旧 provider 后继续沿用旧资格。
- 当前仅 Test308 未完成工作和 Test302 明确增量基线保留完整构建缓存。
  默认/Test263/272/290/299/303/305 七个目录已精简，必要产物和两个源码树
  保留；`.work/build` 从 44.69 GiB 降至 17.71 GiB，释放约 27 GiB。这取代
  上次清理时对这七个目录“保留完整构建树”的状态记录。当前工作完成后，
  再按实际消费者收敛完整缓存，不把基线或独立 profile 名称作为永久豁免。
- 清理记录与 330,078 个保留文件的实际校验见
  `reference/host-storage-cleanup/2026-10-03-build-intermediates/`。

### 移植遗留产物清理补充（2026-10-03）

- 停用的准备源码工作树先记录原始 commit、保存 tracked binary diff 和全部
  未跟踪文件，并验证可恢复，再通过 `git worktree remove` 移除。只有已完整
  保存、验证且无现用消费者的临时准备树才可使用 `--force`，并记录原因；
  上游 checkout、当前源码树和用户正在修改的源码不得作为临时缓存清理。
- 过期模块目录先逐项校验完整文件集合与归档哈希，再删除展开副本。当前
  生产/回退、近期候选及脚本默认依赖的 `modules-root` 保留；历史工具若需要
  已清理目录，须按清单恢复后重新校验，不把目录存在当成版本匹配证明。
- adbd 等一次性构建的 mktemp 工作目录，在产物和源码差异归档完成后本轮
  清理；下载源包统一复用已校验缓存。运行依赖、最终二进制和原始日志不按
  临时构建目录删除。历史大文件优先按内容哈希保留一份可还原的压缩文件。
- 本次移除 3 个停用源码工作树、28 处旧模块展开副本、5 个 adbd 临时目录、
  3 个迁移归档中的重复未压缩模块包和 2 个早期镜像暂存目录；17 个历史
  符号/模块包及 7 组旧原始调试资料已压缩保存。扣除硬链接重复计数和新归档
  后净减少约 15.5 GiB。原始证据、必要配套产物和 Test308 当前修改保留。
  恢复位置与校验记录见
  `reference/host-storage-cleanup/2026-10-03-porting-leftovers/`。

## Current state (2026-10-03)

2026-10-08 Test362 PEN_PROBED_CAPTURE_LIVE_OWNER_PENDING.
Pushedab638aa9 precedes1normalinsmod, same33125ff0ad0/6-0056/event5/tabletclass.
Queryfw4018/maxX14752/maxY23603/pressure4095, axesres100, no fallback/MPUerror;
5sIRQdelta0 beforeownerpen -> notphysicalinputpass. No newkernel fault/failedunit,
GNOME/touch/SSHnormal/66%25.6C GoodDischarging/taint12804unchanged/no force.
Collector5264/start311022 confirmedlive/stateS/0events/no terminal, max600s;
owner hover/stroke/grid/buttons pending; no restart whenSSHreturns.
Currentboot-onlypen, existingFTSstub -> no penpalm suppression. No firmware/
config/DT/181dir/charging/autoload/flash/reboot; tests/build:false results/reuse15
C/W1/29CRC.348grantunused/freshdesktopinactive admission/finalexact331TWRP.

2026-10-08 Test362 PEN_CAPTURE_DEADLINE_NO_EVENTS.
Collector5264/start311022 ran600.606s non-grabbing and ended at its registered
deadline with0events/0frames/0trailing bytes, same331 boot25ff0ad0,65%24.0C
GoodDischarging, no failed unit/new fault. No owner pen interaction occurred;
therefore physical pen input is incomplete, neither pass nor driver failure.
Terminal/final-health/raw-empty evidence retained; future fresh scope needed for
hover/tap/grid/button/pressure/release. No restart/unload/flash/reboot/charging.
Full port active;348grantunused/finalexact331TWRP.

2026-10-08 Test362 REGISTERED_FEDORA_WEZ01_S_PEN_ONE_LOAD.
Same33125ff0ad0/currentGNOME+touch accepted,67%25.9C GoodDischarging/client6-0056
unbound. Fedoraab123e7d remoteHEADunchanged; optional external WEZ01 module with
rearmabletimer/draincallback/devresordering/probestarterror fixes, no DT/config.
W1 build0warnings/15actual-C+guards PASS, all29 importedCRCs match exact331Image;
normal loader/BTF/signature remainsrequired/no force. Oneinsmodoutside181dir,
5sIRQ then<=600s pen-onlynon-grab capture/ownerpending, no persistentautoload.
ExistingFTSstub unchanged -> no penpalm suppression; no suspend/calibration/
firmware/flash/reboot/charging. Window353–362/no352image retirement;348grantunused,
futurefreshdesktopinactive admission includespen delta/finalexact331TWRP.

2026-10-08 Test361 OWNER_CURRENT_RUN_NO_HEAT_REPORTED.
Owner“本次没有发热，上次运行时发热”; historicalheat causeunproven/notreproduced.
Keep ownerbrightness unchanged/no50or70%write/no extraheat-reproduction stress.
msreducedmotionfalse reversible viaoriginalabsent-key reset, GUI/touchnormal.
Results-onlytests/build:false/no device action; continueotherport work, not
block fullgoal on unobservedheat.348grantunused/freshinactive admission/finalTWRP.

2026-10-08 Test361 REDUCED_MOTION_APPLIED_TWO_NORMAL_USE_WINDOWS_COMPLETE.
Same33125ff0ad0,2x60s/14snapshots; onlymsenable-animations=false viaactivebus,
originalexplicitabsent saved (resetrollback). GUI/touchleftactive/no newfailed
unit/severekernel fault; collector4348terminal/no restart. Pack26.0->26.8C,
GPU67.6/89.9% runtimesuspended; CPU7 deeperidle/WFI advances, cachedfreq !=busy.
CPUcapacity13.51/4.46%,QQ/activitychanged -> no causal cooling claim. Rawbrightness
2047/2047 bothwindows vs earlier628; owner50/70/retainedbrightness choicepending.
8affectedtestsPASS/no full/build/CI; no OPP/governor/thermal/charging/USB/kernel/
DT/181dir/flash/reboot.348grantunused/freshinactive admission/finalTWRP retained.

2026-10-08 Test361 REGISTERED_GNOME_REDUCED_MOTION_HEAT_OBSERVATION.
Same33125ff0ad0/currentowner360UIaccepted,72%25.5CGoodDischarging/animationson.
60s normal-use snapshots thenonlymsenable-animations=false (save exact dconf),
60s after, no stress. Per10s boot/pack/newkernel guards, rawCPU/procs/TSENS/
GPUruntimePM/brightness; no argv/env/inputcapture, no zone37 reads/zero-fill.
8affected counter/PIDreuse/unit tests PASS; no full/routing/kernel build.
Firstfault restores exactkey/partial evidence/no retries; no OPP/governor/
thermal/current/charging/USB/DT/181dir/flash/reboot. Window352–361/no351images;
348grantunused/current331+348provider retained/freshinactive admission/finalTWRP.

2026-10-08 Test360 OWNER_NEWBOOT_LOGIN_AND_TOUCH_CONFIRMED_PASS.
Owner“登录和触摸桌面正常” after installedGDM-Wants one normalnewbootload;
functional persistentGNOMEtouch step complete on33125ff0ad0. GUI remainsactive,
GDMautostart masks retained; no autoGUIboot/suspend/longtermheat reliability.
Results-onlytests/build:false; no additionaldevice operation forconfirmation.
Nextseparate desktopheat/idle analysis, no OPP/charging/thermal limit change;
fullport incomplete/348grantunused/freshinactive admission/finalTWRP retained.

2026-10-08 Test360 NEWBOOT_PERSISTENT_GDM_TOUCH_LOAD_PASS_OWNER_UI_PENDING.
Same33125ff0ad0 ownerboot, oneGDMstart triggers installedGDM-Wants normal1insmod,
loadedJSON/return0/client7-0049/event4. Finalalreadyloaded/GDMactive/SSHnormal,
3GDMmasks restored without --now; nofailedunit. Kernel1104->1111/seven startup
records/no newsevere signature; knownunsignedO/E516->12804 preserved/no force.
Read-only11.649s startup pack25.4C unchanged/73%GoodDischarging; GPUondemand
220MHz endpoint. CPU7 cachedhigh bothphases !=proofsustainedCPU load; heat
cause/longterm/SoC/surface unproven, ownerasks laterdesktop heatoptimization.
Owner newboot login/touch confirmation pending; no silent reuse of357UIpass.
Tests/build:false results-only/reuse17+8C/W1/37CRC; no charging/OPP/thermal/USB/
config/DT/181dir/flash/reboot.348grantunused/freshinactive admission/finalTWRP.

2026-10-08 Test360 REGISTERED_INSTALLED_TOUCH_NEWBOOT_GDM_LOAD.
Owner manual25ff0ad0 boot confirmed, exact331 installedloader/module gate ready;
textboot/no load expected. OneGDMstart triggers enabledGDM-Wants touch service,
normal1insmod/no force or retry;10s initialcheck thenownerUIpending. Restore
3GDMmasks without --now; no reboot/flash/charging/config/DT/181-dir change.
Existing17loader+8C/W1/37CRC reused, activationPython syntaxchecked/no fullbuild.
Historical351–360/no350images to retire;348grantunused/provider/331protected,
futurefreshdesktopinactive admission/finalTWRP unchanged.

2026-10-08 Test359 INSTALLED_CURRENTBOOT_NOOP_PASS; LATER_OWNER_MANUAL_REBOOT.
Onebackup recovery Resultsuccess/status0, no clock/timer/RTC/NTP policy change.
3ownedtouchfiles installed outside181dir; GDM-Wants-only unit enabled/start
alreadyloaded/0insmod,2.875s device/8.163s host; same331/GDM/SSH normal,75%32.3C.
1143kernel records before/after/0new, nofailedunit; all3GDM masks retained.
After scope ownerpaused/manualrebootconfirmed ->25ff0ad0, same331/73%31.8C.
Nowtextboot/GDM+touch inactive/loaderready, no newload; future GDM-triggered
newboot touch acceptance NOTyetproven. CorrectedcompactUUID priorjournal and
currentjournal/pstore preserved/no severe fault; oldbootorderlypoweroff.
17tests reused/results-onlytests/build:false; no kernel/DT/charging/USB/flash/
reboot command.348grantunused; futurefreshdesktopinactive admission/finalTWRP.

2026-10-08 Test358 STOP_BEFORE_INSTALL_DPKG_START_LIMIT; Test359 REGISTERED.
358zeroownedwrites/insmod, same331/GDM/touch accepted remainsnormal; dpkgbackup
five successfulruns then start-limit-hit/ExecMainStatus0, disk96GiBfree.
Currenttimer/time stable; earlierOct25timestamp/rapid-trigger cause unproven.
359one scoped reset-failed+one normalbackup mustverify success, then same3file
optionalGNOME component/noop start. No timer/RTC/NTP/hardware/reboot/flash.
17loaderqualification reused unchanged/syntax reviewed; priorSTOP/raw preserved.
Historical350–359; active348grantunused/provider and331rollback retained.

2026-10-08 Test358 REGISTERED_OPTIONAL_PERSISTENT_GNOME_TOUCH.
Same3311adc0f13/Test357 owner+raw accepted module; install3 absent ownedfiles
outside181dir, gdm.service.wants only; GDM masks/defaulttarget unchanged.
Exact config/notes/module/board gates; unknown/SM5440opts/lpcharge1 skip, no
textboot dependency/retry/force/firmware/sysfs/unload. Currentalreadyloaded
service start mustbe no-op/0insmod; futureboot loading explicitly untested.
17affectedtests PASS; initialfixturebug/beforeinstallmissingtarget preserved.
Existing8C/W1/37CRC qualification reused; no kernel/full/routing/CI/flash/reboot.
348unused activependingassets/provider and331rollback preserved outsidehistory
window349–358; futurefreshdesktopinactive admission/finalTWRP unchanged.

2026-10-08 Test357 FEDORA_TOUCH_OWNER_AND_RAW_EVENTS_PASS.
One normal load of byte-identical X710Fedorafts; same3311adc0f13/7-0049/event4,
37 importedCRCs match; GDM/SSH responsive and ownercoordinates/directionsPASS.
191.244s raw12777events/2113frames/two simultaneous contacts; finalslot snapshot
all10released. No newkernel fault/failedunit;80%32.8C Good. Unsigned/outoftree
warning/taint516->12804 preserved, no force flags. Collector3294terminal after
ownerconfirmation, no restart; module/GNOMEleftactive, no permanentautoload.
No firmware/Spen/doubletap/suspend/unload/config/DT/charging/flash/reboot.
8Ctests/W1 reused/currentCRCgatePASS; results-onlytests/build:false.
34820minunused/fullportincomplete, futurefreshdesktopinactive admission/finalTWRP.

2026-10-08 Test357 REGISTERED_NEWBOOT_FEDORA_TOUCH.
Independent new1adc0f13 scope after355zero-load stop;356shortkey regressionPASS.
Fresh same331/config/notes/81%32.1C Good/GDMactive/WiFi157/client7-0049 unbound.
Same qualified module/37CRC pairing; one load outside181dir/normal loader,
unsigned external taint recorded (SIG_FORCE=n), no forced flags/retry.
5sIRQ/input then<=900s rawnon-grabbingcapture withsleepinhibit; ownertouchpending.
No firmware/Spen/doubletap/suspend/charging/flash/reboot. Expired347images retired
unless348 consumer;348grantunused/finalTWRP. Existing8tests/W1 reused/no fullbuild.

2026-10-08 Test356 SHORT_PRESS_REGRESSION_PASS.
Owner“熄屏再亮屏，桌面正常”; authenticated same1adc0f13/GDM/backlighthelper
active, two short-key events/noPowerOff in new journal. GNOME nothing policy
restores existingbacklight ownership; no logind/kernel/charging changes.
Desktop staysactive, touch not loaded. Next fresh touchregistration onthisboot.

2026-10-08 Test356 GNOME_POLICY_APPLIED_AWAITING_SHORT_PRESS_CONFIRMATION.
GNOME default plus ms/greeter effective nothing verified, prior explicit values
both absent, saved raw. Same3311adc0f13, GDMone10.140s PASS/leftactive/masked,
SSH responsive/zero new kernelfault or failedunits,82%32.1C Good. Existing
logindignore/backlighthelper untouched. Owner asked two short presses; physical
pass not yet claimed. No touch/flash/reboot/charging.1real-schema testPASS,
fulltests/build:false;348unused and freshdesktopinactive admission/finalTWRP.

2026-10-08 Test356 REGISTERED_GNOME_POWER_KEY_NOTHING.
Fix only GNOME48.1 VM-non-nothing shutdown path: schema default plus ms/greeter
power-button-action=nothing; save exact old explicit dconf values. Same331new
boot1adc0f13/WiFi157, one10s GDMstart/all3persistentmasks/no autostart. Existing
logindignore/backlighthelper unchanged. Ask two short presses before acceptance.
RealDebian48.1 schema test PASS; no fulltests/build/kernel/DT/module/charging/
touch/reboot/flash.348scopeunused; freshdesktopinactive admission/finalTWRP.

2026-10-08 Test355 STOP_BEFORE_TOUCH_LOAD_POWER_KEY_POWEROFF.
Owner reports spontaneousoff/manual restart before module upload/insmod (zero).
New331boot1adc0f13 at WiFi10.175.236.157, config/notes unchanged,83%32.4C Good.
Priorboot power-key event -> GNOME48.1 VM-non-nothing policy -> logind PowerOff
-> orderly shutdown. vm-other/defaultsuspend; existing logindignore/backlight
helper correct. Full prior/current kernel no recorded stall/panic, pstore empty.
No touch load/logdir. Next scoped GNOME nothing policy; new touch registration
requires newboot; no charging activation. Tests/build:false for incidentresults.

2026-10-08 Test355 REGISTERED_FEDORA_TOUCH_ONE_LOAD.
Same331/activeGNOME; pinned same-model byte-identical module,37 imports CRCs
match exact331 Image/module_layout; BTF.base normal loader gate/no force flags.
One insmod from var/tmp, no accepted181-dir/kernel/DT/config/charging change.
5s IRQcheck and <=900s non-grabbing rawtouch capture/sleepinhibit; owner UI
acceptance pending, no suspend/doubletap/Spen/firmwareupdate/unload/flash/reboot.
8affected actual-C tests PASS; existingW1 modulebuild reused/no fullsuite.
Retired expired345stage/images;331/348 protected,348grantunused/finalTWRP.

2026-10-08 Test354 GNOME_KEYBOARD_SESSION_OWNER_CONFIRMED_FUNCTIONAL.
Owner “已测试，功能正常” confirms reopened desktop manual functionality.
Prior accelerated EGL/Turnip and keyboard/password evidence retained; no touch
acceptance or reliability claim. No new device operation; desktop left active,
persistent autostart masks unchanged.348 paused/unused; tests/build:false for
this owner-confirmation/status change. See354owner-confirmation/RESULTS/summary.

2026-10-08 Test354 GNOME_ACTIVE_FOR_MANUAL_KEYBOARD_TEST.
One GDMstart/10.294s check PASS, same331 boot/config/notes, SSH responsive,
zero new kernelfault/failedunits/renderpermission fallback,86%32.2C Good.
Desktop LEFT ACTIVE for owner use; no60s shutdown. All3persistent masks restored
without --now; future autostart blocked. Touch unloaded, no flash/reboot/charging
change.348 remains paused/unused and requires GDM stopped before future admission.
Evidence SHA/syntax reviewed; tests/build:false (unchanged source qualification).

2026-10-08 Test354 REGISTERED_INTERACTIVE_GNOME_REOPEN.
Owner requests desktop reopen, confirms previous keyboard/password login. One
start/10s initial check then leave GDM active; no 60s autoclose. Restore all3
persistent masks without --now, same331/no install/touch/charging/reboot/flash.
348 remains paused/unused; future admission requires desktop stopped. Retired
expired344stage/images,331/348 preserved; tests/build:false for registration.

2026-10-08 Test353 ORDINARY_USER_ADRENO_AND_BOUNDED_GNOME_VALIDATED.
Only render memberships added; user Turnip/FD740 EGL PASS, GDM60.055s/no new
kernel fault or software fallback; owner confirms keyboard/password login.
Greeter UID103 Xwayland exit during login retained separately from ms session.
Endpoint GDM inactive/all3masked, touch unloaded. Same331;348 unused/paused.
Evidence hashes reviewed; tests/build executed:false for results-only change.

2026-10-08 Test353 REGISTERED_RENDER_ACCESS_CORRECTION.
Only add ms/Debian-gdm to existing render group; preserve other groups/udev/node
modes. One userVulkan30s/surfacelessEGL30s, conditionalGDM60s; maskedendpoint.
Same331/healthy/protected critical files; no kernel/DT/config/module/charging/
touchload/reboot/flash. Original352partial retained;348grantunused/finalTWRP.
Retired superseded343images/stage unless explicitly reused within344–353.

2026-10-08 Test352 PARTIAL_DESKTOP_VISIBLE_RENDER_ACCESS_PENDING.
Exact368packages/3GPUfirmware installed, existing versions preserved. Root
Vulkan TurnipAdreno740/Mesa25.0.7 identified. One60.045s GNOME/GDM observation,
owner confirmed graphical login; same331boot/no new kernelfault; GDM stopped/
remasked. ms/Debian-gdm lack render group; renderD1280660 caused permission
failure/software framebuffer sharing. No desktop HWaccel acceptance yet.
Next scoped group correction, no kernel patch. Touchunloaded/charging frozen;
348grantunused/finalTWRP unchanged.29affected tests PASS; build/full:false.

2026-10-08 Test352 REGISTERED_LOCAL_ONLY_APT_CORRECTION.
Correct --no-download local-acquisition failure using invocation-local empty
APT sources; no /etc/apt change/network fetch.29affected tests PASS including
realAPT localdeb simulation; readonly device exact368plan PASS. Reuse complete
351cache, upload only hash-bound installer/helper. Oneinstall, conditional30sGPU/
60sGDM, maskedendpoint. Same331/protected38/charging frozen, no touchload/reboot/
flash. OriginalSTOPs retained;348grantunused/finalTWRP unchanged.342stage retired.

2026-10-08 Test351 STOP_BEFORE_INSTALLATION_APT_LOCAL_ACQUISITION.
Verified-prefix transfer PASS56.15s/full archive SHA;381members extracted.
Sole installerPID3703 ended before masks/firmware/APT: --no-download prevented
local .deb acquisition. Readonly corrected-source simulation exact368/no upgrade/
removal PASS. Original STOP/raw kept; cache reusable. Same331 normal90%32.0C.
No GPU/GDM/touch/reboot/charging;348grantunused/finalTWRP unchanged.

2026-10-08 Test351 REGISTERED_VERIFIED_PREFIX_DESKTOP_RESUME.
Reuse exact139493376-byte device prefix, hash matches qualified local archive;
only26998784bytes upload, full SHA before extraction. Same331boot protected38/
health/zero failed PASS at91%31.8C. Same GNOME installation/GPU/GDM scope; no
kernel/DT/module/charging/reboot/touchload. Prior349/350 STOP retained. GDMmasked
endpoint,348one1200s unused/finalTWRP unchanged. Superseded341stage retired.

2026-10-08 Test350 STOP_HOST_CANCELLED_UPLOAD_FOR_RESUME.
Host explicitly cancelled bulk upload696.88s; SSH255 is cancellation, not send
stall. Same331boot responsive/protected38 unchanged/no failedunits; exact device
prefix hash matches qualified host archive. No extraction/APT/firmware/GUI.
Preserve STOP/raw and verified prefix; fresh resumable registration next, not a
whole-file blind retry. Original348watch remains terminal; grantunused/finalTWRP.

2026-10-08 Test350 REGISTERED_CORRECTED_BULK_DESKTOP_TRANSPORT.
Independent partial-send proxy avoids349sendall1s timeout;10 focused tests PASS.
Original charging transport unchanged. Fresh same331boot/protected38/health PASS;
no concurrent dischargewatch during900s transfer. Exact archive size/hash before
extraction; oneinstall, optional boundedGPU/GDM as349, no touchload/flash/reboot/
charging. GDMmasked endpoint,348grantunused/finalTWRP preserved. Superseded340
Windowsstage retired;331/348 retained. Kernel/fulltests executed:false.

2026-10-08 Test349 STOP_HOST_PROXY_SEND_TIMEOUT_BEFORE_INSTALL.
One bulk upload wrote only16154624bytes; native Windows sendall inherited1s
socket timeout. No extraction/APT/firmware/GDM/GPU/touch/reboot occurred.
Fresh authenticated same331be1baaaa responsive, protected38 hashes unchanged,
zero failedunits,94%31.6C normaldischarge. Original348 observerPID31327/session68905
is terminal at sample50 banner timeout during bulk transfer; raw/terminal kept,
not live/not restarted. Fix isolated bulk transport before fresh desktop attempt.
348one1200s grantunused/finalTWRP unchanged. Tests/build executed:false forresults.
See Test349 RESULTS/summary and348natural-discharge terminal evidence.

2026-10-08 Test349 REGISTERED_DESKTOP_DURING_DISCHARGE.
Owner explicitly requested GPU/GNOME work during wait; earlier assistant-created
after348 ordering superseded. Separate349 only adds verified desktop userspace/
GPUfirmware on exact331; no kernel/config/DT/modules/charging change, no touchload.
Readonly allfive181/config/notes/DCC/zero failed/38gts9hashes/WiFi PASS,95%31.6C.
One install, one30s Vulkanprobe, one60s controlledGDM observation; GDMmasked after.
Register/push before devicewrite. 348 grantunused and finalTWRP unchanged; fresh
desktop-inactive admission/rootfsdelta required before348. Retired superseded339
images/stage; source/config/DT/modules/raw preserved. See349README/registration.

2026-10-08 GNOME host transfer bundle VERIFIED_NOT_TRANSFERRED.
out/gnome-trixie-arm64/gts9-gnome-deploy.tar,381 regularmembers/166492160bytes,
368packages/3GPUfirmware/controlledinstaller/optionalunloadedtouch. Fulltar set/
bytes checked; existing installer/touch qualification identities required.
No device operation/Windowscopy/newkernel/fullsuite. This temporarytar follows
desktopdeployment closurecleanup; manifests/source retained. See desktop deploy-bundle.

2026-10-08 GNOME installer OFFLINE_PREPARED_NOT_EXECUTED.
Local verifiedcache/simulation gate, no upgrade/removal, expectednativeX710boot;
reject chargingtestparameters. Persistent gdm/gdm3/display-manager masks before
APT, temporary policy-rc.d restored on ordinarysuccess/error, checkpoints/rawlogs.
No GUIstart/touchload/reboot/flash. Existinguser ms confirmed readonly same331boot.
Affectedmock/cache/policy tests only; actualAPTinstall/build/full/deviceGUI:false.
Run only after348closure as separatedevice stage. See userspace/gnome/README.md.

2026-10-08 X710 touch OFFLINE_MODULE_COMPILED_NOT_DEPLOYED.
Byte-identical Fedoraab123e7d FTS1BA90A/header imported under kernel/desktop,
outside defaultbuild. OptionalWacomstub used; noSpen/firmwareupdate. ARM64W1
externalmodule compiled against qualified348provider, protectedfiles unchanged;
eight actualC decoder tests PASS. No install/load/unload/devicewrite; samevermagic
does not establish331acceptance. Touch/GNOME hardwarework follows348closure,
frozen kernel/config/DT/modules remainunchanged. See desktop touchREADME/evidence.

2026-10-08 GPU/GNOME HOST_PREPARED_NOT_DEPLOYED during Test348 discharge.
Owner selected GNOME/touch and authorized reference to Fedora/S9U/Samsung.
Read-only current331 inventory: adreno renderD128 and DPU DSI2560x1600 present;
GPU initialization/rendering not proven, rootfs SQE/GMU/ZAP and DRI/Vulkan/GNOME
missing. Existing X710 FTS DT node has no driver/input yet. Host cache368 Debian
ARM64/all packages165385796bytes verified; three pinned same-model GPU blobs
staged, complete-MBN ZAP unchanged under requested.mdt name. No deployment,
kernel/config/DT/rootfs-service change or GPU load;348 frozenqualification/grant
unchanged. Affected preparation tests only; build/full/device tests:false.
See docs/GPU_GNOME_BRINGUP.md and desktopinventory.
Desktop installation/activation follows348 closure; final348endpoint stillTWRP.

2026-10-08 PC USB input-control source assessment only.
Samsung BUCK_OFF differs from CHARGING_OFF: Q4on -> CNTL2SUSPEND -> Q4off;
restore clearsSUSPEND then10-11ms wait. Currentmainline inputlimit readonly,
no implemented PCinput-inhibit API. Q4off/100mA is not noVSYSinput. No charger
register/driver write, no test/build executed for this documentation change.
See docs/SM5714_USB_INPUT_CONTROL.md and desktopinventory sourcehashes.

2026-10-08 Test348 READONLY_NATURAL_DISCHARGE_LIVE.
Owner“已拔线”; read-only hostPID31327/unifiedsession68905 first authenticated
sample same331be1baaaa, USBoffline/Discharging/100%/30.5C/4.371V/-1.563A.
Natural58% target,60s reads/max6h,no load/write/PPS/pumpON. No candidateinstall,
one1200s grantunused. Re-poll same livehandle; do not restart for observation
timeout. At target freshPCpreflight/install/admission/C1 stillrequired. FinalTWRP.
Evidencecollector syntax/actualread passed; tests/build:false,reusequalification.
See348active-natural-watch/preparation-status and watchhandle. FullportNOT_READY.

2026-10-08 Test348 WIFI_RESCUE_RECOVERED_AWAITING_UNPLUG.
Owner“已同网”; Windows10.175.236.63 and tablet10.175.236.175, authenticatedSSH
matches331be1baaaa/config/notes/machine. SOC100/31.0C/PCUSBonline, ownerasked
unplugfornatural58% headroom; no watcherstarted yet. Candidate stagedonly,
no install/PPS/pumpON, one1200s grantunused. Final331restore/TWRPunchanged.
Evidence-only tests/build:false. See348PREPARATION and preparation-status.

2026-10-08 Test348 AUTHORIZED_STAGED_WAITING_WIFI_AND_DISCHARGE.
FreshTWRP/exact331boot confirmed; one normal331 boot be1baaaa47fc41f582558f7092c01653
with exactconfig/notes, ADB/deviceNCM/noCode43/zero failedunits/physicalpumpOFF.
SOC100/31.2C/4.447V refuses <=60%/<4.3V preparation. No install/PPS/pumpON,
scope unused. WiFi10.175.236.175 vsWindows10.30.54.214: firstSSH banner timedout;
owner asked to joinsameOnePlus13s hotspot,USBstillconnected. No dischargewatcher
running. SevenWindows348files staged/hashverified; device ordinary331Debian
onlyforpreparation. Naturalheadroom58 afterWiFi+ownerunplug; finalTWRPunchanged.
Evidence-only tests/build:false,reusequalification. FullportNOT_READY. See348
PREPARATION/preparation-status and rawbaseline folders.

2026-10-08 Test348 AUTHORIZED_ONE1200S_PENDING_FRESH_BASELINE.
Owner “允许执行 20 分钟测试” authorizes the independent one1200s scope:
hardware1700/PPS+raw1800, exact331/allfive/original181 restore, finalTWRP.
No physical action yet. Prior offline manifests preserved; flags now authorized.
Fresh baseline normal331 boot/identity/rescue/battery, <=60 SOC preparation,
one install/admission/OFFpark and fresh candidate-bound C1 reply precede sole
launch. No Test347 grant reuse/restart or current increase. Fullport NOT_READY.

2026-10-08 Test348 REGISTERED_OFFLINE_PENDING_PHYSICAL_AUTHORIZATION.
Independent1200000ms runner reuses qualified0b731 source/build, packages armed
boot offline only.49 affected host tests and Python/shell syntax PASS; artifacts
hash verified. No kernel rebuild/full regression (executed:false), no Windowsstage
or device operation. Preparation/activationSOC<=60 (naturalheadroom58), hardware
1700/PPS+raw1800 unchanged; native1200/guardian1260/monitor1300/outer1500.
One fresh scope and candidate-bound C1 reply required; no Test347 grant reuse.
Original-process timeout handling and exact331/allfive/181 restoration ending
TWRP are host-tested. Device stays TWRP/restored331 per owner; no1200s hardware
acceptance.339–348 retention expired338, nine verified files371499694 bytes
retired. Full port NOT_READY. See Test348 OFFLINE_RESULTS/offline-summary.

2026-10-08 Offline1200s duration candidate READY_OFFLINE_DEFAULT_OFF.
Source0b731b4a adds only immutable1200000ms exclusive one-shot; defaultOFF/30s
and300s retained, hardware1700/PPS+raw1800/current/voltage/fault/thermal/PM/
lease/refresh/reserve unchanged.167 affected tests PASS (85actualC/11parser/
71retained), historical frozen-parser comparisons use manifest-bound Git bytes.
Incremental ARM64/modules84.982s/W1+sparse13.493s PASS/no new warnings;
exact331 config/DT/release,108 protected sources/9 old formal artifacts preserved.
181 modules match Test347 runtime; metadata pair changed. Formal defaultOFF
outputs out/kernel-x710-twenty-minute, boot-bundle-x710-twenty-minute-off.
Device remains TWRP/restored331; no device operation/Windowsstage/armedboot.
No1200s physical runner or authorization yet; next independent registration,
not Test347 restart. Full port NOT_READY. See charging/test347-twenty-minute-followup.

2026-10-08 Test347 CLOSED_300S_PASS_RESTORED331_STAYING_TWRP.
One owner-confirmed300s native attempt passed: 62 refreshes/63 zero proofs,
417 active frames, rawIBUS max1.781875A, pack32.7°C/die48.5°C. OFF/unbound/
fixed9, ordinarycharge31.022s, discharge15.606s and one PC ADB/deviceNCM/noCode43
all passed. No new journal fault. Owner “已接回电脑，本轮完成后保持在twrp”
changed only final endpoint: exact331 boot/allfive/original181 restored and
verified, Debian unmounted, final TWRP3.7.1 identity; no restored Debian reboot
or fresh runtime acceptance. rollback_required=false. Device must remain TWRP.
Seven-file Windows347 transfer stage retired after verification; qualified WSL
candidate/current331 rollback retained. No second activation; 300s grant consumed.
Evidence-only tests/build false, reused60host/79C/ARM64/W1+sparse; one-time
completion syntax and actual recovery gates passed. Full port NOT_READY: next
1200s candidate/independent registration and physical scope still required.
See Test347 PHYSICAL_RESULTS/physical-summary and recovery-completion evidence.

2026-10-08 Test347 DISCHARGE_PASS_AWAITING_PC_RESTORE.
Owner unplug confirmed; same candidate 19fbf941 passed 15.606s discharge,
USB/TCPM offline, battery 71% / 32.0°C / −0.646A, physical pump OFF/unbound.
Native 300s and fixed9 ordinary charge already passed. Await owner PC return
for one ADB/device-NCM/Windows check, then unconditional exact331/allfive/
original181 restoration. No second PPS/pump attempt. Full round not closed,
full port NOT_READY. Evidence-only tests/build false; qualification reused.
See Test347 PHYSICAL_PROGRESS and discharge raw evidence.

2026-10-08 Test347 NATIVE_300S_AND_FIXED9_CHARGE_PASS_PENDING_RESTORE.
Fresh owner C1 reply launched sole guardian 1762 on candidate 19fbf941. Native
300000ms proof passed: 62 PPS refreshes, 63 parked-zero proofs, 417 active frames,
raw IBUS max 1.781875A, pack max 32.7°C, die max 48.5°C (ADC uncalibrated).
Pump OFF/unbound and fixed9 restored; ordinary charge passed 31.022s, endpoint
71% / 32.6°C / +2.069A. Complete raw guardian/full-journal collection passed.
Discharge observer active awaiting owner unplug, then one PC rescue check and
unconditional exact331/original181 restoration. No second activation. Overall
round not yet closed; full port NOT_READY. Evidence-only tests/build false,
reuse existing qualification. See Test347 PHYSICAL_PROGRESS.json.

2026-10-08 Test347 DEPLOYED_OFF_UNBOUND_AWAITING_FRESH_OWNER_C1.
Fresh PC preflight on Test331 a96de8c0 passed at 68% / 32.0°C. One paired install
verified all five partitions and 181 module files. Normal candidate boot
19fbf94136a64f7cb73e9e263da8549c is uniquely attributed; exact identities/journal/
ADB/device NCM/Wi-Fi SSH passed, address 10.175.236.175, 69% / 32.4°C.
Initial worker drained, physical pump OFF/unbound and no-entry proof retained.
No guardian/activation/PPS/pump run yet. Fresh boot-bound owner C1 reply precedes
sole guardian start; no manual-handoff timer. Same one300s / hardware1700 /
PPS+raw1800 scope, unconditional exact331/allfive/original181 restoration required.
Evidence-only tests/build executed:false; reuse qualification. Full port NOT_READY.
See Test347 DEPLOYED_STATUS, PREPARED_STATUS and raw admission/installation/park.

2026-10-08 Test347 NATURAL_HEADROOM_READY_AWAITING_PC.
Read-only process 6681 / session 8056 ended normally: 29 samples over 915.390s,
SOC 70→68%, final 31.3°C / 4.009V / −1.332A. Every sample was USB offline,
discharging and from accepted Test331 boot a96de8c0. No Test347 install, reboot,
guardian, PPS or pump command. Target 68 reserves PC/install headroom; the
registered 20..70 admission and unused one300s scope are unchanged. The prior
SOC71 preflight rejection remains preserved. Fresh PC preflight must use a new
namespace before paired install/admission; fresh candidate-bound C1 reply must
precede the only guardian launch. Evidence/docs-only tests/build executed:false;
reuse existing qualification. Full port NOT_READY. See Test347 PREPARED_STATUS
and natural-headroom-1791427878.

2026-10-08 Test347 PC_PREPARATION_MARGIN_PENDING_NO_MUTATION.
OwnerPCreply“已接”; firstreadonlypreflightstopped SOC71>registered70 after
PCcharge, same331a96de8c0/config51/notes03/31.9C/services+rolesnormal. No Test347
recovery/write/modules/reboot/guardian/PPS/pump. Originalsnapshot/exception
preserved, not hardwarechargingfailure oracceptance. Ownerunplugrequested,
natural target68 nowreservesPC/installmargin; existing20..70 admission,
one300s scope/currentcaps/331restoreunchanged. Freshpreflight onlyaftermargin
andPCreturn, newnamespace; do not reuseincompletesnapshot. Evidenceonly
tests/build:false. FullportNOT_READY. See347preflight/admission-status.json.

2026-10-08 Test347 AUTHORIZED_STAGED_NATURAL_MARGIN_READY_AWAITING_PC.
Originalread-only naturalwatch3972/session58323 terminalPASS2312.176s/75samples;
76->70%/31.0C/4.034V/-1.538A, allUSBoffline/discharging/same331a96de8c0.
Rawretained; no Test347preflight/install/newboot/guardian/PPS/pump operation.
OwnerPCreconnect requested; freshidentity/rescue/battery/OFF/preflight required
then onepairedinstall/admission/park. FreshcandidateC1reply precedessoleguard
launch, no humanwaittimer/replay. Existingunusedone300s/currentcaps/331restore
scope unchanged. IndependentACPItool repair recordedbelow; kernel/charging/
frozen347inputsunchanged. Evidenceonlytests/build:false, reusequalification.
FullportNOT_READY. See347PREPARED_STATUS/natural-discharge-1791425171.

2026-10-08 Independent ACPI reporting repair installed during347 discharge wait.
Owner explicitly requested repair of acpi -b. Kernel/UPower percentage already
correct; Debianacpi1.8 ignoredcapacity and calculatedfrommissingchargefields.
PatchedoriginalC nowusesvalidcapacity, retainscharge/energy/procfallback,
reportsunknown time/learnedfull honestly.12actualCLItestsPASS0.522s/ARM64build
PASS; /usr/local/bin/acpi a0f62ffe installedatomically, original/usr/bin unchanged.
NormalPATH/nativeacpi/sysfs/UPower all74%, same331a96de8c0/30.7C/discharging/
USBoffline; no reboot/flash/service/charging/kernelchange,347INPUTS_MATCH.
Naturalwatchsession58323 ongoing;347notinstalled/guardiannotstarted. No full
regression/kernelbuild repeated. FullportNOT_READY. See userspace/acpi and
reference/battery-reporting/acpi-upower-compat/RESULTS.md.

2026-10-08 Test347 AUTHORIZED_STAGED_WAITING_NATURAL_DISCHARGE.
Enrollment978c19ad pushed; Windows347transferstage verified, device stillexact331
lastboot a96de8c0/74%31.5C. No formalpreflight/flash/newboot/guardian/PPS/pump.
Ownerunplug requested; naturallyreach<=70 beforefreshPCpreflight/install. Fresh
C1reply thenimmediateguard/start onthatcandidateboot, no humanwaittimer. Same
unusedone300s scope/currentcaps/331restore; noextraactivation. Reuse60host/79C/
build/W1sparse; stagingresults-onlytests/build:false. FullportNOT_READY.

2026-10-08 Test347 AUTHORIZED_UNUSED_ONE300S_SCOPE_AWAITING_SOC.
Owner original“允许测试，平板为手动关机重启” approvedone actual300s charging
observation;346 workflowtimeouthadzeroentry/PPS/pump and331restored. With owner
portinggoalresumed, sameunusedscope carried to independenthost-only347; no new
ownerreplyinvented/no346replay/noextraactivation/current/duration. Fresh347C1
boot-boundreply stillrequired. Current331a96de8c0/74%31.5C/config51/notes03/ADB
normal; requestnaturaldischarge<=70 beforeformalpreflight/install. Deviceunchanged.
See347AUTHORIZATION/readiness/scope; original346STOP retained. FullportNOT_READY.

2026-10-08 Test347 REGISTERED_READY_AWAITING_NEW_ROUND_AUTHORIZATION.
Independenthost-only workflow: no guardian duringmanualhandoff/OFF-unbound;
freshboot-bound C1reply<=120s/fixed9 precheck thenimmediateguard/solebind.
Launchresponseambiguity persistsoriginalPID/adoptonly/no restart; prelaunch
failure alsoforbids replay. PersistentWSL acceptedpublictrust/no keyscan/copy.
60affectedhost PASS0.361s/Python+shellsyntax/frozeninputs+artifactsPASS. Reuse
exact5c90/b6acboot/4399modules/79C/build/W1sparse/configDT/runtime181; no kernel
or currentpolicychange/rebuild/fullsuite/Actions/deviceoperation/Windowsstage.
executionfalse/newownerroundauthorization required, no auto retryofclosed346.
Device lastaccepted331a96de8c0; futurefreshpreflight/one300s hardware1700/PPS+
raw1800/unconditionalexact331restore. Retention338..347/expired337 retired.
FullportNOT_READY. See347README/OFFLINE_RESULTS/inputs/scope.

2026-10-08 Test346 CLOSED_MANUAL_HANDOFF_TIMEOUT_NO_ACTIVATION_RESTORED331.
Original900s guardianhandoff timeout whileOFF/unbound;0activeframes/noentry/no
activationmarker/noPPS test, not CPU/pumpfailure or300s acceptance. OriginalSTOP
andrawretained/no restart/rebind. Samecandidate0ad61ab7 OFF/unbound/fixed9/68%
29.1C/no newkernelfault; ownerPCreturn then exact331/original181/allfive restored.
Finala96de8c0/WiFi10.175.236.117/69%4.101V30.1C/config51/notes03/DCCabsent/
pumpOFF/rescue/journal/units/WindowsPASS; rollback_required=false. Futurehandoff
workflow review/newregistration/authorization required, no newround here.
Evidenceonlytests/build:false/reuse32host/79C/build/W1sparse. FullportNOT_READY.
See346PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256/raw.

2026-10-08 Test346 STOP_MANUAL_HANDOFF_EXPIRED_BEFORE_ACTIVATION.
Originalguardian1717 finished900s ownerhandoff timeout/cleanup_error=null;
handle absent, samecandidate0ad61ab7/noactivationmarker/noentry/0activeframes.
NoPPS/pump test executed; workflowSTOP not CPU/chargingfailure or acceptance.
Rawguardian/fulljournalretained; samebootOFF/unbound/fixed9/68%29.1C/no new
kernelfault verified. Hosttemporarytrust absent restored onlyfromacceptedkey,
failedquery retained/no keyscan. AwaitPC USB forunconditionalexact331restore,
rollback_required=true; no guardianrestart/rebind/retry. Evidenceonlytests/build:false,
reusequalification. FullportNOT_READY. See346STOP_STATUS/progress/raw.

2026-10-08 Test346 DEPLOYED_GUARDIAN_READY_OFF_UNBOUND_AWAITING_OWNER_C1.
Fresh331683bdd12 preflight68%29.1C/allfive181/confignotes/rescue/WindowsPASS;
onepairedinstall, normalcandidate0ad61ab7/WiFi10.175.236.46/config51/notes10/
allfive181/once300000/uniqueattribution/journalPASS. Preentryworker drained,
physicalOFF/unbound/69%30.2C; guardian1717 exactpathverifiedlive awaitingowner
C1<=900s outside300s. No activation/PPS/pump yet. Scope hardware1700/PPS+raw1800,
one300s only. Exact331rollback_required=true/original181saved. Reuse32host/79C/
build/W1sparse; operationstests/build:false. FullportNOT_READY. See346progress/raw.

2026-10-08 Test346 AUTHORIZED_STAGED_AWAITING_PC_USB.
Enrollment e765eb4b pushed; Windows346 stage verified, no device mutation.
FreshWiFi683bdd12 ownermanualattributed/69%24.8C/config51/notes03match331;
ADBlistempty, pendingPC cableconnection beforefullpreflight/install. Reuse32host/
79C/build/W1sparse; operationresults-onlytests/build:false. No newPPS/pump/reboot.
FullportNOT_READY. See346PREPARED_STATUS/authorized-readiness/PC-connect-wait.

2026-10-08 Test346 AUTHORIZED_ONE300S_ATTEMPT_NOT_DEPLOYED.
Owner “允许测试，平板为手动关机重启” explicitly approves300s and attributes
683bdd12 to manual poweroff/restart. Originalpendingtelemetry retained with
separateattribution. Scope hardware1700/PPS+raw1800/oneactivation/no20min/no
highercurrent/unconditionalexact331 restoration unchanged. Enrollmentrefrozen;
freshPC rescue/identity/SOC20..70 preflight required beforedeployment. Reuse
32host/79C/build/configDT qualification; record-onlytests/build:false.
FullportNOT_READY. See346execution-scope/INPUTS anddevice-statusattribution.

2026-10-08 Test346 REGISTERED_READY_AWAITING_EXPLICIT300S_AUTHORIZATION.
Independent300s guardian/runner/native binding;19new+8parser+5transport=32host
PASS0.211s/syntax/45frozeninputs/artifactsPASS. Old30s grant/witness rejected;
host timeout follows samePID/no restart, primary/cleanup retained. Reuse5c90
79C/build104.643s/W1+sparse15.691s; config/DT/runtime181 unchanged/newmetadata
pairing. Armedbootb6ac504e prepared only, hardware1700/PPS+raw1800 unchanged.
executionfalse/noWindowsstage/flash/PPS/pump; owner300s approval required before
freshPCpreflight and committed/pushed enrollment. Exact331 restoration remains
unconditional after later authorized attempt. Separate ownerunplug telemetry
boot683bdd12 differs from accepted64440dd5; attribution pending, no assumption
of uncommanded reboot. FullportNOT_READY. See346README/OFFLINE_RESULTS/summary.

2026-10-07 bounded-duration candidate READY_OFFLINE_DEFAULT_OFF, source5c90a4b5.
Readonly once_ms accepts30s(default)/300s only;300s requires exclusiveonce,
invalidprofiles refused beforeI2C. Hardware1700/PPS+raw1800 and safety unchanged.
79actualC/23evidence testsPASS; incrementbuild104.643s/W1+sparse15.691s/no warnings.
Exact331config/DT/release/181runtime, protected108/prior37 preserved. DefaultOFF
boot497736be/notes10dcf27f/modules4399bcc1, no opt-in/Windowsstage/deviceoperation.
Device still accepted33164440dd5. Newduration parser explicitwindow, actual345PASS/
344STOP replays preserved; historical345livegate still rejects newkernel.
Next independent300s guardian/runner/registration + explicitdurationauthorization;
no physical300s registration yet, cannot deploy package as armed acceptance.
FullportNOT_READY. See charging/test345-duration-followup RESULTS/PACKAGE/qualification.

2026-10-07 bounded-duration follow-up IMPLEMENTED_OFFLINE_BUILD_PENDING. Immutable once_ms selector accepts30s(default)/300s only;300s requires exclusiveonce, invalidprofile refused beforeI2C. Hardware1700/PPS+raw1800/thermal/fault/PM/lease/refresh reserve unchanged.79actualC PASS0.398s; buildnext using existingcache. Device exact33164440dd5 remains installed, no newdeviceoperation. Future300s physicalauthorization/guardian/registration absent. FullportNOT_READY. See charging/test345-duration-followup.

2026-10-07 Test345 CLOSED BOUNDED_PPS_NATIVE_RETURN_CHARGE_DISCHARGE_PASS_RESTORED331.
Oneactivation9d7a1a38/37activeframes/rawIBUSmax1.770625A/pack29.5C/die43.5C;
five refreshes/sixzero proofs/final357ms deferral/native complete lease0PASS.
PumpOFF/unbound/fixed9input1.5A; ordinarycharge30.845s/discharge15.650sPASS.
LivePCreturn sameboot/ADB/deviceNCM/SinkDevice/WindowsCode0PASS. Exact331/
allfive/original181 restored, final64440dd5/WiFi10.175.236.106/64%32.8C/identity/
rescue/journal/unitsPASS; rollback_required=false. Hardware1700/PPS+raw1800,
no secondactivation/no highercurrent/longduration/calibration/45W acceptance.
FullportNOT_READY. Next separate five-minute conservative duration candidate,
not authorized physical300s by existing<=30s scope. Evidenceonlytests/build:false,
reuse72C/build/20host. See345PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256.

2026-10-07 Test345 native/ordinarycharge/dischargePASS; sameboot discharge15.650s/63%28.2C/-0.840A/offline. Waiting ownerPCreturn for onceADB/deviceNCM and unconditionalexact331restore. rollback_required=true, fullacceptancepending; evidence-onlytests/build:false.

2026-10-07 Test345 NATIVE_AND_FIXED_RETURN_CHARGE_PASS_AWAITING_UNPLUG.
One activation9d7a1a38/37activeframes/maxrawIBUS1.770625A/pack29.5C/die43.5C;
five refreshes/sixzero proofs/onefinal<=2s deferral/native completionPASS.
PumpOFF/unbound/fixed9input1.5A cleanup verified. Sameboot ordinary charging
30.845sPASS/63%4.096V28.7C/no new kernelfault or failedunit. Dischargeobserver
armed; ownerunplug, PCreturn and unconditionalexact331restore pending.
rollback_required=true, not fullacceptance/no replay/no currentincrease.
See345PHYSICAL_PROGRESS/rawguardian/charge. Evidenceonlytests/build:false,
reuse72C/build/20host. FullportNOT_READY.

2026-10-07 Test345 DEPLOYED_PREPARED_OFF_UNBOUND_AWAITING_OWNER_C1.
Gitprotocol500 bypassed via verifiedexact GitAPIobjects/force:false fastforward;
3commitSHA identical/38blobs/origin-test7b32d07f synchronized beforedeployment,
no historyrewrite/Actions. Fresh331PCpreflight59%33.8C/allfive181/rescuePASS.
Candidate9d7a1a38/WiFi10.175.236.233/60%32.9C/config51/notes893c/allfive181/
DCCabsent/unique normalboot/rescue/journal/noCode43PASS. Preentryworker drained,
physicalOFF/unbound; guardian1714 awaiting freshownerC1<=900s. No activation/PPS/
pump yet; hardware1700/PPS+raw1800/<=30s/final2s reserve scope unchanged.
Exact331rollback_required=true/original181saved; reused72C/build/20host,
operationphase tests/build:false. See345PREPARED_STATUS/PUSH_RECOVERY/rawoperation.
FullportNOT_READY.

2026-10-07 Test345 REGISTRATION_PUSH_PENDING_NO_DEPLOYMENT. Local7c596eed
registered/20hostPASS + candidate72C/buildPASS, but remote-test remains01747a5f.
Four normalpushes rejected GitHubInternalServerError (includingHTTP1.1); request
IDs/times preserved345PUSH_STATUS. No force/bypass/Actions/Windowsstage/flash/
PPS/pump. Device stays accepted331beb65af6 after344restoration. Next resolve
ordinarypush then freshPCpreflight/onecandidate; do not weaken registered push
requirement. FullportNOT_READY; no newtest/build for this statusrecord.

2026-10-07 Test345 REGISTERED_NOT_DEPLOYED. Reuse01747a5f/source72C/build/
W1/sparse/config/DT/181, armedsoleonceboot. Guardian validates final<=2s deferral
withoutpark/rearm/extendeddeadline; explicitnativefault pre-scan retains -62
primary on actual344replay, inheritedzero/current/thermal/late-refresh/cleanup
kept.20affectedhosttestsPASS0.256s/syntax/inputsPASS, no fullsuite/Actions/rebuild.
Device accepted331beb65af6/PC54%31.6C, no newphysicaloperation/Windowsstage.
Freshpreflight and pushedregistration beforemutation; ownerC1confirm then one
<=30s/hardware1700/PPS+raw1800 attempt, unconditionalexact331restore. Window336–345,
335noimage/Windowsstage. GitHub500 on priorqualification push; mustresolvepush
before deployment. See345README/registration/OFFLINE_RESULTS/INPUTS/package.
FullportNOT_READY.

2026-10-07 Test344 follow-up READY_OFFLINE_DEFAULT_OFF, source01747a5f.
Final<=2s refresh deferral/freshboottime, unchanged30s/current/faultgates;
72actualC PASS0.441s/incrementbuildPASS101.591s/W1+sparsePASS13.799s/no warnings.
Exact331config/DT/release/181runtime preserved; protected108+priorformal30 intact.
DefaultOFFboot0af5fe72/notes893cb9a2/modules8e289739, no armedflag/Windowsstage/
newdeployment. Device331beb65af6 onPC54%31.6C, no operationafteracceptedrestore.
Future345 plan only, notregistered/activated; do not replay344. FullportNOT_READY.
See charging/test344-refresh-deadline RESULTS/qualification/PACKAGE/SHA256.

2026-10-07 Test344 follow-up OFFLINE_REFRESH_RESERVE_IMPLEMENTED_BUILD_PENDING.
One-shot final<=2s defers nextOFF/PPS/ON transaction, continues100ms safety/WDT
until unchanged30s deadline; freshboottime aftermeasurement. Earlier admitted
refreshoverrun remainsfault, no -ETIME promotion/gap/current gate relaxation.
72actualC testsPASS0.441s incl168ms/boundaries/full delayedAVG window/faults/
no-rearm. Exact331beb65af6 staysinstalled54%31.6C; no newdevice operation.
Protected108/priorformal frozen, samecache incrementbuildnext. Future345 only
independentregistration, never replay344. See charging/test344-refresh-deadline.
FullportNOT_READY.

2026-10-07 Test344 CLOSED STOP_DEADLINE_DURING_PARKED_REFRESH_RESTORED331.
One ownerconfirmed activation41activeframes/maxIBUS1.770A/pack28.6C/die42C;
initial+5refreshes parkedzero proofPASS. Sixthpark195.976859 only168ms before
196145ms deadline; no resume/nativeSTOPprimary-62 cleanup0 lease0, fixedreturn
physical8732mV/rawIBUS0/OFF. Guardian invalidfixedreturnorder masks later native
primary; retainedseparately. Nonclean immutable, no replay/higherpower. Failed
1143row journal CPUfaultcounts empty/nativeSTOP suspect retained. Exact331/
original181/allfive restored, finalbeb65af6/WiFi10.175.236.97/54%31.6C/identity/
rescue/kernelPASS/rollback_required=false. Next offline avoid late refresh start
without extending30s; improve failedtransaction diagnostic, keep gates. Closure
tests/build:false, unchanged68C/15host qualification reused. FullportNOT_READY.
See344 PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256/rawguardian+finalacceptance.

2026-10-07 Test344 DEPLOYED_PREPARED_OFF_UNBOUND_AWAITING_OWNER_C1.
Owner“已同网” restored transport; freshpreflight53%32C/331identity/rescuePASS.
Candidateb7b4fa77/WiFi10.175.236.68/notes92fb/config51/allfive181/DCCabsent/
unique normalboot/fulljournal/rescue/noCode43PASS. Initial preentryqueue drained;
physicalOFF/unbound proof; guardian1770 awaits ownerC1<=900s, no activation/PPS/
pump yet. Hardware1700/PPS+raw1800/<=30s/orderedzero proof unchanged. Exact331
rollback_required=true, original181 saved. Qualification reused, evidencephase
build/tests:false. See344 PREPARED_STATUS/rawpreflight/install/admission/park/arm.
FullportNOT_READY.

2026-10-07 Test344 PREDEPLOYMENT_WIFI_NETWORK_MISMATCH. OwnerPC connected,
ADBsame331dc8442f1/config/notes/52%30.6C; preflight WiFirescue timesout before
mutation. Devicewlp1s0/sshd up10.175.236.14/24, WindowsWLAN changed10.30.254.86/16;
not CPUstall/newcandidatefailure. Freshowner sameWiFi handoff requested; retain
stricttrust, no deviceconfig/reboot/flash/PPS/pump. Hoststageverified, no mutation
state/rollbackrequired. Preserve failedpreflight/pc-transport-recheck-01; fresh
preflight required when transport returns. Evidencephase tests/build:false,
qualification unchanged. FullportNOT_READY.

2026-10-07 Test344 NATURAL_DISCHARGE_READY_AWAITING_OWNER_PC. Finite read-only
watch five packets/125.610s ends75%4.070V26.4C/-1.726A/USBoffline/directN,
exact331dc8442f1 unchanged. No stress/devicewrite/flash/reboot/PPS/pump. Qualified hoststage now verified;
ownerPC handoff and devicepreflight/install not executed. Fresh preparation gate still required after ownerPC handoff; candidate/offline
qualification unchanged, this results phase tests/build executed:false. See344
PREEXECUTION_STATUS/natural-discharge-watch-01/watch-soc.py. FullportNOT_READY.

2026-10-07 Test344 PREEXECUTION_SSH_RESTORED_BATTERY_PENDING, hostrevision2.
WindowsTCP22 open while WSLdirecttimeout; encrypted nativeWindowsPython relay
restores WSL strictSSH/originalkey+trust, exact331config/notes/machine/sameboot
dc8442f1. No keycopy/permissionweakening/relearn/device/network changes. Runner
registered windows-tcp profile;15affectedhost+guardian testsPASS0.257s, no build/
fullsuite/Actions, reuse d60f2641 kernel/68C/config/DT/181. Latest77%4.085V26.5C/
-1.639A/USBoffline/directN; prep75% pending, no stress. No Windowsstage/flash/
reboot/PPS/pump/newkernel deployment; priorconnectivity question resolved,
ownerphysicalPC+C1 confirmations still required. See344 HOST_TRANSPORT_RESULTS/
connectivity-recheck-01/host-qualification and revised frozeninputs.

2026-10-07 Test344 PREEXECUTION_CONNECTIVITY_PENDING, not a physical result.
Candidate qualified/registered/pushed; no Windowsstage/preflight/install/reboot/
PPS/pump. Lastconfirmed331dc8442f1 naturallydischarging80%28.7C; laterreadonly
SSH10.175.236.14 timedout, boundedtwo-pass enrolled/24 scan no trustedendpoint.
Latestboot/pack/CPU stateunknown; do not call CPUstall or newcandidatefailure.
Ownerquestionpending Debian/network/IP/manualreboot or PCreconnect; frozen
hosttrust retained, no blindretry/mutation. Keep75%preparation gate. Source/
build/68C+10guardian qualification remains; results-onlytests executed:false.
See344 PREEXECUTION_STATUS/wireless-readonly-01/status+rawdiscovery.

2026-10-07 Test344 retentioncleanup: expired334 two Windowsduplicates192MiB
and332canonical Image/defaultOFF/armedboot removed after last334consumerexpiry;
5 exacthashed targets,405.11MiB total. No335..344consumer;
source/config/DT/modules/rawlogs/hashes retained,331current/newrollback intact.
No device operation ortests/build. See host-storage-cleanup/
2026-10-07-test344-image-retirement/deletion-manifest/RESULTS.

2026-10-07 Test344 REGISTERED_NOT_DEPLOYED. Reuse source d60f2641 qualified
parked-settle kernel, soleonceboot/offlinepackage. Independent guardian requires
ordered3zero/>=100ms witness before firstON and eachresume; prior1.7Aprogram/
1.8APPS+rawcap/30s/PM/late-refresh/voltage/thermal/identity/cleanup kept.
10 affected guardian testsPASS0.278s, syntax/inputhashPASS;68C/build/W1/sparse/
exact331config/DT/181 reused. No fullsuite/Actions/Windowsstage/device mutation.
Device accepted331dc8442f1 ownerunpluggedPC,naturaldischarge,last80%28.7C;
preparationSOC20..75 gate pending, no stressload. No343replay orcurrentincrease.
Retentionwindow335–344, expired334/332 lastconsumer image retirement pending;
exact331 active/newrollback retained. FullportNOT_READY. See344 README/
registration/INPUTS/EXECUTION_INPUTS/offline-summary/qualification-reference.

2026-10-07 Test343 follow-up READY_OFFLINE_DEFAULT_OFF, sourced60f2641.
Bounded parkedzero wait preserving Fedora AVG32/OFF-PPS-VBUS-ON and old limits;
68 actualC testsPASS0.354s, incrementalImage/DT/181 buildPASS94.976s,
changedW1+sparsePASS14.708s/no newwarnings. Exact331config/DT/release,
protected108+priorformal23 unchanged. DefaultOFF boot6cc62712,
notes92fb9e6f; no armedflag/Windowsstage/deployment/PPS/pump.
OwnerunplugPC,naturaldischarge same331dc8442f1,80%4.163V28.7C/-1.455A;
aboveprep75%, no stressload. Next independent344registration only, no343replay;
fullportNOT_READY, ADCfreshness/calibration and actualparkedsettle unresolved.
See reference/charging/test343-parked-settle/RESULTS/qualification/PACKAGE.

2026-10-07 Test343 follow-up OFFLINE_PARKED_SETTLE_IMPLEMENTED_BUILD_PENDING.
Keep Fedora ab123e7d OFF/PPS/VBUSsettle/ON and AVG32 recipe; new boundedOFF
wait observes3rawIBUSzero over>=100ms (30polls first20 then50ms), refuses
persistentnonzero, all other unsafe readings/I2C/IRQfault/ownership/PM/deadline.
Privatepending result differs from transportEAGAIN; no permission to ignore
nonzero. ActualC mock now models delayed/stuck/oscillating OFF ADC;68testsPASS
0.354s/no skip. Hardware1700/PPS+raw1800/30s/thermal/lease/fixed9 unchanged.
Protected108sources and priorformal hashes unchanged. Incrementalbuildpending,
no deploy/activation/replay343; device accepted331dc8442f1. FullportNOT_READY.
See reference/charging/test343-parked-settle/PLAN/development.

2026-10-07 Test343 CLOSED STOP_PARKED_NONZERO_IBUS_RESTORED331.
Source95159eec hardware1700/PPS1800/rawcap1800 witness; one ownerconfirmed
activation,7 live mode4 frames,maxIBUS1751875uA. First refresh OFF at337.392397s
then native337.460017s rejects OFF/nonzeroIBUS1744375uA; voltage/thermal/current
cap pass that tuple. ADC freshness/current decay unknown, no gate relaxation.
Nativeprimary=-34 cleanup=0 lease=0; physicalOFF/fixed9/rawIBUS0 return proved,
guardian drained/unbound. No resumedrefresh/30scompletion/retry/highercurrent.
Exact331/original181/allfive restored; bootdc8442f1,WiFi10.175.236.14,
78%4.203V31.8C/+0.678A,finalidentity/rescue/kernelPASS,rollback_required=false.
Full failed1154row journal CPUfaultcounts empty; native range/STOP suspects retained.
Closure tests/build executed:false,reuse39host/58C/build; no fullsuite/Actions.
Next offlineOFF/ADCfreshness+vendor/Fedorarefresh analysis; no new registration
or physicaloperation. FullportNOT_READY. See343 PHYSICAL_RESULTS/physical-summary.

2026-10-07 Test343 DEPLOYED_PREPARED_OFF_UNBOUND_AWAITING_OWNER_C1.
Candidate4b6d8165/WiFi10.175.236.169, boot840773ba/config51/notesb8d8/181,
allfive/DCC/rescue/journal/unique normalboot admissionPASS;76%4.176V32.0C.
Initial readinessqueue canceled/drained before entry/STOP; physicalOFF/unbound
proved. Guardian1715 awaits fresh ownerC1confirmation<=900s; no activation/PPS/
pumpON yet. Hardware setting1.7A/request and rawSTOP1.8A/<=30s unchanged scope.
Exact331 rollback_required=true, original181 saved. No charging acceptance;
source/build/39tests qualification reused, no fullsuite/Actions. See343
PREPARED_STATUS/prepared-summary and raw admission/park/arm evidence.

2026-10-07 Test343 REGISTERED_PREPARED_NOT_DEPLOYED. Reuse source95159eec
current-margin Image/notesb8d8d4a0/config51/DT233a/181; offline armedboot840773ba
soleonceflag, no kernel rebuild/change. Independent guardian nativehardware1700/
PPS1800/matchingtarget witness and terminal range-log STOP; rawstop1800000 and
thermal/voltage/gap/no-retry/lease/fixed9/ownerconfirmedOFF-unbound gates retained.
39 affected hosttests PASS/0.455s/no skip/syntax/inputhashes PASS; prior58C/build
qualification reused, no fullsuite/Actions. FreshPCpreflight/push beforemutation.
Device remains3312fc3593e on naturaldischarge,76%26.8C/-1.186A/USBoffline/Good;
not a PC gate and above preparation75% max. No Windowsstage/flash/reboot/activation/
PPS/pump yet. Test342 STOP immutable; fullportNOT_READY. Retentionwindow334–343,
expired333 two Windowsduplicates exact-hashed/retired192MiB;332canonical provider
still334consumer,331 activeproduction/343rollback preserved. See343 README/
registration/INPUTS/EXECUTION_INPUTS/execution-scope/offline-summary/OFFLINE_RESULTS.

2026-10-07 Test342 follow-up BUILT READY_OFFLINE_DEFAULT_OFF, no deployment.
Source95159eec: SM5440 programmed1.7A, PPS/raw stop1.8A unchanged; terminal raw
range logs, no policy expansion. Final58 actualC tests PASS/0.487s;35 unchanged
guardian tests reused from initial93PASS. Incremental Image/DT/181 buildPASS
102.097s, changed-objectW1+sparsePASS/15.453s/no warnings. Exact331 config/DT/
release unchanged, protected108inputs/14formal artifacts intact. DefaultOFF boot
abe828fc/notesb8d8d4a0 paired181; no armedflag/Windowsstage/flash/reboot/PPS/pumpON.
Device stays3312fc3593e on naturaldischarge,76%/27.0C/-1.579A USBoffline/Good.
Proposed343 plan only, not registered physicaltest; do not replay342 or relax
raw1800000 ceiling. No fullsuite/Actions/new cache tree. FullportNOT_READY; actual
current accuracy/regulation margin remains unvalidated. See reference/charging/
test342-current-margin RESULTS/qualification/PACKAGE/SHA256/NEXT_TEST_PLAN.

2026-10-07 Test342 follow-up offline current-margin implementation. Device stays
accepted3312fc3593e on owner-requested natural discharge; strictWiFi packet77%/
4.141V28.3C/-1.647A/USBoffline/directN. No flash/reboot/pump/PPS/devicewrite.
Separate SM5440 programming1.7A from unchanged1.8A PPS/raw stop cap;50mA vendor
encoding,100mA provisional margin not calibration guarantee. Preserve frequency/
ADC/voltage/thermal/lease/30s/no-retry/fixed9 policy. Terminal rejected ranges log
raw625uA/500uV pack/status values without extra bus reads.93 affected tests PASS,
then58 changedC tests PASS after stronger old-register readback case;35 unchanged
guardian tests reused. Build pending using same cache, oldformal artifacts frozen;
protected108kernel inputs unchanged. Future343 plan only, no physical scope or
activation; fullportNOT_READY. See reference/charging/test342-current-margin.

2026-10-07 Test342 CLOSED STOP_ACTIVE_RANGE_CHECK_RESTORED331. One owner-
confirmed activation/PPS9220mV1.8A and short pumpON; raw host ADC IBUS1.84375A
exceeds registered1.8A. Guardian primary activePPSbudget; native primary-34
cleanup0/lease0. Mixed TCPM9220/271mA frame overlaps fixedreturn, exact native
predicate not logged; no host-only PASS or source-withdrew-PPS claim. Native
start-to-terminal1.996855s includescleanup, no30s completion/refresh. PhysicalOFF/
fixed9 verified/drained/unbound, ordinary charging resumed. OwnerPCreturn exact331
allfive/original181 restored; unique normalboot2fc3593e/config51/notes03/DCCabsent/
physicalOFF/ADB/WiFi10.175.236.207/deviceNCM/noCode43/fulljournal/no newfault/unit
PASS,76%4.208V32.5C. rollback_required=false. Full failedboot1139rows retained;
CPU fault counts empty, nativeSTOP remains nonclean. No retry/cap increase/build/
fulltests/Actions/source/config/DT/rootfs/adbd change. Reuse34226tests/339 build.
See342 PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256. FullportNOT_READY.

2026-10-07 Test340 closure retention: expired330 three Windows duplicate images
and old Fedora Image/armed/default-OFF boot retired after exact hashes and no
331–341 PACKAGE consumers; reclaimed approximately501MiB. Current331 production/
rollback and323 secondary remain registered consumers of340/341, not permanent
historical exemptions;339/341 qualified artifacts and source/config/DT/modules/
rawlogs retained. See host-storage-cleanup/2026-10-07-test340-image-retirement.

2026-10-07 Test341 closure retirement: expired331/332 Windows duplicate images
and eligible332 canonical images retired after recorded manifest/hash/no333–342
PACKAGE consumer check. Canonical331 activeproduction/342registeredrollback,
339/342 qualified candidates and all source/config/DT/modules/rawlogs preserved.
See host-storage-cleanup/2026-10-07-test341-image-retirement/summary.json for exact
paths/bytes and any retained consumers. No device/code/test/build operation.

2026-10-07 Test342 DEPLOYED/PREPARED, awaiting ownerC1confirmation. Candidate
2fb982f0 uniquely attributed/config51/notes e014/allfive181/DCCabsent/onceflag/
ADB/WiFi10.175.236.173/deviceNCM/noCode43/fulljournal/pack/OFF PASS,74%4.181V32.4C.
InitialPC readinessqueue canceled/drained and corrected host park proof PASS.
Guardian1696 ready on knownOFF/unbound provider, no marker/bind/nativeentry/PPS/
pumpON. Manualhandoff <=900s while OFF/unbound, only fresh ownerC1confirmation
and fixed9 gates permit sole bind/1.8A<=30s. No341replay/current increase/source
change/build/fullrun/Actions. Test331 rollback_required=true until unconditional
finalrestoration; preparation is not charging acceptance. See342 prepared-live/
preparation-park/mutation-state/PREPARED_SHA256. FullportNOT_READY.

2026-10-07 Test342 owner continues, execution scope recorded independently of
frozen prepared metadata. Fresh331254a7cc9/config51/notes03/DCCabsent/OFF/allfive181/
ADB/WiFi126/deviceNCM/noCode43/fulljournal/no newfault/unit PASS,73%4.175V33.5C.
Reuse exact339 artifacts/26 tests, no new source/build/fullsuite/Actions. Push
scope before stage/install; PCqueue cancellation/OFF-unbound guardian before
ownerC1confirmation, one fresh bind/1.8A<=30s, firstnonclean stops and exact331
unconditionalrestoration. No341replay/current increase. See342 DEPLOYMENT/
execution-scope/DEPLOYMENT_INPUTS. FullportNOT_READY.

2026-10-07 Test342 PREPARED/NOT_DEPLOYED host source-capability correction.
26 affected native/cleanup/thermal/activation/source tests PASS0.213s/no skip;
Python/shell/input hashes PASS. Preentry5V advertised capability<=3A while actual
SM5714 input<=1.8A;9V/source/input/postentry fallback<=1.5A unchanged. Emit rejected
raw sample beforevalidation; bad3A actualinput/source>3A/9V>1.5A still STOP.
Reuse exact339 kernel/config/DT/181/boot/build; no kernel/current/thermal/source/
rootfs/USB/adbd change, fullsuite/Actions or device action. No execution-scope/
Windowsstage/flash/rebind/PPS/pump; needs fresh331 boundary and owner continuation.
Current accepted331254a7cc9 healthy72%/32.1C, rollback_required=false;341 STOP/errors
and missing tuple unchanged. FullportNOT_READY. See342 OFFLINE_RESULTS/offline-
summary/SHA256 and341 physical closure. Current331 production/rollback still used
by342, preserve canonical provider; it is not a permanent historical exemption.

2026-10-07 Test341 CLOSED STOP_PREENTRY_SOURCE_OBSERVER_RESTORED331. Guardian
stopped OFF/unbound on ordinary-source-limit beforemarker/bind/nativeentry/PPS/
pumpON;97 prep samples, rejectedtuple missing. Fullsourcejournal shows implicit
5V/3A budget plus actualinputprogram1.8A then fixed9/1.5A: observer confuses
capability with drawlimit; exact triggering tuple unproven. Owner marker refused
finishedguardian, no replay. AfterPCreturn exact331 allfive/original181 restored,
normalboot254a7cc9/config51/notes03/DCCabsent/OFF/ADB/WiFi10.175.236.126/deviceNCM/
WindowsnoCode43/fulljournal/no newfault/unit PASS;72%4.156V32.1C/+0.871A onPC.
rollback_required=false. Pending/prepared/raw errors retained; no build/fullrun/
Actions/source/current/thermal change. Next prepared342 host-only sourcecapability
and raw rejected-sample correction, not yet deployed. FullportNOT_READY. See341
PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256.

2026-10-07 Test341 DEPLOYED/PREPARED, no PPS/pump attempt yet. Candidateboot
0570988d uniquely attributed/allfive181/config51/notes e014/DCCabsent/normal
onceflag/ADB/WiFi10.175.236.123/deviceNCM/noCode43/pack PASS;69%4.126V32.1C.
InitialPC readinessqueue canceled/drained; corrected mC/deciC park proof PASS.
Guardian1722 armed on knownOFF/unbound provider at /tmp/gts9-test341-monitor;
no activation marker/bind/entry/PPS/pumpON. Await ownerC1confirmation, only then
single fixed9-gated bind; manualhandoff <=900s OFF/unbound, active1.8A<=30s gates
unchanged. Test331 rollback_required=true until unconditional finalrestoration;
never call prepared hardware charging acceptance or reuse STOP340/339boot.
See341 prepared-live/preparation-park/mutation-state. FullportNOT_READY.

2026-10-07 Test341 registered/qualified corrected host thermal units. Exact339
kernel/config/DT/181/boot reused; kernel source unchanged.34 affected tests PASS
0.427s/no skip, Python/shell syntax PASS. Preparation thermistor uses mC while
power_supply uses deciC: factor100, both20–<38C, existing500mC coherence.340 host
unit STOP/result immutable;341 new fresh candidate boot, no replay. Same owner-
confirmed OFF/unbound manualhandoff/one exclusive bind and1.8A<=30s scope; no
fault/thermal/current/deadline relaxation. Current331 f38e35d4 allfive181/OFF/
ADB/WiFi241/deviceNCM/noCode43 preflight PASS,68%4.121V33.1C. Push registration
before mutation; fullportNOT_READY. See341 README/offline-summary/OFFLINE_RESULTS.

2026-10-07 Test340 CLOSED STOP_HOST_THERMAL_UNIT_ERROR_RESTORED331. Candidate
12dbf267 admittedPC, initialqueue canceled/drained beforeentry/PPS/pump. New host
check incorrectly compared thermal32000mC with battery320deciC; both32.0C.
No guardian/ownerhandoff/activation; observer defect, not a battery fault.
Exact331 allfive/original181 restored, normal f38e35d4/config51/notes03/OFF/DCC
absent/ADB/WiFi241/deviceNCM/noCode43/fulljournal/no newfault/unit PASS.68%4.112V
32.0C/+0.840A onPC, rollback_required=false. Firstfailure/input/raw evidence kept;
no340replay. Next independent adapter uses existing ordinary_charge_window mC/
deciC factor100 and500mC coherence, realistic-unit host tests; kernel unchanged.
FullportNOT_READY. See340 PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256.

2026-10-07 Test340 registered/host-qualified confirmed-source activation. Reuse
exact339 Image/notes/config/DT/181/armedboot; no kernel/config/DTS/USB/adbd/rootfs
change or build.33 affected guard/cleanup/activation/adapter/module-slot/script
syntax tests PASS/no skip. Initial healthyPC queue is canceled/drained before
handoff, fulljournal forbids any prior entry/STOP. KnownOFF/unbound guardian then
waits<=900s; fresh boot/token + actualownerC1confirmation and fixed9/pack gate
permit one exclusive bind. New readiness/guardian budget starts after handshake;
1.8A/30s/fault/thermal/no-retry unchanged. No stopped339replay. Current331boot
953185ab,67%4.110V33.1C/allfive181/OFF/ADB/WiFi198/deviceNCM/noCode43 PASS.
Registration/push before new mutation; fullportNOT_READY. See340 README/offline-
summary/OFFLINE_RESULTS. No fullsuite/Actions; protected339inputs unchanged.

2026-10-07 Test339 CLOSED STOP_PREENTRY_WAIT_TIMEOUT_RESTORED331. PC5 throughout
432 samples; readiness deadline expired at source301.280435s primary-110/cleanup0/
lease0; no entry/PPS/pumpON. Guardian drained/unbound and proved preentry ordinary
PC5/OFF without masked fixed9 secondary. Late C1 confirmation remains separate;
no replay/rearm. Initial ADB-absent restoration failed before any recovery write,
preserved in rollback-install; after ownerPCreturn exact331 boot/original181 and
allfive restored in rollback-install-PC-return. Normalboot953185ab uniquely
attributed, config51/notes03/DCCabsent/OFF/ADB/strictWiFi10.175.236.198/deviceNCM/
WindowsnoCode43/fulljournal/no newfault/unit PASS;65%4.082V31.9C/+0.848A onPC.
rollback_required=false. Failed339 full1132rowjournal preserved with native timeout
suspect and no classified CPU fault. No new build/fulltests/Actions/source change.
Next independent registration must keep worker unbound/OFF during manualhandoff,
guardian ready before single activation after ownerC1confirmation; adapter tests
required, not yet implemented/qualified, no automatic new pump attempt. Fullport
NOT_READY. See339 PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256. Retention
330–339;329 unchanged-USB recovery created no kernel image/provider to retire.

2026-10-07 Test339 registered/qualified, not yet deployed: source81583618 fixes
pre-lease sourceENODATA→boundedEAGAIN only; realpack/I2C/activefaults unchanged.
Ordered entry witness beforelease/PPS; new guardian phaseproof afterunbind with
fullsameboot/Linuxstart, preentryOFF offline/PC5/fixed9 permitted; postentry fixed9
strict; primary/cleanup preserved.69 C/guardian+8 adapter/module-swap tests PASS;
build81.955s/staticW1sparse12.881s/no warning; exact331config/DT/release,181archive
58f66same338, protected108/prior23files preserved. No fullsuite/Actions/current
voltage/thermal/DTS/USB/adbd/rootfs change. Owner继续 independently registers
same1.8A<=30s339, no338replay, unconditional331restore. Currentsame331a8c809d1,
62%4.057V32.4C, allfive181/OFF/ADB/strictWiFi250/deviceNCM/noCode43/newfault
preflightPASS. FullportNOT_READY; physical338STOP remains frozen.
See339README and sm5440-preentry-detachRESULTS/PACKAGE/SHA256.

2026-10-07 Test338 CLOSED STOP_PREENTRY_RESTORED331: owner-authorized bounded1.8A
one<=30s pump candidate installed/admitted onPC, guardian armed. Normal PCdetach
returned-ENODATA at73.54s; one-shot wait only handles EAGAIN/ENODEV, stopped
primary=-61 cleanup=0 lease0 at73.954s before any PPS/pumpON.62 samples allOFF.
Guardian unbound but unconditionalfixed9 predicate onONLINE0 masked outererror;
primary preserved in raw events/full1133rowjournal. No charging/retry/currentadvance
acceptance. Exact331 allfive/original181 restored, normalboot a8c809d1 uniquely
attributed, config51/notes03/DCCabsent/OFF/ADB/strictWiFi10.175.236.250/deviceNCM/
WindowsnoCode43/fulljournal/no newfault/unit PASS;58%4.022V29.3C/+0.958A onPC.
rollback_required=false.7 adapter+9 guardian testsPASS, exactbuild/config/DT reused,
no rebuild/fullsuite/Actions/source policychanges. Next separate repair: pre-entry
ENODATA boundedwait only, preserve actual/active faults; guardianprimary/cleanup
separation and OFF/offline pre-entry cleanup, then re-register (no338replay).
FullportNOT_READY. See338PHYSICAL_RESULTS/physical-summary/PHYSICAL_SHA256.
Retention329–338; expired328 Windowsimage duplicates retire separately, canonical
Fedora images still consumed by330 remain.

2026-10-07 Test338 PREPARED/NOT_EXECUTED: bounded Fedora-source1.8A pump
candidate cf02c822 qualified. Default-false direct_charge_once exclusive mode:
one<=30s software budget/100ms monitoring/500ms gap stop, raw625uA current,
traced init readback, pre/postON pack/ADC, firstfault terminal/no restart/resume,
parked4s refresh refuses deadline rearm.284 affectedC/host +44 guardian/window/
discovery/module-slot tests PASS/no skip; build81.939s, W1+sparse12.793s/no warning.
Exact331config51/DT233a/release/181 runtime/protected108+formal16 preserved.
Armedbootf7c5e153/notes03846e81 only once opt-in; no deployment/Windowsstage/
reboot/devicePPS/pumpON. Current strictWiFi166 same331boot6dc80750/config51/notes03/
normalcmdline/DCCabsent,58%3.883V24.4C/discharging; nativeADB empty, no complete
new allfive/181/OFF preflight. This is preparation, not a338 physical failure.
Explicit new pumpON scope + fresh rescue/identity/pack preflight required; no
scope copied from337, no current increase/automaticactivation. Software monitor
is not hard-realtime cutoff; vendor needs SW OCP, actual protection/current/
calibration remain untested. FullportNOT_READY. Registered <=30s attempt +30s
ordinary return/15sunplug/unconditionalexact331 restore. Latest physical337
CLOSED PASS and retention328–337 remain authoritative;338 is current prepared
consumer. See sm5440-bounded-directRESULTS and test338README/PACKAGE/INPUTS.

2026-10-07 Test337 CLOSED PASS_RESTORED_ACCEPTED331 within registered pump-OFF
scope. Native8940mV/1800mA→ADC9267/fixed9proof/lease0 PASS; verified ordinary
reprogram0.046988s later, fixed9 charging30.925s/30samples PASS, unplug15.641s
PASS/sameabf8901d, enum8warnings0. No pumpON/high-current/calibration acceptance.
Exact331boot025e/notes03/config51/allfive/original181 restored; normal boot
6dc80750 uniquely attributed, ADB/strictWiFi10.91.255.166/deviceNCM/noCode43,
physicalOFF/PPSfalse/normalcmdline/fulljournal/no classifiedfault/unit PASS.
Final57%3.965V28.1C/+0.954A on PC; raw SOC across boots is not capacity proof.
Mutation rollback_required=false. Driver/config/DTS/rootfs unchanged thisphase;
tests/build executedfalse/reused295+65/offlinebuild/static, nofullrun/Actions.
Window328–337 expired327 Windows duplicate images192MiB removed; canonical
327-origin files still consumed by in-window328/330 preserved, plus331/323/337.
Original336STOP kept. No automatic new pump/current scope. FullportNOT_READY.
See337PHYSICAL_RESULTS.md/physical-summary.json and test337-image-retirement.


2026-10-07 Test337 unplug PASS/same abf8901d: offline/discharging held
15.641s, endpoint62%/4.002V/24.9C/-0.628A,
realpack/OFF/fulljournal/no newfault/unit gate. Charge/native PASS already archived.
137 samples include pre-unplug wait; actual15s separately measured. Await PC
reconnect for unconditional exact331 restoration; installed337/rollback_required
true. No replay/source/build/host rerun/pump or current advance. FullportNOT_READY.
See337discharge/RESULTS.md and summary.json.


2026-10-07 Test337 candidate abf8901d uniquely attributed, WiFi10.91.255.27.
Native singlePPSOFF8940mV/1800mA→ADC9267→fixed9OFFproof/lease0 PASS;
ordinary reprogram log 0.046988s after native terminal. Healthy ordinary fixed9
30.925s/30samples PASS, input1.5A, endpoint61%4.086V25.3C/+2.067A,
packnormal/SinkDevice/pumpOFF. Enum8warnings0/fulljournal/no newfault/unit gate.
Unplug15s and unconditional exact331 rollback still pending; installed337,
rollback_required=true. No source/build/test rerun; no pump/current advance.
See337charge/RESULTS.md/native-recovery-timeline.json. FullportNOT_READY.


2026-10-07 Test337 correction installed after owner scope/fresh331 gate:
candidateboot39bf8476/notes39a825d1/paired181, allfive readback/BCBclear/root
unmount PASS; original331181 preserved, exact331 rollback staged. CurrentlyTWRP,
await owner PC→C1 (C2empty)→System once. No native PPS/pumpON yet. Single pump-OFF
transaction/10ssettle+30scharge/15sunplug/unconditional331restore remains scope.
No driver/config/DTS/rootfs change; tests/build not rerun. Installation evidence
archived; retire expired327 when337 closes. See337installation/RESULTS.md and
mutation-state.json; rollback_required=true. FullportNOT_READY.


2026-10-07 owner “继续，设备已连接电脑” continues registered337 single
pump-OFF PPS/fixed-return scope. Fresh exact33124545782/config51/notes03/allfive/
181/normalcmdline/Code0/ADB/strictWiFi10.91.255.52/deviceNCM/OFF preflight PASS,
59%4.007V28.5C/+1.273A. New337 execution-scope binds frozen INPUTS; no old336
scope reused. Install staged candidate39bf8476+paired181 only afterpush; stopTWRP
for ownerC1→System once; unconditional exact331 restoration. No pumpON/current
advance. Scope/results only; reused295+65/build/static, no rerun/CI/Actions.
See337DEPLOYMENT.md/execution-scope.json/active-preflight.json. FullportNOT_READY.


2026-10-07 Async-fixed-restore correction OFFLINE PASS/source86f7b678:
295 affected actual-C/host PASS6.526s;65 final admission/window PASS0.442s,
no skips. Build81.492s/W1+sparse13.395s no warning. Exact331 config51/DT233a/
release unchanged;paired181/module runtime allocations/107protected+17formal
preserved. Armedboot39bf8476/notes39a825d1 is PPS-OFF-only, not defaultproduction.
Independent Test337 PREPARED/registered, flat-discovery admission corrected;
unchanged/missing/extra boot history/transport stops tested. No execution-scope
file, no Windows stage/device commands/flash/reboot/PPS/pumpON in this phase.
Installed331 last physical proof remains336 final24545782; current live pack/
transport not recollected. Fresh gates plus explicit337 PPS-OFF scope required.
Single transaction/10ssettle+30scharge/15sunplug/unconditional exact331 rollback;
no current/timeout/thermal/float/config/DTS/TCPM/USB/adbd/rootfs change.
No routing/fullrun/Actions. Original336 STOP/source/runner/inputs unchanged.
Latest completed physical336 window327–336; prepared337 images are a current
candidate consumer, retire expired327 when337 physically closes. FullportNOT_READY.
See charging/sm5714-async-fixed-restoreRESULTS and test337README/PACKAGE/INPUTS.


2026-10-07 Test336 follow-up implemented: async release queues one locked
ordinary reconfiguration even with cached fixedPD; acquire/revoke cancel it,
normal temp/fault/PM/grant gates and prior program-loss budget preserved.
sm5714-usb declares PD_PPS; host fixed gate uses ONLINE/contract rather than
source capability label.295 affected tests PASS/no skip6.526s; no routing/fullrun.
Candidate build/qualification pending in sm5714-async-fixed-restore namespace;
installed device remains accepted331, no new device command/flash/PPS/pumpON.
Historical336 runner/error/inputs unchanged; next admission needs flat-result
integration before Test337 registration. No automatic current/pump advance.



2026-10-07 Test336 CLOSED: STOP_RESTORED_ACCEPTED331. Native single pump-OFF
PPS8920mV/1800mA→physical fixed9 proof/release PASS; ordinary switching did not
recover (uptime118.09s: Not charging/-0.959A/input100mA despite fixed ONLINE1).
Original admission KeyError(identity) retained; missing read-only sameboot
proof only, no repeat PPS/boot, no completed30s/15s acceptance.412 enum8 warnings.
USB_TYPE PD_PPS is source capability, not active PPS proof. Follow-up targets
async-release poller reconfiguration, declared USB enum and flat discovery
integration; source gap is inference, not captured internal flags. No fix yet.
Exact331 boot025e/notes03/config51/allfive/original181 restored; normalboot
24545782 attributed, ADB/strictWiFi10.91.255.52/deviceNCM/WindowsCode0/physicalOFF
PASS,58%4.021V27.9C/+0.957A. No classified kernel fault/suspect/failedunits.
Mutation rollback_required=false. No new device experiment or pump/current
advance. Evidence/docs only; executed:false, unchanged qualification reused.
Window327–336 expired326 four exacthash images removed324132788bytes; current
331/323/qualified336 preserved. See336PHYSICAL_RESULTS.md/physical-summary.json
and2026-10-07-test336-image-retirement/. FullportNOT_READY.


2026-10-07 owner authorized “重启并继续测试”. One unchanged331 normal reboot
3d359c92→90274be1 uniquely attributed; normal cmdline/config51/notes03 recovered,
fresh allfive/181/nativeADB/strictWiFi/deviceNCM/WindowsCode0/OFF/pack preflight
PASS. Six endpoint packets16.427s;57%4.010V28.3C. Inline capture's duplicate final
pump filename STOP retained; only missing final read-only evidence supplemented
sameboot/no second reboot; device scope PASS, no retrospective host PASS.
Registered336 PPS-OFF scope recorded/pushed96991b9d; qualified candidate staged
and installed after fresh gate. Allfive readback/paired181/BCBclear/root unmount;
currently TWRP, awaiting owner C1-only→System once. Candidatebootffb7bc94,
notes59a97374/pps_return_check sole opt-in/directOFF. No PPS or pumpON yet.
Unconditional exact331 restore remains required after this one run. New phase
evidence only: no build/test rerun/fullsuite/Actions. Retire expired326 images
when336 completes; preserve current331 rollback and qualified336 consumer.
See336installation/RESULTS.md, mutation-state.json and normal-boot-recovery/.

2026-10-07 owner returnedPC;336 read-only preflight STOP exact cmdline:
newboot3d359c92 has lpcharge1 vendor tokens. Accepted331 config51/notes03,
allfive/181 match; nativeADB/strictWiFi10.91.255.247/WindowsCode0, physicalCNTL5
01OFF/directN/checks absent, fulljournal no faults/suspects/failedunits. Initial
56%3.969V25.4C/+0.935A. No flash/reboot/PPS/module/rootfs change; not a physical336
failure. Preserve stopped packet, do not relax normal-cmdline gate. Separate
one unchanged331 normal-reboot proposal awaits owner approval; no automaticrepair
or Test336 PPS authorization inferred. No build/tests rerun for evidence only.
See336preflight/RESULTS.md and normal-boot-recovery-plan.json. FullportNOT_READY.

2026-10-07 Test336 PREPARED/REGISTERED for one pump-OFF PPS API transaction,
native ADC/ordered fixed9 proof/release, bounded10s ordinary settling+30s charge,
15s unplug, unconditional exact331 allfive/181 restoration. Frozen candidate
4d058527/armedbootffb7bc94/notes59a97374 reused; no kernel/config/DTS/rootfs changes,
no Windows stage/new build/fullrun/Actions/physical execution/PPS/pumpON.
Independent PPS-aware parser/observer and336 module slots; enrolled-key discovery
and first-STOP gates retained.57 affected host tests PASS; syntax/input artifacts
match. Current read-only preparation ADB empty/known-IP+boundedWiFi timed out;
missing temporary trust restored from accepted334 key, no new enrollment.
Current device identity/pack not reconfirmed; last accepted installed331/physical335
remains historical status. Await PC/currentWiFi and fresh baseline preflight;
explicit Test336 PPS-OFF execution scope required before stage/install/admission.
No automatic direct charging/current advance. FullportNOT_READY.
See reference/boot-tests/test-336-pps-off-roundtrip/README.md and RESULTS.md.
Image-retention latest completed physical round remains335; prepared336 creates
no new image/copy. Apply the327–336 window retirement when336 is executed/closed.

2026-10-06 PPS-OFF-return candidate OFFLINE qualified; source4d058527,
readonly/defaultfalse/exclusive pps_return_check, one existing worker/300s/one
owned PPS call/ADC-only/zeroON, terminal fixed9 proof/release and separate errors.
263affectedC+10entry PASS, cached build83.583s/W1+sparse13.524s no warnings,
config/DT equal331/181 paired/108protected+17formal unchanged. Armedbootffb7bc94,
notes59a97374; rollback331025e/181. Helper03f8d9bf bounds10s healthy-charge
settling before30s;335 sealed. No device commands/flash/PPS/ON/new buildtree/
fullrun/Actions; latest physical remains335 and installed331. Proposed336 needs
separate registration and explicit PPS-OFF scope; no automaticactivation or
pump/current escalation. FullportNOT_READY. See sm5440-pps-off-returnRESULTS.


2026-10-06 Test335 DEVICE_SCOPE_PASS on unchanged331f1/config51/notes03:
fixed9 switching30.244s/30samples, unplug15.675s, pumpOFF/PPSfalse, no new
kernel/unit fault, final68%/4.055V/24.9C/-0.615A. Original runnerSTOP early
negativeFG current at first9V retained; published supplement collected missing
first30s without new attach/flash/reboot, not retroactive clean. 53host reused,
no build/fullrun/Actions/driver change. Native334proof not replayed. Futurehost
admission needs bounded healthy-charge settling; no automaticPPS/current advance.
FullportNOT_READY. Expired325 Image/boot122.8MB removed exacthash/no current
consumer;331/323/334 retained. See335RESULTS/summary and cleanup record.


2026-10-06 Test335 REGISTERED: same accepted331f1 boot/config51/notes03;
read-only fixed9 switching30s then unplug15s, new bounded enrolled WiFi helper.
No flash/reboot/kernel/rootfs/native-check/PPS/ON/current change; Test334 native
proof retained and original transportSTOP sealed. 53 affected tests PASS; reuse
unchanged build/allfive/181 qualification, no fullrun/Actions. Physical not yet
executed; next arm and owner C2 action only. FullportNOT_READY. See335README.


2026-10-06 host discovery cd667ae7 read-only livePASS: previousIP19→current163
matched32.154s/drained32.156s, strict same331f1e9a45a/config51/notes03/machine/
boot, TCPpeak≤16/23affectedtests. No reboot/flash/charging replay/PPS/ON/build/
fullrun. ADB bootstrap absent (rawpreserved), authenticatedknownWiFi fallback;
69%24.6CDischarging. New helper ready for separately registered use, no historical
334 verdict rewrite/cause overclaim. Next ordinaryfixed9 30s observation on331
without nativecheckreflash, no PPS/current advance. See wifi-discovery-recoveryRESULTS.


2026-10-06 host-only WiFi discovery correction OFFLINE qualified23PASS0.112s.
New charging_wifi_discovery.py: recentIP directstrictSSH, fallback RFC1918-/24,
TCP3s/16workers/SSH2slots/shared90s/two passes, perattempt JSONL, identity/boot/
enrolledkey unchanged-file gates, cancellation drains children. No kernel/charging/
rootfs/USB/ADB/config change; sealed333/334 untouched/no build/fullrun/Actions.
Next one read-only oldIP19→current331 identity discovery check afterpush; no
reboot/flash/PPS/pump or nativecheck replay. FullportNOT_READY; prior334 cause
not uniquely proven. See reference/charging/wifi-discovery-recovery/README.


2026-10-06 Test334 native fixed-return PROVEN, series STOP hostWiFi90s,331 restored.
Unique216deecd native10.642744s: source9/lease1/VBUS9.427V/3samples121ms/
range9427..9427/rawIBUS0/OFF, then lease0/PPS0/ON0 completion. No30s host
observation, not fullscopePASS or PPS transition/calibration. PCcapture68%/4.103V/
29.7C, OFF01, WiFi19; priorSSH probe raced registeredrecovery and is inconclusive.
Allfive/181 exact331 restored uniquef1e9a45a: config51/notes03/checkabsent/directOFF,
68%4.103V29.7C/+0.796A, ADB/WindowsCode0/deviceNCM/strictWiFi163/fulljournal/
failedunits empty/no newfault. Rollbackfalse;334-original consumed,331-original323
retained. Source/build/55host reused. Next bounded hostdiscovery correction (0.4s/
254burst suspect, cause not uniquelyproven), no unchangednativecheck reflash or
autoPPS/current escalation. FullportNOT_READY. See334RESULTS/summary/nativeproof.


2026-10-06 Test334 paired install complete after pushed8c647724. Allfive/181
verified, BCBclear/rootunmounted, staysTWRP awaiting owner C2-before-System boot;
no host Systemreboot. Exact331 saved334-original;331-original323 secondary
untouched. No physical proof yet, rollbackrequired. PumpOFF/PPSfalse/30s/native
300s/pack gates unchanged. No build or repeatedhost regression. See334INSTALLATION.


2026-10-06 owner continues Test334 after preparation9a135c1b. Fresh append-only
PC preflight same3ae598ff,67%4.097V30.5C, allfive/181/OFF/ADB/deviceNCM/strict
WiFi238/WindowsCode0/fresh334slots. Execution record pushed before deployment;
reuse48cc5d16 build/55host qualification, no kernel/config/power changes. Install
once then pauseTWRP; owner C2-before-System boot, fixed9 OFF proof+30s and exact331
restore mandatory. No PPS/pumpON/current progression. Not physically accepted.


2026-10-06 Test334 PREPARED ONLY, no recovery/reboot/partition/module write.
Owner asks prepare next test. Fresh PC preflight on accepted331 same3ae598ff:
66%4.079V29.0C/+1.050A, exactallfive/181/OFF/ADB/WindowsCode0/deviceNCM/strict
WiFi238, fresh334slots. Reuse48cc5d16/3fe4adf1/config51/notesff/DT233a/181;
55affected hostPASS0.275s/no kernel build/fullrun. Added pre-recovery SOC≤75
margin; native/physical<80/<4.3V/20–<38C/300s/30s/OFF gates unchanged. Appended
preflight-refresh namespace/hash pointer preserves preparation evidence and
retains600s freshness; obtain fresh preflight before later execution instruction.
Primaryrollback331, explicitly assigned323 secondary; no PPS/current progression.
Ready for new charger-first OFF-only scope, not full port READY. See334README/
preparation-summary. No physical Test334 outcome yet; Test333STOP sealed.


2026-10-06 Test333 completed STOPPED entry limit, exact331 restored. Candidate
unique49c58e20 onC2: SOC80/4.288V27.4C/fixed9budget1.5A; native10.470670s
-ERANGE/lease0, exact native field unlogged. No proof/30s/PPS/pumpON; rawOFF01.
Allfive/181 exact331 recovery and unique3ae598ff accepted: config51/notes03/no
checkflag/directOFF,81%4.263V30.7C/+0.764A, ADB/WindowsCode0/deviceNCM/strict
WiFi238/fulljournal/failedunits empty. Rollbackfalse;333-original consumed,
331-original323 secondary retained. 43runner+5restore tests, existingkernel
qualification reused/no build/fullrun. Next naturalSOC margin suggested≤75,
fresh registered entry gates; no auto PPS/current increase. FullportNOT_READY.
See333RESULTS/summary; historical pending states below superseded.


2026-10-06 Test333 STOP at charger System boot49c58e20: SOC80/VBAT4.288V/
pack27.4C/fixed9budget1.5A. Native -ERANGE(-34)/lease0 agrees entry refusal;
read pump OFF, fulljournal preserved. No physical proof/30s acceptance/PPS/ON.
Owner returnedPC. Exact331 restoration registered with separate normal baseline
endpoint (SOC≤100/VBAT≤4.44V); candidate bring-up <80/<4.3 gates unchanged,
restoration helper rejects candidate phase. Five affected tests PASS, no build.
Rollback pending; no repeated Test333 or automatic escalation. See333 restoration.


2026-10-06 Test333 charger-attached fixed9 OFF check registered. Reuse unchanged
48cc5d16/3fe4adf1/notesff706409/config51/DT233a/181 qualification. 43 affected
host tests PASS (0.263s); no rebuild/full run. Install pauses in TWRP; owner
attaches C2 18W/C1empty before single System boot. Native300s/physical proof/
30s/OFF/thermal/identity gates unchanged. Strict enrolled private-/24 WiFi
admission preserves unique boot history; complete journal retains early proof.
No PPS/pumpON/current raise. Restore exact331 after owner PC return regardless
of result;331-original323 secondary retained. Registration333README; no physical
acceptance yet. Installation completed: allfive/181 verified, BCBclear/root
unmounted, stays in TWRP awaiting owner C2-before-System boot. No host System
reboot issued; exact331 saved333-original, rollback required. Fresh preflight
READY same205a2404,79%4.254V32.3C, exact
allfive/181/OFF/ADB/deviceNCM/strictWiFi55/WindowsCode0, fresh333slots.
This is already-fixed9 return, not PPS transition/calibration.


2026-10-06 Test332 stopped before fixed9 acquisition; exact331 restored.
Candidate48cc5d16/3fe4adf1/paired181 PCstartup healthy7b5eef2d, but two host-only
pre-collection defects (strict trust path, ramoops substring) consumed wait;
both corrected/tested37PASS with originals preserved, no kernel/reflash/replay.
Native301.280545s fixed-check wait expired onPC5,ret-110/lease0. No fixed9
proof, lease acquisition, PPS or pumpON. Allfive/181 exact331 restoration,
unique205a240476ea4aaeb60e0e913a8cc2a8, defaultOFF/no fixed-check flag,76%
4.203V31.2C/+0.930A,ADB/deviceNCM/strictWiFi55/Windows normal.332original
consumed,331-original323 retained. FullportNOT_READY. Next new OFF-only scope
must attachC2 before manualSystem boot inTWRP, then pinnedWiFi journal/30s;
reuse48cc5d16 build, no changed power policy or repeated PCboot deadline.
See Test332RESULTS; original hostfailures/deadline are not a fixed9/ADC failure.

2026-10-06 Test332 OFF-only fixed9 return scope registered/preflight READY:
source48cc5d16 defaultfalse/readonly fixed_return_check, mutual exclusion with
direct/PPS activation, one existing worker transaction/300s absolute probe
wait/no retries. Only checkedOFF+existingADCchannelsdf+lease/pack/fixed proof/
release; no init/reset/PPS/ON/currentraise. 253affectedPASS/build80.690s/
W1+sparse12.810s zero newwarning; config/DT identical331/181 matched. Newboot
3fe4adf1 single fixed-check flag, notesff706409; default-directN. 35runner tests
PASS, kernel qualification reused. Fresh preflight same331boot6b76a591,
73%4.180V32.2C/+1.171A, allfive/181/OFF/strictWiFi193/WindowsCode0,332slots
fresh. Register/push before installation. Owner C2alone after armed observer,
30s healthy fixed9 after source-bound release; complete journal/native physical
proof required. Unconditionally restore exact331 OFF boot+paired181 afterward;
331-original323 secondary retained. No physical execution yet. FullportNOT_READY;
this cannot establish PPS voltage transition or calibration. See Test332README.

2026-10-06 fixed-return gate correction OFFLINE qualified, source9901200d:
shared fixed5/9V steady window±5% (USB-IF Table4.6, source-receptacle rule,
not ADC calibration), Fedora producer three consecutive rawIBUSzero samples
across≥100ms/range≤100mV; fresh≤100ms/source/lease/pumpOFF intact. 248affected
hostPASS5.748s/build80.757s/W1+sparse14.443s zero newwarning; exact331config/DTB,
181 module archive identical,839protected/22formal unchanged. New defaultOFF
boot167730dd in out/boot-bundle-x710-fedora-fixed-return, no deployment.
Device same331boot6b76a591,67%4.116V32.3C/+1.239A,checkedCNTL5=01OFF,
ADB/services/roles normal. Next separately register actual pump-OFF fixed-return
proof, then boundedPPS; PPS ADC/request mismatch stillunresolved. No current/
ADC/safety/config/DTS/rootfs change, fullportNOT_READY. Earlier ±100mV entries
are historical gate/result records; do not overwrite sealed Test330 failure.
See reference/charging/sm5440-fixed-return-window/RESULTS.md.

2026-10-06 Test331 defaultOFF physicalPASS retained: corrected1f1d8568 candidate
025ebea4+paired181 installed via TWRP/allfive/BCBclear/unmount, unique67673895→
6b76a591f91648c0917d207b772175b4. Exactconfig51ba6a9c/notes03c9c46e/defaultN/
sm5440-fedora, fourCNTL5=01OFF across30.508s, endpoint62%4.059V31.9C/+1.264A/
PCinput1.8A. NativeADB/WindowsCode0/deviceNCM/WiFi193 authenticated, failedunits
empty/fullkerneljournal/no newfault. Original323181 saved .gts9-test331-original,
rollbackfalse/retain candidate;323formal boot+archive remain. No PPS/pumpON/
ADC/current/proof change or kernel rebuild. 27newhostPASS and187/build reused.
Independentfixedreturn proof stillunresolved/fullportNOT_READY; this accepts
OFF-only scope, not activePPS. See Test331RESULTS/summary.


2026-10-06 Test331 independent defaultOFF PC acceptance registered after owner
continue-testing. Reuse corrected1f1d8568/11c5967f artifacts/187tests/build/static;
no PPS/pump/currentraise or proofrelaxation. Fresh331 module backup slots, each
collision checked independently (hostfixture exposed compound-and/set-e bug).
27hostPASS; candidate025ebea4/config51ba6a9c/notes03c9c46e/paired181; exact323
rollback. PC30s/fourOFF samples/newunique boot/fulljournal/deviceNCM, firstfault
restore. Baseline initialreadonly67673895/passive/60%4.045V32.4C/charging/ADB.
PreflightREADY67673895/61%4.053V32.3C, exactallfive/181/OFF/strictWiFi/
WindowsCode0/nativeADB/no kernelfault;331slots absent. Registerpush before
mutation. FullportNOT_READY, independent
physicalfixedreturn proof unresolved. Registration331; historical330 sealed.


2026-10-06 offline PPS adapter correction: kernel1f1d8568/current observer11e2ce1d.
Both pack coherence reads use leased PPS API after handoff; fixed-only mock now
reproduces former-EAGAIN. Newcurrentguard uses ONLINE mode/capability distinction,
requires actual switching recovery; sealed328/330 unchanged. 187affectedPASS,
83.454s ARM64 build/13.115s W1+sparse no warnings, config+DT identical testedFedora,
181paired/runtimechecked; defaultOFF package in out/*-fedora-snapshot-fix.
Physical±100mV fixedreturn timeout independently unresolved; +272mV test still
OFF/leaseheld/timeout. No ADC/current/safety/TCPC/USB/rootfs changes or device
commands/replay. Lastaccepteddevice323 per330restore, no freshliveclaim.
FullportNOT_READY; next independently justified/registered return-proof scope,
not pump escalation. See reference/charging/sm5440-pps-snapshot-fix/RESULTS.md.


2026-10-06 Test330 STOP firstrealPPSfailure: TCPM ONLINE2/8.72V/1.8A observed2
samples, directstart-11/physicalfixedreturn-110, switchinginhibited. Guardian
firstfault/unbind and cleanupfailure preserved;169samples/noON/no30s pumpwindow,
no retry/currentraise. Pack27.9–31.7C/3.903–3.971V/noCPUfault. OwnerC1unplug/PC,
exact323boot+saved327original181/allfive/BCB/unmount restored; uniquely67673895,
54%3.954V30.6C/passiveOFF/ordinarycharging/nativeADB/no43/deviceNCM/WiFi109,
rollbackfalse. Saved327original consumed, failedFedora181 at327tested; formal
artifacts retained. Sourceaudit finds PPS finalcoherence uses fixed-only API,
observer wronglyuses PPS-capableUSBTYPE as active; physical100mV proof timeout
also unresolved. No ADCrepair/relaxedproof/sourcefix/replay in thisstoppedseries.
Results/ANALYSIS330; nextphasecorrectadapter/observer offline, fullportNOT_READY.


2026-10-06 Test330 c064e61a boot-only opt-in installed, allfive readback/181
unchanged/BCBclear/rootunmount; new32a075d2 uniquelyfrom222efdcc. Correctordered
cmd/confignotes, FedoraY but PC CNTL5=01 OFF,54%3.960V30.5C, ADB/no43/WiFi108/
deviceNCM healthy. Device-local guard armed in /tmp/gts9-test330/capture;
awaitownerC1alone/C2empty, wait240s,30s PPS1.8A then finallyunbind/OFF/fixed9.
rollback_requiredTRUE; afterownerPC return defaultOFF327restore or firstreal
PPSfault323boot/saved327original181. Guardexpiry is not permissiontoactivate;
checkstatus first. No new kernel/driver/rootfs/USBchange;38affectedhostPASS.


2026-10-06 Test330 new independent firstPPS1.8A/30s registration after328host
separatorbug. Only hostidentity compares exactordered tokens afterone opt-in;
allflags/order/duplicates/confignotes/safety preserved. Exact328guard/payload/
181/source reused, nobuild/driverchange. New330 namespace/hardlinkedstage,
registerpush before oneinstall; PCbootOFF/armedWiFi beforeC1. PASS327defaultOFF
restore, firstrealPPSfault exact323+saved327original181. Current222efdcc327OFF,
52%29.4C/WiFi150/nativeADB/no43. FullportNOT_READY; physicalawaitregistration.


2026-10-06 Test328 STOP_HOST_CMDLINE_WHITESPACE beforePPS: boot-onlyopt-in
4d64e996 exactconfig/notes/orderedtokens exceptflag, bytecomparison rejected
one/twospaces. No newkernelfault or charger/PPS/pumpobservation. Originalerror
andfulljournal retained. Automaticexact327defaultOFFrestore completed allfive/
181/BCB/unmount; normal222efdcc,52%3.937V29.4C/FedoraN/OFF/nativeADB/no43/
WiFi150/deviceNCM healthy,rollbackfalse. Next host-only parserfix and separate
Test330 registration; do not rewrite STOP/replay PPS or rebuildkernel.


2026-10-06 Test328 resumed preflight READY after ownerdischarge and PCreturn:
accepted327/329boot094c2a35,52%3.928V29.4C, ADB/Windowsno43/WiFi152 healthy,
allfive partitions/exact181/confignotes/OFF match. Original highSOC/Code43
incidents retained,329 ordinaryrecoveryaccepted; noTest328mutation yet. Reuse
unchanged registered328opt-inboot c064e61a and34hosttests, nobuild/fullsuite.
Next oneboot-only install then armedWiFiguard before ownerC1attach,1.8A/30s;
firstfault cleanup and exact323restore, PASS327defaultOFFrestore. No limitraise.


2026-10-06 Test329 deviceUSBrecovery PASS: one ordinaryunchanged327 reboot,
7f9c0caa→094c2a35 uniquelyattributed, sameconfig51ba6a9c/notes5ec694b4/normalcmd,
FedoraN/CNTL5=01 OFF. NativeADB/WindowsCode0/WiFi152/deviceNCM/15s endpoint/no
newfault;84%4.294V30.9C/input1.8A/pack+1.105A. Early7.64s SSHactivating/WiFinotready
hostgateerror preserved, missingready evidencecompleted within150s sameboot,
no secondreboot/reflash/retest. No software/rootfs/USBchange/PPS/pumpON. Retain
327defaultOFF, rollbacknotneeded; notpermanentUSBfix. Test328stilluninstalled/
unstarted, SOC84 fails PPS<80, no thresholdraise. Results329; fullportNOT_READY.


2026-10-06 Test329 registered one unchanged327 ordinarywarm reboot for persistent
incomingCode43 after ownerportretry. WiFi7f9c0caa healthy/defaultOFF, latestSOC83;
ordinaryrecovery20–<95 distinctfromPPS<80 (notwaived). No flash/BCB/rootfs/gadget/
adbd/config/module changes/PPS/pumpON. One uniqueboot/nativeADB+Code0/WiFi/device
NCM/15s endpoint/fulljournal, firstfailure stops/nosecondreset. Existing gate/
parser reused, build/testsfalse. Physicalawaitregistrationpush. Test328 unstarted.


2026-10-06 Test328 incoming PC USB Code43 before mutation; no flash/PPS/pump.
Same327boot7f9c0caa/config51ba6a9c/notes5ec694b4/WiFi224 healthy, FedoraN/
CNTL5=01 OFF,75%4.153V25.5C. Windows descriptorfailure/ADBempty despite device
UDCconfigured/usb0up; full journal no newfault. RawUSB/PnP/service/kernel/OFF
saved usb-incident-01; PnP event-log queryunavailable explicitlyrecorded. Await
one owner20s cable/otherdirectPCport reconnect, requirefresh nativeADB/no43
before anyPPSdeployment. No livegadget/adbd reset/configchange; fullportNOT_READY.


2026-10-06 Test328 registered first Fedora PPS1.8A/30s; source376693d7 and
qualificationf105ffed unchanged. Boot-only opt-in, exact327 config/DT/notes/181;
no source rebuild/ADC repair/current ramp. PCpreflight79%4.234V31.2C/WiFi224,
allfive/181/OFF healthy. Device-local observer finally drains worker/unbinds,
checks OFF+fixed9V; firstfault stops. After ownerPCreturn restore327defaultOFF
onPASS, exact323+saved327original181 onrealPPSfault. Registrationb33b6d65 pushed;34 affected runner/guardian PASS. Fresh PC
follow-upSOC81%4.232V31.7C/paramN/same327boot; entry blocked before any
mutation, await ownerunplug/discharge78%. PhysicalNOTEXECUTED. Plan/reference test-328-fedora-pps-short; fullportNOT_READY.


2026-10-06 Test327 physical default-OFF PASS; pushedregistrationbd4251e6/source376693d7,
paired boot181 installed/TWRP/allfive readback/BCBclear/rootunmount/one normal
7f9c0caa uniquelyfrom3233f4cf492. Fedora0-0063 ID0x21/paramN/CNTL5=01/OFF across4
samples;30.480s PC ordinaryinput1.8A/packpositive1.192A/84%4.296V31.9C. ADB/
deviceNCM/newWiFi224authenticated/Code0/no newkernel fault; retainedcandidate,
rollback_requiredfalse. Exact323boot + .gts9-test327-original181 kept. Earlier
hostWiFi163/refusedoldprovider reader errors archived, no mutation/replay there.
21new runner testsPASS, reusedoffline build/155tests/configDT/181/protectedaudit,
no rebuild/full suite. PPS/pumpON nottested/customADCroute stopped. Owner asked
USBunplug forSOC<80 before separate1.8A registration; no threshold/current ramp.
RESULTS327; full higher-power hardware NOT_READY.


2026-10-06 Test327 registered Fedora source default-OFF PC acceptance; source376693d7/qualificationf105ffed reused,21 new host PASS0.003s/no kernel rebuild. One pairedboot181 install/normalstartup/30s pack+OFF/ADB+deviceNCM+WiFi; retain onlyPASS, exact323 first-failure rollback. NoPPS/pumpON/ADCrepair; ordinaryflashSOC20–<95 separated from futurePPS<80. Device still3233f4cf492 at initial read82%/4.276V32.2C. NewWindowsstage327; finalpreflight83%/4.290V32.2C/allfive181/pumpOFF/ADB+authenticatedUSB NCM pass. HostWiFi unreachable retained; PC-onlyOFF stage allowsNCM rescue, no wirelessPPS grant. PhysicalNOTEXECUTED untilregistrationpush.


2026-10-06 Fedora X710 source route now supersedes custom ADC repair: kernel source
376693d7 imports ab123e7d SM5440 charging worker, continuous ADC and PPS/settle/ON
with current TCPM/switching lease integration. Isolated sm5440-fedora profile,
default direct_charge=false/read-only boot opt-in; compiled activation exists,
not a closed passive-only profile. No device commands/deployment/PPS/pump ON in
this source port; live accepted323 final3f4cf492 retained. Fixed5V1.8A/9V1.5A,
SM5714 float4.44/thermal unchanged; initial PPS cap1.8A/8.2–10.5V. OFF/fallback/
watchdog/suspend veto/backoff fail-closed. 155 affected PASS6.912s; final15 metadata
suite PASS0.289s overlaps155. ARM64 final PASS75.858s; W1/sparse PASS12.344s/no
warnings; exact DTB,181 runtime modules,59 protected/37 formal,only6 expected
config deltas. Host-only metadata/results reuse final build. Formal candidate
out/kernel-x710-fedora + boot-bundle-x710-fedora, UNREGISTERED; no new Windows
copy/full tree. reference/charging/sm5440-fedora-port/RESULTS.md + next plan.
Do not replay326 or rewrite its timeout; next separate registration checks this
new source then conservative PPS. Full hardware port NOT_READY.


2026-10-06 Test326 STOP_NATIVE_100MS_TIMEOUT; two startupconfirmations completed,
nativeattempt1count0/error-110/cleanup0OFF0. Candidate d25fc7ec raw/sourcejournal
retained. Finally restored323boot/181/allfive/BCBclear/rootunmount; finalnormal
3f4cf492/75%4.180V30.3C/ADB+NCM+WiFi, rollbackfalse. Owner directs same-model Fedora
SM5440/PPS source; stop custom ADC repair/replay. Keep323 livebaseline until new
candidate qualified/registered. NoPPS/pump/current/USBchange326. FullportNOTREADY.


2026-10-06 Test326 boot/181 paired modules installed via TWRP; allfive readback
verified, BCB cleared/root unmounted, no automaticcandidateboot. Awaiting owner
C2bootSystemonce/hold>=30s thenPCreturn sameboot; captureonce and unconditional
exact323 restoreinfinally. DeviceTWRP/rollback_requiredtrue; original323 saved
.gts9-test326-original. Installation results archived; unchanged qualifications
reused, build/testsfalse. No PPS/pump/current/protection/USB change. FullportNOTREADY.


2026-10-06 Test326 registered exactf338eeb3 completeddiagnosticdispatch/newunique
closingproducer; qualificationee59e368 reuse88actualworker tests+ARM6481.920s/
W1sparsePASS/exactconfigDTB181/59protected37formal.22newpacket/parserPASS0.058s,
no kernelrebuildforregistration. Fresh323normalabc27877/allfive181/confignotes/
71%4.148V31.5CGood/ADBWiFiNCMWindowsCode0/input1800fast115float45. OneC2candidate
boot/30s->PCretainedADCcapture andautomaticfinallyexact323restore, no325replay/
PPS/pump/current/protection/USBchange. Notinstalledyet; stage325verified/renamed326
no duplicateWindowscopy; retention317–326,316hadno standaloneimage. FullportNOTREADY.


2026-10-06 Test325 STOP/nativeattempt0count0, exact323 restored normalabc27877/
70%4.127V29.3C/ADB+NCM+WiFi/allfive181/rollbackfalse. Rawcandidateboot/config/notes
uniquehistory proof; duplicateboot-end hostproducer bug retained, normalized
onlyderivedanalysis with3matchingIDs. InitialOFF9.437V/REVBLK/livecleanfault,
VBAT4.0795/gauge4.160V gap80.5mV. New9Ventryadmitted/pending2 butgenericfault
recheckusedordinaryPC classifier, immediately fault1/no confirms/native. Not100ms
failure/CPUcause/calibration. Nextfixbothdispatch sites andactualfullworker mock,
newregistration singleclosingmarker. No repeat325/PPS/pump/current/protection/
USBchange. RESULTS325/fullportNOTREADY.


2026-10-06 Test325 candidate boot/181 installed viaTWRP, allfive readback match,
BCBclear/rootunmounted; no automaticcandidate reboot. OwnermustC2bootSystemonce,
hold>=30s afterlogin thenreturnPCsameboot. CurrentdeviceTWRP/rollback_requiredtrue;
accepted323original181saved .gts9-test325-original, independent311backupretained.
Fresh68%4.111V30.0CGood/allfive/rescue entry. Captureonce rawbeforeparse and
unconditional323restoreinfinally, manualTWRP ifrescue lost. No newPPS/pump/current/
protection/USB grants. CURRENT_STATUS325/installation evidence; build/testsfalse
reuse exactqualifiedinputs. FullportNOTREADY.


2026-10-06 Test325 newretained-evidence fixed9V OFF registration: reuse80d590f0/
d910fe06 candidate;32new runner/parser/cleanup testsPASS0.092s, no kernelrebuild.
Freshaccepted323 normal4cf32922/confignotes/allfive181/68%/pack30.0CGood/input1800/
fast115float45/ADB+WiFi+NCM+WindowsCode0. OneTWRPboot-only181 install thenownerC2
bootonce, hold>=30s andreturnPCwithoutreboot; no staleDHCPcollector. Actualkernel
source timestamps mustspanfour100ms native samples/fixed9 budget/2newsameclass
confirmations; latePCpacket distinct. Unconditional323restoreinfinally; first
faultstops/no replay/PPS/pump/current/protection/USBchange. Candidate not yet
installed; live323 retained. Windows324completedstage verified/renamed325/no
second248MBcopy. Registration325, currentretention316–325. FullportNOTREADY.


2026-10-06 isolated fixed9V startup correction source80d590f0 qualifiedoffline:
onlyONESHOT acceptsOFF8.5–9.5V initialinactiveREVBLK then2freshclean/sameclass/
unchangedcontrols/5s; ordinaryPC3predicates/converter/rearm/PM unchanged.158affected
PASS6.601s; finalARM64PASS60.731s; W1/sparsePASS/no warnings/exactobjectrestored.
SameTest324config/exact323DTB/181runtime/59protected/30formal verified. Newformal
out/kernel-x710-oneshot-fixed9 and boot-bundle-x710-oneshot-fixed9; samecache reused,
not oldprovider. No physical325 registration/deployment yet; deviceaccepted323
4cf32922 retained,324STOP preserved. No PPS/pump/current/protection/USB change;
NEXT_PHYSICAL_PLAN needsnewregistration. FullportNOTREADY.


2026-10-06 Test324 stopped and exact accepted323 restored. OwnerPCreturn recovered
originalcandidate eb24355a, normal/exactconfig/notes/uniquejournalhistory;
nativeattempt0/samples0, initialOFF9.4V/REVBLKlatchevent/livecleanfaultcontext
outsideordinaryPC4.5–5.5Vclassifier, NOT100mstimeout. ADC4.009V/gauge4.087V gap78mV
notcalibrated. Full1103kernelrows/noCPUfaultsignature preserved; originalWiFistop
notrewrittenPASS. Frozen0725runner restored323boot/saved181/allfive,BCBclear/root
unmounted. Finalnormal4cf32922/exact323identity/64%4.076V30.9C/ADB+NCM+WiFi;
rollback_requiredfalse, ordinary323retained. Separatehostaddressfix15PASSafter
physicalrestore, no repeatTest324. Nextdiagnosticonlyfixed9startupclassification
mustrequiretwofreshcleanconfirmations/unchangedcontrols; noordinary/100ms/
PPS/pump/thermal/current/USBchange. RESULTS324/fullportNOTREADY.


2026-10-05 Test324 ownerreports fixed9V boot Debian, but authenticatedWiFi
collector failed150s/registered address; boundedsubnetTCP22 foundnone. STOP,
no candidatebootID/ADC/kernel yet; no CPUcause or ADC/chargingPASS inference.
Owneraskedcharger->PC withoutreboot for originalboot evidence then exact323
pairedrestore. Currentruntime unverified; rollback_requiredtrue .gts9-test324-
original saved. No secondboot/rebind/PPS/ON or blindwrite; manualTWRP ifrescue
unavailable. CURRENT_STATUS324/rawfirstfailure; unchangedqualifications reused,
build/testsfalse. FullportNOTREADY.


2026-10-05 Test324 candidate boot/181 installed, allfive readback verified,
BCBcleared/rootunmounted; currentdeviceTWRP R52X10045LT awaiting ownerC2fixed9V
boot, NOTaccepted Debian candidate. Exact323 original181saved .gts9-test324-original,
323 rollbackboot sealed; original311independent saved remains. No automatic
candidate reboot/PPS/pump/current/protection/USB change. Build/testsfalse for
installation, reuseab30aff2+9registered tests. On capture/firstfault requirePC
reconnect and unconditional exact323 restoration; no secondcandidateboot/replay.
CURRENT_STATUS324 and rawinstallation evidence. FullportNOTREADY.


2026-10-05 Test324 isolated native one-shot fixed9V registration prepared:
oneTWRPboot-only/181 install with no automatic candidate reboot; owner switches
PC->acceptedC2 inTWRP and bootsSystem once, WiFi captures four READY/checked100ms
transactions +15s endpoint. Unconditional exact323 boot/saved181/allfive restore.
Fresh fca646a8 normal59%4.034V31.9C/preflightallfive181/rescue/WindowsCode0 and
input1800/fast115/float45 confirmed.9new parser/lifecycle/current323 baseline
PASS0.042s; unchangedab30aff2 build reused. Registration test324-native-oneshot-off,
Windowsgts9-test324; no physical mutation yet. Currentdevice323 retained;
no PPS/pump/current/protection/USB change or calibration/OCP grant. FullportNOTREADY.


2026-10-05 native single-shot OFF candidate qualified offline (not deployed):
new isolated SM5440_ADC_ONESHOT_TEST invokes unchanged100ms converter four times
with pack/source brackets and terminal cleanup; no native actuator/controller,
PPS/ON/OCP/calibration grant.139affected PASS6.485s; ARM64PASS78.783s, W1/sparse
known upstreamVDSO only; exact323DTB, only newONESHOT absent->y,181paired runtime,
59protected/23formal preserved. Current ordinary323 fca646a8 unchanged, latest
PCnet+1.238A/56%/32CGood. Read-only0c control data are stale startup-fault cache,
not ADCselfclear proof. Candidate out/kernel-x710-oneshot and boot-bundle-x710-
oneshot; evidence reference/charging/sm5440-native-oneshot. Test324 needs one
qualified fixed9V OFF acquisition and exact323 paired rollback; no speculative
mask/ENHIZ/protection/charging/USB change. FullportNOTREADY.


2026-10-05 post323 one bounded read-only ADC context captured: actualordinary
MSK1..4=00/00/00/00, ADCCNTL1=0c/ADCCNTL2=df, ID21/MODE01beforeafterOFF.
VendorMSK4f8diff now measured, not proven historicaltimeoutcause; no maskwrite/
ADCstart/INTread/PPS/ON or fresh/calibration/OCP grant. Same323identity; existing
12script tests reused, build/testsfalse(resultonly). reference/charging/
sm5440-adc-completion-audit/ordinary323-context/. FullportNOTREADY.

2026-10-05 Test323 PC fixed5V source-budget candidate physically accepted and
retained: newnormal fca646a8-8cc0-405c-814d-36cde33baa9e, config31d5a9419dbe027e4c3d735a363b490c9484584152d22bb83eb990c092076132,
notesd8e5fcf394811878c0368d8bd1db461e79e29a2cf949dc493256924f464d51f9,
exact311DTB, boot+181matchingmodules readback/otherfourunchanged. TCPM5V1800,
hardwareinput1800/fast115/float45/Q4mode verified admission+endpoint,60s/four
snapshots bracket74.52s net+1.022..1.323A/SOC49->50/30.2..31.2C/Good. ADB+NCM
(device/hostSSH)+freshWiFi+WindowsCode0; fulljournal/attributedboot/no newkernel
signature/programdrift. PPS/pump/native remainOFF; no TCPC/USB/DTS/adbd/rootfs/
thermal change. ActualUSBwatts NOTmeasured. Current baseline now ordinary323,
not old311 config/notes;311 original308 exactrollback .gts9-test323-original
preserved. Results323;build/hostqualification reused, no repeatedfullchecks.
FullportNOTREADY: ADC/current/calibration/cutoff/PPS/pump/faultPM acceptance remain.
Expired312/313 threeimagecopies removed223462033bytes per cleanup2026-10-05-test323.


2026-10-05 Test323 same ordinary PC candidate registered for one boot-only +181
matched swap; no repeat normalization/rebuild. Wi-Fi address now included in
bounded150s readiness then authenticated fresh rescue.20affected gate/startup
PASS0.032s, exact precedingbuild reused. Fresh aca39fe7 normalpreflight49%3.867V
30.5C, allfive/181/config/notes/SinkDevice/packthermal/ADB+WiFi/NCMdevice/Windows
confirmed; oldphysicalinput500 despite grant1800. Retain only after capped hardware
controls,60s four sameboot snapshots/netpositive endpoint/fullkernel; failure
restores accepted311, no PPS/ON/ADC/native/USB/rootfschange. Staging322 renamed323
no duplicate. FullportNOTREADY. Test322STOP preserved; windows314–323.


2026-10-05 Test322 stopped before flash at early Wi-Fi admission. One unchanged
normal boot nowaca39fe7, lpcharge0/exact311 identity,49%3.870V30.4C, late Wi-Fi
10.139.153.254/authenticated/oneattributed boot/full kernel no new CPUfault.
Late recovery is not322PASS; no module/bootwrite/PPS/ON. Evidence322 RESULTS.

2026-10-05 ordinary PC candidate/Test322 registered:
85419619 correction rebuilt in reused308 passive cache PASS89.513s;49passive
PASS1.807s, previous109charging reused,14newgate/runnerPASS0.033s. Exact311DTB,
onlyRAW/TIMING absent->n config entries;181paired runtime unchanged/BTFchanges,
57protected/48formal frozen. Native controls absent/PPS/pumpclosed. Offline
boot-only out/boot-bundle-x710-pc-ordinary, qualified out/kernel-x710-pc-ordinary.
Owner charged/reconnected; actualADB9e6e4813 sameaccepted311 config/notes,
49%3.877V30.4CGood,lpcharge1; TCPM5V1800 versusUSB500/net−517mA. WiFi10.139.153.35,
SinkDevice/NCM/restoredADB. Pushed322 permits one unchanged normalreboot then
fresh normalSOC>=20%/rescue/allfive181 admission, boot+paired181,60s observedPC
program/netcurrent acceptance; first devicefailure restores311, no PPS/ADC/ON.
Test311 original308 currentrollback attached to322 retention; never reuse308
cacheasoldprovider. Current device still311 until newresults. FullportNOTREADY.


2026-10-05 source-authorized fixed5V budget correction qualified offline:
SM5714 ordinary configuration now gives existing TCPM5V>500mA authorization
precedence over SDP/UNKNOWN/CDP, capped1800mA; lower pack target rises only to
capped grant. DefaultSDP500, fixed9V1500/pack2100, DCP2100, float4440, thermal500/
fail-closed/PM/PPS switching inhibition unchanged. Test307 raw historical grant
3000->1800 alongside500 charging supports underuse, not current PC capability.
Twelve pre-fix actual-C failures;109 affectedPASS4.604s/0skip; old500 recovery
assertions retained plus higher-grant exact assertions. ARM64PASS76.045s;
W1/sparsePASS6.998s known upstreamVDSO only, standard object exactly restored.
Patch checkpatch clean; seven unchanged whole-file baseline styleCHECKs recorded.
Exact preceding native config/accepted311DTB/181paired/56protected/42formal preserved.
Formal out/kernel-x710-pc-current/, evidence reference/charging/x710-pc-current/.
No device deployment/USB/TCPC/DTS/config/rootfs/PPS/ON; grantsclosed. Owner current
low-battery shutdown requires accepted18W recharge/normalSOC>=20% entry before
physical source-grant/5V charging acceptance. Current PC port remains unknown.
Full port NOT READY: ADC/current/calibration/cutoff, PPS-OFF/pump/faultPM and
higher-power acceptance remain. No new cache tree/Windows staging/Actions.


2026-10-05 native cancellation/queue-refusal increment qualified offline:
active cancelled sessions refuse new controls; an active regular queue refusal
keeps EBUSY and schedules once-only terminal OFF/fixed/release. Twelve actual-C
pre-fix failing subcases reproduced; 29 affected controller tests PASS 0.442s,
unchanged prior dependencies reused by exact hashes, not a new full regression.
ARM64 PASS 85.446s; W=1/sparse PASS 7.014s, known upstream vDSO warning only;
standard flags restored after debug-only object differences. Exact preceding
native config/accepted311 DTB/181 paired files/56 protected/36 formal preserved.
Formal out/kernel-x710-cancel-drain/, evidence reference/charging/x710-cancel-drain/.
No device/SM5714/TCPC/DTS/config/USB/adbd/rootfs/current/thermal/PPS/ON changes;
activation/OCP grants remain closed. Full port NOT READY: physical ADC/current/
calibration/cutoff and separate PPS/pump/fault/PM/higher-power acceptance remain.
Owner now attributes current access loss to low-battery shutdown; recharge using
accepted 18W supply before physical normal-entry checks. This does not attribute
previous unaccounted boot changes. PC port capability remains pending; review
found possible valid 5V grant underuse via SDP clamp, but no blind current raise.


2026-10-05 native real pack current now retained/bracketed/mandatory in actual
controller/core/actuator/supervisor/paused resume: both acquisitions refused
independently, invalid reads erase previous current, raw refusal telemetry.
Six actual-C missing-current guard cases reproduced before fix. Signed±3.6A
bringup envelope/sourcecc_gl=2*ci_gl, not vendorOCP/current programming; vendor
preset actually target_ibus*50/100 audit corrected.351 affectedPASS11.072s/0skip,
ARM64PASS90.621s/W1sparse7.376s knownVDSOonly/checkpatch0. Exact previous native
config/accepted311DTB/181paired/53protected/30formal preserved. Formal
out/kernel-x710-pack-current/, evidence reference/charging/x710-pack-current/.
Same native cache now this provider, not old303. No SM5714/TCPC/DTS/config/USB/
adbd/rootfs/device/flash/reboot/PPS/ON/Actions change; native/OCP grantsclosed.
FullgoalNOTREADY: physicalADC/current freshness/calibration/cutoff, independent
PPSOFF/<=1.8A pump/faultPM/higherpower stillrequired. Latest owner reconnect access
unavailable/current IP/power/boot replypending; do not deploy until normal entry.


2026-10-05 owner replied reconnect complete; endpoint capture 114135Z STOP:
nativeADB list empty/filteredWindowsPnP no match; expandedWindowsUSB/context
20s timeout preserved, Code43UNKNOWN. Wi-Fi last10.139.153.84 No route before
auth; no currentboot/identity/battery/deviceUSB/journal, no CPUstall proof.
Prior113152Z same5e039c8f lpcharge1/0%3.213V/30.5C/net−351mA retained separately,
not a current observation or shutdown-cause proof. Owner screen/IP/reboot reply
pending. No automatic recovery/flash/reboot/service/config/ADC/PPS/ON; tests/
buildfalse (evidence only). reference/charging/usb-reconnect/20261005T114135Z/.


2026-10-05 ADC context read stopped before registers because boot changed to
5e039c8f-c138-47d2-9629-3a07ae6162ff. Sameaccepted311 config/notes,lpcharge=1,
1%3.409V29.2C/PCnet−239mA. No agentreboot; ownercause/recharge reply pending.
Full prior/currentkernel and prior systemjournals saved; late shutdown.target is
user@0.service/PID2614, NOT systempoweroff proof. Actualmaskvalues UNKNOWN.
VendorMSK4F8 is a missing comparison fact, notproven READYcause. Single bounded
readonly scripts/sm5440-adc-context.py ready;12testsPASS0.029s, no kernel/build/
DT/config/USB/charging change. reference/charging/sm5440-adc-completion-audit/.
No write/ADC/PPS/ON/flash or automaticrecovery; no relaxed100ms/READY/grant.
Battery recovery/normal-entry attribution first; fullgoalNOTREADY.


2026-10-05 retained native active-session integration now preserves ownership
across actual entry/monitor/paused refresh-retarget/resume/stop, native owned
source+switching binding outsideio_lock/epoch mapping,20ms monitor/4s paused
retarget; once-only terminal OFF/fixed/release and PM/cancel drain. Pending paused
OFF ADC cleanup omission reproduced in actualC, fixed by cancelling both converter
contexts; no altered hardware limits. Kernel controller/native/OCP grants remain
closed/no public setter; mock-only grants excluded from build. 325 affectedPASS
10.256s/0skip, ARM64PASS79.796s/W1sparse7.416s knownVDSOonly/checkpatch0.
Exact previous native config/accepted311 DTB/181paired/53protected/24formal preserved.
reference/charging/x710-active-session/,out/kernel-x710-active-session/. No
physical deployment/PPS/ON/rootfs/USB/Actions; currentordinarydevice unchanged.
FullgoalNOTREADY: physicalADC/calibration/current/protection/cutoff qualification
then independent activation/PPSOFF/<=1.8A pump/faultPM/higherpower stillrequired.
Same native cache reused; old303 provider identity not revived.


2026-10-05 latest owner-confirmed USB reconnect endpoint passes nativeADB/Windows
composite+ADB+NCM Code0/Up/interface-bound NCM SSH/authenticatedWi-Fi, sameecaa3c64
accepted311 config/notes/SinkDevice/DCCabsent/pumpOFF. Battery0%/3.226V/30.8C/Good
and PCnet−119mA: no deployment/reboot; asked owner to recharge on accepted18W C2.
Read-only evidence reference/charging/usb-reconnect/20261005T105902Z/. First Wi-Fi
host tempfile-path error preserved, corrected pinned retry succeeds. Endpoint
only/no permanentfix or cycle timing claim. No device mutation; tests/buildfalse.


2026-10-05 native OFF coordination worker now links real source/pack/SM5440
owner/ADC/switching lease/TCPM PPS/fixed-return operations, explicitly requested
only under X710_NATIVE_CONTROL. Generation/provider checks, timeout cancellation
and once-only cleanup/PM drain; unknown OFF prohibits voltage/release, unresolved
ownership blocks retry. Native raw VBUS/die exported without rounding proof.
313 affected PASS11.044s/0skip +17 native export PASS0.765s; ARM64 modules
PASS60.247s/W1sparse7.702s only known upstreamVDSO warning. Exact prior native
config/accepted311 DTB/181 paired,53 protected/18 formal hashes preserved.
reference/charging/x710-native-controller/,out/kernel-x710-native-controller/.
No device operation/flash/PPS/ON/rootfs/USB/Actions. Direct remains unarmed,
OCP/calibration/cutoff unaccepted; retained ACTIVE/park/resume and scheduled
monitor/refresh integration still required. Full goal NOTREADY; not a direct-
charge release or new physical result. Same native-profile cache reused.

2026-10-05 native SM5440 hardware executor now linked to actual bound I2C/map/
poller ownership under new isolated sm5440-native-control/X710_NATIVE_CONTROL.
Old offline-policy control meaning/frozen quiesce/rearm/converter unchanged;
no old tests changed. Native generation/token/lifetime/drain/cached-request
exclusion/PM cleanup/terminal OFF-first restore implemented; WRITE_ONCE owner
publication. Default native actuator has no activation/lease/OCP grant; START/
RESUME/PAUSE/active-monitor refused, no auto API calls. Final535 related PASS
16.673s/0skip +16 native PASS0.761s after publication;
ARM64 PASS78.340s, W1/sparsePASS, knownvDSOwarning only/checkpatch0.
Config vsobserver only NATIVE absent->y; vsaccepted311 alsoPOLICYn->y/CONDITIONn
->absent; DTBidentical/181paired/runtimebytes unchanged beyond BTF/buildID/debug;
builtinmetadata matchesobserver. Protected51/formal27 preserved; helpers only
comment updates. reference/charging/sm5440-native-control/, formal
out/kernel-sm5440-native-control/. Existing303named cache now this profile's
provider, NOT old303/observer. No device/flash/reboot/PPS/ON/rootfs/USB/Actions;
current accepted311 baseline not changed. FullgoalNOTREADY: real source-bound
controller/transaction workloop/fixedfallback + physical ADC/current/cutoff/OCP/
PPS/ON/higherpower acceptance stillrequired. Do not deploy/arm from these logs.

2026-10-05 subsequent owner-confirmed PC USB reconnect endpoint passes once:
same ecaa3c64 accepted311 config/notes/cmdline, nativeADB, Windows composite/
ADB/NCM Code0/Up, interface-bound NCM SSH banner and authenticated Wi-Fi.
Pack16%/3.699V/31.3C/Good, PCSDP500mA net-349mA; below20% deployment gate,
no flash/reboot/reset/service/config/PPS/ON. SM5440 OFF/IBUS0/fault0.
Full1108-row journal, prior1104 exactcursorprefix, four ordinary screen/stack
rows/no new detected CPU signature. Endpoint only, physical-cycle timing and
permanent USB fix unproved; prior display faults UNKNOWN. Evidence
reference/charging/usb-reconnect/20261005T070314Z/; tests/build executed:false,
noActions. Offline native-observer/control integration remains unfinished.

2026-10-05 native charging observation worker now actually linked under existing
X710_CHARGING_POLICY profile: native source/pack/OFFfresh ADC bracket, exact
instance/generation/PDO/budget/lease consistency, queued-token cancellation,
500ms waiter timeout without another ADC, PM drain/resume-no-restart. No automatic
sampling/lease/PPS/ON/charging controls. Final189 affected PASS4.367s/0skip
incl15 threaded actual-C observer tests; ARM64 PASS168.276s after correcting
kernel current macro collision and adding that macro to fixture. W1/sparsePASS,
knownupstreamvDSOwarning only; checkpatch0. Exact embeddedconfig/Test303 nodiff;
vsaccepted311 only POLICYn->y/CONDITIONn->absent(!POLICY dependency). DTBidentical,
181paired files;167module BTF/build-ID/DWARF directory offsets differ, all other
runtime bytes/shape/relocations/nondebug symbols unchanged; collector inlining
proved byDWARF + actualnative references. Protected61/formal20 preserved.
Qualification reference/charging/x710-native-observer/, formalout/kernel-x710-native-observer/.
Reused303named directory now new native-observer provider, not oldTest303; keep
this incremental policy cache for actual unfinished integration. Original303/
accepted311/RAW formal outputs retained. No device mutation/flash/reboot/Actions/
newfullrun; previoushistoricalfullNOTPASS unchanged. Current accepted311 device
fromTest321 unchanged. FullgoalNOTREADY: actualcontrol/actuator/monitor/fallback
integration and physicalADC/current/cutoff/OCP/PPS/ON acceptance stillunfinished.


2026-10-05 owner-confirmed PC USB reconnect endpoint passes a single read-only
capture on same Test321 final ecaa3c64: accepted311 config/notes/normalcmdline,
nativeADB shell, Windows composite/ADB/NCM Code0/Up, interface-bound NCM SSH
banner and authenticated Wi-Fi10.139.153.84. Pack20%/3.730V/31.6C/Good with
PCSDP500mA and net-381mA; pumpOFF/IBUS0/fault0. Full1104-row kernel journal,
exact1067-row prior cursor prefix,37 extra rows without new detected CPU fault;
known startupMDSS/SMMU UNKNOWN unchanged. Endpoint recovery only, no captured
physical-cycle timing/permanent USB fix. No reboot/flash/service/config/PPS/ON,
no new host/kernel/Actions. Evidence reference/charging/usb-reconnect/20261005T055849Z/.


2026-10-05 Test321 physically executed once and PASSED OFF raw transport scope:
candidate6d6fe2e7 exact config/notes/normal/181/uniquehistory; eightreads0READY,
42polls/507ms transaction/61ms rearm, firstread23ms fromenable,next59ms from
previousreadend,1ms readbrackets. Nativeepochs stable,0c/df exactADCrestore,
error/cleanup0. VBUS4.941V/IBUS0/die25.5C,VBAT3.5350–3.5355V(oneLSB),nativepack
3.705–3.747V: OFF difference170–212mV, notcalibration/fresh/coherent100ms/OCP
proof, nooffsetfix/grant. Candidate15s endpoint/ADB/deviceNCM/hostNCM/roles/
realthermal/controls/DCC/noCode43 pass. Exactaccepted311 originalboot/181/allfive
rollback completed/BCBclear/unmounted, finalecaa3c64 normalidentity/uniquehistory/
20%3.710V29.8CGood/pumpOFF/fault0/rescueWindowsCode0, freshauthenticated Wi-Fi
10.139.153.84. rollback_required:false. Outerzshstatus-variable assignment
failedafterPythoncontrollercompleted; retainedhosterror, no physicalreplay.
Fulljournals/source timestamps/rawcmd/hashseals underTest321, known10startup
MDSS/SMMU contexts UNKNOWN retained, nooverallstabilityclean. No new kernel/
full/Actions; exactd2b4c127/b4f5qualification/29hosttests reused. NoPPS/ON/current/
protection/ENHIZ/rootfs/DT/USB/adbd change. Failed318STOP unchanged. Fullgoal
NOTREADY; next actualnative adapter/worker fault/PM/fallback integration with
activationdisabled, then independent safety/current/freshness qualification.


Test321 registered offline: one PCfixed5/OFF continuous RAW boot, eight bounded
rawreads/READYoptional/2000ms, one15s endpoint, unconditional exactaccepted311
originalboot/181/allfive restoration. Reuse d2b4c127/b4f5c3e3 RAWbuild/qualification,
no new kernel/full/Actions. Newparser/lifecycle13 + old31816=29 PASS0.160s/no
skips; noREADY/fresh/OCPgrant, nativefault wins over startupservicepending,
completedraw may wait bounded150s for services without repeatingADC. Offline
boot-only package/payload/header/DTB/paired181/stagedinputhashes verified. Inputs
under reference/boot-tests/test-321-off-continuous-raw-adc/. Original308 current
accepted311 operational rollback assigned321; currentretentionwindow312–321.
Latest readonlypacket samee71954cf normalbaseline,21%/3.735V/31.6C/net-369mA
onPC/Wi-Fi.184; not physical321preflight/flash/result. Need fresh20%SOCrescue
and once allfive/181 beforeoneinstall. No PPS/ON/current/protection/ENHIZ/USB/
adbd/rootfs/DT change. Failed318 remainsSTOP; fullcharginggoalNOTREADY.


OFF continuous raw ADC observation is integrated in actual passive driver/shared
helper/Kbuild, default-off sm5440-adc-raw profile. Vendor/Fedora direct raw reads
replace per-READY assumption only in new profile; failed318 and oldREADY semantics
retained. Eight raw reads first20ms(afterenable/readback)/next50ms/total2000ms,
READYoptional, explicit nofreshnessclaim/noAPIpublication. Native fixed/pack
epochs/fault/OFF/bounds/exactcleanup/PM gates unchanged. A new actual-C clock
regression first FAILED, RAW anchor guard thenfixed; final68affected PASS1.922s
0skip incl13RAW/21oldTIMING. FinalARM64build PASS57.583s; twoobjectsW1/sparsePASS,
nochangeddriverwarning, knownupstreamvDSOwarning retained. Exactembeddedconfig,
DTidentical/181pairedfiles/BTF-onlychanges/209protected/26oldformal hashesPASS.
Configvsaccepted311 only RAWabsent->y/TIMINGabsent->n; DCCn/container/SM5714
float/thermal/fixedlimits preserved. Full2178run NOTPASS: historicalretired
cpuidle/CSD/Test187 images3subtestfail/12errors/25skips; no testweakening/rebuild
ofexpiredimages. Rawreports preserved; latestaffected rerun includes clockfix.
Qualification reference/charging/sm5440-continuous-raw/, design
docs/SM5440_CONTINUOUS_RAW_OBSERVATION.md, out/kernel-x710-continuous-raw/.
Incremental308namedtree nowRAWprovider, not historicalbaseline; formalrollback
retained. No deviceflash/reboot/ADC/PPS/ON/current/ENHIZ/protection/rootfs/DT/
USB/adbd/Actions/main change. Next separatelyregister onePCfixed5/OFFraw with
exactaccepted311restore; no failed318 replay. Fullgoal remainsNOTREADY: freshADC/
current/cutoff/OCP/actualactiveworker/PPS/fallback/PM stillunfinished.


2026-10-05 owner PCUSB reconnect endpoint now passes one read-only capture:
same e71954cf accepted311 normal config/notes/cmdline, nativeADB shell and
authenticated Wi-Fi.184, interface-bound WindowsNCM SSHbanner, composite/ADB/NCM
Code0/adapterUp. Pack22%/3.746V/31.5C/Good, PCSDP500mA net-280mA; pumpOFF/IBUS0/
fault0, Sink/Device, three services active/no failed unit/DCCabsent. Full1100-row
kernel JSON losslessgzip, prior1060-row exactcursorprefix,40additional rows no
detected CPU-stall/panic/Oops signature. Previous startupMDSS/SMMU UNKNOWN retained.
No agentreboot/flash/reset/service/config/PPS/ON, no new build/host/Actions.
Current USB recovery only; physical cycle timing not observed/permanentfix NOT
proven. Test319/318 failures unchanged. Evidence reference/charging/usb-reconnect/
20261005T051810Z/. Fullcharginggoal stillNOTREADY.


2026-10-05 Test318 physically executed once and STOPPED. Candidate df1ce8c0
exact identity/uniquehistory; nativefixed5/packadmission passed, but OFFcontinuous
READY never arrived within500ms: error-110/count0/polls38/589ms transaction,
control0x0f/channeldf/statushealthy. ExactADC0x0c/df cleanup and checkedOFF pass.
Original host services/role/DCC/failed first-error retained (SSHinactive6.31s),
not a waiver for earlier realADCtimeout. Unconditional exact accepted311boot/
181/allfive rollback completed, final e71954cf normalidentity/controls/realthermal
ADB/deviceNCM/WindowsCode0/NCMhost/Wi-Fi10.139.153.184 pass,22%/31.4C/Good/OFF.
No PPS/ON/current/protection/ENHIZ/rootfs/DT or active100ms-gate change. No new
build/host regression/Actions; frozen44c2190a qualification reused. Full raw
journals/snapshot/commands/hashseals; RESULTS/ANALYSIS underTest318. Do not flash
this failed READY profile again unchanged. Fedora continuous path reads raw
ADC without per-sampleREADY; vendor1100ms is policycadence, not conversion proof.
No successfulcontinuouscalibration/current/cutoff/OCP/PPS/ON acceptance; actual
activeworker/nativeadapter/PM/fallback still unfinished, fullgoalNOTREADY.


Test318 fresh NORMAL preflight passed after Test320: same8146a9cf accepted311,
allfive partitions/exact181 modules, realpack22%/3.763V/31.3C, ordinaryPC500mA
controls/float4440, passiveOFF, nativeADB/deviceNCM/authenticated Wi-Fi.11 and
WindowsCode0/no43. Frozen source/profile/artifact/stage identities unchanged;
no new build/full regression/Actions. Preflight evidence sealed before the one
registered OFF timing candidate boot and unconditional exact311 restoration.
No candidate deployment/result is claimed by this entry.


2026-10-05 Test320 recovered USB with exactly one registered unchanged Wi-Fi
normal reboot. New8146a9cf uniquely attributed, exact accepted311 config/notes
and NORMALcmdline/lpcharge0. Native ADB shell25.783s; authenticated Wi-Fi at new
DHCP10.139.153.11 within125.952s; Windows composite/ADB/NCM Code0 within128.680s,
no Code43. Old .121 readiness probe false-negative retained/resolved by actual
new-address evidence; never repeat a boot for stale DHCP.15s endpoint sameboot
pack22%/3.767V/31.1C/Good/realthermal, passiveOFF/IBUS0/fault0, services/deviceNCM
normal/DCCabsent. Full old/new/end journals; no new CPU/unclassified fault; known
10 startupMDSS/SMMU contexts UNKNOWN, no overallstabilityclean claim. No flash/
BCB/modules/config/PPS/pumpON/build/full/Actions.7 existingidentity tests PASS
0.004s/0skip. Test319 remains STOP; Test318 undeployed. USB runtime recovery
only, permanent charger-to-PC rootcause/fix UNDETERMINED. Read Test320 RESULTS.


2026-10-05 Test319 STOP before reboot: actual Windows Code43 descriptor failure
survives owner-confirmed PC cable/port reconnect; nativeADB absent, same647d50c8
Wi-Fi/config/notes/pack22%/26.5C/pumpOFF remain healthy. No reboot/flash/BCB/modules
or device config write. Test318 undeployed. Test320 independently registers ONE
unchanged normal Wi-Fi systemctlreboot for USB recovery; intentional incoming
Code43 only, exactnormal endpoint/uniquehistory/nativeADB/PnP0/15s health required.
No live gadget/adbd restart, no charging policy change/PPS/ON/second reset;
first non-clean STOP. Reuse frozen parsers, tests/build executed:false.
Original308 accepted311 operating rollback belongs to318/320; no new image.


2026-10-05 Test319 normal accepted311 reentry registered before Test318 ADC
deployment. Owner confirmed manual647d50c8; config/notes exact but known incoming
lpcharge=1 args differ from normal. Ordinary C2 charge observed, source9V/1.5A,
pumpOFF/zeroIBUS/fault0; pack reached20%/3.867V/27.5C. Bounded32-row maintenance
log ended965.069s, no writes/PPS/ON. Test319 one unchanged PCsystemctlreboot after
push: allfive/181 checked once, exact incoming then exactnormal cmdline, unique
boot attribution/15s endpoint; no flash/BCB/modules, first non-cleanSTOP/no second
reboot. Seven identity/no-replay tests PASS0.004s/no skips; no build/full/Actions.
Test318 remains unexecuted and needs freshnormal preflight after319. Operational
original308 rollback belongs to current318/319, not an expired historicalimage.

Test318 entry now filters real pack reserve before expensive probes. Actual
ADB packet sameac442c81/SOC4%/3.651V/net-331mA/31.2C refused in0.092s; no full
preflight/mutation/candidate ADC.16 affected parser/lifecycle tests PASS0.033s,
unchanged kernel/artifact qualification reused. Await genuine ordinary C2 charge
recovery and20%SOC reserve; no reported source change inferred.

Test318 registered offline: one PCfixed5/OFFcontinuousREADYtiming boot, eight
raw events/500ms perREADY/2000ms transaction, one15s endpoint, unconditional exact
accepted311 boot/original181 rollback. Source44c2190a qualification reused, exact
DT/packagedpayload/readback/pairedarchive hashes;15 new parser/lifecycle tests
PASS0.028s/no skips, no kernel rebuild/full/Actions. Package/stage/runner/gate
reference/boot-tests/test-318-off-continuous-adc-timing/. Actual latest accepted311
maintenance packet sameac442c81 SOC4%/3.634V/net-1.058A/31.2C/Good onPC SDP500.
No physical318 preflight/flash/reboot/ADC/PPS/ON; pending owner C2 ordinarycharge.
Need fresh20–<80%SOC flash/rescue reserve first. Registration does not infer
charge recovery. Retained operational rollback original308 belongs to318 and
current device, not an expired historical308 backup. Fullcharginggoal NOTREADY.

OFF continuous ADC timing is now integrated in actual passive driver/Kbuild,
separate default-off sm5440-adc-timing profile, not an unlinked foundation.
Existing frozen one-shot/startup gates preserved; native fixed/pack provenance,
vendor AVG32/RATE1/50ms, eight READY/raw/read brackets, mode/live/latch/control
checks, one exact ADC cleanup and source/pack endpoint. No companion publication,
PPS/lease/Q4/current/protection/ENHIZ/ON operation or resume rearm. Fault uses
existing checked OFF before converter cleanup. Diagnostic500/2000ms does NOT
change active100ms gate or certify analog/OCP/coherent channel/current/cutoff.
Latest21 actual-C tests PASS0.628s plus175unchanged affected deps; previous
combined196PASS11.628s/no skips. Final full ARM64build PASS83.143s; twoactual
objects W1/sparse PASS6.177s/nochanged-driverwarning.209protectedsources and
21priorformal artifacts exact; config vsaccepted311 only newTIMING absent->y,
DTidentical,181pairedfiles/167BTF-only ko changes/no code-data/metadata change.
Formal out/kernel-x710-continuous-timing; evidence reference/charging/
sm5440-continuous-timing/, design docs/SM5440_CONTINUOUS_ADC_TIMING.md.
No flash/reboot/deviceADC/PPS/pump/current raise/Actions/full regression.
Device stillaccepted311/ac442c81, latestread6%/3.660V/31.1C/Good/net-427mA onPC.
Owner asked to connect previously accepted C2 ordinary18W charging; reply pending,
no inferred connection/charge or new test. Next separately register Test318 one
PCfixed5 boot/OFFtiming/exact311 unconditional restore after battery readiness.
Full charging goal remainsNOTREADY; physical100ms/OCP/current/cutoff/liveworker/
ON/PPS/fallback/PM acceptance still remain. Older next-step entries historical.

2026-10-04 owner powered-on report: fresh read-only boot ac442c81, embedded
config/notes match accepted311; ADB/authenticated Wi-Fi SSH/device usb0 respond.
Real sm5714-battery zone37 enabled30.7C, pack9%/3.670V/net-405mA on PC USB;
pump Not charging. Current/previous complete journal and historical photo boot
retained under reference/charging/device-startup/2026-10-04-ac442c81/.
Photo224.226049s belongs to old acdd2dfc SM5440 passive zone, as already proven
by Test299 enumeration; accepted Test300 no_thermal fix is retained. Dynamic
zone37 now identifies pack, not that old cache. No current thermal-disable
message; no new continuous die-temperature/OCP/direct-charge acceptance.
No device mutation/build/tests/Actions; results-only executed:false.
Next independently qualify OFF continuous ADC timing using actual vendor
AVG32/RATE1/50ms rearm, without altering frozen one-shot or100ms active gate.

2026-10-04 native pack observation is now implemented in real battery driver
and consumed by the real OFF-only PPS session. Real gauge/SOC/signedcurrent/
onepackIIO read, native time, liveSTATUS attach/presence/health checks and exact
lease/state generation; no cached/default successful data. Registry->charger
short try-pin/token only, IIO/gauge outsidecorelocks, drain/finalput-wakeupbarrier
beforedevres. Vendor STATUS2[2] now drives public PRESENT; errorspropagate.
162 affected actual-C/pthread tests PASS5.774s/noskips, final full ARM64build
PASS64.202s, twoactualW1/sparse objects PASS7.260s/nochanged-driverwarning.
14 hardwarepolicyfunctions unchanged;136protected sources/15oldartifacts exact.
Existing policy-offline config includes actualsession and excludes ADCdiagnostic
via !policy dependency (absent, not explicitn); exactdiff retained/DTidentical311.
181 pairedfiles,167koBTF-only/3expectedbuiltinmetadata changes. Evidence
reference/charging/sm5714-pack-snapshot/, docs/SM5714_NATIVE_PACK_OBSERVATION.md.
No devicecommands/flash/reboot/PPS/pump/currentincrease/Actions/fullregression.
Previous accepted311 device observation historical reuse only, not freshtest.
Realworker/adapter/physicalADC/current/cutoff/OCP/refresh/fallback/PM stillremain.
500msfacts bracket not100msphysicalprotection, no deadline/averaging relaxation.
Fullgoal NOTREADY; existing fixedcaps/4.44V/thermal/USB/DCC remain.

Native read-only owned PPS API is now integrated in the actual TCPC/header and
linked through normal Kbuild; previous unapplied-patch entries below are
historical.88 actual-C/pthread affected tests PASS1.609s/no skips, full ARM64
Image/DT/modules PASS88.423s, actual TCPC W1/sparse PASS7.202s/no changed-driver
warning. Config equals316; DT equalsaccepted311; only prior diagnostic ADC
profile delta vs311.181 paired files;167ko changed only BTF, code/data/version
sections identical.137 protected sources/nine old artifacts retained. Evidence
reference/charging/sm5714-owned-observer-integration/. Current device stillsame
accepted311 boot6f0d319b/exactconfig+notes, ADB/usb0/Wi-Fi up, pack31.3C and
battery thermal_zone37 enabled; oldphoto error not reproduced/not declaredfixed.
No flash/reboot/PPS/pump/currentincrease/Actions/full regression. Source API is
logical evidence only; realpack/worker/physical100ms/current/cutoff/OCP/native
refresh/fallback/PM acceptance remain. Converter unchanged. Fullgoal NOTREADY.

Test317 now completed salvage and unconditional exactaccepted311 restore.
Attributed candidatecc6d3fae/matched316 config+notes; early fixed9 OFF context
phase10/error0/cleanup0, five zeroIBUS samples9.138–9.342V, sample-prefix gates
pass, ADC/gauge43.5mV. Later current source5V/gen13 differsretainedgen9, so
registered current-source/15s endpoint refused; no fake9V receipt/boot replay.
Full1111 kernel rows/new CPU-panic-I2C counts empty; initial inactive latch and
known display/SMMU diagnostics retained. ADCread brackets128–130ms, diagnostic
500ms only/NOT active100ms/OCP proof. Exactaccepted311 originalboot+181/allfive
restored/readback; final6f0d319b attributed, config/notes/ordinary4.44V controls,
ADB/deviceNCM/hostSSH/services/roles/DCC pass;19%3.709V29.4C. rollback_required
false. Test317 RESULTS/summary/raw evidence authoritative; older access-pending
and candidate-installed entries below historical. No new build/tests/Actions
for results; reuse73host/Test316 qualification. Next actual native observation/
pack/worker integration and physical100ms/current/cutoff/OCP/ON/PPS/fallback/PM
remain. Full chargingport goal NOT complete; no pump/current escalation grant.


Current public TCPC snapshot is fixed-only; active PPS needs a fresh readonly
producer, not Request-per-sample or restamped entry receipts. Prepared an
unapplied two-file owned-PPS observer patch: existing native getter/lifetime/
try-control/token/APDO/lease checks, original acquisition timestamps, zero
failed output, no mutation.88 affected host tests PASS1.456s; complete patched
TCPC unlinked ARM64/W1/sparse PASS5.841s, no changed-driver warning. Original
negative publication stimulus error retained/corrected. Seven provider files,
98 Test317 inputs/nine artifacts exact; config/DT diff empty, no Image/full/
Actions/current TCPC change/device PPS/pump. Evidence reference/charging/
sm5714-owned-observer/, design docs/SM5714_OWNED_PPS_OBSERVATION.md. Apply only
in a separately qualified future integration after317 capture/accepted311
rollback. Actual adapter/pack/ADC/OCP/cutoff/ON/fallback/PM remain; full goal
NOT complete. ADB still empty thisturn; current IP/connection pending.


Offline actuator PPS park/resume now keeps OFF across native negotiation,
retains settings/WDT and requires advancing real budget generation, same
attach/lease/source and physical OFF ADC acquired after PPS completion. Current
can only fall; uncertain first OFF latches unknown ownership without hidden
retry. Fresh post-ON supervisor required.88 affected actual-C host tests PASS
1.795s; two ARM64/W1/sparse objects PASS4.998s, no changed-helper warning.
Six cached provider/98 Test317 inputs/nine artifacts unchanged, config/DT diff
empty. No Kbuild/live worker/Image/full/Actions/device PPS/pump operation.
Evidence reference/charging/sm5440-park-foundation/ and docs/SM5440_PPS_PARK_RESUME.md.
Physical OCP/ADC/cutoff/native integration/fallback/PM still unqualified; full
goal NOT complete. Test317 access/current owner IP/connection pending, capture
NOT EXECUTED and accepted311 rollback remains required. No blind boot replay.


Native monitor/shutdown foundation now composes actual converter, actuator OFF
and WDT helpers. Real source/facts/epoch/100ms gates, exact625uA trip, new raw
MEASURED before cleanup, OFF priority, healthy-only WDT service, separate first/
cleanup errors and terminal no retry. Managed ADC cleanup halts on first error;
standalone behavior retained and converter requalified.76 affected actual-C
tests PASS1.668s, two unlinked ARM64 objects/W=1/sparse PASS4.898s, no changed
helper warning. Initial quiescence assertion failures retained/corrected to
preserve unknown cleanup. Six provider/98 Test317 inputs/nine artifacts exact,
config/DT diff empty; no Kbuild/worker/Image/full/Actions/device charging write.
Evidence reference/charging/sm5440-supervisor-foundation/. Physical ADC/OCP/
cutoff/live adapter/refresh lifecycle/fallback/PM acceptance still missing;
software_ocp_verified remains false on device. Whole goal NOT complete.
Current317 Wi-Fi/ADB access pending; one bounded registered-subnet discovery
found no SSH listener, not a device-fault inference. Capture NOTEXECUTED and
exactaccepted311 rollback still required; no unobserved reflash or boot replay.


Offline bounded converter layer now provides actual regmap begin/advance/cancel,
vendor 20 ms rearm/one-shot AVG32, fresh READY provenance, live/latch separation,
raw ADC/current precision and checked original converter cleanup. Native BOOTTIME
request <=100 ms including cleanup; no sleeps/locks/cache restamps/old READY.
60 affected actual-C tests PASS0.825s, ARM64 single object W=1/sparse PASS4.520s,
no changed-helper warning. Initial decoding/failed-disable assertion failures
retained and corrected. Six provider/98 Test317 inputs/nine artifacts unchanged;
config/DT diff empty. No Kbuild/caller/Image/device/PPS/pump/full/Actions.
Results reference/charging/sm5440-conversion-foundation/. Vendor200ms worker and
Fedora continuous ADC are NOT physical100ms/OCP proof; actual acceptance and live
adapter remain open. Test317 capture pending/rollback_required=true, awaiting
current Wi-Fi IP/connection after owner's powered-on report. Goal NOT complete.


Owner now reports powered on. Fresh bounded checks show no ADB device and
registered Wi-Fi 10.139.153.84 returns No route to host. No new boot ID,
kernel identity or charger connection has been observed; current device state
is unverified. This does not prove a CPU fault or that TWRP remains running.
Test317 capture NOT EXECUTED; rollback_required=true. Current Wi-Fi IP and
physical connection are pending. Raw evidence and hashes are under Test317
post-install-availability. Status-only tests/build executed:false; reuse unchanged
73 affected host tests and Test316 build qualification. No reflash/reboot/PPS/pump.

Unintegrated pump register layer now supplies actualchecked ENHIZ/CHG_ON/OFF
plus existingsettings/watchdog cleanup, noKbuild/caller/activation. Disabledby
zero init; mandatoryqualifiedOCP/lease/realPPS ONLINE2/mirrorednativeepochs/
matchingAPDO/physical100ms/facts400ms/<=1.8A/42C die. Singleattemptcleanup,
unknownOFF keepsWDT/settings owned; no automaticsecondOFF/PM rearm.44 affected
hostPASS0.574s (14actuator/16WDT/14OFFsettings), ARM64singleobject/W1/sparse
PASS3.657s; six316provider/98sealed317inputs/nineartifacts exact/configDTsame.
Noimage/full/CI/devicechargingwrite. Initialhostsignedness/mockparenthesis
corrected; earlierARM64beforecleanup-latch superseded/logsretained. Results
reference/charging/sm5440-actuator-foundation/. Fullport stillNOTREADY: integrate
real adapter onlyafter ADC/OCP/current/cutoff/PM acceptance, no deviceON grant.
Latest317access: initiallyTWRP, laterADBempty andWi-Fi No route; no newbootID,
no livecaptureprocess, no failure/success inference. OwnerC2boot reply/access
pending; candidate installed/rollback_required=true. Finish317 andexact311restore
before separately integrating futureactiveprofile. This supersedes older
checkpoint wording that device is stillTWRP; presentboot/transport unknown.

Unintegrated watchdog foundation now supplies realchecked regmap arm/service/
OFF-only restore, vendorCNTL1 timer/enable/reset provenance and Fedoraactual
refresh semantics (plainregmap equalupdate wouldskipwrite).16 actualC fault
hostPASS0.233s, ARM64singleobject/W1/sparsePASS3.236s; initialkernelcurrentmacro
collision corrected/logexit2 retained. NoKbuild/caller/export/ON/PPS/devicewrite.
All316provider/317sealedinputs/formalpackage hashesunchanged; noimage relink/
config/DT/full/Actions. Results reference/charging/sm5440-watchdog-foundation/.
Device observedstillTWRP;317ownerC2boot pending/rollback_required=true. No live
capture process, no failedcandidateboot inference from Wi-Fi No route. Goal
active/fullportNOTREADY; finish317 then integratefutureactiveprofile separately.

Test317 INSTALLED_IN_TWRP_AWAITING_OWNER_FIXED9_BOOT_ROLLBACK_REQUIRED. Qualified316 kernel only,
73 affected host PASS0.745s/no skips, syntaxPASS; no rebuild/full/routing/Actions.
One source-bound OFF context/ENHIZ comparison, diagnostic500ms notactive100ms;
no PPS/pump/current raise. Install/readback boot+181 in validatedTWRP, clearBCB/
unmount, STOPthere; owner attachesLenovoC2fixed9 BEFOREboot, authenticatedWi-Fi
capture/fullkernel/epochs/liveSTATUS/15s endpoint; firstfaultSTOP. Unconditional
exactaccepted311 rollback and device rescue. Test313 remains terminal/no5Vreplay.
Window308-317 no expired307 images found. Installed311 unchanged1f1e01bf/29%/
3.770V31.9C at shortread; fresh full rescue preflight mandatory before mutation.
Fresh317preflight allfive/181/config/notes/actualQ4ON500mA/4.44V/pack31.7C/
28%3.77V/same1f1e01bf/Code0/deviceNCM/authenticatedWi-Fi pass. Fullkernel
knownpassiveADCrefusal retained, no new CPU signature; onehostNCM probe separate.
317candidateboot+181 installed/readbackonce/allfiveverified/BCBclear/rootunmounted.
STOPinTWRP, no scriptedcandidateboot; ownerPC->C2fixed9 thenRebootSystem pending.
CaptureNOTEXECUTED/rollback_required=true; afteronceWi-Fi capture orfirstfault
reconnectPC and restoreaccepted311 unconditionally. Fullchargingport NOTREADY.

Test316 FIXED_CONTRACT_CLASSIFICATION_OFFLINE_QUALIFIED_NOT_DEPLOYED,
source8b77b426. Match unchanged standard producer capability labels, active
mode still fixedONLINE1/!pps/fixed9<=1.5A. Source-bound initial5V+fixed9>=1A PDO
can wait for normalTCPM negotiation,40calls/4s elapsed; first rawstandby/epochs/
timing saved; late supplier refused/no hardware before9V/no fault retry.128
host PASS1.931s; ARM64 PASS81.444s; W1/sparse PASS7.616s/standardobjects restored
exact6.150s/vmlinux unchanged/no changed-driver warning. Only ADC_TEST n->y
vsaccepted311, DTBsame/96protected/12overlays/181modules/containers/DCC pass.
315 symbols/79inputs and formal hashes frozen; solecache now316. No device/
PPS/pump/TCPMcore/battery/DTS/USB/rootfs/full/Actions; fullport NOT READY.
Next separately register fixed9 OFF comparison and unconditional exact311restore.


Test315 FIXED9_OFF_CONTEXT_OFFLINE_QUALIFIED_NOT_DEPLOYED, source30cf862a.
Existing isolated ADC-condition profile only; source/pack/physical9V + checked
SM5714 lease before real OFF settings/ENHIZ comparison. Pre-liveSTATUS/timing/
raw/protection witnesses, error+cleanup/pending retained; lease inhibited, no
500ms->100ms grant/release/PPS/ON.122 affected host PASS1.632s; ARM64 PASS86.218s;
W1/sparse exit0/no changed-driver warning. Initial object-equality guard failures
retained; two standard objects restored exactly6.057s/vmlinux unchanged, not
false W1==standard claim. Only ADC_CONDITION_TEST n->y vsaccepted311, DTBsame/
96protected/12overlays/181modules/container/DCC pass.314 symbols/79 inputs frozen
and formal artifacts intact; cache now315 diagnostic. Window306-315 four old305
images deleted with hashes, no archive. No device315/full/Actions. Installed311
same1f1e01bf at owner follow-up/32%3.785V31.6C/ADBnetwork/knownADCrefusal retained.
Read315 RESULTS/summary/design; next separately register fixed9 preattached
one-shot context with unconditional exact311 restore, not PC5V replay. Full
port NOT READY: physicalADC/OCP/watchdog/ON/PPS/fallback/PM still remain.


Test314 OFF_ONLY_SETTINGS_OFFLINE_QUALIFIED_NOT_DEPLOYED, source deb28242.
New actual regmap OFF-only input/regulation/frequency transaction, original
field restoration and ten protection/operating witnesses; uncertain writes
and failed OFF/cleanup retain pending/errors. No caller/export/probe/ON/PPS
or SM5714/DTS/USB/adbd/rootfs change.105 affected host PASS1.529s; ARM64 build
PASS87.075s; W1/sparse PASS6.987s/object+vmlinux unchanged/known vDSO warning.
Exact config X710_CHARGING_POLICY n->y; ADC_CONDITION_TEST n->absent due !policy;
unexpected empty, DTB identical,96 protected and12 overlays verified,181 paired
module files, embedded config/container/DCC gates pass. Formal308/312 intact;
312 symbols+79 inputs verified before cache reuse, now314 provider. No device
operation/full/Actions. Initial overbroad444-test historical-image failure/skips
retained, not all-pass; tests unchanged. Read314 RESULTS/summary and new OFF
transaction design. Next actual source-bound preparation/ADC/OCP/watchdog/ON/
handoff/fallback/PM remain; accepted311 stays installed; full goal NOT READY.


Owner powered-on follow-up: same restoredaccepted311 boot1f1e01bf, config/notes
match, SOC37/3.794V/31.9C; ordinaryQ4/input500/fast500/float4440 verified once,
ADB/services/deviceNCM/Wi-Fi/SinkDevice/DCCabsent. Full1100kernel rows, matched
CPUfaults empty; knownpassiveADCrefusal retained/notcharginggrant. Currentzone37
pack enabled/read31900mC/no temperature warning thisboot; oldphoto numeric ID
doesnotidentify historicalprovider. Initialhostdebugfspathlookup error retained,
correctprovidercommand captured; noflash/reboot/PPS/pump/configchange. Evidence
313/post-boot-20261003T092948Z; tests/build executed:false unchangedqualification.
313STOP remains terminal; fullchargingport active/notready.


Post313 source comparison: Samsungattached+OFF setsENHIZ; ordinary ADC gated below
CHECK_VBAT; Fedoraab123e7d activeinit followsfixed9V switchinghandoff, notPC5V
bit-only recipe.313source-analysis exact hashes/lines retained. Next source-bound
pumpOFFpreparation needsactualVBUS/pre-status/pack/epoch/switching context; no
logical9V-onlygrant, faultmasking/reset/protection-disable copy, same5Vreplay or
claim9Vcure. Docscondition+architecture current311/313 state corrected. Prose/
sourceexcerpt review only, tests/build/device executed:false; prior qualification
unchanged. Fullgoalactive/Stage3NR, active actuator/protection+physical acceptance remain.


Test313 STOP_LIVE_REVBLK_AND_NONZERO_OFF_IBUS_ACCEPTED311_RESTORED. Singlecandidate
41c7fe02/raw1060kernel/fullsnapshot preserved. CNTL6 89->09->89 readvalid/
ADCoff+ENHIZcleanup verified; ADC3.7995V/gauge3.802V(delta2.5mV),5.010V VBUS/
30.625mA IBUS/liveSTATUS3=22/REVBLK80; mode01/01 OFF/no pump activation support.
Originalerrorpumpcurrent/newfault preserved, NOT CHG_ON proof. conditionvalid0/
fault1/no endpoint/devicePASS/calibration/freshness. CauseUNKNOWN/pre-clearSTATUS
missing; no treatingLIVEfault asoldinactive latch. Offlineboot attributionderived
from savedrollbacktargethistory, notclean reclassification. Exactaccepted311
boot+181 restoredonce/allfive/BCBclear/finalnormal1f1e01bf/39%3.796V30.2C/
actualordinarycontrols/notesconfig/pack/rescue/attribution. Knownpassiverefusal
retained/hostNCM255separate/rollback_required=false/313terminal/noreplay.51host
PASS reused/no newbuild/full/PPS/pump/current/rootfs/USB. Next source-backed
operatingcontext/livepre-status/freshVBUS/fixedcontract/pack gates before any
newconditiontrial; do not copyvendor/Fedorafullactiveinit or guess9V cure.
Fullgoalactive/Stage3NR: ADC/protection/actuator/PPS/handoff/fallback/PM remain.


Test313 OFFLINE_REGISTERED_ONE_CONDITION_COMPARISON_READY. Qualified312diagnostic/
accepted311ordinary recovery preserved; one pumpOFFconversion+15sendpoint, exact
accepted311boot+181 unconditionalrestore.51affectedactualrunner/parser/fixture
hostPASS0.324s/syntaxPASS; no newkernel/full/Actions. Serialactualcontrols/thermal/
fullkernel beforeone20shistory; partialADC/restore error immediateSTOP; corrected
DebianPARTNAME/providerbinding; knownfault provenance unchanged. Conditiongate
byteidentical306/ordinarygate+readeridentical311; sourceinputs sealed. Physical
NOTEXECUTED, fresh safe normalaccepted311preflight mandatory. NoPPS/pump/current
raise/DTS/USB/adbd/rootfs change. Fullgoalactive/Stage3NR. Read313README/RESULTS.


Test312 OFFLINE_ADC_CONDITION_WITH_ACCEPTED_ORDINARY_RECOVERY_QUALIFIED. Current
Test311 accepted45f6c912 retained, no312device command. Same158d0dd3 source /
onlyCONFIG_SM5440_ADC_CONDITION_TEST n->y vsaccepted308/311;DTBidentical/96protected/
10overlays/181paired/embeddedconfig andDocker/DCC gatesPASS. Build89.526s/
36affected actual-C/profile testsPASS1.651s/W1sparse8.221s object+vmlinuxidentical;
knownupstreamvDSOwarning retained/no full/Actions. Actual308 incrementalpath reused
as312diagnosticprovider: old308cachequalification ends; formal308artifacts unchanged,
oldvmlinux+79CRC/config/generated inputs verified inout/debug-x710-308-accepted.
Existingvendor one-conversion ENHIZ bit7/PumpOFF/restoration diagnostic source
unchanged/no PPS/pumpON/currentraise. Next independent physicalregistration needs
freshaccepted311preflight and exact308/311boot+181 unconditionalrollback, notold
305reverting ordinary recovery.312RESULTS/summary/validation; sourceinputs sealed.
Window303-312/3old302Imagesdeleted without archive; originaldebug/logs kept.
Fullgoalactive/Stage3NR; physicalADC/calibration/freshness/protection/PPS/handoff/PM remain.


Test311 ORDINARY_RECOVERY_CANDIDATE_DEVICE_SCOPE_COMPLETED. Normal45f6c912 retained/
unique attribution/boot+181written+readback/allfive/BCBclear. Baseline40%3.809V31.8C;
admission40%3.798V30.2C;15sendpoint40%3.818V31.4C. ActualQ4ON/input500/fast500/
float4440 twice/no program drift or naturalrecovery; recoverybranch not physically
proved under drift. DeviceADB/services/NCM/SinkDevice/realthermal PASS; hostNCM255
separate. Full1071/1107journal rows/fault_counts empty/knownstartup warnings retained,
no broadstabilityclaim. OriginalSM5440REVBLK retained/two freshconfirmations inactive;
ADC/gauge263/211/329mV disagreement UNKNOWN/notcalibrated. PC500mA netnegative
batterycurrent recorded.311 terminal/PASSretained/no rollbackpending/no replay/
PPS/pump/currentraise/config/DTS/USB/adbd/rootfs change; offline35 PASS reused.
Exact299rollback/current308 artifacts retained. Next isolatedvendor ENHIZ/ADC
comparison must retain newly accepted ordinaryrecovery; no old305 flash reverting
that driver. Fullgoalactive/Stage3NR: ADC/protection/actuator/PPS/handoff/PM remain.


Test311 OFFLINE_SERIAL_COLLECTOR_REGISTRATION_READY.35affected host PASS0.145s/
syntaxPASS; exact308kernel/artifacts reused/no kernel/config/DTS/USB/adbd/rootfs/
PPS/pump/current change/build/full/Actions. Primaryidentity/thermal/actualcontrols/
fullkernel classification precede single20shistory; ADBserial; allactual safety/
attribution/15sendpoint gates retained, missinghistory stillSTOP.125 inherited310
inputs unchanged/136sealed; sixWindowsstage hardlinks+one uniquehelper/no largecopy.
Physical311 NOTEXECUTED; freshsafe normal299preflight required. Lastactual final
788fef75 accepted299 restored after310STOP, not fresh311identity.309/310terminal/
noreplay. Test263 historicalrollbackimages retired; current299production/rollback
and exact308candidate retained. See311RESULTS/summary/validation. Fullgoalactive/
Stage3NR: physicalADC/protection/actuator/PPS/handoff/fallback/PM still outstanding.


Test310 STOP_BOOT_HISTORY_CAPTURE_TIMEOUT_ACCEPTED299_RESTORED.32affectedhost
PASS0.146s/providercollector correct onbaselineBEFOREflash Q4/input500/fast500/
float4440. Candidatec9663df0 identity/pack/rescue/currentstate0.292s/fullkernel
1064rows1.279s/CPU0; parallelbootlist10.014stimeout, no candidatecontrols/15s
endpoint/completeattribution/cleanclaim. CauseUNKNOWN, not CPUcausalproof.
Failurekernel/history0.154/0.153s; exact299boot/181 restoredonce/allfive/BCBclear,
finalnormal788fef75/42%/3.815V/30.2C/ADBdeviceNCM/attributed; finalhistory7.627s.
Knownpassive startuprefusal retained; hostNCM255separate. Rollbackrequiredfalse/
310terminal/noreplay/noPPS/pump/current/kernelbuild/fullCI. Nexthostcollector
prioritizeactualcontrols/thermal/journal, serializeADBjobs, single boundedhistory
query; keep allactualidentity/boot/faultgates. Fullgoalactive/Stage3NR.

Test309 STOP_COLLECTOR_AMBIGUOUS_I2C_ADDRESSES_ACCEPTED299_RESTORED. Normal
224ffde1 preflight passed allfive/181 afterhostnamespacefix77PASS; candidate
766bce71 installed+readback/identity/pack/rescue/attribution/1063journal CPU0.
Collector failed BEFOREbusopen: global*-0049 uniqueness wrong, boardhas2-0049+
7-0049; actualbatteryprovider2-0049/boundSM5714/OFverified. No15sendpoint/clean
claim/no registertransactions. Exact299boot/181 restoredonce/allfive readback/
BCBclear; finalnormal732d3733/43%/3.823V/29.3C/confignotes/rescue/attributed/
1065journal CPU0. Knownpassive startuprefusal retained/notADCacceptance; host
NCM255recorded. Mutationrollback_required=false;309terminal/noreplay. Preserve
source/collector/raw; newfollowup must anchor power_supply provider withalias/
binding/OF guards and tolerate unrelatedsameaddress. Reuse308kernelartifact/no
kernelchange/build/full/PPS/pump/current/rootfs/USB. Fullgoalactive/Stage3NR.

Current architecture documentation now distinguishes historical Test255 policy
from retained299 hardware and undeployed308/309 candidate. Test302 native TCPM
and Test303 owned pump-OFF consumer are implemented/compiled/host-tested, not
physical PPS or active pump acceptance. Three design documents were corrected;
no source/profile/runner/test changed,114registered309inputs unchanged. Review
record309validation/architecture-docs-review.json; extra host/build executed:false
per reviewed prose-only workflow. Current storage reuse rules replace the old
per-stage full-tree recommendation. No device operation in this docs update.


Test308 OFFLINE_ORDINARY_PROGRAM_RECOVERY_QUALIFIED, source158d0dd3. Actual
readback witness/four stable controls/AICL reduction preserved/one recovery per
binding; intentionalOFF invalidates/second mismatch+I/O+silentwrite sticky
program fault even withoutTCPM ownership/cleanupOFF+input readback. Existing
5V1.8A/9V1.5A/4.44V/thermal/full/PM/lease retained; noPPS/pump/reset/WDTclear/
TCPCcore/configfragment/DT/USB/adbd/device command.102unique affected PASS4.759s/
ARM6485.037s/W1sparse8.314s/object+vmlinuxsame/96protected/10overlays/181paired.
Against299only existingdiagnosticdeclaration absent->n; DTB identical/notfalse
byteconfigclaim. No full/CI; earlier interrupted logs preserved asNOTpasses.
Read308RESULTS/summary/validation. ArtifactsWSLonly;302regen intermediates
trimmed3.87GiB/7871debuginputsverified/308sole current incremental cache;302path
no longer completeincrementalprovider (supersedes above two-cache listing).
Owner storage cleanup commitsc22a6856precede source qualification; retiredold
Stage2Image not checkedasexisting. Last3070%/2.775V/lpcharge boot remains unsafe;
owner C2recharge confirmation pending/no newpoll/flash/reboot. Next separately
register ordinary recovery acceptance after safe battery; old306source seal
cannot be bypassed. Fullgoalactive/Stage3NOTREADY; ADC/OCP/PPS/PM hardware remain.


Test307 STOP_CRITICALLY_LOW_BATTERY_AND_CHARGE_PROGRAM_MISMATCH. One readonly
ADB incident capture: new fd198...boot (cause unknown/no reboot issued), same
299 notes/config but lpcharge=1/normal306cmdline mismatch; SOC0/VBAT2.775V/
~+6mA/31.5C/Good/Not charging. PC SDP online reports1800mA;8 atomic stable
register-pointer reads show Q4OFF/input1800/fast97/float4200; initial logs500/500
at1.52/1.98s. Mode5/WDT04(disabled NOW); reset cause/prior WDT unknown. Initial
name guard failure before I2C preserved/corrected via bound driver+OF.1109raw
kernel rows/zero matched CPU signatures/packzone enabled; no write/flash/PPS/
pump/current/reset/rootfs. Old WiFi19 unavailable/new16; no further polling.
Owner C2recharge/current-state confirmation pending. Do not run306 at lowbattery
or lpcharge boot. Next bounded ordinary programmed-state recovery per design
SM5714_PROGRAM_STATE_RECOVERY, not active pump bringup.307 docs/evidence only,
host/build executed:false. Full Stage3NOTREADY/fullgoalactive; current normal
production acceptance not asserted from notes/config alone.

Test306 OFFLINE_REGISTRATION_PACKAGE_AND_RUNNER_READY. Qualified305 source and
artifacts reused; boot-only package / paired181 / exact accepted299 rollback
staged in D:\android\gts9-active\gts9-test306.51 affected host tests PASS; no new
kernel build/full/CI/device command. One OFF-mode ENHIZ comparison, exact restore
flags / original fault / unique ADC-gauge pair /15s endpoint; unconditional299
rollback, not263. Baseline/candidate config checked separately; lightweight
readiness / one full identity / parallel journal-history-USB / one NCM probe.
Cleanup tracked before BCB request; unknown identity/rescue -> manual TWRP, no
blind retry. Physical NOT EXECUTED: owner recharge/current-screen confirmation
still pending; last0%/3.145V is historical, not fresh proof. Read306 registration,
RESULTS/summary/INPUTS. No PPS/pump/current/freshness waiver; full Stage3NOTREADY,
full goalactive. Register/push before any future physical mutation.

Test305 follow-up:11 bounded readonlyWiFi rows completed; same299boot57535...,
allSDP500mA/SOC0/temp31.3C/netnegative, min3.135V/final3.145V. No chargerchange
observed/owner C2reconnect pending. Monitor terminal/notrestarted; no mutation,
flash/reboot/PPS/pump/current/ADC invocation. EntrySTOP lowbattery; first restore
ordinaryaccepted18Wcharging, thenSOC/VBATsafe andregisteredphysicalscope. Read
305low-battery-observation raw/summary. Offlinequalification unchanged; no
host/buildrepeat. Goalactive/fullStage3NOTREADY, notCPUwedgecausalproof.

Test305 OFFLINE_ADC_CONDITION_CANDIDATE_QUALIFIED, source9dceb767. One isolated
ENHIZbit7 clear/unchangedADC/verifiedrestore, OFF+ADC-off checks/firsterror+cleanup/
pendingfault onfailure/PMdrain; no companion publication/reschedule/secondresume
experiment/PPS/pump/reset/threshold/current. Default/passive/policy compiled
paths unchanged; new default-n SM5440_ADC_CONDITION_TEST only explicit profile,
cannot coexist withPPSconsumer. Full1748PASS112.621s then final21PASS0.705s with
addedpreprocessorcheck;1749unique (1728reused+21final), nofail/error/skip/CI.
ARM6492.647/W1sparse8.078/object+vmlinuxidentical/96protected/10overlays/181paired
PASS; exactlyTest299config absent->y diagnostic symbol, DTB identical. Driver
warnings0/checkpatch0/upstreamvDSOwarning retained. Old297cache reused onlyafter
2733debug/generated inputs compressed+verified;25formal263297299302303seals intact,
old297cachepath no longer usable provider. Read305RESULTS/summary/design.
Device still299/Test30057535...sameaccepted notes/config, no mutation. Final
read found0%/3.287V/netnegative/SDP500mA/31.3C/SinkDevice; WiFi10.139.153.19 strict
SSHresponsive. PHYSICALENTRYSTOP lowbattery; owner asked reconnectaccepted18W C2,
no reboot. Recharge is ordinary baseline, notcandidateacceptance. No flash/PPS/
pump untilbattery recovers andnewphysical scope registered+pushed. ENHIZcause/
ADCvalidity100ms/OCP/activecoordinator/physicalPPS+PM remain/fullStage3NOTREADY/
fullgoalactive. Do not invoke known-failing303 or relabeldiag ascharginggrant.

Test304 READ_ONLY_OPERATING_STATE_CAPTURED. Same retained299/Test30057535...
notes/config;19 single stable control/identity regmap reads (exact range0-2b,
7-byte seek/read/O_RDONLY/noINT), no devicewrite/reboot/PPS/pump/faultclear.
CNTL6=89/ENHIZ1; vendor init09 clears it but vendor attached+OFF explicitly
setsENHIZ1: condition difference, NOT proven bug/cause. Other principal init
controls already match vendor; do not import wholesale active init. Inherited
inactive VBATCNTL37=4487.5mV/IBUSCNTL41=3250mA not measured/approved limits.
Sameboot1180journal/zeroCPUfault+thermaldisable/packzoneenabled31.8C/noSM5440zone;
snapshot stale/fault1/pending2 remains. Startup pairs222/328mV difference,
142/128ms converter intervals retained; cause/100ms grant unresolved.
Initial wrong debugfs path rawerror retained, corrected set-e source path.
Evidence-only host/build executed:false; no full/CI. Read304RESULTS/summary.
Next isolated source-backed ENHIZ/ADC condition comparison with OFF/readback/
restore/PM/fault preservation, registered before mutation; no delay-only replay,
guessedoffset/threshold waiver or known-failing303 invocation. Stage3NOTREADY/
fullgoalactive;303consumer remains offline/currentdevice299 thermalfix retained.

Test303 OFFLINE_OWNED_PPS_CONSUMER_QUALIFIED, source53f223cf.568unique affected
PASS (511unchanged reused+57final); ARM6491.651s/W1sparse8.435s/object+vmlinux
identical/96protected/10overlays/4headercopies/181paired PASS. Explicit policy
offline profile only: exactly X710_CHARGING_POLICY n->y vs302, DTB identical,
container/DCC preserved. Real pack/strict100ms SM5440 proof/Q4lease/nativePPS->
fixed/source-bound async authorization release; PM cancellation/drain/noautoarm/
unresolved blocks retry+suspend/native failed fallback not retried. Release
notQ4completion: unchanged ordinary poller programs later, try-only locks avoid
501ms possible IIO wait under TCPC. No auto-start/pumpON/devicecommand/PPS/
rootfs/core/USB/ordinarylimit change. Source style0errors/1MAINTAINERSadvisory/
2bracechecks retained; changed driver W1/sparse0warnings. No full/CI.
Old301cache reused after2731debug/generated inputs compressed+hashverified;
301/302 formal artifacts immutable/302cache retained/old301path no longer usable
provider. Device stays299/Test30057535...thermalfix. Read303RESULTS/summary/design.
ADC validity/startup/refusal/>100ms physical gate remains unwaived; next source-
backed operating-condition fix before physical replay, not delay-only retest.
Physical PPS/pump/activeOCP/PM/fullcoordinator acceptance remains/Stage3NOTREADY/
fullgoalactive. No automatic deployment of known-failing ADC prerequisite.

Test302 OFFLINE_OWNED_TCPM_PPS_PROTOCOL_QUALIFIED, code de2ebc5c/build21d534c1.
185affected PASS5.102s/ARM6496.678s/W1sparse8.361s/object+vmlinuxidentical/
exact301configDT/96protected/8overlays/twoheadercopies/181paired PASS. No full/CI.
Actual kernel-only ONLINE2/current/voltage with checked switch-OFFlease/source/
token; exact per-operation RDO permission closes onreturn, native2.5W standby,
kind distinguishes PPS9V from fixed9V. No installed liveconsumer/devicePPS/pump/
release/core/DTconfig/USB/current increase. Sharedheader changes require newly
paired module CRCs. Device stays retained299/Test30057535...thermalfix. Owner
photo byte-identical to299; read-only sameboot1145journal/zero thermal disable,
packzone37enabled31.8C, noSM5440zone; see300photo-followup-2026-10-02.
Read302RESULTS/summary/design. ActiveStage3 NOTREADY; liveconsumer/PM/physical
ADCfreshness/OCP/PPS/pump acceptance remain/fullgoalactive. Next purposeful
pumpOFF protocol scope onlyafteractual physical gates, no unchanged delay replay.

Test301 OFFLINE_TCPM_FIXED_RESTORATION_QUALIFIED, source2207d132.143affected
PASS4.549s/ARM6492.282s/W1sparse/linkedobjects exact (initial omitted ccacheBASE
mismatch retained/resolved)/exact299configDT/96protected/8overlays/181pairedPASS.
No full/CI/devicewrite/PPSactivate/tune/pump/release/liveconsumer; actualRequest
stillfalse. Kernel-only standardONLINE1 restore requires exactport/source and
acquiredlease, no propertylocks/pinned drain/zerooutput; alreadyfixed no write.
USBTYPEcapability +ONLINE1 fixesPPS-capable fixed observation; ONLINE2/3 refused.
Budgetchange stillrevokeslease/inhibit, logicalsnapshotnotphysical/releasegrant.
Device remains retained299/Test30057535... thermalfix, alloldseals intact.
Next owned PPS callback/exactRDOauthorization +liveconsumer with ADC/OCP/PM
physical gates, not delay-only replay. Read301RESULTS/summary/design; activeStage3
NOTREADY/fullgoalactive. Staticcommands must inherit CCACHE_BASEDIR=.work and
sloppiness from build script; make will not detect a changed ccache environment.

Test301 OFFLINE fixed-restoration prerequisite implemented/143affected host PASS.
Fixed snapshot uses ONLINE1 + PD capability (PD/PPS/SPRAVS/dual), never ONLINE2/3;
new kernel-only ONLINE1 fallback requires exactport/source +acquired lease,
real standardPSY/no propertylocks/pinned drain/zerooutput/refusals. No activation/
tuning/pump/release/liveconsumer; actualRequestguardstillfalse. Budgetchange
stillrevokeslease/inhibit; logicalsnapshotnotphysical/releasegrant. ARM64/static/
configDT/protected181 qualification pending. Device remains retained299source
9173df11/Test30057535..., thermalfixnotreverted/no deviceoperation. Read301README
and docs/SM5714_TCPM_FIXED_RESTORE; fullgoalactive/activeStage3NOTREADY.

Test300 PASSIVE_THERMAL_FIX_DEVICE_ACCEPTED_CANDIDATE_RETAINED. Currentdevice
source9173df11/Test299, boot57535beda62648d0aaaa3071ac8332e5; NO LONGER263.
Oneboot/dynamic noSM5440thermalzone/realpackzone37enabled31.1->31.5C/15sendpoint
ADB/deviceNCM/SinkDevice/Code0/config notes/fullJSON/noCPUfault pass. Retained
underregisteredfe9ca9ce; all5write/readback/181paired/BCBclear/unmount pass.
Notesaea7c145b3901408040453648d8f81cd4cca23f27443d0e1c30d701e35717403; configf2891de2 unchanged.
Knownpassive startuprefusal/fault1 stays; nofakeTEMP/clearfault/activegrant/PPS/
pump/current. HostNCMoneprobe255 recorded/no prolongedretry. Exact263boot+
300original181modules/olderbackups retained; rollback:false onregisteredPASS.
29affected/buildW1sparse/exactconfigDT/protected181299 reused+8runnerPASS;
no full/buildrepeatCI. Read300RESULTS/CURRENT_STATUS/PACKAGE/summary/raw.
Next real liveTCPM/PPS adapter; USBTYPEPDPPS capability != ONLINE2 activePPS;
ADC/OCP/PM remain unresolved/Stage3NOTREADY/fullgoalactive. Reuseinstallation
when inputsunchanged; newmutation needsregistration. No224sdelay/oldfixrollback.

Test300 ONE passive thermal registration fix test registered. Source9173df11/
29929affected/buildW1sparse/exactconfigDT/protected181 qualified;8runner PASS.
PCUSB/one candidate boot/dynamic thermal NAME absence+realpackvalid/15sendpoint;
retain299PASSfix/paired181 ondevice; exact263rollback onlyonfirstfailure/new300
original slots retained. Current263acdd2dfc all5/181/confignotes/rescue/packnormal
preflightpass; oldzone37SM5440warning explicitlypreflight-only, nevercandidate or
packwaiver. NoPPS/pump/current/ADCmath/threshold/faultclear/core/DTconfig/USB change.
Pushregistrationbeforemutation; no224sdelay/fullrepeatCI. Read300README/plan/
PACKAGE. Goalactive/Stage3NR; retention fixesowner symptom, notdirectgrant.

Test299 incident+OFFLINEfix qualified9173df11. Thermalzone37 old263/acdd2dfc
isSM5440passive, refusedstartup4.037s->cacheENODATA->autozone disabled224.224s;
packzone38/IIO31.8C normal. Onlydesc.no_thermal=true; TEMP/ENODATA/fault/sampler/
packpolicy unchanged.5registration+24passive tests/ARM6496.64s/W1sparse/objectsame/
exact297configDT/protected96/overlays/181pairedPASS. No device mutation/PPS/pump/
current/rootfs/DTconfig/coreUSB. Next pushTest300oneboot/assertpassivezoneabsent+
realpackzone/15s endpoint; retainPASSfix, exact263rollbackonfailure. No224sdelay/
fullrepeatCI. Goalactive/Stage3NOTREADY. Read299RESULTS/summary/raw/photo.

Test299 owner photo thermalzone37 at224s attributed read-only to restored263/
acdd2dfc, typeSM5440passive/cacheENODATA afteroldstartuprefusal4.037s. Packzone38
normal/enabled31.8C/IIO, noCPUfault/servicefailure. `.no_thermal=true` onlypassive
PSYmetadata prevents automatic tripless registration; TEMP/ENODATA/fault/ADC/
packthermal unchanged.5actualmainline-registration +24passive host PASS;
ARM64qualification pending. No newdevicewrite/PPS/pump/current. Next register
one Test300 short absence-of-passive-zone +packzone proof/15s/exact263rollback;
no224sdelay needed toprove registration absent. Goalactive/Stage3NOTREADY.

Test298 RUNTIME_DEVICE_DIAGNOSTIC_COMPLETED_EXACT263_RESTORED. Sourceeefef33f,
registration15f1bae6/oneboot1b47865f/oneAPIret0 at17.275s:
instance1/source9/budget14/PDO3701912c fixed5V3A/currentTCPM5V1.8A;15sdevice
endpoint ADB/deviceNCM/SinkDevice/Code0/noCPUfaultpass. PCactualinput500mA/SDP,
not9Wphysicalmeasurement/chargegrant. CandidateSM5440cachedOFF/fault0/IBUS0;
oldADC/OCP/PM questions unresolved. HostNCMoneprobe255 recorded/no retry.
All5/181263 restored/BCBclear/rootunmounted; finalacdd2dfc
Good43%/3.817V/29.8C/ADB/deviceNCM/Code0.
10runner PASS;reuse297119/buildW1sparse/exactconfigDT/protected181/no fullrepeatCI.
NoPPS/pump/current/rootfs/configDT/USB/core change. Read298RESULTS/summary/raw.
Next real liveTCPM/PPS coordinator withphysicalADC/OCP/PM gates, no delay-only
replay. Fullgoalactive/Stage3NOTREADY. Changedchecks+shortpurposefuldevice scope.

Test298 ONE standardTCPM runtime read registered; qualified297sourceeefef33f/
119tests/buildW1sparse/exactconfigDT/protected181 reused;10new runner PASS.
Current263ffca1c7b sameboot/all5/181/confignotes/ADB/deviceNCM/Code0/Goodbattery
read-onlypreflightpass; NCMauth sameboot/PD5V reported. One0400realAPIread +15s
endpoint/exact263rollback; unexpectedrefusal STOP/no retry/no observermodule.
ExplicitENODATA only ifPCnoPD; contract values notphysical/grant. Pushregistration
beforemutation; new298backupslots. Host-onlyNCMoneprobe/no prolongedwait; device
safety mandatory. NoPPS/pumpON/current/ADCthreshold/USB/core/DTconfig changes.
Read298README/registration/PACKAGE; goalactive/Stage3NOTREADY.

Test297 OFFLINE_RUNTIME_SNAPSHOT_QUALIFIED, sourceeefef33f (d352deb4 +macrofix).
119affected PASS4.399s; ARM6466.85s/W1sparse/objectidentical/exact296configDT/
protected96/compiled overlays/181pairedpass. Initial macro build failure retained;
fixed actualC fixture covers kernel macro. StandardTCPM/source/fixed mirrors/
lifetime drain/0400realAPI; no atomicTCPM/physical/chargegrant claim. No core/
configDT/USB/SM5440/PPS/pump/current change. Next separate one Test298 read/
15sdeviceendpoint/exact263rollback. Fullnotrerun/noCI; goalactive/Stage3NR.
Read297RESULTS/summary/validation. Current263ffca1c7b unchanged/read-only298preflight.

Test297 runtime snapshot implemented;119affected SM5714 host tests PASS4.546s.
Lifetime-pinned standard TCPM PSY/source/fixed callback mirrors, generations,
zero-output refusal/no property locks;0400 debugfs uses actual API. No PPS/pump/
charge grant/configDT/USB/SM5440 changes. ARM64/W1sparse/pairing pending; no new
physical operations. Next separately register one short Test298 read +exact263
rollback, not more ADCdelay trials. Currentdevice last263ffca1c7b from296.
Read297README/registration +SM5714_TCPM_RUNTIME_SNAPSHOT. Fullgoalactive/Stage3NR.

Test296 DEVICE_REARM_DIAGNOSTIC_COMPLETED_EXACT263_RESTORED. Source18e495bc,
oneboot6f688b21/3pairs/15sdeviceendpoint pass;
20msvendorrearm didnotresolve adjacentwindow224.5–319mV difference; startup
refusal2.666175s retained/nocalibration orcausalproof. ADB/deviceNCM/Code0/noCPU
fault, hostNCMtimeouts recordedunderdevice-centredscope/no retry. All5/181263
restored/BCBclear/unmounted; finalffca1c7b Good44%
3.826V30.2C, passivehealthREFUSED.
228affected+5runner/ARM6491.64s/W1sparse/objectsame/exactconfigDT/protected181pass;
no fullrepeat/CI/PPS/pump/current/threshold/faultclear. Read296RESULTS/paired/raw.
Next real mainline coordinator prerequisites +vendorOFF-modeADC validity, not
more delay-only trials orguessedoffset. Fullportgoalactive/Stage3NOTREADY.

Test296 ONE source-backed ADC20msrearm comparison registered, source18e495bc.
228affected/8new+5runner PASS; ARM6491.64s/W1sparse/objectsame/exact295configDT/
protected/181pairedpass. CheckedOFF/ADCdisable+unlock20ms+cancellation before
unchangedconverter; no ADCmath/threshold/deadline/fault/freshnesswaiver. OnePCUSB
boot/three startup pairs/fullJSON/15sdeviceendpoint/exact263rollback; hostNCM
oneprobe recorded, host-onlytimeout doesnot prolongOFF-only diagnostic; device/
Code43/kernel/thermal gatesremain. Push beforemutation; read296docs/registration/
package/artifacts. No PPS/pump/current; notcausalproof/Stage3activeNOTREADY.

Test295 PAIRED_STARTUP_CAPTURED_STOP_NCM_EXACT263_RESTORED. One1028ae06 boot,
3near-time pairs: SM5440/gauge3.5985/3.891,3.6/3.844,3.499/3.854V;244–355mV
adjacent-window difference, no calibratedoffset/trueVBAT/causalproof; startup
refusal at2.594914s retained. FirstcandidateNCMtimeout STOP/no15sendpoint/retry;
ADB/deviceNCM/WindowsCode0/noCPUfault. Exact263all5/181restore/BCBclear/unmounted;
finalADB Good45%3.831V29.9C, NCMhosttimeout/passivehealthREFUSED. 208affected+
11initial/12recoveryrunner tests/build/W1sparse/exactconfigDT/protected/181pass;
fullnotrerun. No PPS/pump/current/threshold/faultclear. Read295RESULTS/summary/
paired-voltage/raw. Next source-backed ADCoperating-condition analysis, not
samefailedtransportprofile or guessedcalibration. ActiveStage3NOTREADY.

Test295 ONE short paired-startup-voltage diagnostic registered, source1028ae06.
208affected +11runner PASS/ARM64/W1sparse/exact294configDT/protected/181paired.
Only startup gauge read outsideio lock; original converter/100ms/500ms/threshold/
deadline/fault unchanged. PCUSB held; ADB+strictNCMSSH sameboot required;
WiFi host unreachable recorded/notrequired forPCscope. Onecandidateboot/cache/
fullkernelJSON/15sendpoint/unconditional exact263rollback; oldstartuprefusal
retaineddiagnostic, no charginggrant/PPS/pump/current. Push beforemutation.
Read295README/registration/PACKAGE/ARTIFACTS/design. ActiveStage3NOTREADY.

Test294 OFFLINE_SWITCHING_OWNERSHIP_QUALIFIED_DEVICE_NOT_TESTED, sourcebb534146.
16actualC +1557full host PASS/0failureerror skip/all1520priorIDs retained; ARM64
99.44s/W1sparse/objectconsistent/exact290configDT/96protected/8overlays/181paired
archive pass. New lease inhibits beforecheckedQ4OFF+100mA, preservesfixedbudget;
standby/budget/fault/detach/PM/unbind revoke butkeepinhibit; rebind sticky/unique
issuer; release needscaller-proven pumpOFF/freshphysicalfixedVBUS. Defaultinactive/
no liveconsumer/PPS/pump/current change.167modulefiles differ: use newpaired294
archive; no section-cause claim. Old263290291292293seals intact. Read294RESULTS/
summary/artifacts/design. Current263b06bb6c2 ADB sameboot Good47%3.845V32C, passive
healthREFUSED unchanged. ActiveStage3NOTREADY/fullportgoalactive.

Latest owner workflow2026-10-02: check actual changed parts, avoid long repeated
review; prioritize short purposeful physical tests using qualified candidates.
Use Fedora X710, S9Ultra common-platform work and Samsung stock as evidence
when helpful. Reuse unchanged build/tests, no routine full-suite run per change
or result commit; broaden only for demonstrated dependency/routing concern.
Register/push each physical scope before mutation; essential identity/thermal/
pumpOFF/rollback and first-failure safety remain. Do not repeatedly flash the
same failed profile; obtain evidence, source-backed fix, next bounded test.

Additional D:project cleanup2026-10-02:7obsolete Kbuild intermediates +13clean
detached source worktrees removed; 36.93GiB guest allocation / 30.95GiB
observed D:free increase, now~37.28GiB free. All43186out/oldreference files
hash-unchanged;21262debug/config/module/generated inputs moved+verified under
.work/host-storage-cleanup/2026-10-02-reclaim/retained-build-inputs. Current263/
272/290/default build providers, formal packages, rollback, WindowsADB/stock/263/
292 remain; Git revisions/tags intact. Removed7oldincremental dirs no longer
usable as build trees; reconstruct ifneeded. Online trim only/no WSLshutdown/
offlinecompact/devicecmd/sourceconfigDTUSBchange. Readreference/host-storage-
cleanup/2026-10-02-reclaim/README, compressed manifests/summary/validation.
Storage-only build/hostregression executed:false. Chargingstate293 unchanged.

Test293 OFFLINE_STARTUP_SAMPLE_REFUSAL_ATTRIBUTED;21affected actual263C/replay
PASS(512combined/1024faultbytevectors),syntax/CLI/old263290291292seals unchanged.
292final b06bb6c2 confirmation2.304099s/576ticksHZ250 =>5sdeadline excluded.
Sole sample predicate VBAT3.4985V<3.5V by1.5mV; OFF/ready/online/VBUS/IBUS0/die/
fault0/protections pass. ADC5a a8/raw2901 matchesvendor; trunc3498mV vs3498.5mV
not scaleerror. Gauge3.879V measuredat283.59s vsretainedsample2.602s: notsamewindow/
calibrationoffset; physical causeUNKNOWN. Parserdiagnostic only/allgrantsfalse;
no threshold/reset/ADC/deadline changes. No devicecmd/kernel/buildfull/routing/CI,
reuseunchanged290/291qualification. Read293RESULTS/replay/INPUTS/script/tests.
Next source-backed samewindow/sensor qualification design, notsamefailedround or
relaxation. Currentdevice lastverified292263b06bb6c2/rescue normal/passivehealth
REFUSED unchanged. Fullwiredportgoalactive/ActiveStage3NOTREADY.

D:project staging cleanup2026-10-02 completed:326oldfiles, ~5.39GiB reclaimed,
free~6.32GiB. Byte-SHA duplicates +two181file payload-identical uncompressed
archives removed; unique smallrecords archived/3packets tracked. Preserve Windows
android/platform-tools +gts9-active/{gts9-stock,gts9-test263,gts9-test292}; no other
Windows/VHD/userfiles/driver change. Readreference/host-storage-cleanup/2026-10-02
manifest/validation/README; storage-only build/tests executed:false. Future rounds
pruneverifiedobsolete staging afterevidencearchive, retainactive+rescue. Current
device remains restored263b06bb6c2 from292: rescue responsive, passivehealthREFUSED;
no newdeviceoperations/charginggrant. Activefullportgoalunchanged/Stage3NOTREADY.

Test292 STOP_ADB_TRANSPORT_NO_OBSERVATION; exact263all5/181rollback verified.
One290candidateb8945a98, zeroobserver/calls/trace/PPS/pump/current. Earlyhost
readiness missed DHCP; sameboot IPv4 observed77.285s,18portable fixPASS. After
interruption Wi-Fi sameboot healthy; hostADBdaemonstartup failed/emptylist while
WindowsCode0/NCMUp/deviceadbdactive/DWC3configured. FirsttransportgapSTOP;
strictWi-Fi BCBhelper+ordinaryreboot/TWRP exactrollback/new292tested/oldbackups/
BCBclear/unmounted. Final263b06bb6c2/Wi-Fi10.125.29.6 exactidentity/ADBWi-FiNCM/
WindowsCode0/Good52%3.879V31.9C/noCPUfault, but PASSIVE HEALTH REFUSED fault1/
pending1/staleOFFsampleVBAT3.4985V vsgauge3.879V/IBUS0. Nohealth exemption/reset/
replay; rootcause/calibration unresolved. Read292RESULTS/summary/raw. Reuse290/
291 buildfull;18portable only; noCI. OfflineUSB/VBAT analysis before newround.
ActiveStage3 NOT READY/fullportgoalactive. Dstoragecleanup authorized/inprogress,
retaincurrent263/292 rescue/stock andADB.

Test292 ONE passive observation registered;16portable tests/syntax/package pass.
Reuse290provider8e890215/291consumer0c5bc998 +1520full/static; no build/full/trace
repeat. Readonly current263d856e6f5 all5/181/config/notes/normalcmdline/healthOFF/
full286journal/ADB/authenticatedWi-Fi/deviceNCM/WindowsCode0 passes. Initial SSH
hostkey lookup failed; publickey pinned through ADB, strict checking recovered
sameboot (raw failure retained). Newpaired290bootd268d702/181modules +module333fe5,
oneboot/load/call/500msDIAGNOSTIC/5scompletion/10sunload; no100msfreshgrant/ADC/
PPS/pump/current change. Push beforemutation; unconditionalexact263rollback/new
292slots/oldbackups retained. Groupinstall/admission/onecall/endpoint/rollback;
read292README/registration/PACKAGE/host_flow. ActiveStage3 NOT READY/goalactive.

Test291 ONE_PASSIVE_OBSERVER_OFFLINE_QUALIFIED_DEVICE_NOT_TESTED.
Independent module333fe5ee/APIobserveCRCcbefd51c paired with2908e890215, onecall/
no retry ortrace; genuine age/seq/epoch, charge+legacyfreshgrant0. Parkedownedtask/
stop_put lifecycle retained.26C/cache/lifetime/builder/coordinator +1520fullPASS,
all1494priorIDs retained/0failureerror skip; externalbuild/W1sparse/samebytes,
290provider and276/289/290seals intact. No kernelrebuild/driverDTconfigrootfsUSB/
ADC/legacy100ms/PPS/pump/current/devicecmd/CI change. Read291RESULTS/artifacts/
inputs/design; separate292physicalregistration needed. Current263d856e6f5 read-only
292preflight sameboot/WindowsCode0; admission completion pending. ActiveStage3
NOT READY/fullportgoalactive. Next grouponepassivecall/endpoint/263rollback,
reusequalification/no redundanttrace/buildfull.

Test290 PASSIVE_OBSERVATION_OFFLINE_QUALIFIED_DEVICE_NOT_TESTED, source8e890215.
13actualC/1494fullPASS/0failureerror skip/all1481prior IDs retained. OneARM64build,
W1sparse/objectconsistent, exact272embeddedresolvedconfig/DTB,96protected/8compiled
overlays/181pairedarchive PASS.167modulebinary changes allBTF(+onebuildid/debug),
otherELFsections incltext match; use newpairedarchive. Old272artifacts/276/283-289
seals intact. Separate500ms DIAGNOSTIC API returns actualoldest acquisition age,
completion/delivery/seq/epoch; legacy/active100ms +converter/quiesce unchanged.
No consumer/observer wired/devicecmd/PPS/pump/current/DT/config/USB/rootfs change.
Installed263d856e6f5/Wi-Fi10.125.29.32 lastverified289 unchanged. Read290RESULTS/
summary/artifacts/seal/design/futureplan. Full coverschangedselection; no repeat
wrapper/buildfull/CI forresultcommit. Next separately qualifyowned passiveconsumer
then oneindependentregisteredcall/263rollback, no samelegacyrefusal replay or
active100mswaiver. Calibration/OCP/livePM/PPS/pumpremain open: Stage3 NOT READY;
fullportgoalactive. Groupstages/batchedtools/parallelreads/reusequalification.

Test290 OFFLINE implementation/build+1494full host PASS; committed-source
artifact pairing/W1sparse finalaudit pending, no device test. Independent passive
observe API returns true oldest acquisition/completion/delivery/age with500ms
DIAGNOSTIC collection only; legacy100ms cached/fresh +active100ms policy andADC
sequence untouched.13new actualC tests,0removed/skips; exact272config/DTB and96
protected inputs pass. Newdriver/header only; fixed/thermal/USB/rootfs unchanged.
Read290CURRENT_STATUS/registration/SOURCE_INPUTS +SM5440_PASSIVE_OBSERVATION_API.
Installed263d856e6f5/Wi-Fi10.125.29.32 unchanged; noflash/reboot/PPS/pump/current.
ActiveStage3 NOT READY/fullportgoalactive; keep289refusal immutable.

Test289 PASSIVE_REFUSAL_CAPTURED; EXACT263_ROLLBACK_DEVICE_SCOPE_COMPLETED.
One2727a4d9ce5boot/one276observer/onefresh-110/0usable; firstrefusalSTOP.
288phaseprofile captured18successfulI2Ctransactions/4polls[0,0,0,1], request
103.737ms/queue8us/worker139.945ms, enable-to-ready-reply127.416ms WALL only;
I2C17.483ms/intertransaction122.436ms, no ADCduration/calibration/timing grant.
Requiredfinalreads afterreturn; exactbranch/causalassignment UNKNOWN. Actual0x0d
AVG32bit3 matchesvendor mask1shift3/FedoraBIT3; bit2UNKNOWN, no guessed field/fix.
Collection0.1457s/500mstail/cleanupunload1.0721s; sameboot healthyOFF/rescue/noCPU
fault/Code43/ownedtraceobserver absent. Exact263all5/181rollback/tested289+
oldbackups retained/BCBclear/rootunmounted. Final263d856e6f593254cc28f3a178579e07c1b
Wi-Fi10.125.29.32/confignotesnormalcmdline/full286journal/uniquehistory/ADBWi-Fi
/deviceNCM healthy; battery64%4.000V31.1C/OFFfault0IBUS0. Displaydiagnostic remains
unresolved/notstabilityclean. Read289RESULTS/summary/raw/seal. Results testsbuildfull
executed:false/reuse28836/28920/2722761481W1sparse/noCI. Next OFFLINE source-backed
acquisition/publication/delivery API design, notsameprofilereplay or100ms/ADCrelax.
No kernel/config/DT/USB/adbd/rootfs/PPS/pump/current change. ActiveStage3 NOT READY;
fullportgoalactive. Groupstages/batchedpush/parallelreads/qualificationreuse.

Test289 paired272deployment+candidateadmission PASS: 7a4d9ce5e4a64b5a82081c54ddcfce3f
/Wi-Fi10.125.29.47; exactidentity/normalcmdline/healthOFF/protection/
rescue/new286journal/uniquehistory. All5/181verified/new289original/oldbackups
retained/BCBclear/rootunmounted. Next ONE288phase acquisition/285IO/firstrefusal
STOP/cleanup/unload then unconditional263rollback. Read289INSTALL_STATUS/raw.
No ADC/deadline/PPS/pump/current change; reuse/no buildfull/CI. ActiveStage3 NR.

Test289 SINGLE passive I2Cphase observation registered on normal26351d70189/
Wi-Fi10.125.29.58; live identity/healthOFF/protection/rescue/286journal +all4
actualI2Ctracepointformats pass. Reuse272/276; select288phaseSession/coordinator/
decoder +285IO +286hostgate +283nativewaiter.20portabletests/syntax/staging pass,
no build/full/CI/sourcechange. Push beforetransfer/BCB/install. Oneboot/load/
max30s8calls100ms/firstrefusalSTOP/500mstail/ownedcleanup/unload; unconditional
exact263rollback/new289slots/oldbackups retained. Groupstages/batchedpush/
parallelreads/no percommand pauses. No newI2Caccess/ADC/deadline/PPS/pump/current/
USB/rootfs change. Read289README/registration/preflight/PACKAGE. ActiveStage3
NOT READY;287raw/refusal unchanged.

Test288 OFFLINE_I2C_PHASE_PROFILE_QUALIFIED_DEVICE_NOT_TESTED:36host/syntax/
source+protectedinput/279280283284285286287seals pass(formatawarehash-only/new
object audit). Newnamed privateSession/decoder/analyser/coordinator observes
existingbus0write/read/reply/result, notnewaccesses. Resultnoaddress=>all4
adapter_nr0filters; sameworkerPID+pollbounds/address63/complete source sequence/
counts/bytes/loss/hash/clock/cleanup required. Observedpolls/ADCbytes/I2Cwall+
intertransfergaps only; ADCduration/other110branchUNKNOWN, no timing/chargegrant.
287enqueueexcludesinitialbudgetbranch; latepollreturn notpublication/wakeup.
Newparser287UNKNOWN(missingI2C), rawunchanged. Zero device/source/ADC/deadline/
PPS/pump/current/buildfull/CI/routingchanges; reuse272/276/279/280/283/285/286/
287. Last26351d70189from287 unchanged. Read288README/RESULTS/qualification +
SM5440_I2C_PHASE_TRACE. Next separate ONEphysicalphaseprofileregistration/
newslots/essentialgates/exact263rollback; no aggregate repeat/100ms/ADCrelax.
ActiveStage3 NOT READY/fullportgoalactive.

Test287 PASSIVE_REFUSAL_CAPTURED + EXACT263_ROLLBACK_DEVICE_SCOPE_COMPLETED.
One2722fe71db0boot/one276observer/onefresh-110/0usable, firstrefusalSTOP.285IO
physically worked:4probes/7events/0miss/loss, request101.510ms/queue11us/worker
134.393ms ending32.900ms afterreturn; aggregate only, ADC/branch/causalityUNKNOWN.
Collection0.1217s/500ms tail/cleanup+unload1.0558s; sameboot endpointhealthyOFF/
ADBWi-FideviceNCM/noCode43/newCPUfault, ownedtrace+observer absent. Exact263all5/
181restored/tested287+oldbackups retained/BCBclear/rootunmounted. Final263
51d701890b84482d9d42b5b7db3508ad/Wi-Fi10.125.29.58 exactidentity/normalcmdline/
full286journal/health/rescue/uniquehistory, battery66%4.020V31.0C/Good/OFFfault0/
IBUS0, observerfreshAPI/DCCabsent. Startupdisplay diagnostic retained/unresolved,
not stabilityclean. Read287RESULTS/raw/summary/seal. Physicalrecordspan416.32s
not benchmark. Groupstages/batchedpush/parallelreads/nativewait; reuse/buildfull
executed:false/noCI. Old283284285286seals/protectedinputs unchanged. Next OFFLINE
worker/I2Cphase sourceanalysis oncapturedtrace, no sameaggregate repeat or ADC/
deadline/PPS/pump/current change; future physicalneeds separateregistration.
ActiveStage3 NOT READY/fullportgoalactive.

Test287 paired272deployment/readback+candidateadmission PASS:2fe71db013594aba
9153d2229a39f00d/Wi-Fi10.125.29.50, exactnotes/config/normalcmdline/currenthealth
OFF/protection/rescue/noCode43/uniquehistory/new286journal. All5/181verified,
new287original/allolderbackups retained/BCBclear/rootunmounted. NativeTWRPwait
27.65s; ancillaryavailability captured. Read287INSTALL_STATUS/raw. Next ONE
279/280trace with285IO/firstrefusalSTOP/ownedcleanup/unload then unconditional
263rollback. No repeat/PPS/pump/current/source change; reuse/no build/full/CI.
ActiveStage3 NOT READY.

Test287 SINGLE passive trace registered on normal263d0bbaeb8/Wi-Fi10.125.29.102;
live identity/health/OFF/rescue/new286diagnostic journal passes. Reuse272/276/
279/280, explicitly select285nonseekTraceFS +286bounded complete SMMUprofile +
283nativewaiter/ADC_UPDATED.19portabletests/syntax/staging pass; no build/full/CI
repeat/sourcechange. Push beforetransfer/BCB/install. Oneboot/load/firstrefusal
STOP/fixed500ms tail/ownedcleanup/unload; unconditionalexact263rollback/new287
slots/alloldbackups retained. Group stages/parallel independent reads, no per-
command pauses. No ADC/deadline/PPS/pump/current/USB/rootfs change; old284STOP
unchanged. Read287README/registration/PACKAGE/preflight. ActiveStage3 NOT READY.

Test286 OFFLINE_DISPLAY_STARTUP_CLASSIFIER_QUALIFIED_DEVICE_NOT_TESTED:19host+
syntax/real28499+103replay/source+compiledDTBmapping/input+283284285seals pass.
New diagnostic-only gate requires full sameboot currentidentity/healthyOFF and
complete <=10 SMMU triplets/first200ms/each1ms/priority3/SID1c00/cb9/splash/
exactflags/matching one observed98/99/102/103tag. Old STOPs/sharedparser/gates
unchanged; CPU/otherfaults stop. SIDdisplay/sourcechronology proved, rootcause
UNKNOWN; earlier unprogrammedbank/harmlessness claim corrected in docs. Zero
device/source/build/full/CI changes. Reuse272/276/279/280/283/285qualification.
Next separate single physical registration selecting285IO +286gate +283native
waiter; unconditional263rollback/no ADC/deadline/PPS/pump/current change. Read
286README/RESULTS/replay. Current263from284 unchanged. ActiveStage3 NOT READY.

Test285 OFFLINE_COMMAND_IO_QUALIFIED_DEVICE_NOT_TESTED:12hosttests inclrealHOST
seq_file appendopenEINVAL/nonseekopen+mockwrite, syntax/hash pass. Newadapter
tracefs_io overrides279kprobe_eventswrite: O_WRONLY|O_CLOEXEC/no append/truncate/
create/seek/onewrite/no retry/openvswrite stage errors. Frozen279Session/280/
parser untouched; no device/source/build/full/routing/CI changes.284actualexception
origin stillsourceinference(no syscallstage/devicePython captured); STOP preserved.
Captured284SMMU10310context+10syndrome rootcause/chargingrelationUNKNOWN, no gate
expansion/hardware retry. Read285README/RESULTS/INPUTS/smmu103facts. Last263from284
unchanged byoffline285. Next OFFLINE SMMU/boothandoff mapping before separate
physicalregistration withnewadapter; no ADC/deadline/PPS/pump/current changes.
Reuse27950/28024/272/2761481qualification. ActiveStage3 NOT READY; fullportgoalactive.

Test284 STOP_TRACE_SETUP_EINVAL; exact263rollback readback/currenthealth completed,
finaljournalSUSPECT retained. One272cdca467dboot admitted new283gate; first symbolic
request_enter definition EINVAL before observerload/tracestart, zero freshcalls.
Originalsetup/snapshot/cleanup errors retained; endpoint namedprobe/instance/
observer absent, kprobelist empty/enabled1/errorlogempty, sameboot device healthy.
All5/181263 restored/tested284+oldbackups kept/BCBclear/rootunmounted. Current263
bootd0bbaeb81d7a422e9e9e44f6e7346b77 notes/config/normalcmdline exact/ADBWi-FiNCM/
batteryOFF healthy/noCode43/CPUfault; fulljournal20early SMMU0x670021/context103
outside registered102 => STOP, not clean. Read284RESULTS/raw/summary/seal. Next
OFFLINE IO/source audit +SMMU evidence only, no auto physicalretry/ADC/deadline/
PPS/pump/current change. Reusequalification/results executed:false/no build/full/
CI. ActiveStage3 NOT READY; rootcause actual open vswrite not yet distinguished.

Test284 paired272deployment/readback+candidateadmission PASS: cdca467d7e604543
b76606c0706b3009/Wi-Fi10.125.29.144 exactnotes/config/normalcmdline+healthyOFF/
ADB/deviceNCM/noCode43/new283startupgate. Portabletools/packet/276observerhash
readback verified. Read284INSTALL_STATUS/raw. Next ONE279/280coordinatedtrace/
firstrefusalSTOP/ownedcleanup/unload then unconditional exact263rollback.
Originalmodules/allbackups retained; no retry/PPS/pump/current/source change.
Reusequalification/no build/full/CI. ActiveStage3 NOT READY.

Test284 independent SINGLE passive trace registered on normal26360b572d1;
preflight identity/health/rescue passes, Wi-Fi10.125.29.204. Reuse272provider+
276ownedobserver+279Session/280coordinator; new283boundedADC_UPDATED/currenthealth
hostgate and native recovery waiter.18portabletests/syntax pass, no runtime/source
change/build/full/CI. Push registration BEFORE device transfer/BCB/install. New284
backup slots; onlypaired272boot/181modules, onecandidateboot/observerload, first
refusalSTOP/fixed500ms trace tail/ownedcleanup/unload; unconditional exact263rollback.
Group stage/parallelreadonlycapture/reusequalification, no per-command pauses.
No gate/ADC/deadline/PPS/pump/current change; preserve282STOP. Read284README/
registration/PACKAGE/preflight. ActiveStage3 NOT READY.

Test283 OFFLINE_CLASSIFIER_AND_RECOVERY_FLOW_QUALIFIED_PHYSICAL_NOT_TESTED.
Read283README/registration/RESULTS/replay and CHARGING_ROUND_WORKFLOW.28hosttests
incl256INT4cases/ASTjournal equivalence+syntax/hash pass. New host gate permits
only startupINT4ADC_UPDATED0/1; all other275conditions retained + mandatorysameboot
currentidentity/healthyOFF. CPU/SMMU rules unchanged;282STOP/raw remain unchanged.
Native recovery waiter removes wrong-state fixed waiting in mocks (28245.948s
excess); not hardware speed benchmarked. No devicecmd/flash/reboot/load/trace/
PPS/pumpON/current/kernel/config/DT/ADC/deadline/USB/rootfs change; reuse272/276/
279/280/282 qualification, no build/full/CI. Lastverified Test263 from282 unchanged
by283. Future separate registered onepassive trace with new gate/waiter, essential
identity/rescue/safety gates + unconditional263rollback. Batch related checks/
parallel independent reads/reuse qualification/no per-command manual pauses;
never shorten safety/observation limits. ActiveStage3 NOT READY.

Test282 STOP_STARTUP_ADMISSION + EXACT263_ROLLBACK_DEVICE_ENDPOINT_COMPLETED.
One272dd9a0205boot; INT00 00 62 01 fails frozen275accepted00 00 62 00, bitmap80/
OFF01/01/IBUS0 and driverconfirmation2.300114s/currenthealthy retained. Zero
observerloads/freshrequests/tracefswrites/tools transfer; no exemption/retry.
Offline bit0=ADC_UPDATED sourcefact, not new acceptance; latchcause unresolved.
Read282RESULTS/summary/raw/sourceanalysis/seals. Exact263all5/181 restored/current
60b572d127b14921b4f5f7332f04d923 Wi-Fi10.125.29.204/ADB/deviceNCM healthy/noCode43/
newCPUfault; notes/config/normalcmdline exact, observer/freshAPI/DCCabsent.
All198protectedinputs/oldseals/portable/staging unchanged; results executed:false
reuse28218/272/2761481/W1/sparse/27950/28024; no build/full/CI. Next OFFLINE bounded
startupbitfield classification review/tests only, independent future physical
registration; no automatic retry/ADC/deadline/PPS/pump/current. ActiveStage3 NOT READY.

Test282 exact263rollback READBACK VERIFIED in TWRP: all5partition/181module
hashes exact; tested272modules and older backups retained/rootunmounted/BCBclear.
Next one263baseline boot/finalendpoint only.282startup STOP retained; zero
observerload/trace/freshrequest; no retry/PPS/pump/current. ActiveStage3 NOT READY.
Read282ROLLBACK_STATUS/raw/seal. Qualification reused/no build/full/CI.

Test282 STOP_UNCLASSIFIED_PASSIVE_STARTUP_EVENT on272dd9a0205: frozen275gate
rejects INT00 00 62 01 vs accepted00 00 62 00. OFF01/01/IBUS0/bitmap80, driver
confirmation2.300114s/currentfault0/healthy/ADBWi-FideviceNCM/noCode43/CPUfault.
No exemption: zeroobserverloads/freshrequests/tracefswrites/tools transfer. Read
282ACQUISITION_STATUS/raw/seal. Next unconditional exact263rollback only; no
second boot/acquisition/ADC/deadline/PPS/pump/current change. ActiveStage3 NOT READY.

Test282 paired installation READBACK VERIFIED in TWRP: sealed272bootd837b52f/
181modules, other4partitions exact263; original181modules under unique282backup/
allolderbackups retained/rootunmounted/BCBclear. Read282INSTALL_STATUS/raw/seal.
Next onecandidate boot/health+identity+rescue admission then onepassive trace and
unconditional exact263rollback. No repeat/PPS/pumpON/current/ADC/deadline change.
Qualification reuse; no build/full/CI. ActiveStage3 NOT READY.

Test282 independent SINGLE passive symbolic trace registered on accepted281normal
Test2631c1c3d0d. Read282README/registration/PACKAGE/preflight before writes. Reuse
272provider+276ownedobserver+279Session+280coordinator;18portable tests/AST/package/
syntax pass,198protected files unchanged; no build/full/CI. Push before transfer/
BCB/boot/modules. New282backup slots, onlypaired272boot/181modules; onecandidate
boot/observer load, firstrefusalSTOP, fixed500ms tail then ownedcleanup/unload.
Require exact normalcmdline and all health/rescue gates, loss/miss/pair/clock gaps
UNKNOWN, no causal/ADC/timing grant. Unconditional exact263rollback/readback/
endpoint; retain all old backups. No repeat/ADC/deadline/PPS/pump/current change.
Preserve275277280281history. ActiveStage3 NOT READY.

Test281 NORMAL_TEST263_BASELINE_REENTRY_COMPLETED: one ordinary reboot31e9a212
->1c1c3d0d387c469098bfcd6db2ac6fb3 uniquely attributed; exact accepted normal
cmdline restored (lpcharge=1 additions absent), configf2891de2/notesfea0613f exact.
All5partitions/181modules verified before reboot, zero software writes/changes.
Battery/OFF/fault0/PCSDP500/ADB/Wi-Fi10.125.29.181/deviceNCM/WindowsCode0 healthy,
no CPU signature/failed unit. Two endpoints86.64s apart, not continuous stability
proof. Read281RESULTS/raw/seal.280STOP retained. No observer/trace/fresh request.
Docs/results executed:false reuse28024/272/2761481/W1/sparse; no build/full/CI.
Next separately registered passive trace wrapper/deployment/263rollback only;
no PPS/pump/current/ADC/deadline change. ActiveStage3 NOT READY.

Test281 independent normal-baseline reentry registered after owner's continue.
Incoming31e9a212 exact owner-explained280lpcharge profile; Test263config/notes/
all5partitions/181module hashes/health/rescue verified once. ONEsystemctlreboot
after push, max180s readiness, exact accepted normal cmdline + unique boot history
and15s sameboot endpoint. If different/extra boot/fault/rescue gap STOP, no second
reboot/auto repair. No flash/module/trace/observer/charging change; preserve280STOP.
Read281README/registration. Docs/results qualification executed:false, reuse
frozen275277gates/28024; no build/full/CI. Active Stage3 remains NOT READY.

Test280 STOP_READONLY_PREFLIGHT_CMDLINE_IDENTITY / OFFLINE_COORDINATOR_QUALIFIED.
Owner confirms31e9a212 manual power-on/reboot, not unexplained reboot. Exact263
config/notes/device health normal; lpcharge=1 still differs from accepted normal
cmdline. No device mutation/trace/load/reboot/transfer/deployment; no retry or
automatic exemption.24 mock integration+syntax pass;198 protected inputs and
275277278279 seals unchanged. Single-process coordinator library only, frozen
observer gate AST and BOOTTIME/errno/count binding; no causal/ADC/timing grant.
Read280RESULTS. Reuse27950/272/2761481/W1/sparse; no build/full/routing/CI. Future
physical wrapper needs accepted normal boot and separate pushed registration/
paired readback/263rollback. Timeout attribution UNKNOWN; Active Stage3 NOT READY.

Test280 read-only preflight STOP_CMDLINE_IDENTITY: currentboot31e9a2127e7c41909c8ddd601badc85b
has accepted263config/notes, healthyPCSDP500/OFF/fault0/battery/ADB/Wi-Fi/deviceNCM,
but lpcharge=1 runtime cmdline differs from accepted normal boot. New boot cause
awaits owner; agent sent no reboot. Raw280preflight retained. No tracefs write,
observer load, transfer, flash or module change; no automatic identity exemption,
reboot or retry. Continue offline single-process trace/observer coordinator tests
only under280registration. Preserve279/275/277 seals; reuse qualification, no
build/full/routing/CI. Future physical test needs separate accepted normal-boot
registration. Active Stage3 remains NOT READY.

Test279 OFFLINE_COLLECTOR_QUALIFIED_PHYSICAL_NOT_TESTED:50 host tests+syntax pass.
Independent tracefs instance and symbolic probes; raw/hash/clock/loss/miss/PID/work
pairing and cleanup audited, no ADC/causal/timing acceptance inferred. Read279
RESULTS and docs/SM5440_FRESH_TRACE_COLLECTOR.md.198 protected files/21 Test278
inputs/275277278 seals unchanged; zero device/tracefs/load/request/flash/build/
full/CI. Reuse272provider/2761481/W1/sparse. Last verified263 from277 unchanged
by this turn. Next separate single passive trace registration; hardware/probe
acceptance and timeout attribution remain untested/UNKNOWN. No automatic retry,
deadline/ADC/PPS/pump/current change. Active Stage3 remains NOT READY.

Test279 registers an OFFLINE private-tracefs collector/parser qualification.
Read its README/registration before work. Host fixtures only: no device command,
tracefs enable, observer load, flash or hardware change. Preserve Test278 UNKNOWN
attribution and Test275/277 raw verdicts. Reuse sealed272/276 qualification;
affected host tests/syntax only, no kernel build/full suite/routing/CI. Future
physical tracing needs a separate registration. Active Stage3 remains NOT READY.

Test278 OFFLINE_TIMING_AUDIT_COMPLETED_ATTRIBUTION_UNRESOLVED:16host+syntax/
byte-identical report/source+275277seals pass. FourAPI-110 branches, all phase
latencies UNKNOWN/null. HZ25025ms=7ticks nominal28ms;112ms four-timeout budget
risk != actual conversion.277cache92ticks368ms != ADC duration, no absolute
BOOTTIME without anchor/false grant. Read278RESULTS/analysis and
SM5440_FRESH_TIMING_AUDIT. Frozen272source/config/DT/ADC/deadline/USB/rootfs/
hardware unchanged; zero device/probe/tracefs/build/full/CI. Reuse272provider/
2761481/W1/sparse. Lastverified263cdce6deb from277, no deployment in278.
Existing KPROBE_EVENTS/workqueue support can narrow future queue/worker timing;
sample_once standalone absent, runtime addresses differ from ELF, symbolic
resolution only. Future offline collector review + separate registered passive
trace, no automatic physical retry/relaxation/PPS/pumpON/current. ActiveStage3 NOT READY.

Test278 registers OFFLINE fresh-timeout source/evidence audit on frozen272/
276 and raw275/277. No device command/flash/reboot/request/kernel/config/DT/
ADC/deadline/USB/rootfs change. Current restored263 unchanged. VerifyINPUTS;
pure host analyser/tests report actual facts and missing phase timestamps,
never infer ADC fault/duration or110branch from errno/cache age.25ms nominal
sleep atHZ250 and100ms guard audited, no relaxation. Future symbolic tracing
plan only, no probe/runtime enabling. Reuse272build/2761481/W1/sparse, affected
host+syntax only/no routing/full/CI. ActiveStage3 NOT READY. Read278README.

Test277 DEVICE_NORMAL_ACQUISITION_REFUSED_ROLLBACK_COMPLETED: ONE2721cb7050bboot/
ONE276observer load/onefresh101ms-110 refusal,0usable/0.211s collection; unload
status0/moduledebugfsabsent/samebootADBWi-FideviceNCM normal/noCode43/newCPUfault.
No30s/timingpass;275STOP/unknown freeze causation retained. Exact263 all5partitions/
181modules restored; currentbootcdce6deba2e04f3481679632e38ac997, Wi-Fi10.125.29.166/
ADB/deviceNCM normal, pack77%/4.140V/32.9C/Good, passivefault0/pumpOFF/IBUS0,
DCC/observer/freshAPI absent. Early readinessstatus1 preserved; sameboot endpoint
completion separate, no new reboot/reflash/cable/software retry. Candidate
modules/allolderbackups retained. Read277RESULTS/summary/raw/seals.22localhost/
syntax pass; reuse272provider/2761481/W1/sparse, no rebuild/full/CI. No PPS/pumpON/
current/ADC/deadline/USB change. Next offline timing-path analysis, not physical
retry/limit relaxation. ActiveStage3 NOT READY.

Test277 exact263rollback READBACK VERIFIED in TWRP: all5partitions/181paired
modules, tested272 directory.gts9-test277-tested/allolderbackups retained,
rootunmounted/BCBclear. One revised276observer load unloaded normally; one
fresh101ms-110 refusal, device normal/acquisition not qualified. Next one263
baselineboot/endpoint only. Read277ROLLBACK_STATUS/raw. No retry/PPS/pumpON/
current/ADC/deadline/USB change. Reuse qualification/no build/full/CI.
ActiveStage3 NOT READY;275freeze causation remains unproved.

Test277 DEVICE_NORMAL_ACQUISITION_REFUSED: one2721cb7050bboot/one276observer
load/onefreshcall-110 in101ms/zero usable,0.211s boundedfirstrefusal collection,
no30s/timingpass. Unload returned0, module/debugfs absent; ADB/Wi-Fi/deviceNCM
sameboot normal/noCode43/no new detected CPU signature,20startupSMMU unresolved.
Read277observation/ACQUISITION_RESULT.275STOP/unknown freeze causation retained.
No retry/PPS/pumpON/current/ADC/deadline change. Next unconditional exact263
rollback under277registration; no further physical acquisition. ActiveStage3 NOT READY.

Test277 paired installation READBACK VERIFIED in TWRP: bootd837b52f+181272
modules, other4partitions exact263, unique277 rollback/all older backups retained,
rootunmounted/BCBclear. Registratione4d0a6d7 pushed beforewrites. Candidate boot
and one revised276observer9aafabf6 load next; no old274reload. No PPS/pumpON/
current/ADC/deadline/USB/rootfs change. Read277INSTALL_STATUS/install. Reuse
272provider/2761481/W1/sparse/22localhost qualification; no rebuild/full/CI.
ActiveStage3 NOT READY; unconditional exact263 rollback after diagnostic.

Test277 independent revised passive observer registered: sealed272399eb497
provider +2767a887eab owned-task observer9aafabf6, ONE PCUSB boot/load,
<=8calls/1s/100ms/max30s; first refusal ends early, safe unload/endpoint assessed
separately. Current exact263/590eca6a preflight passes five partitions/181modules/
ADB/Wi-Fi/deviceNCM/battery/pumpOFF. Preserve275STOP, no old274reload. New277
backup slots, all older backups retained; exact263 rollback after diagnostic.
Read277README/registration/PACKAGE/preflight.22localhost+syntax pass; reuse272
build/2761481/W1/sparse, no rebuild/full/CI. No PPS/pumpON/current/ADC/deadline/
rootfs/USB change. Push registration BEFORE writes. ActiveStage3 NOT READY.

Test275 STOP retained; exact Test263 rollback and device endpoint COMPLETED.
All five partition hashes and 181 paired module files match accepted Test263.
Baseline boot590eca6af9574abbb0fe98e127a6b835: ADB, Wi-Fi SSH10.125.29.70,
device NCM/sshd normal, no Code43; config/notes exact, DCC/observer/freshAPI absent,
battery Good, passive fault0/pumpOFF/IBUS0. Candidate modules and older backups
preserved. Failed e701 persistent journal1109rows ends316.436572s before request
513.484s; pstore empty. Actual freeze mechanism remains unproved, not a clean test.
Read Test275 RESULTS/final-summary; original STOP and raw evidence are retained.
Test2767a887eab task-lifetime fix is OFFLINE qualified:26affected/full1481/W1/
sparse pass, all1475 prior IDs retained,149 protected inputs/provider/config/DT/
181-module archive unchanged. New module9aafabf6 NOT deployed. Original274 module
must NOT be reloaded. No PPS/pumpON/current/deadline/ADC change. ActiveStage3
NOT READY; any revised physical observer test needs independent registration.

The entries below are historical checkpoints; the state above is authoritative.


Test275 STOP_TRANSPORT_LOSS_DURING_DIAGNOSTIC_UNLOAD. ONE272e7018be8boot/
ONE274observerload/onefreshcall-110 in108ms/zero usable/firsterrorSTOP. rmmod
timeout20s, postkernel reads timeout25s, Wi-Fi252banner timeout; Windowsenumerated
ADB/NCM Code0 != devicehealth. Read275CURRENT_STATUS/summary/STOPseal/raw. No
complete30s/endpoint acceptance/retry/PPS/pumpON/currentincrease. Owner asked for
TWRP;272installed,263rollback NOT yet executed/confirmed. No Debian boot/reload.
Source audit proves observer unowned exited kthread pointer lifetime bug; actual
post-unload kernel fault/CPUstall cause UNKNOWN until persistentjournal. Preserve
APIrefusal separately; old274module NOT safe for further load/unload. Next offline
lifetime fix only, no deadline/ADC/register/safety relaxation. ActiveStage3 NOT READY.


Test275 ONE272candidateboot e7018be8 healthy, no observer loaded yet. Original
host startup STOP preserved: extra bitmap substring rule misclassified frozen
0x80 twofresh recovery (0.290722->2.598256s), currentfault0/OFF/IBUS0/gauge4.146V/
31.2C/SDP500.16affected tests+syntax pass for exact earlysafe branch attribution,
no live/incremental/other/repeated/late fault exemption; globalparser/driver/gates
unchanged. Read275STARTUP_OBSERVER_CORRECTION. DHCPnew10.125.29.252 is derived
from ADB and authenticatedsameboot, no staleIP retry. No repeatboot/flash/latch
clear/PPS/pumpON/current/full/build/CI. Push correction before one observer load.


Test275 paired installation verified in TWRP:272bootd837b52f+181modules,
other4partitions exact263; new275-original rollback/allolderbackups retained,
rootunmounted/BCBclear. Candidate not booted, no observer load/PPS/pumpON. Read
275INSTALL_STATUS and originalhoststops: p.e import beforeBCB corrected; unused
hostvbmeta b95e5ef9 vs accepted9844859b manifest corrected by readonly copy,
no repeated flash.12localhost/syntax pass; registrationseal checked at0e95e9e3,
installationseal separate. Reuse272/274qualification/no build/full/CI repeat.
Next one candidateboot/passive observer, firstrefusal unload/no retry.


Test275 registered passive fresh delivery: sealed272399eb497 provider +27410d57da0
observer, ONE PCUSB candidateboot/load, <=8calls/1s/100ms and bounded30s; first
refusal stop/unload/no retry, device-normal and acquisition verdicts separate.
Read275README/registration/PACKAGE/preflight: exact263 installed/181modules/five
partitions/ADB/Wi-Fi/deviceNCM normal,75%/4.105V/32.6C/fault0/OFF. Newboot
d837b52f; config/DT identical263, other4partitions unchanged; exact263 rollback
with fresh275slots/allolderbackups retained.11localhost/syntax/package checks pass;
reuse272kernel1424 +274final1475/W1/sparse, no build/full/CI repeat.20startup
SMMU suspects remain unresolved; local bounded diagnostic attribution only, global
parser untouched/no CLEAN claim. No PPS/pumpON/current/protection/gate/rootfs
change; ActiveStage3 NOT READY. Registration push precedes any device writes.


Test274 OFFLINE_BOUNDED_FRESH_OBSERVER_QUALIFIED at10d57da0: stand-alone external
GPL .ko9d66c080/267536B against frozen272provider399eb497; max8calls/1s/firsterror
STOP, cached0400/rawstatus/times, no parameters/readtrigger/I2C/ON/PPS/policy.
20affected (18actualC +2isolatedbuilder) and finalall1475 pass/zero skips; W1/
sparse/ARM64 pass, unchangedobject/module/config/DT/Image/181archive, all1424prior
and1473initial IDs retained. Initial1473 superseded after final frozen-source build
provenance guard, preserved. Read274RESULTS/summary/ARTIFACTS/finalseal and future
275plan. Publicsequence internalAPI guard, not exported/invented rowcounter.
No device commands/flash/reboot/install/current/hardware/rootfs changes; installed
263 remains. Results-only reuse qualification/executed:false, no build/full/CI
rerun. Future passive30s PCUSB/one observer load only after independent275 registration
and exactprovider deployment; never force-load on263. ActiveStage3 NOT READY:
actual100ms/ADC/nonzero current/OCP/liveadapter/PM still unqualified. C1APDO5–11V3A
captured273, not45W proof. Next passive acquisition acceptance, no automaticPPS/ON.


Test274 registers OFFLINE bounded freshADC diagnostic consumer. Read274README/
registration and SM5440_FRESH_OBSERVER before implementation. Stand-alone .ko
against sealed272 provider, max8calls/1s between successes/firsterror STOP, cached
read-only results, no autoload/parameters/PPS/pumpON. Installed263 unchanged,
no device commands/flash/reboot/current/config/DT/hardwaredriver changes. One
module build/W1/sparse and finalfullhost; reuse unchanged272Image/DT/181modules.
Future275 physical plan only; ActiveStage3 NOT READY. Docs-only executed:false.


Test273 DEVICE_SOURCE_IDENTIFICATION_AND_PC_ENDPOINT_COMPLETED_WITH_HOST_OBSERVER_
CORRECTIONS: ONE C1/C2empty attach, same263/846248af, counted6PDO +partner sysfs
agree: fixed5/9/12/15V3A/20V3.25A and PPS5–11V3A. Actualfixed9V1500/ONLINE1/
SM5714input1500,30.883s/7healthy samples,77%/29C, passivefault0/OFF/IBUS0.
Onecharger→PC endpoint ADB/WiFi/deviceusb0/sshd normal/noCode43/sameboot, SDP500.
HostNCM_TCP nottested. No newkernel fault;20oldstartupSMMU unresolved. Original
prepare/source hostSTOPs unchanged, freshnamespace completions separate; no
hardware retry/flash/reboot/PPS/pumpON/current/software/gate change. Read273
RESULTS/summary/finalseal; historicalseals verified at recordedcommits.31+18host/
syntax reuse, results-only executed:false/no build/full/CI rerun; unchanged272
qualification reused. C1APDO nowcaptured, not a PPS contract/45W proof; contract
ceiling13.5W != actualdraw. ActiveStage3 NOT READY until fresh100ms/current/ADC/
OCP/liveadapter/PM qualification. Next offlineconsumer/adapter audit, no automatic
higher-power activation. Installed263 and rollback unchanged.


Test273 source-completion COMPLETED30.883s/7samples same263/846248af after ONE
C1attach/C2empty. Freshcounted6PDO +currentpartner agree: fixed5/9/12/15/20V,
PPS5–11V3A; actualRequest fixed9V1500/ONLINE1/SM5714input1500, no APDO Request.
Battery77%/4.227–4.233V/+1.298..1.952A/29C, passiveGood/fault0/OFF/IBUS0/VBUS
9.136–9.148V, no new kernel fault;20oldSMMU unresolved. Originalobserver STOP
preserved, sameattach completion separate. Read273SOURCE_RESULTS/seal. OnePC
endpoint pending. No flash/reboot/software/PPS/pumpON/current change; results-only
executed:false/reuse31+18host/unchanged272build/all1424, no build/full/CI rerun.
Source APDO nowproved advertised; ActiveStage3 NOT READY until remaining freshADC/
nonzero calibration/OCP/liveadapter/PM gates qualified.13.5W contract != measureddraw.


Test273 C1source originalobserver STOP/zero-window retained: USB_TYPE[PD_PPS]
means source PPS supported in pinnedTCPM, NOT activePPS. ActualONLINE1/fixed9V/
1500mA, SM5714input1500, pack29.9C/Good, passivefault0/OFF/IBUS0/VBUS9.136V.
Firstfresh6PDO C1ring saved+partner sysfs agree: fixed5/9/12/15/20V and PPS5-11V
3A; actualRequest fixed9V1500, no APDO request. Correcthost ONLINE1 vs active2/3,
ignore onlygenericpower directory, preservecount/lifecycle/current/thermal gates.
31parser+18collector/syntax pass. Read273SOURCE_OBSERVER_CORRECTION; same-attach
source-completion30s supplementsmissingwindow, no reattach/physicalretry/device
software/PPS/pumpON/current/gate change. Unchanged272build/all1424 reused.


Test273 prepare-completion READY same846248af/exact263, DCCabsent,75%/4.108V/
32.9C Good/passivefault0/OFF/IBUS0/cache692ms; firstPC TCPM ring archived once.
Originalprepare host-only omittedDCC STOP preserved, no physical attempt yet.
Actual log review distinguishes pendingreset timer from executedreset;29parser+
16collector gates/syntax pass, historicalseals againstb7e27663/60feb5c5. Read273
PREPARATION_RESULTS/currentobserverseal. C1APDO stillUNKNOWN; owner cable-confirmed
source30s next, no flash/reboot/PPS/pumpON/current/software/gate change. Reuse
unchanged272 build/all1424, no build/full/CI rerun. ActiveStage3 NOT READY.


Test273 initialprepare STOP/zero samples retained: host CURRENT omitted @@dcc,
not evidence that DCC returned (exact263config/notes). No ring consumed/cable
request/charging window yet. Correct only read-only DCC field, fresh
prepare-completion namespace, originalobserver archived/seal againstb7e27663.
No device/software/gate change; affectedcollector16tests/syntax pass, reuse
unchangedparser25/272kernel/all1424. No physical retry/reflash/CI.


Test273 registers ONE owner-confirmed LenovoYG65G C1 attach/C2empty,30s ordinary
fixed-PD source-capability identification on unchanged263/846248af. Read273README
and registration; counted freshTCPM frame/currentpartner sysfs must agree,
missing/overflow/reset/mismatch UNKNOWN, not negativePPS proof or charging grant.
Initial5V/3A Rp budget is not measured draw; actual5V1800/9V1500 input and final
fixed contract independently capped. Source offers>9V are not selected voltage.
FirstPC ring read archived after push/before owner action, then onePC endpoint.
No flash/reboot/PPS/pumpON/current/protection/kernel/rootfs/USB change.20oldSMMU
startup suspects unchanged/unresolved, no globalwhitelist.40affected gates/syntax
pass; unchanged272 build/all1424 reused, no build/full/CI rerun. ActualC1 APDO
stillUNKNOWN; ActiveStage3 NOT READY. Owner cable confirmation required before
source window; no retry/latch clear. HostNCM not a device acceptance prerequisite.


Owner identifies LenovoYG65G C1<=65W, stockAndroid reportedly~45W (method unknown).
Read X710_PPS_SOURCE_PLAN: C1/C2empty is candidate for future ordinary fixed-PD
Source_Capabilities capture, not proof of PPS/mainline45W or current escalation.
Actual APDO/independent calibration/OCP/liveadapter remain unqualified. No cable
request/device command in this doc update. Installed263 fixed5V1800/9V1500mA;
Test272399eb497 offlinequalification reused, executed:false for new checks.

Test272 OFFLINE_INTERFACE_QUALIFIED at399eb497: sleepable kernel-only fresh
OFF-mode request, genuine conversion seq/stamp/delivery100ms validity, atomic
users/drain and PMepoch; same system_percpu_wq as existing monitor.28actualC
new/112affected/all1424 pass (1396retained); final passive Image/DTB/181modules,
W1/sparse/audit pass, exact263config/DTB,85containers/DCC/96protected/frozen intact.
Initial2c8c8b9a qualification superseded after queue-identity review; retained.
Read272 RESULTS/summary/seal and SM5440_FRESH_REQUEST. No device command/flash/
reboot/PPS/pumpON/current/DT/USB/safety change; installed263 untouched.
Actual fresh-API timing/current/calibration/OCP/liveadapter/APDO unqualified,
ActiveStage3 NOT READY. Future read-only consumer/physical plan not executed.
Results-only reuse final qualification; no build/full/CI rerun.

Test271 finalized DEVICE_PASSIVE_DIAGNOSIS_COMPLETED_WITH_STARTUP_CLASSIFICATION_GAP:
one unchanged263 normal reboot to846248af, separate sameboot30.158s/7samples,
Good/fault0/advancing cachedADC/OFF/IBUS0; ADB/Wi-Fi10.125.29.77/DCC normal.
Original runner STOP/zero-window and20 fsynr660021/S1CBNDX102 startupSMMU
suspects retained unresolved, globalparser unchanged; no original CLEAN claim.
No startupREVBLK innewboot/twofresh branch coverage. HostNCM nottested.
No flash/PPS/pumpON/current/protection/gate/software change. ActiveStage3 NOT
READY: SOC83 plus physical100ms/calibration/OCP/livePM/APDO proof remain.
Read271 RESULTS/summary/seal. Preserve267/270 failures, no automatic retry.
Results-only reuse8focused/263/269 qualification; no build/full/CI rerun.


Test271 separately registers ONE normal unchanged263 warm boot +30s passive
startup/freshcache diagnosis at currentgauge4.215V, under renewed owner physical
request. Read271README before reboot. DiagnosticSOC84 allowed ordinary OFF-mode
baseline boot, NEVER higher-power admission (unchangedSOC<80 still fails).
Original<4.3V/twofresh<=5s startup gate/snapshot/protection unchanged. Push before
reboot; no secondboot/retry/flash/latchclear/PPS/pumpON/currentchange.8focused
gates/syntax pass; exact263/269qualification reused, no build/full repeat.


Test270 high-power preflight NOT READY: same263/4bbd8221 ADB healthy, oldWi-Fi
10.168 timeout preserved; actual10.125.29.149 firstauth works. Battery84%/4.215V/
32.7C Good; SOC<80 fails, oldpassive0x80 and stale4.3215V snapshot persist.
No reboot/flash/PPS/pumpON/gate/current change in270; no Test269 live test. Read
270 RESULTS/seal. Owner renewed physical authorization may cover a separately
registered single baseline startup diagnostic, not activecharge admission or
retroactive267 pass. No build/full rerun for evidence-only work.


Owner now permits physical testing. Test270 registers one bounded read-only
high-power readiness capture on expected263/Wi-Fi; read270README. Actual failed/
stale monitor or missing liveadapter/freshADC/OCP qualification stops before
charging. No automatic flash/reboot/PPS/pumpON/current/gate/latch clear. Reuse
269 qualification, no build/full repeat. Preserve267STOP and cached provenance.


Test269 OFFLINE PPS retarget QUALIFIED at19991d6c: freshVBAT/source operating point,
OFF across Request, physical settle/current reprogram/ON and checked fallback;
no automatic current increase, <=1.8A/10.5V initial limits unchanged.55 realC +
all1396 pass (all1379 retained); one isolated policy Image/DTB/181module build,
W1/sparse/artifact audit pass. Config263 delta onlyX710_CHARGING_POLICY n->y,
DTB identical,85containers/DCC/96protected/frozenimages intact. Read269 RESULTS/
summary/seal and X710_PPS_RETARGET. No liveadapter/device command/flash/reboot/
PPS/pumpON/gate/charging current/thermal/USB change. Installed263/Test267STOP
unchanged; fullpack/freshADC/nonzero-current/OCP/livePM and actualAPDO supply
remain blockers, ActiveStage3 NOT READY. Results-only reuse qualification,
no build/full/CI rerun; future physical plan is not executed/authorized.


Owner requests higher-power porting. Test269 registers OFFLINE PPS operating-point
retarget core, see X710_PPS_RETARGET/269README. Recompute freshVBAT/source while
OFF, no automatic current increase; <=1.8A/10.5V initialcap unchanged. One final
isolated policy build/full qualification. No liveadapter/device command/flash/
reboot/PPS/pumpON/gate/current/DT/USB change. Test267 STOP/installed263 unchanged;
fullpack/freshADC/current/OCP/livePM blockers remain, ActiveStage3 NOT READY.


Test268 battery-only window COMPLETED150.378s/28samples on unchanged263/4bbd8221.
SOC99, gauge4.343–4.366V, discharge−1.320..−0.510A, pack29.0→27.8C; Wi-Fi healthy,
no new CPU/kernel fault/failedunit. USB unplugged intentionally. OldSM5440x80
stoppedcache unchanged/unqualified; Test267 stillSTOP, ActiveStage3 NOT READY.
Read268 RESULTS/summary/SHA256. No flash/reboot/PPS/pumpON/latchclear/gate/config
change; no rollback needed. Results-only reuse8focused/263qualification, no build/
full rerun. Next offline fullpack classifier/freshADC audit, no automatic retry.


Owner requests continued physical testing. Test268 registers battery-only150s
readiness on unchanged263/4bbd8221 via verifiedWiFi10.168.36.149, after owner
unplug confirmation. StillSOC100/4.394V/32.3C, oldpassive0x80 fault/cachestale.
No Test267 retry/SM5440 acceptance/latchclear/flash/reboot/PPS/pumpON/threshold
change. Read268README/registration; gauge onlyentryhint, not freshADC.8focused
gates+syntax pass, no build/full rerun. Push registration before cable action.


Test267 finalized STOP_PASSIVE_MONITOR_FAULT, zero30s window completed. Exact
263 restored/readback and Debian4bbd8221 config/notes/cmdline pass; ADB/NCM/WiFi
normal/noCode43/newCPUfault. Baseline also0x80 atVBAT4.3215V/OFF/IBUS0; passive
Unspecifiedfailure persists, batteryGood. This is not fixed by rollback or a
qualified Test266 physical pass. Read Test267 RESULTS/summary/seal. Preserve
original observer hostcmdline STOP; fullruntime actually equals263. Next offline
audit existingfullpack startupclassifier (VBAT<4.3V), no automatic retry/cutoff
relaxation/clear-latch/PPS/pumpON. Device263; all olderbackups retained. Results
reuse266 qualification/42focused checks; no build/full/CI repeat.


Test267 exact Test263 boot+181modules restored/readback; all5partitions match
accepted263. Candidate module directory preserved .gts9-test267-tested, older
backups intact; root unmounted/BCB clear. StillTWRP, next ordinary baseline
boot/recovery endpoint only, no repeat candidate/charging test. Monitor failure
and hostcmdline defect retained; no gates/PPS/pumpON/current/USB change.


Test267 candidate0fb695fd reached responsiveDebian/config/notes match. Physical
passive monitor STOP: retained0x80 at0.278016s, VBAT4.3055V outside unchanged
<4.3V startup classifier; pumpOFF/IBUS0, batteryGood/SOC99, no CPU/kernel fault.
Window not completed. Observer firsthostcmdline error preserved: runtime equals
accepted263, vendor-only input was wrong comparison. Read first-device-fault.
Restore exact263 boot/.gts9-test267-original via verifiedTWRP; no retry/gate
relaxation/PPS/pumpON. No claimed Test267 physical pass.


Test267 boot b9f296d8 +181paired modules installed/readback; other4partitions
unchanged, exact263 modules in .gts9-test267-original/older backups intact.
Root unmounted/BCB clear; candidate not yet booted. Next one ordinary PCUSB
boot/passive30s. Existing startupREVBLK classifier VBAT<4.3V stays; fullbattery
fault must stop, no whitelist/gate change. Read INSTALL_STATUS/install summary.


Owner now authorizes Test267 deployment/physical test of qualified Test266.
Read Test267 README/registration/PACKAGE first. Device arrives in verifiedTWRP;
five partitions/181modules match263; full battery100%/4.409V/25.2C. Install only
boot+181paired modules, fresh267 rollback slots; keep otherpartitions/backups.
One ordinary PCUSB boot/passive30s/full-battery bounded snapshot + rescue endpoint;
no9V power trial/PPS/pumpON/liveadapter/current/thermal/USB change. Device-normal
completion rule applies; unknown evidence incomplete, actualfault stops/rollback.
Reuse266 qualification, no kernel/full rerun. Push registration before install.


Test266 cached passive consumer implemented: coherent copieduV/uA/deciC plus
oldest acquisition-start BOOTTIME,100ms/stopped/fault/pending/mode/unbound gates;
clear output on failure. Registry->tryio lock, busyI2C refuses without wait,
unpublish before devres teardown; no pointer escape/I2C/on-demand conversion.
44 affected + finalfull1379 pass; final passive Image/DTB/modules build and
W1/sparse pass, unchanged object/knownVDSO warning. Config/DTB byte-identical263.
Initial build/full1378 retained, superseded after busy-lock review; not final
qualification. Final committed-source artifact audit6477a094 passed:181 paired files,
85 containers/DCC/96 protectedfiles and frozen artifacts intact. Read Test266
RESULTS/summary/seal. Results-only changes reuse this qualification, no
repeat build/full/CI. Installed263 untouched; no device command/flash/PPS/pumpON/current/protection/thermal/USB.
Read SM5440_CACHED_CONSUMER and Test266. ActiveStage3 NOT READY; stale reads
between1s polls are refused, not an active100ms sampler/calibration claim.

Test266 registers OFFLINE passive SM5440 coherent cached-consumer API;
read Test266 README/registration. Add actual acquisition-start BOOTTIME metadata,
max100ms refusal and short registry->io lock lifetime; no I2C on read/new worker/
converter/ON/PPS/protection/current change. Existing passive polling/property/
startup/PM behavior stays. Consumer may ESTALE between1s polls; no fresh-on-read
or ADC calibration claim. One passive build/full qualification after code;
config/DTB must equal263, protected/containers/DCC intact. Installed263 untouched;
no device command/physical test authorized. ActiveStage3 NOT READY.

Test265 OFFLINE PM CORE QUALIFIED at0da8e89a: Fedora-derived suspend latch/
revoke/checkOFF-fixed-measure-switching; resume never auto-arms.38 actualC tests
(10 new PM) + full1369 pass, all prior1351 IDs retained; one isolated policy
Image/DTB/181modules build, embedded config/notes/source/85containers/96protected
and W1/sparse pass (knownVDSO warning retained). Exact263 config delta only
X710_CHARGING_POLICY n->y; DTB identical. Read Test265 RESULTS/summary/seal and
X710_FEDORA_PM_PORT. No liveadapter/notifier/device command/flash/reboot/PPS/
pumpON/current/thermal/USB change. Installed263 accepted,260 rollback intact.
ActiveStage3 NOT READY: physical ADC/current/OCP/live PM supplier order remain.
Results-only commits reuse exact qualification; no repeat build/full/CI.

Test265 Fedora-derived unwired PM core implemented: suspend latch/revoke grant,
checked OFF/fixed/measure/switching exit; resume never auto-arms and refuses
fault/epoch/inhibit.38 actual-C tests (10 new PM) and full1369 pass. Isolated
policy-offline Image/DTB/modules build passes; exact config delta only
X710_CHARGING_POLICY n->y, DTB byte-identical263; W1/sparse pass (knownVDSO
warning only, unchanged object hash). Final committed-source artifact audit
pending; initial precommit-revision mismatch report retained as host attribution
setup, not build failure. No device/flash/PPS/pumpON/USB/current/thermal change.
Read docs/X710_FEDORA_PM_PORT.md. Installed263 stays; activeStage3 NOT READY.

Test265 registers OFFLINE Fedora-derived PM transitions in unwired C core;
read Test265 README/registration. Adopt drain/OFF/fixed-before-suspend order,
revoke arming/latch suspend, checked errors and no resume auto-arm. No live
adapter/notifier/hardware API/device command; installed Test263 untouched.
One isolated policy-offline build/full qualification after implementation;
expected config delta only X710_CHARGING_POLICY=y, identical DTB/protected
hardware/containers/DCC. ActiveStage3 NOT READY. No physical test authorized.

Test264 OFFLINE review/helper PASS:55 affected tests, zero failures/errors/skips;
new future completion helper uses fresh child directory, preserves parent raw/
STOP, tests actual Recorder overwrite guard. Read Test264 RESULTS/summary/seal.
Fedora reuse approved; implement its drain/OFF/fixed-before-PM semantics with
checked errors, not unchecked fallback. No device/kernel/config/DT/USB change;
no build/full rerun, reuse ea938b24. Installed Test263 remains device accepted.
ActiveStage3 NOT READY; next unwired PM core, no automatic physical test.

Test264 continues OFFLINE from655d39fa: protection/watchdog/PM audit against
Samsung X710 and Fedora ab123e7d, plus future isolated completion evidence helper.
Read docs/SM5440_ACTIVE_PROTECTION_PM_PLAN.md and Test264 README/sources.
Owner permits direct use/port of Fedora same-model logic: adopt its OFF-before-
refresh and drain/OFF/fixed-before-PM order, with checked errors/readback rather
than copying unchecked restore or introducing private frameworks. No device
command/flash/reboot/PPS/pumpON/current/protection/config/DT/USB change.
Installed Test263 device acceptance stays complete; Test260 rollback intact.
Source review confirms unsupported HW OCP and vendor unchecked mode/WDT writes;
activeStage3 remains NOT READY. Reuse ea938b24 kernel qualification for this
host/docs-only phase; affected helper tests only, no kernel/full repeat.

## Current state (2026-09-30)

Test263 attempt01 DEVICE ACCEPTANCE COMPLETED under updated owner criteria:
PC30.220s/PD30.420s/unplug15.370s and final separate read-onlyADB/NCM/SSH/
Wi-Fi/config/notes/DCC/health pass on33435db7, no Code43/newfault. Original
pc-endpoint host filename-collision STOP preserved; not original runnerCLEAN.
Owner says device normal completes test, so no rollback/reflash/reboot/retrial
for this host defect; device remains Test263 with Test260 rollback intact.
Read attempt01 RESULTS/summary/CURRENT_STATUS/device-completion/raw seal.
Future physical acceptance: judge the registered device behavior; host-only
logging/parser errors are recorded separately and do not by themselves require
rollback or repeat physical windows when device evidence confirms normal state.
If device state is unknown, report incomplete evidence rather than invent a
pass. Actual device safety/identity/transport fault still stops; no current/
PPS/pumpON expansion. Results executed:false; exact qualification reused.
ActiveStage3 NOT READY (ADC calibration/OCP/PM/livehandoff unresolved).

Test263 attempt01 STOP at final PCendpoint: host recorder kernel-json filename
collision between Wi-Fi capture and ADB admit, original error/evidence retained.
PriorPC30.220s/PD30.420s/unplug15.370s pass; final1sample/ADB identity/no newfault
captured but NCM/Windows/DCC-service gate NOT complete. No observed devicefault
claim or retry-to-clean. Read attempt01 RESULTS/CURRENT_STATUS. Registered exact
Test260 rollback pending; no PPS/pumpON/current/protection/thermal/USB change.
Results executed:false; unchanged source qualification reused. ActiveStage3
NOT READY. Fix evidence namespaces offline with combined-recorder test before
any separately registered hardware attempt.

Test263 attempt01 unplug endpoint PASS15.370s/4samples on33435db7: offline
USB/TCPM/passive, Discharging -1.720..-1.063A, pack29.4C, SM5440 OFF/IBUS0/
validfresh/unchangedprotection, no new fault. Read UNPLUG_RESULTS/raw seal.
Detached4.096V is raw-zero ADC floor, not attachedsource/calibration. PCrescue
endpoint pending owner connection; no transition/recoverylatency claim.
Results executed:false, reuse15 focused checks/ea938b24 qualification; no
kernel/full repeat. No PPS/pumpON/config/current/thermal/USB change. Whole
series incomplete; activeStage3 NOT READY.

Test263 attempt01 fixed9V snapshot PASS30.420s/7samples on33435db7: reported
VBUS9.076..9.109V, IBUS0/OFF, validfresh/rawdecode/protection unchanged,
pack29.0..29.1C, netbatterymean7.813216W (not USBinputpower). Read PD_RESULTS/
CURRENT_STATUS/raw seal. Unplug15s endpoint and PCrescue remain pending owner
confirmation; no human-wait timer or transition/latency claim. Endpoint host
helper15 focused checks pass, no kernel/full repeat. No PPS/pumpON/current/
protection/thermal/USB change; whole series NOT complete, activeStage3 NOT READY.


Test263 attempt01 passivePC snapshot PASS30.220s/7samples on33435db7: exact
config/notes/partitions/181 modules, valid cachedraw/fresh age128..948ms/OFF/
unchangedprotection, bounded startup0x80 retained, no newfault/Code43. Read
attempt01 PC_RESULTS/CURRENT_STATUS/raw seal. Wi-Fi now10.191.121.33; PD host
uses verifiedpostboot address, 13 focused checks pass, no network setting change.
Fixed9V30s and unplug/PC endpoints pending owner cable confirmation. No PPS/
pumpON/protection/current/thermal/USB change; whole series NOT complete.


Test263 attempt01 boot/vendor and181 paired modules installed/readback verified;
original Test260 modules saved in .gts9-test263-original, older backups intact.
Root unmounted and BCB cleared. Candidate has not yet booted/accepted. Next one
normal Debian boot, exact config/notes/journal attribution and passivePC30s
snapshot observation. No PPS/pumpON/protection/current/thermal/USB change.


Test263 attempt01 verified TWRP identity/root/five original partitions/current181
modules and staged files; no boot/vendor/module write yet. Save/push this evidence
before paired installation. Exact Test260 rollback and older backups remain.
No PPS/pumpON/current/protection/USB change. Read attempt01 registration.


Owner authorizes Test263 physical acceptance (continue hardware test). Read
Test263 attempt-01 README/PACKAGE/STAGED_FILES before action. Reuse ea938b24
qualified snapshot candidate; host gate12/module adapter5/syntax/bundle pass,
no kernel/full repeat. Current18bce160 Test260 identity/rescue/safety passes.
Only paired boot/vendor/modules deployment, passivePC30s and owner-confirmed
fixed9V30s telemetry comparison, then endpoints; exact Test260 rollback in
fresh263 slots. Push registration before recovery/write; preserve oldbackups.
No PPS/pumpON/protection/current/thermal/USB change. Stop first non-clean;
no absolute ADC calibration claim or activeStage3 readiness.


Test263 OFFLINE QUALIFIED at ea938b245bff3ae9e3c1828751ea149a90337992: optional
root-read-only cached SM5440 raw ADC/freshness/startup/error snapshot, zero I2C
on read and unchanged hardware/charging policy. Read Test263 RESULTS/summary/
SHA256 and docs/SM5440_ADC_SNAPSHOT.md. Final build/embedded-config/DT/protected/
181-file pairing audit, 34 affected +11 PM checks and one full1351 pass; prior
1290 IDs retained. W=1/actual compatible sparse pass, known VDSO warning retained.
Config/DTB identical acceptedTest260;85 containers/DCC/96 protectedfiles intact.
No device command/deployment/rootfs/USB/current/thermal/protection/PPS/pumpON.
Device remains Test260/Test262. Next passive ADC evidence acceptance requires
new authorization/registration; no automatic physical test. Independent ADC
calibration/OCP/PM/live handoff still unresolved; ActiveStage3 NOT READY.
Results-only commits reuse exact qualification, executed:false, no rebuild/CI.


Owner requests next porting step. Test263 registers OFFLINE passiveSM5440 cached
ADC/raw/freshness evidence interface; read docs/SM5440_ADC_SNAPSHOT.md first.
No new register operation, PPS/liveadapter/pumpON/config/DT/current/thermal/
USB change or device command/deployment. Current Test260/Test262 fixed path
remains installed. New263 output directories; qualify source once with affected
checks + one build/full run, reuse for result commits. ActiveStage3 NOT READY;
ADC calibration/protection/PM still require separately authorized acceptance.


Test262 finalized COMPLETED_WITH_EVIDENCE_GAP: fixed9V/1.5A300.011s/61samples
chargingPASS (netbatterymean7.827W, SOC54→56%, pack28.4–29.2C); post-owner
unplug15.001s offline/Discharging endpointPASS and PCADB/NCM/Wi-Fi/config/
notes/DCC/health endpointPASS on same18bce160. Original unplug observerSTOP
waiting300s is retained; no captured transition or precise recovery time claim,
not whole-seriesCLEAN. Read Test262 RESULTS/summary/SHA256. HostparserfirstSTOP
and pretestWindowschimes/rootcauseunknown retained. Device remains Test260
passive onPCUSB; no hardware/config/source change/reboot/flash/PPS/pumpON.
Reuse44 affected tests and Test260 pairing/build, results executed:false.
ActiveStage3 NOT READY; no automatic next physical test/current increase.


Test262 charging phasePASS retained. Original unplug observer STOP waiting300s
before owner removal; keep its rawSTOP and do not claim captured transition.
After owner's "已拔", separate read-only15.001s endpoint confirms offline/
Discharging/current-0.91..-1.129A/pack29.6C, same18bce160/no newfault. No new
charging trial. PC rescue attachment/check now pending owner confirmation; use
one bounded check afterward, not a human-wait timer. WholeTest262 has an evidence
gap and must not be labeled whollyCLEAN. No PPS/pumpON/config/reboot/flash.


Test262 attempt02 fixed9V/1.5A charging phase PASS300.011s/61samples on18bce160:
netbatterymean7.827W, SOC54→56%, pack28.4–29.2C, passiveSM5440 OFF/IBUS0,
no newkernel/CPU/failedunit/passivefault. Read CURRENT_STATUS/charging RESULTS.
Unplug15s verification and freshPCADB/NCM/Wi-Fi gates pending; wholeTest262
not yet complete. FirsthostparserSTOP and Windowschimeincident retained.
No actual inputpower/calibratedVBUS claim, no20min extension, no PPS/pumpON/
configuration/reboot/flash. Reuse44 affectedhosttests and Test260 pairing/build.


Test262 charging attempt01 STOP before charger prompt/window due host parser
empty@@failed EOF recognition, no physical charging fault or device change.
Retain charging/RESULTS/raw STOP/seal. EOF correction44 affected tests+syntax
pass, no kernel/full repeat. Fresh charging-attempt-02 uses same18bce160 boot,
unchanged300s5V/9V limits and first-fault stops. Push registration, start Wi-Fi
collector, wait ARMED, then request18W C2 connection. No PPS/pumpON/reboot.

Test262 charging has NOT started yet. Owner reports Windows connection sounds
resolved after manual PC-USB replug; fresh ADB/NCM/Wi-Fi/boot/battery/passive-OFF
gates pass. Read usb-chime-incident RESULTS/summary/raw seal. Root cause unknown;
no USB/kernel/service change or repeated-reconnect qualification. Keep incident
separate from charging results. Resume registered300s fixed-PD via Wi-Fi only
once collector is ARMED, then request the owner's18W source connection.

Owner authorizes ordinary charging test. Test262 registers300s SM5714 fixedPD
on currentTest260/18bce160, priorLenovoYG65G C2 18W source, WiFi10.191.121.145.
Read Test262 README before cable action. No PPS/pumpON/current/config change,
reflash/reboot or automatic20min extension. Keep SM5440 passive/OFF and first
fault stops; record battery netpower vs contract/ICL ceilings separately.
PassiveADC is uncalibrated; no inputpower/absolutevoltage safety-proof claim.
Qualify affected host tests only, reuse Test260 artifact/kernel qualification.

Test260 attempt02 PASS bounded passivePCUSB: boot18bce160,150.197s/30samples,
181 modulehashes/partitionreadbacks/config/notes match. First-only0x80 retained:
pending0.290025s/event0.290045s/confirmed2.609795s; two fresh safe conversions,
Good health/IBUS0 throughout, no newkernel/CPU/failedunit/Code43. ADB/NCM/WiFi
pass; dynamicAPIPA169.254.59.206 matchesWSLeth2, one-shotboundauth, no retries.
Read attempt02 RESULTS/summary/rawseal; historicalTest258/259 failures unchanged.
Device now stays on passedTest260 passive, exactTest255 original modules in
.gts9-test260-original plus rollback images retained, older tested backups intact.
No PPS/pumpON/protection/current/thermal/USB change. No automaticnextphysicaltest.
Passive pass is NOT ADC calibration/OCP/PM/direct readiness; ActiveStage3 NOT READY.

Test260 attempt02 installed sealed boot/vendor_boot and181 paired modules with
five-partition readback; exact Test255 original modules saved in fresh260slot.
TWRP root unmounted/BCB cleared, candidate not yet booted/accepted at this record.
Next one normal Debian boot, ADB-first admission and150s passivePCUSB observation;
stop first and restore Test255 if needed. No PPS/pumpON/protection/currentchange.

Test260 attempt01 STOP before deployment: unsupported journalctl --no-legend
auxiliary capture, raw firsterror retained; no recovery/devicewrites occurred.
Attempt02 corrects the host spelling before first physical test; inherited
preflight timestamps are explicit and sameboot/config/notes/battery/history
refresh passes. Same sealed artifacts/slots, affected6+actualarchive5 reused.
Read attempt02 README; original owner flash authorization still applies to
this predeployment correction, not to retry after a physical failure.

Owner now authorizes "开始刷机测试": Test260 attempt01 passive PCUSB150s only,
superseding prior no-flash scope for this attempt/rollback. Read its README.
Reuse source6fbafede sealed candidate/full1290, no rebuild/fullrepeat. ADB-first
hardware admission unchanged; explicit30s host-readiness adapter/source-bound
one-shotSSH, first unready delay retained as suspect. Keep first faults and exact
Test255 rollback/new260 module slots/older tested backups. No PPS/pumpON/current/
protection/thermal/USB change. Register/push before recovery/write; stop first.

Test261 source3ecf2093: explicit NCM host-readiness/source-bound SSH entry passes
one read-only check on acceptedTest255 bootcfb09d01. Windows NIC9 preferred
169.254.74.160/16 matches WSLeth2/directroute; noCode43, oneSSH0.83s, sameboot.
First metadata capture13.883s is not APIPA recovery time.109 affectedhosttests
and syntax pass, no routing/kernel/build changes or full/buildrepeat. Read
Test261 RESULTS/summary and docs/NCM_HOST_READINESS.md. HistoricalTest259 early
~9.3s SSHtimeout cause remains unknown; no startup/reconnect qualification.
No flash/reboot/configuration/device writes; Test260 stays offline/unaccepted.

Owner clarifies "先修 NCM，暂不刷机". Test261 registers host-only bounded NCM
readiness and one source-bound SSH connection on unchanged Test255. Read
docs/NCM_HOST_READINESS.md and Test261 README. No flash/reboot/rootfs/network/
USB/kernel/charging changes; Test260 remains offline. Preserve first unready
metadata/first SSH failure; no retry-to-clean. New helper is opt-in for fresh
registrations, never silently changes old runner deadlines. Historical Test259
timeout cause is not established. Qualify affected host tests only; no rebuild
or repeated full kernel regression for this host-only change.

Test260 offline correction source6fbafede now qualifies: startupREVBLK first-only
confirmation state; build/bundle/protected/config/DT/181module audit andfull1290
pass, all prior1270IDs retained. Driverfocused23 and W=1/sparse pass (one retained
VDSO warning). Host-only followup5ee5ce56 captures tablet-side state on every
transport failure; affected12 admission checks pass, no rebuild/fullrepeat.
Config/DTB identicalTest259;96 protectedfiles/85containers/DCC unchanged. Read
Test260 RESULTS/summary/PHYSICAL_PLAN. No physicalattempt/flash/reboot/settings
change: currentcfb09d01 remains acceptedTest255. Readonly transport works now,
historicalNCMtimeout rootcause unresolved. Startupfix has NOhardwareacceptance;
noautomaticphysicalretry, no0x82whitelist/PPS/pumpON/protection/currentchange.
ActiveStage3 NOT READY. Futurepassive test needs fresh registration and retained
startup-warning classification; qualified artifacts are reused, not rebuilt.


Owner requests continued repair. Test260 is OFFLINE: narrow first-only inactive
startupREVBLK confirmation (two new safe conversions within5s), retained raw
startup event, UNKNOWN/noADC publication while pending. Live/recurrentREVBLK,
allVBAT_OVP (including0x82), unsafeADC/I2C/deadline/protectionchange/PM still
stop. Read docs/SM5440_PASSIVE_STARTUP_STATE.md and Test260 registration.
ADB-first host admission saves hardware evidence before NCM; first transport
failure is retained, no retry-to-clean. Current read-only Windows/WSL snapshots
show mirroredAPIPA eth2 and working boundbanner/NCM on restoredcfb09d01;
historicalTest259 timeout cause remains unknown. No USB/config/rootfs change,
no physical retry/reboot/flash/PPS/pumpON authorized by this offline correction.
Qualify changed candidate once; preserve frozenTest258/259/Test255 artifacts.
ActiveStage3 remains NOT READY; passive hardware acceptance pending.


Test259 source74e75de6 fixes first-fault INT/STATUS/ADC/protection provenance;
passive build/bundle/protected/config/DT audit/full1270/related15/archive5 pass.
Attempt01 hosthelperpath STOP before permanentwrites retained. Attempt02 installed
and booted08af1c86, then firstNCM SSHtimeout + source0x80: INT3=0x62 vs live
STATUS3=0x20, modeOFF, ADC4.867V/3.938V/0A/28.5C. See RESULTS/FAILURE_ANALYSIS.
No150s pass, no retry-to-clean, no PPS/pumpON/protection/current change. This
cannot prove priorTest2580x82 benign. ExactTest255 fivepartitions/181modules
restored; finalbootcfb09d01 passes13 health/rescue gates, WiFi10.191.121.114;
Test258/Test259 testedmodules preserved. ActiveStage3 NOT READY. Next is offline
vendor startup-latch/state/protection audit and separateNCM timing diagnosis,
not faultmasking or another automaticphysicalattempt. Results commits reuse
unchanged qualifications (executed:false); no CI or rebuild/fullrerun.


Owner requests "修复并继续测试". Test259 fixes passive first-fault provenance
only, retaining all fault stops and fixed-PD behavior. Read its registration.
Qualify changed source once, seal/push before the authorized PC-USB passive
physical test; use distinct Test259 slots and preserve Test258 failed modules.
No PPS/pump ON/protection/current change. On first fault retain raw evidence,
stop and restore exact Test255. Do not mask0x82 to obtain a pass. Prior offline-
only next-step restriction is superseded for this bounded diagnostic test.


Test258 attempt02 physically installed/booted the qualified passive candidate:
paired boot/vendor_boot and181 modules passed readback, SM5440 revision2 probed
on0-0063, ADB/NCM/Wi-Fi/Sink-Device/no-Code43 gates passed. First source fault
at1.608590s is software bitmap0x82 (VBAT_OVP+REVBLK); first host sample30.07s
reports Unspecified failure with stale/unavailable ADC fields. STOP, no150s
pass and no retry. No PPS/pump ON/current increase. Exact Test255 rollback
boot/vendor/181 modules completed; all five partition readbacks match, candidate
modules retained at .gts9-test258-tested. Final bootf965e054 has12 health/identity/
rescue gates passed, Wi-Fi10.191.121.242, battery62%,29.2C,4018mV,Good.
Read attempt02 RESULTS/FAILURE_ANALYSIS/summary. Raw fault provenance is missing
(INT latches merged with STATUS); actual overvoltage is not established. Next
is offline first-fault raw-snapshot/vendor-state audit, not another physical
attempt/PPS activation. Active Stage3 remains NOT READY. Reused build/full1264
and5 focused archive checks; no repeated build/full run for result commits.

Owner now requests "继续实机测试": Test258 attempt02 registers the SAME passive
candidate with the release-root install helper. Read attempt02 README first.
Fresh runtime preflight on0456f423 finds ADB/NCM/Wi-Fi10.191.121.119 working;
old Wi-Fi failures are retained, cause/recovery timing unknown. Reuse f3a266b5
build/full1264 and a4437ece five actual-archive host tests, no rebuild/full rerun.
Push registration before recovery. TWRP verifies baseline partitions/modules
before installing paired boot/vendor_boot/modules;150s PC USB passive only.
No PPS/pump/current increase. Stop first, retain evidence and restore accepted
Test255 if needed. Earlier stopped attempt below is immutable, not continued.

Test258 physical deployment STOPPED before image writes/current-module rename:
the qualified module archive is release-root, while the historical staging
helper expected lib/modules. Keep the first failure, raw recovery and results.
Five partitions and181 original modules verified unchanged; failed extraction
removed, root unmounted/BCB cleared, ordinary Test255 returned on0456f423.
ADB/NCM remain working, no Code43/new kernel fault/failed unit; Wi-Fi SSH to
new DHCP10.191.121.119 failed initially and in one read-only diagnostic retry.
Do not call Test258 booted/passed; its150s candidate observation never started.
No candidate retry/PPS/pump. A release-root helper is prepared offline separately
with real-archive transaction tests; it has not been sent to the device.
Next deployment needs a fresh bounded registration and working rescue preflight,
using unchanged qualified artifacts without another kernel/full host run.

The owner requests reduced checking overhead. The change-scoped workflow below
supersedes historical requirements to rebuild/retest after every commit. Qualify
each candidate once; documentation/results commits do not invalidate unchanged
source or artifacts. Do not repeat a full build/regression because HEAD changed.
Test258 source f3a266b5 already passed its passive build, artifact/bundle audit
and all1264 host tests. Reuse those exact hashed artifacts for the authorized
test; retain essential device identity, rescue/rollback, battery safety and
write/readback gates. Active PPS/pump authorization remains unchanged.

The owner now explicitly requests "刷入测试吧". Test258 registers ONLY the
separate SM5440 passive profile: pumpOFF, no PPS/live transaction core, ordinary
PC USB150s. Read its README/preflight before any action. Preliminary current
boot c1716879 has accepted Test255 five-partition/config/notes/181-module and
rescue identities, but vendor lpcharge=1 differs from the accepted command line.
Read-only diagnosis passed every other gate. Registration permits ONE ordinary
baseline reboot after push to restore normal entry; no image/module repair or
candidate flash before a fresh normal-preflight passes. Keep all STOP evidence.
This authorization supersedes the earlier offline-only restriction for these
specific Test258 actions; active PPS/pump tests remain NOT READY/unapproved.

The owner has requested continued OFFLINE development without flashing.
Continuation starts at a3ddd0de on test. Test257 registers transaction source-
offer/freshness/monitor-deadline guards and a deeper software-OCP audit. Keep
Test256 evidence sealed. This does not authorize device commands, a live PPS
adapter, pump ON, new APDO, configuration/DT/current/float/thermal changes.
Read docs/SM5440_SOFTWARE_OCP_AUDIT.md and Test257 registration first.

Test257 source31ca86ca now has offline source-offer/freshness/monitor guards.
Full1253 host tests passed, with all1239 previous IDs retained and14 new.
Default fixed Image/DTB/config/notes/module archive are byte-identical to Test256;
isolated policy build retains the same config/DT gates and181 module-directory
files. No DTS/config/hardware-driver changes. The core remains unwired and
unarmed by default;500ms facts/100ms ADC-monitor refusal limits do NOT qualify
physical software OCP. Actual protection, ADC, sensors and live transaction/PM
adapter remain unresolved. Read Test257 RESULTS/summary before continuing.
No flash, tablet command or hardware acceptance occurred; active PPS NOT READY.

Test257 post-record build/config/DT/protected audit passed at260133f0. Its host
rerun exposed global sync waiting on WSL/Windows mounts; three interrupted runs
are preserved, not passed. Follow-up scopes ONLY temporary host boot-record/
misc.img fixture sync to real syncfs on that filesystem and adds30s waits;
device scripts unchanged. Focused66 and changed/full1255 passed with zero
failures/errors/skips; all1253 Test257 IDs retained,2 fixture checks added.
Read Test257 POST_RECORD_CHECKS.md and post-record evidence/summary. Original
Test257/Test256 seals and qualified outputs remain immutable. No device action.

The owner now authorizes **offline X710 vendor charging audit and staged
refactor/SM5440 development only**. Start HEAD is ebf4af1c, work branch test.
Read docs/X710_VENDOR_CHARGING_AUDIT.md, X710_CHARGING_ARCHITECTURE.md,
SM5440_REGISTER_AUDIT.md, SM5714_SM5440_HANDOFF.md and
X710_CHARGING_TEST_PLAN.md, plus Test256 registration. Samsung sources under
/home/ms/Samsung/kernel_platform are read-only evidence; Fedora snapshot is
ab123e7d. Preserve sealed Test255 and its installed fixed5/9V limits, float,
thermal, Test253 adbd/Test254 container gates and rollback pairs. No device
commands, deploy/flash/reboot/modules/rootfs changes, live PPS or pump activation.
Keep Stage3A/default fixed behavior separate from passive Stage3B/profile.
Direct activation remains blocked by actual ADC/OCP/sensor/transaction acceptance;
vendor aggregate protection init must not be copied blindly. Use the current
change-scoped validation rules below; push origin/test, no CI/main merge.
The earlier physical history below is retained, not new device authorization.

Test256 offline source revision61336aff is now qualified. Read its RESULTS.md,
BUILD_RESULTS.md, summary.json and validation evidence. All1239 host checks
passed with no failures/errors/skips (1200 retained +39 added). Default
fixed-refactor config adds only CHARGER_SM5440_DIRECT=n; DTB is byte-identical
to Test255. Separate passive/policy profiles enable only the pump monitor and
optional unused transaction core, with only charger@63 status changed. Each
candidate has181 paired module-directory files;96 protected files,8 Stage1
helpers,62 reference sources and frozen Stage2 artifacts are intact. W=1/sparse
reported no changed-driver diagnostics; dtbs_check retains the baseline unbound
PS5169 usb-role-switch type diagnostic, not a clean whole-board schema result.
No device commands or deployment occurred. Live PPS/pump-ON remains unavailable:
software OCP/protection, actual ADC/sensors and live transaction/PM adapter are
unaccepted. Active Stage3 candidate NOT READY. Next requires separately registered
passive probe/ADC acceptance, never automatic PPS or pump activation. The
stage2-fixed-pd-known-good tag preserves ebf4af1c; use the accepted artifact pair
for an authorized device rollback, not a rebuilt refactor image.

The owner has revised the Test255 workflow to connect the existing Lenovo
YG65G USB-C2 18W PD supply directly and inspect power/battery telemetry.
Attempt03 registers this bounded observation without an external VBUS meter or
separate5V-only supply. Read its README before continuing: measured battery net
power is VBAT*IBAT; TCPM voltage/current and switching input-current limits are
policy values, not actual charger input watts. No kernel/driver/DTS/rootfs or
charging-policy change, reboot, flash or Stage3 is authorized by this revision.
Registration b63fad60 and23 fresh Wi-Fi identity gates preceded attachment.
Attempt03 first300.011s fixed9V/1500mA battery telemetry passed:61 positive
current samples, mean battery net7.771W, SOC59->61%,28.7..29.7°C.
The full1500.060s charging window now passed:301 positive-current samples,
fixed9V/1500mA, mean battery net7.828W, SOC59->69%,28.7..31.5°C,
no detected new kernel fault/failed unit. Unplug150.005s passed; nativeADB/
NCM recovery<=14.056s with no failed initial command/new warning, followed
by156.412s PC USB stability, passed on the same boot/PID827. Fresh final22
identity gates, native binary-config transfer, PnP/banner/NCM/Wi-Fi and
all three181-file rollback directories/settings match. PC temperature
34.1..35.1°C(final35.2), input500mA; net battery discharge on PC is recorded
separately. Charger is disconnected, computer USB/Wi-Fi retained. Read
attempt03 RESULTS.md/summary.json. No reboot/flash/config/driver/rootfs
change or Stage3 occurred; no independent actual input watts/VBUS claim.
Final all1200 host checks passed in96.129s with zero failures/errors/skips;
all retained tests remain present, no CI. Per-stage/raw evidence is sealed.
The independent physical-VBUS gate remains unobserved, not passed. Earlier
sealed attempt01/02 results remain unchanged.

Latest installed Test255 Stage2 candidate boot is `d745248e…`, following the
owner's reported manual reboot after attempt01 battery testing. Attempt02
initial27/final26 identity/health gates and a fresh162.143-second PC USB window
passed: ADB binary-config transfer, NCM authenticated SSH/interface-bound
Windows banner, Wi-Fi, Sink/Device, no Code43/new kernel fault/failed unit.
Candidate boot/vendor_boot/config/notes/exact181 modules and all three181-file
Test254/Test252/Test249 rollback directories plus Test253 settings are intact.
No reboot or software/hardware change was commanded in attempt02. Read its
`RESULTS.md`/`summary.json` under Test255 before continuing. A fresh changed
host invocation executed all1183 tests with zero failures/errors/skips in98.483s;
the earlier WSL sync interruption remains preserved as a separate failed run.
Attempt01's155.473-second battery-only pass is retained; its following same-boot
PC reconnect was interrupted by the manual reboot and is not passed. Fixed-PD
5V-only/9V charging and charger-to-PC acceptance remain unexecuted: no independent
VBUS meter/5V-only source is available. No PD charger was connected by this
attempt, no full Stage2 acceptance or Stage3 work is claimed.

### Earlier first-boot physical checkpoint (superseded by attempt02)

Test255 attempt01 Stage2 candidate has now been installed and booted under the
owner's physical-test authorization. TWRP readback and Debian first-boot
identity passed: boot26ef6bd1…, vendor_boot d80d03cd…, config cd7ec9cb…,
notes fb3d2496…, exact181 modules; init_boot/dtbo/vbmeta stayed Test254.
The new boot a5b8b87f… reports Type-C Sink/Device; ADB, NCM and Wi-Fi work,
Windows has no Code43, and first-boot plus a 991-second same-boot kernel scan
found no new fault. Test254 boot/vendor_boot images and 181 modules are retained
as a distinct rollback pair beside the Test252/Test249 backups. See
`reference/boot-tests/test-255-sm5714-fixed-pd/attempt-01/CURRENT_STATUS.md`
and its raw preflight/recovery/install/boot/postboot/holding-status evidence.
The first 300-second USB-connected waiting monitor did not count as battery
testing. After the owner disconnected the PC cable, a fresh 155.473-second
battery-only window passed on the same boot, with USB offline, Discharging,
negative current, Good health, stable temperature and no new kernel fault.
Await manual PC USB reconnect, then verify ADB/NCM/SSH for 150 seconds on
the same boot. The Lenovo 18W PD charger
has not been connected; no independent VBUS meter or 5V-only source is
available, so fixed 5V/9V acceptance remains pending. Do not start Stage3.

### Earlier offline-candidate record (before physical authorization)

Test255 was an **offline Stage2 fixed-PD candidate**, prepared under the
owner's explicit no-device-command/no-flash instruction. Installed state stays
Test254 with Test252 Stage1 and Test253 userspace adbd repair; no live identity
query, reboot, partition/module/rootfs change or Stage3 occurred. Starting local
and origin/test HEAD was26d62393; plan c799fadf preceded implementation814788a3.
Read docs/SM5714_STAGE2_PD_PLAN.md and Test255 README/SOURCE_AUDIT/BUILD_RESULTS/
RESULTS/ARTIFACTS/validation/summary.json before proposing hardware work.

Candidate uses stock Linux7.2-rc3 TCPM and a built-in SM5714 TCPC transport at
hub9/0x33/400kHz/GPIO133-low. Sink+Device only, fixed5V1800/9V1500mA; actual9V
switching input<=1500mA(13.5W), positive grant honored. Q4 charge-off plus100mA
hardware input minimum covers zero/subminimum budget, pending TCPC probe/fault;
it is not complete VBUS/VSYS isolation. Original4440mV float, pack thermistor,
2100mA pack cap, thermal helpers and suspend stop-charge remain. No Source/OTG,
role-swap/dock/DP/PS5169/SBU/PPS/SM5440 driver or register operation was added.
Inherited SM5440 DT child is disabled/unlinked; hub3/GPI remains unchanged.
DWC3 stays peripheral with retained USB2 graph; delete its inherited inactive
usb-role-switch flag so TCPM does not defer waiting for an absent provider.
TCPM/DWC3/gadget/adbd/rootfs and OPP sources are unchanged.

Exact Test254 resolved-config delta is only TYPEC_SM5714 absent->y; config
cd7ec9cb…, notes fb3d2496…, DCC off and all85 container gates preserved.
Final Image f1ce90a4…, DTB c6148471…, archive28e33cda… and181 paired files/
167 ko passed embedded-config/source/DTB/depmod/archive checks. Separate outputs
out/kernel-sm5714-stage2 and out/boot-bundle-sm5714-stage2 preserve rollback.
Boot26ef6bd1… and vendor_boot d80d03cd… both carry the new DTB; exact old cmdline,
bootconfig/ramdisk and init_boot/dtbo are retained. Generated vbmeta is not the
accepted installed vbmeta: never deploy generated init_boot/dtbo/vbmeta.
Changed/wrapper/full each execute1183 tests with zero failures/errors/skips;
35 new,1148 retained. An earlier PTY partial-read fixture failure was separately
fixed in a718bd89 without weakening assertions; raw failed evidence is retained.
No GitHub Actions or CI. No hardware acceptance/safety guarantee is implied.

At that time, future Test255 required fresh authorization plus pushed rescue registration,
retained Test254 boot+vendor_boot+181 modules alongside Test252/Test249 pairs,
and an independent measured-VBUS gate (TCPM voltage_now is contract state).
Use registered battery150s/PC Sink-UFP/5V/proven9V/5min-then20min/unplug150s/
same-boot charger-to-PC bounded reconnect gates; stop first anomaly. No device
work is authorized by this offline result. Water detection, USB3 orientation,
suspend PD continuity and BC1.2/PD timing remain unaccepted; no Stage3.
Test254's independent Docker I/O/registry/GUdev/network/rootless/cable limits
remain as recorded. Preserve every old sealed/stopped result and the bounded
Test247/Test249 DCC conclusion.

### Previously recorded installed-state history (preserved)

The owner subsequently authorized **“刷入测试”**. Test254 attempt01 stopped
before any device write on initial Windows Code43/absent rescue transports;
its result/raw evidence remain immutable. Owner confirmed manual reboot and
computer USB attachment. Attempt02 fresh full Test252 identity/rescue passed,
and registration369ebe3a was pushed before maintenance. TWRP installed only
candidate boot ea73e65836ab316af658ed53273be0ec6351b335750978095e509054164509f7
and181 paired modules, retaining exact Test252 modules at .gts9-test254-original
and the older Test249 backup. Temporary label-validated misc BCB was cleared.
TWRP blkid returned no UUID; raw ext4 superblock verified the original microSD
before any module/boot write. Four other partitions are unchanged/readback verified.
Current boot6c3dde80334e495589169a1e576c8024 has exact Test254 config c80d3c66…
and notes7bbb0dc3…, DCC absent, protected Test253/USB/SSH unchanged, no failed
unit/kernel fault and ADB/source-bound NCM/Wi-Fi working (Wi-Fi10.191.121.241).
Boot151.6s observation, USER_NS/mqueue/cgroup2 and unchanged PrivateUsers=yes
UPower activation/battery enumeration now pass. Two GUdev assertions remain
independently recorded. Debian Docker26.1.5/CLI/containerd/runc/iptables-nft/
uidmap/ipvsadm installed (11 new/no upgrades), daemon cgroup2/overlay2/seccomp
passes. Attempt02 stopped on first direct Docker Hub pull timeout; its raw
incident/full post-stop/seal remain preserved, no container/cable test run there.
Host official registry access works; separately registered attempt03 verified
four official ARM64 image source/config/layer/archive identities and loaded them
on the same boot. Actual hello-world/trixie/mqueue plus CPU/memory/pids/cpuset
controls pass. Attempt03 stopped at first ineffective I/O limit (io.max empty).
Fake-endpoint analysis proves the installed CLI sends empty throttle arrays
before contacting the real daemon; internal client cause not established.
BLK_DEV_THROTTLING=y/io controller/file exist: this is not proof of missing kernel
throttling. No Docker/client/kernel/service workaround applied. Test container
cleaned. DNS/outbound/NAT/publishing/optional networks/IPVS and physical cable
regression were not executed after the stop; do not claim full Docker acceptance.
UPower's two GUdev assertions and direct registry access remain unresolved;
rootless runtime/delegation unaccepted. Full final same-boot five partitions/
181 current+181 Test252+181 Test249/DCC/protected settings/three transports/kernel
and healthy battery pass (1430.74s,71%,29.0°C,4.062V,SDP500mA). No Stage2/3 or
extra charging test. Candidate remains installed, exact rollback retained, no
rollback executed. Read Test254 RESULTS/PHYSICAL_SUMMARY/CURRENT_STATUS and
attempt03 RESULTS before a separately scoped client-input investigation.
Preserve all old stopped results and original sealed offline documents.

The owner authorized offline UPower/OCI kernel configuration enablement only.
Test254 is a separate **unflashed candidate and future acceptance plan** under
`reference/boot-tests/test-254-debian-container-kernel/`; read its BUILD_RESULTS
and README before any later action. USER_NS resolves the missing kernel
prerequisite for shipped UPower PrivateUsers=yes, without a service workaround.
The container gate runs after olddefconfig. Preserve Linux7.2-rc3, DCC off,
SM5714/ADC5 Gen3 and all hardware/adbd/rootfs settings. Build outputs are
isolated in out/kernel-container-candidate so Test252/rollback artifacts remain
intact. Final offline kernel+modules and85 prerequisite gates pass; exact config
delta96 entries has zero unexpected changes (39 explicit+6 dependency enables).
DTB is byte-identical; all181 paired module archive files are verified. Required
wrapper/changed/full each execute1148 retained tests with zero failures/errors/
skips; new24 config checks pass. Host no-argument sync is qualified by real
syncfs on repo ext4 and /tmp tmpfs after an unrelated WSL global-sync block;
original incomplete runs are preserved, no helper/test/selector changed.
This task does not authorize deployment, device commands, hardware
acceptance or Stage2/3. Installed state and the unresolved installed UPower
issue remain as recorded below until a separately authorized physical test.

Current device is the authorized **Test252 Stage1 candidate**, not the exact
accepted Test249 production image. Battery-only/ordinary charge/plug-out windows
passed, but the attempt stopped on USB ADB offline after computer reconnect.
NCM and Wi-Fi SSH work; candidate identities/181 files and181 rollback files
remain verified. Stage1 full acceptance is incomplete; Stage2/3 have not started.
Read `reference/boot-tests/test-252-sm5714-stage1/RESULTS.md` before hardware work.
The historical accepted production baseline remains Test249 below.

The owner requested "先解决adb问题" then "继续修复adb吧". Test253 uses a
separate optional Debian34.0.5-12 userspace daemon at
/usr/local/libexec/gts9-adbd-reconnect, selected by gts9-adbd-run. It repairs
glibc worker-completion and retained-ep0/BIND handling, preserving packaged
adbd, restart guard/holder and NCM/SSH/kernel/charge settings. Initial preflight
stopped on UPower217/USER: shipped PrivateUsers=yes with USER_NS disabled.
The owner adopted an exact hash-pinned classification; that independent UPower
issue remains unresolved. Source/build and1088 host checks pass.

Attempt02 installed the fixed daemon/launcher/ExecStart and issued one normal
boot,461c1408e42643afae5b48162771d077, PID834. Exact Test252 config/notes/five
partitions/181 paired/181 original files and DCC/runtime profile still match.
Native shell and152.945s responsive observation passed. Connected Windows
`adb reconnect` then removed the host transport and native recovery could not
be established; attempt02 stopped before file transfer/physical cycles.
NCM/Wi-Fi SSH, device worker/monitor and PnP remain normal, no Code43/CPU fault.
The daemon is installed but reconnect acceptance is incomplete. No extra
reboot/reset/device-service restart occurred. Current Wi-Fi address is
10.191.121.29 (DHCP changed from195). Read attempt02 RESULTS/summary/evidence.

Attempt03 independently reopened the same37.0.1/LIBADBUSB Windows ADB server
once; native USB shell and1MiB byte/hash roundtrip now pass, with same boot/
PID834/hash and uninterrupted NCM SSH. The device was not rebooted or reset,
and no device service/config changed. Current native ADB works. The owner performed physical cycle01; native ADB recovered on the same
boot/PID/hash, but the sampler wrongly required UDC to stop showing configured
while USB supply was offline. Recovery<=60s/150s elapsed evidence was not
collected, so attempt03 is stopped with one cycle performed and zero accepted.
Full post-stop five-partition/config/notes/181+181/DCC/protected-settings and
ADB/NCM/Wi-Fi checks pass with no Code43/failed unit/kernel fault. A new
pre-enable FunctionFS DISABLE warning was recorded before ENABLE/new worker;
review source before future classification. No further cable cycle/reboot/reset
was made. Read attempt03 RESULTS/review; keep all old outcomes/seals intact.
`scripts/gts9-adb-host-rescan.sh` is the verified host recovery for the observed
missing table entry; raw `adb reconnect`37.0.1 remains an unresolved separate
limitation. Do not switch backend, modify production or start Stage2/3.

Attempt04 was explicitly adopted (reply: "使用新方案") and completed3/3
bounded physical cable-recovery cycles on the same boot461c.../PID834/hash.
Native+NCM recovery upper bounds14.100/15.346/15.060s, followed by real ADB/
NCM/Wi-Fi responsive windows155.487/155.466/151.345s. Each cycle's first NCM
8s timeout recovered inside60s and is retained; cycle02 also had first native
not-found before enumeration. This is accepted bounded recovery with observed
transients, not three transient-free Test250 CLEAN rounds. Two exact new
pre-enable DISABLE W events satisfied the adopted contextual/source/count/5s+1s
bounds; cycle03 had none. No other new daemon fault or CPU/kernel signature,
extra boot, Code43 or failed unit was detected.
Full final five-partition/config/notes/181 candidate+181 original/DCC/daemon/
protected-settings/kernel/three-channel acceptance passes; Windows37.0.1/
LIBADBUSB status is unchanged. The single final full check also serves cycle03's
post-gate. No software/backend/driver change, device or host-server restart,
reset/flash/reboot occurred in this attempt. Host implementation validation
1124 all+33 focused, adoption33 and final87 archive tests pass.
Read attempt04 RESULTS/summary/seals and Test253 CURRENT_STATUS.md. Physical
USB ADB reconnect is now verified within these windows; raw connected Windows
`adb reconnect` remains unaccepted with a separately verified host rescan
workaround. Preserve all earlier stopped attempts/seals. Current Test252 Stage1
kernel remains installed, its original attempt still stopped/unaccepted; do
not retroactively pass/promote it or begin Stage2/3/extra charging tests. Future
hardware work needs its own authorized registration and fresh preflight.


The production DCC-path repair is deployed and accepted on the SM-X710. The
pinned Linux 7.2-rc3 production build has `CONFIG_HVC_DCC=n`, matching boot and
vendor_boot images, and all 181 matching module files. Test249 verified the
first boot from TWRP for 158.22 s and one ordinary warm boot for 120.09 s; a
later same-boot check verified all five partition hashes, the 181 modules and
no new kernel fault. `/dev/hvc0` and `serial-getty@hvc0` are absent. Temporary
pseudo-NMI, CSD, last-activity, ECC and BBM diagnostics were removed from the
production build. There is no pending test249 flash or diagnostic rollback.
See `reference/boot-tests/test-249-no-dcc-production/RESULTS.md` and
`BUILD_RESULTS.md` for exact identities, hashes and validation limits.

Test247 captured a natural CPU4 stall in `hvc_dcc0_put_chars`: the DCC TX-busy
poll was unbounded while `hvc_write` held an IRQ-saving spinlock. Test248
validated the DCC-disabled diagnostic candidate, and test249 validated the
production transition on two boot paths. This supports repair of that concrete
DCC failure path; it does not prove that every earlier CPU stall shared the
same cause or rule out future stalls. Keep the accepted production images and
modules paired. Preserve the original230 and passing248 rollback pairs until a
separate, verified retention decision. A recurrence needs fresh boot-attributed
evidence before a new causal claim. See
`reference/boot-tests/test-247-early-csd-pnmi/RESULTS.md`,
`reference/boot-tests/test-248-no-dcc/RESULTS.md` and the test249 result above.

Native USB ADB and NCM/SSH are present in the production profile. A prior
Windows Code43 descriptor failure and a separate transient warm-boot NCM TCP
failure remain unresolved; test249 records both without attributing a cause.
The Debian login-screen `aux_bridge` deferred probe is a separate missing
PS5169/DisplayPort bridge-provider issue, not evidence of the DCC CPU fault.
See `reference/boot-tests/test-249-no-dcc-production/usb-incident/RESULTS.md`
and `docs/AUX_BRIDGE_LOGIN_MESSAGE.md` before changing USB or display wiring.

Historical D-drive test files live in ignored
`.work/d-drive-test-archive/2026-09-28/`, with tracked hashes in
`reference/d-drive-test-archive-20260928/SHA256SUMS`. Windows retains only the
rescue/rollback artifacts below `D:\android\gts9-active\`;
`gts9-stock/`, `gts9-test230/`, `gts9-test248/` and `gts9-test249/` are beneath
it. The owner subsequently explicitly requested that ADB tools remain directly
below `D:\android\platform-tools\` (2026-09-28). Current scripts therefore
use `/mnt/d/android/platform-tools/adb.exe`; this overrides the earlier tools
location under gts9-active without relocating test/rollback artifacts. Old absolute
paths in immutable test records describe where files were at test time. See
`reference/d-drive-test-archive-20260928/README.md`.

The test249 registration README and earlier dated reviews are historical plans;
its `RESULTS.md` is the final device-state record. Keep new physical tests
bounded, attributable and separately logged. Use the changed-file host test
selection for local iteration and the full retained suite when changing test
routing or reviewing a final candidate; see `docs/HOST_TEST_WORKFLOW.md`.

Test250 registered 20 unchanged-production warm reboots but stopped during
read-only preflight, before issuing any reboot (0/20 rounds). Test249 config,
notes, five partitions and all 181 modules still match and DCC remains absent.
The conservative parser flagged early warning/SMMU parameter variants; the
same SMMU fault class already exists in both accepted Test249 production boots,
so this is not proof of a new CPU stall. Supplemental same-boot transport
capture independently found two Windows NCM TCP timeouts followed by automatic
recovery, with ADB and authenticated SSH available and no Code43. Do not treat
the current boot as a clean Test250 round or retry automatically. Keep production
unchanged and review `reference/boot-tests/test-250-production-warm-reboot/RESULTS.md`
and its raw evidence before another hardware test. Test251 was not created.

The owner subsequently explicitly requested physical testing again. Test250
attempt 02 is separately registered in
`reference/boot-tests/test-250-production-warm-reboot/attempt-02/README.md`.
Use `--attempt 2` to preserve the stopped original records. Its host-only
parser recognizes tightly bounded startup classes from both manifest-verified
Test249 accepted production captures; it does not change the device or accept
USB transients as clean. The same 20-round/150-second, exact-production and
stop-on-first-non-clean requirements apply. Check attempt-02 results before
any further test; an explicit restart request is not permission to ignore a
new non-clean condition.

Attempt 02 subsequently passed full unchanged-production preflight and issued
one ordinary warm reboot, from `b08bbc9b-3bbf-417e-9935-619fcc5d7222` to
`188fd5c9-14ca-4818-9ded-e96669a9c836`. Round 01 stopped as suspect at the
20.11 s observation poll because ten early SMMU IOVAs exceeded its registered
range; no second reboot was issued and no 150 s window completed. Captured
journals show no CPU-stall/panic signature. Full post-stop read-only identity
still matches Test249, with DCC absent and no failed unit; an independent
same-boot NCM TCP transient recovered on its third attempt. Do not call this
round clean or broaden the gate after the stop. See attempt-02 `RESULTS.md`
and `summary.json` before further hardware work. Production remains unchanged.

The owner then explicitly requested completion of the full regression.
Test250 attempt 03 is separately registered under its `attempt-03/README.md`.
Read-only post-attempt02 analysis proves the production splash carveout is
43 MiB (`0xb8000000`–`0xbab00000`), larger than attempt 02's sampled 2 MiB gate;
attempt 03 derives the bound from the hash-verified accepted Test249 DTB and
checks the live property without changing it. It also records source-bound
Windows NCM socket endpoints; earlier TCP timeout causes remain unproven.
Only use `--attempt 3` after its pushed registration and accepted preflight.
All original 20/150-second exact-production and first-non-clean stop conditions
remain in force. Prior stopped attempts remain stopped, not clean or resumed.

Attempt 03 passed pushed exact-production preflight and issued one ordinary
warm reboot from `188fd5c9-14ca-4818-9ded-e96669a9c836` to
`830da717-5e6d-40be-8390-7398b55ff2e2`. It stopped as suspect at the 21.30 s
health poll on `Bluetooth: hci0: unexpected event for opcode 0xfc48`; no second
reboot was issued and no 150 s registered window completed. Exact Test249
config/notes/five partitions/all 181 modules and DCC absence remain verified.
ADB, source-bound NCM and authenticated SSH passed post-stop; Bluetooth setup
completed and the same boot remained responsive. No CPU-stall/panic signature
was detected. The HCI event mismatch remains unclassified, despite similar
historical Test241/Test247 logs; do not silently exempt it or call the round
clean. Keep the series stopped and production unchanged, read attempt-03
`RESULTS.md` and `round-01/offline-analysis/`, and do not create Test251.

A subsequent read-only source review identified `0xfc48` as the QCA UART
baudrate command encoded as `0x48, 0xFC`. A primary Qualcomm patch discussion
covers the same WCN6855 response-handling issue; this boot completed UART setup
0.808107 s after its event. This improves the explanation but does not prove
packet ordering or amend the stopped verdict. See Test250
`post-attempt03-analysis/README.md` for source evidence and an unapproved,
precisely bounded host-only classification proposal. Keep physical testing
stopped until the owner explicitly resolves that classification; production
and the current runner stay unchanged.

The owner subsequently explicitly adopted the bounded QCA classification
proposal (reply: "采用"). Test250 attempt 04 is a fresh registration under
`attempt-04/README.md` and `policy.json`, using `--attempt 4`. Its host parser
counts only the one exact early hci0/0xfc48 priority-3 event with WCN6855 setup
completed within 5 s, plus same-boot powered-controller/active-unit health.
The full 20-round/150-second Test249 identity, attribution, CPU/USB/evidence and
first-non-clean gates remain. Push registration/tests, then accepted full
preflight, before reboot. Previous attempts remain stopped and sealed; their
old plans do not authorize resumption. Production is not modified. Check
attempt-04 RESULTS/summary if present before starting any work on the device.

Attempt 04 subsequently passed full read-only preflight on boot
`830da717-5e6d-40be-8390-7398b55ff2e2`: exact Test249 config/notes, five partition
hashes, all 181 module hashes, DCC and backup absence, unchanged live splash
property, no failed unit and no CPU signature. Bluetooth is healthy and the
single early QCA event satisfies the owner-approved bounds. ADB and bound
NCM/authenticated SSH passed on their first attempts with no Code43. See its
`preflight/summary.json`; commit/push this accepted evidence before `run --attempt 4`.

Attempt 04 then issued five ordinary warm reboots. Rounds 01–04 were clean
through 153.71, 153.98, 154.04 and 153.51 s. Round 05, new boot
`457ecc1a-5d90-4d6f-8c5f-ad67e069bef3`, stopped as suspect at the 21.37 s poll
because two exact early `hci0/0xfc48` messages exceeded the approved maximum
of one per boot. Each belonged to a separate completed WCN6855 setup cycle;
this does not exempt the repeated count or prove a CPU fault. No sixth reboot
or final 20-round acceptance occurred. Full post-stop read-only config/notes,
five partitions and 181 modules still match Test249, DCC remains absent, and
Bluetooth/ADB/bound NCM/authenticated SSH are healthy. No CPU-stall/panic
signature was detected in the captured journals. See attempt-04 `RESULTS.md`,
`summary.json`, `EVIDENCE_AUDIT.json` and `round-05/post-stop/`. Keep the series
stopped and production unchanged; the 20-round goal is incomplete. Do not
silently broaden the QCA count, resume/reclassify this attempt or create Test251.
Further hardware work requires the owner to resolve this new non-clean bound.
Its post-stop `setup-cycle-review.json` compares eight raw journals and the
system timeline; `classification-proposal.json` proposes at most two events,
one per distinct completed cycle, at most three early cycles. That proposal
is unapproved and unimplemented; it does not authorize another reboot.

The owner subsequently explicitly adopted that bounded cycle proposal and
requested a fresh 20-round registration. Test250 attempt 05 lives under
`attempt-05/README.md` and `policy.json`; use only `--attempt 5` for this fresh
series. Its host-only rule permits at most two exact early priority-3 hci0
events, one per distinct completed WCN6855 cycle, at most three cycles, all
setup/event/completion times within 20 s and each event completed within 5 s.
Same-boot powered-controller and active-unit checks plus all original Test249
identity, CPU/USB/evidence/20-round/150-second/first-non-clean gates remain.
Earlier stopped attempts and seals remain unchanged. Push passing tests and
registration, then full accepted read-only preflight, before any reboot.
Production remains untouched; check attempt-05 results before further work.

Attempt 05 passed full read-only preflight on the still-current
`457ecc1a-5d90-4d6f-8c5f-ad67e069bef3` boot: exact Test249 config/notes, all five
partition hashes and 181 module hashes, DCC/backup absence, unchanged live
splash and runtime profile. The two earlier QCA events belong to separate
completed cycles and satisfy this newly approved policy; attempt 04's verdict
remains suspect. Bluetooth is powered with both units active, no failed unit or
CPU signature; ADB, bound NCM and authenticated SSH passed immediately, without
Code43. Push its sealed accepted preflight before `run --attempt 5`.

Attempt 05 issued twelve ordinary warm reboots and recorded twelve CLEAN
new boots, each observed beyond 150 s with exact attribution and no detected
CPU fault. Round 13 stopped during source preflight before any reboot: the
first Windows source-bound NCM SSH-banner PowerShell command timed out at its
20 s host deadline and the runner ended before bounded retries. Later
read-only probes on the same boot succeeded, but cannot classify the first
timeout's internal stage or make the source gate clean. Full post-stop
Test249 production identity (five partitions, 181 modules, config/notes,
DCC absence) still matches, and no CPU-stall/panic signature was detected.
See attempt-05 `RESULTS.md`, `summary.json`, `EVIDENCE_AUDIT.json` and
`round-13/post-stop/`. No thirteenth reboot, final 20-round acceptance or
Test251 occurred. The Test250 goal remains incomplete; keep this attempt
stopped and production unchanged. Any further physical series requires a
fresh registration and owner decision about this host probe timeout.
The post-attempt05 read-only review compares 29 successful host probes
(2.104–2.520 s, median 2.179 s) with the 20.025 s timeout and records an
unapproved attempt-06 proposal in `post-attempt05-analysis/README.md`.
It would add stage timestamps and allow 30 s for the outer Windows process
while keeping the 5 s TCP-connect/banner-read deadlines and every other
stop gate. It has not changed the runner or authorized a new hardware test.

The owner then explicitly changed the future Test250 completion criterion to
continue from round 13 and count the bounded warm-reboot series complete if
the prior CPU hang does not recur. A separately registered CPU-focused
continuation under `continuation-cpu-13-20/` kept attempt 05's original
stopped verdict intact. Eight more ordinary Test249-production warm reboots,
rounds 13–20, were uniquely attributed and each observed to at least 150 s;
no CPU-stall/panic signature was detected. Together with attempt 05's twelve
strictly CLEAN rounds, this completes **20 attributed CPU-focused warm-reboot
observations**, not 20 CLEAN rounds under the superseded strict transport gate.
Full final five-partition/181-module/config/notes/DCC and transport acceptance
passed; offline evidence replay passed. See continuation `RESULTS.md`,
`summary.json` and `EVIDENCE_AUDIT.json`. Production remained unchanged.
The earlier Windows probe timeout is unresolved. No Test251 was created or
run; cold/battery-only/Type-C power paths remain untested.

Stage0 X710 battery/charging audit is recorded in
`docs/X710_BATTERY_CHARGING_PORT_PLAN.md`. Stage1 is a **host-built, unflashed
SM5714 candidate**, independently registered under
`reference/boot-tests/test-252-sm5714-stage1/`. It adds the battery/ordinary
switching-charger driver and mandatory PMK8550 ADC5 Gen3 pack-thermistor
provider; the exact resolved delta is BATTERY_SM5714 absent -> y and
QCOM_SPMI_ADC5_GEN3 n -> y. The DTB, DCC-off CPU profile, cmdline, rootfs and
USB gadget remain unchanged. Source comparison is pinned to the same-model
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`; 8400mAh is typical capacity,
8160mAh is rated minimum and remains the design metadata. Read its
BUILD_RESULTS/SAFETY_REVIEW/ARTIFACTS before later deployment. No candidate
boot/probe/charge or new physical acceptance is claimed. Do not flash without
a new explicit owner request and fresh baseline preflight. Stage2 TCPM and
Stage3 SM5440 are not implemented and require the earlier stages' physical
acceptance. Installed production remains Test249 as accepted by Test250.

The owner subsequently requested Test252 physical testing ("开始测试吧").
Attempt01 is registered under `test-252-sm5714-stage1/attempt-01/README.md`.
Full read-only Test249 preflight and offline module install/restore rehearsal
passed. The candidate boot and paired181 modules are now installed, and boot
`fcb9a367-fa8e-43df-afb1-08db722ff2f1` has exact candidate notes/config/modules,
five-partition identity, DCC absence, both supplies and working ADB/NCM/Wi-Fi
SSH. Only boot changed; the other four partitions match accepted Test249.
Initial computer SDP input is limited500mA and does not overcome system load;
Charging labels alone are not charging acceptance. Battery-only151.021s passed
and ordinary Lenovo YG65G USB-C2 charging passed1201.035s/121 samples: SOC92 ->97,
actual pack current+432..1381mA, temperature30.6..31.2C, voltage4.330..4.418V.
No CPU/kernel/charge fault occurred. Plug-out passed151.127s, returning to
online0/Discharging with negative actual current. Final USB gate stopped on persistent ADB offline after reconnect, although
Windows enumerates both interfaces and source-bound NCM/Wi-Fi SSH work without
Code43. Post-stop exact candidate config/notes/five partitions/181 files and181
original files remain verified, DCC absent and no CPU/kernel fault or failed unit.
Stage1 full acceptance is incomplete. Preserve this stopped attempt/USB evidence;
no daemon restart, gadget reset, further experiment, rollback or cleanup was made.
Candidate remains installed for offline USB analysis, not promoted to production.
The on-device `.gts9-test252-original` contains all181 verified Test249 files;
external Test249 boot/module rollback is retained. Do not remove it or start
Stage2/3 before the results and retention decision. The original prepared-only
statements above describe the earlier phase, not the currently installed boot.
Check attempt01 RESULTS/summary before the next hardware action. ADB tools use
the owner's later `/mnt/d/android/platform-tools/adb.exe` location. One old GPU
firmware-file-not-found error was recorded separately during preflight; no GPU
or firmware change was made, and no CPU fault was observed in that evidence.

## Mission

Maintain a mainline-first Linux port for Samsung Galaxy Tab S9 Wi-Fi (`SM-X710`, Android codename `gts9wifi`) on Qualcomm SM8550 (`kalama`). Prefer upstream Linux interfaces and bindings. Samsung's downstream 5.15.153 sources/config/device tree are evidence about hardware, not the target architecture.

## Ground truth and pins

- Device: SM-X710 / gts9wifi, Wi-Fi model.
- SoC: SM8550 / Snapdragon 8 Gen 2; GPU Adreno 740.
- Samsung ABL selector values observed in the supplied live DTS:
  - `compatible = "qcom,kalama-mtp", "qcom,kalama", "qcom,mtp"`
  - `qcom,board-id = <0x10008 0x04>`
  - `qcom,msm-id = <0x218 0x20000 0x207 0x20000 0x207 0x10000 0x218 0x10000>`
- Stock config evidence: Linux 5.15.153, Android clang 14.0.7.
- Mainline build pin: Linux `v7.2-rc3`, commit `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`.
- Bootstrap board DTS reference: `troikoss/gts9wifi-fedora` commit `656d2ded8031657b60cde22e6fdfbc0b722a9dff`.
- Earlier X710 bring-up reference: `Azkali/sm8550-mainline` branch `gts9wifi-7.0`, inspected at `c48fedbd799a2b792a095840eeb96746afe2f327`. See `docs/AZKALI_SM8550_MAINLINE_ANALYSIS.md` and `kernel/PROVENANCE.md`.

Do not silently change either pin. A kernel bump and a hardware-port change must be separate changes so regressions remain attributable.

## Stock evidence supplied by the owner

The owner supplied a live DTB, a decompiled live DTS and a full stock `.config`. Their SHA-256 values and extracted hardware facts are recorded in `reference/stock/MANIFEST.md`.

Important device-specific differences from the S9 Ultra/X910:

- SM-X710 panel: `GTS9_ANA38407_AMSA10FA01`.
- Touch: STM FTS1BA90A, not the X910 Goodix GT9916.
- Pen: Wacom W90xx / WEZ01 family on I2C.
- WLAN/BT: QCA6490/WCN6855-class, not X910 WCN7850/Kiwi v2.
- Power: SM5714 charger/fuel gauge/USB-PD plus SM5440 direct charger.
- Type-C redriver: Parade PS5169; eUSB2 repeater: NXP PTN3222.
- Audio: four CS35L45 speaker amplifiers are visible in the stock DTS.

Never copy the entire downstream DTS into `arch/arm64/boot/dts/qcom/` and call that a mainline port. Translate only evidenced hardware into upstream bindings and keep unsupported vendor-only properties out.

## Repository invariants

1. `scripts/fetch-mainline.sh` must verify the exact upstream commit.
2. The upstream checkout under `.work/linux-mainline` stays pristine.
3. Device changes are staged into a disposable worktree under `.work/build/`.
4. Kernel build output goes to `.work/build/linux-out` and `out/kernel-gts9wifi`; never commit it.
5. Use `USE_CCACHE=1 ARCH=arm64 LLVM=1`; ccache is required for builds. Do not introduce a GCC-only build path unless there is a demonstrated need.
6. Keep critical early-boot/storage/console providers built in when the port depends on them before the root filesystem is available.
7. The owner-extracted stock config is immutable evidence: reconstruct it with `scripts/materialize-stock-config.sh`, verify its recorded SHA-256, then use it as the Kconfig seed. A symbol requested by the mainline fragment but dropped by `olddefconfig` must be treated as a build/config issue, not ignored.
8. Kernel image, DTB, config and release string must be hashed in every build.
9. No build script may flash or repartition a physical device.
10. Do not claim hardware works because a driver compiles or probes. Record `compiled`, `booted`, `enumerated`, and `physically verified` as different states.

## Remote workflow (owner instruction, 2026-09-21)

- `main` is left alone unless the owner explicitly asks for it. Work happens on a
  branch (currently `test`) and is pushed there.
- One purpose per commit; do not batch unrelated work into one commit.
- **Push to `origin` after every operation.** Verified work must not exist only on
  the local disk: commit it and push the branch, so the remote always matches what
  was actually built, tested or documented.
- If an operation changes nothing in the tree (a read-only check, for example),
  there is nothing to push; do not create an empty commit.
- GitHub Actions is **manual-only** (`workflow_dispatch`). A normal push must not
  start a kernel build or packaging job.
- Routine development is validated **locally**. After pushing a commit, do not wait
  for, poll, or require GitHub Actions before continuing.
- Run the GitHub Actions workflow only when the owner explicitly requests a remote
  CI check. A local successful build/validation is sufficient evidence for
  `compiled` / `packaged` status; it is still not evidence of a physical boot.

## Historical bring-up findings and physical-test workflow (owner instruction, 2026-09-21)

The milestones below describe their individual test dates. The current
production state is recorded at the top of this file and in test249 results.

- **Milestone reached (test 010, `reference/boot-tests/test-010-.../`): the
  owner watched the tablet power itself off while running this port's kernel.**
  `ABL -> mainline Linux -> BusyBox /init` is therefore established on hardware.
  A hung kernel cannot power a tablet off and `panic=0` removes the only way it
  could fake it. Everything below applies to work *beyond* that chain.
- The "stuck on the Samsung logo" state is a **running initramfs** waiting on a
  console that does not exist (no panel driver, unreachable UART, and a
  `console=null` the bootloader appends). Do not read it as a kernel failure.
- **Do not use the sec_log ring as evidence.** Test 007 measured the
  bootloader's own log spanning 2,096,187 of the 2,097,136 bytes of
  `sec_log_buf`, so mainline writes are overwritten before recovery can read
  them. An empty ring proves nothing. Live channels (USB, once it probes) or
  physical observation are the evidence paths.
- **Storage is up** (test 020): the missing provider was `CONFIG_QCOM_PDC`, the
  interrupt controller the SPMI arbiter hangs off.  With it the microSD (`mmc1`)
  and UFS (`sda`..`sdf`) both enumerate, the PMIC GPIO card detect works, and the
  bring-up report reaches the card - see tests 020 and 028.
- **The evidence loop is closed** (test 028): `/init` writes the report to the
  microSD card, waits ten seconds and resets into TWRP through the Android
  bootloader control block, so a test costs about half a minute and needs no
  hand-carried recovery boot.  `scripts/read-bringup-report.sh` reads the card.
- **The display pipeline is up** (test 035): the ported ANA38407 panel driver
  probes, `card0`/`card0-DSI-1` exist, the connector reports `connected`,
  `2560x1600` appears twice (the panel's 120 Hz and 60 Hz mode sets) and
  `/proc/fb` is `msm-kmsdrmfb`, so fbcon finally has a real surface.  Two things
  had to be true at once: `msm.separate_gpu_kms=1` (the Adreno is a component of
  the msm DRM master and fails without GPU firmware, which fails the card), and
  that parameter must sit near the *front* of our cmdline - the bootloader appends
  kilobytes of its own and was dropping the last token of ours.
- **Display status update (offline audit, 2026-09-22):** test 038's fb blank
  cycle recovered panel ID `80 00 04`, but CTL/vblank timeouts and partial
  pixels remain. Test 039's no-DSC modes exceed the DSI OPP limit and provide
  no decoding verdict. DSC/120 Hz is the default again; premature kickoff
  patch 0005 is held in pending because normal MSM kickoff follows modeset
  enable and DSC preparation. See `docs/DISPLAY_OFFLINE_AUDIT.md`.
- **Official-source candidate v1 (2026-09-22):** the owner supplied the full
  X710 source archive, including vendor display commands. The panel now uses
  X710 slew/PM_EN/TSP-sync/120HS programming, exposes only DSC/120 Hz and uses
  236 x 148 mm dimensions. Stock PPS matches the pinned helpers byte-for-byte
  over its 88 supplied bytes. Kernel, six host tests and an isolated boot
  bundle validate locally. See `docs/DISPLAY_X710_OFFICIAL_V1.md`.
- **The panel displays (test 040, `reference/boot-tests/test-040-.../`):** the
  official candidate was flashed to `boot` only and it works. The owner saw the
  boot command line on the panel, then a green/black marker, then three lines
  written two seconds apart appearing live - so the console both decodes and
  updates. `ctl start` failures are zero, where tests 037-039 never completed a
  command-mode start. What fixed it was the DDIC's own power-on and refresh-mode
  programming (`0x60`/`DD 0x13`/`B9 0x10 = 80 00 00 00` for 120HS), not DSC and
  not the DPU. The panel still cold-boots dark and is still recovered by the
  framebuffer blank cycle, now in 8 s. Unvalidated: the brightness/gamma/ACL
  stack, 60 Hz, other panel revisions, and long-run stability.
- **Pogo keyboard: input driver registered, application startup unresolved (test 045,
  `reference/boot-tests/test-045-.../`).** The driver
  (`kernel/drivers/keyboard-samsung-pogo.c`, `0006-input-add-samsung-pogo-keyboard.patch`)
  binds on hardware, registers `Book Cover Keyboard Slim (EF-DX710)` as event0,
  powers the rail, pulses the MCU's reset and reads its version actively, which is
  how Samsung's own driver proves presence. Five real faults were found and fixed
  along the way: the connect line is an edge not a presence level, cycling the
  rail on every edge reset the STM32 before it could answer, the diagnostic
  flooded the panel console, the handshake was passive, and the SWD pins were not
  owned by the driver.
  At that stage every application read returned `-ENXIO` (a NACK:
  the transfer ran, the bus was idle, nothing acknowledged) and a quick-write scan
  of the whole adapter finds **no device at any address**, while TWRP's stock
  kernel enumerates the same cover minutes earlier as `EF-DX710_v1.4.1.0`,
  `con:1/1`, `model_id 0x2`. The controller, pins (`qup2_se7` on gpio72/106),
  address, IRQ type, reset and rail model all match the vendor node. Two
  candidates were fitted and did not help: patch 0007
  (`samsung,reset-before-trans`, now in `pending/`) and an explicit rail
  power-cycle; both are retired with that result recorded.
  Round 2 compared the stock and mainline regulator tables: the pogo rail is
  enabled in **both** (`fixed_regulator${#}` / `pogo-vdd`, use=1, each with its
  client as consumer), no relevant rail differs, and the rail's source is not
  modelled as a parent in either tree.  It also established that gpiolib refuses
  to hand out gpio72/106 while they are multiplexed to `qup2_se7` (-EINVAL) and
  that `of_get_named_gpio()` no longer exists, which is why the vendor reads those
  lines with `gpio_get_value()` on numbers it never claims.
  Round 3 read the tree TWRP is built from: it uses a **prebuilt stock kernel**
  plus stock `dtb.img`/`dtbo.img` and Samsung's module stack, so its working
  environment is not reproducible in mainline.  Two facts came out of it.  Stock's
  log shows `rst:0`, so the MCU answered first try and was *already running* when
  the stock driver probed - nothing in that driver powers it from cold.  And
  `stm32_pogo_v3_start()` begins by instantiating a second I2C client at
  **`boot_addr = 0x51`**, the STM32's **system bootloader** interface, then runs
  `stm32_dev_firmware_update_menu(stm32, 0)`; the application interface at 0x2a is
  used only after that, and `client->addr != 0x51` guards the driver's power-reset
  and connect-state paths.
  Round 4 implemented that handshake and it answered: `MCU bootloader took the
  0xFF sync`, then `MCU bootloader version 0x12`.  **The MCU is powered and
  executing** - rail, bus, pins and address are all correct, and the whole
  power/supply line of investigation is closed.  What does not happen is the
  *application*: after the vendor's `sysboot_disconnect()` sequence the bootloader
  goes quiet and 0x2a never answers, which is what a boot-mode selection problem
  looks like.
  Round 5 tried both app-entry mechanisms on hardware and both failed: the
  vendor's exact `stm32_sysboot_disconnect()` timings leave 0x2a NAKing, and the
  bootloader's `GO` (0x21) write then times out because by that point the MCU
  answers on neither interface.  It has left the bootloader without the
  application coming up on i2c.
  Round 6 disproved the read-first hypothesis: with no rail cycle, no reset and no
  bootloader dance the application does not answer either, so the MCU genuinely
  sits in its system bootloader and goes quiet on both interfaces after any
  app-entry attempt.  It also established that the gpio12/13 sharing with the DMIC
  is genuine hardware sharing present in the vendor tree as well
  (`dmic45_clk_active`/`dmic45_data_active`, `function = "func1"`), and inactive
  here - the pinmux still shows those pins owned by `5-002a` minutes in.
  Round 7 offline audit (2026-09-22): commit `776b7d4` sends GO while the
  bootloader session is live, but leaves Get Version's final ACK unread. Samsung's
  `stm32_sysboot_i2c_get_info()` and ST AN4221 both require ACK/version/ACK.
  The caller also unconditionally resets after app entry, and the read-first
  success path skips mode checking, leaving `ready` false. These are driver
  defects; the earlier assertion that the remaining issue lies outside the driver
  was not established. The new candidate consumes the full version response,
  restarts a failed version session before GO, preserves successful application
  startup and checks mode on both success paths. Bus recovery now runs only after
  an application read fails. See `docs/POGO_STARTUP_REPAIR.md` for validation.
  Test 046 (`reference/boot-tests/test-046-20260922T055740Z/`) booted that
  candidate and returned safely to TWRP. The owner saw the console, but version
  exchange timed out (-110), GO was refused, and the application still NAKed
  after reset. The version error did not identify a transfer stage. Stock's
  `stm32_sysboot_connect()` then revealed a missing STEP3: after probing with
  unknown command 0xFF it resets into the bootloader again, without another
  probe, before issuing commands. The follow-up candidate now mirrors that
  sequence, tested against the actual GPIO/reset helper on the host.
  Test 047 (`reference/boot-tests/test-047-20260922T060344Z/`) validates that
  correction: the full version exchange returns 0x12 and both GO command/address
  ACKs succeed. Application 0x2a still NAKs after 150 ms; the fallback resets it
  and 40 further retries fail. The owner confirmed the keyboard stayed attached
  and unfolded. Pretest TWRP identifies EF-DX710, firmware 34, con:1/1, rst:0.
  Both tests returned safely to TWRP; 1d8a977 remains installed with read-back
  hashes verified. No key has been typed through mainline yet.
- **The acknowledged GO was the wrong command (2026-09-22, round 6).**  Tests 048
  and 049 settled it: no reset timing and no polling window makes the application
  answer after `GO 0x08000000`, and the READ path (now working, framed exactly like
  `stm32_sysboot_i2c_read`) shows `0x08000000` holds a Cortex-M vector table
  (SP `0x200056c0`, reset vector `0x0800c4a5`), not Samsung's `"STM32"` header -
  that header sits at offset `0xbc`/`0xc0` *inside* the image. After the GO the MCU
  answered on neither `0x2a` nor `0x51`. The vendor's own bring-up, run on every
  stock boot, never sends GO: `stm32_sysboot_mcu_validation()` enters the system
  bootloader, `stm32_sysboot_i2c_read()` takes the IC version from `0x08000200`
  (stock prints its last byte as `mcu_fw(ic):34`) and `stm32_sysboot_disconnect()`
  - BOOT0 low, one NRST pulse, 150 ms - releases the part so the application runs
  from flash. The port now does exactly that, plus stock's
  `stm32_set_mode(MODE_APP)`: a part reporting DFU mode gets the ABORT command
  (`0x17`) before it is read again. Test 050 measures it.
- **The host harness is not a compile test (2026-09-22).**  `tests/test_pogo_startup.py`
  strips forward declarations (`re.sub(r'^static [^\n]+;\n', ...)`) and mocks the
  helpers it does not extract, so it passed while the driver still called
  `pogo_recover_bus()` and `pogo_scan_bus()` after their definitions had been
  deleted. Always run `scripts/build-kernel.sh` before flashing, and treat the
  kernel build - not the harness - as the gate.
- **Display regression, found and fixed (2026-09-22, round 5).**  The owner
  reported a blank screen; `display_recover` was cycling the framebuffer as soon as
  `fb0` appeared, 5.91 s, before the panel driver's first read at 6.29 s, and had
  no retry - so test 040's working display stayed dark.  It now waits for the
  driver's own line and retries the full cycle up to three times; cycle 1 recovers
  `80 00 04` at 6.5 s and the owner confirms the console is visible again.
- **Physical tests need a recorded owner request (2026-09-22).** The test 040
  flash was made on one and tests 041-045 continued under the same recorded
  authorization, which each test's `source.txt` quotes. Do not flash, reboot or
  claim a hardware observation without a current request; ccache builds are
  always authorized. Compilation is not screen or keyboard validation.
- The microSD Debian rootfs, USB ADB/NCM/SSH and panel login were established
  after these early bring-up tests. Use current evidence before declaring a
  touchscreen, keyboard or other feature physically verified.
- **The USB rescue channel works** (test 029): with `gts9_usb_gadget=msc` the
  gadget exports the microSD partition read-only, Windows mounts it by itself,
  and the report can be read off the running tablet over USB - no TWRP, no power
  button, no owner.  Bulk transfers are therefore fine; the CDC-ACM function is
  what fails (the host sees its control interface and never its data interface),
  so a serial console is a gadget-side fix rather than a PHY problem.
- Known blockers on the way: an SPMI *write* blocks this kernel uninterruptibly,
  so `reboot recovery` through the SDAM and the RTC state word are both out until
  it is understood - the BCB path (a UFS write) replaces the former.  Nothing on
  this device clears that BCB afterwards (TWRP's cmdline still said
  `androidboot.boot_recovery=1` after a `gts9-to-recovery` boot), so `/init` now
  clears a stale block on every mainline boot: one request, one boot.  Reaching
  mainline at all means the request was served, so this is safe by construction.
- USB re-enumeration is marginal: the gadget comes up on most boots, but test 035
  lost it after a DSI host rebind under a live DRM master, and Windows then
  reported a failed device-descriptor request (code 43).  Do not rebind the DSI
  host while DRM holds it; a real suspend/resume is the documented recovery for
  the panel's cold-boot state.
- The generic initramfs lives in **init_boot**, so include init_boot whenever the
  new bundle differs from the flashed version. `gts9_userspace_proof=<seconds>`
  stays an opt-in in the initramfs (it powers the tablet off by itself) and is
  deliberately absent from `boot/cmdline.example.txt`; re-add it to reproduce
  test 010.
- Early candidate flashes were authorized and recorded per test. For later
  hardware work, follow the owner's authorization in the current session and
  the specific test registration. Validate the bundle, device identity,
  partition sizes, backups and per-partition write/read-back hashes before
  writing. Build and validation scripts must remain non-flashing. Do not rewrite
  recovery, vbmeta, bootloaders, userdata or the partition table as part of a
  boot-image test.
- Start log capture before reboot and use the test's registered observation
  window and stop conditions. If ADB is absent, correlate device-side and
  Windows-side evidence and ask for a physical observation only when needed;
  absence of ADB alone does not establish a crash.
- **Every subsequent physical test must have a committed log directory** under
  `reference/boot-tests/test-NNN-*/`, including failed or aborted
  attempts. Save raw last_kmsg, available pstore, recovery dmesg (labelled as
  recovery), device/layout checks, flash/read-back transcript, artifact hashes,
  source commit, bundle metadata and an observation/result README. Mark absent
  logs explicitly; never fabricate a successful capture or overwrite an older
  test directory. A directory containing only a summary is insufficient when
  raw logs are available. Do not commit firmware images or partition backups.
- Hash the archived evidence and commit/push it to `origin/test` after each
  test, before changing the next kernel/config/DTB. `.work` or external folders
  are staging locations, not the sole home of test evidence. The capture tool
  defaults to the tracked archive; pass CAPTURE_DIR for the specific test.
- Mainline log/marker present: follow the last proven stage and the actual
  panic/probe output. Init reached: verify persistence, then storage and USB
  rescue. Reboots without mainline evidence require independent kernel-handoff
  and retention checks; the measured `sec_log` ring is not a reliable Linux log.
  An absent write-back marker, empty pstore or a compressed-file DTB offset does
  not prove that Linux was never entered.
- Keep experiments attributable: change one failure hypothesis per follow-up
  test. MMU-off/head.S or Gunyah watchdog instrumentation remains a separate
  diagnostic branch, not a default workaround. Record the final device state
  and any stock restoration with read-back hashes in the test record.

## Pogo audit (2026-09-22; historical candidate after f6c5c6b)

That candidate restored DATA to IRQ_TYPE_LEVEL_LOW: announce-gpios is
GPIO_ACTIVE_LOW, so descriptor 1 means a physical low, not a high pulse. The
normal startup now releases the protocol mutex before enabling DATA, with only
50 ms power settling and no bootloader/scan/rail cycle. A model event makes a
single version-read attempt, not a minute-long loop under that same mutex.
Previous local startup experiments remain opt-in through
`keyboard_samsung_pogo.startup_diagnostics=1`; do not enable this for normal
keyboard validation. See `docs/POGO_EVENT_STARTUP.md` for the pinned S9U source
comparison and limits. The S9U firmware-update result is not permission or proof
that X710 needs another MCU image. Host tests pass; record physical results
separately and keep pre-existing test-087 logs distinct from new tests.

## Build commands

### Change-scoped validation (owner instruction, 2026-09-30)

- Kernel/driver/config/DTS or build integration changes: build once after the
  implementation is ready; validate resolved config, DT, protected files and
  paired artifacts. Run affected host tests during development and one full
  regression for final candidate review. Do not run wrapper/changed/all in
  succession when they select the same tests.
- Host runner/parser changes: run affected tests and syntax checks. Rebuild only
  if those changes also affect kernel inputs or packaging. Routing changes still
  require one full host regression; never delete or weaken tests to save time.
- Documentation/status/results changes: review the diff; check newly recorded
  evidence hashes and summary consistency as appropriate. No kernel rebuild or
  full host regression. Record `executed: false` for tests not run and reference
  the existing qualification separately. Changed-mode's conservative fallback
  is not a requirement to run all tests for a reviewed prose-only commit.
- Reuse qualification only while relevant source, profile, upstream pin,
  toolchain, build inputs and artifact hashes are unchanged. New source/input,
  artifact mismatch, failed validation or a relevant unresolved concern
  invalidates the affected qualification; commit SHA alone does not.
- Device testing: one full baseline check before deployment; verify staged
  files and written partitions/modules at the write boundary. Check current
  boot/config/notes, rescue transports and battery safety after boot. During a
  same-candidate observation, collect boot ID, telemetry, transport and new
  faults together; do not repeatedly hash every partition and rollback module
  directory or fetch an unchanged full journal for every sample. Save full
  journal at observation boundaries and on first anomaly. A new reboot or
  unexplained identity change requires fresh applicable checks. Keep registered
  observation windows, stop conditions and rollback; reduce duplicate checks,
  not safety limits or evidence needed to attribute a failure.

Host regression uses `bash scripts/check-stall-offline.sh` (changed files by default).
Use `--changed --base REV` for committed changes, `--core` for unconditional core
regression, or `--full` for all tests. A clean worktree against HEAD runs no tests;
it does not establish a regression pass. Unknown dependencies select all tests.
See `docs/HOST_TEST_WORKFLOW.md` for artifact/archive triggers and exact suite
selection. `--full` remains exhaustive; run it after changing suite routing or
retiring tests. New tests default to core. Do not interpret skipped prerequisites
as successful artifact validation; use `--fail-on-skip` on the Python runner when
complete validation is required. These commands do not contact the device.

Normal build:

```bash
./scripts/fetch-mainline.sh
./scripts/build-kernel.sh
```

Clean source-level comparison:

```bash
KERNEL_CLEAN=1 ./scripts/build-kernel.sh
```

Faster compile-only iteration when modules are irrelevant:

```bash
BUILD_MODULES=0 ./scripts/build-kernel.sh
```

Audit stock evidence supplied locally:

```bash
./scripts/audit-stock.sh /path/to/stock.config /path/to/live-device-tree.dts
```

Before committing a script change, at minimum run:

```bash
for script in scripts/*.sh scripts/lib/*.sh boot/*.sh; do
    bash -n "$script"
done
```

If the build environment is available, also perform `BUILD_MODULES=0 ./scripts/build-kernel.sh`. For config/DTS/patch changes, a clean build is preferred.

## Bring-up order

Do not debug everything at once. Work in this order unless logs prove another dependency is blocking:

1. ABL accepts the Android v4 image and enters Linux.
2. persistent log / serial diagnostics survive reboot;
3. reserved-memory is safe and there are no TrustZone fatal resets;
4. UFS and/or microSD root storage;
5. USB gadget/Ethernet rescue path;
6. panel/display;
7. touch, buttons and S Pen;
8. GPU/Turnip;
9. Wi-Fi and Bluetooth;
10. audio and DSPs;
11. charging/Type-C/DisplayPort;
12. cameras, sensors and fingerprint/SPSS.

A failure before Linux entry must be debugged as an ABL/boot-image/DT selection problem. An empty pstore is not evidence of a kernel crash if the bootloader never transferred control.

## Boot architecture after the Debian userspace split (2026-09-24)

The minimal profile (`gts9_minimal_rootfs=1`) now does one thing: find the TF
card, mount it, and `switch_root` into Debian. Everything that used to happen
in the initramfs before that - panel recovery, the USB ACM gadget, the report
channels - is Debian's job:

- `boot/minimal-rootfs-init.sh` + `boot/minimal-rootfs-state.sh` write the
  persistent stage record `/var/log/gts9-minimal-last-boot` on the Debian root
  (atomic replace, `switch-root` flushed before the exec).
- `rootfs-overlay/` carries the Debian units and helpers:
  `gts9-debian-entered/basic/getty/multi-user-stage.service` continue the same
  record from systemd, `gts9-usb-acm.service` creates only `acm.usb0`,
  `gts9-panel-recover.service` runs the X710 framebuffer blank/unblank cycle,
  and the ttyGS0 drop-in auto-logs in root on that console only.
- `scripts/install-debian-rootfs.sh` installs that overlay into a mounted
  Debian root or builds `out/gts9-debian-overlay.tar` for TWRP.  Kernel
  modules and firmware live in Debian under `lib/modules/<release>` and
  `lib/firmware/`; the minimal initramfs carries neither.
- `scripts/twrp-mount-debian.sh` and `docs/TWRP_DEBIAN_RECOVERY.md` are the
  offline path: identify the ext4 partition, mount it read-only and read the
  record when the panel is black and no USB console appears.

Rules that follow from this:

- Never make USB, DRM or tty1 a dependency of the root handoff. Panel and USB
  must fail independently of each other.
- A black screen plus no COM port is not a rootfs failure verdict; read the
  persistent record first (live or from TWRP).
- Do not modify regulator/PMIC parameters without stage evidence proving that
  the card never appeared.
- Keep the boot-critical providers built in (MMC/SDHCI, ext4, RPMh, PMIC, PDC,
  clock, pinctrl); do not move Pogo or the panel to modules yet.

## Samsung ABL constraints

Keep the legacy Samsung selectors in the board DTS unless a physical test proves they are no longer required. The X710 Azkali bring-up and sibling X910 work both demonstrate that Samsung ABL can reject an otherwise valid upstream-style DTB before Linux starts. Preserve `/__symbols__` in DTBs used in experiments that exercise Samsung's DT overlay path (`DTC_FLAGS_... := -@`).

For the pinned Linux 7.2-rc3 baseline, keep `kernel/patches/0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch`: Samsung ABL expects `qcom_tzlog`, `arch_timer`, and `qcom_scm` labels in the SM8550 base tree. Re-check whether the patch is still needed whenever the upstream kernel pin changes.

The current boot-bundle script uses the safer appended-DTB fallback pattern and deliberately does not flash anything. Do not change `dtbo` strategy casually; document the reason and recovery path first.

## Working with the stock config

The owner-extracted stock 5.15.153 `.config` is the **immutable seed and evidence baseline**, but it is not assumed to map one-for-one onto Linux 7.2. It is stored as deterministic Base64/gzip parts under `reference/stock/config/`; `scripts/materialize-stock-config.sh` reconstructs the original bytes and refuses a SHA-256 mismatch.

Use the stock config to answer questions such as:

- was a hardware block enabled in Samsung's kernel?
- was a driver built-in or modular?
- what compiler/Kconfig features did stock use?

For the mainline build, reconstruct the stock config, merge `kernel/config/gts9wifi-mainline.fragment`, then run Linux 7.2 `olddefconfig`. Unknown Samsung/Android-only 5.15 symbols are expected to disappear; required upstream symbols must be asserted explicitly by the fragment/build checks. Never edit the stock seed in place. A refreshed stock extraction must be added as a new identified artifact with updated hashes.

## Patch discipline

- Prefer upstream commits/backports over local patches.
- Every local patch should have one purpose and an explanatory commit message.
- Keep device-specific quirks gated to SM-X710/SM8550 where practical.
- If a patch becomes upstream, replace the local copy on the next controlled kernel rebase.
- Do not add Android-rooting/security modifications to this repository; keep the mainline hardware port focused.
- Do not import Azkali's `c48fedbd799a` early-boot framebuffer/Gunyah watchdog instrumentation into the default patch queue. If conventional logs are unavailable, reproduce it only as a temporary diagnostic series on a dedicated branch.

## Logs to request after physical tests

Ask for the smallest useful evidence set, typically:

```bash
uname -a
cat /proc/cmdline
dmesg -T > dmesg.txt
cat /proc/iomem > iomem.txt
cat /sys/firmware/devicetree/base/model 2>/dev/null
ls -l /dev/dri /dev/mmcblk* /dev/sd* 2>/dev/null
lspci -nn 2>/dev/null
ip -br link
```

For boot failures also collect Samsung/TWRP `last_kmsg` or ramoops/pstore if available. Record the exact artifact hashes that were flashed/tested.
