# Cháº¡y dá»± Ã¡n trÃªn laptop Ubuntu (clone vá» mÃ¡y má»›i)

TÃ i liá»‡u nÃ y lÃ  runbook cho **mÃ¡y Ubuntu tháº­t** (laptop Linux). Náº¿u dÃ¹ng Windows
thÃ¬ xem [environment.md](environment.md) (WSL2 Ubuntu). ToÃ n bá»™ lá»‡nh dÆ°á»›i Ä‘Ã¢y
cháº¡y trong terminal Ubuntu, khÃ´ng cáº§n máº¡ng sau bÆ°á»›c cÃ i toolchain.

## 0. Äiá»u kiá»‡n cáº§n

| Háº¡ng má»¥c | YÃªu cáº§u | Ghi chÃº |
| --- | --- | --- |
| OS | **Ubuntu 24.04 LTS** (khuyáº¿n nghá»‹) | 22.04 cÃ³ QEMU 6.2 < 7.2 â†’ Makefile bÃ¡o lá»—i; cáº§n 24.04+ hoáº·c PPA |
| CPU/RAM | 2 CPU / 2 GB trá»Ÿ lÃªn | `CPUS=4` cáº§n â‰¥ 4 CPU; `-m 128M` nÃªn RAM khÃ´ng cáº§n nhiá»u |
| ÄÄ©a | ~2 GB trá»‘ng | toolchain ~1 GB + source/build |
| Quyá»n | `sudo` (má»™t láº§n Ä‘á»ƒ cÃ i) | build/test khÃ´ng cáº§n root |
| Máº¡ng | láº§n Ä‘áº§u cÃ i apt + clone repo | sau Ä‘Ã³ cháº¡y offline Ä‘Æ°á»£c |
| Truy cáº­p repo | repo **private** â†’ cáº§n PAT/SSH key GitHub | dÃ¹ng `gh auth login` hoáº·c SSH key |

> Repo private theo yÃªu cáº§u há»c pháº§n; giáº£ng viÃªn pháº£i Ä‘Æ°á»£c cáº¥p quyá»n Ä‘á»c.

## 1. Clone source (Ä‘Ãºng commit)

```bash
git clone https://github.com/HieuPahm-R2/Asynchronous-virtio-blk-and-IO-Schedulers.git ~/ET4290
cd ~/ET4290

git log --oneline -2          # pháº£i tháº¥y commit base/baseline cá»§a nhÃ³m
cat .xv6-commit               # commit xv6 Ä‘ang pin
git rev-parse HEAD            # ghi hash nÃ y vÃ o bÃ¡o cÃ¡o tuáº§n
```

NÃªn clone vÃ o `~/ET4290` (Ä‘Æ°á»ng dáº«n **khÃ´ng cÃ³ dáº¥u cÃ¡ch**).

## 2. CÃ i toolchain (má»™t láº§n cho má»—i mÃ¡y)

```bash
sudo bash scripts/setup-env.sh
# hoáº·c tá»‘i thiá»ƒu: sudo bash scripts/setup-env.sh --minimal
```

Script cÃ i: `build-essential`, `gcc-riscv64-linux-gnu`, `binutils-riscv64-linux-gnu`,
`qemu-system-misc`, `gdb-multiarch`, `bc`, `perl`, `python3`, `clang-format`â€¦
(idempotent â€” cháº¡y láº¡i vÃ´ háº¡i; tá»± thá»­ IPv4 náº¿u apt lá»—i máº¡ng).

## 3. Kiá»ƒm tra mÃ´i trÆ°á»ng â€” bÆ°á»›c quan trá»ng nháº¥t

```bash
make env-check
```

Káº¿t quáº£ máº«u (mÃ¡y dev WSL2, laptop Ubuntu sáº½ tÆ°Æ¡ng tá»±):

```text
== Há»‡ Ä‘iá»u hÃ nh ==
  distro: Ubuntu 24.04 LTS
  kernel: 5.15.167.4-microsoft-standard-WSL2
  mÃ´i trÆ°á»ng: WSL2
  CPU: 6  |  RAM: 7.7Gi

== Pin xv6-riscv ==
  f780d7850765d74cbdcd1fff4b822d8829f7c9bd 2026-10-15 build with -fno-delete-null-pointer-checks
  [ OK ] Ä‘Ã£ ghi pin xv6 (.xv6-commit)

== Toolchain ==
  [ OK ] make: GNU Make 4.3
  [ OK ] git: git version 2.43.0
  [ OK ] python3: Python 3.12.3
  [ OK ] bc: bc 1.07.1
  [ OK ] perl: v5.38.2
  [ OK ] RISC-V gcc: riscv64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
  [ OK ] QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18)
  [ OK ] QEMU >= 7.2
  [ OK ] gdb-multiarch (debug kernel)
  [ OK ] clang-format (Ubuntu clang-format version 18.1.3)

== Build thá»­ (make -j) ==
  [ OK ] build kernel/kernel + fs.img thÃ nh cÃ´ng (272K kernel)

== Boot smoke (QEMU, CPUS=1) ==
  --- [1/1] boot-smoke (CPUS=1) ... PASS (3.6s)
  [ OK ] QEMU boot xv6 vÃ  shell tráº£ lá»i

== MÃ”I TRÆ¯á»œNG Sáº´N SÃ€NG (cáº£nh bÃ¡o: 0) ==
```

