# W4-H01/H02 real policy and loaded switch verification

- Status: PASS
- HEAD: `f5130bb9898c4154c3e761e2c85f3038f3a02a86`
- Dirty/source snapshot: False (see meta.json/source.patch)
- Real device: QEMU virtio-blk READ; tick is not physical seek latency.

- real-policy CPUS=1: PASS
- real-policy CPUS=4: PASS
- real-negative CPUS=4: EXPECTED_FAIL
- switch-stress-01 CPUS=1: PASS
- switch-stress-02 CPUS=1: PASS
- switch-stress-03 CPUS=1: PASS
- switch-stress-04 CPUS=1: PASS
- switch-stress-05 CPUS=1: PASS
- switch-stress-01 CPUS=4: PASS
- switch-stress-02 CPUS=4: PASS
- switch-stress-03 CPUS=4: PASS
- switch-stress-04 CPUS=4: PASS
- switch-stress-05 CPUS=4: PASS
- stress-negative CPUS=4: EXPECTED_FAIL
- production-restore-smoke CPUS=1: PASS
