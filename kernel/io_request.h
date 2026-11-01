//
// kernel/io_request.h
// W2-G01 contract: asynchronous block READ request layer for xv6-riscv.
//
// Implemented by the integrated week-2 request, queue and driver layers. This header is
// the single source of truth for the week-2 async interface, buffer ownership
// and locking rules. The prose contract is docs/week02/interface.md; if the two
// ever disagree, fix both in the same PR.
//
// Who implements what (week 2):
//   io_request.c  - pool/state/handle, poll/wait/release, stats   (Hiếu, W2-I01/I02)
//   io_queue.c    - pending queue, FCFS dispatcher, enqueue_seq   (Lợi,  W2-L01)
//   virtio_disk.c - try-submit READ, descriptor owner/reclaim,
//                   IRQ completion, io_lock accessor             (Hoàng, W2-H01/H02)
//
// MVP scope (chốt, không mở rộng trong tuần 2):
//   - kernel-level C API only, no user syscall;
//   - READ one block, BSIZE = 1024 bytes, one device (ROOTDEV);
//   - FCFS queue; WRITE/log keeps the stock synchronous path;
//   - the async READ path does NOT replace bread() (buffer-cache coherence is
//     an open design item); tests read a fixed, read-only fixture.
//
// Locking: exactly one spinlock in this prototype, called io_lock and owned by
// the virtio driver (virtio_disk_io_lock()). It protects the request pool, the
// pending queue, request states, the descriptor allocator/rings/owner map and
// b->disk. There is no second async lock and no nested io lock. Functions whose
// name ends in _locked must be called with io_lock already held; they must not
// acquire it again. Never sleep while holding io_lock: follow
//   sleep_prepare(chan); release(io_lock); sleep(); acquire(io_lock);
// The detailed lock table and error contract are in docs/week02/interface.md.
//
#ifndef _IO_REQUEST_H_
#define _IO_REQUEST_H_

// Include order (xv6 convention: headers do not include each other):
//   types.h, param.h, fs.h (BSIZE), spinlock.h, then this header.
// This keeps the project aligned with buf.h/virtio.h and avoids double-including
// upstream headers that have no include guards.
struct spinlock; // defined in spinlock.h; only a pointer is used here

// Number of software request slots. Finite on purpose: a full pool must return
// IO_EAGAIN, not sleep, not panic. Slot bytes: 16 * sizeof(struct io_request)
// = 16 * 1080 B = 17 280 B (~16.9 KiB) of static BSS; no kalloc on this path.
// This is an example value from the week-2 plan, fixed by the contract until
// re-measured; changing it is a contract change.
#define IO_NREQ 16

// The async MVP transfers exactly one on-disk block per request.
#if BSIZE != 1024
#error "io_request.h: async READ MVP requires BSIZE == 1024"
#endif

// Public address unit is blockno (not sector). The only conversion for async
// requests happens in virtio_disk_try_submit_read(): sector = blockno * 2 on the
// pinned driver. Do not multiply twice: the request layer never stores sector.
#define IO_SECTORS_PER_BLOCK (BSIZE / 512)

// Sentinel for "no queue link" / "no descriptor head".
#define IO_NIL (-1)

// Negative return codes used by this API. Values match Linux/xv6 user errno so a
// future syscall layer can translate them, but the kernel does not include
// <errno.h> (none exists in xv6). Callers must treat only 0 as success.
#define IO_EINVAL (-22) // bad argument (dev/blockno/handle pointer)
#define IO_ENODEV (-19) // dev != ROOTDEV (one device in the MVP)
#define IO_ERANGE (-34) // blockno >= FSSIZE (outside device capacity)
#define IO_ENOENT (-2)  // stale/invalid handle (id/gen mismatch or free slot)
#define IO_EAGAIN (-11) // transient resource shortage (pool full); retry later
#define IO_EIO    (-5)  // terminal device error (virtio status != 0)
#define IO_EBUSY  (-16) // release/wait refused while the request is still live

// Request lifecycle (single global spinlock protects all of it):
//   FREE -> ALLOCATED -> QUEUED -> INFLIGHT -> DONE | ERROR -> FREE
// ALLOCATED is a transient state inside aio_read_submit() and is never observed
// by another CPU. DONE/ERROR still occupy a pool slot until aio_release().
enum io_state {
  IO_SLOT_FREE = 0,
  IO_ALLOCATED,
  IO_QUEUED,
  IO_INFLIGHT,
  IO_DONE,
  IO_ERROR,
};

