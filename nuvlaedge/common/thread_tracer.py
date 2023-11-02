import sys
import threading
import traceback
import faulthandler


def log_threads_stacks_traces():
    print_args = dict(file=sys.stderr, flush=True)
    print("\nfaulthandler.dump_traceback()", **print_args)
    faulthandler.dump_traceback()
    print("\nthreading.enumerate()", **print_args)
    for th in threading.enumerate():
        print(th, **print_args)
        traceback.print_stack(sys._current_frames()[th.ident])
    print(**print_args)


def signal_usr1(signum, frame):
    log_threads_stacks_traces()
