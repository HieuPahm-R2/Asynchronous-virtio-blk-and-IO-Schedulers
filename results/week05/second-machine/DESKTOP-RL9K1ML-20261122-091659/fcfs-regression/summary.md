# Hoàng week 02/03 verification (unified TOOLPREFIX)

Status: PASS
HEAD: `f5130bb9898c4154c3e761e2c85f3038f3a02a86` (`week4/hieu-contract-oracle`)
xv6 pin: `f780d7850765d74cbdcd1fff4b822d8829f7c9bd 2026-10-15 build with -fno-delete-null-pointer-checks`
TOOLPREFIX: `riscv64-linux-gnu-` (`/usr/bin/riscv64-linux-gnu-gcc-13`, `/usr/bin/riscv64-linux-gnu-nm`)

- real-virtio CPUS=1: PASS (hw-cpus1-01.log)
- real-virtio CPUS=1: PASS (hw-cpus1-02.log)
- real-virtio CPUS=1: PASS (hw-cpus1-03.log)
- real-virtio CPUS=1: PASS (hw-cpus1-04.log)
- real-virtio CPUS=1: PASS (hw-cpus1-05.log)
- real-virtio CPUS=1: PASS (hw-cpus1-06.log)
- real-virtio CPUS=1: PASS (hw-cpus1-07.log)
- real-virtio CPUS=1: PASS (hw-cpus1-08.log)
- real-virtio CPUS=1: PASS (hw-cpus1-09.log)
- real-virtio CPUS=1: PASS (hw-cpus1-10.log)
- real-virtio CPUS=4: PASS (hw-cpus4-01.log)
- real-virtio CPUS=4: PASS (hw-cpus4-02.log)
- real-virtio CPUS=4: PASS (hw-cpus4-03.log)
- real-virtio CPUS=4: PASS (hw-cpus4-04.log)
- real-virtio CPUS=4: PASS (hw-cpus4-05.log)
- real-virtio CPUS=4: PASS (hw-cpus4-06.log)
- real-virtio CPUS=4: PASS (hw-cpus4-07.log)
- real-virtio CPUS=4: PASS (hw-cpus4-08.log)
- real-virtio CPUS=4: PASS (hw-cpus4-09.log)
- real-virtio CPUS=4: PASS (hw-cpus4-10.log)
- negative-control CPUS=1: EXPECTED_FAIL (negative-corrupt-fixture.log)
- pool-mock-timer CPUS=1: PASS (pool-cpus1.log)
- pool-mock-timer CPUS=4: PASS (pool-cpus4.log)
- queue-mock CPUS=1: PASS (queue-cpus1.log)
- queue-mock CPUS=4: PASS (queue-cpus4.log)

Negative control is intentionally corrupt; mock/timer tests are not hardware evidence.