// Operation tag. The MVP accepts only IO_OP_READ; the field exists so a later
// WRITE/merge extension does not change the struct layout.
enum io_op {
  IO_OP_READ = 0,
  IO_OP_WRITE = 1,
};

// Owner tag stored by the driver per descriptor chain head. Exactly one owner
// may reclaim a chain: async = IRQ, stock = the caller of virtio_disk_rw().
enum io_head_owner {
  IO_HEAD_FREE = 0,
  IO_HEAD_STOCK,
  IO_HEAD_ASYNC,
};

// Handle returned to the caller. The caller must present the same (id, gen)
// pair to every later call; a stale handle is rejected, never dereferenced.
struct io_handle {
  int id;   // 0 .. IO_NREQ-1
  uint gen; // slot generation at submit time (>= 1)
};

// One pool slot + its private DMA staging buffer. The pool owns both; the
// caller never supplies or frees a buffer. Layout is a contract: fields may be
// appended, but existing fields must not be reordered silently.
struct io_request {
  int id;                // index in io_pool[], stable for slot lifetime
  uint gen;              // bumped on every release; never 0
  enum io_state state;   // see enum io_state; protected by io_lock
  enum io_op op;         // IO_OP_READ in the MVP
  int status;            // 0 = OK; >0 virtio device status; <0 internal error
  uint dev;              // ROOTDEV
  uint blockno;          // public unit; sector derived once in the driver
  uint enqueue_seq;      // FCFS order, monotonic, assigned by io_queue.c
  int next;              // pending-queue link (index or IO_NIL)
  int head;              // virtio descriptor head while INFLIGHT, else IO_NIL
  uint t_enqueue;        // debug/measurement, ticks at enqueue
  uint t_dispatch;       // debug/measurement, ticks at publish
  uint t_complete;       // debug/measurement, ticks at terminal state
  uint waiters;          // 0 or 1 in the MVP (single consumer contract)
  uchar data[BSIZE];     // DMA staging buffer, stable address (inside pool BSS)
};

// Request-layer counters for tests T02/T03/T11. Filled by io_get_stats() in
// process context; io_get_stats() takes io_lock itself.
struct io_stats {
  uint submitted;     // successful aio_read_submit() calls (handles handed out)
  uint completed;     // requests that reached DONE
  uint errors;        // requests that reached ERROR
  uint queued;        // current QUEUED count (snapshot)
  uint inflight;      // current INFLIGHT count (snapshot)
  uint max_inflight;  // high-water mark since boot (evidence for R01)
  uint free_req;      // IO_NREQ - (submitted - released)
  uint eagain_pool;   // rejected submits due to a full pool
  uint stale_handle;  // calls rejected with IO_ENOENT
  uint released;      // cumulative terminal slots released (not a gauge)
  uint done;          // current DONE slots, still owned until release
  uint error;         // current ERROR slots, still owned until release
};

// Driver counters for T08/T11 (owner: W2-H02). Filled in process context by
// virtio_disk_get_stats(), which takes io_lock itself.
struct io_desc_stats {
  uint free_desc;       // current free descriptor count, 0..NUM
  uint eagain_desc;     // try-submit attempts that lacked 3 descriptors
  uint completed_stock; // used-ring entries owned by the stock path
  uint completed_async; // used-ring entries owned by the async path
  uint head_reuse;      // async heads re-published before caller release (T08)
};

// ---------------------------------------------------------------------------
// Public async API (kernel context). Implemented in kernel/io_request.c.
// Context: process context unless stated otherwise. None of these may be called
// with io_lock held; each takes the lock itself.
// ---------------------------------------------------------------------------

// One-time boot init: zero the pool, init stats, init the pending queue.
// Called from main() once, after virtio_disk_init() and before userinit().
// Context: boot CPU, no concurrency; may take io_lock. No allocation, no sleep
// beyond initlock-free boot activity.
void io_init(void);

