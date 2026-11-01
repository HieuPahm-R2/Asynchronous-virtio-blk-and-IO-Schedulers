# Hoàng week 02 verification

Status: PASS

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
