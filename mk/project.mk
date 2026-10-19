# Mục tiêu build/test/đo của dự án ET4290.
#
# File này KHÔNG chứa rule build của xv6. Nó được include ở cuối Makefile
# upstream (xem khối "ET4290 project targets"). Khi cập nhật xv6 lên tag mới,
# scripts/update-xv6.sh sẽ nối lại include này.

PYTHON ?= python3
TEST_ARGS ?=
BASELINE_ARGS ?=

.PHONY: help env-check list-tests test test-fast test-slow baseline clean-all

help:
	@echo "ET4290 — Async virtio-blk & I/O schedulers trên xv6-riscv"
	@echo ""
	@echo "  make qemu              boot xv6 (đặt CPUS=1..4, mặc định 3)"
	@echo "  make qemu-gdb          boot và chờ gdb-multiarch kết nối"
	@echo "  make test              suite mặc định (nhanh + stock usertests -q, CPUS=1/4)"
	@echo "  make test-fast         smoke test: boot + shell (~10 giây)"
	@echo "  make test-slow         stock usertests đầy đủ + grind (lâu, chạy có chủ đích)"
	@echo "  make baseline          đo baseline stock, ghi kết quả vào results/baseline/"
	@echo "  make list-tests        liệt kê test case đã đăng ký"
	@echo "  make env-check         kiểm tra toolchain + build + boot"
	@echo "  make clean-all         make clean + xoá kết quả test cục bộ"
	@echo ""
	@echo "  Ví dụ: make qemu CPUS=1 | make test TEST_ARGS='--verbose'"

env-check:
	@bash scripts/check-env.sh

list-tests:
	@$(PYTHON) tests/runner.py --list

test:
	@$(PYTHON) tests/runner.py $(TEST_ARGS)

test-fast:
	@$(PYTHON) tests/runner.py --tag fast $(TEST_ARGS)

test-slow:
	@$(PYTHON) tests/runner.py --tag slow $(TEST_ARGS)

baseline:
	@bash scripts/baseline.sh $(BASELINE_ARGS)

clean-all: clean
	rm -rf results/local