// Submit one READ of blockno on device dev. Returns 0 on success (handle stored
// in *out) or a negative IO_E* code. On any error *out is left untouched.
// - IO_EINVAL: out == 0, dev/blockno invalid form
// - IO_ENODEV: dev != ROOTDEV
// - IO_ERANGE: blockno >= FSSIZE
// - IO_EAGAIN: pool full (free_req == 0); no slot consumed, counters unchanged
// The request may already be INFLIGHT or still QUEUED when this returns; this
// call never waits for the device.
int aio_read_submit(uint dev, uint blockno, struct io_handle *out);

// Non-blocking status check. Returns 1 for DONE, 0 for QUEUED/INFLIGHT,
// IO_EIO for ERROR, or IO_E* for an invalid/stale handle. Never sleeps, never
// frees the slot, never modifies the request.
int aio_poll(struct io_handle h);

// Wait for terminal state and return 0 for DONE or IO_EIO for ERROR. Returns
// immediately if the request already completed (complete-before-wait). Process
// context only; returns IO_EINVAL if called with no current process. Does NOT
// release the request; the caller must still call aio_release(). Never sleeps
// while holding io_lock; uses the sleep_prepare/release/sleep/acquire pattern.
// A second concurrent aio_wait() on the same handle returns IO_EBUSY (single
// consumer in the MVP).
int aio_wait(struct io_handle h);

// Release a terminal request back to the pool. Returns 0, or:
// - IO_EBUSY: state is QUEUED/INFLIGHT, or waiters != 0
// - IO_E*: invalid/stale handle
// On success: state -> FREE, generation bumped (never 0), handle becomes stale,
// the data pointer from aio_data() is invalid from this point on.
int aio_release(struct io_handle h);

// Return the request's staging buffer (BSIZE bytes) only in DONE; NULL for
// pending/error/invalid handles. The pointer stays valid until aio_release().
// Contents are defined only after DONE (aio_wait()==0 / aio_poll()==1) and the
// caller must treat them as read-only; the pool frees the slot, not the caller.
void *aio_data(struct io_handle h);

// Fill *out with request-layer counters. Process context; takes io_lock.
void io_get_stats(struct io_stats *out);

// Snapshot of driver counters (descriptor pressure, owner split, head reuse).
// Process context; takes io_lock. Implemented in virtio_disk.c by W2-H02.
void virtio_disk_get_stats(struct io_desc_stats *out);

// ---------------------------------------------------------------------------
// Request-layer internal helpers (W2-I01, implemented in kernel/io_request.c).
// Callers MUST hold io_lock; the _locked suffix states that precondition.
// These are the primitives that aio_read_submit()/aio_poll()/aio_wait()/
// aio_release() (W2-I02) and the kernel sefltest build on. They never sleep,
// never allocate and never touch the device.
// ---------------------------------------------------------------------------

// Pick a FREE slot, mark it IO_ALLOCATED, initialise every field (staging
// buffer zeroed, head/next = IO_NIL) and return it. The generation is NOT
// bumped here: it belongs to the slot and changes only on release, so a handle
// from an older occupancy stays stale across reuse.
// Returns NULL when all IO_NREQ slots are in use and increments
// stats.eagain_pool; the caller maps that to IO_EAGAIN.
struct io_request *io_alloc_slot_locked(void);

// Validate (id in range, slot in use, generation match) and return the slot.
// Never dereferences an out-of-range index. Returns NULL for a stale/invalid
// handle and increments stats.stale_handle; callers map that to IO_ENOENT.
struct io_request *io_lookup_handle_locked(struct io_handle h);

// Release a terminal slot (DONE/ERROR only, waiters == 0) back to the pool:
// bump the generation (never 0), reset the slot to FREE, invalidate the handle.
// Returns 0, IO_EBUSY (still live or has a waiter) or IO_ENOENT (stale).
// Descriptor chains are already reclaimed by the IRQ before DONE, so this
// function never touches virtqueue state (contract D7).
int io_release_locked(struct io_handle h);

// ---------------------------------------------------------------------------
// Request <-> queue contract. Implemented in kernel/io_queue.c (W2-L01).
// All *_locked functions require io_lock held; they never sleep or allocate.
// ---------------------------------------------------------------------------

// One-time queue init (called by io_init()).
void io_queue_init(void);

// Append req to the FCFS pending queue: state = QUEUED, monotonic enqueue_seq,
// next link. Caller has already validated fields. Context: io_lock held.
void io_queue_enqueue_locked(struct io_request *req);