Äiá»u kiá»‡n Ä‘áº¡t: dÃ²ng cuá»‘i `MÃ”I TRÆ¯á»œNG Sáº´N SÃ€NG` vÃ  **khÃ´ng cÃ³ `[FAIL]`**.
Náº¿u cÃ³ `[FAIL]` â†’ xem báº£ng sá»± cá»‘ á»Ÿ má»¥c 8.

## 4. Boot thá»­ xv6

```bash
make qemu             # CPUS=3 máº·c Ä‘á»‹nh
make qemu CPUS=1      # báº¯t buá»™c thá»­ cáº£ 1 vÃ  4 theo spec
make qemu CPUS=4
```

Káº¿t quáº£ máº«u trÃªn serial console (bÃªn trong QEMU):

```text
xv6 kernel is booting

init: starting sh
$ echo BOOT_OK
BOOT_OK
$
```

ThoÃ¡t QEMU: `Ctrl-A` rá»“i `X`. (Hoáº·c `bash scripts/run-qemu.sh --timeout 15`
Ä‘á»ƒ tá»± kill sau 15 giÃ¢y, dÃ¹ng cho CI/ghi log.)

## 5. Test harness â€” PASS/FAIL tá»«ng case

```bash
make test-fast        # 2 case, ~8 giÃ¢y
make list-tests       # xem toÃ n bá»™ case sáº½ cháº¡y
make test             # suite máº·c Ä‘á»‹nh, ~10â€“20 phÃºt trÃªn QEMU TCG
```

Káº¿t quáº£ máº«u:

```text
== ET4290 test runner â€” 2 case ==
   káº¿t quáº£: /home/<user>/ET4290/results/local/tests-2026-10-21_214921
--- [1/2] boot-smoke (CPUS=1) ... PASS (3.1s)
--- [2/2] shell-fs-cpus3 (CPUS=3) ... PASS (4.1s)

== Káº¿t quáº£: 2 PASS / 0 FAIL ==
```

Káº¿t quáº£ náº±m trong `results/local/<timestamp>/` (`summary.md`, `meta.json`,
`logs/<case>.log`) â€” **khÃ´ng** commit (Ä‘Ã£ gitignore).

## 6. Baseline riÃªng cho mÃ¡y nÃ y (khuyáº¿n nghá»‹)

```bash
make baseline         # build sáº¡ch + usertests -q CPUS=1/4 + grind 60s Ã—2
```

Káº¿t quáº£ vÃ o `results/baseline/<timestamp>/`; máº¥t **10â€“25 phÃºt tÃ¹y mÃ¡y**.
Sá»‘ liá»‡u **khÃ¡c mÃ¡y dev lÃ  bÃ¬nh thÆ°á»ng** â€” chá»‰ so sÃ¡nh giá»¯a cÃ¡c láº§n Ä‘o cÃ¹ng mÃ¡y,
cÃ¹ng QEMU command line. Giá»¯ láº§n cháº¡y má»›i, khÃ´ng ghi Ä‘Ã¨ láº§n cÅ©.

> Khi baseline xong: ghi hash commit + version toolchain (trong `meta.json`) vÃ o
> bÃ¡o cÃ¡o tuáº§n Ä‘á»ƒ cáº£ nhÃ³m Ä‘á»‘i chiáº¿u.

## 7. LÃ m viá»‡c háº±ng ngÃ y

```bash
git pull                          # láº¥y code má»›i cá»§a nhÃ³m
make env-check                    # náº¿u vá»«a pull/Ä‘á»•i tag xv6
make qemu CPUS=4                  # phÃ¡t triá»ƒn
make test-fast                    # sau má»—i thay Ä‘á»•i nhá» (~8s)
make test                         # trÆ°á»›c khi commit lá»›n/PR (~10â€“20 phÃºt)
make baseline                     # khi cáº§n sá»‘ liá»‡u so sÃ¡nh
```

## 8. Quan tÃ¢m nhá»¯ng gÃ¬ (quan trá»ng nháº¥t)

1. **ÄÃºng commit** â€” ghi `git rev-parse HEAD` + ná»™i dung `.xv6-commit`. KhÃ´ng so
   sá»‘ liá»‡u giá»¯a hai mÃ¡y khÃ¡c commit/toolchain; Ä‘Ã³ lÃ  lá»—i hay bá»‹ báº¯t trong bÃ¡o cÃ¡o.
