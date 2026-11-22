# W4-H01/H02 real policy and loaded switch verification

- Status: PASS
- HEAD: `efe28493d22fd506317df781b87a58bbc9cc54a0`
- Dirty/source snapshot: True (see meta.json/source.patch)
- Real device: QEMU virtio-blk READ; tick is not physical seek latency.

- real-policy CPUS=1: PASS
- real-policy CPUS=4: PASS
- real-negative CPUS=4: EXPECTED_FAIL
- production-restore-smoke CPUS=1: PASS
