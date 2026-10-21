# Demo cho giáº£ng viÃªn â€” xem cÃ¡i gÃ¬, cháº¡y cÃ¡i gÃ¬

TÃ i liá»‡u nÃ y tráº£ lá»i: **demo cho GV xem cÃ¡i gÃ¬, theo tá»«ng má»‘c**, kÃ¨m káº¿t quáº£ máº«u
cháº¡y tháº­t trÃªn base hiá»‡n táº¡i vÃ  storyboard cho demo cuá»‘i ká»³ 20 phÃºt.

> NguyÃªn táº¯c: **demo lÃ  cháº¡y tháº­t + log tháº­t**, khÃ´ng pháº£i Ä‘á»c slide.
> Má»i con sá»‘ pháº£i má»Ÿ Ä‘Æ°á»£c file báº±ng chá»©ng trong `results/` hoáº·c `docs/`.
> Pháº§n chÆ°a lÃ m thÃ¬ ghi rÃµ **chÆ°a cÃ³**, khÃ´ng diá»…n cho giá»‘ng Ä‘Ã£ xong.

## 1. Demo theo tá»«ng má»‘c cá»§a há»c pháº§n

| Má»‘c | Thá»i lÆ°á»£ng | Demo cÃ¡i gÃ¬ | Báº±ng chá»©ng trong repo |
| --- | --- | --- | --- |
| **Check-in tuáº§n 1** | 10 phÃºt | mÃ´i trÆ°á»ng build/boot, baseline stock, sÆ¡ Ä‘á»“ I/O, phÃ¢n cÃ´ng, blocker | `make demo`, `results/baseline/<ts>/`, `docs/architecture.md` |
| Proposal (tuáº§n há»c pháº§n 3) | 2â€“3 trang + trao Ä‘á»•i | chá»‘t interface/lock/scope, trace FCFS/SCAN trÃªn giáº¥y | `docs/architecture.md`, test case skeleton |
| Midterm (tuáº§n há»c pháº§n 5) | 10 phÃºt | core cháº¡y má»™t pháº§n + test Ä‘áº§u tiÃªn | `make test` PASS, PR/issue |
| Code freeze (tuáº§n 8) | â€” | tag final, build tá»« clone má»›i | tag + log CI |
| **Final demo (tuáº§n 9)** | **20 phÃºt ká»ƒ cáº£ Q&A** | 6 pháº§n bÃªn dÆ°á»›i | trace, Ä‘á»“ thá»‹, stress log, checksum |

## 2. Check-in tuáº§n 1 (10 phÃºt) â€” cháº¡y Ä‘Æ°á»£c ngay hÃ´m nay

### 2.1 Ká»‹ch báº£n theo má»¥c 8 cá»§a káº¿ hoáº¡ch

| PhÃºt | Ná»™i dung | Thao tÃ¡c trÃªn mÃ¡y |
| ---: | --- | --- |
| 0â€“1 | Má»¥c tiÃªu/pháº¡m vi Ä‘á» tÃ i (1 cÃ¢u) | slide 1 dÃ²ng |
| 1â€“3 | Baseline & mÃ´i trÆ°á»ng | `make demo` (pháº§n 1, 2, 4, 5) |
| 3â€“6 | SÆ¡ Ä‘á»“ submit/completion + rá»§i ro | má»Ÿ [`architecture.md`](architecture.md) (Mermaid) |
| 6â€“8 | PhÃ¢n cÃ´ng tuáº§n 2, má»—i ngÆ°á»i 1 module kernel | README má»¥c "NhÃ³m" |
| 8â€“10 | Blocker + cÃ¢u há»i GV + káº¿ hoáº¡ch tuáº§n sau | README má»¥c "Viá»‡c cáº§n chá»‘t" |

### 2.2 Ba thá»© nÃªn má»Ÿ sáºµn trÆ°á»›c khi vÃ o

1. Terminal cháº¡y `make demo` (nÃªn cháº¡y nÃ³ng trÆ°á»›c 1 láº§n cho cache build).
2. [`docs/architecture.md`](architecture.md) â€” sÆ¡ Ä‘á»“ Mermaid + lifecycle request.
3. `results/baseline/<timestamp>/summary.md` â€” báº£ng 6/6 PASS.