2. **QEMU â‰¥ 7.2** â€” Makefile cháº·n náº¿u tháº¥p hÆ¡n. Ubuntu 22.04 máº·c Ä‘á»‹nh 6.2 â†’ dÃ¹ng
   Æ°u tiÃªn 24.04.
3. **CÃ¹ng toolchain** â€” `make env-check` in ra version; chá»¥p láº¡i vÃ o bÃ¡o cÃ¡o tuáº§n
   (T1-05 yÃªu cáº§u cáº£ ba lÆ°u git hash, compiler, QEMU, OS).
4. **TCG vs KVM** â€” laptop Ubuntu cÃ³ thá»ƒ cÃ³ `/dev/kvm`; hiá»‡n dÃ¹ng TCG (nhÆ° Makefile)
   nÃªn sá»‘ liá»‡u tuyá»‡t Ä‘á»‘i phá»¥ thuá»™c mÃ¡y. Muá»‘n nhanh hÆ¡n cÃ³ thá»ƒ tá»± thÃªm `-accel kvm`
   khi cháº¡y QEMU thá»§ cÃ´ng, nhÆ°ng **khÃ´ng** trá»™n cáº¥u hÃ¬nh khi so sÃ¡nh.
5. **KhÃ´ng commit build artifacts** â€” `fs.img`, `kernel/kernel`, `*.o`â€¦ Ä‘Ã£ gitignore.
6. **Repo private** â€” khÃ´ng Ä‘Æ°a token/PAT vÃ o log/README; dÃ¹ng credential helper.
7. **KhÃ´ng sá»­a Ä‘á»ƒ "cháº¡y Ä‘Æ°á»£c trÃªn mÃ¡y tÃ´i"** â€” náº¿u build fail, sá»­a mÃ´i trÆ°á»ng
   (cÃ i package/Ä‘á»•i QEMU), khÃ´ng sá»­a Makefile/source Ä‘á»ƒ lÃ¡ch; má»i thay Ä‘á»•i pháº£i qua PR.
8. **Thá»i gian** â€” QEMU TCG cháº­m; Ä‘á»«ng báº­t `make test` rá»“i Ä‘i lÃ m viá»‡c khÃ¡c rá»“i
   tÆ°á»Ÿng treo. `usertests -q` ~8â€“10 phÃºt/cáº¥u hÃ¬nh lÃ  bÃ¬nh thÆ°á»ng.

## 9. Sá»± cá»‘ thÆ°á»ng gáº·p

| Triá»‡u chá»©ng | NguyÃªn nhÃ¢n | Xá»­ lÃ½ |
| --- | --- | --- |
| `Couldn't find a riscv64 version of GCC/binutils` | thiáº¿u toolchain | `sudo bash scripts/setup-env.sh` |
| `Need qemu version >= 7.2` | QEMU cÅ© (Ubuntu 22.04) | nÃ¢ng lÃªn Ubuntu 24.04 / cÃ i QEMU má»›i hÆ¡n |
| `make: bc: No such file or directory` | thiáº¿u `bc` | `sudo apt install bc` |
| `Permission denied` khi clone | chÆ°a Ä‘Äƒng nháº­p GitHub cho repo private | `gh auth login` hoáº·c SSH key |
| `apt-get update` lá»—i máº¡ng/IPv6 | máº¡ng chá»‰ IPv6 lá»—i | script Ä‘Ã£ tá»± thá»­ IPv4; hoáº·c `-o Acquire::ForceIPv4=true` |
| QEMU Ä‘á»©ng á»Ÿ "xv6 kernel is booting" | hiáº¿m: `fs.img` há»ng/CPU Ã­t | `make clean && make`, thá»­ `CPUS=1` |
| `make fmt` lá»—i `invalid boolean` | `.clang-format` upstream cáº§n clang-format â‰¥ 19 | khÃ´ng báº¯t buá»™c; xem environment.md |
| Build cháº­m | QEMU TCG + Ã­t CPU | bÃ¬nh thÆ°á»ng; build kernel chá»‰ ~2â€“5 giÃ¢y, cháº­m lÃ  pháº§n QEMU/USERTESTS |
| `results/local` khÃ´ng tháº¥y trong git status | Ä‘Ãºng thiáº¿t káº¿ | log cháº¡y thá»­ bá»‹ gitignore; chá»‰ `results/baseline` Ä‘Æ°á»£c commit |

## 10. Cháº¡y demo Ä‘á»ƒ tá»± kiá»ƒm tra / demo GV

```bash
make demo               # 6 pháº§n: mÃ´i trÆ°á»ng â†’ build â†’ boot â†’ test â†’ baseline â†’ háº¡ táº§ng
make demo DEMO_ARGS=--no-qemu     # chá»‰ in thÃ´ng tin, khÃ´ng cháº¡y QEMU
```

Ká»‹ch báº£n demo Ä‘áº§y Ä‘á»§ cho giáº£ng viÃªn: [demo.md](demo.md).

