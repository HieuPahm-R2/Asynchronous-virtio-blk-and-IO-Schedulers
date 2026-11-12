# W3-L02 SCAN oracle (MOCK)

- Status: PASS
- HEAD: `b70a4106aed1e68be2a0efb4a873671e21501c55` (dirty: không)
- Toolchain: {'riscv64-unknown-elf-gcc': 'riscv64-unknown-elf-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0', 'qemu-system-riscv64': 'QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18)'}

- scan-mock CPUS=1: PASS (scan-cpus1.log)
- scan-mock CPUS=4: PASS (scan-cpus4.log)
- mutant scan-m1-no-reverse: EXPECTED_FAIL (scan-m1-no-reverse-cpus1.log)
- mutant scan-m2-tie-latest: EXPECTED_FAIL (scan-m2-tie-latest-cpus1.log)
- mutant scan-m3-unlink-tail: EXPECTED_FAIL (scan-m3-unlink-tail-cpus1.log)
- production hooks absent: True

MOCK driver: không phải bằng chứng READ thật/seek vật lý.
