# W4-H01/H02 real policy and loaded switch verification

- Status: PASS
- HEAD: `c6e0dae62a73f82a572b8d55c38f16bae6bff40d`
- Dirty/source snapshot: False (see meta.json/source.patch)
- Real device: QEMU virtio-blk READ; tick is not physical seek latency.

- real-policy CPUS=1: PASS
- real-policy CPUS=4: PASS
- real-negative CPUS=4: EXPECTED_FAIL
- switch-stress-01 CPUS=1: PASS
- switch-stress-01 CPUS=4: PASS
- stress-negative CPUS=4: EXPECTED_FAIL
- production-restore-smoke CPUS=1: PASS
