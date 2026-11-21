# W4-L01/L02 deadline + runtime switch (MOCK)

- Status: PASS
- HEAD: `5191ed8beda658120bf08667b87657fa45ed1861` (dirty: có)
- Toolchain: {'riscv64-linux-gnu-gcc': 'riscv64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0', 'qemu-system-riscv64': 'QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18)'}

- policy-mock CPUS=1: PASS (policy-cpus1.log)
- policy-mock CPUS=4: PASS (policy-cpus4.log)
- mutant dl-m1-no-expired: EXPECTED_FAIL (dl-m1-no-expired-cpus1.log)
- mutant dl-m3-eagain-batch: EXPECTED_FAIL (dl-m3-eagain-batch-cpus1.log)
- mutant sw-m2-reset-age: EXPECTED_FAIL (sw-m2-reset-age-cpus1.log)
- mutant scan-m1-no-reverse: EXPECTED_FAIL (scan-m1-no-reverse-cpus1.log)
- mutant scan-m2-tie-latest: EXPECTED_FAIL (scan-m2-tie-latest-cpus1.log)
- mutant scan-m3-unlink-tail: EXPECTED_FAIL (scan-m3-unlink-tail-cpus1.log)
- production hooks absent: True
- Deadline D21: READ expire=50 tick, batch=4 (đề xuất, chờ G01)

MOCK driver + đồng hồ giả: không phải bằng chứng READ thật/seek/latency.