### 2.3 Output máº«u â€” cháº¡y tháº­t trÃªn base hiá»‡n táº¡i

`make demo` (rÃºt gá»n, nguyÃªn báº£n dÃ i hÆ¡n):

```text
================================================================
 1/6. MÃ”I TRÆ¯á»œNG & PIN XV6
================================================================
  Distro:             Ubuntu 24.04 LTS
  Kernel:             Linux 6.x ... x86_64
  CPU / RAM:          6 CPU / 7.7Gi
  Project commit:     29774c8 main
  xv6 pin:            f780d7850765... 2026-10-15
  RISC-V gcc:         riscv64-linux-gnu-gcc (Ubuntu 13.3.0...) 13.3.0
  QEMU:               QEMU emulator version 8.2.2
  -> KhÃ´ng cÃ³ /dev/kvm â€” QEMU cháº¡y TCG (cháº­m hÆ¡n KVM, váº«n Ä‘Ãºng chá»©c nÄƒng)

================================================================
 2/6. BUILD Má»˜T Lá»†NH
================================================================
  make kernel/kernel fs.img:   OK (1 giÃ¢y)
  kernel/kernel:               272K
  fs.img:                      2.0M

================================================================
 3/6. BOOT XV6 TRONG QEMU (CPUS=1)
================================================================
  xv6 kernel is booting
  init: starting sh
  $ echo BOOT_OK
  BOOT_OK
  $
  -> PASS: xv6 boot, init cháº¡y, shell nháº­n lá»‡nh

================================================================
 4/6. TEST HARNESS â€” PASS/FAIL Tá»ªNG CASE (make test-fast)
================================================================
--- [1/2] boot-smoke (CPUS=1) ... PASS (3.1s)
--- [2/2] shell-fs-cpus3 (CPUS=3) ... PASS (4.1s)
== Káº¿t quáº£: 2 PASS / 0 FAIL ==

================================================================
 5/6. BASELINE STOCK ÄÃƒ ÄO (báº±ng chá»©ng tuáº§n 1)
================================================================
  | `boot-smoke`            | 1 | PASS | 3.50  |
  | `shell-fs-cpus3`        | 3 | PASS | 4.27  |
  | `usertests-quick-cpus1` | 1 | PASS | 536.77|
  | `usertests-quick-cpus4` | 4 | PASS | 492.98|
  | `grind-smoke-cpus1`     | 1 | PASS | 63.00 |
  | `grind-smoke-cpus4`     | 4 | PASS | 63.27 |
  -> 6 PASS / 0 FAIL â€” results/baseline/2026-10-19_222935/

================================================================
 6/6. Háº  Táº¦NG CHá»œ CHO TUáº¦N 2 TRá»ž ÄI
================================================================
  (danh sÃ¡ch 8 test case: boot, shell, usertests, grind...)
  => Táº¤T Cáº¢ PASS: mÃ´i trÆ°á»ng + build + boot + test + baseline Ä‘á»u sáºµn sÃ ng.
```

Báº£n Ä‘áº§y Ä‘á»§: cháº¡y `make demo` trÃªn mÃ¡y báº¡n. Boot serial náº±m á»Ÿ
`results/local/demo/logs/boot-smoke.log`, baseline á»Ÿ
[`../results/baseline/2026-10-19_222935/summary.md`](../results/baseline/2026-10-19_222935/summary.md).

## 3. Final demo 20 phÃºt (tuáº§n 9) â€” storyboard

Theo má»¥c 10 cá»§a káº¿ hoáº¡ch. Cá»™t "hiá»‡n cÃ³" cho biáº¿t pháº§n nÃ o base Ä‘Ã£ cÃ³ sáºµn hÃ´m nay,
pháº§n nÃ o sáº½ Ä‘Æ°á»£c xÃ¢y á»Ÿ tuáº§n 2â€“8.

