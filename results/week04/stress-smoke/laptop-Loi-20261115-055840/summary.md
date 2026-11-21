# W3-H02 Multi-producer async READ stress verification

- Status: **PASS**
- HEAD: `5191ed8beda658120bf08667b87657fa45ed1861` (`week4/loi-deadline-switch`)
- Seed: `0x26128003`
- Toolchain: `riscv64-linux-gnu-` (`/usr/bin/riscv64-linux-gnu-gcc-13`)
- Production hooks absent: `True`

## Runs

- stress-multi-producer CPUS=1: **PASS** (`stress-cpus1-01.log`)
- stress-multi-producer CPUS=4: **PASS** (`stress-cpus4-01.log`)
- negative-control-1byte CPUS=4: **EXPECTED_FAIL** (`negative-corrupt-fixture.log`)
- production-restore-smoke CPUS=1: **PASS** (`production-smoke.log`)
