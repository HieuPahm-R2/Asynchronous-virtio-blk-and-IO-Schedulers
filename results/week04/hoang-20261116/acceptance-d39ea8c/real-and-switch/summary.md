# W4-H01/H02 real policy and loaded switch verification

- Status: PASS
- HEAD: `d39ea8cf3500a0fdcf023efeab2c850dd2b767d6`
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
