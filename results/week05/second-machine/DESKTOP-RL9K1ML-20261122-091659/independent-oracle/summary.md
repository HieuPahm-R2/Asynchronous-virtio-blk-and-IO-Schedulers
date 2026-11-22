# W4-I01 — Oracle độc lập deadline/switch + snapshot + mutant

- Status: **PASS**
- HEAD: `f5130bb9898c4154c3e761e2c85f3038f3a02a86` (`week4/hieu-contract-oracle`)
- xv6 pin: `f780d7850765d74cbdcd1fff4b822d8829f7c9bd 2026-10-15 build with -fno-delete-null-pointer-checks`
- TOOLPREFIX: `riscv64-linux-gnu-`
- Dirty lúc chạy: `không`

## 1. Oracle độc lập I01 trên mock (CPU1/4)
- CPUS=1: PASS (policy-cpus1.log)
- CPUS=4: PASS (policy-cpus4.log)

## 2. Mutant (EXPECTED_FAIL)
- i01-m1-expired-latest [DEADLINE]: EXPECTED_FAIL (i01-m1-expired-latest-cpus1.log)
- i01-m2-noop-epoch [SWITCH]: EXPECTED_FAIL (i01-m2-noop-epoch-cpus1.log)
- i01-m3-keep-batch [SWITCH]: EXPECTED_FAIL (i01-m3-keep-batch-cpus1.log)
- dl-m1-no-expired [DEADLINE]: EXPECTED_FAIL (dl-m1-no-expired-cpus1.log)
- dl-m3-eagain-batch [DEADLINE]: EXPECTED_FAIL (dl-m3-eagain-batch-cpus1.log)
- sw-m2-reset-age [SWITCH]: EXPECTED_FAIL (sw-m2-reset-age-cpus1.log)

## 3. READ thật cơ bản + snapshot timing
- CPUS=1: PASS (hw-cpus1-snap.log)
- IO-SNAP: samples=83, wait_sum=0, wait_max=0, service_sum=0, service_max=0, total_sum=0, total_max=0, zero_total=83 tick

## 4. Production + repo checks
- production hooks absent: True
- check-text rc: 0
- git diff --check rc: 0

MOCK deadline/switch: không chứng minh READ thật/seek/latency vật lý.
READ thật ở đây chỉ 1 boot CPU1 cho mẫu snapshot/timing; acceptance
SCAN/deadline real 10 boot và máy thứ hai thuộc H01/H02/G02.
Tick = 100 ms trên QEMU pin: mẫu 0 nghĩa là dưới 1 tick, không phải 0 ms.