| PhÃºt | Pháº§n | Show gÃ¬ (khi hoÃ n thÃ nh) | Hiá»‡n cÃ³ |
| ---: | --- | --- | --- |
| 0â€“2 | Kiáº¿n trÃºc | sÆ¡ Ä‘á»“ Ä‘Æ°á»ng I/O + state machine request + lock order | âœ… `docs/architecture.md` |
| 2â€“6 | Async & nhiá»u outstanding | submit nhiá»u request, kernel trace `INFLIGHT`, counter `max_inflight â‰¥ 2`, káº¿t quáº£ Ä‘Ãºng | â³ cáº§n code + user program |
| 6â€“10 | Äá»•i scheduler khi Ä‘ang cháº¡y | workload Ä‘ang cháº¡y, Ä‘á»•i FCFSâ†’SCANâ†’deadline, trace dispatch, counter `policy_switch`, khÃ´ng máº¥t request | â³ |
| 10â€“13 | Merging + checksum | nhiá»u request read liá»n ká» â†’ **má»™t** lá»‡nh thiáº¿t bá»‹, checksum Ä‘Ãºng tá»«ng request con, descriptor exhaustion test | â³ |
| 13â€“16 | Äá»“ thá»‹ + stress + háº¡n cháº¿ | throughput/latency cÃ¹ng workload, p50/p95, log stress 30 phÃºt, danh sÃ¡ch háº¡n cháº¿ | âœ… sá»‘ baseline, â³ Ä‘á»“ thá»‹ scheduler |
| 16â€“20 | Q&A | má»—i ngÆ°á»i giáº£i thÃ­ch module kernel cá»§a mÃ¬nh | â€” |

### 3.1 Demo sáº½ "trÃ´ng nhÆ° tháº¿ nÃ o" â€” vÃ­ dá»¥ trace dá»± kiáº¿n (chÆ°a cÃ³, tuáº§n 2â€“5 sáº½ in ra)

Khi cÃ³ tÃ­nh nÄƒng, demo lÃ  má»™t chuá»—i lá»‡nh ngáº¯n, má»—i lá»‡nh in ra báº±ng chá»©ng:

```text
$ iotest async 4            # submit 4 read báº¥t Ä‘á»“ng bá»™ rá»“i lÃ m viá»‡c khÃ¡c
SUBMIT   id=1 seq=1 sector=100 nbytes=1024
SUBMIT   id=2 seq=2 sector=102 nbytes=1024
SUBMIT   id=3 seq=3 sector=104 nbytes=1024
SUBMIT   id=4 seq=4 sector=106 nbytes=1024
WORK     caller lÃ m viá»‡c khÃ¡c trong lÃºc chá»
DISPATCH id=2 policy=FCFS max_inflight=2
DISPATCH id=1 policy=FCFS max_inflight=2
COMPLETE id=2 checksum=OK
...
RESULT   max_inflight=2 (>=2), 4 request, checksum ALL OK
```

```text
$ sched FCFS; iotest randread 20; sched switch SCAN
POLICY   FCFS -> SCAN (policy_switch=1, queued=7, inflight=2)
DISPATCH id=3 sector=180 dir=up
DISPATCH id=5 sector=196 dir=up
DISPATCH id=7 sector=204 dir=up
REVERSE  head=capacity, dir=down          # SCAN khÃ¡c LOOK á»Ÿ chá»— Ä‘i tá»›i biÃªn
DISPATCH id=2 sector=196 dir=down
RESULT   no request lost, queued/inflight preserved
```

```text
$ iotest merge                 # 8 logical read liá»n ká»
MERGE    children=[1,2,3,4] -> device_cmd sector=100 nbytes=4096
MERGE    children=[5,6,7,8] -> device_cmd sector=108 nbytes=4096
COMPLETE child=1 checksum=OK ... child=8 checksum=OK
RESULT   logical=8 device_cmds=2 merge_ratio=4.0, descriptor leak=0
```

```text
$ make bench                   # káº¿t quáº£ tháº­t khi cÃ³ scheduler
policy   merge  throughput(MB/s)  latency p50/p95 (ms)  max_inflight
stock    -      1.0               ...
FCFS     off    ...               ...
FCFS     on     ...               ...
SCAN     off    ...
SCAN     on     ...
deadline off    ...
deadline on     ...
â†’ Ä‘á»“ thá»‹: results/bench/<timestamp>/throughput.png
```

