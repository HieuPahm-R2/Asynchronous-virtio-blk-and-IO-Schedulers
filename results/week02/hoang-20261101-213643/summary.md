# Hoàng week 02 verification

Status: PASS

- real-virtio CPUS=1: PASS (hw-cpus1-01.log)
- real-virtio CPUS=4: PASS (hw-cpus4-01.log)
- negative-control CPUS=1: EXPECTED_FAIL (negative-corrupt-fixture.log)

Negative control is intentionally corrupt; mock/timer tests are not hardware evidence.