// Dispatch as many QUEUED requests as the driver accepts, in enqueue_seq order.
// Stops at the first IO_EAGAIN (keeps the request at the head, keeps its
// enqueue_seq) and never busy-spins. Must be called with io_lock held from:
//   1. aio_read_submit() after enqueue,
//   2. virtio_disk_intr() after a completion was handled and its chain reclaimed,
//   3. virtio_disk_rw() after the stock caller reclaims its chain (W2-H02/G02).
void io_dispatch_locked(void);

// Current number of QUEUED requests. Context: io_lock held.
int io_queue_count_locked(void);

// ---------------------------------------------------------------------------
// Request <-> driver contract. Implemented in kernel/virtio_disk.c (W2-H01/H02)
// and kernel/io_request.c (completion callback). All _locked functions require
// io_lock held; the IRQ path must not sleep, allocate, copyin/copyout or printk.
// ---------------------------------------------------------------------------

// THE single lock domain for the async prototype: returns &disk.vdisk_lock.
// It is the same lock the stock driver and virtio_disk_intr() already use, so
// there is exactly one lock and no lock-order inversion between queue and driver.
// Implemented by W2-H01; callable after virtio_disk_init().
struct spinlock *virtio_disk_io_lock(void);

// Try to publish req (already QUEUED, op READ, blockno set) as one 3-descriptor
// chain (header/data/status). On success sets state = INFLIGHT, req->head and
// the per-head owner map BEFORE publishing to the avail ring, fences, notifies
// the device and returns 0. On shortage of descriptors it rolls back every
// descriptor it took, leaves the request untouched (still QUEUED) and returns
// IO_EAGAIN. Never sleeps, never partially publishes. Context: io_lock held,
// process or IRQ context (the dispatcher runs from both); never sleeps.
int virtio_disk_try_submit_read(struct io_request *req);

// Complete one async request that the driver just reaped from the used ring.
// The driver has already validated the head->request mapping and copied the
// 1-byte device status into dev_status. Sets DONE (dev_status == 0) or ERROR,
// records req->status/t_complete, bumps completed/errors, wakeup(req). Does not
// touch descriptors and does not dispatch; the caller handles the chain and
// then calls io_dispatch_locked(). IRQ context, io_lock held, no sleep.
void io_async_completed_locked(struct io_request *req, int dev_status);

// Driver transition before publishing the chain. Same io_lock held; updates
// max_inflight while simultaneous INFLIGHT states are still observable.
void io_started_locked(struct io_request *req, int head);

#ifdef IO_HW_SELFTEST
// Test-only controls over real device completions. Holding used processing
// does not prevent DMA: buffers/chains stay live until actual reaping.
void virtio_test_hold_used(int hold);
uint virtio_test_used_count(void);
void virtio_test_reverse_pair(void);
uint virtio_test_reversed(void);
void virtio_test_status(struct io_handle h, int status);
void virtio_test_unhold_locked(void);
void io_hw_set_wait_hook(void (*fn)(void));
int io_hw_selftest(void);
#endif

// ---------------------------------------------------------------------------
// TEST-ONLY hooks for `make test-io` (W2-I02). Compiled only with
// -DIO_SELFTEST; never present in a production kernel. They let the kernel
// selftest drive completion deterministically without a real device/IRQ:
//   - a one-shot hook called INSIDE aio_wait(), after sleep_prepare() and
//     before release()+sleep(), to exercise the lost-wakeup window (T06a);
//   - a timer-tick completion so a real sleeping waiter is woken by an
//     interrupt (T06b, controlled by a tick countdown, not a lucky delay);
//   - a flag the selftest uses to prove the sleep path was entered.
// ---------------------------------------------------------------------------
#ifdef IO_SELFTEST
// fn(req) runs with io_lock held, in process context, must not sleep.
void io_test_set_wait_hook(void (*fn)(struct io_request *));
// Arm completion of h after delay_ticks timer ticks (status 0 = DONE, else
// ERROR). Must be called from process context; the request must be INFLIGHT.
void io_test_arm_timer_completion(struct io_handle h, int status, int delay_ticks);
// 1 if the last aio_wait() reached the sleep() path; clears the flag.
int io_test_take_slept_flag(void);
// Called from clockintr() on every timer tick in a -DIO_SELFTEST build.
void io_test_timer_tick(void);
#endif

#endif // _IO_REQUEST_H_