> CÃ¡c chÆ°Æ¡ng trÃ¬nh `iotest`/`sched`/`bench` **chÆ°a tá»“n táº¡i** â€” chÃºng lÃ  viá»‡c cá»§a
> tuáº§n 2â€“8. Base hiá»‡n cÃ³ harness QEMU Ä‘á»ƒ cháº¡y chÃºng dÆ°á»›i dáº¡ng test case khi xong.

### 3.2 Äiá»u báº¯t buá»™c theo spec

- Má»—i thÃ nh viÃªn **tá»± trÃ¬nh bÃ y module kernel mÃ¬nh lÃ m** (khÃ´ng Ä‘á»ƒ 1 ngÆ°á»i nÃ³i háº¿t).
- Chuáº©n bá»‹ workload ngáº¯n (â‰¤ 2 phÃºt) tÃ¡i láº­p Ä‘Æ°á»£c; log stress 30 phÃºt lÃ  báº±ng chá»©ng bá»• sung.
- Q&A 4 phÃºt: tráº£ lá»i Ä‘Æ°á»£c vÃ¬ sao thá»© tá»± dispatch Ä‘Ãºng, vÃ¬ sao khÃ´ng máº¥t wakeup,
  vÃ¬ sao merging khÃ´ng sai dá»¯ liá»‡u, vÃ¬ sao khÃ´ng rÃ² descriptor.

## 4. Checklist trÆ°á»›c buá»•i demo (tá»± kiá»ƒm 10 phÃºt)

- [ ] CÃ¹ng commit Ä‘Ã£ push: `git rev-parse HEAD` khá»›p commit trÃªn GitHub.
- [ ] `make env-check` PASS trÃªn **Ä‘Ãºng mÃ¡y demo**.
- [ ] `make demo` PASS; má»Ÿ sáºµn `results/baseline/<ts>/summary.md`.
- [ ] CÃ¡c log/trace/Ä‘á»“ thá»‹ cáº§n demo Ä‘Ã£ cÃ³ trong `results/` (khÃ´ng phá»¥ thuá»™c máº¡ng).
- [ ] KhÃ´ng dÃ¹ng sá»‘ liá»‡u chÆ°a cÃ³ log; pháº§n chÆ°a lÃ m thÃ¬ nÃ³i "chÆ°a cÃ³ / káº¿ hoáº¡ch tuáº§n X".
- [ ] Quay video dá»± phÃ²ng 2â€“3 phÃºt toÃ n bá»™ luá»“ng demo (trÆ°á»ng há»£p QEMU lá»—i táº¡i chá»—).
- [ ] Táº¯t thÃ´ng bÃ¡o; terminal font Ä‘á»§ lá»›n; Ä‘Ã³ng tab thá»«a.
- [ ] Má»—i ngÆ°á»i biáº¿t pháº§n mÃ¬nh nÃ³i + 2 cÃ¢u Q&A dá»± kiáº¿n.

## 5. Lá»—i thÆ°á»ng gáº·p khi demo & cÃ¡ch xá»­ lÃ½

| TÃ¬nh huá»‘ng | Xá»­ lÃ½ ngay |
| --- | --- |
| QEMU khá»Ÿi Ä‘á»™ng cháº­m/vÆ°á»›ng | cháº¡y `make demo DEMO_ARGS=--no-qemu`, dÃ¹ng video dá»± phÃ²ng, chá»‰ vÃ o log Ä‘Ã£ lÆ°u |
| Build fail táº¡i chá»— | cháº¡y `make env-check` vÃ  nÃ³i rÃµ Ä‘Ã¢y lÃ  mÃ´i trÆ°á»ng; má»Ÿ log baseline Ä‘Ã£ lÆ°u |
| Máº¥t máº¡ng | má»i thá»© Ä‘Ã£ local (source + log), khÃ´ng cáº§n máº¡ng Ä‘á»ƒ demo |
| GV há»i sá»‘ liá»‡u | má»Ÿ Ä‘Ãºng file `results/.../summary.md` + `meta.json` (commit, toolchain, CPUS) |
| Thá»i gian trÃ´i | bÃ¡m má»‘c phÃºt trong báº£ng; pháº§n Q&A luÃ´n giá»¯ 4 phÃºt |
| CÃ¢u há»i ngoÃ i pháº¡m vi | ghi vÃ o "pending" â€” khÃ´ng tráº£ lá»i phá»ng Ä‘oÃ¡n |

